# 报告素材

## 选题

鲁棒图像水印可用于图像内容的完整性保护、授权验证、篡改定位和来源追踪。工程主线聚焦空间冗余嵌入、强度配置和平台变换鲁棒性，并扩展到来源更新和多源合成图溯源。

## 课程关联

- 密码与认证：水印消息可作为内容认证和归属验证载荷。
- 数据完整性：攻击后提取准确率和局部置信度下降可用于完整性判断。
- 授权与访问控制：二次水印用于再授权、版本更新和来源更新。
- Web 与应用安全：平台压缩、缩放、裁剪和格式转换对应真实传播链路。
- 数据安全技术：多源合成图溯源用于内容来源追踪和证据保全。

## 已实现模块

| 模块 | 实现位置 | 结果目录 |
| --- | --- | --- |
| 基础复现 | `watermark_anything/extensions/baseline_reproduction/run.py` | `results_output/baseline_reproduction` |
| 攻击基准 | `watermark_anything/extensions/attack_benchmark/run.py` | `results_output/attack_benchmark` |
| 空间冗余 | `watermark_anything/extensions/spatial_redundancy/` | `results_output/redundant_regions`, `results_output/distributed_layout`, `results_output/coverage_search` |
| 鲁棒性配置 | `watermark_anything/extensions/robustness_profiles/` | `results_output/strength_search`, `results_output/spatial_strength_profile` |
| 平台变换 | `watermark_anything/extensions/transform_profiles/platform_modes.py` | `results_output/platform_modes` |
| 篡改定位 | `watermark_anything/extensions/tamper_localization/localizer.py` | `results_output/tamper_localization` |
| 来源更新 | `watermark_anything/extensions/provenance_update/pipeline.py` | `results_output/provenance_update` |
| 多源溯源 | `watermark_anything/extensions/source_tracing/` | `results_output/source_tracing`, `results_output/source_tracing_redundant_id`, `results_output/source_tracing_codebook_match` |

## 主要结论

- 基础复现已跑通单水印和多水印推理，关键输出在 `results_output/baseline_reproduction/baseline_reproduction_metrics.csv`。
- 攻击基线显示强 JPEG、极端缩放、强裁剪和局部移除是主要薄弱场景。
- 空间冗余嵌入在强压缩和局部破坏下提供更稳定的恢复机会，但需要控制覆盖面积和视觉质量。
- 覆盖率搜索表明 `Q=30%` 更偏画质，`Q=50%` 更偏鲁棒。
- 强度搜索表明 `scaling_w=2.5` 和 `scaling_w=3.0` 是主要候选档位。
- 平台变换评估形成三档模式：质量优先、均衡鲁棒、安全优先。
- 篡改定位在覆盖区域内效果较好，覆盖外区域需要额外检测机制。
- 来源更新可以保留双消息，但图像质量会下降。
- 多源合成图溯源需要局部裁剪和重同步；码本匹配能提升来源匹配稳定性。

## 推荐主方案

```text
空间冗余嵌入 + 强度配置 + 平台变换评估
```

推荐三档配置：

| 模式 | 覆盖率 | 区域数 | 强度 | 使用场景 |
| --- | --- | --- | --- | --- |
| 质量优先 | 30% | 5 | 2.5 | 画质优先发布 |
| 均衡鲁棒 | 50% | 5 | 2.5 | 常规鲁棒认证 |
| 安全优先 | 50% | 5 | 3.0 | 强压缩和二次传播场景 |

## 证据文件

- `experiment_notes/baseline_reproduction.md`
- `experiment_notes/attack_benchmark.md`
- `experiment_notes/coverage_search.md`
- `experiment_notes/spatial_strength_profile.md`
- `experiment_notes/platform_modes.md`
- `experiment_notes/tamper_localization.md`
- `experiment_notes/provenance_update.md`
- `experiment_notes/source_tracing.md`
- `docs/results_index.md`
