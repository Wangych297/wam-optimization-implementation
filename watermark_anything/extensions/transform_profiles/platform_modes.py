import argparse
import csv
import io
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, features

import torch


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=70608)
    return parser.parse_args()


def jpeg_roundtrip_pil(img, quality):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(quality))
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def webp_roundtrip_pil(img, quality):
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=int(quality), method=4)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def pil_attack(img_norm, transform_fn, area, default_transform, unnormalize_img, device):
    img = area.tensor_to_pil(img_norm, unnormalize_img)
    return area.pil_to_tensor(transform_fn(img.convert("RGB")), default_transform, device)


def resize_then_jpeg(img_norm, scale, quality, atk, default_transform, unnormalize_img, device):
    resized = atk.apply_resize(img_norm, scale, default_transform, unnormalize_img, device)
    return atk.apply_jpeg(resized, quality, default_transform, unnormalize_img, device)


def make_attacks(area, atk, default_transform, unnormalize_img, device):
    attack_fns = [
        ("none", lambda img_w, img_o: img_w),
        ("jpeg_q50", lambda img_w, img_o: atk.apply_jpeg(img_w, 50, default_transform, unnormalize_img, device)),
        ("jpeg_q30", lambda img_w, img_o: atk.apply_jpeg(img_w, 30, default_transform, unnormalize_img, device)),
        ("gaussian_blur_1.2", lambda img_w, img_o: pil_attack(img_w, lambda img: img.filter(ImageFilter.GaussianBlur(radius=1.2)), area, default_transform, unnormalize_img, device)),
        ("median_filter_3", lambda img_w, img_o: pil_attack(img_w, lambda img: img.filter(ImageFilter.MedianFilter(size=3)), area, default_transform, unnormalize_img, device)),
        ("brightness_1.5", lambda img_w, img_o: pil_attack(img_w, lambda img: ImageEnhance.Brightness(img).enhance(1.5), area, default_transform, unnormalize_img, device)),
        ("contrast_1.5", lambda img_w, img_o: pil_attack(img_w, lambda img: ImageEnhance.Contrast(img).enhance(1.5), area, default_transform, unnormalize_img, device)),
        ("saturation_1.5", lambda img_w, img_o: pil_attack(img_w, lambda img: ImageEnhance.Color(img).enhance(1.5), area, default_transform, unnormalize_img, device)),
        ("sharpness_2.0", lambda img_w, img_o: pil_attack(img_w, lambda img: ImageEnhance.Sharpness(img).enhance(2.0), area, default_transform, unnormalize_img, device)),
        ("bright_contrast_jpeg80", lambda img_w, img_o: pil_attack(
            img_w,
            lambda img: jpeg_roundtrip_pil(ImageEnhance.Contrast(ImageEnhance.Brightness(img).enhance(1.3)).enhance(1.3), 80),
            area,
            default_transform,
            unnormalize_img,
            device,
        )),
        ("resize_0.5_jpeg50", lambda img_w, img_o: resize_then_jpeg(img_w, 0.5, 50, atk, default_transform, unnormalize_img, device)),
    ]

    if features.check("webp"):
        attack_fns.extend([
            ("webp_q80", lambda img_w, img_o: pil_attack(img_w, lambda img: webp_roundtrip_pil(img, 80), area, default_transform, unnormalize_img, device)),
            ("webp_q50", lambda img_w, img_o: pil_attack(img_w, lambda img: webp_roundtrip_pil(img, 50), area, default_transform, unnormalize_img, device)),
            ("saturation_sharpness_webp80", lambda img_w, img_o: pil_attack(
                img_w,
                lambda img: webp_roundtrip_pil(ImageEnhance.Sharpness(ImageEnhance.Color(img).enhance(1.3)).enhance(1.5), 80),
                area,
                default_transform,
                unnormalize_img,
                device,
            )),
        ])
    return attack_fns


def mode_definitions():
    return [
        {
            "scheme": "single_center50_s2.5",
            "region_strategy": "single_center",
            "area_percent": 50.0,
            "block_count": 1,
            "scaling_w": 2.5,
        },
        {
            "scheme": "single_center50_s3.0",
            "region_strategy": "single_center",
            "area_percent": 50.0,
            "block_count": 1,
            "scaling_w": 3.0,
        },
        {
            "scheme": "coverage_default_q30_s2.5",
            "region_strategy": "fixed_anchor_regions",
            "area_percent": 30.0,
            "block_count": 5,
            "scaling_w": 2.5,
        },
        {
            "scheme": "coverage_robust_q50_s2.5",
            "region_strategy": "fixed_anchor_regions",
            "area_percent": 50.0,
            "block_count": 5,
            "scaling_w": 2.5,
        },
        {
            "scheme": "coverage_strong_q30_s3.0",
            "region_strategy": "fixed_anchor_regions",
            "area_percent": 30.0,
            "block_count": 5,
            "scaling_w": 3.0,
        },
        {
            "scheme": "coverage_robust_strong_q50_s3.0",
            "region_strategy": "fixed_anchor_regions",
            "area_percent": 50.0,
            "block_count": 5,
            "scaling_w": 3.0,
        },
    ]


def build_mode_image(mode, img_pt, embedded_full, area):
    if mode["region_strategy"] == "single_center":
        mask = area.baseline_center_mask(img_pt)
    elif mode["region_strategy"] == "fixed_anchor_regions":
        masks = area.distributed_area_masks(img_pt, mode["area_percent"], mode["block_count"])
        mask = area.union_masks(masks)
    else:
        raise ValueError(f"Unknown region strategy: {mode['region_strategy']}")
    return embedded_full * mask + img_pt * (1 - mask)


def write_summaries(rows, out_dir, attack_order):
    summary_groups = {}
    for row in rows:
        key = (row["scheme"], row["attack"])
        summary_groups.setdefault(key, []).append(row)

    summary_path = out_dir / "platform_modes_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "attack",
                "mean_bit_accuracy",
                "min_bit_accuracy",
                "message_success_rate",
                "mean_psnr_watermarked",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scheme, attack), vals in sorted(summary_groups.items()):
            accs = [float(v["bit_accuracy"]) for v in vals]
            psnrs = [float(v["psnr_watermarked"]) for v in vals]
            successes = [int(v["message_success"]) for v in vals]
            writer.writerow({
                "scheme": scheme,
                "attack": attack,
                "mean_bit_accuracy": f"{np.mean(accs):.6f}",
                "min_bit_accuracy": f"{np.min(accs):.6f}",
                "message_success_rate": f"{np.mean(successes):.6f}",
                "mean_psnr_watermarked": f"{np.mean(psnrs):.4f}",
                "num_images": len(vals),
            })

    overview_groups = {}
    for row in rows:
        key = (row["scheme"], row["region_strategy"], row["area_percent"], row["block_count"], row["scaling_w"])
        overview_groups.setdefault(key, {"psnr": [], "attacks": {}})
        overview_groups[key]["psnr"].append(float(row["psnr_watermarked"]))
        overview_groups[key]["attacks"].setdefault(row["attack"], []).append(float(row["bit_accuracy"]))

    overview_path = out_dir / "platform_modes_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "scheme",
            "region_strategy",
            "area_percent",
            "block_count",
            "scaling_w",
            "mean_psnr_watermarked",
            "clean_accuracy",
            "mean_selected_attack_accuracy",
            "worst_selected_attack_accuracy",
        ] + [f"{attack}_mean" for attack in attack_order]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for key, data in sorted(overview_groups.items(), key=lambda item: item[0][0]):
            scheme, strategy, area_percent, block_count, scaling_w = key
            selected = []
            row = {
                "scheme": scheme,
                "region_strategy": strategy,
                "area_percent": area_percent,
                "block_count": block_count,
                "scaling_w": scaling_w,
                "mean_psnr_watermarked": f"{np.mean(data['psnr']):.4f}",
            }
            for attack in attack_order:
                vals = data["attacks"].get(attack, [])
                mean_val = float(np.mean(vals)) if vals else np.nan
                row[f"{attack}_mean"] = "" if np.isnan(mean_val) else f"{mean_val:.6f}"
                if attack == "none":
                    row["clean_accuracy"] = "" if np.isnan(mean_val) else f"{mean_val:.6f}"
                elif vals:
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

    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
    from watermark_anything.extensions.attack_benchmark import run as atk
    from watermark_anything.extensions.spatial_redundancy import coverage_search as area

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

    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]
    if not image_paths:
        raise RuntimeError(f"No images found under {args.image_dir}")

    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={area.msg_to_str(target_msg)}", flush=True)
    print(f"webp_supported={features.check('webp')}", flush=True)

    attacks = make_attacks(area, atk, default_transform, unnormalize_img, device)
    attack_order = [name for name, _ in attacks]
    modes = mode_definitions()

    rows = []
    fieldnames = [
        "image",
        "scheme",
        "region_strategy",
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

    try:
        with torch.inference_mode():
            cached_inputs = []
            for image_path in image_paths:
                img = Image.open(image_path).convert("RGB")
                img_pt = default_transform(img).unsqueeze(0).to(device)
                cached_inputs.append((image_path.name, img_pt))

            for image_name, img_pt in cached_inputs:
                for mode in modes:
                    wam.scaling_w = float(mode["scaling_w"])
                    embedded_full = wam.embed(img_pt, target_msg)["imgs_w"]
                    img_w = build_mode_image(mode, img_pt, embedded_full, area)
                    psnr_watermarked = atk.psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt))

                    for attack_name, attack_fn in attacks:
                        attacked = attack_fn(img_w, img_pt)
                        pred, acc, mask_pixels, fallback = area.decode(wam, attacked, target_msg, msg_predict_inference)
                        row = {
                            "image": image_name,
                            "scheme": mode["scheme"],
                            "region_strategy": mode["region_strategy"],
                            "area_percent": f"{mode['area_percent']:.0f}",
                            "block_count": str(mode["block_count"]),
                            "scaling_w": f"{mode['scaling_w']:.4f}",
                            "attack": attack_name,
                            "message": area.msg_to_str(target_msg),
                            "predicted": area.msg_to_str(pred),
                            "bit_accuracy": f"{acc:.6f}",
                            "message_success": int(acc >= 0.999),
                            "psnr_watermarked": f"{psnr_watermarked:.4f}",
                            "psnr_attacked": f"{atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt)):.4f}",
                            "mask_pixels": mask_pixels,
                            "used_fallback": fallback,
                        }
                        rows.append(row)
                        print(row, flush=True)
    finally:
        wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "platform_modes_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_path, overview_path = write_summaries(rows, out_dir, attack_order)
    print(f"metrics={metrics_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    print(f"overview={overview_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
