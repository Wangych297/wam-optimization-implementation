"""
Ablation Study — Consolidated Pipeline

Two independent series, both on COCO 50:

Series 1 (32-bit, no ECC):
  A: Baseline (single-scale)
  B: + Multi-scale
  C: B + Geometric 20° scan

Series 2 (rep4 encoded, 8-bit payload):
  D: Baseline + ECC decode
  E: + Multi-scale + ECC
  F: + Geometric 20° + ECC

All attacks: none, center_crop_0.5, random_crop_0.5,
            jpeg_q30, resize_0.25, rotate_73, flip_h
"""

import argparse, csv, io, os, random, sys
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
    return p.parse_args()


SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]
GEO_ANGLES = list(range(0, 360, 20))

# Ablation configurations
MODES = [
    ("A_base",       False, False, False),
    ("B_ms",         True,  False, False),
    ("C_ms_geo",     True,  False, True),
    ("D_ecc",        False, True,  False),
    ("E_ms_ecc",     True,  True,  False),
    ("F_ms_ecc_geo", True,  True,  True),
]


def create_random_mask(img_pt, ratio, rng, device):
    _, _, h, w = img_pt.shape; mask = torch.zeros(1,1,h,w,device=device)
    area=int(h*w*ratio); side=max(1,int(area**0.5)); side=min(side,h,w)
    top=rng.randint(0,max(0,h-side)); left=rng.randint(0,max(0,w-side))
    mask[:,:,top:top+side,left:left+side]=1.0
    return mask


def rotate_tensor_gpu(img_t, angle_deg):
    a=angle_deg*np.pi/180; ca,sa=np.cos(a),np.sin(a)
    theta=torch.tensor([[[ca,-sa,0.0],[sa,ca,0.0]]],dtype=torch.float32,device=img_t.device)
    grid=F.affine_grid(theta,img_t.size(),align_corners=False)
    return F.grid_sample(img_t,grid,mode='bilinear',padding_mode='zeros',align_corners=False)


def apply_attack(name, img_w, unnorm, dft, device, rng):
    img01=unnorm(img_w.detach().clone()).clamp(0,1).squeeze(0).cpu()
    pil=TVF.to_pil_image(img01); w,h=pil.size
    if name=="none": return img_w
    elif name=="center_crop_0.5":
        cw,ch=max(1,int(w*.5)),max(1,int(h*.5)); l,t=(w-cw)//2,(h-ch)//2
        cropped=pil.crop((l,t,l+cw,t+ch)).resize((w,h),Image.BICUBIC)
    elif name=="random_crop_0.5":
        cw,ch=max(1,int(w*.5)),max(1,int(h*.5))
        l=rng.randint(0,max(0,w-cw)); t=rng.randint(0,max(0,h-ch))
        cropped=pil.crop((l,t,l+cw,t+ch)).resize((w,h),Image.BICUBIC)
    elif name=="jpeg_q30":
        buf=io.BytesIO(); pil.save(buf,format="JPEG",quality=30); buf.seek(0)
        cropped=Image.open(buf).convert("RGB")
    elif name.startswith("resize_"):
        ratio=float(name.split("_")[-1])
        nw,nh=max(1,int(w*ratio)),max(1,int(h*ratio))
        cropped=pil.resize((nw,nh),Image.BICUBIC).resize((w,h),Image.BICUBIC)
    elif name.startswith("rotate_"):
        angle=float(name.split("_")[-1])
        cropped=pil.rotate(angle,resample=Image.BICUBIC,expand=False)
    elif name=="flip_h": cropped=pil.transpose(Image.FLIP_LEFT_RIGHT)
    else: return img_w
    return dft(cropped).unsqueeze(0).to(device)


def detect_single(attacked_pt, wam, mp_infer, target_msg):
    preds=wam.detect(attacked_pt)["preds"]
    mp_t=torch.sigmoid(preds[:,0:1,:,:]); bp_t=preds[:,1:,:,:]
    pred_msg=mp_infer(bp_t,mp_t,method="semihard").float()
    return pred_msg


def detect_ms(attacked_pt, wam, mp_infer, device, unnorm, dft, target_msg):
    _,_,h,w=attacked_pt.shape; best=None; best_conf=0.0
    for scale in SCALES:
        if abs(scale-1.0)<1e-6: scaled=attacked_pt
        else:
            ns=int(h*scale); p=TVF.to_pil_image(unnorm(attacked_pt).clamp(0,1).squeeze(0).cpu())
            p=p.resize((ns,ns),Image.BICUBIC)
            if scale<1.0: c=Image.new("RGB",(w,h),(0,0,0)); c.paste(p,((w-ns)//2,(h-ns)//2)); p=c
            else: lt=(ns-w)//2; p=p.crop((lt,lt,lt+w,lt+h))
            scaled=dft(p).unsqueeze(0).to(device)
        preds=wam.detect(scaled)["preds"]
        mp_t=torch.sigmoid(preds[:,0:1,:,:]); bp_t=preds[:,1:,:,:]
        pred_msg=mp_infer(bp_t,mp_t,method="semihard").float()
        conf=mp_t.mean().item()
        if conf>best_conf: best_conf=conf; best=pred_msg
    best_acc=(best==target_msg).float().mean().item() if best is not None else 0.0
    return best, best_acc


def detect_geo(attacked_pt, wam, mp_infer, device, unnorm, dft, target_msg):
    cands=[rotate_tensor_gpu(attacked_pt,-a) for a in GEO_ANGLES]
    batch=torch.cat(cands,dim=0)
    preds_b=wam.detect(batch)["preds"]
    best_conf=0.0; best_msg=None
    for i in range(len(GEO_ANGLES)):
        mp_t=torch.sigmoid(preds_b[i:i+1,0:1,:,:]); bp_t=preds_b[i:i+1,1:,:,:]
        pred_msg=mp_infer(bp_t,mp_t,method="semihard").float()
        conf=mp_t.mean().item()
        if conf>best_conf: best_conf=conf; best_msg=pred_msg
    return (best_msg==target_msg).float().mean().item() if best_msg is not None else 0.0


def ecc_encode_rep4(payload):
    bits=[b for b in payload for _ in range(4)]  # 32 bits
    return torch.tensor(bits,dtype=torch.float32)


def ecc_decode_rep4(bits_32):
    recovered=[]
    for i in range(8): recovered.append(1 if sum(bits_32[i*4:(i+1)*4])>=2 else 0)
    return recovered


def main():
    args=parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    run_root=Path(args.project_root).resolve()
    sys.path.insert(0,str(run_root)); sys.path.insert(0,str(run_root/"notebooks")); os.chdir(run_root)

    from inference_utils import load_model_from_checkpoint
    from watermark_anything.data.metrics import msg_predict_inference as mp_infer
    from torchvision import transforms as T
    from watermark_anything.data.transforms import default_transform as dft, unnormalize_img as unnorm

    out_dir=Path(args.out_dir).resolve(); out_dir.mkdir(parents=True,exist_ok=True)
    device=torch.device("cuda")
    wam=load_model_from_checkpoint(args.params,args.checkpoint).to(device).eval()
    wam.scaling_w=float(args.scaling_w)

    it=T.Compose([T.Resize(256),T.CenterCrop(256),dft])
    image_paths=sorted(sum([list(Path(args.image_dir).glob(f"*.{s}")) for s in ["jpg","jpeg","png","bmp"]],[]))[:args.limit]
    rng=np.random.RandomState(args.seed)

    # Two embedding messages
    msg_32=torch.from_numpy(rng.randint(0,2,32).astype(np.float32)).unsqueeze(0).to(device)  # Series 1
    payload_8=[rng.randint(0,1) for _ in range(8)]
    msg_32_ecc=ecc_encode_rep4(payload_8).unsqueeze(0).to(device)  # Series 2

    attacks=["none","center_crop_0.5","random_crop_0.5","jpeg_q30","resize_0.25","rotate_73","flip_h"]
    rows=[]

    for img_idx,image_path in enumerate(image_paths):
        img=Image.open(image_path).convert("RGB"); img_pt=it(img).unsqueeze(0).to(device)
        mask=create_random_mask(img_pt,0.5,rng,device)

        # Embed both messages
        img_w_32=wam.embed(img_pt,msg_32)["imgs_w"]*mask+img_pt*(1-mask)
        img_w_ecc=wam.embed(img_pt,msg_32_ecc)["imgs_w"]*mask+img_pt*(1-mask)

        for attack_name in attacks:
            att_32=apply_attack(attack_name,img_w_32,unnorm,dft,device,rng)
            att_ecc=apply_attack(attack_name,img_w_ecc,unnorm,dft,device,rng)

            for name,use_ms,use_ecc,use_geo in MODES:
                if use_ecc: eval_att=att_ecc; tgt=msg_32_ecc
                else: eval_att=att_32; tgt=msg_32

                if use_geo and attack_name.startswith("rotate_"):
                    bit_acc_32=detect_geo(eval_att,wam,mp_infer,device,unnorm,dft,tgt)
                    if use_ecc:
                        best_msg,_=detect_ms(eval_att,wam,mp_infer,device,unnorm,dft,tgt)
                        if best_msg is not None:
                            recovered=ecc_decode_rep4(best_msg.int().view(-1).tolist())
                            bit_acc=sum(1 for a,b in zip(recovered,payload_8) if a==b)/8
                        else: bit_acc=0.0
                    else: bit_acc=bit_acc_32
                elif use_ms:
                    best_msg,best_acc_32=detect_ms(eval_att,wam,mp_infer,device,unnorm,dft,tgt)
                    if use_ecc and best_msg is not None:
                        recovered=ecc_decode_rep4(best_msg.int().view(-1).tolist())
                        bit_acc=sum(1 for a,b in zip(recovered,payload_8) if a==b)/8
                    else: bit_acc=best_acc_32
                else:
                    pred_msg=detect_single(eval_att,wam,mp_infer,tgt)
                    if use_ecc:
                        recovered=ecc_decode_rep4(pred_msg.int().view(-1).tolist())
                        bit_acc=sum(1 for a,b in zip(recovered,payload_8) if a==b)/8
                    else: bit_acc=(pred_msg==tgt).float().mean().item()

                rows.append({"image":image_path.name,"attack":attack_name,"mode":name,
                             "bit_accuracy":f"{bit_acc:.6f}","message_success":1 if bit_acc==1.0 else 0})
        print(f"[{img_idx+1}/{len(image_paths)}] {image_path.name}",flush=True)

    csv_path=out_dir/"ablation_metrics.csv"
    with csv_path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,["image","attack","mode","bit_accuracy","message_success"]); w.writeheader(); w.writerows(rows)

    summary=out_dir/"ablation_summary.csv"
    agg=defaultdict(lambda:{"s":0.0,"c":0,"ok":0})
    for r in rows:
        k=(r["attack"],r["mode"]); agg[k]["s"]+=float(r["bit_accuracy"]); agg[k]["c"]+=1; agg[k]["ok"]+=int(r["message_success"])
    with summary.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["attack","mode","mean_bit_accuracy","message_success_rate","num_samples"])
        for (att,mode) in sorted(agg.keys()): d=agg[(att,mode)]; w.writerow([att,mode,f"{d['s']/d['c']:.6f}",f"{d['ok']/d['c']:.4f}",d['c']])

    print("\n===== ABLATION RESULTS =====\n")
    print(f"{'Attack':<22}{'A_base':>10}{'B_ms':>10}{'C_ms_geo':>12}{'D_ecc':>10}{'E_ms_ecc':>12}{'F_full':>10}")
    print("-"*76)
    for att in sorted(set(k[0] for k in agg)):
        print(f"{att:<22}",end="")
        for _,_,_,name in [(0,0,0,"A_base"),(1,0,0,"B_ms"),(1,0,1,"C_ms_geo"),(0,1,0,"D_ecc"),(1,1,0,"E_ms_ecc"),(1,1,1,"F_full")]:
            if (att,name) in agg: d=agg[(att,name)]; print(f"{d['s']/d['c']:.4f}".rjust(10),end=""); print(f" {d['ok']/d['c']:.0%}".rjust(4),end="")
            else: print(" " * 14,end="")
        print()
    print(f"\nNote: A/B/C use 32-bit metric, D/E/F use 8-bit ECC metric",flush=True)


if __name__=="__main__": raise SystemExit(main())
