"""
Mixed Precision (FP16) Benchmark

Runs FP32 vs FP16 comparison on COCO 50:
- Model size (FP32 vs FP16)
- Inference speed
- Bit accuracy impact

FP16 is natively supported on CUDA GPUs and typically gives ~2x speedup
with minimal accuracy loss for transformer models.

Reference: Micikevicius et al., "Mixed Precision Training", ICLR 2018
"""

import argparse, csv, os, random, sys, time
from pathlib import Path
from collections import defaultdict
import numpy as np
from PIL import Image
import torch


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--params", required=True)
    p.add_argument("--image-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--scaling-w", type=float, default=2.5)
    return p.parse_args()


def get_model_size_mb(model):
    total = 0
    for p in model.parameters():
        total += p.numel() * p.element_size()
    return total / 1024 / 1024


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * ratio); side = max(1, int(area**0.5)); side = min(side, h, w)
    top = rng.randint(0, max(0, h - side)); left = rng.randint(0, max(0, w - side))
    mask[:, :, top:top+side, left:left+side] = 1.0
    return mask


def msg_to_str(m): return "".join("1" if b else "0" for b in m.detach().cpu().int().view(-1).tolist())


def main():
    args = parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    run_root = Path(args.project_root).resolve()
    sys.path.insert(0, str(run_root)); sys.path.insert(0, str(run_root/"notebooks")); os.chdir(run_root)

    from inference_utils import load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference as mp_infer
    from torchvision import transforms as T
    from watermark_anything.data.transforms import default_transform as dft, unnormalize_img as unnorm

    out_dir = Path(args.out_dir).resolve(); out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda")

    # FP32 baseline
    print("Loading FP32 model...", flush=True)
    wam_fp32 = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam_fp32.scaling_w = float(args.scaling_w)
    fp32_size = get_model_size_mb(wam_fp32)

    # FP16 model
    print("Converting to FP16...", flush=True)
    wam_fp16 = load_model_from_checkpoint(args.params, args.checkpoint).to("cpu").eval()
    wam_fp16.scaling_w = float(args.scaling_w)
    wam_fp16 = wam_fp16.half().to(device).eval()
    fp16_size = get_model_size_mb(wam_fp16)
    print(f"FP32: {fp32_size:.0f}MB → FP16: {fp16_size:.0f}MB ({100*(1-fp16_size/fp32_size):.0f}% reduction)", flush=True)

    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])
    image_paths = sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]], []))[:args.limit]
    rng = np.random.RandomState(args.seed)
    msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)

    rows = []
    # Warmup both
    dummy = torch.randn(1, 3, 256, 256, device=device)
    _ = wam_fp32.detect(dummy)
    _ = wam_fp16.detect(dummy.half())

    for img_idx, image_path in enumerate(image_paths):
        img = Image.open(image_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device)

        mask = create_random_mask(img_pt, 0.5, rng, device)
        outputs = wam_fp32.embed(img_pt, msg)
        img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

        for model, tag, dtype_t in [(wam_fp32, "fp32", torch.float32), (wam_fp16, "fp16", torch.float16)]:
            # Convert input to correct dtype
            inp = img_w.to(dtype_t)

            # Warmup
            for _ in range(10): _ = model.detect(inp)
            torch.cuda.synchronize()
            # Timed
            t0 = time.time()
            N = 50
            for _ in range(N): _ = model.detect(inp)
            torch.cuda.synchronize()
            avg_ms = (time.time() - t0) / N * 1000

            # Accuracy (detect in fp16, decode in fp32 for stability)
            preds = model.detect(inp)
            mp_t = torch.sigmoid(preds["preds"][:, 0:1, :, :].float())
            bp_t = preds["preds"][:, 1:, :, :].float()
            pred_msg = mp_infer(bp_t, mp_t, method="semihard").float()
            bit_acc = (pred_msg == msg).float().mean().item()

            rows.append({"image": image_path.name, "model": tag,
                         "bit_accuracy": f"{bit_acc:.6f}",
                         "message_success": 1 if bit_acc == 1.0 else 0,
                         "infer_ms": f"{avg_ms:.1f}"})
        print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}", flush=True)

    # Summary
    csv_path = out_dir / "quantization_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image","model","bit_accuracy","message_success","infer_ms"])
        w.writeheader(); w.writerows(rows)

    summary = out_dir / "quantization_summary.csv"
    agg = defaultdict(lambda: {"acc":0.0, "c":0, "ok":0, "ms":0.0})
    for r in rows:
        agg[r["model"]]["acc"] += float(r["bit_accuracy"]); agg[r["model"]]["c"] += 1
        agg[r["model"]]["ok"] += int(r["message_success"]); agg[r["model"]]["ms"] += float(r["infer_ms"])
    with summary.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["model","mean_bit_accuracy","message_success_rate","avg_infer_ms","model_size_mb","num_samples"])
        for m in ["fp32", "fp16"]:
            d = agg[m]; sz = fp32_size if m=="fp32" else fp16_size
            w.writerow([m, f"{d['acc']/d['c']:.6f}", f"{d['ok']/d['c']:.4f}", f"{d['ms']/d['c']:.1f}", f"{sz:.0f}", d['c']])
    print(f"\n=== RESULTS ===", flush=True)
    print(f"FP32: acc={agg['fp32']['acc']/agg['fp32']['c']:.4f}, {agg['fp32']['ms']/agg['fp32']['c']:.1f}ms, {fp32_size:.0f}MB", flush=True)
    print(f"FP16: acc={agg['fp16']['acc']/agg['fp16']['c']:.4f}, {agg['fp16']['ms']/agg['fp16']['c']:.1f}ms, {fp16_size:.0f}MB", flush=True)
    print(f"Speedup: {agg['fp32']['ms']/agg['fp16']['ms']:.2f}x", flush=True)
    print(f"Size:    {fp16_size:.0f}/{fp32_size:.0f}MB ({100-100*fp16_size/fp32_size:.0f}% reduction)", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
