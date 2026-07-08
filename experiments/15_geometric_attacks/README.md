# 15 几何攻击鲁棒性评估

## 目标

WAM 在多尺度+ECC 优化后已能应对压缩、裁剪、缩放等攻击，但几何变换（旋转、翻转）尚未评估。本实验系统测试 WAM 在常见几何攻击下的表现，并验证多尺度检测是否能提供几何不变性。

## 参考文献

- **GResMark: Swin Transformer with Locally-enhanced Channel Attention** (ESWA 2025) — 几何失真免疫水印框架，Swin+DCN，旋转攻击准确率 >98%
- **A Geometric Distortion Immunized Deep Watermarking Framework** (ECCV 2024) — Swin+可变形卷积，几何攻击下提取率 100%

## 实验设置

- 模型：WAM wam_mit.pth, scaling_w=2.5, mask_ratio=0.5
- 攻击：旋转 15°/30°/45°/90°/180°，水平/垂直翻转，旋转45°+中心裁剪50%
- 对比：单尺度 vs 多尺度检测
- 数据：COCO 50
- 实现：`watermark_anything/extensions/utilities/geometric_attacks.py`（`--use-multi-scale` 参数）

## 运行命令

```bash
# 单尺度
python watermark_anything/extensions/utilities/geometric_attacks.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/geometric/single \
  --limit 50

# 多尺度
python watermark_anything/extensions/utilities/geometric_attacks.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/geometric/multi \
  --limit 50 --use-multi-scale
```

## 结论 — 强负向

| 攻击 | 单尺度 mean | 多尺度 mean |
|------|:----------:|:----------:|
| none | 0.999 | 0.999 |
| flip_h | 0.646 | 0.646 |
| flip_v | 0.509 | 0.518 |
| rotate_15 | 0.539 | 0.557 |
| rotate_30 | 0.499 | 0.502 |
| rotate_45 | 0.483 | 0.540 |
| rotate_90 | 0.494 | 0.506 |
| rotate_180 | 0.546 | 0.622 |
| rotate_45_crop_50 | 0.478 | 0.507 |

1. WAM 对几何变换**完全不具备鲁棒性**，所有旋转/翻转 accuracy 在 0.48-0.65 之间
2. 多尺度检测**无法**提供几何不变性（单尺度和多尺度几乎一致）
3. 根因：ViT 骨干未针对旋转不变性训练，纯推理侧无法解决
4. 需重新训练（引入旋转增强或 Swin+可变形卷积架构）
