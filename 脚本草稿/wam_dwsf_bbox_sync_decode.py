import argparse
import csv
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

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
    parser.add_argument("--seed", type=int, default=9753)
    parser.add_argument("--scales", nargs="+", type=float, default=[2.5, 3.0])
    parser.add_argument("--max-boxes", type=int, default=4)
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


def dwsf_five_region_masks(img_pt):
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


def decode_one(wam, img_norm, target_msg, msg_predict_inference):
    preds = wam.detect(img_norm)["preds"]
    mask_probs = torch.sigmoid(preds[:, 0:1, :, :])
    bit_logits = preds[:, 1:, :, :]
    mask_pixels = int((mask_probs > 0.5).sum().item())
    if mask_pixels < 8:
        pred = torch.zeros_like(target_msg)
        return {
            "pred": pred,
            "bit_accuracy": 0.0,
            "confidence": 0.0,
            "mask_pixels": mask_pixels,
            "used_fallback": 1,
            "mask_probs": mask_probs,
        }
    pred = msg_predict_inference(bit_logits, mask_probs, method="semihard").float()
    acc = float((pred == target_msg).float().mean().item())
    bit_probs = torch.sigmoid(bit_logits)
    bit_conf = (bit_probs - 0.5).abs() * 2.0
    weights = mask_probs * (mask_probs > 0.3).float()
    denom = weights.sum() * bit_conf.shape[1] + 1e-6
    weighted_conf = float((bit_conf * weights).sum().item() / denom.item())
    h, w = mask_probs.shape[-2:]
    mask_factor = min(mask_pixels / float(h * w) / 0.05, 1.0)
    return {
        "pred": pred,
        "bit_accuracy": acc,
        "confidence": weighted_conf * mask_factor,
        "mask_pixels": mask_pixels,
        "used_fallback": 0,
        "mask_probs": mask_probs,
    }


def component_boxes(mask_probs, max_boxes=4):
    mask_np = mask_probs.detach().cpu().squeeze().numpy()
    boxes = []
    for threshold in (0.5, 0.35, 0.2):
        binary = mask_np > threshold
        labels, num = ndi.label(binary)
        found = []
        for label in range(1, num + 1):
            ys, xs = np.where(labels == label)
            area = len(xs)
            if area < 200:
                continue
            found.append((area, int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1, threshold))
        if found:
            boxes = sorted(found, reverse=True)[:max_boxes]
            all_ys, all_xs = np.where(binary)
            if len(all_xs) >= 200:
                boxes.insert(0, (len(all_xs), int(all_xs.min()), int(all_ys.min()), int(all_xs.max()) + 1, int(all_ys.max()) + 1, threshold))
            break
    return boxes


def crop_box_to_full(img_norm, box, default_transform, unnormalize_img, device, margin=0.25):
    _, _, img_h, img_w = img_norm.shape
    area, x0, y0, x1, y1, threshold = box
    det_w = det_h = 256.0
    sx = img_w / det_w
    sy = img_h / det_h
    bx0, by0, bx1, by1 = x0 * sx, y0 * sy, x1 * sx, y1 * sy
    bw, bh = bx1 - bx0, by1 - by0
    bx0 -= bw * margin
    bx1 += bw * margin
    by0 -= bh * margin
    by1 += bh * margin
    bx0 = max(0, min(img_w - 1, int(round(bx0))))
    by0 = max(0, min(img_h - 1, int(round(by0))))
    bx1 = max(bx0 + 1, min(img_w, int(round(bx1))))
    by1 = max(by0 + 1, min(img_h, int(round(by1))))
    img = tensor_to_pil(img_norm, unnormalize_img)
    cropped = img.crop((bx0, by0, bx1, by1)).resize((img_w, img_h), Image.BICUBIC)
    return pil_to_tensor(cropped, default_transform, device), (bx0, by0, bx1, by1, threshold, area)


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


def summarize(rows, out_dir):
    groups = {}
    for row in rows:
        key = (row["scheme"], row["scaling_w"], row["attack"], row["method"])
        groups.setdefault(key, []).append(float(row["bit_accuracy"]))
    summary_path = out_dir / "wam_dwsf_bbox_sync_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["scheme", "scaling_w", "attack", "method", "mean_bit_accuracy", "min_bit_accuracy", "num_images"])
        writer.writeheader()
        for (scheme, scale, attack, method), vals in sorted(groups.items(), key=lambda item: (item[0][0], float(item[0][1]), item[0][2], item[0][3])):
            writer.writerow({
                "scheme": scheme,
                "scaling_w": scale,
                "attack": attack,
                "method": method,
                "mean_bit_accuracy": f"{np.mean(vals):.6f}",
                "min_bit_accuracy": f"{np.min(vals):.6f}",
                "num_images": len(vals),
            })
    return summary_path


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

    image_paths = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(Path(args.image_dir).glob(suffix))
    image_paths = sorted(image_paths)[: args.limit]

    target_msg = torch.randint(0, 2, (1, 32), device=device).float()
    print(f"message={msg_to_str(target_msg)}", flush=True)

    attacks = [
        ("crop_top_left_50", lambda img_w: crop_region(img_w, 0.0, 0.0, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_bottom_right_50", lambda img_w: crop_region(img_w, 0.5, 0.5, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("crop_center_50", lambda img_w: crop_region(img_w, 0.25, 0.25, 0.5, 0.5, default_transform, unnormalize_img, device)),
        ("jpeg_q20", lambda img_w: atk.apply_jpeg(img_w, 20, default_transform, unnormalize_img, device)),
        ("resize_0.25_jpeg_q50", lambda img_w: resize_then_jpeg(img_w, 0.25, 50, atk, default_transform, unnormalize_img, device)),
    ]

    method_rows = []
    candidate_rows = []
    method_fields = [
        "image",
        "scheme",
        "scaling_w",
        "attack",
        "method",
        "selected_candidate",
        "message",
        "predicted",
        "bit_accuracy",
        "message_success",
        "confidence",
        "mask_pixels",
    ]
    candidate_fields = [
        "image",
        "scheme",
        "scaling_w",
        "attack",
        "candidate",
        "box",
        "message",
        "predicted",
        "bit_accuracy",
        "confidence",
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
                base_img = base_outputs["imgs_w"] * baseline_center_mask(img_pt) + img_pt * (1 - baseline_center_mask(img_pt))

                dwsf_img = img_pt.clone()
                for mask in dwsf_five_region_masks(img_pt):
                    outputs = wam.embed(img_pt, target_msg)
                    dwsf_img = outputs["imgs_w"] * mask + dwsf_img * (1 - mask)

                for scheme, img_w in (("single_center_50pct", base_img), ("dwsf_5region_spatial", dwsf_img)):
                    for attack_name, attack_fn in attacks:
                        attacked = attack_fn(img_w)
                        global_decoded = decode_one(wam, attacked, target_msg, msg_predict_inference)
                        global_decoded["candidate"] = "global"
                        global_decoded["box"] = "full"
                        candidates = [global_decoded]

                        boxes = component_boxes(global_decoded["mask_probs"], max_boxes=args.max_boxes)
                        for idx, box in enumerate(boxes):
                            crop_tensor, crop_info = crop_box_to_full(attacked, box, default_transform, unnormalize_img, device)
                            decoded = decode_one(wam, crop_tensor, target_msg, msg_predict_inference)
                            decoded["candidate"] = f"bbox_{idx}"
                            decoded["box"] = ",".join(str(x) for x in crop_info)
                            candidates.append(decoded)

                        for cand in candidates:
                            candidate_rows.append({
                                "image": image_name,
                                "scheme": scheme,
                                "scaling_w": f"{scale:.4f}",
                                "attack": attack_name,
                                "candidate": cand["candidate"],
                                "box": cand["box"],
                                "message": msg_to_str(target_msg),
                                "predicted": msg_to_str(cand["pred"]),
                                "bit_accuracy": f"{cand['bit_accuracy']:.6f}",
                                "confidence": f"{cand['confidence']:.6f}",
                                "mask_pixels": cand["mask_pixels"],
                                "used_fallback": cand["used_fallback"],
                            })

                        selected = {
                            "global_decode": global_decoded,
                            "bbox_confidence_select": choose_by_confidence(candidates),
                            "bbox_similarity_select": choose_by_similarity(candidates),
                            "oracle_best_candidate": max(candidates, key=lambda item: (item["bit_accuracy"], item["confidence"])),
                        }
                        for method_name, cand in selected.items():
                            row = {
                                "image": image_name,
                                "scheme": scheme,
                                "scaling_w": f"{scale:.4f}",
                                "attack": attack_name,
                                "method": method_name,
                                "selected_candidate": cand["candidate"],
                                "message": msg_to_str(target_msg),
                                "predicted": msg_to_str(cand["pred"]),
                                "bit_accuracy": f"{cand['bit_accuracy']:.6f}",
                                "message_success": int(cand["bit_accuracy"] >= 0.999),
                                "confidence": f"{cand['confidence']:.6f}",
                                "mask_pixels": cand["mask_pixels"],
                            }
                            method_rows.append(row)
                            print(row, flush=True)

    wam.scaling_w = original_scaling_w

    candidates_path = out_dir / "wam_dwsf_bbox_sync_candidates.csv"
    with candidates_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=candidate_fields)
        writer.writeheader()
        writer.writerows(candidate_rows)

    methods_path = out_dir / "wam_dwsf_bbox_sync_methods.csv"
    with methods_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=method_fields)
        writer.writeheader()
        writer.writerows(method_rows)

    summary_path = summarize(method_rows, out_dir)
    print(f"candidates={candidates_path}", flush=True)
    print(f"methods={methods_path}", flush=True)
    print(f"summary={summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
