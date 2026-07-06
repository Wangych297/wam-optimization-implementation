# 08 辅助模块

## 目标

本实验目录集中运行几组辅助创新模块。这些模块不一定单独作为主线方案，但它们分别针对压缩恢复、载荷可靠性、区域选择和区域同步等关键问题提供补强能力。

## 创新设计

辅助模块的共同目标是提高系统在复杂场景中的可用性，而不是只追求干净图像上的提取成功率。

包含的方向如下：

- 压缩恢复：面对强压缩后的图像，不只使用单一路径解码，而是尝试多分支恢复策略。
- 重复载荷：把重要消息以重复方式分散写入，提高局部损坏后的恢复机会。
- 编码变体：比较不同载荷组织方式，观察短消息、重复消息和结构化消息的差异。
- 自适应区域选择：根据图像内容选择更适合嵌入的区域，避免把水印写到过于平坦或容易被破坏的位置。
- 区域同步：在裁剪、缩放或局部破坏后重新寻找可用区域，提高多区域方案的可解码性。

## 工程实现

本目录的 `run.ps1` 会依次运行多个模块，输出分别写入对应结果目录。它适合在主线实验完成后做补充验证，判断哪些辅助能力可以并入最终方案。

## 结果解读

重点不是看每个辅助模块是否都超过主线，而是判断它们在哪些场景下有价值：

- 如果压缩恢复在强 JPEG 下提升明显，可以作为平台传播场景的补充。
- 如果重复载荷在裁剪后更稳定，可以和空间冗余组合。
- 如果自适应选择能减少画质损伤，可以用于质量优先配置。
- 如果区域同步提升裁剪后的恢复率，可以作为多区域方案的必要组件。

## 实现位置

```text
watermark_anything/extensions/compression_recovery/multi_branch_decode.py
watermark_anything/extensions/payload_coding/repetition_payload.py
watermark_anything/extensions/payload_coding/coding_variants.py
watermark_anything/extensions/region_selection/adaptive_selector.py
watermark_anything/extensions/spatial_redundancy/region_sync.py
```

## 输出目录

```text
results_output/compression_recovery
results_output/repetition_payload
results_output/coding_variants
results_output/adaptive_selector
results_output/region_sync
```

## 运行方式

```powershell
.\experiments\08_auxiliary_modules\run.ps1
```
