import argparse
import csv
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import torch


HAMMING_INTERLEAVE_POS = [0, 7, 14, 21, 28, 3, 10, 17, 24, 31, 6, 13, 20, 27, 2, 9, 16, 23, 30, 5, 12]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wam-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--seed", type=int, default=16180)
    parser.add_argument("--scale", type=float, default=2.5)
    parser.add_argument("--area", type=float, default=30.0)
    parser.add_argument("--block-count", type=int, default=5)
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def encode_uncoded10(payload, filler):
    msg = torch.zeros((1, 32), device=payload.device)
    msg[:, :10] = payload
    msg[:, 10:] = filler[:, :22]
    return msg


def decode_uncoded10(pred_msg):
    return pred_msg[:, :10]


def encode_rep3_adjacent10(payload, filler):
    msg = torch.zeros((1, 32), device=payload.device)
    for i in range(10):
        msg[:, 3 * i : 3 * i + 3] = payload[:, i : i + 1]
    msg[:, 30:] = filler[:, :2]
    return msg


def decode_rep3_adjacent10(pred_msg):
    decoded = []
    for i in range(10):
        triplet = pred_msg[:, 3 * i : 3 * i + 3]
        decoded.append((triplet.sum(dim=1, keepdim=True) >= 2).float())
    return torch.cat(decoded, dim=1)


def encode_rep3_interleaved10(payload, filler):
    msg = torch.zeros((1, 32), device=payload.device)
    for i in range(10):
        msg[:, i] = payload[:, i]
        msg[:, i + 10] = payload[:, i]
        msg[:, i + 20] = payload[:, i]
    msg[:, 30:] = filler[:, :2]
    return msg


def decode_rep3_interleaved10(pred_msg):
    decoded = []
    for i in range(10):
        triplet = torch.stack([pred_msg[:, i], pred_msg[:, i + 10], pred_msg[:, i + 20]], dim=1)
        decoded.append((triplet.sum(dim=1, keepdim=True) >= 2).float())
    return torch.cat(decoded, dim=1)


def hamming74_encode_group(data4):
    d1, d2, d3, d4 = data4[:, 0:1], data4[:, 1:2], data4[:, 2:3], data4[:, 3:4]
    p1 = (d1 + d2 + d4) % 2
    p2 = (d1 + d3 + d4) % 2
    p4 = (d2 + d3 + d4) % 2
    return torch.cat([p1, p2, d1, p4, d2, d3, d4], dim=1)


def hamming74_decode_group(code7):
    bits = code7.clone().long()
    s1 = (bits[:, 0] + bits[:, 2] + bits[:, 4] + bits[:, 6]) % 2
    s2 = (bits[:, 1] + bits[:, 2] + bits[:, 5] + bits[:, 6]) % 2
    s4 = (bits[:, 3] + bits[:, 4] + bits[:, 5] + bits[:, 6]) % 2
    syndrome = s1 + 2 * s2 + 4 * s4
    for row in range(bits.shape[0]):
        pos = int(syndrome[row].item())
        if 1 <= pos <= 7:
            bits[row, pos - 1] = 1 - bits[row, pos - 1]
    return torch.stack([bits[:, 2], bits[:, 4], bits[:, 5], bits[:, 6]], dim=1).float()


def hamming74_encode_12(data12):
    groups = []
    for start in (0, 4, 8):
        groups.append(hamming74_encode_group(data12[:, start : start + 4]))
    return torch.cat(groups, dim=1)


def hamming74_decode_12(code21):
    groups = []
    for start in (0, 7, 14):
        groups.append(hamming74_decode_group(code21[:, start : start + 7]))
    return torch.cat(groups, dim=1)


def encode_hamming74_10(payload, filler):
    pad = torch.zeros((payload.shape[0], 2), dtype=payload.dtype, device=payload.device)
    data12 = torch.cat([payload, pad], dim=1)
    code21 = hamming74_encode_12(data12)
    msg = torch.zeros((1, 32), device=payload.device)
    msg[:, :21] = code21
    msg[:, 21:] = filler[:, :11]
    return msg


def decode_hamming74_10(pred_msg):
    data12 = hamming74_decode_12(pred_msg[:, :21])
    return data12[:, :10]


def encode_hamming74_interleaved10(payload, filler):
    pad = torch.zeros((payload.shape[0], 2), dtype=payload.dtype, device=payload.device)
    data12 = torch.cat([payload, pad], dim=1)
    code21 = hamming74_encode_12(data12)
    msg = torch.zeros((1, 32), device=payload.device)
    used = set(HAMMING_INTERLEAVE_POS)
    for idx, pos in enumerate(HAMMING_INTERLEAVE_POS):
        msg[:, pos] = code21[:, idx]
    filler_idx = 0
    for pos in range(32):
        if pos not in used:
            msg[:, pos] = filler[:, filler_idx]
            filler_idx += 1
    return msg


def decode_hamming74_interleaved10(pred_msg):
    gathered = torch.stack([pred_msg[:, pos] for pos in HAMMING_INTERLEAVE_POS], dim=1)
    data12 = hamming74_decode_12(gathered)
    return data12[:, :10]


def summarize(rows, out_dir):
    groups = {}
    for row in rows:
        key = (row["coding"], row["attack"])
        groups.setdefault(key, []).append(row)

    summary_path = out_dir / "wam_payload_ecc_variants_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "coding",
                "attack",
                "mean_payload_accuracy",
                "payload_success_rate",
                "min_payload_accuracy",
                "mean_full_bit_accuracy",
                "num_images",
            ],
        )
        writer.writeheader()
        for (coding, attack), vals in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
            payload_accs = [float(v["payload_accuracy"]) for v in vals]
            successes = [int(v["payload_success"]) for v in vals]
            full_accs = [float(v["full_bit_accuracy"]) for v in vals]
            writer.writerow({
                "coding": coding,
                "attack": attack,
                "mean_payload_accuracy": f"{np.mean(payload_accs):.6f}",
                "payload_success_rate": f"{np.mean(successes):.6f}",
                "min_payload_accuracy": f"{np.min(payload_accs):.6f}",
                "mean_full_bit_accuracy": f"{np.mean(full_accs):.6f}",
                "num_images": len(vals),
            })

    attack_order = [
        "none",
        "crop_bottom_right_50",
        "crop_center_50",
        "jpeg_q30",
        "jpeg_q20",
        "resize_0.25_jpeg_q50",
    ]
    overview = {}
    for row in rows:
        overview.setdefault(row["coding"], {"attacks": {}})
        overview[row["coding"]]["attacks"].setdefault(row["attack"], []).append(float(row["payload_success"]))

    overview_path = out_dir / "wam_payload_ecc_variants_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["coding", "mean_selected_payload_success", "worst_selected_payload_success"] + [f"{a}_success" for a in attack_order],
        )
        writer.writeheader()
        for coding, data in sorted(overview.items()):
            selected = []
            row = {"coding": coding}
            for attack in attack_order:
                vals = data["attacks"].get(attack, [])
                mean_val = float(np.mean(vals)) if vals else np.nan
                row[f"{attack}_success"] = "" if np.isnan(mean_val) else f"{mean_val:.6f}"
                if attack != "none" and vals:
                    selected.append(mean_val)
            row["mean_selected_payload_success"] = f"{np.mean(selected):.6f}" if selected else ""
            row["worst_selected_payload_success"] = f"{np.min(selected):.6f}" if selected else ""
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
    import wam_dwsf_area_sweep as area
    import wam_payload_ecc_eval as ecc_base

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

    payload = torch.randint(0, 2, (1, 10), device=device).float()
    filler = torch.randint(0, 2, (1, 22), device=device).float()
    print(f"payload={msg_to_str(payload)}", flush=True)
    print(f"scale={args.scale} area={args.area} block_count={args.block_count}", flush=True)

    coding_specs = [
        ("uncoded10", encode_uncoded10, decode_uncoded10),
        ("rep3_adjacent10", encode_rep3_adjacent10, decode_rep3_adjacent10),
        ("rep3_interleaved10", encode_rep3_interleaved10, decode_rep3_interleaved10),
        ("hamming74_10", encode_hamming74_10, decode_hamming74_10),
        ("hamming74_interleaved10", encode_hamming74_interleaved10, decode_hamming74_interleaved10),
    ]

    attacks = [
        ("none", lambda img_w: img_w),
        ("crop_bottom_right_50", lambda img_w: area.crop_region(img_w, 0.5, 0.5, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_center_50", lambda img_w: area.crop_region(img_w, 0.25, 0.25, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("jpeg_q30", lambda img_w: atk.apply_jpeg(img_w, 30, default_transform, unnormalize_img, device)),
        ("jpeg_q20", lambda img_w: atk.apply_jpeg(img_w, 20, default_transform, unnormalize_img, device)),
        ("resize_0.25_jpeg_q50", lambda img_w: area.resize_then_jpeg(img_w, 0.25, 50, atk, default_transform, unnormalize_img, device)),
    ]

    rows = []
    fieldnames = [
        "image",
        "scheme",
        "scaling_w",
        "area_percent",
        "block_count",
        "coding",
        "attack",
        "payload",
        "decoded_payload",
        "payload_accuracy",
        "payload_success",
        "full_message",
        "predicted_full_message",
        "full_bit_accuracy",
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

        for coding, encoder, decoder in coding_specs:
            target_msg = encoder(payload, filler)
            for image_name, img_pt in cached_inputs:
                embedded_full = wam.embed(img_pt, target_msg)["imgs_w"]
                mask_union = area.union_masks(area.dwsf_area_masks(img_pt, args.area, args.block_count))
                dwsf_img = embedded_full * mask_union + img_pt * (1 - mask_union)
                psnr_watermarked = atk.psnr_tensor(unnormalize_img(dwsf_img), unnormalize_img(img_pt))
                for attack_name, attack_fn in attacks:
                    attacked = attack_fn(dwsf_img)
                    pred_msg, full_acc, mask_pixels, fallback = ecc_base.decode_wam(wam, attacked, target_msg, msg_predict_inference)
                    decoded_payload = decoder(pred_msg)
                    payload_acc = float((decoded_payload == payload).float().mean().item())
                    row = {
                        "image": image_name,
                        "scheme": "dwsf_q30_5block",
                        "scaling_w": f"{args.scale:.4f}",
                        "area_percent": f"{args.area:.0f}",
                        "block_count": str(args.block_count),
                        "coding": coding,
                        "attack": attack_name,
                        "payload": msg_to_str(payload),
                        "decoded_payload": msg_to_str(decoded_payload),
                        "payload_accuracy": f"{payload_acc:.6f}",
                        "payload_success": int(payload_acc >= 0.999),
                        "full_message": msg_to_str(target_msg),
                        "predicted_full_message": msg_to_str(pred_msg),
                        "full_bit_accuracy": f"{full_acc:.6f}",
                        "psnr_watermarked": f"{psnr_watermarked:.4f}",
                        "psnr_attacked": f"{atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt)):.4f}",
                        "mask_pixels": mask_pixels,
                        "used_fallback": fallback,
                    }
                    rows.append(row)
                    print(row, flush=True)

    wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "wam_payload_ecc_variants_metrics.csv"
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
