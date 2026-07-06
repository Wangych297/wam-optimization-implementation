import argparse
import csv
import io
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

import torch


RESAMPLE = Image.Resampling.BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed", type=int, default=240724)
    parser.add_argument("--material-size", type=int, default=256)
    parser.add_argument("--canvas-size", type=int, default=512)
    return parser.parse_args()


def msg_to_str(msg):
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def pil_jpeg(img, quality):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(quality))
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def psnr_pil(a, b):
    arr_a = np.asarray(a.convert("RGB"), dtype=np.float32) / 255.0
    arr_b = np.asarray(b.convert("RGB"), dtype=np.float32) / 255.0
    mse = float(np.mean((arr_a - arr_b) ** 2))
    if mse <= 1e-12:
        return 99.0
    return float(20.0 * np.log10(1.0 / np.sqrt(mse)))


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
            "scheme": "full_material_s2.5",
            "region_strategy": "full_image",
            "area_percent": 100.0,
            "block_count": 1,
            "scaling_w": 2.5,
        },
        {
            "scheme": "full_material_s3.0",
            "region_strategy": "full_image",
            "area_percent": 100.0,
            "block_count": 1,
            "scaling_w": 3.0,
        },
        {
            "scheme": "distributed_q50_s2.5",
            "region_strategy": "fixed_anchor_regions",
            "area_percent": 50.0,
            "block_count": 5,
            "scaling_w": 2.5,
        },
        {
            "scheme": "distributed_q50_s3.0",
            "region_strategy": "fixed_anchor_regions",
            "area_percent": 50.0,
            "block_count": 5,
            "scaling_w": 3.0,
        },
    ]


def scenario_definitions(canvas_size):
    return [
        {
            "scenario": "two_sources_downsize",
            "placements": [
                {"source_idx": 0, "box": (34, 42, 222, 230), "crop": None, "contrast": 1.0, "feather": 0},
                {"source_idx": 1, "box": (270, 172, 450, 352), "crop": None, "contrast": 1.0, "feather": 0},
            ],
        },
        {
            "scenario": "three_sources_extreme_downsize",
            "placements": [
                {"source_idx": 0, "box": (30, 36, 164, 170), "crop": (0.08, 0.06, 0.92, 0.92), "contrast": 1.1, "feather": 0},
                {"source_idx": 1, "box": (188, 88, 318, 218), "crop": (0.10, 0.12, 0.88, 0.90), "contrast": 1.0, "feather": 0},
                {"source_idx": 2, "box": (336, 260, 466, 390), "crop": (0.05, 0.10, 0.95, 0.88), "contrast": 1.15, "feather": 0},
            ],
        },
        {
            "scenario": "three_sources_crop_feather",
            "placements": [
                {"source_idx": 0, "box": (40, 280, 216, 456), "crop": (0.15, 0.00, 0.95, 0.84), "contrast": 1.2, "feather": 8},
                {"source_idx": 1, "box": (166, 36, 342, 212), "crop": (0.00, 0.16, 0.86, 1.00), "contrast": 1.15, "feather": 8},
                {"source_idx": 2, "box": (300, 244, 484, 428), "crop": (0.12, 0.10, 0.94, 0.94), "contrast": 1.25, "feather": 8},
            ],
        },
    ]


def crop_fraction(img, frac_box):
    if frac_box is None:
        return img
    w, h = img.size
    l, t, r, b = frac_box
    box = (
        max(0, min(w - 1, int(round(l * w)))),
        max(0, min(h - 1, int(round(t * h)))),
        max(1, min(w, int(round(r * w)))),
        max(1, min(h, int(round(b * h)))),
    )
    return img.crop(box)


def feather_alpha(size, feather):
    if feather <= 0:
        return None
    w, h = size
    alpha = Image.new("L", size, 0)
    draw = ImageDraw.Draw(alpha)
    pad = max(1, int(feather))
    draw.rectangle((pad, pad, max(pad + 1, w - pad), max(pad + 1, h - pad)), fill=255)
    return alpha.filter(ImageFilter.GaussianBlur(radius=feather))


def prepare_patch(material, placement):
    box = placement["box"]
    out_size = (box[2] - box[0], box[3] - box[1])
    patch = crop_fraction(material, placement.get("crop"))
    patch = patch.resize(out_size, RESAMPLE)
    contrast = float(placement.get("contrast", 1.0))
    if abs(contrast - 1.0) > 1e-6:
        patch = ImageEnhance.Contrast(patch).enhance(contrast)
    alpha = feather_alpha(out_size, int(placement.get("feather", 0)))
    return patch, alpha


def compose_scene(background, materials, scenario):
    canvas = background.copy()
    boxes = []
    for placement in scenario["placements"]:
        source_idx = int(placement["source_idx"])
        patch, alpha = prepare_patch(materials[source_idx], placement)
        x0, y0, x1, y1 = placement["box"]
        canvas.paste(patch, (x0, y0), alpha)
        boxes.append({
            "source_idx": source_idx,
            "box": (x0, y0, x1, y1),
        })
    return canvas, boxes


def apply_composite_attacks(canvas):
    w, h = canvas.size
    resized = canvas.resize((w // 2, h // 2), RESAMPLE).resize((w, h), RESAMPLE)
    return [
        ("none", canvas),
        ("jpeg_q70", pil_jpeg(canvas, 70)),
        ("jpeg_q50", pil_jpeg(canvas, 50)),
        ("resize_0.5_jpeg70", pil_jpeg(resized, 70)),
    ]


def build_mode_image(mode, img_pt, embedded_full, area):
    if mode["region_strategy"] == "single_center":
        mask = area.baseline_center_mask(img_pt)
    elif mode["region_strategy"] == "full_image":
        mask = torch.ones((1, 1, img_pt.shape[-2], img_pt.shape[-1]), dtype=img_pt.dtype, device=img_pt.device)
    elif mode["region_strategy"] == "fixed_anchor_regions":
        masks = area.distributed_area_masks(img_pt, mode["area_percent"], mode["block_count"])
        mask = area.union_masks(masks)
    else:
        raise ValueError(f"Unknown region strategy: {mode['region_strategy']}")
    return embedded_full * mask + img_pt * (1 - mask)


def decode_image(wam, img, target_msg, area, default_transform, device, msg_predict_inference):
    img_pt = area.pil_to_tensor(img, default_transform, device)
    pred, acc, mask_pixels, fallback = area.decode(wam, img_pt, target_msg, msg_predict_inference)
    return pred, acc, mask_pixels, fallback


def write_summaries(rows, out_dir):
    summary_groups = {}
    for row in rows:
        key = (row["scheme"], row["scenario"], row["attack"], row["decode_method"])
        summary_groups.setdefault(key, []).append(row)

    summary_path = out_dir / "source_tracing_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "scenario",
                "attack",
                "decode_method",
                "mean_source_accuracy",
                "min_source_accuracy",
                "source_success_rate",
                "mean_mask_pixels",
                "mean_composite_psnr",
                "num_source_rows",
            ],
        )
        writer.writeheader()
        for (scheme, scenario, attack, method), vals in sorted(summary_groups.items()):
            accs = [float(v["bit_accuracy"]) for v in vals]
            successes = [int(v["source_success"]) for v in vals]
            mask_pixels = [int(v["mask_pixels"]) for v in vals]
            psnrs = [float(v["composite_psnr"]) for v in vals]
            writer.writerow({
                "scheme": scheme,
                "scenario": scenario,
                "attack": attack,
                "decode_method": method,
                "mean_source_accuracy": f"{np.mean(accs):.6f}",
                "min_source_accuracy": f"{np.min(accs):.6f}",
                "source_success_rate": f"{np.mean(successes):.6f}",
                "mean_mask_pixels": f"{np.mean(mask_pixels):.1f}",
                "mean_composite_psnr": f"{np.mean(psnrs):.4f}",
                "num_source_rows": len(vals),
            })

    overview_groups = {}
    for row in rows:
        key = (row["scheme"], row["decode_method"])
        overview_groups.setdefault(key, []).append(row)

    overview_path = out_dir / "source_tracing_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "decode_method",
                "mean_source_accuracy",
                "min_source_accuracy",
                "source_success_rate",
                "mean_composite_psnr",
            ],
        )
        writer.writeheader()
        for (scheme, method), vals in sorted(overview_groups.items()):
            accs = [float(v["bit_accuracy"]) for v in vals]
            successes = [int(v["source_success"]) for v in vals]
            psnrs = [float(v["composite_psnr"]) for v in vals]
            writer.writerow({
                "scheme": scheme,
                "decode_method": method,
                "mean_source_accuracy": f"{np.mean(accs):.6f}",
                "min_source_accuracy": f"{np.min(accs):.6f}",
                "source_success_rate": f"{np.mean(successes):.6f}",
                "mean_composite_psnr": f"{np.mean(psnrs):.4f}",
            })
    return summary_path, overview_path


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
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
    image_paths = sorted(image_paths)
    if len(image_paths) < 4:
        raise RuntimeError(f"Need at least four images under {args.image_dir}")

    background_path = next((p for p in image_paths if "seabackground" in p.name.lower()), image_paths[-1])
    source_paths = [p for p in image_paths if p != background_path][:3]
    if len(source_paths) < 3:
        raise RuntimeError("Need at least three source material images.")

    background = ImageOps.fit(Image.open(background_path).convert("RGB"), (args.canvas_size, args.canvas_size), method=RESAMPLE)
    clean_materials = [
        ImageOps.fit(Image.open(p).convert("RGB"), (args.material_size, args.material_size), method=RESAMPLE)
        for p in source_paths
    ]
    messages = [torch.randint(0, 2, (1, 32), device=device).float() for _ in source_paths]
    print(f"background={background_path.name}", flush=True)
    print(f"sources={[p.name for p in source_paths]}", flush=True)
    for idx, msg in enumerate(messages):
        print(f"source_{idx}_msg={msg_to_str(msg)}", flush=True)

    rows = []
    fieldnames = [
        "scheme",
        "scenario",
        "attack",
        "decode_method",
        "source_idx",
        "source_image",
        "target_message",
        "predicted_message",
        "bit_accuracy",
        "source_success",
        "mask_pixels",
        "used_fallback",
        "composite_psnr",
        "box",
    ]

    try:
        with torch.inference_mode():
            for mode in mode_definitions():
                wam.scaling_w = float(mode["scaling_w"])
                watermarked_materials = []
                for material, msg in zip(clean_materials, messages):
                    img_pt = area.pil_to_tensor(material, default_transform, device)
                    embedded = wam.embed(img_pt, msg)["imgs_w"]
                    img_w = build_mode_image(mode, img_pt, embedded, area)
                    watermarked_materials.append(area.tensor_to_pil(img_w, unnormalize_img))

                for scenario in scenario_definitions(args.canvas_size):
                    clean_composite, boxes = compose_scene(background, clean_materials, scenario)
                    wm_composite, boxes = compose_scene(background, watermarked_materials, scenario)
                    composite_psnr = psnr_pil(wm_composite, clean_composite)

                    for attack_name, attacked in apply_composite_attacks(wm_composite):
                        global_preds = {}
                        for source_idx, msg in enumerate(messages):
                            pred, acc, mask_pixels, fallback = decode_image(
                                wam, attacked, msg, area, default_transform, device, msg_predict_inference
                            )
                            global_preds[source_idx] = (pred, acc, mask_pixels, fallback)

                        for source_info in boxes:
                            source_idx = int(source_info["source_idx"])
                            target_msg = messages[source_idx]
                            source_name = source_paths[source_idx].name
                            box = source_info["box"]
                            crop = attacked.crop(box)
                            decoded_items = [
                                ("global_full_canvas", attacked, global_preds[source_idx]),
                                ("oracle_box_raw", crop, None),
                                ("localized_resize", crop.resize((args.material_size, args.material_size), RESAMPLE), None),
                            ]
                            for method, decode_img, cached in decoded_items:
                                if cached is None:
                                    pred, acc, mask_pixels, fallback = decode_image(
                                        wam, decode_img, target_msg, area, default_transform, device, msg_predict_inference
                                    )
                                else:
                                    pred, acc, mask_pixels, fallback = cached
                                row = {
                                    "scheme": mode["scheme"],
                                    "scenario": scenario["scenario"],
                                    "attack": attack_name,
                                    "decode_method": method,
                                    "source_idx": source_idx,
                                    "source_image": source_name,
                                    "target_message": msg_to_str(target_msg),
                                    "predicted_message": msg_to_str(pred),
                                    "bit_accuracy": f"{acc:.6f}",
                                    "source_success": int(acc >= 0.999),
                                    "mask_pixels": mask_pixels,
                                    "used_fallback": fallback,
                                    "composite_psnr": f"{composite_psnr:.4f}",
                                    "box": f"{box[0]},{box[1]},{box[2]},{box[3]}",
                                }
                                rows.append(row)
                                print(row, flush=True)
    finally:
        wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "source_tracing_metrics.csv"
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
