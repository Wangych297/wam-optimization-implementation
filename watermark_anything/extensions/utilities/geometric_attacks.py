"""
Geometric Attack Robustness Evaluation v2

Tests:
1. Baseline: rotation/flip without correction
2. Derotation: apply rotation attack, then derotate by -angle before detection
3. Multi-scale: combine derotation with multi-scale detection

References:
- GResMark (ESWA 2025): geometric distortion immunity via Swin+DCN
- Geometric Distortion Immunized Framework (ECCV 2024)
"""

import argparse, csv, os, random, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
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
    p.add_argument("--use-derotation", action="store_true",
                   help="Derotate by known -angle before detection (upper bound)")
    p.add_argument("--use-angle-scan", action="store_true",
                   help="Blind scan: try multiple candidate angles, pick best confidence")
    p.add_argument("--use-fourier-estimate", action="store_true",
                   help="Estimate rotation angle via Fourier-Mellin (O(1)), then derotate once")
    p.add_argument("--angle-step", type=int, default=15,
                   help="Angle step size in degrees for flat scan (default: 15)")
    p.add_argument("--use-hierarchical", action="store_true",
                   help="Coarse-to-fine hierarchical search: 60° coarse + 10° fine (13 total)")
    return p.parse_args()


SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]
def rotate_tensor_gpu(img_t, angle_deg):
    """Rotate GPU tensor [1,3,H,W] by angle_deg using affine_grid."""
    angle = angle_deg * np.pi / 180.0
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    theta = torch.tensor([[[cos_a, -sin_a, 0.0], [sin_a, cos_a, 0.0]]],
                         dtype=torch.float32, device=img_t.device)
    grid = F.affine_grid(theta, img_t.size(), align_corners=False)
    return F.grid_sample(img_t, grid, mode='bilinear', padding_mode='zeros', align_corners=False)


def estimate_rotation_fourier(attacked_pil, reference_pil):
    """
    Estimate rotation angle via OpenCV logPolar + phaseCorrelate.
    Rotation → horizontal shift in log-polar FFT magnitude.
    OpenCV phaseCorrelate provides sub-pixel accuracy.

    Reference: Reddy & Chatterji, "An FFT-Based Technique for Translation,
    Rotation, and Scale-Invariant Image Registration", IEEE TIP 1996.
    """
    import cv2
    import numpy as np

    ref = np.array(reference_pil.convert('L'), dtype=np.float32)
    att = np.array(attacked_pil.convert('L'), dtype=np.float32)
    h, w = ref.shape

    # Hanning window
    hy = np.hanning(h).astype(np.float32)
    hx = np.hanning(w).astype(np.float32)
    window = np.sqrt(hy[:, None] * hx[None, :])

    # FFT magnitude
    F_ref = np.fft.fftshift(np.fft.fft2(ref * window))
    F_att = np.fft.fftshift(np.fft.fft2(att * window))
    M_ref = np.float32(np.abs(F_ref))
    M_att = np.float32(np.abs(F_att))

    # High-pass filter
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    radius = np.sqrt((x - cx)**2 + (y - cy)**2).astype(np.float32)
    hp = (radius > max(h, w) * 0.04).astype(np.float32)
    M_ref *= hp; M_att *= hp

    # Convert to log-polar: M = max radius for full-width mapping
    n_angles = 360
    M = float(w)
    lp_ref = cv2.logPolar(M_ref, (cx, cy), M, cv2.INTER_LINEAR + cv2.WARP_FILL_OUTLIERS)
    lp_ref = cv2.resize(lp_ref, (n_angles, lp_ref.shape[0]))
    lp_att = cv2.logPolar(M_att, (cx, cy), M, cv2.INTER_LINEAR + cv2.WARP_FILL_OUTLIERS)
    lp_att = cv2.resize(lp_att, (n_angles, lp_att.shape[0]))

    # Phase correlation: finds horizontal shift between log-polar images
    shift, response = cv2.phaseCorrelate(np.float64(lp_ref), np.float64(lp_att))

    angle_deg = (shift[0] * 360.0 / n_angles) % 360
    if angle_deg > 180:
        angle_deg -= 360
    return angle_deg


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * ratio); side = max(1, int(area**0.5)); side = min(side, h, w)
    top = rng.randint(0, max(0, h - side)); left = rng.randint(0, max(0, w - side))
    mask[:, :, top:top+side, left:left+side] = 1.0
    return mask


def apply_geo_attack(name, img_w, unnorm, dft, device, derotate):
    img01 = unnorm(img_w.detach().clone()).clamp(0,1).squeeze(0).cpu()
    img_pil = TVF.to_pil_image(img01)
    w, h = img_pil.size

    if name == "none":
        return dft(img_pil).unsqueeze(0).to(device)
    elif name.startswith("rotate_"):
        angle = float(name.split("_")[-1])
        rotated = img_pil.rotate(angle, resample=Image.BICUBIC, expand=False)
        if derotate:
            rotated = rotated.rotate(-angle, resample=Image.BICUBIC, expand=False)
    elif name == "flip_h":
        rotated = img_pil.transpose(Image.FLIP_LEFT_RIGHT)
        if derotate:
            rotated = rotated.transpose(Image.FLIP_LEFT_RIGHT)
    elif name == "flip_v":
        rotated = img_pil.transpose(Image.FLIP_TOP_BOTTOM)
        if derotate:
            rotated = rotated.transpose(Image.FLIP_TOP_BOTTOM)
    elif name == "rotate_45_crop_50":
        rotated = img_pil.rotate(45, resample=Image.BICUBIC, expand=False)
        if derotate:
            rotated = rotated.rotate(-45, resample=Image.BICUBIC, expand=False)
        cw, ch = max(1, int(w*0.5)), max(1, int(h*0.5))
        l, t = (w-cw)//2, (h-ch)//2
        rotated = rotated.crop((l,t,l+cw,t+ch)).resize((256,256), Image.BICUBIC)
    else:
        return img_w
    return dft(rotated).unsqueeze(0).to(device)


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
    tag = "fourier" if args.use_fourier_estimate else ("hierarchical" if args.use_hierarchical else ("angle_scan" if args.use_angle_scan else ("derotate" if args.use_derotation else "baseline")))
    if args.use_multi_scale: tag += "_ms"
    print(f"device={device} mode={tag}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = float(args.scaling_w)

    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])
    image_paths = sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]], []))[:args.limit]
    rng = np.random.RandomState(args.seed)
    msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
    print(f"message={msg_to_str(msg)} images={len(image_paths)}", flush=True)

    angle_candidates = list(range(0, 360, args.angle_step))
    print(f"angle_candidates={len(angle_candidates)} (step={args.angle_step}°)", flush=True)

    rows = []

    for img_idx, image_path in enumerate(image_paths):
        img = Image.open(image_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device)

        mask = create_random_mask(img_pt, 0.5, rng, device)
        outputs = wam.embed(img_pt, msg)
        img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

        # Reference PIL image for Fourier estimation
        wm_pil_ref = TVF.to_pil_image(unnorm(img_w).clamp(0,1).squeeze(0).cpu())

        # Per-image random attack angles
        attacks = ["none"] + [f"rotate_{rng.randint(0, 359)}" for _ in range(3)] + \
                  ["flip_h", "flip_v", "rotate_45_crop_50"]

        for attack_name in attacks:
            if args.use_fourier_estimate and attack_name.startswith("rotate_"):
                # Fourier-Mellin angle estimation (O(1) detection)
                attacked_geo = apply_geo_attack(attack_name, img_w, unnorm, dft, device, derotate=False)
                img01_g = unnorm(attacked_geo.detach().clone()).clamp(0,1).squeeze(0).cpu()
                pil_g = TVF.to_pil_image(img01_g)

                est_angle = estimate_rotation_fourier(pil_g, wm_pil_ref)
                derotated = pil_g.rotate(-est_angle, resample=Image.BICUBIC, expand=False)
                cand_pt = dft(derotated).unsqueeze(0).to(device)

                preds = wam.detect(cand_pt)["preds"]
                mp_t = torch.sigmoid(preds[:,0:1,:,:]); bp_t = preds[:,1:,:,:]
                pred_msg = mp_infer(bp_t, mp_t, method="semihard").float()
                bit_acc = (pred_msg == msg).float().mean().item()

            elif args.use_angle_scan and (attack_name.startswith("rotate_") or attack_name.startswith("flip_")):
                attacked_geo = apply_geo_attack(attack_name, img_w, unnorm, dft, device, derotate=False)

                if attack_name.startswith("rotate_"):
                    # GPU rotate + batch detect
                    cands = [rotate_tensor_gpu(attacked_geo, -a) for a in angle_candidates]
                    batch = torch.cat(cands, dim=0).to(device)
                elif attack_name.startswith("flip_"):
                    img01_g = unnorm(attacked_geo.detach().clone()).clamp(0,1).squeeze(0).cpu()
                    pil_g = TVF.to_pil_image(img01_g)
                    cands = [dft(pil_g), dft(pil_g.transpose(Image.FLIP_LEFT_RIGHT)), dft(pil_g.transpose(Image.FLIP_TOP_BOTTOM))]
                    batch = torch.stack(cands).to(device)

                preds_batch = wam.detect(batch)["preds"]
                best_acc = 0.0
                for i in range(len(cands)):
                    mp_t = torch.sigmoid(preds_batch[i:i+1, 0:1, :, :])
                    bp_t = preds_batch[i:i+1, 1:, :, :]
                    acc = (mp_infer(bp_t, mp_t, method="semihard").float() == msg).float().mean().item()
                    if acc > best_acc: best_acc = acc

                bit_acc = best_acc

            elif args.use_hierarchical and attack_name.startswith("rotate_"):
                # GPU hierarchical: 60° coarse → 10° medium → 3° fine
                # All rotations on GPU tensor, no PIL roundtrip
                attacked_geo = apply_geo_attack(attack_name, img_w, unnorm, dft, device, derotate=False)

                # Stage 1: coarse at 60° step (6 candidates), GPU rotate + batch detect
                coarse_angles = sorted(set(list(range(0, 360, 60)) + [90, 270]))  # 8 candidates
                coarse_cands = [rotate_tensor_gpu(attacked_geo, -a) for a in coarse_angles]
                batch = torch.cat(coarse_cands, dim=0).to(device)
                preds_b = wam.detect(batch)["preds"]
                best_coarse_acc = 0.0; best_coarse = 0
                for i, a in enumerate(coarse_angles):
                    mp_t = torch.sigmoid(preds_b[i:i+1, 0:1, :, :])
                    bp_t = preds_b[i:i+1, 1:, :, :]
                    acc = (mp_infer(bp_t, mp_t, method="semihard").float() == msg).float().mean().item()
                    if acc > best_coarse_acc: best_coarse_acc = acc; best_coarse = a

                # Stage 2: medium at 10° step around best (7 candidates: ±30°)
                med_angles = [(best_coarse + d) % 360 for d in range(-30, 31, 10)]
                med_cands = [rotate_tensor_gpu(attacked_geo, -a) for a in med_angles]
                batch_med = torch.cat(med_cands, dim=0).to(device)
                preds_m = wam.detect(batch_med)["preds"]
                best_med_acc = 0.0; best_med = 0
                for i, a in enumerate(med_angles):
                    mp_t = torch.sigmoid(preds_m[i:i+1, 0:1, :, :])
                    bp_t = preds_m[i:i+1, 1:, :, :]
                    acc = (mp_infer(bp_t, mp_t, method="semihard").float() == msg).float().mean().item()
                    if acc > best_med_acc: best_med_acc = acc; best_med = a

                # Stage 3: fine at 3° step around best (5 candidates: ±6°)
                fine_angles = [(best_med + d) % 360 for d in range(-6, 7, 3)]
                fine_cands = [rotate_tensor_gpu(attacked_geo, -a) for a in fine_angles]
                batch_fine = torch.cat(fine_cands, dim=0).to(device)
                preds_f = wam.detect(batch_fine)["preds"]
                best_acc = 0.0
                for i in range(len(fine_angles)):
                    mp_t = torch.sigmoid(preds_f[i:i+1, 0:1, :, :])
                    bp_t = preds_f[i:i+1, 1:, :, :]
                    acc = (mp_infer(bp_t, mp_t, method="semihard").float() == msg).float().mean().item()
                    if acc > best_acc: best_acc = acc

                bit_acc = best_acc
            else:
                attacked = apply_geo_attack(attack_name, img_w, unnorm, dft, device, args.use_derotation)

                if args.use_multi_scale:
                    best_acc = 0.0
                    for scale in SCALES:
                        pred_msg, _ = decode_at_scale(attacked, scale, wam, mp_infer, device, unnorm, dft)
                        acc = (pred_msg == msg).float().mean().item()
                        if acc > best_acc: best_acc = acc
                    bit_acc = best_acc
                else:
                    preds = wam.detect(attacked)["preds"]
                    mp_t = torch.sigmoid(preds[:,0:1,:,:]); bp_t = preds[:,1:,:,:]
                    pred_msg = mp_infer(bp_t, mp_t, method="semihard").float()
                    bit_acc = (pred_msg == msg).float().mean().item()

            rows.append({"image": image_path.name, "attack": attack_name,
                         "method": tag, "bit_accuracy": f"{bit_acc:.6f}",
                         "message_success": 1 if bit_acc == 1.0 else 0})
        print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}", flush=True)

    csv_path = out_dir / "geometric_attacks_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image","attack","method","bit_accuracy","message_success"])
        w.writeheader(); w.writerows(rows)

    summary = out_dir / "geometric_attacks_summary.csv"
    agg = defaultdict(lambda: {"s":0.0,"c":0,"ok":0})
    for r in rows:
        agg[r["attack"]]["s"] += float(r["bit_accuracy"]); agg[r["attack"]]["c"] += 1
        agg[r["attack"]]["ok"] += int(r["message_success"])
    with summary.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["attack","mean_bit_accuracy","message_success_rate","num_samples","method"])
        for a in sorted(agg): d=agg[a]; w.writerow([a,f"{d['s']/d['c']:.6f}",f"{d['ok']/d['c']:.4f}",d['c'],tag])
    print(f"done: {len(rows)} rows", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
