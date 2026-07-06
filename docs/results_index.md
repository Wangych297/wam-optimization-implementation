# Results Index

## 主线结果

| 方向 | 输出目录 | 结论 |
|---|---|---|
| WAM 官方复现 | `结果输出/wam_official_repro` | 官方推理流程跑通，单水印和多水印均可恢复 |
| WAM 攻击基线 | `结果输出/wam_attack_eval` | 弱点集中在强 JPEG、极端 resize、强裁剪 |
| DWSF 面积扫描 | `结果输出/wam_dwsf_area_sweep` | Q=30% 质量优先，Q=50% 鲁棒优先 |
| TrustMark 强度扫描 | `结果输出/wam_trustmark_strength` | scaling_w=2.5/3.0 是鲁棒增强候选 |
| DWSF+强度组合 | `结果输出/wam_combined_dwsf_strength` | 多区域+强度权衡构成主创新 |
| 平台变换模式选择 | `结果输出/wam_practical_transform_modes` | 得到三档最终推荐模式 |

## 附加分支

| 方向 | 输出目录 | 结论 |
|---|---|---|
| 主动篡改定位 | `结果输出/wam_tamper_localization` | 覆盖区域内定位效果好，覆盖外无能为力 |
| 二次水印 | `结果输出/wam_rewatermarking` | 非重叠分区能保留双消息，但 PSNR 降低 |
| MuST 多源追踪 | `结果输出/wam_must_composite_tracing` | MER 重同步必要；复杂压缩场景不稳 |
| MuST + ECC | `结果输出/wam_must_composite_tracing_ecc` | 短 ID 冗余有帮助但不充分 |
| Codebook 匹配 | `结果输出/wam_must_codebook_match` | 两源缩小场景可显著提升 source tracing |

## 探索和负结果

| 方向 | 输出目录 | 结论 |
|---|---|---|
| MBRS 多分支 JPEG | `结果输出/wam_mbrs_multibranch` | 有小幅提升，不够稳定 |
| ECC 变体 | `结果输出/wam_payload_ecc_variants` | 改善最差情况，不能根治强 JPEG |
| 自适应区域选择 | `结果输出/wam_adaptive_region_select` | 不如固定 DWSF 区域稳定 |
| bbox 同步解码 | `结果输出/wam_dwsf_bbox_sync` | 小幅改善，不解决裁剪同步问题 |
