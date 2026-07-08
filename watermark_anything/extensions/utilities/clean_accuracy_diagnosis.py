"""
Clean Accuracy Diagnosis

Analyzes why 8-14% of images fail to achieve 100% bit accuracy
even without any attack (attack=none). Tests whether failures are
caused by image content (inherently hard) or mask randomness
(solvable by retrying with a different mask).

Usage:
  python clean_accuracy_diagnosis.py \
    --metrics results_output/coco5000_multi_scale/control/multi_scale_metrics.csv \
    --image-dir assets/images_coco5000 \
    --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
    --out-dir results_output/clean_diagnosis \
    --n-seeds 10
"""

import argparse, csv, os, random, sys
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
import torch
from PIL import Image


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", default=str(Path(__file__).resolve().parents[3]))
    p.add_argument("--metrics", required=True, help="COCO 5000 control metrics CSV")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--params", required=True)
    p.add_argument("--image-dir", required=True, help="Root of COCO image chunks")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--n-seeds", type=int, default=10, help="Number of random seeds to test per failed image")
    p.add_argument("--limit-failed", type=int, default=0, help="Max failed images to test (0=all)")
    return p.parse_args()


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * ratio)
    side = max(1, int(area ** 0.5))
    side = min(side, h, w)
    top = rng.randint(0, max(0, h - side))
    left = rng.randint(0, max(0, w - side))
    mask[:, :, top:top + side, left:left + side] = 1.0
    return mask


def find_file(image_name, image_root):
    """Search for image in chunk subdirectories."""
    for chunk_dir in sorted(Path(image_root).glob("chunk_*")):
        p = chunk_dir / image_name
        if p.exists():
            return p
    return None


def main():
    args = parse_args()
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    run_root = Path(args.project_root).resolve()
    sys.path.insert(0, str(run_root))
    sys.path.insert(0, str(run_root / "notebooks"))
    os.chdir(run_root)

    from inference_utils import load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference as mp_infer
    from torchvision import transforms as T
    from watermark_anything.data.transforms import default_transform as dft, unnormalize_img as unnorm

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Find failed images
    print("Step 1: Finding failed images...", flush=True)
    failed_images = set()
    with open(args.metrics, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["method"] == "single_scale" and row["attack"] == "none":
                acc = float(row["bit_accuracy"])
                if acc < 1.0:
                    failed_images.add(row["image"])

    failed_list = sorted(failed_images)
    n_failed = len(failed_list)
    total = len(set(1 for _ in csv.DictReader(open(args.metrics, newline="", encoding="utf-8-sig"))
                    if _.get("method") == "single_scale" and _.get("attack") == "none"))
    # Actually, let's count properly
    with open(args.metrics, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    total_images = len(set(r["image"] for r in rows if r["method"] == "single_scale" and r["attack"] == "none"))
    print(f"Failed: {n_failed}/{total_images} ({100*n_failed/total_images:.1f}%)", flush=True)

    if args.limit_failed > 0:
        failed_list = failed_list[:args.limit_failed]
        print(f"Limited to {len(failed_list)} images for testing", flush=True)

    # Step 2: Multi-seed test on failed images
    print(f"\nStep 2: Testing each failed image with {args.n_seeds} random seeds...", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = 2.5
    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])

    results = []  # (image, seed, bit_accuracy, bit_errors_detail)
    seed_recovery = Counter()  # seed -> number of images it fixes
    image_fixable = Counter()  # image -> number of seeds it passes

    for img_idx, image_name in enumerate(failed_list):
        img_path = find_file(image_name, args.image_dir)
        if img_path is None:
            print(f"  WARNING: {image_name} not found, skipping", flush=True)
            continue

        img = Image.open(img_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device)

        passed_seeds = 0
        for seed in range(args.n_seeds):
            rng = np.random.RandomState(seed)
            msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
            mask = create_random_mask(img_pt, 0.5, rng, device)
            outputs = wam.embed(img_pt, msg)
            img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

            preds = wam.detect(img_w)["preds"]
            mask_preds = torch.sigmoid(preds[:, 0:1, :, :])
            bit_preds = preds[:, 1:, :, :]
            pred_msg = mp_infer(bit_preds, mask_preds, method="semihard").float()
            bit_acc = (pred_msg == msg).float().mean().item()

            results.append({"image": image_name, "seed": seed, "bit_accuracy": f"{bit_acc:.6f}"})
            if bit_acc == 1.0:
                passed_seeds += 1
                seed_recovery[seed] += 1

        image_fixable[image_name] = passed_seeds
        print(f"[{img_idx+1}/{len(failed_list)}] {image_name}: {passed_seeds}/{args.n_seeds} seeds pass", flush=True)

    # Step 3: Summary
    print(f"\n===== DIAGNOSIS SUMMARY =====", flush=True)
    fully_fixable = sum(1 for c in image_fixable.values() if c > 0)
    always_fixable = sum(1 for c in image_fixable.values() if c == args.n_seeds)
    never_fixable = sum(1 for c in image_fixable.values() if c == 0)

    print(f"Tested {len(failed_list)} failed images with {args.n_seeds} seeds each", flush=True)
    print(f"  Fixable by retry (≥1 seed pass): {fully_fixable}/{len(failed_list)} ({100*fully_fixable/max(1,len(failed_list)):.1f}%)", flush=True)
    print(f"  Always fixable (all seeds pass): {always_fixable}", flush=True)
    print(f"  Never fixable (0 seeds pass):   {never_fixable}", flush=True)
    print(f"  Avg pass rate per image: {sum(image_fixable.values())/max(1,len(image_fixable)):.1f}/{args.n_seeds}", flush=True)

    # Per-image detail
    detail_path = out_dir / "clean_diagnosis_detail.csv"
    with detail_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image", "seed", "bit_accuracy"])
        w.writeheader()
        w.writerows(results)
    print(f"\nDetail: {detail_path}", flush=True)

    # Summary CSV
    summary_path = out_dir / "clean_diagnosis_summary.csv"
    summary_rows = [{"image": img, "pass_rate": f"{image_fixable[img]}/{args.n_seeds}"}
                    for img in sorted(image_fixable.keys(), key=lambda x: image_fixable[x])]
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image", "pass_rate"])
        w.writeheader()
        w.writerows(summary_rows)
    print(f"Summary: {summary_path}", flush=True)

    # Conclusion
    if never_fixable == 0 and always_fixable > 0.5 * len(failed_list):
        print("\nCONCLUSION: Failures are primarily due to mask randomness. Retrying with different seeds/masks can recover most images.", flush=True)
    elif never_fixable > 0.5 * len(failed_list):
        print("\nCONCLUSION: Failures are primarily due to image content. These images are inherently hard for WAM.", flush=True)
    else:
        print("\nCONCLUSION: Mixed causes. Some images are mask-dependent, some are inherently hard.", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
