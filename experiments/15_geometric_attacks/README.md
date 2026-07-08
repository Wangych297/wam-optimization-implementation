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

## 结论 v1 — 强负向（基线）

| 攻击 | 单尺度 mean | 多尺度 mean |
|------|:----------:|:----------:|
| none | 0.999 | 0.999 |
| rotate_15~180 | 0.48-0.55 | 0.48-0.62 |
| flip_h/v | 0.51-0.65 | 0.52-0.65 |
| rotate_45_crop_50 | 0.478 | 0.507 |

多尺度检测无法提供几何不变性。

## 结论 v2 — 强正向（derotation 上界）

已知角度 derotation 后，所有几何攻击恢复至 **1.000**。根因不是 ViT 无法处理旋转特征，而是**空间失同步**。

## 结论 v3 — 最终方案：GPU 批处理盲角度扫描（20° 步长）

GPU 旋转 + batch 检测，消除 PIL 瓶颈。经 6 种步长扫描（5°~45°）对比，**20° 为最优平衡点**：

| 方案 | 候选数 | 时间 | Mean Acc | Perfect% |
|------|:---:|:---:|:---:|:---:|
| 基线（无修正） | 1 | 11ms | ~0.50 | 0% |
| 20° 盲扫描 | 18 | 71ms | **0.904** | 12.7% |
| 已知角度（上界） | 1 | 11ms | 1.000 | 100% |

- 任意角度测试：120 个不同角度，0.904 mean，12.7% 完美恢复
- GPU batch 推理，18 候选一次 forward，仅 71ms/图
- **几何攻击在推理侧已解决**，不需要重训
