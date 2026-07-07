import argparse
import csv
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F
from torchvision.utils import save_image


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mask-ratio", type=float, default=0.5)
    parser.add_argument("--multi-count", type=int, default=2)
    parser.add_argument("--multi-mask-ratio", type=float, default=0.1)
    return parser.parse_args()


def psnr_tensor(a: torch.Tensor, b: torch.Tensor) -> float:
    a = a.detach().clamp(0, 1)
    b = b.detach().clamp(0, 1)
    mse = torch.mean((a - b) ** 2).item()
    if mse <= 1e-12:
        return 99.0
    return float(20.0 * np.log10(1.0 / np.sqrt(mse)))


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    run_root = Path(args.project_root).resolve()
    sys.path.insert(0, str(run_root))
    sys.path.insert(0, str(run_root / "notebooks"))
    os.chdir(run_root)

    from inference_utils import create_random_mask, load_model_from_checkpoint, multiwm_dbscan
    from watermark_anything.data.metrics import msg_predict_inference
    from torchvision import transforms as T
    from watermark_anything.data.transforms import default_transform, unnormalize_img

    inference_transform = T.Compose([
        T.Resize(256),
        T.CenterCrop(256),
        default_transform,
    ])

    out_dir = Path(args.out_dir).resolve()
    vis_dir = out_dir / "visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "baseline_reproduction_metrics.csv"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)
    if device.type == "cuda":
        print(f"gpu={torch.cuda.get_device_name(0)}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()

    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]
    if not image_paths:
        raise RuntimeError(f"No images found under {args.image_dir}")

    fieldnames = [
        "mode",
        "image",
        "message",
        "predicted",
        "bit_accuracy",
        "psnr",
        "mask_ratio",
        "num_detected_messages",
    ]
    rows = []

    with torch.inference_mode():
        fixed_msg = torch.randint(0, 2, (1, 32), device=device).float()
        print(f"single_message={msg_to_str(fixed_msg)}", flush=True)

        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = inference_transform(img).unsqueeze(0).to(device)

            outputs = wam.embed(img_pt, fixed_msg)
            mask = create_random_mask(img_pt, num_masks=1, mask_percentage=args.mask_ratio)
            img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

            preds = wam.detect(img_w)["preds"]
            mask_logits = preds[:, 0:1, :, :]
            mask_preds = torch.sigmoid(mask_logits)
            bit_preds = preds[:, 1:, :, :]
            pred_message = msg_predict_inference(bit_preds, mask_preds, method="semihard").float()
            bit_acc = (pred_message == fixed_msg).float().mean().item()

            base = image_path.stem
            mask_res = F.interpolate(mask_preds, size=img_pt.shape[-2:], mode="bilinear", align_corners=False)
            target_res = mask
            diff = (unnormalize_img(img_w) - unnormalize_img(img_pt)).abs() * 10.0
            save_image(unnormalize_img(img_pt), vis_dir / f"{base}_single_original.png")
            save_image(unnormalize_img(img_w), vis_dir / f"{base}_single_watermarked.png")
            save_image(mask_res, vis_dir / f"{base}_single_pred_mask.png")
            save_image(target_res, vis_dir / f"{base}_single_target_mask.png")
            save_image(diff.clamp(0, 1), vis_dir / f"{base}_single_diff_x10.png")

            row = {
                "mode": "single",
                "image": image_path.name,
                "message": msg_to_str(fixed_msg),
                "predicted": msg_to_str(pred_message),
                "bit_accuracy": f"{bit_acc:.6f}",
                "psnr": f"{psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt)):.4f}",
                "mask_ratio": args.mask_ratio,
                "num_detected_messages": "",
            }
            rows.append(row)
            print(row, flush=True)

        multi_messages = torch.randint(0, 2, (args.multi_count, 32), device=device).float()
        print("multi_messages=" + ",".join(msg_to_str(x) for x in multi_messages), flush=True)

        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = inference_transform(img).unsqueeze(0).to(device)
            masks = create_random_mask(
                img_pt,
                num_masks=args.multi_count,
                mask_percentage=args.multi_mask_ratio,
            )
            multi_wm_img = img_pt.clone()
            for idx in range(args.multi_count):
                msg = multi_messages[idx : idx + 1]
                outputs = wam.embed(img_pt, msg)
                mask = masks[idx : idx + 1]
                multi_wm_img = outputs["imgs_w"] * mask + multi_wm_img * (1 - mask)

            preds = wam.detect(multi_wm_img)["preds"]
            mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
            bit_preds = preds[:, 1:, :, :]
            centroids, labels = multiwm_dbscan(
                bit_preds,
                mask_preds,
                epsilon=1,
                min_samples=500,
            )

            detected = []
            best_acc = 0.0
            for centroid in centroids.values():
                centroid = centroid.to(device).float()
                accs = (centroid.unsqueeze(0) == multi_messages).float().mean(dim=1)
                best_acc = max(best_acc, float(accs.max().item()))
                detected.append(msg_to_str(centroid))

            base = image_path.stem
            mask_res = F.interpolate(mask_preds, size=img_pt.shape[-2:], mode="bilinear", align_corners=False)
            save_image(unnormalize_img(multi_wm_img), vis_dir / f"{base}_multi_watermarked.png")
            save_image(mask_res, vis_dir / f"{base}_multi_pred_mask.png")
            for idx, mask in enumerate(masks):
                save_image(mask, vis_dir / f"{base}_multi_target_mask_{idx}.png")

            row = {
                "mode": "multi",
                "image": image_path.name,
                "message": "|".join(msg_to_str(x) for x in multi_messages),
                "predicted": "|".join(detected),
                "bit_accuracy": f"{best_acc:.6f}",
                "psnr": f"{psnr_tensor(unnormalize_img(multi_wm_img), unnormalize_img(img_pt)):.4f}",
                "mask_ratio": args.multi_mask_ratio,
                "num_detected_messages": len(detected),
            }
            rows.append(row)
            print(row, flush=True)

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"metrics={csv_path}", flush=True)
    print(f"visuals={vis_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
