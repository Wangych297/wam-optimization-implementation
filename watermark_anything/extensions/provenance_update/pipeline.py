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
    parser.add_argument("--seed", type=int, default=51515)
    parser.add_argument("--scale", type=float, default=2.5)
    parser.add_argument("--epsilon", type=float, default=1.0)
    parser.add_argument("--min-samples", type=int, default=500)
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def rect_mask_like(img_pt, left, top, width, height):
    _, _, h, w = img_pt.shape
    x0 = max(0, min(w - 1, int(round(left * w))))
    y0 = max(0, min(h - 1, int(round(top * h))))
    x1 = max(x0 + 1, min(w, int(round((left + width) * w))))
    y1 = max(y0 + 1, min(h, int(round((top + height) * h))))
    mask = torch.zeros((1, 1, h, w), dtype=img_pt.dtype, device=img_pt.device)
    mask[:, :, y0:y1, x0:x1] = 1.0
    return mask


def union_masks(masks):
    out = torch.zeros_like(masks[0])
    for mask in masks:
        out = torch.maximum(out, mask)
    return out


def q30_anchor_mask(img_pt):
    side = (0.30 / 5.0) ** 0.5
    center = (1.0 - side) / 2.0
    positions = [
        (0.0, 0.0),
        (1.0 - side, 0.0),
        (0.0, 1.0 - side),
        (1.0 - side, 1.0 - side),
        (center, center),
    ]
    return union_masks([rect_mask_like(img_pt, left, top, side, side) for left, top in positions])


def side_mid_4block_mask(img_pt):
    side = (0.24 / 4.0) ** 0.5
    center = (1.0 - side) / 2.0
    positions = [
        (center, 0.0),
        (center, 1.0 - side),
        (0.0, center),
        (1.0 - side, center),
    ]
    return union_masks([rect_mask_like(img_pt, left, top, side, side) for left, top in positions])


def tensor_to_pil(img_norm, unnormalize_img):
    from torchvision.transforms import functional as TVF

    img01 = unnormalize_img(img_norm.detach().cpu()).squeeze(0).clamp(0, 1)
    return TVF.to_pil_image(img01)


def pil_to_tensor(img, default_transform, device):
    return default_transform(img.convert("RGB")).unsqueeze(0).to(device)


def crop_center_50(img_norm, default_transform, unnormalize_img, device):
    img = tensor_to_pil(img_norm, unnormalize_img)
    w, h = img.size
    x0, y0, x1, y1 = int(0.25 * w), int(0.25 * h), int(0.75 * w), int(0.75 * h)
    cropped = img.crop((x0, y0, x1, y1)).resize((w, h), Image.BICUBIC)
    return pil_to_tensor(cropped, default_transform, device)


def resize_then_jpeg(img_norm, atk, default_transform, unnormalize_img, device):
    resized = atk.apply_resize(img_norm, 0.5, default_transform, unnormalize_img, device)
    return atk.apply_jpeg(resized, 50, default_transform, unnormalize_img, device)


def decode_slot(wam, img_norm, slot_mask, target_msg, msg_predict_inference):
    preds = wam.detect(img_norm)["preds"]
    mask_probs = torch.sigmoid(preds[:, 0:1, :, :])
    bit_preds = preds[:, 1:, :, :]
    slot_det = torch.nn.functional.interpolate(slot_mask.float(), size=mask_probs.shape[-2:], mode="nearest")
    weights = mask_probs * slot_det
    mask_pixels = int((weights > 0.3).sum().item())
    if mask_pixels < 8:
        pred = torch.zeros_like(target_msg)
        return pred, 0.0, mask_pixels
    pred = msg_predict_inference(bit_preds, weights, method="semihard").float()
    acc = float((pred == target_msg).float().mean().item())
    return pred, acc, mask_pixels


def summarize(rows, out_dir):
    groups = {}
    for row in rows:
        key = (row["scheme"], row["attack"])
        groups.setdefault(key, []).append(row)

    summary_path = out_dir / "provenance_update_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "attack",
                "mean_msg_a_accuracy",
                "mean_msg_b_accuracy",
                "both_success_rate",
                "mean_slot_a_pixels",
                "mean_slot_b_pixels",
                "mean_psnr_watermarked",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scheme, attack), vals in sorted(groups.items(), key=lambda item: item[0]):
            writer.writerow({
                "scheme": scheme,
                "attack": attack,
                "mean_msg_a_accuracy": f"{np.mean([float(v['msg_a_accuracy']) for v in vals]):.6f}",
                "mean_msg_b_accuracy": f"{np.mean([float(v['msg_b_accuracy']) for v in vals]):.6f}",
                "both_success_rate": f"{np.mean([int(v['both_success']) for v in vals]):.6f}",
                "mean_slot_a_pixels": f"{np.mean([int(v['slot_a_pixels']) for v in vals]):.1f}",
                "mean_slot_b_pixels": f"{np.mean([int(v['slot_b_pixels']) for v in vals]):.1f}",
                "mean_psnr_watermarked": f"{np.mean([float(v['psnr_watermarked']) for v in vals]):.4f}",
                "num_images": len(vals),
            })

    overview = {}
    for row in rows:
        overview.setdefault(row["scheme"], []).append(row)
    overview_path = out_dir / "provenance_update_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "mean_msg_a_accuracy",
                "mean_msg_b_accuracy",
                "both_success_rate",
                "mean_slot_a_pixels",
                "mean_slot_b_pixels",
                "mean_psnr_watermarked",
            ],
        )
        writer.writeheader()
        for scheme, vals in sorted(overview.items()):
            writer.writerow({
                "scheme": scheme,
                "mean_msg_a_accuracy": f"{np.mean([float(v['msg_a_accuracy']) for v in vals]):.6f}",
                "mean_msg_b_accuracy": f"{np.mean([float(v['msg_b_accuracy']) for v in vals]):.6f}",
                "both_success_rate": f"{np.mean([int(v['both_success']) for v in vals]):.6f}",
                "mean_slot_a_pixels": f"{np.mean([int(v['slot_a_pixels']) for v in vals]):.1f}",
                "mean_slot_b_pixels": f"{np.mean([int(v['slot_b_pixels']) for v in vals]):.1f}",
                "mean_psnr_watermarked": f"{np.mean([float(v['psnr_watermarked']) for v in vals]):.4f}",
            })
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

    from inference_utils import load_model_from_checkpoint
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
    wam.scaling_w = float(args.scale)

    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]
    if not image_paths:
        raise RuntimeError(f"No images found under {args.image_dir}")

    msg_a = torch.randint(0, 2, (1, 32), device=device).float()
    msg_b = torch.randint(0, 2, (1, 32), device=device).float()
    targets = torch.cat([msg_a, msg_b], dim=0)
    print(f"msg_a={msg_to_str(msg_a)}", flush=True)
    print(f"msg_b={msg_to_str(msg_b)}", flush=True)

    attacks = [
        ("none", lambda img_w: img_w),
        ("jpeg_q50", lambda img_w: atk.apply_jpeg(img_w, 50, default_transform, unnormalize_img, device)),
        ("resize_0.5_jpeg_q50", lambda img_w: resize_then_jpeg(img_w, atk, default_transform, unnormalize_img, device)),
    ]

    rows = []
    fieldnames = [
        "image",
        "scheme",
        "attack",
        "msg_a",
        "msg_b",
        "pred_msg_a_slot",
        "pred_msg_b_slot",
        "msg_a_accuracy",
        "msg_b_accuracy",
        "both_success",
        "slot_a_pixels",
        "slot_b_pixels",
        "psnr_watermarked",
        "psnr_attacked",
    ]

    with torch.inference_mode():
        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = default_transform(img).unsqueeze(0).to(device)

            mask_a = q30_anchor_mask(img_pt)
            mask_b = side_mid_4block_mask(img_pt)

            embed_a = wam.embed(img_pt, msg_a)["imgs_w"]
            img_a = embed_a * mask_a + img_pt * (1 - mask_a)

            embed_b_clean = wam.embed(img_pt, msg_b)["imgs_w"]
            img_overlap = embed_b_clean * mask_a + img_a * (1 - mask_a)
            img_disjoint = embed_b_clean * mask_b + img_a * (1 - mask_b)

            schemes = [
                ("overlap_replace_same_region", img_overlap, mask_a, mask_a),
                ("disjoint_append_side_regions", img_disjoint, mask_a, mask_b),
            ]

            for scheme, img_w, slot_a, slot_b in schemes:
                psnr_watermarked = atk.psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt))
                for attack_name, attack_fn in attacks:
                    attacked = attack_fn(img_w)
                    pred_a, acc_a, pix_a = decode_slot(wam, attacked, slot_a, msg_a, msg_predict_inference)
                    pred_b, acc_b, pix_b = decode_slot(wam, attacked, slot_b, msg_b, msg_predict_inference)
                    row = {
                        "image": image_path.name,
                        "scheme": scheme,
                        "attack": attack_name,
                        "msg_a": msg_to_str(msg_a),
                        "msg_b": msg_to_str(msg_b),
                        "pred_msg_a_slot": msg_to_str(pred_a),
                        "pred_msg_b_slot": msg_to_str(pred_b),
                        "msg_a_accuracy": f"{acc_a:.6f}",
                        "msg_b_accuracy": f"{acc_b:.6f}",
                        "both_success": int(acc_a >= 0.999 and acc_b >= 0.999),
                        "slot_a_pixels": pix_a,
                        "slot_b_pixels": pix_b,
                        "psnr_watermarked": f"{psnr_watermarked:.4f}",
                        "psnr_attacked": f"{atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt)):.4f}",
                    }
                    rows.append(row)
                    print(row, flush=True)

    wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "provenance_update_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_path, overview_path = summarize(rows, out_dir)
    print(f"metrics={metrics_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    print(f"overview={overview_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
