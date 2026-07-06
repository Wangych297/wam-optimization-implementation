# WAM 攻击评测基线

## 目标

在 WAM 官方流程跑通后，构建一套后续改进实验可复用的攻击评测基线，用来衡量原始 WAM 在不同失真/攻击下的消息恢复能力。

## 实验设置

- 主论文模型：WAM / Watermark Anything
- 权重：`wam_mit.pth`
- 环境：`bamboo`，RTX 4060 Laptop GPU
- 测试图像：官方 `assets/images` 中 5 张示例图
- 嵌入方式：单条 32-bit 消息，随机 50% 区域保留水印
- 固定消息：

```text
01001001101000111101110000000011
```

## 攻击类型

本轮攻击评测包含：

- no attack
- JPEG：Q=95/85/75/65/50/30
- Resize：0.75/0.5/0.25 后恢复原分辨率
- Center crop：0.9/0.75/0.5 后恢复原分辨率
- Random crop：0.9/0.75/0.5 后恢复原分辨率
- Local occlusion：遮挡 5%/10%/20% 面积
- Partial removal：将 5%/10%/20% 区域替换回原图内容，模拟局部水印移除

## 输出文件

- 评测脚本：`watermark_anything\extensions\attack_benchmark/run.py`
- 逐样本指标：`results_output\attack_benchmark\attack_benchmark_metrics.csv`
- 按攻击汇总：`results_output\attack_benchmark\attack_benchmark_summary.csv`
- 本地可视化目录：`results_output\attack_benchmark\visuals`

说明：批量攻击可视化 PNG 文件体积较大，仅本地保留，不全部提交到 git。后续需要报告配图时再挑选代表样例压缩整理。

## 汇总结果

| 攻击 | 平均 bit accuracy | 最低 bit accuracy | 图像数 |
|---|---:|---:|---:|
| none | 1.000000 | 1.000000 | 5 |
| jpeg_q95 | 1.000000 | 1.000000 | 5 |
| jpeg_q85 | 0.993750 | 0.968750 | 5 |
| jpeg_q75 | 0.987500 | 0.937500 | 5 |
| jpeg_q65 | 0.993750 | 0.968750 | 5 |
| jpeg_q50 | 0.968750 | 0.875000 | 5 |
| jpeg_q30 | 0.925000 | 0.781250 | 5 |
| resize_0.75 | 1.000000 | 1.000000 | 5 |
| resize_0.5 | 1.000000 | 1.000000 | 5 |
| resize_0.25 | 0.962500 | 0.812500 | 5 |
| center_crop_0.9 | 1.000000 | 1.000000 | 5 |
| center_crop_0.75 | 1.000000 | 1.000000 | 5 |
| center_crop_0.5 | 0.950000 | 0.906250 | 5 |
| random_crop_0.9 | 1.000000 | 1.000000 | 5 |
| random_crop_0.75 | 1.000000 | 1.000000 | 5 |
| random_crop_0.5 | 0.987500 | 0.968750 | 5 |
| occlusion_0.05 | 1.000000 | 1.000000 | 5 |
| occlusion_0.1 | 1.000000 | 1.000000 | 5 |
| occlusion_0.2 | 1.000000 | 1.000000 | 5 |
| partial_removal_0.05 | 1.000000 | 1.000000 | 5 |
| partial_removal_0.1 | 1.000000 | 1.000000 | 5 |
| partial_removal_0.2 | 1.000000 | 1.000000 | 5 |

## 暴露出的弱点

当前 WAM baseline 的主要弱点集中在：

- 强 JPEG 压缩：`jpeg_q30` 平均 0.925，最低 0.78125。
- 极端 resize：`resize_0.25` 平均 0.9625，最低 0.8125。
- 强中心裁剪：`center_crop_0.5` 平均 0.95，最低 0.90625。
- 个别图像在 JPEG Q=50/75/85 也会出现少量 bit 错误。

这说明后续改进应重点关注：

- MBRS 式 JPEG 鲁棒增强或多次解码策略。
- DWSF 式多区域冗余嵌入与融合，用来提升裁剪、极端缩放和局部破坏后的恢复率。
- TrustMark 式水印强度与图像质量权衡，观察是否能在不明显牺牲 PSNR 的情况下提升强攻击恢复率。

## 当前结论

WAM baseline 已经具备较强基础鲁棒性，但在强 JPEG、极端缩放、强裁剪下仍有可优化空间。这些弱点与 DWSF、MBRS、TrustMark 等论文的思想可以自然衔接，适合作为后续创新优化的目标。
