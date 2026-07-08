"""
Saturation Weakness Diagnosis

Analyzes why saturation_1.5 attack causes bit accuracy degradation
(COCO 5000: mean 0.968 for single_center). Tests whether failures
are caused by image content or saturation threshold.

Finds images where saturation attack degrades accuracy vs clean,
then tests different saturation levels to find the drop-off point.
"""

import argparse, csv, io, os, random, sys
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
from PIL import Image
import torch
from torchvision.transforms import functional as TVF


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--params", required=True)
    p.add_argument("--image-dir", required=True, help="COCO 50 images dir")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--n-seeds", type=int, default=10)
    return p.parse_args()


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * ratio); side = max(1, int(area**0.5)); side = min(side, h, w)
    top = rng.randint(0, max(0, h - side)); left = rng.randint(0, max(0, w - side))
    mask[:, :, top:top+side, left:left+side] = 1.0
    return mask


def apply_saturation(img_pil, factor):
    return TVF.adjust_saturation(img_pil, factor)


def main():
    args = parse_args()
    random.seed(42); np.random.seed(42); torch.manual_seed(42)

    run_root = Path(args.project_root).resolve()
    sys.path.insert(0, str(run_root)); sys.path.insert(0, str(run_root / "notebooks")); os.chdir(run_root)

    from inference_utils import load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference as mp_infer
    from torchvision import transforms as T
    from watermark_anything.data.transforms import default_transform as dft, unnormalize_img as unnorm

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = Path(args.out_dir).resolve(); out_dir.mkdir(parents=True, exist_ok=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = 2.5
    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])

    image_paths = sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]], []))[:args.limit]
    print(f"Testing {len(image_paths)} images with {args.n_seeds} seeds each", flush=True)

    # Phase 1: Find saturation-sensitive images
    print("\nPhase 1: Finding saturation-sensitive images...", flush=True)
    sensitive = []

    for img_idx, image_path in enumerate(image_paths):
        img = Image.open(image_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device)
        img_pil = TVF.to_pil_image(unnorm(img_pt).clamp(0,1).squeeze(0).cpu())

        clean_ok = 0; sat_ok = 0
        for seed in range(args.n_seeds):
            rng = np.random.RandomState(seed)
            msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
            mask = create_random_mask(img_pt, 0.5, rng, device)

            # Embed
            outputs = wam.embed(img_pt, msg)
            img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

            # Clean detection
            preds = wam.detect(img_w)["preds"]
            mp = torch.sigmoid(preds[:,0:1,:,:]); bp = preds[:,1:,:,:]
            clean_acc = (mp_infer(bp, mp, method="semihard").float() == msg).float().mean().item()
            if clean_acc == 1.0: clean_ok += 1

            # Saturation attack
            wm_pil = TVF.to_pil_image(unnorm(img_w).clamp(0,1).squeeze(0).cpu())
            sat_pil = apply_saturation(wm_pil, 1.5)
            sat_pt = dft(sat_pil).unsqueeze(0).to(device)
            preds_s = wam.detect(sat_pt)["preds"]
            mps = torch.sigmoid(preds_s[:,0:1,:,:]); bps = preds_s[:,1:,:,:]
            sat_acc = (mp_infer(bps, mps, method="semihard").float() == msg).float().mean().item()
            if sat_acc == 1.0: sat_ok += 1

        drop = clean_ok - sat_ok
        if drop > 0:
            sensitive.append(image_path.name)
            print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}: clean_ok={clean_ok}/{args.n_seeds} sat_ok={sat_ok}/{args.n_seeds} drop={drop}", flush=True)
        else:
            print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}: ok", flush=True)

    print(f"\nFound {len(sensitive)}/{len(image_paths)} saturation-sensitive images", flush=True)

    # Phase 2: Saturation sweep on sensitive images
    if sensitive:
        print(f"\nPhase 2: Saturation sweep ({len(sensitive)} images) — testing gradual saturation levels...", flush=True)
        sat_levels = [1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0]
        sweep_results = []

        for img_idx, image_name in enumerate(sensitive):
            img_path = next((Path(args.image_dir) / image_name), None)
            if img_path is None or not img_path.exists():
                continue
            img = Image.open(img_path).convert("RGB")
            img_pt = it(img).unsqueeze(0).to(device)

            for seed in range(min(5, args.n_seeds)):
                rng = np.random.RandomState(seed)
                msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
                mask = create_random_mask(img_pt, 0.5, rng, device)
                outputs = wam.embed(img_pt, msg)
                img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)
                wm_pil = TVF.to_pil_image(unnorm(img_w).clamp(0,1).squeeze(0).cpu())

                for level in sat_levels:
                    sat_pil = apply_saturation(wm_pil, level)
                    sat_pt = dft(sat_pil).unsqueeze(0).to(device)
                    preds = wam.detect(sat_pt)["preds"]
                    mp_t = torch.sigmoid(preds[:,0:1,:,:]); bp_t = preds[:,1:,:,:]
                    sat_acc = (mp_infer(bp_t, mp_t, method="semihard").float() == msg).float().mean().item()
                    sweep_results.append({"image": image_name, "seed": seed, "sat_level": f"{level:.2f}", "bit_accuracy": f"{sat_acc:.6f}"})

            print(f"[{img_idx+1}/{len(sensitive)}] {image_name}: sweep done", flush=True)

        # Summary: mean accuracy at each saturation level
        agg = defaultdict(lambda: {"s":0.0,"c":0})
        for r in sweep_results:
            agg[r["sat_level"]]["s"] += float(r["bit_accuracy"])
            agg[r["sat_level"]]["c"] += 1

        summary_path = out_dir / "saturation_diagnosis_summary.csv"
        with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["sat_level","mean_accuracy","n_samples"])
            for level in sorted(agg.keys(), key=float):
                d=agg[level]; w.writerow([level, f"{d['s']/d['c']:.6f}", d['c']])
        print(f"\nSummary saved to {summary_path}", flush=True)

        # Detail
        detail_path = out_dir / "saturation_diagnosis_detail.csv"
        with detail_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, ["image","seed","sat_level","bit_accuracy"])
            w.writeheader(); w.writerows(sweep_results)

        # Conclusion
        first = float(sorted(agg.keys(), key=float)[0]); last = float(sorted(agg.keys(), key=float)[-1])
        first_acc = agg[f"{first:.2f}"]["s"]/agg[f"{first:.2f}"]["c"]
        last_acc = agg[f"{last:.2f}"]["s"]/agg[f"{last:.2f}"]["c"]
        print(f"\nSaturation {first}→{last}: accuracy {first_acc:.4f}→{last_acc:.4f}", flush=True)
        print(f"Sensitive images: {len(sensitive)}/{args.limit} ({100*len(sensitive)/args.limit:.0f}%)", flush=True)

    # Phase 3: Color histogram analysis on sensitive vs insensitive
    if sensitive:
        print(f"\nPhase 3: Color histogram analysis...", flush=True)
        insensitive = [p.name for p in image_paths if p.name not in set(sensitive)]
        for label, group in [("sensitive", sensitive[:5]), ("insensitive", insensitive[:5])]:
            mean_sats = []
            for name in group:
                img = Image.open(Path(args.image_dir) / name).convert("RGB")
                arr = np.array(img, dtype=np.float32) / 255.0
                hsv = Image.fromarray((arr*255).astype(np.uint8)).convert("HSV")
                s_channel = np.array(hsv.split()[1], dtype=np.float32) / 255.0
                mean_sats.append(s_channel.mean())
            print(f"  {label} (n={len(mean_sats)}): mean saturation = {np.mean(mean_sats):.3f}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
