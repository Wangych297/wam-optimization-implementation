import argparse
import csv
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F
from skimage.measure import label as cc_label


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wam-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=456)
    parser.add_argument("--baseline-mask-ratio", type=float, default=0.5)
    parser.add_argument("--regions", type=int, default=5)
    parser.add_argument("--region-ratio", type=float, default=0.1)
    parser.add_argument("--min-component-pixels", type=int, default=80)
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def decode_global(wam, attacked, target_msg, msg_predict_inference):
    preds = wam.detect(attacked)["preds"]
    mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
    bit_preds = preds[:, 1:, :, :]
    mask_pixels = int((mask_preds > 0.5).sum().item())
    if mask_pixels < 8:
        pred = torch.zeros_like(target_msg)
        return pred, 0.0, mask_preds, bit_preds, mask_pixels, 1
    pred = msg_predict_inference(bit_preds, mask_preds, method="semihard").float()
    acc = float((pred == target_msg).float().mean().item())
    return pred, acc, mask_preds, bit_preds, mask_pixels, 0


def component_predictions(bit_preds, mask_preds, min_pixels):
    mask = (mask_preds[0, 0].detach().cpu().numpy() > 0.5)
    labels = cc_label(mask, connectivity=2)
    comps = []
    bit_map = bit_preds[0].detach().cpu()  # K H W
    for label_id in range(1, int(labels.max()) + 1):
        ys, xs = np.where(labels == label_id)
        if len(xs) < min_pixels:
            continue
        values = bit_map[:, ys, xs].float()  # K N
        avg = values.mean(dim=1)
        bits = (avg > 0.5).float()
        confidence = torch.abs(avg - 0.5).mean().item()
        comps.append({
            "label": label_id,
            "pixels": int(len(xs)),
            "avg": avg,
            "bits": bits,
            "confidence": float(confidence),
        })
    return comps


def fuse_majority(components, target_msg):
    if not components:
        pred = torch.zeros_like(target_msg.cpu())
        return pred, 0.0
    bits = torch.stack([c["bits"] for c in components], dim=0)
    pred = (bits.mean(dim=0) >= 0.5).float().unsqueeze(0)
    acc = float((pred == target_msg.cpu()).float().mean().item())
    return pred, acc


def fuse_confidence(components, target_msg):
    if not components:
        pred = torch.zeros_like(target_msg.cpu())
        return pred, 0.0
    avgs = torch.stack([c["avg"] for c in components], dim=0)
    weights = torch.tensor(
        [max(1e-6, c["confidence"]) * max(1, c["pixels"]) for c in components],
        dtype=torch.float32,
    )
    weights = weights / weights.sum()
    pred = ((avgs * weights[:, None]).sum(dim=0) > 0.5).float().unsqueeze(0)
    acc = float((pred == target_msg.cpu()).float().mean().item())
    return pred, acc


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)

    task_script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(task_script_dir))
    import wam_attack_eval as atk

    wam_root = Path(args.wam_root).resolve()
    sys.path.insert(0, str(wam_root))
    sys.path.insert(0, str(wam_root / "notebooks"))
    os.chdir(wam_root)

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

    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]
    if not image_paths:
        raise RuntimeError(f"No images found under {args.image_dir}")

    attacks = [("none", None)]
    attacks += [(f"jpeg_q{q}", ("jpeg", q)) for q in (95, 85, 75, 65, 50, 30)]
    attacks += [(f"resize_{s}", ("resize", s)) for s in (0.75, 0.5, 0.25)]
    attacks += [(f"center_crop_{r}", ("center_crop", r)) for r in (0.9, 0.75, 0.5)]
    attacks += [(f"random_crop_{r}", ("random_crop", r)) for r in (0.9, 0.75, 0.5)]
    attacks += [(f"occlusion_{r}", ("occlusion", r)) for r in (0.05, 0.1, 0.2)]
    attacks += [(f"partial_removal_{r}", ("partial_removal", r)) for r in (0.05, 0.1, 0.2)]

    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={msg_to_str(target_msg)}", flush=True)

    rows = []
    fieldnames = [
        "image",
        "attack",
        "scheme",
        "decoder",
        "message",
        "predicted",
        "bit_accuracy",
        "message_success",
        "psnr_vs_original",
        "mask_pixels",
        "component_count",
        "used_fallback",
    ]

    def apply_attack(img_w, img_orig, spec):
        if spec is None:
            return img_w
        if spec[0] == "jpeg":
            return atk.apply_jpeg(img_w, spec[1], default_transform, unnormalize_img, device)
        if spec[0] == "resize":
            return atk.apply_resize(img_w, spec[1], default_transform, unnormalize_img, device)
        if spec[0] == "center_crop":
            return atk.apply_center_crop(img_w, spec[1], default_transform, unnormalize_img, device)
        if spec[0] == "random_crop":
            return atk.apply_random_crop(img_w, spec[1], default_transform, unnormalize_img, device, rng)
        if spec[0] == "occlusion":
            return atk.apply_occlusion(img_w, spec[1], default_transform, unnormalize_img, device, rng)
        if spec[0] == "partial_removal":
            return atk.apply_partial_removal(img_w, img_orig, spec[1], default_transform, unnormalize_img, device, rng)
        raise ValueError(spec)

    with torch.inference_mode():
        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = default_transform(img).unsqueeze(0).to(device)

            baseline_outputs = wam.embed(img_pt, target_msg)
            baseline_mask = create_random_mask(
                img_pt,
                num_masks=1,
                mask_percentage=args.baseline_mask_ratio,
            )
            baseline_img = baseline_outputs["imgs_w"] * baseline_mask + img_pt * (1 - baseline_mask)

            region_masks = create_random_mask(
                img_pt,
                num_masks=args.regions,
                mask_percentage=args.region_ratio,
            )
            redundant_img = img_pt.clone()
            for idx in range(args.regions):
                outputs = wam.embed(img_pt, target_msg)
                mask = region_masks[idx : idx + 1]
                redundant_img = outputs["imgs_w"] * mask + redundant_img * (1 - mask)

            for attack_name, spec in attacks:
                for scheme, img_w in (("baseline_single_region", baseline_img), ("dwsf_redundant_regions", redundant_img)):
                    attacked = apply_attack(img_w, img_pt, spec)
                    pred, acc, mask_preds, bit_preds, mask_pixels, fallback = decode_global(
                        wam,
                        attacked,
                        target_msg,
                        msg_predict_inference,
                    )
                    psnr_val = atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt))
                    rows.append({
                        "image": image_path.name,
                        "attack": attack_name,
                        "scheme": scheme,
                        "decoder": "global_mask_average",
                        "message": msg_to_str(target_msg),
                        "predicted": msg_to_str(pred),
                        "bit_accuracy": f"{acc:.6f}",
                        "message_success": int(acc >= 0.999),
                        "psnr_vs_original": f"{psnr_val:.4f}",
                        "mask_pixels": mask_pixels,
                        "component_count": "",
                        "used_fallback": fallback,
                    })

                    if scheme == "dwsf_redundant_regions":
                        components = component_predictions(bit_preds, mask_preds, args.min_component_pixels)
                        pred_m, acc_m = fuse_majority(components, target_msg)
                        pred_c, acc_c = fuse_confidence(components, target_msg)
                        rows.append({
                            "image": image_path.name,
                            "attack": attack_name,
                            "scheme": scheme,
                            "decoder": "component_majority",
                            "message": msg_to_str(target_msg),
                            "predicted": msg_to_str(pred_m),
                            "bit_accuracy": f"{acc_m:.6f}",
                            "message_success": int(acc_m >= 0.999),
                            "psnr_vs_original": f"{psnr_val:.4f}",
                            "mask_pixels": mask_pixels,
                            "component_count": len(components),
                            "used_fallback": int(len(components) == 0),
                        })
                        rows.append({
                            "image": image_path.name,
                            "attack": attack_name,
                            "scheme": scheme,
                            "decoder": "component_confidence_weighted",
                            "message": msg_to_str(target_msg),
                            "predicted": msg_to_str(pred_c),
                            "bit_accuracy": f"{acc_c:.6f}",
                            "message_success": int(acc_c >= 0.999),
                            "psnr_vs_original": f"{psnr_val:.4f}",
                            "mask_pixels": mask_pixels,
                            "component_count": len(components),
                            "used_fallback": int(len(components) == 0),
                        })
                    print(rows[-1], flush=True)

    metrics_path = out_dir / "wam_dwsf_redundant_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    groups = {}
    for row in rows:
        key = (row["attack"], row["scheme"], row["decoder"])
        groups.setdefault(key, []).append(float(row["bit_accuracy"]))
    summary_path = out_dir / "wam_dwsf_redundant_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["attack", "scheme", "decoder", "mean_bit_accuracy", "min_bit_accuracy", "num_images"],
        )
        writer.writeheader()
        for (attack, scheme, decoder), vals in groups.items():
            writer.writerow({
                "attack": attack,
                "scheme": scheme,
                "decoder": decoder,
                "mean_bit_accuracy": f"{np.mean(vals):.6f}",
                "min_bit_accuracy": f"{np.min(vals):.6f}",
                "num_images": len(vals),
            })

    print(f"metrics={metrics_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
