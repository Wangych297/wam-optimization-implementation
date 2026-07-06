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
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=8642)
    parser.add_argument("--scales", nargs="+", type=float, default=[1.5, 2.0, 2.5, 3.0])
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


def baseline_center_mask(img_pt):
    side = 0.5 ** 0.5
    margin = (1.0 - side) / 2.0
    return rect_mask_like(img_pt, margin, margin, side, side)


def five_region_masks(img_pt):
    side = 0.1 ** 0.5
    center = (1.0 - side) / 2.0
    positions = [
        (0.0, 0.0),
        (1.0 - side, 0.0),
        (0.0, 1.0 - side),
        (1.0 - side, 1.0 - side),
        (center, center),
    ]
    return [rect_mask_like(img_pt, left, top, side, side) for left, top in positions]


def pil_to_tensor(img: Image.Image, default_transform, device):
    return default_transform(img.convert("RGB")).unsqueeze(0).to(device)


def tensor_to_pil(img_norm, unnormalize_img) -> Image.Image:
    img01 = unnormalize_img(img_norm.detach().cpu()).squeeze(0).clamp(0, 1)
    return TVF.to_pil_image(img01)


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
        key = (row["scheme"], row["scaling_w"], row["attack"])
        groups.setdefault(key, []).append(row)

    summary_path = out_dir / "spatial_strength_profile_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "scaling_w",
                "attack",
                "mean_bit_accuracy",
                "min_bit_accuracy",
                "mean_psnr_watermarked",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scheme, scale, attack), vals in sorted(groups.items(), key=lambda item: (item[0][0], float(item[0][1]), item[0][2])):
            accs = [float(v["bit_accuracy"]) for v in vals]
            psnrs = [float(v["psnr_watermarked"]) for v in vals]
            writer.writerow({
                "scheme": scheme,
                "scaling_w": scale,
                "attack": attack,
                "mean_bit_accuracy": f"{np.mean(accs):.6f}",
                "min_bit_accuracy": f"{np.min(accs):.6f}",
                "mean_psnr_watermarked": f"{np.mean(psnrs):.4f}",
                "num_images": len(vals),
            })

    overview = {}
    for row in rows:
        key = (row["scheme"], row["scaling_w"])
        overview.setdefault(key, {"psnr": [], "attacks": {}})
        overview[key]["psnr"].append(float(row["psnr_watermarked"]))
        overview[key]["attacks"].setdefault(row["attack"], []).append(float(row["bit_accuracy"]))

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
    overview_path = out_dir / "spatial_strength_profile_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["scheme", "scaling_w", "mean_psnr_watermarked", "mean_selected_attack_accuracy"] + [f"{a}_mean" for a in attack_order],
        )
        writer.writeheader()
        for (scheme, scale), data in sorted(overview.items(), key=lambda item: (item[0][0], float(item[0][1]))):
            selected = []
            row = {
                "scheme": scheme,
                "scaling_w": scale,
                "mean_psnr_watermarked": f"{np.mean(data['psnr']):.4f}",
            }
            for attack in attack_order:
                vals = data["attacks"].get(attack, [])
                mean_val = float(np.mean(vals)) if vals else np.nan
                row[f"{attack}_mean"] = "" if np.isnan(mean_val) else f"{mean_val:.6f}"
                if attack != "none" and vals:
                    selected.append(mean_val)
            row["mean_selected_attack_accuracy"] = f"{np.mean(selected):.6f}" if selected else ""
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
    print(f"message={msg_to_str(target_msg)}", flush=True)

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

        for scale in args.scales:
            wam.scaling_w = float(scale)
            print(f"scaling_w={scale}", flush=True)
            for image_name, img_pt in cached_inputs:
                base_outputs = wam.embed(img_pt, target_msg)
                base_mask = baseline_center_mask(img_pt)
                base_img = base_outputs["imgs_w"] * base_mask + img_pt * (1 - base_mask)

                distributed_img = img_pt.clone()
                for mask in five_region_masks(img_pt):
                    outputs = wam.embed(img_pt, target_msg)
                    distributed_img = outputs["imgs_w"] * mask + distributed_img * (1 - mask)

                schemes = [
                    ("single_center_50pct", base_img),
                    ("five_region_spatial", distributed_img),
                ]
                for scheme, img_w in schemes:
                    psnr_watermarked = atk.psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt))
                    for attack_name, attack_fn in attacks:
                        attacked = attack_fn(img_w, img_pt)
                        pred, acc, mask_pixels, fallback = decode(wam, attacked, target_msg, msg_predict_inference)
                        row = {
                            "image": image_name,
                            "scheme": scheme,
                            "scaling_w": f"{scale:.4f}",
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

    metrics_path = out_dir / "spatial_strength_profile_metrics.csv"
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
