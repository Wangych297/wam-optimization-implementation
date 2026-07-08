# 14 ECC 编码方案扩展 + 新攻击类型覆盖

## 目标

在实验 11（rep3/rep5/rep4_interleaved）基础上，进一步探索交织编码对 random_crop 的影响，并评估多尺度+ECC 管线在 resize、极端 JPEG、组合攻击上的表现。

## 参考文献

- **RoSteALS: Robust Steganography using Autoencoder Latent Space** (CVPR 2023 Workshop) — 交织编码抵抗 burst error
- **MBRS: Enhancing Robustness of DNN-based Watermarking** (ACM MM 2021) — message processor 冗余编码
- 实验 11 和实验 11 v2 — 延续已有 ECC 探索

## 实验设置

- 模型：WAM wam_mit.pth, scaling_w=2.5, mask_ratio=0.5
- 所有测试均开启多尺度检测 + ECC
- ECC 方案：rep3（对照）、rep3_interleaved（NEW）、rep4_adjacent（NEW）、rep4_interleaved（最优）
- 攻击：原有 5 种 + resize_0.5、resize_0.25、jpeg_q10、jpeg_q5、crop_50_jpeg_30
- 数据：COCO 50
- 实现：`watermark_anything/extensions/multi_scale/multi_scale_ecc.py`（`--ecc-mode` 参数）

## 运行命令

```bash
# rep3_interleaved (10-bit)
python watermark_anything/extensions/multi_scale/multi_scale_ecc.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/ecc_v3/rep3_interleaved \
  --limit 50 --use-multi-scale --use-ecc --ecc-mode rep3_interleaved

# rep4_adjacent (8-bit, no interleave)
python watermark_anything/extensions/multi_scale/multi_scale_ecc.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/ecc_v3/rep4_adjacent \
  --limit 50 --use-multi-scale --use-ecc --ecc-mode rep4_adjacent

# rep3 baseline + new attacks
python watermark_anything/extensions/multi_scale/multi_scale_ecc.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/ecc_v3/rep3_newattacks \
  --limit 50 --use-multi-scale --use-ecc --ecc-mode rep3
```

## 结论 — 正向 + 扩展覆盖

### ECC 模式对比 (random_crop_0.5)

| ECC 模式 | 有效载荷 | mean | 成功率 | vs rep3 |
|----------|:------:|:----:|:-----:|:-------:|
| rep3 (baseline) | 10-bit | 0.816 | 8.0% | — |
| rep3_interleaved | 10-bit | 0.802 | **20.0%** | 成功率 ×2.5 |
| rep4_adjacent | 8-bit | 0.818 | 18.0% | mean 略高 |
| rep4_interleaved | 8-bit | **0.823** | **20.0%** | 综合最优 |

### 新攻击类型

| 攻击 | rep3 mean | 判断 |
|------|:----:|------|
| resize_0.5 | 1.000 | ✅ |
| resize_0.25 | 0.972 (+rep4_adj: 1.000) | 🟡 |
| jpeg_q10 | 0.996 | ✅ |
| jpeg_q5 | 0.998 | ✅ |
| crop_50_jpeg_30 | 1.000 | ✅ |

1. 交织编码是关键：rep3→rep3_int 成功率翻 2.5×，确认 burst error 是 random_crop 残余问题
2. rep4_interleaved 仍是综合最优：最高 mean + 最高成功率
3. resize/极端JPEG/组合攻击均被多尺度+ECC 管线有效覆盖
