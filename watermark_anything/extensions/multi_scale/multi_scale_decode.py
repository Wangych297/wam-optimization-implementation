"""
Multi-Scale Detection for Crop Robustness

Tests whether detecting watermarks at multiple spatial scales improves
robustness against crop attacks. Crop+resize distorts the effective
scale of watermark patterns; multi-scale detection aims to find the
scale where the pattern best matches the detector's expectations.

References:
- Feature Pyramid Networks (Lin et al., CVPR 2017)
- Experiment 09 findings (bottleneck is in detection, not embedding)

Usage:
  # Default (single-scale, original behavior)
  python multi_scale_decode.py --checkpoint ... --params ... \
    --image-dir ... --out-dir ... --limit 50

  # Multi-scale decoding
  python multi_scale_decode.py --checkpoint ... --params ... \
    --image-dir ... --out-dir ... --limit 50 --use-multi-scale
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
        "--use-multi-scale",
        action="store_true",
        help="Enable multi-scale detection (ref: FPN, CVPR 2017)",
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


def tensor_to_255(watermarked_img, unnormalize_img):
    """Convert normalized tensor to [0,255] PIL Image."""
    img01 = unnormalize_img(watermarked_img.detach().clone()).clamp(0, 1)
    return TVF.to_pil_image(img01.squeeze(0).cpu())


def apply_center_crop(watermarked_img, ratio, default_transform, unnormalize_img, device):
    """Crop center region then resize back."""
    img_pil = tensor_to_255(watermarked_img, unnormalize_img)
    w, h = img_pil.size
    cw, ch = max(1, int(w * ratio)), max(1, int(h * ratio))
    left = (w - cw) // 2
    top = (h - ch) // 2
    cropped = img_pil.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BICUBIC)
    return default_transform(cropped).unsqueeze(0).to(device)


def apply_random_crop(watermarked_img, ratio, default_transform, unnormalize_img, device, rng):
    """Crop random region then resize back."""
    img_pil = tensor_to_255(watermarked_img, unnormalize_img)
    w, h = img_pil.size
    cw, ch = max(1, int(w * ratio)), max(1, int(h * ratio))
    left = rng.randint(0, max(0, w - cw))
    top = rng.randint(0, max(0, h - ch))
    cropped = img_pil.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BICUBIC)
    return default_transform(cropped).unsqueeze(0).to(device)


def apply_jpeg(watermarked_img, quality, default_transform, unnormalize_img, device):
    """Apply JPEG compression then reload."""
    img_pil = tensor_to_255(watermarked_img, unnormalize_img)
    buf = io.BytesIO()
    img_pil.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    img_jpg = Image.open(buf).convert("RGB")
    return default_transform(img_jpg).unsqueeze(0).to(device)


def create_random_mask(img_pt, mask_ratio, rng, device):
    """Create a random mask at specified coverage ratio."""
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * mask_ratio)
    side = max(1, int(area ** 0.5))
    side = min(side, h, w)
    top = rng.randint(0, max(0, h - side))
    left = rng.randint(0, max(0, w - side))
    mask[:, :, top : top + side, left : left + side] = 1.0
    return mask


MULTI_SCALE_FACTORS = [0.5, 0.75, 1.0, 1.25, 1.5]


def decode_at_scale(attacked_pt, scale, wam, msg_predict_inference, device,
                    unnormalize_img, default_transform):
    """
    Decode watermark at a specific spatial scale.
    scale < 1.0: shrink then pad
    scale = 1.0: as-is
    scale > 1.0: enlarge then center-crop
    """
    _, _, h, w = attacked_pt.shape
    if abs(scale - 1.0) < 1e-6:
        preds = wam.detect(attacked_pt)["preds"]
    else:
        new_size = int(h * scale)
        img01 = unnormalize_img(attacked_pt.detach().clone()).clamp(0, 1)
        img_pil = TVF.to_pil_image(img01.squeeze(0).cpu())
        img_pil = img_pil.resize((new_size, new_size), Image.BICUBIC)

        if scale < 1.0:
            canvas = Image.new("RGB", (w, h), (0, 0, 0))
            offset = ((w - new_size) // 2, (h - new_size) // 2)
            canvas.paste(img_pil, offset)
            img_pil = canvas
        else:
            left = (new_size - w) // 2
            top = (new_size - h) // 2
            img_pil = img_pil.crop((left, top, left + w, top + h))

        scaled = default_transform(img_pil).unsqueeze(0).to(device)
        preds = wam.detect(scaled)["preds"]

    mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
    bit_preds = preds[:, 1:, :, :]
    pred_msg = msg_predict_inference(bit_preds, mask_preds, method="semihard").float()
    mean_conf = mask_preds.mean().item()
    return pred_msg, mean_conf


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
    csv_path = out_dir / "multi_scale_metrics.csv"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)
    if device.type == "cuda":
        print(f"gpu={torch.cuda.get_device_name(0)}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = float(args.scaling_w)

    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]
    if not image_paths:
        raise RuntimeError(f"No images found under {args.image_dir}")

    rng = np.random.RandomState(args.seed)
    msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
    print(f"message={msg_to_str(msg)}", flush=True)
    print(f"multi_scale={args.use_multi_scale}", flush=True)
    print(f"images={len(image_paths)}", flush=True)

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
        "image", "attack", "method",
        "bit_accuracy", "message_success",
        "psnr_watermarked", "psnr_attacked",
        "best_scale",
    ]
    rows = []

    with torch.inference_mode():
        for img_idx, image_path in enumerate(image_paths):
            img = Image.open(image_path).convert("RGB")
            img_pt = inference_transform(img).unsqueeze(0).to(device)
            img_01 = unnormalize_img(img_pt).clamp(0, 1)

            # Embed
            mask = create_random_mask(img_pt, 0.5, rng, device)
            outputs = wam.embed(img_pt, msg)
            img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)
            img_w_01 = unnormalize_img(img_w).clamp(0, 1)
            clean_psnr = psnr_tensor(img_w_01, img_01)

            for attack_name, attack_fn in attacks.items():
                if attack_name == "none":
                    attacked = img_w
                    attacked_psnr = clean_psnr
                else:
                    attacked = attack_fn(img_w)
                    attacked_01 = unnormalize_img(attacked).clamp(0, 1)
                    attacked_psnr = psnr_tensor(attacked_01, img_01)

                # Single-scale decode (baseline)
                preds = wam.detect(attacked)["preds"]
                mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
                bit_preds = preds[:, 1:, :, :]
                pred_msg_single = msg_predict_inference(
                    bit_preds, mask_preds, method="semihard"
                ).float()
                bit_acc_single = (pred_msg_single == msg).float().mean().item()

                row = {
                    "image": image_path.name,
                    "attack": attack_name,
                    "method": "single_scale",
                    "bit_accuracy": f"{bit_acc_single:.6f}",
                    "message_success": 1 if bit_acc_single == 1.0 else 0,
                    "psnr_watermarked": f"{clean_psnr:.4f}",
                    "psnr_attacked": f"{attacked_psnr:.4f}",
                    "best_scale": "1.0",
                }
                rows.append(row)

                # Multi-scale decode (experimental)
                if args.use_multi_scale:
                    best_acc = bit_acc_single
                    best_scale = 1.0
                    for scale in MULTI_SCALE_FACTORS:
                        if abs(scale - 1.0) < 1e-6:
                            continue  # already tested
                        pred_msg_multi, conf = decode_at_scale(
                            attacked, scale, wam, msg_predict_inference, device,
                            unnormalize_img, default_transform
                        )
                        bit_acc_multi = (pred_msg_multi == msg).float().mean().item()
                        if bit_acc_multi > best_acc:
                            best_acc = bit_acc_multi
                            best_scale = scale

                    row_multi = {
                        "image": image_path.name,
                        "attack": attack_name,
                        "method": "multi_scale",
                        "bit_accuracy": f"{best_acc:.6f}",
                        "message_success": 1 if best_acc == 1.0 else 0,
                        "psnr_watermarked": f"{clean_psnr:.4f}",
                        "psnr_attacked": f"{attacked_psnr:.4f}",
                        "best_scale": f"{best_scale:.2f}",
                    }
                    rows.append(row_multi)

            print(
                f"[{img_idx+1}/{len(image_paths)}] {image_path.name} "
                f"clean_acc={bit_acc_single:.4f} psnr={clean_psnr:.2f}",
                flush=True,
            )

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    summary_path = out_dir / "multi_scale_summary.csv"
    from collections import defaultdict

    agg = defaultdict(lambda: {"acc_sum": 0.0, "count": 0, "success": 0})
    for row in rows:
        key = (row["method"], row["attack"])
        agg[key]["acc_sum"] += float(row["bit_accuracy"])
        agg[key]["count"] += 1
        agg[key]["success"] += int(row["message_success"])

    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["method", "attack", "mean_bit_accuracy", "message_success_rate", "num_samples"])
        for (method, attack) in sorted(agg.keys()):
            d = agg[(method, attack)]
            writer.writerow([
                method, attack,
                f"{d['acc_sum'] / d['count']:.6f}",
                f"{d['success'] / d['count']:.4f}",
                d["count"],
            ])

    print(f"metrics={csv_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    print(f"total_rows={len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
