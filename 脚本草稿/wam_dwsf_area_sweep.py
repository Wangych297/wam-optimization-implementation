import argparse
import csv
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
    parser.add_argument("--wam-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=31415)
    parser.add_argument("--scale", type=float, default=2.5)
    parser.add_argument("--areas", nargs="+", type=float, default=[10, 20, 25, 30, 50])
    parser.add_argument("--block-counts", nargs="+", type=int, default=[5, 9])
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def pil_to_tensor(img: Image.Image, default_transform, device):
    return default_transform(img.convert("RGB")).unsqueeze(0).to(device)


def tensor_to_pil(img_norm, unnormalize_img) -> Image.Image:
    img01 = unnormalize_img(img_norm.detach().cpu()).squeeze(0).clamp(0, 1)
    return TVF.to_pil_image(img01)


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


def baseline_center_mask(img_pt):
    side = 0.5 ** 0.5
    margin = (1.0 - side) / 2.0
    return rect_mask_like(img_pt, margin, margin, side, side)


def anchor_positions(block_count, side):
    if block_count == 5:
        center = (1.0 - side) / 2.0
        return [
            (0.0, 0.0),
            (1.0 - side, 0.0),
            (0.0, 1.0 - side),
            (1.0 - side, 1.0 - side),
            (center, center),
        ]
    if block_count == 9:
        starts = [0.0, (1.0 - side) / 2.0, 1.0 - side]
        return [(x, y) for y in starts for x in starts]
    raise ValueError(f"Unsupported block_count={block_count}; use 5 or 9.")


def dwsf_area_masks(img_pt, total_area_percent, block_count):
    total = max(0.01, min(0.95, float(total_area_percent) / 100.0))
    per_block_area = total / float(block_count)
    side = per_block_area ** 0.5
    positions = anchor_positions(block_count, side)
    return [rect_mask_like(img_pt, left, top, side, side) for left, top in positions]


def replace_rect_with_original(img_w_norm, img_orig_norm, left, top, width, height, default_transform, unnormalize_img, device):
    wm01 = unnormalize_img(img_w_norm.detach().clone()).clamp(0, 1)
    orig01 = unnormalize_img(img_orig_norm.detach().clone()).clamp(0, 1)
    _, _, h, w = wm01.shape
    x0 = max(0, min(w - 1, int(round(left * w))))
    y0 = max(0, min(h - 1, int(round(top * h))))
    x1 = max(x0 + 1, min(w, int(round((left + width) * w))))
    y1 = max(y0 + 1, min(h, int(round((top + height) * h))))
    wm01[:, :, y0:y1, x0:x1] = orig01[:, :, y0:y1, x0:x1]
    return pil_to_tensor(TVF.to_pil_image(wm01.squeeze(0).cpu()), default_transform, device)


def black_rect(img_w_norm, left, top, width, height, default_transform, unnormalize_img, device):
    wm01 = unnormalize_img(img_w_norm.detach().clone()).clamp(0, 1)
    _, _, h, w = wm01.shape
    x0 = max(0, min(w - 1, int(round(left * w))))
    y0 = max(0, min(h - 1, int(round(top * h))))
    x1 = max(x0 + 1, min(w, int(round((left + width) * w))))
    y1 = max(y0 + 1, min(h, int(round((top + height) * h))))
    wm01[:, :, y0:y1, x0:x1] = 0.0
    return pil_to_tensor(TVF.to_pil_image(wm01.squeeze(0).cpu()), default_transform, device)


def crop_region(img_w_norm, left, top, width, height, default_transform, unnormalize_img, device):
    img = tensor_to_pil(img_w_norm, unnormalize_img)
    w, h = img.size
    x0 = max(0, min(w - 1, int(round(left * w))))
    y0 = max(0, min(h - 1, int(round(top * h))))
    x1 = max(x0 + 1, min(w, int(round((left + width) * w))))
    y1 = max(y0 + 1, min(h, int(round((top + height) * h))))
    cropped = img.crop((x0, y0, x1, y1)).resize((w, h), Image.BICUBIC)
    return pil_to_tensor(cropped, default_transform, device)


def resize_then_jpeg(img_norm, scale, quality, atk, default_transform, unnormalize_img, device):
    resized = atk.apply_resize(img_norm, scale, default_transform, unnormalize_img, device)
    return atk.apply_jpeg(resized, quality, default_transform, unnormalize_img, device)


def decode(wam, attacked, target_msg, msg_predict_inference):
    preds = wam.detect(attacked)["preds"]
    mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
    bit_preds = preds[:, 1:, :, :]
    mask_pixels = int((mask_preds > 0.5).sum().item())
    if mask_pixels < 8:
        pred = torch.zeros_like(target_msg)
        return pred, 0.0, mask_pixels, 1
    pred = msg_predict_inference(bit_preds, mask_preds, method="semihard").float()
    acc = float((pred == target_msg).float().mean().item())
    return pred, acc, mask_pixels, 0


def write_summaries(rows, out_dir):
    groups = {}
    for row in rows:
        key = (row["scheme"], row["area_percent"], row["block_count"], row["attack"])
        groups.setdefault(key, []).append(row)

    summary_path = out_dir / "wam_dwsf_area_sweep_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "area_percent",
                "block_count",
                "attack",
                "mean_bit_accuracy",
                "min_bit_accuracy",
                "message_success_rate",
                "mean_psnr_watermarked",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scheme, area, block_count, attack), vals in sorted(groups.items(), key=lambda item: (item[0][0], float(item[0][1]), int(item[0][2]), item[0][3])):
            accs = [float(v["bit_accuracy"]) for v in vals]
            psnrs = [float(v["psnr_watermarked"]) for v in vals]
            successes = [int(v["message_success"]) for v in vals]
            writer.writerow({
                "scheme": scheme,
                "area_percent": area,
                "block_count": block_count,
                "attack": attack,
                "mean_bit_accuracy": f"{np.mean(accs):.6f}",
                "min_bit_accuracy": f"{np.min(accs):.6f}",
                "message_success_rate": f"{np.mean(successes):.6f}",
                "mean_psnr_watermarked": f"{np.mean(psnrs):.4f}",
                "num_images": len(vals),
            })

    attack_order = [
        "none",
        "remove_center_40",
        "black_center_40",
        "crop_top_left_50",
        "crop_bottom_right_50",
        "crop_center_50",
        "jpeg_q30",
        "jpeg_q20",
        "resize_0.25_jpeg_q50",
    ]
    overview = {}
    for row in rows:
        key = (row["scheme"], row["area_percent"], row["block_count"])
        overview.setdefault(key, {"psnr": [], "attacks": {}})
        overview[key]["psnr"].append(float(row["psnr_watermarked"]))
        overview[key]["attacks"].setdefault(row["attack"], []).append(float(row["bit_accuracy"]))

    overview_path = out_dir / "wam_dwsf_area_sweep_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "area_percent",
                "block_count",
                "mean_psnr_watermarked",
                "mean_selected_attack_accuracy",
                "worst_selected_attack_accuracy",
            ] + [f"{attack}_mean" for attack in attack_order],
        )
        writer.writeheader()
        for (scheme, area, block_count), data in sorted(overview.items(), key=lambda item: (item[0][0], float(item[0][1]), int(item[0][2]))):
            selected = []
            row = {
                "scheme": scheme,
                "area_percent": area,
                "block_count": block_count,
                "mean_psnr_watermarked": f"{np.mean(data['psnr']):.4f}",
            }
            for attack in attack_order:
                vals = data["attacks"].get(attack, [])
                mean_val = float(np.mean(vals)) if vals else np.nan
                row[f"{attack}_mean"] = "" if np.isnan(mean_val) else f"{mean_val:.6f}"
                if attack != "none" and vals:
                    selected.append(mean_val)
            row["mean_selected_attack_accuracy"] = f"{np.mean(selected):.6f}" if selected else ""
            row["worst_selected_attack_accuracy"] = f"{np.min(selected):.6f}" if selected else ""
            writer.writerow(row)
    return summary_path, overview_path


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    task_script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(task_script_dir))
    import wam_attack_eval as atk

    wam_root = Path(args.wam_root).resolve()
    sys.path.insert(0, str(wam_root))
    sys.path.insert(0, str(wam_root / "notebooks"))
    os.chdir(wam_root)

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

    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={msg_to_str(target_msg)}", flush=True)
    print(f"scaling_w={args.scale}", flush=True)

    attacks = [
        ("none", lambda img_w, img_o: img_w),
        ("remove_center_40", lambda img_w, img_o: replace_rect_with_original(img_w, img_o, 0.1838, 0.1838, 0.6324, 0.6324, default_transform, unnormalize_img, device)),
        ("black_center_40", lambda img_w, img_o: black_rect(img_w, 0.1838, 0.1838, 0.6324, 0.6324, default_transform, unnormalize_img, device)),
        ("crop_top_left_50", lambda img_w, img_o: crop_region(img_w, 0.0, 0.0, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_bottom_right_50", lambda img_w, img_o: crop_region(img_w, 0.5, 0.5, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_center_50", lambda img_w, img_o: crop_region(img_w, 0.25, 0.25, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("jpeg_q30", lambda img_w, img_o: atk.apply_jpeg(img_w, 30, default_transform, unnormalize_img, device)),
        ("jpeg_q20", lambda img_w, img_o: atk.apply_jpeg(img_w, 20, default_transform, unnormalize_img, device)),
        ("resize_0.25_jpeg_q50", lambda img_w, img_o: resize_then_jpeg(img_w, 0.25, 50, atk, default_transform, unnormalize_img, device)),
    ]

    rows = []
    fieldnames = [
        "image",
        "scheme",
        "area_percent",
        "block_count",
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
            cached_inputs.append((image_path.name, img_pt))

        for image_name, img_pt in cached_inputs:
            embedded_full = wam.embed(img_pt, target_msg)["imgs_w"]
            base_mask = baseline_center_mask(img_pt)
            base_img = embedded_full * base_mask + img_pt * (1 - base_mask)

            schemes = [("single_center_50pct", "50", "1", base_img)]
            for area in args.areas:
                for block_count in args.block_counts:
                    masks = dwsf_area_masks(img_pt, area, block_count)
                    mask_union = union_masks(masks)
                    scheme_img = embedded_full * mask_union + img_pt * (1 - mask_union)
                    scheme_name = f"dwsf_q{int(area):02d}_{block_count}block"
                    schemes.append((scheme_name, f"{area:.0f}", str(block_count), scheme_img))

            for scheme, area, block_count, img_w in schemes:
                psnr_watermarked = atk.psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt))
                for attack_name, attack_fn in attacks:
                    attacked = attack_fn(img_w, img_pt)
                    pred, acc, mask_pixels, fallback = decode(wam, attacked, target_msg, msg_predict_inference)
                    row = {
                        "image": image_name,
                        "scheme": scheme,
                        "area_percent": area,
                        "block_count": block_count,
                        "scaling_w": f"{args.scale:.4f}",
                        "attack": attack_name,
                        "message": msg_to_str(target_msg),
                        "predicted": msg_to_str(pred),
                        "bit_accuracy": f"{acc:.6f}",
                        "message_success": int(acc >= 0.999),
                        "psnr_watermarked": f"{psnr_watermarked:.4f}",
                        "psnr_attacked": f"{atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt)):.4f}",
                        "mask_pixels": mask_pixels,
                        "used_fallback": fallback,
                    }
                    rows.append(row)
                    print(row, flush=True)

    wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "wam_dwsf_area_sweep_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_path, overview_path = write_summaries(rows, out_dir)
    print(f"metrics={metrics_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    print(f"overview={overview_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
