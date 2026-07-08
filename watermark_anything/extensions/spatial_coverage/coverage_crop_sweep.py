"""
Coverage-Crop Robustness Sweep

Sweeps mask_ratio under single_center layout to find optimal coverage
for crop attack robustness.

References:
- DWSF (ACM MM 2023): area-percentage Q vs robustness-quality trade-off
- TrustMark (USENIX 2024): scaling factor vs quality Pareto analysis

Usage:
  # Default (mask_ratio=0.5 only, original behavior)
  python coverage_crop_sweep.py --checkpoint ... --params ... \
    --image-dir ... --out-dir ... --limit 50

  # Full sweep
  python coverage_crop_sweep.py --checkpoint ... --params ... \
    --image-dir ... --out-dir ... --limit 50 \
    --mask-ratios 0.5 0.6 0.7 0.8 0.9 1.0
"""

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
from torchvision.transforms import functional as TVF


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scaling-w", type=float, default=2.5)
    parser.add_argument(
        "--mask-ratios",
        type=float,
        nargs="+",
        default=[0.5],
        help="Mask coverage ratios to sweep (default: 0.5 = original behavior)",
    )
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


def create_mask_at_ratio(img_pt, mask_ratio, rng, device):
    """Create a single centered rectangular mask at specified coverage ratio."""
    _, _, h, w = img_pt.shape
    area = int(h * w * mask_ratio)
    side = int(area**0.5)
    side = min(side, h, w)
    # Center the mask
    top = (h - side) // 2
    left = (w - side) // 2
    mask = torch.zeros(1, 1, h, w, device=device)
    mask[:, :, top : top + side, left : left + side] = 1.0
    return mask


def apply_center_crop(watermarked_img, ratio, default_transform, unnormalize_img, device):
    """Crop center region then resize back. Same logic as attack_benchmark."""
    img_pil = TVF.to_pil_image(
        unnormalize_img(watermarked_img.detach().clone()).clamp(0, 1).squeeze(0).cpu()
    )
    w, h = img_pil.size
    cw, ch = max(1, int(w * ratio)), max(1, int(h * ratio))
    left = (w - cw) // 2
    top = (h - ch) // 2
    cropped = img_pil.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BICUBIC)
    img_t = default_transform(cropped).unsqueeze(0).to(device)
    return img_t


def apply_random_crop(watermarked_img, ratio, default_transform, unnormalize_img, device, rng):
    """Crop random region then resize back. Same logic as attack_benchmark."""
    img_pil = TVF.to_pil_image(
        unnormalize_img(watermarked_img.detach().clone()).clamp(0, 1).squeeze(0).cpu()
    )
    w, h = img_pil.size
    cw, ch = max(1, int(w * ratio)), max(1, int(h * ratio))
    left = rng.randint(0, max(0, w - cw))
    top = rng.randint(0, max(0, h - ch))
    cropped = img_pil.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BICUBIC)
    img_t = default_transform(cropped).unsqueeze(0).to(device)
    return img_t


def apply_jpeg(watermarked_img, quality, default_transform, unnormalize_img, device):
    """Apply JPEG compression then reload. Same logic as attack_benchmark."""
    img_pil = TVF.to_pil_image(
        unnormalize_img(watermarked_img.detach().clone()).clamp(0, 1).squeeze(0).cpu()
    )
    buf = io.BytesIO()
    img_pil.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    img_jpg = Image.open(buf).convert("RGB")
    img_t = default_transform(img_jpg).unsqueeze(0).to(device)
    return img_t


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    run_root = Path(args.project_root).resolve()
    sys.path.insert(0, str(run_root))
    sys.path.insert(0, str(run_root / "notebooks"))
    os.chdir(run_root)

    from inference_utils import load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference
    from torchvision import transforms as T
    from watermark_anything.data.transforms import default_transform, unnormalize_img

    inference_transform = T.Compose(
        [T.Resize(256), T.CenterCrop(256), default_transform]
    )

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "coverage_crop_sweep_metrics.csv"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)
    if device.type == "cuda":
        print(f"gpu={torch.cuda.get_device_name(0)}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = float(args.scaling_w)

    # Load images
    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]
    if not image_paths:
        raise RuntimeError(f"No images found under {args.image_dir}")

    # Fixed message for all tests
    rng = np.random.RandomState(args.seed)
    msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
    print(f"message={msg_to_str(msg)}", flush=True)
    print(f"mask_ratios={args.mask_ratios}", flush=True)
    print(f"images={len(image_paths)}", flush=True)

    # Define attacks
    attacks = {
        "none": lambda img_w: img_w,
        "center_crop_0.5": lambda img_w: apply_center_crop(
            img_w, 0.5, default_transform, unnormalize_img, device
        ),
        "center_crop_0.75": lambda img_w: apply_center_crop(
            img_w, 0.75, default_transform, unnormalize_img, device
        ),
        "random_crop_0.5": lambda img_w: apply_random_crop(
            img_w, 0.5, default_transform, unnormalize_img, device, rng
        ),
        "jpeg_q30": lambda img_w: apply_jpeg(
            img_w, 30, default_transform, unnormalize_img, device
        ),
    }

    fieldnames = [
        "image",
        "mask_ratio",
        "attack",
        "bit_accuracy",
        "message_success",
        "psnr_watermarked",
        "psnr_attacked",
    ]
    rows = []

    with torch.inference_mode():
        for img_idx, image_path in enumerate(image_paths):
            img = Image.open(image_path).convert("RGB")
            img_pt = inference_transform(img).unsqueeze(0).to(device)
            img_01 = unnormalize_img(img_pt).clamp(0, 1)

            for ratio in args.mask_ratios:
                # Create mask at specified ratio
                mask = create_mask_at_ratio(img_pt, ratio, rng, device)

                # Embed watermark
                outputs = wam.embed(img_pt, msg)
                img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)
                img_w_01 = unnormalize_img(img_w).clamp(0, 1)

                # Compute clean PSNR
                clean_psnr = psnr_tensor(img_w_01, img_01)

                # Test each attack
                for attack_name, attack_fn in attacks.items():
                    if attack_name == "none":
                        attacked = img_w
                        attacked_psnr = clean_psnr
                    else:
                        attacked = attack_fn(img_w)
                        attacked_01 = unnormalize_img(attacked).clamp(0, 1)
                        attacked_psnr = psnr_tensor(attacked_01, img_01)

                    # Detect and decode
                    preds = wam.detect(attacked)["preds"]
                    mask_logits = preds[:, 0:1, :, :]
                    mask_preds = torch.sigmoid(mask_logits)
                    bit_preds = preds[:, 1:, :, :]
                    pred_message = msg_predict_inference(
                        bit_preds, mask_preds, method="semihard"
                    ).float()
                    bit_acc = (pred_message == msg).float().mean().item()
                    msg_success = 1 if bit_acc == 1.0 else 0

                    row = {
                        "image": image_path.name,
                        "mask_ratio": f"{ratio:.1f}",
                        "attack": attack_name,
                        "bit_accuracy": f"{bit_acc:.6f}",
                        "message_success": msg_success,
                        "psnr_watermarked": f"{clean_psnr:.4f}",
                        "psnr_attacked": f"{attacked_psnr:.4f}",
                    }
                    rows.append(row)

                    if attack_name == "none":
                        print(
                            f"[{img_idx+1}/{len(image_paths)}] {image_path.name} "
                            f"ratio={ratio:.1f} clean: acc={bit_acc:.4f} psnr={clean_psnr:.2f}",
                            flush=True,
                        )

    # Save results
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Compute and save summary
    summary_path = out_dir / "coverage_crop_sweep_summary.csv"
    from collections import defaultdict

    agg = defaultdict(lambda: {"acc_sum": 0.0, "psnr_sum": 0.0, "count": 0, "success_count": 0})
    for row in rows:
        key = (row["mask_ratio"], row["attack"])
        agg[key]["acc_sum"] += float(row["bit_accuracy"])
        agg[key]["psnr_sum"] += float(row["psnr_watermarked"])
        agg[key]["count"] += 1
        agg[key]["success_count"] += int(row["message_success"])

    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["mask_ratio", "attack", "mean_bit_accuracy", "message_success_rate", "mean_psnr", "num_samples"])
        for (ratio, attack) in sorted(agg.keys()):
            d = agg[(ratio, attack)]
            writer.writerow([
                ratio,
                attack,
                f"{d['acc_sum'] / d['count']:.6f}",
                f"{d['success_count'] / d['count']:.4f}",
                f"{d['psnr_sum'] / d['count']:.4f}",
                d["count"],
            ])

    print(f"metrics={csv_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    print(f"total_rows={len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
