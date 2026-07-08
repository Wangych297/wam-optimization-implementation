# 10 多尺度检测对裁剪鲁棒性的影响

## 目标

实验 09 证实瓶颈在检测侧：crop 后 BICUBIC 插值回 256×256 导致水印信号空间尺度畸变，ViT 提取器的位置编码与失真后的水印模式失配。

本实验在**检测阶段**引入多尺度解码：对攻击后的图像在多个分辨率尺度上分别检测，取置信度最高的结果。核心假设是：crop+resize 改变了水印的有效空间尺度，但其中某个中间尺度恰好能匹配 WAM 提取器的预期输入分布。

## 参考文献

- **Feature Pyramid Networks for Object Detection** (Lin et al., CVPR 2017) — 借鉴多尺度特征金字塔思想，在多个尺度上分别检测再融合，是计算机视觉中处理尺度变化的经典方法
- **Region Synchronization** (本项目中 `region_sync.py`) — 借鉴 bbox 裁剪+重采样解码的思路，本实验将"同步"思想泛化到连续尺度空间
- 实验 09（本报告） — 直接动机：否定嵌入侧优化后，验证检测侧优化是否有效

## 实验设置

- 模型：WAM wam_mit.pth, scaling_w=2.5, mask_ratio=0.5（保持原始设置）
- 扫描参数：scale_factors ∈ [0.5, 0.75, 1.0, 1.25, 1.5]
- 聚合策略：取 mean mask_pred（检测置信度）最高的尺度对应的解码消息
- 攻击：none, center_crop_0.5, center_crop_0.75, random_crop_0.5, jpeg_q30
- 数据：COCO 50
- 实现：`watermark_anything/extensions/multi_scale/multi_scale_decode.py`
- 参数控制：`--use-multi-scale`（默认关，保持原有单尺度行为）

## 运行命令

```bash
# 对照组（默认单尺度）
python watermark_anything/extensions/multi_scale/multi_scale_decode.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/multi_scale/control \
  --limit 50

# 实验组（开启多尺度）
python watermark_anything/extensions/multi_scale/multi_scale_decode.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/multi_scale/experimental \
  --limit 50 \
  --use-multi-scale
```

## 输出

```text
results_output/multi_scale/
├── control/multi_scale_metrics.csv
├── experimental/multi_scale_metrics.csv
└── experimental/multi_scale_summary.csv
```

## 结论 — 强正向

多尺度检测几乎完全解决了中心裁剪问题，50 图和 5000 图结论一致。

### COCO 50 结果

| Attack | Single | Multi | 提升 |
|--------|:------:|:-----:|:----:|
| center_crop_0.5 | 0.500 | **1.000** | +100% |
| center_crop_0.75 | 0.529 | **1.000** | +89% |
| random_crop_0.5 | 0.515 | **0.698** | +36% |
| jpeg_q30 | 0.998 | 0.998 | — |
| none | 1.000 | 1.000 | — |

### COCO 5000 结果

| Attack | Single | Multi | 提升 | 成功率 |
|--------|:------:|:-----:|:----:|:------:|
| center_crop_0.5 | 0.502 | **0.99975** | +99.5% | 99.2% |
| center_crop_0.75 | 0.533 | **1.000** | +87.6% | 100% |
| random_crop_0.5 | 0.511 | **0.701** | +37.2% | 0%（accuracy提升但无perfect match） |
| jpeg_q30 | 0.999 | 0.999 | — | — |
| none | 1.000 | 1.000 | — | — |

### 最优尺度分布（5000 图）

- center_crop_0.5 → **100%** 选择 scale=0.5
- center_crop_0.75 → **100%** 选择 scale=0.75
- random_crop_0.5 → **93.5%** 选择 scale=0.5

**数学规律**：裁剪比例 = 最优检测尺度。已知裁剪量即可精确恢复水印。

### 贡献

这是本项目第一个**强正向结果**，证明了：
1. 裁剪弱点的根因是检测侧的尺度失配，不是嵌入侧的信息不足（实验 09 已排除）
2. 多尺度检测是解决该问题的有效且简单的方法
3. 不需要重新训练模型，纯推理侧优化即可
