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
    parser.add_argument("--seed", type=int, default=1122)
    parser.add_argument("--scales", nargs="+", type=float, default=[2.5, 3.0])
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


def encode_uncoded10(payload, filler):
    msg = torch.zeros((1, 32), device=payload.device)
    msg[:, :10] = payload
    msg[:, 10:] = filler[:, :22]
    return msg


def decode_uncoded10(pred_msg):
    return pred_msg[:, :10]


def encode_rep3_10(payload, filler):
    msg = torch.zeros((1, 32), device=payload.device)
    for i in range(10):
        msg[:, 3 * i : 3 * i + 3] = payload[:, i : i + 1]
    msg[:, 30:] = filler[:, :2]
    return msg


def decode_rep3_10(pred_msg):
    decoded = []
    for i in range(10):
        triplet = pred_msg[:, 3 * i : 3 * i + 3]
        decoded.append((triplet.sum(dim=1, keepdim=True) >= 2).float())
    return torch.cat(decoded, dim=1)


def decode_wam(wam, attacked, target_msg, msg_predict_inference):
    preds = wam.detect(attacked)["preds"]
    mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
    bit_preds = preds[:, 1:, :, :]
    mask_pixels = int((mask_preds > 0.5).sum().item())
    if mask_pixels < 8:
        return torch.zeros_like(target_msg), 0.0, mask_pixels, 1
    pred_msg = msg_predict_inference(bit_preds, mask_preds, method="semihard").float()
    full_acc = float((pred_msg == target_msg).float().mean().item())
    return pred_msg, full_acc, mask_pixels, 0


def summarize(rows, out_dir):
    groups = {}
    for row in rows:
        key = (row["scaling_w"], row["coding"], row["attack"])
        groups.setdefault(key, []).append(row)
    summary_path = out_dir / "repetition_payload_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scaling_w",
                "coding",
                "attack",
                "mean_payload_accuracy",
                "payload_success_rate",
                "mean_full_bit_accuracy",
                "min_payload_accuracy",
                "num_images",
            ],
        )
        writer.writeheader()
        for (scale, coding, attack), vals in sorted(groups.items(), key=lambda item: (float(item[0][0]), item[0][1], item[0][2])):
            payload_accs = [float(v["payload_accuracy"]) for v in vals]
            successes = [int(v["payload_success"]) for v in vals]
            full_accs = [float(v["full_bit_accuracy"]) for v in vals]
            writer.writerow({
                "scaling_w": scale,
                "coding": coding,
                "attack": attack,
                "mean_payload_accuracy": f"{np.mean(payload_accs):.6f}",
                "payload_success_rate": f"{np.mean(successes):.6f}",
                "mean_full_bit_accuracy": f"{np.mean(full_accs):.6f}",
                "min_payload_accuracy": f"{np.min(payload_accs):.6f}",
                "num_images": len(vals),
            })
    return summary_path


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

    payload = torch.randint(0, 2, (1, 10), device=device).float()
    filler = torch.randint(0, 2, (1, 22), device=device).float()
    print(f"payload={msg_to_str(payload)}", flush=True)

    coding_specs = [
        ("uncoded10", encode_uncoded10, decode_uncoded10),
        ("rep3_10", encode_rep3_10, decode_rep3_10),
    ]

    attacks = [
        ("none", lambda img_w: img_w),
        ("crop_bottom_right_50", lambda img_w: crop_region(img_w, 0.5, 0.5, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_center_50", lambda img_w: crop_region(img_w, 0.25, 0.25, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("jpeg_q30", lambda img_w: atk.apply_jpeg(img_w, 30, default_transform, unnormalize_img, device)),
        ("jpeg_q20", lambda img_w: atk.apply_jpeg(img_w, 20, default_transform, unnormalize_img, device)),
        ("resize_0.25_jpeg_q50", lambda img_w: resize_then_jpeg(img_w, 0.25, 50, atk, default_transform, unnormalize_img, device)),
    ]

    rows = []
    fieldnames = [
        "image",
        "scheme",
        "scaling_w",
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

        for scale in args.scales:
            wam.scaling_w = float(scale)
            print(f"scaling_w={scale}", flush=True)
            for coding, encoder, decoder in coding_specs:
                target_msg = encoder(payload, filler)
                for image_name, img_pt in cached_inputs:
                    distributed_img = img_pt.clone()
                    for mask in five_region_masks(img_pt):
                        outputs = wam.embed(img_pt, target_msg)
                        distributed_img = outputs["imgs_w"] * mask + distributed_img * (1 - mask)
                    psnr_watermarked = atk.psnr_tensor(unnormalize_img(distributed_img), unnormalize_img(img_pt))
                    for attack_name, attack_fn in attacks:
                        attacked = attack_fn(distributed_img)
                        pred_msg, full_acc, mask_pixels, fallback = decode_wam(wam, attacked, target_msg, msg_predict_inference)
                        decoded_payload = decoder(pred_msg)
                        payload_acc = float((decoded_payload == payload).float().mean().item())
                        row = {
                            "image": image_name,
                            "scheme": "five_region_spatial",
                            "scaling_w": f"{scale:.4f}",
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

    metrics_path = out_dir / "repetition_payload_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_path = summarize(rows, out_dir)
    print(f"metrics={metrics_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
