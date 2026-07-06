# 结果索引

## 主线实验

| 方向 | 输出目录 | 目的 |
| --- | --- | --- |
| 基础复现 | `results_output/baseline_reproduction` | 跑通基础嵌入和提取流程 |
| 攻击基准评测 | `results_output/attack_benchmark` | 建立 JPEG、resize、crop 等攻击下的基线 |
| 空间冗余嵌入 | `results_output/redundant_regions` | 比较单区域和多区域冗余的鲁棒性 |
| 空间布局分散 | `results_output/distributed_layout` | 测试固定多区域布局 |
| 覆盖率搜索 | `results_output/coverage_search` | 扫描覆盖面积和区域数量 |
| 强度搜索 | `results_output/strength_search` | 搜索嵌入强度与画质的取舍 |
| 空间-强度组合 | `results_output/spatial_strength_profile` | 组合多区域嵌入和强度调节 |
| 平台变换模式 | `results_output/platform_modes` | 评估常见平台编辑变换下的推荐模式 |
| 篡改定位 | `results_output/tamper_localization` | 定位被主动移除或破坏的区域 |
| 来源更新 | `results_output/provenance_update` | 测试再授权、分区覆盖和信息保留 |
| 多源素材溯源 | `results_output/source_tracing` | 在合成图中定位并恢复不同来源信息 |
| 冗余 ID 溯源 | `results_output/source_tracing_redundant_id` | 用短 ID 冗余增强多源溯源 |
| 码本匹配溯源 | `results_output/source_tracing_codebook_match` | 用注册码本提升来源匹配 |

## 辅助实验

| 方向 | 输出目录 | 目的 |
| --- | --- | --- |
| 压缩恢复 | `results_output/compression_recovery` | 测试 JPEG 压缩后的多分支候选恢复 |
| 重复载荷 | `results_output/repetition_payload` | 测试重复编码能否提升载荷恢复 |
| 编码变体 | `results_output/coding_variants` | 比较不同冗余编码方式 |
| 自适应区域选择 | `results_output/adaptive_selector` | 测试按图像内容选择嵌入区域 |
| 区域同步 | `results_output/region_sync` | 测试裁剪后区域重同步解码 |
