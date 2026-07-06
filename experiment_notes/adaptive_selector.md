# 自适应区域选择 v1

## 目的

这轮尝试把 DWSF 的分散嵌入与 OmniGuard/WAM/TrustMark 中的感知质量思想结合：不再固定四角 + 中心，而是在同样 `Q=30%, 5 blocks, scaling_w=2.5` 条件下，根据图像内容选择水印区域。

要验证的问题是：内容自适应选择是否能在保持 DWSF 鲁棒性的同时进一步改善画质，或者改善某些裁剪/压缩攻击。

## 论文来源

- DWSF：分散嵌入、稀疏块、同一消息重复嵌入。
- OmniGuard：localized watermark 可以通过 content-aware texture 改善隐藏质量。
- WAM：JND / HVS 思想强调亮度与对比度掩蔽，高纹理区域对扰动更不敏感。
- TrustMark：强调 watermark quality 与 recovery 的权衡。

## 实验设置

- 脚本：`watermark_anything\extensions\region_selection/adaptive_selector.py`。
- 输出：`results_output/adaptive_selector/`。
- 主模型：WAM 官方 MIT 权重。
- 图像：WAM 官方 5 张示例图。
- 水印：固定随机 32-bit 消息。
- 固定变量：
  - `Q=30%`
  - `5 blocks`
  - `scaling_w=2.5`
- selector：
  - `fixed_anchor`：固定四角 + 中心。
  - `random`：从候选网格随机选择不重叠块。
  - `texture_top`：选择局部梯度/纹理最高的块。
  - `low_residual`：先生成全图水印，选择水印残差 MSE 最低的块。
  - `hybrid_texture_residual`：纹理高 + 残差低的加权组合。
- 攻击：
  - none
  - remove_center_40
  - black_center_40
  - crop_top_left_50
  - crop_bottom_right_50
  - crop_center_50
  - jpeg_q30
  - jpeg_q20
  - resize_0.25_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\region_selection/adaptive_selector.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\adaptive_selector `
  --limit 5 `
  --scale 2.5 `
  --area 30 `
  --block-count 5 `
  --grid 11
```

## 关键结果

总计 225 条逐图逐攻击记录，stderr 为空。

overview：

| scheme | selector | PSNR | selected attack mean | worst selected attack |
|---|---|---:|---:|---:|
| adaptive_q30_5block_hybrid_texture_residual | hybrid_texture_residual | 41.0139 | 0.948438 | 0.881250 |
| fixed_q30_5block | fixed_anchor | 42.0139 | 0.945312 | 0.906250 |
| adaptive_q30_5block_texture_top | texture_top | 40.1578 | 0.935937 | 0.731250 |
| adaptive_q30_5block_random | random | 41.5479 | 0.912500 | 0.706250 |
| adaptive_q30_5block_low_residual | low_residual | 43.6530 | 0.890625 | 0.675000 |

细项：

| attack | fixed_anchor | hybrid_texture_residual | low_residual | texture_top |
|---|---:|---:|---:|---:|
| crop_top_left_50 | 0.906250 | 0.925000 | 0.925000 | 0.956250 |
| crop_bottom_right_50 | 0.956250 | 0.950000 | 0.943750 | 0.981250 |
| crop_center_50 | 0.931250 | 0.968750 | 0.868750 | 0.950000 |
| jpeg_q20 | 0.906250 | 0.881250 | 0.675000 | 0.731250 |
| resize_0.25_jpeg_q50 | 0.950000 | 0.943750 | 0.900000 | 0.937500 |

## 判断

这轮不能作为最终主创新。

1. `hybrid_texture_residual` 的平均攻击准确率 0.948438 略高于固定布局 0.945312，但 PSNR 从 42.0139 降到 41.0139，worst selected attack 从 0.906250 降到 0.881250。收益太小，代价更明显。
2. `low_residual` 确实把 PSNR 提到 43.6530，但强 JPEG 与 resize+JPEG 明显退化，selected attack mean 只有 0.890625。说明只按残差最小选区域会选到水印信号弱、解码不稳的位置。
3. `texture_top` 对部分裁剪有帮助，但强 JPEG 崩得更明显，PSNR 也不如固定布局。
4. `random` 不稳定，作为 DWSF 原始思想的随机性参考可以保留，但不适合当默认策略。

## 保留价值

- 这是一轮有效的负结果：简单内容自适应区域选择不应替代当前 `Q=30%, 5 blocks` 固定布局。
- 可以在报告中作为“尝试过但淘汰”的创新探索，说明我们不是只挑好结果。
- 如果后续还有时间，可进一步做更严格的 perceptual metric 或训练式选择器；但在当前课程大作业范围内，不建议继续深挖这个分支。

## 输出文件

- `results_output/adaptive_selector/adaptive_selector_metrics.csv`
- `results_output/adaptive_selector/adaptive_selector_regions.csv`
- `results_output/adaptive_selector/adaptive_selector_summary.csv`
- `results_output/adaptive_selector/adaptive_selector_overview.csv`
