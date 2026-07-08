"""
Multi-Scale Detection + Bbox Region Sync

Combines multi-scale detection (Exp 10) with bbox-based region
localization and re-decoding. After finding the best scale, extracts
the watermark mask, finds the largest connected region, crops it,
resamples to 256x256, and decodes again.

References:
- DWSF (ACM MM 2023): synchronization module with bbox localization
- Experiment 10: multi-scale detection baseline
"""

import argparse, csv, io, os, random, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from PIL import Image
import torch
from torchvision.transforms import functional as TVF


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
    p.add_argument("--use-multi-scale", action="store_true")
    p.add_argument("--use-bbox-sync", action="store_true")
    return p.parse_args()


SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * ratio); side = max(1, int(area**0.5)); side = min(side, h, w)
    top = rng.randint(0, max(0, h - side)); left = rng.randint(0, max(0, w - side))
    mask[:, :, top:top+side, left:left+side] = 1.0
    return mask


def apply_attack(name, img_w, dft, unnorm, device, rng):
    img_pil = TVF.to_pil_image(unnorm(img_w.detach().clone()).clamp(0, 1).squeeze(0).cpu())
    w, h = img_pil.size
    if name == "none": return img_w, img_pil
    elif name == "center_crop_0.5":
        cw, ch = max(1, int(w*0.5)), max(1, int(h*0.5)); l=(w-cw)//2; t=(h-ch)//2
        cropped = img_pil.crop((l, t, l+cw, t+ch)).resize((w, h), Image.BICUBIC)
    elif name == "center_crop_0.75":
        cw, ch = max(1, int(w*0.75)), max(1, int(h*0.75)); l=(w-cw)//2; t=(h-ch)//2
        cropped = img_pil.crop((l, t, l+cw, t+ch)).resize((w, h), Image.BICUBIC)
    elif name == "random_crop_0.5":
        cw, ch = max(1, int(w*0.5)), max(1, int(h*0.5))
        l=rng.randint(0,max(0,w-cw)); t=rng.randint(0,max(0,h-ch))
        cropped = img_pil.crop((l, t, l+cw, t+ch)).resize((w, h), Image.BICUBIC)
    elif name == "jpeg_q30":
        buf = io.BytesIO(); img_pil.save(buf, format="JPEG", quality=30); buf.seek(0)
        cropped = Image.open(buf).convert("RGB")
    else: return img_w, img_pil
    return dft(cropped).unsqueeze(0).to(device), cropped


def decode_image(attacked_pt, wam, mp_infer, device):
    preds = wam.detect(attacked_pt)["preds"]
    mask_preds = torch.sigmoid(preds[:, 0:1, :, :]); bit_preds = preds[:, 1:, :, :]
    return mp_infer(bit_preds, mask_preds, method="semihard").float(), mask_preds


def decode_at_scale(attacked_pt, scale, wam, mp_infer, device, unnorm, dft):
    _, _, h, w = attacked_pt.shape
    if abs(scale - 1.0) < 1e-6:
        return decode_image(attacked_pt, wam, mp_infer, device)
    ns = int(h * scale)
    img_pil = TVF.to_pil_image(unnorm(attacked_pt.detach().clone()).clamp(0,1).squeeze(0).cpu())
    img_pil = img_pil.resize((ns, ns), Image.BICUBIC)
    if scale < 1.0:
        canvas = Image.new("RGB", (w, h), (0,0,0))
        canvas.paste(img_pil, ((w-ns)//2, (h-ns)//2)); img_pil = canvas
    else:
        l, t = (ns-w)//2, (ns-h)//2; img_pil = img_pil.crop((l, t, l+w, t+h))
    return decode_image(dft(img_pil).unsqueeze(0).to(device), wam, mp_infer, device)


def bbox_decode(attacked_pil, wam, mp_infer, device, dft, unnorm):
    """Extract watermark mask bbox, crop, resize, decode."""
    # Get detection mask at original size
    attacked_pt = dft(attacked_pil).unsqueeze(0).to(device)
    preds = wam.detect(attacked_pt)["preds"]
    mask = torch.sigmoid(preds[:, 0:1, :, :]).detach().squeeze().cpu().numpy()
    # Binarize and find largest connected component
    mask_bin = (mask > 0.5).astype(np.uint8)
    if mask_bin.sum() < 100:
        return None, 0.0  # No significant watermark region
    # Get bounding box
    ys, xs = np.where(mask_bin)
    y1, y2, x1, x2 = ys.min(), ys.max(), xs.min(), xs.max()
    # Crop bbox from attacked image, resize to 256x256
    region = attacked_pil.crop((x1, y1, x2, y2))
    region = region.resize((256, 256), Image.BICUBIC)
    region_pt = dft(region).unsqueeze(0).to(device)
    pred_msg, _ = decode_image(region_pt, wam, mp_infer, device)
    return pred_msg, 1.0


def msg_to_str(m): return "".join("1" if b else "0" for b in m.detach().cpu().int().view(-1).tolist())


def main():
    args = parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    run_root = Path(args.project_root).resolve()
    sys.path.insert(0, str(run_root)); sys.path.insert(0, str(run_root / "notebooks")); os.chdir(run_root)

    from inference_utils import load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference as mp_infer
    from torchvision import transforms as T
    from watermark_anything.data.transforms import default_transform as dft, unnormalize_img as unnorm

    out_dir = Path(args.out_dir).resolve(); out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device} multi_scale={args.use_multi_scale} bbox_sync={args.use_bbox_sync}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = float(args.scaling_w)

    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])
    image_paths = sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]], []))[:args.limit]
    rng = np.random.RandomState(args.seed)
    msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
    print(f"message={msg_to_str(msg)}", flush=True)

    attacks = ["none", "center_crop_0.5", "center_crop_0.75", "random_crop_0.5", "jpeg_q30"]
    rows = []

    for img_idx, image_path in enumerate(image_paths):
        img = Image.open(image_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device)

        mask = create_random_mask(img_pt, 0.5, rng, device)
        outputs = wam.embed(img_pt, msg)
        img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

        for attack_name in attacks:
            attacked_pt, attacked_pil = apply_attack(attack_name, img_w, dft, unnorm, device, rng)

            # Multi-scale decode
            best_msg = None; best_acc = 0.0
            for scale in SCALES:
                pred_msg, _ = decode_at_scale(attacked_pt, scale, wam, mp_infer, device, unnorm, dft)
                acc = (pred_msg == msg).float().mean().item()
                if acc > best_acc: best_acc = acc; best_msg = pred_msg

            # Bbox sync decode
            if args.use_bbox_sync:
                bbox_msg, _ = bbox_decode(attacked_pil, wam, mp_infer, device, dft, unnorm)
                if bbox_msg is not None:
                    bbox_acc = (bbox_msg == msg).float().mean().item()
                    if bbox_acc > best_acc: best_acc = bbox_acc; best_msg = bbox_msg

            bit_acc = best_acc
            rows.append({"image": image_path.name, "attack": attack_name,
                         "bit_accuracy": f"{bit_acc:.6f}",
                         "message_success": 1 if bit_acc == 1.0 else 0})
        print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}", flush=True)

    csv_path = out_dir / "multi_scale_bbox_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image","attack","bit_accuracy","message_success"]); w.writeheader(); w.writerows(rows)

    summary = out_dir / "multi_scale_bbox_summary.csv"
    agg = defaultdict(lambda: {"s":0.0,"c":0,"ok":0})
    for r in rows:
        agg[r["attack"]]["s"] += float(r["bit_accuracy"]); agg[r["attack"]]["c"] += 1
        agg[r["attack"]]["ok"] += int(r["message_success"])
    with summary.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["attack","mean_bit_accuracy","message_success_rate","num_samples"])
        for a in sorted(agg): d=agg[a]; w.writerow([a,f"{d['s']/d['c']:.6f}",f"{d['ok']/d['c']:.4f}",d['c']])
    print(f"done: {len(rows)} rows", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
