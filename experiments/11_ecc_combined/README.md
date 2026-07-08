# 11 多尺度检测 + 纠错码组合

## 目标

实验 10 证明多尺度检测能将 center_crop 提升至 0.99975，但 random_crop 仅到 0.701。残余错误源于随机裁剪后部分水印像素彻底丢失。本实验在多尺度检测基础上叠加轻量纠错码 (ECC)，用容量换鲁棒性，测试是否能进一步提升 random_crop 恢复率。

## 参考文献

- **MBRS: Enhancing Robustness of DNN-based Watermarking by Mini-Batch of Real and Simulated JPEG Compression** (ACM MM 2021) — 借鉴 message processor 扩展消息实现冗余的思想
- **RoSteALS: Robust Steganography using Autoencoder Latent Space** (CVPR 2023 Workshop) — 借鉴 BCH/ECC 码在噪声信道下改善 secret recovery 的经验

## 实验设置

- 模型：WAM wam_mit.pth, scaling_w=2.5, mask_ratio=0.5
- ECC 方案：rep3（每 bit 重复 3 次，32-bit → 10-bit 有效载荷 + 2-bit padding）
- 所有试验均开启多尺度检测（实验 10 已证明有效）
- 攻击：center_crop_0.5, center_crop_0.75, random_crop_0.5, jpeg_q30, none
- 数据：COCO 50
- 实现：`watermark_anything/extensions/multi_scale/multi_scale_ecc.py`
- 参数：`--use-ecc`（默认关）

## 运行命令

```bash
# 对照组（多尺度，无 ECC）
python watermark_anything/extensions/multi_scale/multi_scale_ecc.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/ecc_combined/control \
  --limit 50 --use-multi-scale

# 实验组（多尺度 + ECC）
python watermark_anything/extensions/multi_scale/multi_scale_ecc.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/ecc_combined/experimental \
  --limit 50 --use-multi-scale --use-ecc
```

## 结论 — 正向

| Attack | Multi-scale (32bit) | + ECC (10bit) | 变化 |
|--------|:---:|:---:|:---:|
| random_crop_0.5 | 0.698 | **0.816** | +16.9% |
| center_crop_0.5/0.75 | 1.000 | 1.000 | — |

ECC 有效，但代价是容量从 32bit→10bit。8% 图片达到完美恢复。

### COCO 5000 全量确认

| Attack | Multi-scale (32bit) | + ECC (10bit) | 变化 | 成功率 |
|--------|:---:|:---:|:---:|:---:|
| random_crop_0.5 | 0.701 | **0.804** | +14.7% | 7.5% |
| center_crop_0.5 | 0.99975 | **1.000** | — | 100% |

50 图和 5000 图一致：ECC 有效，以容量换鲁棒性。

### ECC 方案扩展（v2）

| ECC 方案 | 有效载荷 | 50图 mean | 50图 成功率 | 5000图 mean | 5000图 成功率 |
|----------|:------:|:---------:|:----------:|:-----------:|:------------:|
| rep3 | 10-bit | 0.816 | 8.0% | 0.804 | 7.5% |
| rep4_interleaved | 8-bit | 0.823 | 20.0% | **0.815** | **19.9%** |
| rep5 | 6-bit | 0.813 | 28.0% | — | — |

rep4_interleaved 是当前最优：最高 accuracy + 成功率翻近 3 倍。adaptive scale 无损（center_crop 可免扫描）。
