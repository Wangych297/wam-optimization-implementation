"""
Preprocessing Recovery for random_crop

Tests whether image preprocessing (sharpen, denoise, contrast enhance)
before detection can recover additional watermark bits from cropped images.

References:
- Image enhancement for degraded image restoration (classic CV)
- Multi-pass inference with preprocessing variants
"""

import argparse, csv, io, os, random, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
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
    p.add_argument("--use-preprocess", action="store_true",
                   help="Try multiple preprocessing passes, take best result")
    return p.parse_args()


SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]

# Preprocessing variants for recovery
PREPROCESS_PIPELINES = {
    "none": lambda img: img,
    "sharpen_2x": lambda img: img.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN),
    "sharpen_1x": lambda img: img.filter(ImageFilter.SHARPEN),
    "unsharp_mask": lambda img: img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)),
    "denoise": lambda img: img.filter(ImageFilter.MedianFilter(3)),
    "contrast_1.2": lambda img: ImageEnhance.Contrast(img).enhance(1.2),
    "contrast_1.5": lambda img: ImageEnhance.Contrast(img).enhance(1.5),
    "edge_enhance": lambda img: img.filter(ImageFilter.EDGE_ENHANCE),
    "detail": lambda img: img.filter(ImageFilter.DETAIL),
}


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * ratio); side = max(1, int(area**0.5)); side = min(side, h, w)
    top = rng.randint(0, max(0, h - side)); left = rng.randint(0, max(0, w - side))
    mask[:, :, top:top+side, left:left+side] = 1.0
    return mask


def apply_attack(name, img_w, unnorm, dft, device, rng):
    img01 = unnorm(img_w.detach().clone()).clamp(0,1).squeeze(0).cpu()
    img_pil = TVF.to_pil_image(img01)
    w, h = img_pil.size
    if name == "none": return img_pil, img_w
    elif name == "random_crop_0.5":
        cw, ch = max(1,int(w*0.5)), max(1,int(h*0.5))
        left=rng.randint(0,max(0,w-cw)); top=rng.randint(0,max(0,h-ch))
        cropped = img_pil.crop((left,top,left+cw,top+ch)).resize((w,h), Image.BICUBIC)
    else:
        return img_pil, img_w
    return cropped, dft(cropped).unsqueeze(0).to(device)


def decode_at_scale(attacked_pt, scale, wam, mp_infer, device, unnorm, dft):
    _, _, h, w = attacked_pt.shape
    if abs(scale - 1.0) < 1e-6: scaled = attacked_pt
    else:
        ns = int(h*scale)
        img_pil = TVF.to_pil_image(unnorm(attacked_pt.detach().clone()).clamp(0,1).squeeze(0).cpu())
        img_pil = img_pil.resize((ns,ns), Image.BICUBIC)
        if scale < 1.0:
            canvas = Image.new("RGB",(w,h),(0,0,0))
            canvas.paste(img_pil,((w-ns)//2,(h-ns)//2)); img_pil = canvas
        else:
            l,t=(ns-w)//2,(ns-h)//2; img_pil = img_pil.crop((l,t,l+w,t+h))
        scaled = dft(img_pil).unsqueeze(0).to(device)
    preds = wam.detect(scaled)["preds"]
    mp = torch.sigmoid(preds[:,0:1,:,:]); bp = preds[:,1:,:,:]
    return mp_infer(bp, mp, method="semihard").float(), mp.mean().item()


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
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tag = "preprocess" if args.use_preprocess else "baseline"
    if args.use_multi_scale: tag += "_ms"
    print(f"device={device} mode={tag}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = float(args.scaling_w)

    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])
    image_paths = sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]], []))[:args.limit]
    rng = np.random.RandomState(args.seed)
    msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
    print(f"images={len(image_paths)}", flush=True)

    attacks = ["none", "random_crop_0.5"]
    rows = []

    for img_idx, image_path in enumerate(image_paths):
        img = Image.open(image_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device)

        mask = create_random_mask(img_pt, 0.5, rng, device)
        outputs = wam.embed(img_pt, msg)
        img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

        for attack_name in attacks:
            attacked_pil, attacked_pt = apply_attack(attack_name, img_w, unnorm, dft, device, rng)

            # Baseline: direct detection
            if args.use_multi_scale:
                best_acc = 0.0
                for scale in SCALES:
                    pred_msg, _ = decode_at_scale(attacked_pt, scale, wam, mp_infer, device, unnorm, dft)
                    acc = (pred_msg == msg).float().mean().item()
                    if acc > best_acc: best_acc = acc
                base_acc = best_acc
            else:
                preds = wam.detect(attacked_pt)["preds"]
                mp_t = torch.sigmoid(preds[:,0:1,:,:]); bp_t = preds[:,1:,:,:]
                pred_msg = mp_infer(bp_t, mp_t, method="semihard").float()
                base_acc = (pred_msg == msg).float().mean().item()

            rows.append({"image": image_path.name, "attack": attack_name,
                         "method": tag, "preprocess": "none",
                         "bit_accuracy": f"{base_acc:.6f}",
                         "message_success": 1 if base_acc == 1.0 else 0})

            # Preprocessing passes
            if args.use_preprocess and attack_name != "none":
                best_pass_acc = base_acc; best_pass = "none"
                for pp_name, pp_fn in PREPROCESS_PIPELINES.items():
                    if pp_name == "none": continue
                    pp_pil = pp_fn(attacked_pil)
                    pp_pt = dft(pp_pil).unsqueeze(0).to(device)

                    if args.use_multi_scale:
                        pp_acc = 0.0
                        for scale in SCALES:
                            pred_msg, _ = decode_at_scale(pp_pt, scale, wam, mp_infer, device, unnorm, dft)
                            acc = (pred_msg == msg).float().mean().item()
                            if acc > pp_acc: pp_acc = acc
                    else:
                        preds = wam.detect(pp_pt)["preds"]
                        mp_t = torch.sigmoid(preds[:,0:1,:,:]); bp_t = preds[:,1:,:,:]
                        pred_msg = mp_infer(bp_t, mp_t, method="semihard").float()
                        pp_acc = (pred_msg == msg).float().mean().item()

                    if pp_acc > best_pass_acc:
                        best_pass_acc = pp_acc; best_pass = pp_name

                rows.append({"image": image_path.name, "attack": attack_name,
                             "method": tag, "preprocess": f"best:{best_pass}",
                             "bit_accuracy": f"{best_pass_acc:.6f}",
                             "message_success": 1 if best_pass_acc == 1.0 else 0})

        print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}", flush=True)

    csv_path = out_dir / "preprocess_recovery_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image","attack","method","preprocess","bit_accuracy","message_success"])
        w.writeheader(); w.writerows(rows)

    # Summary: baseline vs best-preprocess
    summary = out_dir / "preprocess_recovery_summary.csv"
    agg = defaultdict(lambda: {"s":0.0,"c":0,"ok":0,"pp_s":0.0,"pp_c":0,"pp_ok":0})
    for r in rows:
        if r["preprocess"] == "none":
            agg[r["attack"]]["s"] += float(r["bit_accuracy"]); agg[r["attack"]]["c"] += 1
            agg[r["attack"]]["ok"] += int(r["message_success"])
        else:
            agg[r["attack"]]["pp_s"] += float(r["bit_accuracy"]); agg[r["attack"]]["pp_c"] += 1
            agg[r["attack"]]["pp_ok"] += int(r["message_success"])

    with summary.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["attack","baseline_mean_acc","baseline_success","preprocess_mean_acc","preprocess_success","num_samples","method"])
        for a in sorted(agg):
            d=agg[a]
            w.writerow([a,
                f"{d['s']/d['c']:.6f}" if d['c']>0 else "0",
                f"{d['ok']/d['c']:.4f}" if d['c']>0 else "0",
                f"{d['pp_s']/d['pp_c']:.6f}" if d['pp_c']>0 else "0",
                f"{d['pp_ok']/d['pp_c']:.4f}" if d['pp_c']>0 else "0",
                d['c'],tag])
    print(f"done: {len(rows)} rows", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
