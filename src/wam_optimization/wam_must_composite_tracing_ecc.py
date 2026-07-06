import argparse
import csv
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

import torch


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wam-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed", type=int, default=240725)
    parser.add_argument("--material-size", type=int, default=256)
    parser.add_argument("--canvas-size", type=int, default=512)
    return parser.parse_args()


def bits_to_str(bits):
    return "".join("1" if int(b) else "0" for b in bits)


def msg_to_str(msg):
    return bits_to_str(msg.detach().cpu().int().view(-1).tolist())


def encode_rep4_adjacent(payload):
    return payload.repeat_interleave(4, dim=1).float()


def decode_rep4_adjacent(pred_message):
    bits = pred_message.detach().cpu().int().view(8, 4)
    decoded = (bits.sum(dim=1) >= 2).int()
    return decoded


def encode_rep4_interleaved(payload):
    return payload.repeat(1, 4).float()


def decode_rep4_interleaved(pred_message):
    bits = pred_message.detach().cpu().int().view(4, 8)
    decoded = (bits.sum(dim=0) >= 2).int()
    return decoded


def code_definitions():
    return [
        ("rep4_adjacent_8bit", encode_rep4_adjacent, decode_rep4_adjacent),
        ("rep4_interleaved_8bit", encode_rep4_interleaved, decode_rep4_interleaved),
    ]


def payload_accuracy(decoded_payload, target_payload):
    target = target_payload.detach().cpu().int().view(-1)
    return float((decoded_payload == target).float().mean().item())


def write_summaries(rows, out_dir):
    summary_groups = {}
    for row in rows:
        key = (row["code_mode"], row["scheme"], row["scenario"], row["attack"], row["decode_method"])
        summary_groups.setdefault(key, []).append(row)

    summary_path = out_dir / "wam_must_composite_tracing_ecc_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "code_mode",
                "scenario",
                "attack",
                "decode_method",
                "mean_bit_accuracy",
                "mean_payload_accuracy",
                "payload_success_rate",
                "mean_composite_psnr",
                "num_source_rows",
            ],
        )
        writer.writeheader()
        for (code_mode, scheme, scenario, attack, method), vals in sorted(summary_groups.items()):
            writer.writerow({
                "scheme": scheme,
                "code_mode": code_mode,
                "scenario": scenario,
                "attack": attack,
                "decode_method": method,
                "mean_bit_accuracy": f"{np.mean([float(v['bit_accuracy']) for v in vals]):.6f}",
                "mean_payload_accuracy": f"{np.mean([float(v['payload_accuracy']) for v in vals]):.6f}",
                "payload_success_rate": f"{np.mean([int(v['payload_success']) for v in vals]):.6f}",
                "mean_composite_psnr": f"{np.mean([float(v['composite_psnr']) for v in vals]):.4f}",
                "num_source_rows": len(vals),
            })

    overview_groups = {}
    for row in rows:
        key = (row["code_mode"], row["scheme"], row["decode_method"])
        overview_groups.setdefault(key, []).append(row)

    overview_path = out_dir / "wam_must_composite_tracing_ecc_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scheme",
                "code_mode",
                "decode_method",
                "mean_bit_accuracy",
                "mean_payload_accuracy",
                "payload_success_rate",
                "mean_composite_psnr",
            ],
        )
        writer.writeheader()
        for (code_mode, scheme, method), vals in sorted(overview_groups.items()):
            writer.writerow({
                "scheme": scheme,
                "code_mode": code_mode,
                "decode_method": method,
                "mean_bit_accuracy": f"{np.mean([float(v['bit_accuracy']) for v in vals]):.6f}",
                "mean_payload_accuracy": f"{np.mean([float(v['payload_accuracy']) for v in vals]):.6f}",
                "payload_success_rate": f"{np.mean([int(v['payload_success']) for v in vals]):.6f}",
                "mean_composite_psnr": f"{np.mean([float(v['composite_psnr']) for v in vals]):.4f}",
            })
    return summary_path, overview_path


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    task_script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(task_script_dir))
    import wam_dwsf_area_sweep as area
    import wam_must_composite_tracing as base

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
    image_paths = sorted(image_paths)
    if len(image_paths) < 4:
        raise RuntimeError(f"Need at least four images under {args.image_dir}")

    background_path = next((p for p in image_paths if "seabackground" in p.name.lower()), image_paths[-1])
    source_paths = [p for p in image_paths if p != background_path][:3]
    if len(source_paths) < 3:
        raise RuntimeError("Need at least three source material images.")

    background = ImageOps.fit(Image.open(background_path).convert("RGB"), (args.canvas_size, args.canvas_size), method=base.RESAMPLE)
    clean_materials = [
        ImageOps.fit(Image.open(p).convert("RGB"), (args.material_size, args.material_size), method=base.RESAMPLE)
        for p in source_paths
    ]

    payloads = [torch.randint(0, 2, (1, 8), device=device).float() for _ in source_paths]
    print(f"background={background_path.name}", flush=True)
    print(f"sources={[p.name for p in source_paths]}", flush=True)
    for idx, payload in enumerate(payloads):
        print(f"source_{idx}_payload={bits_to_str(payload.detach().cpu().int().view(-1).tolist())}", flush=True)

    rows = []
    fieldnames = [
        "code_mode",
        "scheme",
        "scenario",
        "attack",
        "decode_method",
        "source_idx",
        "source_image",
        "target_payload",
        "decoded_payload",
        "target_message",
        "predicted_message",
        "bit_accuracy",
        "payload_accuracy",
        "payload_success",
        "mask_pixels",
        "used_fallback",
        "composite_psnr",
        "box",
    ]

    try:
        with torch.inference_mode():
            for code_mode, encode_fn, decode_fn in code_definitions():
                messages = [encode_fn(payload) for payload in payloads]
                for idx, msg in enumerate(messages):
                    print(f"{code_mode}_source_{idx}_message={msg_to_str(msg)}", flush=True)
                for mode in base.mode_definitions():
                    wam.scaling_w = float(mode["scaling_w"])
                    watermarked_materials = []
                    for material, msg in zip(clean_materials, messages):
                        img_pt = area.pil_to_tensor(material, default_transform, device)
                        embedded = wam.embed(img_pt, msg)["imgs_w"]
                        img_w = base.build_mode_image(mode, img_pt, embedded, area)
                        watermarked_materials.append(area.tensor_to_pil(img_w, unnormalize_img))

                    for scenario in base.scenario_definitions(args.canvas_size):
                        clean_composite, boxes = base.compose_scene(background, clean_materials, scenario)
                        wm_composite, boxes = base.compose_scene(background, watermarked_materials, scenario)
                        composite_psnr = base.psnr_pil(wm_composite, clean_composite)

                        for attack_name, attacked in base.apply_composite_attacks(wm_composite):
                            global_preds = {}
                            for source_idx, msg in enumerate(messages):
                                pred, acc, mask_pixels, fallback = base.decode_image(
                                    wam, attacked, msg, area, default_transform, device, msg_predict_inference
                                )
                                global_preds[source_idx] = (pred, acc, mask_pixels, fallback)

                            for source_info in boxes:
                                source_idx = int(source_info["source_idx"])
                                target_msg = messages[source_idx]
                                target_payload = payloads[source_idx]
                                source_name = source_paths[source_idx].name
                                box = source_info["box"]
                                crop = attacked.crop(box)
                                decoded_items = [
                                    ("global_full_canvas", attacked, global_preds[source_idx]),
                                    ("oracle_box_raw", crop, None),
                                    ("must_mer_resize", crop.resize((args.material_size, args.material_size), base.RESAMPLE), None),
                                ]
                                for method, decode_img, cached in decoded_items:
                                    if cached is None:
                                        pred, bit_acc, mask_pixels, fallback = base.decode_image(
                                            wam, decode_img, target_msg, area, default_transform, device, msg_predict_inference
                                        )
                                    else:
                                        pred, bit_acc, mask_pixels, fallback = cached
                                    decoded_payload = decode_fn(pred)
                                    pay_acc = payload_accuracy(decoded_payload, target_payload)
                                    row = {
                                        "code_mode": code_mode,
                                        "scheme": mode["scheme"],
                                        "scenario": scenario["scenario"],
                                        "attack": attack_name,
                                        "decode_method": method,
                                        "source_idx": source_idx,
                                        "source_image": source_name,
                                        "target_payload": bits_to_str(target_payload.detach().cpu().int().view(-1).tolist()),
                                        "decoded_payload": bits_to_str(decoded_payload.tolist()),
                                        "target_message": msg_to_str(target_msg),
                                        "predicted_message": msg_to_str(pred),
                                        "bit_accuracy": f"{bit_acc:.6f}",
                                        "payload_accuracy": f"{pay_acc:.6f}",
                                        "payload_success": int(pay_acc >= 0.999),
                                        "mask_pixels": mask_pixels,
                                        "used_fallback": fallback,
                                        "composite_psnr": f"{composite_psnr:.4f}",
                                        "box": f"{box[0]},{box[1]},{box[2]},{box[3]}",
                                    }
                                    rows.append(row)
                                    print(row, flush=True)
    finally:
        wam.scaling_w = original_scaling_w

    metrics_path = out_dir / "wam_must_composite_tracing_ecc_metrics.csv"
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
