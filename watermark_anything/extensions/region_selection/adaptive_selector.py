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
    parser.add_argument("--seed", type=int, default=27182)
    parser.add_argument("--scale", type=float, default=2.5)
    parser.add_argument("--area", type=float, default=30.0)
    parser.add_argument("--block-count", type=int, default=5)
    parser.add_argument("--grid", type=int, default=11)
    return parser.parse_args()


def rect_to_pixels(rect, h, w):
    left, top, width, height = rect
    x0 = max(0, min(w - 1, int(round(left * w))))
    y0 = max(0, min(h - 1, int(round(top * h))))
    x1 = max(x0 + 1, min(w, int(round((left + width) * w))))
    y1 = max(y0 + 1, min(h, int(round((top + height) * h))))
    return x0, y0, x1, y1


def rects_overlap(a, b):
    ax0, ay0, ax1, ay1 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx0, by0, bx1, by1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def candidate_rects(total_area_percent, block_count, grid):
    total = max(0.01, min(0.95, float(total_area_percent) / 100.0))
    side = (total / float(block_count)) ** 0.5
    starts = np.linspace(0.0, 1.0 - side, int(grid))
    return [(float(x), float(y), float(side), float(side)) for y in starts for x in starts]


def select_greedy(scored_rects, block_count, reverse=True):
    selected = []
    for score, rect in sorted(scored_rects, key=lambda item: item[0], reverse=reverse):
        if all(not rects_overlap(rect, chosen) for chosen in selected):
            selected.append(rect)
            if len(selected) >= block_count:
                break
    return selected


def fixed_anchor_rects(total_area_percent, block_count):
    if block_count != 5:
        raise ValueError("fixed_anchor_rects currently supports 5 blocks.")
    total = max(0.01, min(0.95, float(total_area_percent) / 100.0))
    side = (total / float(block_count)) ** 0.5
    center = (1.0 - side) / 2.0
    return [
        (0.0, 0.0, side, side),
        (1.0 - side, 0.0, side, side),
        (0.0, 1.0 - side, side, side),
        (1.0 - side, 1.0 - side, side, side),
        (center, center, side, side),
    ]


def texture_map(img01):
    gray = 0.299 * img01[:, 0:1] + 0.587 * img01[:, 1:2] + 0.114 * img01[:, 2:3]
    gx = torch.zeros_like(gray)
    gy = torch.zeros_like(gray)
    gx[:, :, :, :-1] = torch.abs(gray[:, :, :, 1:] - gray[:, :, :, :-1])
    gy[:, :, :-1, :] = torch.abs(gray[:, :, 1:, :] - gray[:, :, :-1, :])
    return gx + gy


def mean_in_rect(score_map, rect):
    _, _, h, w = score_map.shape
    x0, y0, x1, y1 = rect_to_pixels(rect, h, w)
    return float(score_map[:, :, y0:y1, x0:x1].mean().item())


def build_mask(img_pt, rects, base):
    masks = [base.rect_mask_like(img_pt, left, top, width, height) for left, top, width, height in rects]
    return base.union_masks(masks)


def normalize_scores(values, invert=False):
    arr = np.array(values, dtype=np.float64)
    if arr.max() - arr.min() < 1e-12:
        out = np.zeros_like(arr)
    else:
        out = (arr - arr.min()) / (arr.max() - arr.min())
    return 1.0 - out if invert else out


def choose_adaptive_rects(selector, candidates, img01, embedded01, rng, block_count):
    tex = texture_map(img01)
    residual = ((embedded01 - img01) ** 2).mean(dim=1, keepdim=True)
    tex_vals = [mean_in_rect(tex, rect) for rect in candidates]
    mse_vals = [mean_in_rect(residual, rect) for rect in candidates]

    if selector == "random":
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        return select_greedy([(idx, rect) for idx, rect in enumerate(shuffled)], block_count, reverse=False)

    if selector == "texture_top":
        return select_greedy(list(zip(tex_vals, candidates)), block_count, reverse=True)

    if selector == "low_residual":
        return select_greedy(list(zip(mse_vals, candidates)), block_count, reverse=False)

    if selector == "hybrid_texture_residual":
        tex_norm = normalize_scores(tex_vals, invert=False)
        mse_good = normalize_scores(mse_vals, invert=True)
        hybrid = 0.55 * tex_norm + 0.45 * mse_good
        return select_greedy(list(zip(hybrid.tolist(), candidates)), block_count, reverse=True)

    raise ValueError(f"Unknown selector={selector}")


def summarize(rows, out_dir):
    groups = {}
    for row in rows:
        key = (row["scheme"], row["selector"], row["attack"])
        groups.setdefault(key, []).append(row)

    summary_path = out_dir / "adaptive_selector_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "selector",
                "attack",
                "mean_bit_accuracy",
                "min_bit_accuracy",
                "message_success_rate",
                "mean_psnr_watermarked",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scheme, selector, attack), vals in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
            accs = [float(v["bit_accuracy"]) for v in vals]
            successes = [int(v["message_success"]) for v in vals]
            psnrs = [float(v["psnr_watermarked"]) for v in vals]
            writer.writerow({
                "scheme": scheme,
                "selector": selector,
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
        key = (row["scheme"], row["selector"])
        overview.setdefault(key, {"psnr": [], "attacks": {}})
        overview[key]["psnr"].append(float(row["psnr_watermarked"]))
        overview[key]["attacks"].setdefault(row["attack"], []).append(float(row["bit_accuracy"]))

    overview_path = out_dir / "adaptive_selector_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "selector",
                "mean_psnr_watermarked",
                "mean_selected_attack_accuracy",
                "worst_selected_attack_accuracy",
            ] + [f"{attack}_mean" for attack in attack_order],
        )
        writer.writeheader()
        for (scheme, selector), data in sorted(overview.items(), key=lambda item: (item[0][0], item[0][1])):
            selected = []
            row = {
                "scheme": scheme,
                "selector": selector,
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
    rng = random.Random(args.seed)

    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
    from watermark_anything.extensions.attack_benchmark import run as atk
    from watermark_anything.extensions.spatial_redundancy import coverage_search as base

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

    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={base.msg_to_str(target_msg)}", flush=True)
    print(f"scale={args.scale} area={args.area} block_count={args.block_count}", flush=True)

    attacks = [
        ("none", lambda img_w, img_o: img_w),
        ("remove_center_40", lambda img_w, img_o: base.replace_rect_with_original(img_w, img_o, 0.1838, 0.1838, 0.6324, 0.6324, default_transform, unnormalize_img, device)),
        ("black_center_40", lambda img_w, img_o: base.black_rect(img_w, 0.1838, 0.1838, 0.6324, 0.6324, default_transform, unnormalize_img, device)),
        ("crop_top_left_50", lambda img_w, img_o: base.crop_region(img_w, 0.0, 0.0, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_bottom_right_50", lambda img_w, img_o: base.crop_region(img_w, 0.5, 0.5, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_center_50", lambda img_w, img_o: base.crop_region(img_w, 0.25, 0.25, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("jpeg_q30", lambda img_w, img_o: atk.apply_jpeg(img_w, 30, default_transform, unnormalize_img, device)),
        ("jpeg_q20", lambda img_w, img_o: atk.apply_jpeg(img_w, 20, default_transform, unnormalize_img, device)),
        ("resize_0.25_jpeg_q50", lambda img_w, img_o: base.resize_then_jpeg(img_w, 0.25, 50, atk, default_transform, unnormalize_img, device)),
    ]

    rows = []
    region_rows = []
    fieldnames = [
        "image",
        "scheme",
        "selector",
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
        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = default_transform(img).unsqueeze(0).to(device)
            embedded_full = wam.embed(img_pt, target_msg)["imgs_w"]
            img01 = unnormalize_img(img_pt).clamp(0, 1)
            embedded01 = unnormalize_img(embedded_full).clamp(0, 1)

            schemes = []
            fixed_rects = fixed_anchor_rects(args.area, args.block_count)
            fixed_mask = build_mask(img_pt, fixed_rects, base)
            schemes.append(("fixed_q30_5block", "fixed_anchor", fixed_rects, embedded_full * fixed_mask + img_pt * (1 - fixed_mask)))

            candidates = candidate_rects(args.area, args.block_count, args.grid)
            for selector in ("random", "texture_top", "low_residual", "hybrid_texture_residual"):
                rects = choose_adaptive_rects(selector, candidates, img01, embedded01, rng, args.block_count)
                mask = build_mask(img_pt, rects, base)
                schemes.append((f"adaptive_q30_5block_{selector}", selector, rects, embedded_full * mask + img_pt * (1 - mask)))

            for scheme, selector, rects, img_w in schemes:
                for idx, rect in enumerate(rects):
                    region_rows.append({
                        "image": image_path.name,
                        "scheme": scheme,
                        "selector": selector,
                        "region_index": idx,
                        "left": f"{rect[0]:.6f}",
                        "top": f"{rect[1]:.6f}",
                        "width": f"{rect[2]:.6f}",
                        "height": f"{rect[3]:.6f}",
                    })
                psnr_watermarked = atk.psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt))
                for attack_name, attack_fn in attacks:
                    attacked = attack_fn(img_w, img_pt)
                    pred, acc, mask_pixels, fallback = base.decode(wam, attacked, target_msg, msg_predict_inference)
                    row = {
                        "image": image_path.name,
                        "scheme": scheme,
                        "selector": selector,
                        "area_percent": f"{args.area:.0f}",
                        "block_count": str(args.block_count),
                        "scaling_w": f"{args.scale:.4f}",
                        "attack": attack_name,
                        "message": base.msg_to_str(target_msg),
                        "predicted": base.msg_to_str(pred),
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

    metrics_path = out_dir / "adaptive_selector_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    regions_path = out_dir / "adaptive_selector_regions.csv"
    with regions_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "scheme", "selector", "region_index", "left", "top", "width", "height"])
        writer.writeheader()
        writer.writerows(region_rows)

    summary_path, overview_path = summarize(rows, out_dir)
    print(f"metrics={metrics_path}", flush=True)
    print(f"regions={regions_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    print(f"overview={overview_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
