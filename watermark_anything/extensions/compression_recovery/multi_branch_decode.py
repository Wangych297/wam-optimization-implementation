import argparse
import csv
import io
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
    parser.add_argument("--seed", type=int, default=2468)
    parser.add_argument("--mask-ratio", type=float, default=0.5)
    return parser.parse_args()


def msg_to_str(msg: torch.Tensor) -> str:
    bits = msg.detach().cpu().int().view(-1).tolist()
    return "".join("1" if b else "0" for b in bits)


def tensor_to_pil(img_norm: torch.Tensor, unnormalize_img) -> Image.Image:
    img01 = unnormalize_img(img_norm.detach().cpu()).squeeze(0).clamp(0, 1)
    return TVF.to_pil_image(img01)


def pil_to_tensor(img: Image.Image, default_transform, device) -> torch.Tensor:
    return default_transform(img.convert("RGB")).unsqueeze(0).to(device)


def jpeg_pil(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=int(quality))
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def dct_basis(n: int = 8) -> np.ndarray:
    basis = np.zeros((n, n), dtype=np.float32)
    for k in range(n):
        alpha = np.sqrt(1.0 / n) if k == 0 else np.sqrt(2.0 / n)
        for i in range(n):
            basis[k, i] = alpha * np.cos(np.pi * (2 * i + 1) * k / (2 * n))
    return basis


DCT8 = dct_basis(8)


def jpeg_mask_like_pil(img: Image.Image, keep_sum: int) -> Image.Image:
    """JPEG-Mask-like branch: keep low-frequency 8x8 DCT coefficients."""
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w, c = arr.shape
    pad_h = (8 - h % 8) % 8
    pad_w = (8 - w % 8) % 8
    padded = np.pad(arr, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    out = np.zeros_like(padded)
    freq_mask = np.fromfunction(lambda u, v: (u + v) <= keep_sum, (8, 8), dtype=int).astype(np.float32)
    for y in range(0, padded.shape[0], 8):
        for x in range(0, padded.shape[1], 8):
            block = padded[y : y + 8, x : x + 8, :] - 128.0
            for ch in range(c):
                coeff = DCT8 @ block[:, :, ch] @ DCT8.T
                recon = DCT8.T @ (coeff * freq_mask) @ DCT8
                out[y : y + 8, x : x + 8, ch] = recon + 128.0
    out = np.clip(out[:h, :w, :], 0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


def apply_resize_then_jpeg(img_norm, scale, quality, default_transform, unnormalize_img, device):
    img = tensor_to_pil(img_norm, unnormalize_img)
    w, h = img.size
    small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BICUBIC)
    restored = small.resize((w, h), Image.BICUBIC)
    return pil_to_tensor(jpeg_pil(restored, quality), default_transform, device)


def decode_one(wam, img_norm, target_msg, msg_predict_inference):
    preds = wam.detect(img_norm)["preds"]
    mask_probs = torch.sigmoid(preds[:, 0:1, :, :])
    bit_logits = preds[:, 1:, :, :]
    mask_pixels = int((mask_probs > 0.5).sum().item())
    h, w = mask_probs.shape[-2:]
    if mask_pixels < 8:
        pred = torch.zeros_like(target_msg)
        return {
            "pred": pred,
            "bit_accuracy": 0.0,
            "confidence": 0.0,
            "mask_pixels": mask_pixels,
            "used_fallback": 1,
        }

    pred = msg_predict_inference(bit_logits, mask_probs, method="semihard").float()
    acc = float((pred == target_msg).float().mean().item())

    bit_probs = torch.sigmoid(bit_logits)
    bit_conf = (bit_probs - 0.5).abs() * 2.0
    weights = mask_probs * (mask_probs > 0.3).float()
    denom = weights.sum() * bit_conf.shape[1] + 1e-6
    weighted_conf = float((bit_conf * weights).sum().item() / denom.item())
    mask_fraction = mask_pixels / float(h * w)
    mask_factor = min(mask_fraction / 0.05, 1.0)
    confidence = weighted_conf * mask_factor

    return {
        "pred": pred,
        "bit_accuracy": acc,
        "confidence": confidence,
        "mask_pixels": mask_pixels,
        "used_fallback": 0,
    }


def hamming(a: torch.Tensor, b: torch.Tensor) -> int:
    return int((a.detach().cpu().int().view(-1) != b.detach().cpu().int().view(-1)).sum().item())


def choose_by_confidence(candidates):
    return max(candidates, key=lambda item: (item["confidence"], item["mask_pixels"]))


def choose_by_similarity(candidates, max_threshold=5):
    valid = [c for c in candidates if not c["used_fallback"]]
    if not valid:
        return choose_by_confidence(candidates)
    for threshold in range(max_threshold + 1):
        scored = []
        for cand in valid:
            neighbors = [other for other in valid if hamming(cand["pred"], other["pred"]) <= threshold]
            mean_conf = float(np.mean([n["confidence"] for n in neighbors]))
            scored.append((len(neighbors), mean_conf, cand["confidence"], cand))
        scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        if scored and scored[0][0] >= 2:
            return scored[0][3]
    return choose_by_confidence(valid)


def summarize(rows, path):
    groups = {}
    for row in rows:
        key = (row["attack"], row["method"])
        groups.setdefault(key, []).append(float(row["bit_accuracy"]))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["attack", "method", "mean_bit_accuracy", "min_bit_accuracy", "num_images"])
        writer.writeheader()
        for (attack, method), vals in groups.items():
            writer.writerow({
                "attack": attack,
                "method": method,
                "mean_bit_accuracy": f"{np.mean(vals):.6f}",
                "min_bit_accuracy": f"{np.min(vals):.6f}",
                "num_images": len(vals),
            })


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

    attacks = []
    attacks += [(f"jpeg_q{q}", lambda img_w, q=q: atk.apply_jpeg(img_w, q, default_transform, unnormalize_img, device)) for q in (95, 85, 75, 65, 50, 30, 20)]
    attacks += [(f"resize_{s}_jpeg_q50", lambda img_w, s=s: apply_resize_then_jpeg(img_w, s, 50, default_transform, unnormalize_img, device)) for s in (0.75, 0.5, 0.25)]
    attacks += [("jpeg_q50_then_q30", lambda img_w: atk.apply_jpeg(atk.apply_jpeg(img_w, 50, default_transform, unnormalize_img, device), 30, default_transform, unnormalize_img, device))]

    branch_specs = [
        ("identity", lambda pil: pil),
        ("real_jpeg_q90", lambda pil: jpeg_pil(pil, 90)),
        ("real_jpeg_q70", lambda pil: jpeg_pil(pil, 70)),
        ("real_jpeg_q50", lambda pil: jpeg_pil(pil, 50)),
        ("jpeg_mask_keep10", lambda pil: jpeg_mask_like_pil(pil, 10)),
        ("jpeg_mask_keep8", lambda pil: jpeg_mask_like_pil(pil, 8)),
        ("jpeg_mask_keep6", lambda pil: jpeg_mask_like_pil(pil, 6)),
        ("jpeg_mask_keep4", lambda pil: jpeg_mask_like_pil(pil, 4)),
    ]

    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={msg_to_str(target_msg)}", flush=True)

    branch_rows = []
    method_rows = []
    branch_fields = [
        "image",
        "attack",
        "branch",
        "message",
        "predicted",
        "bit_accuracy",
        "confidence",
        "mask_pixels",
        "used_fallback",
    ]
    method_fields = [
        "image",
        "attack",
        "method",
        "selected_branch",
        "message",
        "predicted",
        "bit_accuracy",
        "message_success",
        "selected_confidence",
        "psnr_vs_original",
    ]

    with torch.inference_mode():
        for image_path in image_paths:
            img = Image.open(image_path).convert("RGB")
            img_pt = default_transform(img).unsqueeze(0).to(device)
            outputs = wam.embed(img_pt, target_msg)
            mask = create_random_mask(img_pt, num_masks=1, mask_percentage=args.mask_ratio)
            img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

            for attack_name, attack_fn in attacks:
                attacked = attack_fn(img_w)
                attacked_pil = tensor_to_pil(attacked, unnormalize_img)
                candidates = []
                for branch_name, branch_fn in branch_specs:
                    branch_img = pil_to_tensor(branch_fn(attacked_pil), default_transform, device)
                    decoded = decode_one(wam, branch_img, target_msg, msg_predict_inference)
                    decoded["branch"] = branch_name
                    candidates.append(decoded)
                    branch_row = {
                        "image": image_path.name,
                        "attack": attack_name,
                        "branch": branch_name,
                        "message": msg_to_str(target_msg),
                        "predicted": msg_to_str(decoded["pred"]),
                        "bit_accuracy": f"{decoded['bit_accuracy']:.6f}",
                        "confidence": f"{decoded['confidence']:.6f}",
                        "mask_pixels": decoded["mask_pixels"],
                        "used_fallback": decoded["used_fallback"],
                    }
                    branch_rows.append(branch_row)

                identity = next(item for item in candidates if item["branch"] == "identity")
                confidence_best = choose_by_confidence(candidates)
                similarity_best = choose_by_similarity(candidates)
                oracle_best = max(candidates, key=lambda item: (item["bit_accuracy"], item["confidence"]))
                methods = [
                    ("baseline_identity", identity),
                    ("confidence_select", confidence_best),
                    ("similarity_select", similarity_best),
                    ("oracle_best_branch", oracle_best),
                ]
                psnr = atk.psnr_tensor(unnormalize_img(attacked), unnormalize_img(img_pt))
                for method_name, selected in methods:
                    row = {
                        "image": image_path.name,
                        "attack": attack_name,
                        "method": method_name,
                        "selected_branch": selected["branch"],
                        "message": msg_to_str(target_msg),
                        "predicted": msg_to_str(selected["pred"]),
                        "bit_accuracy": f"{selected['bit_accuracy']:.6f}",
                        "message_success": int(selected["bit_accuracy"] >= 0.999),
                        "selected_confidence": f"{selected['confidence']:.6f}",
                        "psnr_vs_original": f"{psnr:.4f}",
                    }
                    method_rows.append(row)
                    print(row, flush=True)

    branch_path = out_dir / "compression_recovery_candidates.csv"
    with branch_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=branch_fields)
        writer.writeheader()
        writer.writerows(branch_rows)

    method_path = out_dir / "compression_recovery_methods.csv"
    with method_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=method_fields)
        writer.writeheader()
        writer.writerows(method_rows)

    summary_path = out_dir / "compression_recovery_summary.csv"
    summarize(method_rows, summary_path)

    print(f"candidates={branch_path}", flush=True)
    print(f"methods={method_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
