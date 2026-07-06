import argparse
import csv
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from torchvision.transforms import functional as TVF

import torch


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wam-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42424)
    parser.add_argument("--scale", type=float, default=2.5)
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def pil_to_tensor(img: Image.Image, default_transform, device):
    return default_transform(img.convert("RGB")).unsqueeze(0).to(device)


def tensor_to_pil(img_norm, unnormalize_img) -> Image.Image:
    img01 = unnormalize_img(img_norm.detach().cpu()).squeeze(0).clamp(0, 1)
    return TVF.to_pil_image(img01)


def tamper_replace_with_original(img_w_norm, img_orig_norm, rect, default_transform, unnormalize_img, device, area_mod):
    left, top, width, height = rect
    wm01 = unnormalize_img(img_w_norm.detach().clone()).clamp(0, 1)
    orig01 = unnormalize_img(img_orig_norm.detach().clone()).clamp(0, 1)
    _, _, h, w = wm01.shape
    x0 = max(0, min(w - 1, int(round(left * w))))
    y0 = max(0, min(h - 1, int(round(top * h))))
    x1 = max(x0 + 1, min(w, int(round((left + width) * w))))
    y1 = max(y0 + 1, min(h, int(round((top + height) * h))))
    wm01[:, :, y0:y1, x0:x1] = orig01[:, :, y0:y1, x0:x1]
    gt_mask = area_mod.rect_mask_like(img_orig_norm, left, top, width, height)
    attacked = pil_to_tensor(TVF.to_pil_image(wm01.squeeze(0).cpu()), default_transform, device)
    return attacked, gt_mask


def tamper_black(img_w_norm, img_orig_norm, rect, default_transform, unnormalize_img, device, area_mod):
    left, top, width, height = rect
    wm01 = unnormalize_img(img_w_norm.detach().clone()).clamp(0, 1)
    _, _, h, w = wm01.shape
    x0 = max(0, min(w - 1, int(round(left * w))))
    y0 = max(0, min(h - 1, int(round(top * h))))
    x1 = max(x0 + 1, min(w, int(round((left + width) * w))))
    y1 = max(y0 + 1, min(h, int(round((top + height) * h))))
    wm01[:, :, y0:y1, x0:x1] = 0.0
    gt_mask = area_mod.rect_mask_like(img_orig_norm, left, top, width, height)
    attacked = pil_to_tensor(TVF.to_pil_image(wm01.squeeze(0).cpu()), default_transform, device)
    return attacked, gt_mask


def detect_mask_and_bits(wam, img_norm, target_msg, msg_predict_inference):
    preds = wam.detect(img_norm)["preds"]
    mask_probs = torch.sigmoid(preds[:, 0:1, :, :])
    bit_logits = preds[:, 1:, :, :]
    mask_pixels = int((mask_probs > 0.5).sum().item())
    if mask_pixels < 8:
        pred = torch.zeros_like(target_msg)
        return mask_probs, pred, 0.0, mask_pixels, 1
    pred = msg_predict_inference(bit_logits, mask_probs, method="semihard").float()
    acc = float((pred == target_msg).float().mean().item())
    return mask_probs, pred, acc, mask_pixels, 0


def metrics(pred_mask, gt_mask):
    pred = pred_mask.bool()
    gt = gt_mask.bool()
    tp = float((pred & gt).sum().item())
    fp = float((pred & ~gt).sum().item())
    fn = float((~pred & gt).sum().item())
    precision = tp / (tp + fp + 1e-6)
    recall = tp / (tp + fn + 1e-6)
    f1 = 2.0 * precision * recall / (precision + recall + 1e-6)
    iou = tp / (tp + fp + fn + 1e-6)
    return precision, recall, f1, iou


def summarize(rows, out_dir):
    groups = {}
    for row in rows:
        key = (row["scheme"], row["tamper"], row["localizer"])
        groups.setdefault(key, []).append(row)

    summary_path = out_dir / "wam_tamper_localization_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "tamper",
                "localizer",
                "mean_global_f1",
                "mean_global_iou",
                "mean_covered_f1",
                "mean_covered_iou",
                "mean_tamper_coverage",
                "mean_bit_accuracy",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scheme, tamper, localizer), vals in sorted(groups.items(), key=lambda item: item[0]):
            writer.writerow({
                "scheme": scheme,
                "tamper": tamper,
                "localizer": localizer,
                "mean_global_f1": f"{np.mean([float(v['global_f1']) for v in vals]):.6f}",
                "mean_global_iou": f"{np.mean([float(v['global_iou']) for v in vals]):.6f}",
                "mean_covered_f1": f"{np.mean([float(v['covered_f1']) for v in vals]):.6f}",
                "mean_covered_iou": f"{np.mean([float(v['covered_iou']) for v in vals]):.6f}",
                "mean_tamper_coverage": f"{np.mean([float(v['tamper_coverage']) for v in vals]):.6f}",
                "mean_bit_accuracy": f"{np.mean([float(v['bit_accuracy']) for v in vals]):.6f}",
                "num_images": len(vals),
            })

    overview = {}
    for row in rows:
        key = (row["scheme"], row["localizer"])
        overview.setdefault(key, []).append(row)

    overview_path = out_dir / "wam_tamper_localization_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "localizer",
                "mean_global_f1",
                "mean_global_iou",
                "mean_covered_f1",
                "mean_covered_iou",
                "mean_tamper_coverage",
                "mean_bit_accuracy",
            ],
        )
        writer.writeheader()
        for (scheme, localizer), vals in sorted(overview.items(), key=lambda item: item[0]):
            writer.writerow({
                "scheme": scheme,
                "localizer": localizer,
                "mean_global_f1": f"{np.mean([float(v['global_f1']) for v in vals]):.6f}",
                "mean_global_iou": f"{np.mean([float(v['global_iou']) for v in vals]):.6f}",
                "mean_covered_f1": f"{np.mean([float(v['covered_f1']) for v in vals]):.6f}",
                "mean_covered_iou": f"{np.mean([float(v['covered_iou']) for v in vals]):.6f}",
                "mean_tamper_coverage": f"{np.mean([float(v['tamper_coverage']) for v in vals]):.6f}",
                "mean_bit_accuracy": f"{np.mean([float(v['bit_accuracy']) for v in vals]):.6f}",
            })
    return summary_path, overview_path


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    task_script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(task_script_dir))
    import wam_attack_eval as atk
    import wam_dwsf_area_sweep as area

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

    tamper_specs = [
        ("remove_center_25", (0.25, 0.25, 0.50, 0.50), tamper_replace_with_original),
        ("remove_center_40", (0.1838, 0.1838, 0.6324, 0.6324), tamper_replace_with_original),
        ("remove_top_left_25", (0.0, 0.0, 0.50, 0.50), tamper_replace_with_original),
        ("remove_bottom_right_25", (0.5, 0.5, 0.50, 0.50), tamper_replace_with_original),
        ("black_center_25", (0.25, 0.25, 0.50, 0.50), tamper_black),
    ]

    rows = []
    fieldnames = [
        "image",
        "scheme",
        "tamper",
        "localizer",
        "message",
        "predicted",
        "bit_accuracy",
        "mask_pixels",
        "tamper_coverage",
        "global_precision",
        "global_recall",
        "global_f1",
        "global_iou",
        "covered_precision",
        "covered_recall",
        "covered_f1",
        "covered_iou",
        "psnr_watermarked",
        "psnr_tampered",
    ]

    with torch.inference_mode():
        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = default_transform(img).unsqueeze(0).to(device)
            embedded_full = wam.embed(img_pt, target_msg)["imgs_w"]

            single_mask = area.baseline_center_mask(img_pt)
            dwsf_q30_mask = area.union_masks(area.dwsf_area_masks(img_pt, 30, 5))
            dwsf_q50_mask = area.union_masks(area.dwsf_area_masks(img_pt, 50, 5))

            schemes = [
                ("single_center_50pct", single_mask, embedded_full * single_mask + img_pt * (1 - single_mask)),
                ("dwsf_q30_5block", dwsf_q30_mask, embedded_full * dwsf_q30_mask + img_pt * (1 - dwsf_q30_mask)),
                ("dwsf_q50_5block", dwsf_q50_mask, embedded_full * dwsf_q50_mask + img_pt * (1 - dwsf_q50_mask)),
            ]

            for scheme, placed_mask, img_w in schemes:
                clean_probs, _, _, _, _ = detect_mask_and_bits(wam, img_w, target_msg, msg_predict_inference)
                psnr_watermarked = atk.psnr_tensor(unnormalize_img(img_w), unnormalize_img(img_pt))
                for tamper_name, rect, tamper_fn in tamper_specs:
                    attacked, gt_mask = tamper_fn(img_w, img_pt, rect, default_transform, unnormalize_img, device, area)
                    attacked_probs, pred_msg, bit_acc, mask_pixels, _ = detect_mask_and_bits(wam, attacked, target_msg, msg_predict_inference)
                    psnr_tampered = atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt))
                    det_size = attacked_probs.shape[-2:]
                    placed_det = torch.nn.functional.interpolate(placed_mask.float(), size=det_size, mode="nearest") > 0.5
                    gt_det = torch.nn.functional.interpolate(gt_mask.float(), size=det_size, mode="nearest") > 0.5

                    localizers = {
                        "expected_missing": (placed_det, placed_det & (attacked_probs < 0.35)),
                        "clean_missing": ((clean_probs > 0.5), (clean_probs > 0.5) & (attacked_probs < 0.35)),
                        "prob_drop": ((clean_probs > 0.35), (clean_probs > 0.35) & ((clean_probs - attacked_probs) > 0.35)),
                    }
                    for localizer, (ref_mask, pred_mask) in localizers.items():
                        gt_bool = gt_det
                        covered_gt = gt_bool & ref_mask
                        coverage = float(covered_gt.sum().item() / (gt_bool.sum().item() + 1e-6))
                        gp, gr, gf1, giou = metrics(pred_mask, gt_bool)
                        cp, cr, cf1, ciou = metrics(pred_mask, covered_gt)
                        row = {
                            "image": image_path.name,
                            "scheme": scheme,
                            "tamper": tamper_name,
                            "localizer": localizer,
                            "message": msg_to_str(target_msg),
                            "predicted": msg_to_str(pred_msg),
                            "bit_accuracy": f"{bit_acc:.6f}",
                            "mask_pixels": mask_pixels,
                            "tamper_coverage": f"{coverage:.6f}",
                            "global_precision": f"{gp:.6f}",
                            "global_recall": f"{gr:.6f}",
                            "global_f1": f"{gf1:.6f}",
                            "global_iou": f"{giou:.6f}",
                            "covered_precision": f"{cp:.6f}",
                            "covered_recall": f"{cr:.6f}",
                            "covered_f1": f"{cf1:.6f}",
                            "covered_iou": f"{ciou:.6f}",
                            "psnr_watermarked": f"{psnr_watermarked:.4f}",
                            "psnr_tampered": f"{psnr_tampered:.4f}",
                        }
                        rows.append(row)
                        print(row, flush=True)

    wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "wam_tamper_localization_metrics.csv"
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
