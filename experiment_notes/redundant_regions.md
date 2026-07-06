# DWSF 式多区域冗余融合 v1

## 来源论文思想

来源：DWSF（Practical Deep Dispersed Watermarking with Synchronization and Fusion）。

DWSF 的核心思想包括：

- 将同一水印消息分散嵌入多个区域，避免单一区域被裁剪或破坏后无法恢复。
- 检测/定位水印区域后再解码。
- 对多个区域的解码结果进行融合，提高最终消息恢复可靠性。

## 实现方案

本轮实现了一个 WAM 上的 DWSF-style 原型：

- baseline：单区域 WAM，随机 50% 区域嵌入一条 32-bit 消息。
- dwsf_redundant_regions：5 个随机不重叠区域，每个区域 10%，重复嵌入同一条 32-bit 消息，总水印面积约等于 baseline。
- 解码方式：
  - `global_mask_average`：WAM 原始全局 mask 平均解码。
  - `component_majority`：对预测水印 mask 做连通区域分割，每个组件独立解码后多数投票。
  - `component_confidence_weighted`：对组件解码结果按置信度和组件像素数加权融合。

脚本：`watermark_anything\extensions\spatial_redundancy/redundant_regions.py`

输出：

- `results_output\redundant_regions\redundant_regions_metrics.csv`
- `results_output\redundant_regions\redundant_regions_summary.csv`

## 实验结果概述

本轮结果是混合的，不能直接包装成成功改进。

主要观察：

- 无攻击、轻度 resize、轻中度裁剪、遮挡、partial removal 下，baseline 和 DWSF 冗余方案大多都能达到 1.0。
- `random_crop_0.5` 下，DWSF 冗余方案的最低 bit accuracy 从 baseline 的 0.9375 提升到 0.96875，但平均值略低。
- `jpeg_q30` 下，DWSF 冗余全局解码最低值从 0.71875 提升到 0.75，但平均值基本不变；组件置信融合反而退化。
- JPEG Q=50、Q=65 和强中心裁剪下，多区域方案出现明显退化。

## 失败/不足分析

第一版方案没有稳定提升，原因可能是：

- 每个冗余区域只有 10%，比 baseline 的 50% 单区域可用像素少，强 JPEG 下单区域信号更弱。
- WAM 的 detection mask 本身已经会在像素级聚合信息，组件级拆分反而可能丢失全局统计优势。
- 当前攻击集里很多攻击并不会“定点摧毁一个大区域”，baseline 的 50% 单区域也能幸存，因此 DWSF 的分散优势没有充分体现。
- DWSF 的同步/融合思想更适合裁剪、局部破坏、区域丢失这类场景，而不是所有攻击通吃。

## 下一步修正方向

不要把 v1 作为最终创新。下一步继续围绕 DWSF 思想做更贴合场景的实验：

1. 构造更强的局部破坏攻击，例如 40%/60% 的局部遮挡、局部水印移除、corner crop。
2. 比较单大区域 vs 多分散区域在“局部大块破坏”下的消息存活率。
3. 尝试规则化区域布局，例如网格/四角+中心，而不是完全随机区域，增强空间分散性。
4. 保留 `global_mask_average` 作为主要解码方式，组件融合只作为消融，不强行作为最佳方案。

## 当前结论

DWSF 式多区域冗余在 WAM 上有可实现性，但 v1 方案不是稳定正向改进。它暴露了一个重要事实：多区域冗余要在“局部区域丢失/破坏”场景下验证，而不是指望它无条件提升 JPEG 或所有几何攻击。后续需要重做更贴合 DWSF 适用场景的 v2。
