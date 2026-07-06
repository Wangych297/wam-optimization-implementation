import argparse
import csv
import io
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F
from torchvision.transforms import functional as TVF
from torchvision.utils import save_image


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wam-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--mask-ratio", type=float, default=0.5)
    parser.add_argument("--save-visuals", action="store_true")
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def psnr_tensor(a: torch.Tensor, b: torch.Tensor) -> float:
    a = a.detach().clamp(0, 1)
    b = b.detach().clamp(0, 1)
    mse = torch.mean((a - b) ** 2).item()
    if mse <= 1e-12:
        return 99.0
    return float(20.0 * np.log10(1.0 / np.sqrt(mse)))


def tensor_to_pil(img_norm: torch.Tensor, unnormalize_img) -> Image.Image:
    img01 = unnormalize_img(img_norm.detach().cpu()).squeeze(0).clamp(0, 1)
    return TVF.to_pil_image(img01)


def pil_to_tensor(img: Image.Image, default_transform, device) -> torch.Tensor:
    return default_transform(img.convert("RGB")).unsqueeze(0).to(device)


def apply_jpeg(img_norm, q, default_transform, unnormalize_img, device):
    img = tensor_to_pil(img_norm, unnormalize_img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(q))
    buf.seek(0)
    return pil_to_tensor(Image.open(buf), default_transform, device)


def apply_resize(img_norm, scale, default_transform, unnormalize_img, device):
    img = tensor_to_pil(img_norm, unnormalize_img)
    w, h = img.size
    small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BICUBIC)
    restored = small.resize((w, h), Image.BICUBIC)
    return pil_to_tensor(restored, default_transform, device)


def apply_center_crop(img_norm, ratio, default_transform, unnormalize_img, device):
    img = tensor_to_pil(img_norm, unnormalize_img)
    w, h = img.size
    cw, ch = max(1, int(w * ratio)), max(1, int(h * ratio))
    left = (w - cw) // 2
    top = (h - ch) // 2
    cropped = img.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BICUBIC)
    return pil_to_tensor(cropped, default_transform, device)


def apply_random_crop(img_norm, ratio, default_transform, unnormalize_img, device, rng):
    img = tensor_to_pil(img_norm, unnormalize_img)
    w, h = img.size
    cw, ch = max(1, int(w * ratio)), max(1, int(h * ratio))
    left = rng.randint(0, max(0, w - cw))
    top = rng.randint(0, max(0, h - ch))
    cropped = img.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BICUBIC)
    return pil_to_tensor(cropped, default_transform, device)


def apply_occlusion(img_norm, ratio, default_transform, unnormalize_img, device, rng):
    img01 = unnormalize_img(img_norm.detach().clone()).clamp(0, 1)
    _, _, h, w = img01.shape
    area = int(h * w * ratio)
    side = max(1, int(area ** 0.5))
    oh, ow = min(h, side), min(w, side)
    top = rng.randint(0, max(0, h - oh))
    left = rng.randint(0, max(0, w - ow))
    img01[:, :, top : top + oh, left : left + ow] = 0.0
    img = TVF.to_pil_image(img01.squeeze(0).detach().cpu())
    return pil_to_tensor(img, default_transform, device)


def apply_partial_removal(img_w_norm, img_orig_norm, ratio, default_transform, unnormalize_img, device, rng):
    wm01 = unnormalize_img(img_w_norm.detach().clone()).clamp(0, 1)
    orig01 = unnormalize_img(img_orig_norm.detach().clone()).clamp(0, 1)
    _, _, h, w = wm01.shape
    area = int(h * w * ratio)
    side = max(1, int(area ** 0.5))
    oh, ow = min(h, side), min(w, side)
    top = rng.randint(0, max(0, h - oh))
    left = rng.randint(0, max(0, w - ow))
    wm01[:, :, top : top + oh, left : left + ow] = orig01[:, :, top : top + oh, left : left + ow]
    img = TVF.to_pil_image(wm01.squeeze(0).detach().cpu())
    return pil_to_tensor(img, default_transform, device)


def decode(wam, attacked, target_msg, msg_predict_inference):
    preds = wam.detect(attacked)["preds"]
    mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
    bit_preds = preds[:, 1:, :, :]
    mask_binary_count = int((mask_preds > 0.5).sum().item())
    if mask_binary_count < 8:
        return {
            "pred": torch.zeros_like(target_msg),
            "bit_accuracy": 0.0,
            "mask_mean": float(mask_preds.mean().item()),
            "mask_pixels": mask_binary_count,
            "used_fallback": 1,
        }
    pred_message = msg_predict_inference(bit_preds, mask_preds, method="semihard").float()
    bit_acc = float((pred_message == target_msg).float().mean().item())
    return {
        "pred": pred_message,
        "bit_accuracy": bit_acc,
        "mask_mean": float(mask_preds.mean().item()),
        "mask_pixels": mask_binary_count,
        "used_fallback": 0,
    }


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)

    wam_root = Path(args.wam_root).resolve()
    sys.path.insert(0, str(wam_root))
    sys.path.insert(0, str(wam_root / "notebooks"))
    os.chdir(wam_root)

    from inference_utils import create_random_mask, load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference
    from watermark_anything.data.transforms import default_transform, unnormalize_img

    out_dir = Path(args.out_dir).resolve()
    vis_dir = out_dir / "visuals"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.save_visuals:
        vis_dir.mkdir(parents=True, exist_ok=True)

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

    attacks = [("none", None)]
    attacks += [(f"jpeg_q{q}", ("jpeg", q)) for q in (95, 85, 75, 65, 50, 30)]
    attacks += [(f"resize_{s}", ("resize", s)) for s in (0.75, 0.5, 0.25)]
    attacks += [(f"center_crop_{r}", ("center_crop", r)) for r in (0.9, 0.75, 0.5)]
    attacks += [(f"random_crop_{r}", ("random_crop", r)) for r in (0.9, 0.75, 0.5)]
    attacks += [(f"occlusion_{r}", ("occlusion", r)) for r in (0.05, 0.1, 0.2)]
    attacks += [(f"partial_removal_{r}", ("partial_removal", r)) for r in (0.05, 0.1, 0.2)]

    fieldnames = [
        "image",
        "attack",
        "message",
        "predicted",
        "bit_accuracy",
        "message_success",
        "psnr_vs_original",
        "mask_mean",
        "mask_pixels",
        "used_fallback",
    ]
    rows = []
    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={msg_to_str(target_msg)}", flush=True)

    with torch.inference_mode():
        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = default_transform(img).unsqueeze(0).to(device)
            outputs = wam.embed(img_pt, target_msg)
            mask = create_random_mask(img_pt, num_masks=1, mask_percentage=args.mask_ratio)
            img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

            for attack_name, spec in attacks:
                if spec is None:
                    attacked = img_w
                elif spec[0] == "jpeg":
                    attacked = apply_jpeg(img_w, spec[1], default_transform, unnormalize_img, device)
                elif spec[0] == "resize":
                    attacked = apply_resize(img_w, spec[1], default_transform, unnormalize_img, device)
                elif spec[0] == "center_crop":
                    attacked = apply_center_crop(img_w, spec[1], default_transform, unnormalize_img, device)
                elif spec[0] == "random_crop":
                    attacked = apply_random_crop(img_w, spec[1], default_transform, unnormalize_img, device, rng)
                elif spec[0] == "occlusion":
                    attacked = apply_occlusion(img_w, spec[1], default_transform, unnormalize_img, device, rng)
                elif spec[0] == "partial_removal":
                    attacked = apply_partial_removal(img_w, img_pt, spec[1], default_transform, unnormalize_img, device, rng)
                else:
                    raise ValueError(spec)

                decoded = decode(wam, attacked, target_msg, msg_predict_inference)
                row = {
                    "image": image_path.name,
                    "attack": attack_name,
                    "message": msg_to_str(target_msg),
                    "predicted": msg_to_str(decoded["pred"]),
                    "bit_accuracy": f"{decoded['bit_accuracy']:.6f}",
                    "message_success": int(decoded["bit_accuracy"] >= 0.999),
                    "psnr_vs_original": f"{psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt)):.4f}",
                    "mask_mean": f"{decoded['mask_mean']:.6f}",
                    "mask_pixels": decoded["mask_pixels"],
                    "used_fallback": decoded["used_fallback"],
                }
                rows.append(row)
                print(row, flush=True)

                if args.save_visuals and image_path == image_paths[0]:
                    base = image_path.stem
                    save_image(unnormalize_img(attacked), vis_dir / f"{base}_{attack_name}.png")

    csv_path = out_dir / "wam_attack_eval_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {}
    for row in rows:
        attack = row["attack"]
        summary.setdefault(attack, []).append(float(row["bit_accuracy"]))
    summary_path = out_dir / "wam_attack_eval_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["attack", "mean_bit_accuracy", "min_bit_accuracy", "num_images"])
        writer.writeheader()
        for attack, vals in summary.items():
            writer.writerow({
                "attack": attack,
                "mean_bit_accuracy": f"{np.mean(vals):.6f}",
                "min_bit_accuracy": f"{np.min(vals):.6f}",
                "num_images": len(vals),
            })

    print(f"metrics={csv_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
