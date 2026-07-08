# 09 空间覆盖率对裁剪鲁棒性的影响

## 目标

COCO 5000 评测显示裁剪是 WAM 水印的最大弱点（center_crop_0.5 mean=0.636, min=0.000）。根因是 random mask 仅覆盖 50% 图像面积，裁剪可能恰好移除全部水印区域。

本实验系统扫描 `mask_ratio` 参数（单中心布局），测试其在裁剪攻击下的 PSNR-鲁棒性 trade-off，寻找最优覆盖率。

**核心假设**：增大 mask_ratio 能提升裁剪鲁棒性，但存在一个临界点——超过该点后 PSNR 持续下降但鲁棒性不再提升（或提取器因 OOD 而退化）。

## 参考文献

- **DWSF: Practical Deep Dispersed Watermarking with Synchronization and Fusion** (ACM MM 2023)
  - 借鉴：面积比例 Q 与块数对鲁棒性-PSNR 权衡的影响。原论文测试了 Q=10-50%，但未测试 >50% 范围，也未专门针对裁剪攻击做单中心布局扫描。
- **TrustMark: Universal Watermarking for Arbitrary Resolution Images** (USENIX 2024)
  - 借鉴：残差强度 scaling factor 与视觉质量的 Pareto 分析。本实验将同样的权衡思想应用于 mask_ratio 维度。

## 实验设置

- 模型：WAM wam_mit.pth, scaling_w=2.5
- 布局：single_center（当前最优基线）
- 扫描参数：mask_ratio ∈ [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
- 攻击：none, center_crop_0.5, center_crop_0.75, random_crop_0.5, jpeg_q30（对照组）
- 数据：COCO 50（首次验证），通过后升级到 COCO 5000

## 代码设计

遵循 CLAUDE.md 规范：优化通过 `--mask-ratios` 参数传入，默认值为 [0.5]（保持原有行为）。

```text
watermark_anything/extensions/spatial_coverage/coverage_crop_sweep.py
```

## 运行命令

### COCO 50 小规模验证

```bash
# 对照组（默认 mask_ratio=0.5）
python watermark_anything/extensions/spatial_coverage/coverage_crop_sweep.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/coverage_crop_sweep/control \
  --limit 50

# 实验组（全参数扫描）
python watermark_anything/extensions/spatial_coverage/coverage_crop_sweep.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/coverage_crop_sweep/sweep \
  --limit 50 \
  --mask-ratios 0.5 0.6 0.7 0.8 0.9 1.0
```

### COCO 5000 全量验证（如 50 图结果正面）

```bash
# 全量扫描，10-way GPU 并行同 coverage_search 模式
for i in $(seq 0 9); do
  idx=$(printf "%02d" $i); gpu=$((i % 3))
  if [ $gpu -eq 0 ]; then gpu_id=0; elif [ $gpu -eq 1 ]; then gpu_id=6; else gpu_id=7; fi
  CUDA_VISIBLE_DEVICES=$gpu_id \
  python watermark_anything/extensions/spatial_coverage/coverage_crop_sweep.py \
    --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
    --image-dir assets/images_coco5000/chunk_${idx} \
    --out-dir results_output/coverage_crop_sweep/chunk_${idx} \
    --mask-ratios 0.5 0.6 0.7 0.8 0.9 1.0 &
done; wait
```

## 输出

```text
results_output/coverage_crop_sweep/
├── control/coverage_crop_sweep_metrics.csv
├── sweep/coverage_crop_sweep_metrics.csv
└── sweep/coverage_crop_sweep_summary.csv
```

## 结论（负向）

**假设不成立**：增大 mask 覆盖率不能提升裁剪鲁棒性。

| mask_ratio | PSNR | center_crop_0.5 | center_crop_0.75 | jpeg_q30 | none |
|:----------:|:----:|:--------------:|:---------------:|:--------:|:----:|
| 0.5 (基线) | 10.22 | 0.500 | 0.661 | 0.998 | 1.000 |
| 0.6 | 9.43 | 0.500 | 0.733 | 0.999 | 1.000 |
| 0.7 | 8.76 | 0.500 | 0.733 | 0.998 | 1.000 |
| 0.8 | 8.21 | 0.500 | 0.733 | 1.000 | 1.000 |
| 0.9 | 7.69 | 0.500 | 0.733 | 1.000 | 1.000 |
| 1.0 | 7.21 | 0.500 | 0.733 | 1.000 | 1.000 |

- `center_crop_0.5` 在所有 ratio 下恒为 0.500（等同于随机猜测），全图嵌入 (ratio=1.0) 也无济于事
- PSNR 从 10.22 线性降至 7.21，纯画质损失无收益
- 瓶颈在检测侧（crop+resize 导致空间失配），不在嵌入侧

**下一步**：转向检测侧优化——多尺度检测、区域重定位解码、bbox 同步解码。
