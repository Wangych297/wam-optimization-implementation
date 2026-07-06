# 结果输出

本目录按实验模块保存生成的指标、汇总表和部分可视化结果。目录名与 `watermark_anything/extensions/` 中的功能模块保持对应，便于从代码定位到结果。

| 结果目录 | 内容 |
| --- | --- |
| `baseline_reproduction/` | 基础嵌入、提取和多水印推理结果。 |
| `attack_benchmark/` | 压缩、缩放、裁剪、局部移除等攻击基准结果。 |
| `redundant_regions/` | 空间冗余嵌入结果。 |
| `distributed_layout/` | 分布式区域布局结果。 |
| `coverage_search/` | 不同覆盖率和区域数量的搜索结果。 |
| `region_sync/` | 区域同步解码结果。 |
| `strength_search/` | 不同水印强度的指标对比。 |
| `spatial_strength_profile/` | 空间区域和强度组合结果。 |
| `platform_modes/` | 平台传播变换模式评估结果。 |
| `compression_recovery/` | 压缩恢复和多分支解码结果。 |
| `repetition_payload/` | 重复载荷策略结果。 |
| `coding_variants/` | 载荷编码变体结果。 |
| `adaptive_selector/` | 自适应区域选择结果。 |
| `tamper_localization/` | 篡改定位指标和可视化结果。 |
| `provenance_update/` | 来源更新和二次水印结果。 |
| `source_tracing/` | 多源合成图溯源结果。 |
| `source_tracing_redundant_id/` | 冗余身份编码溯源结果。 |
| `source_tracing_codebook_match/` | 码本匹配溯源结果。 |

常见输出格式包括 `.csv`、`.json`、`.png` 和水印图像文件。报告中需要引用的结论统一整理在 `docs/report_materials.md`。
