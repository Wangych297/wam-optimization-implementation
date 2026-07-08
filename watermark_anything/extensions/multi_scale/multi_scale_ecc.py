"""
Multi-Scale + ECC Combined Decoding (v2)

Extends multi-scale detection (Exp 10) with configurable error correction coding
and adaptive scale selection.

ECC modes:
  - rep3: 10-bit payload, each bit ×3 → 30 + 2 pad = 32 (baseline, Exp 11)
  - rep5: 6-bit payload,  each bit ×5 → 30 + 2 pad = 32 (more redundancy)
  - rep4_interleaved: 8-bit payload, each bit ×4, interleaved → 32 (best so far)
  - rep3_interleaved: 10-bit payload, each bit ×3, interleaved → 32 (compare to rep3)
  - rep4_adjacent: 8-bit payload, each bit ×4, NOT interleaved → 32 (isolate interleaving benefit)

Adaptive scale: skip multi-scale scan when crop ratio is known (center_crop).

References:
- MBRS (ACM MM 2021): message processor redundancy
- RoSteALS (CVPRW 2023): BCH/ECC for noisy channel recovery
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
    p.add_argument("--use-ecc", action="store_true")
    p.add_argument("--ecc-mode", default="rep3",
                   choices=["rep3", "rep5", "rep4_interleaved", "rep3_interleaved", "rep4_adjacent"],
                   help="ECC coding scheme (default: rep3)")
    p.add_argument("--adaptive-scale", action="store_true",
                   help="Skip multi-scale scan for center_crop, use known ratio directly")
    return p.parse_args()


SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]

# ECC mode configs: (payload_bits, repeat_factor, interleaved)
ECC_CONFIGS = {
    "rep3":              (10, 3, False),
    "rep5":              (6,  5, False),
    "rep4_interleaved":  (8,  4, True),
    "rep3_interleaved":  (10, 3, True),
    "rep4_adjacent":     (8,  4, False),
}


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
    if name == "none": return img_w
    elif name.startswith("center_crop"):
        ratio = float(name.split("_")[-1])
        cw, ch = max(1, int(w*ratio)), max(1, int(h*ratio))
        left=(w-cw)//2; top=(h-ch)//2
        cropped = img_pil.crop((left, top, left+cw, top+ch)).resize((w, h), Image.BICUBIC)
    elif name.startswith("random_crop"):
        ratio = float(name.split("_")[-1])
        cw, ch = max(1, int(w*ratio)), max(1, int(h*ratio))
        left=rng.randint(0,max(0,w-cw)); top=rng.randint(0,max(0,h-ch))
        cropped = img_pil.crop((left, top, left+cw, top+ch)).resize((w, h), Image.BICUBIC)
    elif name.startswith("resize_"):
        ratio = float(name.split("_")[-1])
        nw, nh = max(1, int(w*ratio)), max(1, int(h*ratio))
        cropped = img_pil.resize((nw, nh), Image.BICUBIC).resize((w, h), Image.BICUBIC)
    elif name.startswith("jpeg_"):
        q = int(name.split("_q")[-1])
        buf=io.BytesIO(); img_pil.save(buf,format="JPEG",quality=q); buf.seek(0)
        cropped=Image.open(buf).convert("RGB")
    elif name == "crop_50_jpeg_30":
        cw,ch=max(1,int(w*0.5)),max(1,int(h*0.5)); l=(w-cw)//2; t=(h-ch)//2
        cropped=img_pil.crop((l,t,l+cw,t+ch)).resize((w,h),Image.BICUBIC)
        buf=io.BytesIO(); cropped.save(buf,format="JPEG",quality=30); buf.seek(0)
        cropped=Image.open(buf).convert("RGB")
    else: return img_w
    return dft(cropped).unsqueeze(0).to(device)


def decode_at_scale(attacked_pt, scale, wam, mp_infer, device, unnorm, dft):
    _, _, h, w = attacked_pt.shape
    if abs(scale - 1.0) < 1e-6: scaled = attacked_pt
    else:
        ns = int(h * scale)
        img_pil = TVF.to_pil_image(unnorm(attacked_pt.detach().clone()).clamp(0,1).squeeze(0).cpu())
        img_pil = img_pil.resize((ns, ns), Image.BICUBIC)
        if scale < 1.0:
            canvas = Image.new("RGB", (w, h), (0,0,0))
            canvas.paste(img_pil, ((w-ns)//2, (h-ns)//2)); img_pil = canvas
        else:
            l, t = (ns-w)//2, (ns-h)//2; img_pil = img_pil.crop((l, t, l+w, t+h))
        scaled = dft(img_pil).unsqueeze(0).to(device)
    preds = wam.detect(scaled)["preds"]
    mp = torch.sigmoid(preds[:, 0:1, :, :]); bp = preds[:, 1:, :, :]
    return mp_infer(bp, mp, method="semihard").float(), mp.mean().item()


def msg_to_str(m): return "".join("1" if b else "0" for b in m.detach().cpu().int().view(-1).tolist())


def ecc_encode(payload, n_bits, repeat, interleaved):
    """Encode n_bits payload with repetition coding → 32-bit WAM message."""
    bits = []
    for i in range(n_bits):
        bits.extend([payload[i]] * repeat)
    bits.extend([0] * (32 - n_bits * repeat))  # padding

    if interleaved:
        # Convert [a,a,a,a, b,b,b,b, c,c,c,c, ...] → [a,b,c,..., a,b,c,..., ...]
        interleaved_bits = []
        for r in range(repeat):
            for i in range(n_bits):
                interleaved_bits.append(payload[i])
        # Pad remaining
        interleaved_bits.extend([0] * (32 - len(interleaved_bits)))
        bits = interleaved_bits[:32]

    return torch.tensor(bits, dtype=torch.float32)


def ecc_decode(pred_32bit, n_bits, repeat, interleaved):
    """Decode with majority vote, handling interleaving."""
    bits = pred_32bit[:n_bits * repeat]
    if interleaved:
        # De-interleave: group bits by original position
        deinterleaved = [[] for _ in range(n_bits)]
        for idx in range(len(bits)):
            deinterleaved[idx % n_bits].append(bits[idx])
        recovered = [1 if sum(g) > len(g)//2 else 0 for g in deinterleaved]
    else:
        recovered = [1 if sum(bits[i*repeat:(i+1)*repeat]) > repeat//2 else 0
                     for i in range(n_bits)]
    return recovered


def get_scales_for_attack(attack_name, adaptive):
    """Return scales to test. If adaptive and center_crop, use only the exact scale."""
    if adaptive and attack_name.startswith("center_crop"):
        ratio = float(attack_name.split("_")[-1])
        return [ratio]
    return SCALES


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

    payload_bits, repeat, interleaved = ECC_CONFIGS[args.ecc_mode]
    tag = f"{args.ecc_mode}"
    if args.adaptive_scale: tag += "_adaptive"
    print(f"device={device} multi_scale={args.use_multi_scale} ecc={args.use_ecc} mode={tag}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = float(args.scaling_w)

    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])
    image_paths = sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]], []))[:args.limit]
    rng = np.random.RandomState(args.seed)

    if args.use_ecc:
        payload_raw = np.array([rng.randint(0, 2) for _ in range(payload_bits)], dtype=np.float32)
    else:
        payload_raw = np.array([rng.randint(0, 2) for _ in range(32)], dtype=np.float32)
    msg_raw = torch.from_numpy(payload_raw).unsqueeze(0).to(device)

    attacks = ["none", "center_crop_0.5", "center_crop_0.75", "random_crop_0.5",
               "jpeg_q30", "jpeg_q10", "jpeg_q5",
               "resize_0.5", "resize_0.25", "crop_50_jpeg_30"]
    rows = []

    for img_idx, image_path in enumerate(image_paths):
        img = Image.open(image_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device)

        if args.use_ecc:
            wam_msg = ecc_encode(payload_raw, payload_bits, repeat, interleaved).unsqueeze(0).to(device)
        else:
            wam_msg = msg_raw

        mask = create_random_mask(img_pt, 0.5, rng, device)
        outputs = wam.embed(img_pt, wam_msg)
        img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

        for attack_name in attacks:
            attacked = apply_attack(attack_name, img_w, dft, unnorm, device, rng)

            # Multi-scale decode (or adaptive single-scale)
            scales_to_try = get_scales_for_attack(attack_name, args.adaptive_scale)
            best_acc = 0.0; best_msg = None
            for scale in scales_to_try:
                pred_msg, _ = decode_at_scale(attacked, scale, wam, mp_infer, device, unnorm, dft)
                acc = (pred_msg == wam_msg).float().mean().item()
                if acc > best_acc: best_acc = acc; best_msg = pred_msg

            if args.use_ecc and best_msg is not None:
                recovered = ecc_decode(best_msg.int().view(-1).tolist(), payload_bits, repeat, interleaved)
                bit_acc = sum(1 for a,b in zip(recovered, payload_raw.astype(int).tolist()) if a==b) / payload_bits
                msg_success = 1 if bit_acc == 1.0 else 0
            else:
                bit_acc = best_acc
                msg_success = 1 if bit_acc == 1.0 else 0

            rows.append({"image": image_path.name, "attack": attack_name,
                         "bit_accuracy": f"{bit_acc:.6f}", "message_success": msg_success,
                         "ecc_mode": tag, "payload_bits": payload_bits})
        print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}", flush=True)

    csv_path = out_dir / "ecc_combined_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image","attack","bit_accuracy","message_success","ecc_mode","payload_bits"])
        w.writeheader(); w.writerows(rows)

    summary = out_dir / "ecc_combined_summary.csv"
    agg = defaultdict(lambda: {"s":0.0,"c":0,"ok":0})
    for r in rows:
        agg[r["attack"]]["s"] += float(r["bit_accuracy"]); agg[r["attack"]]["c"] += 1
        agg[r["attack"]]["ok"] += int(r["message_success"])
    with summary.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["attack","mean_bit_accuracy","message_success_rate","num_samples","ecc_mode","payload_bits"])
        for a in sorted(agg): d=agg[a]; w.writerow([a,f"{d['s']/d['c']:.6f}",f"{d['ok']/d['c']:.4f}",d['c'],tag,payload_bits])
    print(f"done: {len(rows)} rows, mode={tag}, payload={payload_bits}bit", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
