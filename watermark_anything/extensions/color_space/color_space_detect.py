"""
Color Space Detection for Saturation Attack Robustness

Tests whether converting the attacked image to a perceptually-uniform
color space (YCbCr, LAB, HSV) and back to RGB before detection improves
robustness against saturation/brightness/contrast attacks.

References:
- WH-SVD-Cb (Traitement du Signal 2025): Cb channel embedding
- Color constancy fundamentals
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
    p.add_argument("--color-space", default="rgb",
                   choices=["rgb", "ycbcr", "lab", "hsv"],
                   help="Color space for pre-detection normalization (default: rgb)")
    return p.parse_args()


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape
    mask = torch.zeros(1, 1, h, w, device=device)
    area = int(h * w * ratio); side = max(1, int(area**0.5)); side = min(side, h, w)
    top = rng.randint(0, max(0, h - side)); left = rng.randint(0, max(0, w - side))
    mask[:, :, top:top+side, left:left+side] = 1.0
    return mask


def color_roundtrip(img_pil, space):
    """Convert PIL RGB -> target color space -> back to RGB."""
    if space == "rgb":
        return img_pil
    elif space == "ycbcr":
        return img_pil.convert("YCbCr").convert("RGB")
    elif space == "lab":
        return img_pil.convert("LAB").convert("RGB")
    elif space == "hsv":
        return img_pil.convert("HSV").convert("RGB")
    return img_pil


def apply_attack(name, img_w, unnorm):
    img01 = unnorm(img_w.detach().clone()).clamp(0, 1).squeeze(0).cpu()
    img_pil = TVF.to_pil_image(img01)
    w, h = img_pil.size
    if name == "none": return img_pil
    elif name == "saturation_1.5":
        from torchvision.transforms import functional as TF
        return TF.adjust_saturation(img_pil, 1.5)
    elif name == "brightness_1.5":
        from torchvision.transforms import functional as TF
        return TF.adjust_brightness(img_pil, 1.5)
    elif name == "contrast_1.5":
        from torchvision.transforms import functional as TF
        return TF.adjust_contrast(img_pil, 1.5)
    elif name == "jpeg_q30":
        buf = io.BytesIO(); img_pil.save(buf, format="JPEG", quality=30); buf.seek(0)
        return Image.open(buf).convert("RGB")
    return img_pil


def psnr_tensor(a, b):
    a, b = a.detach().clamp(0,1), b.detach().clamp(0,1)
    mse = torch.mean((a-b)**2).item()
    return 99.0 if mse <= 1e-12 else float(20.0 * np.log10(1.0 / np.sqrt(mse)))


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
    print(f"device={device} color_space={args.color_space}", flush=True)

    wam = load_model_from_checkpoint(args.params, args.checkpoint).to(device).eval()
    wam.scaling_w = float(args.scaling_w)

    it = T.Compose([T.Resize(256), T.CenterCrop(256), dft])
    image_paths = sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]], []))[:args.limit]
    rng = np.random.RandomState(args.seed)
    msg = torch.from_numpy(rng.randint(0, 2, 32).astype(np.float32)).unsqueeze(0).to(device)
    print(f"message={msg_to_str(msg)}", flush=True)

    attacks = ["none", "saturation_1.5", "brightness_1.5", "contrast_1.5", "jpeg_q30"]
    rows = []

    for img_idx, image_path in enumerate(image_paths):
        img = Image.open(image_path).convert("RGB")
        img_pt = it(img).unsqueeze(0).to(device); img_01 = unnorm(img_pt).clamp(0, 1)

        mask = create_random_mask(img_pt, 0.5, rng, device)
        outputs = wam.embed(img_pt, msg)
        img_w = outputs["imgs_w"] * mask + img_pt * (1 - mask)

        for attack_name in attacks:
            attacked_pil = apply_attack(attack_name, img_w, unnorm)
            # Color space roundtrip
            processed_pil = color_roundtrip(attacked_pil, args.color_space)
            attacked_pt = dft(processed_pil).unsqueeze(0).to(device)

            preds = wam.detect(attacked_pt)["preds"]
            mask_preds = torch.sigmoid(preds[:, 0:1, :, :]); bit_preds = preds[:, 1:, :, :]
            pred_msg = mp_infer(bit_preds, mask_preds, method="semihard").float()
            bit_acc = (pred_msg == msg).float().mean().item()

            rows.append({"image": image_path.name, "attack": attack_name,
                         "bit_accuracy": f"{bit_acc:.6f}",
                         "message_success": 1 if bit_acc == 1.0 else 0})
        print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}", flush=True)

    csv_path = out_dir / "color_space_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["image","attack","bit_accuracy","message_success"]); w.writeheader(); w.writerows(rows)

    summary = out_dir / "color_space_summary.csv"
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
