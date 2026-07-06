import argparse
import csv
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import torch


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=3579)
    parser.add_argument("--mask-ratio", type=float, default=0.5)
    parser.add_argument("--scales", nargs="+", type=float, default=[0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0])
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def decode(wam, attacked, target_msg, msg_predict_inference):
    preds = wam.detect(attacked)["preds"]
    mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
    bit_preds = preds[:, 1:, :, :]
    mask_pixels = int((mask_preds > 0.5).sum().item())
    if mask_pixels < 8:
        return torch.zeros_like(target_msg), 0.0, mask_pixels, 1
    pred = msg_predict_inference(bit_preds, mask_preds, method="semihard").float()
    acc = float((pred == target_msg).float().mean().item())
    return pred, acc, mask_pixels, 0


def resize_then_jpeg(img_norm, scale, quality, atk, default_transform, unnormalize_img, device):
    resized = atk.apply_resize(img_norm, scale, default_transform, unnormalize_img, device)
    return atk.apply_jpeg(resized, quality, default_transform, unnormalize_img, device)


def write_summary(rows, out_dir):
    grouped = {}
    for row in rows:
        key = (row["scaling_w"], row["attack"])
        grouped.setdefault(key, []).append(row)

    summary_path = out_dir / "strength_search_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scaling_w",
                "attack",
                "mean_bit_accuracy",
                "min_bit_accuracy",
                "mean_clean_psnr",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scale, attack), vals in sorted(grouped.items(), key=lambda item: (float(item[0][0]), item[0][1])):
            accs = [float(v["bit_accuracy"]) for v in vals]
            psnrs = [float(v["psnr_watermarked"]) for v in vals]
            writer.writerow({
                "scaling_w": scale,
                "attack": attack,
                "mean_bit_accuracy": f"{np.mean(accs):.6f}",
                "min_bit_accuracy": f"{np.min(accs):.6f}",
                "mean_clean_psnr": f"{np.mean(psnrs):.4f}",
                "num_images": len(vals),
            })

    overview = {}
    for row in rows:
        scale = row["scaling_w"]
        overview.setdefault(scale, {"psnr": [], "attacks": {}})
        overview[scale]["psnr"].append(float(row["psnr_watermarked"]))
        overview[scale]["attacks"].setdefault(row["attack"], []).append(float(row["bit_accuracy"]))

    overview_path = out_dir / "strength_search_overview.csv"
    attack_order = ["none", "jpeg_q50", "jpeg_q30", "jpeg_q20", "resize_0.25", "resize_0.25_jpeg_q50", "center_crop_0.5"]
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["scaling_w", "mean_clean_psnr", "mean_selected_attack_accuracy"] + [f"{name}_mean" for name in attack_order],
        )
        writer.writeheader()
        for scale in sorted(overview.keys(), key=float):
            data = overview[scale]
            attack_means = {}
            selected = []
            for attack in attack_order:
                vals = data["attacks"].get(attack, [])
                mean_val = float(np.mean(vals)) if vals else np.nan
                attack_means[attack] = mean_val
                if attack != "none" and vals:
                    selected.append(mean_val)
            row = {
                "scaling_w": scale,
                "mean_clean_psnr": f"{np.mean(data['psnr']):.4f}",
                "mean_selected_attack_accuracy": f"{np.mean(selected):.6f}" if selected else "",
            }
            for attack in attack_order:
                val = attack_means[attack]
                row[f"{attack}_mean"] = "" if np.isnan(val) else f"{val:.6f}"
            writer.writerow(row)

    return summary_path, overview_path


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
    from watermark_anything.extensions.attack_benchmark import run as atk

    run_root = Path(args.project_root).resolve()
    sys.path.insert(0, str(run_root))
    sys.path.insert(0, str(run_root / "notebooks"))
    os.chdir(run_root)

    from inference_utils import create_random_mask, load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference
    from watermark_anything.data.transforms import default_transform, unnormalize_img

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)
    if device.type == "cuda":
        print(f"gpu={torch.cuda.get_device_name(0)}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    original_scaling_w = float(wam.scaling_w)
    print(f"original_scaling_w={original_scaling_w}", flush=True)

    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]
    if not image_paths:
        raise RuntimeError(f"No images found under {args.image_dir}")

    attacks = [
        ("none", lambda img_w: img_w),
        ("jpeg_q50", lambda img_w: atk.apply_jpeg(img_w, 50, default_transform, unnormalize_img, device)),
        ("jpeg_q30", lambda img_w: atk.apply_jpeg(img_w, 30, default_transform, unnormalize_img, device)),
        ("jpeg_q20", lambda img_w: atk.apply_jpeg(img_w, 20, default_transform, unnormalize_img, device)),
        ("resize_0.5", lambda img_w: atk.apply_resize(img_w, 0.5, default_transform, unnormalize_img, device)),
        ("resize_0.25", lambda img_w: atk.apply_resize(img_w, 0.25, default_transform, unnormalize_img, device)),
        ("resize_0.25_jpeg_q50", lambda img_w: resize_then_jpeg(img_w, 0.25, 50, atk, default_transform, unnormalize_img, device)),
        ("center_crop_0.5", lambda img_w: atk.apply_center_crop(img_w, 0.5, default_transform, unnormalize_img, device)),
    ]

    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={msg_to_str(target_msg)}", flush=True)

    rows = []
    fieldnames = [
        "image",
        "scaling_w",
        "attack",
        "message",
        "predicted",
        "bit_accuracy",
        "message_success",
        "psnr_watermarked",
        "psnr_attacked",
        "mask_pixels",
        "used_fallback",
    ]

    with torch.inference_mode():
        cached_inputs = []
        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = default_transform(img).unsqueeze(0).to(device)
            mask = create_random_mask(img_pt, num_masks=1, mask_percentage=args.mask_ratio)
            cached_inputs.append((image_path.name, img_pt, mask))

        for scale in args.scales:
            wam.scaling_w = float(scale)
            print(f"scaling_w={scale}", flush=True)
            for image_name, img_pt, mask in cached_inputs:
                outputs = wam.embed(img_pt, target_msg)
                img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)
                psnr_watermarked = atk.psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt))
                for attack_name, attack_fn in attacks:
                    attacked = attack_fn(img_w)
                    pred, acc, mask_pixels, fallback = decode(wam, attacked, target_msg, msg_predict_inference)
                    psnr_attacked = atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt))
                    row = {
                        "image": image_name,
                        "scaling_w": f"{scale:.4f}",
                        "attack": attack_name,
                        "message": msg_to_str(target_msg),
                        "predicted": msg_to_str(pred),
                        "bit_accuracy": f"{acc:.6f}",
                        "message_success": int(acc >= 0.999),
                        "psnr_watermarked": f"{psnr_watermarked:.4f}",
                        "psnr_attacked": f"{psnr_attacked:.4f}",
                        "mask_pixels": mask_pixels,
                        "used_fallback": fallback,
                    }
                    rows.append(row)
                    print(row, flush=True)

    wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "strength_search_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_path, overview_path = write_summary(rows, out_dir)
    print(f"metrics={metrics_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    print(f"overview={overview_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
