# MuST 式多源合成追踪 v1

## 目的

这一轮来自 MuST 的多源图像素材追踪思想：多个带有不同 source ID 的素材被缩放、裁剪、粘贴到同一合成图中后，系统应能从合成图里追踪各素材来源。

本实验不是把攻击列表继续加长，而是验证 WAM-DWSF 是否能扩展到一个更纯正的信息安全场景：多源版权溯源。

## 论文来源

- MuST：multi-source image tracing，核心包含 multi-source detector、minimum external rectangle (MER) 重同步和多素材 ID 提取。
- WAM：localized messages 和多水印能力，可为局部素材嵌入不同 ID。
- DWSF：分散嵌入与覆盖面积权衡。
- MBRS / RoSteALS：消息冗余和 ECC，用短 source ID 牺牲容量换鲁棒性。

## 实验设置

- 主模型：WAM 官方 MIT 权重。
- 环境：`bamboo` conda 环境，RTX 4060 Laptop GPU。
- 原始素材：WAM 官方示例图中选 3 张作为 source materials，`seabackground` 作为背景。
- 合成画布：512x512。
- 素材标准尺寸：256x256。
- 合成场景：
  - `two_sources_downsize`：两个素材缩小粘贴。
  - `three_sources_extreme_downsize`：三个素材更强缩小并裁剪。
  - `three_sources_crop_feather`：三个素材裁剪、增强对比度并羽化边缘。
- 合成后攻击：
  - none
  - JPEG Q70 / Q50
  - resize 0.5 + JPEG Q70
- 解码方法：
  - `global_full_canvas`：整张合成图直接解码。
  - `oracle_box_raw`：用已知素材框裁剪后直接解码。
  - `must_mer_resize`：用已知素材框裁剪后缩放回 256x256 再解码，模拟 MuST 的 MER 重同步。

## 脚本

- 基础多源追踪：`src\wam_optimization/wam_must_composite_tracing.py`
- 8-bit source ID + rep4 冗余：`src\wam_optimization/wam_must_composite_tracing_ecc.py`
- 注册源 ID 最近码字匹配：`src\wam_optimization/wam_must_codebook_match.py`

## 关键结果一：MER 重同步是必要的

在无合成后二次压缩时，`must_mer_resize` 和 `oracle_box_raw` 对所有场景都能把每个 source ID 解到 1.000000；`global_full_canvas` 基本失败。这说明多源合成图不能直接整图混合解码，必须先定位素材区域，再进行局部重同步。

代表性无攻击结果：

| scenario | scheme | global_full_canvas | must_mer_resize |
|---|---|---:|---:|
| two_sources_downsize | dwsf_q50_s2.5 | 0.000000 | 1.000000 |
| three_sources_extreme_downsize | dwsf_q50_s2.5 | 0.395833 | 1.000000 |
| three_sources_crop_feather | dwsf_q50_s2.5 | 0.468750 | 1.000000 |

## 关键结果二：小素材二次压缩下，稀疏 DWSF 不如 full-material source-trace 模式

基础 32-bit 解码的整体 overview：

| scheme | decode_method | mean_source_accuracy | source_success_rate | PSNR |
|---|---|---:|---:|---:|
| full_material_s3.0 | must_mer_resize | 0.626953 | 0.250000 | 39.1471 |
| full_material_s2.5 | must_mer_resize | 0.587891 | 0.250000 | 40.6792 |
| single_center50_s2.5 | must_mer_resize | 0.559570 | 0.250000 | 42.2053 |
| dwsf_q50_s2.5 | must_mer_resize | 0.480469 | 0.250000 | 44.2526 |
| dwsf_q50_s3.0 | must_mer_resize | 0.479492 | 0.250000 | 42.7517 |

判断：当素材会被缩小、裁剪、再压缩时，DWSF 的空间稀疏覆盖会让单个小素材内可用水印证据不足；MuST 场景更适合切换到 full-material 或 single-center 的 source-trace 模式。

## 关键结果三：rep4 ECC 有帮助，但单靠 payload 全恢复仍不够

ECC overview 中，`must_mer_resize` 的 payload success：

| code mode | scheme | payload_success_rate |
|---|---|---:|
| rep4_interleaved_8bit | dwsf_q50_s3.0 | 0.312500 |
| rep4_adjacent_8bit | dwsf_q50_s3.0 | 0.281250 |
| rep4_adjacent_8bit | full_material_s3.0 | 0.250000 |
| rep4_interleaved_8bit | full_material_s3.0 | 0.250000 |

判断：交织冗余能在个别困难场景把 bit accuracy 约 0.71875 的预测恢复成 8-bit source ID 成功，但强压缩/三源极端缩小仍不稳定，不能把 ECC 写成彻底解决方案。

## 关键结果四：注册 codebook 最近码字匹配更符合 source tracing

对 source tracing 来说，查询图通常只需要匹配到注册库中的哪个 source ID，而不一定要求逐位完美恢复。对 ECC 预测消息做最近码字匹配后，结果明显优于 payload 全恢复。

整体 overview：

| code mode | scheme | decode_method | payload_success_rate | codebook_strict_match_rate |
|---|---|---|---:|---:|
| rep4_adjacent_8bit | full_material_s2.5 | oracle_box_raw | 0.250000 | 0.562500 |
| rep4_adjacent_8bit | full_material_s3.0 | oracle_box_raw | 0.250000 | 0.562500 |
| rep4_adjacent_8bit | full_material_s2.5 | must_mer_resize | 0.250000 | 0.531250 |
| rep4_adjacent_8bit | full_material_s3.0 | must_mer_resize | 0.250000 | 0.531250 |
| rep4_adjacent_8bit | single_center50_s2.5 | must_mer_resize | 0.250000 | 0.531250 |
| rep4_adjacent_8bit | dwsf_q50_s3.0 | must_mer_resize | 0.281250 | 0.531250 |

两源缩小场景中，codebook 匹配非常有效：

| code mode | scheme | attack | payload_success_rate | codebook_strict_match_rate |
|---|---|---|---:|---:|
| rep4_adjacent_8bit | full_material_s2.5 | jpeg_q50 | 0.000000 | 1.000000 |
| rep4_adjacent_8bit | full_material_s2.5 | jpeg_q70 | 0.000000 | 1.000000 |
| rep4_adjacent_8bit | full_material_s2.5 | resize_0.5_jpeg70 | 0.000000 | 1.000000 |
| rep4_interleaved_8bit | full_material_s2.5 | resize_0.5_jpeg70 | 0.000000 | 1.000000 |
| rep4_interleaved_8bit | dwsf_q50_s3.0 | jpeg_q70 | 0.500000 | 1.000000 |

## 判断

1. MuST 思路适合作为补充分支：WAM 负责局部水印，MER/box crop 负责重同步，ECC/codebook 负责 source ID 级溯源。
2. 这个分支不能替代主线 DWSF 鲁棒水印方案，因为真实 detector 未训练，这里使用的是 oracle box；三源极端缩小 + 压缩仍不稳。
3. 对最终方案的可用启发是：当应用目标是“合成图素材来源追踪”时，不应默认用 DWSF 稀疏分散模式；更合理的是切换到 full-material/source-trace 覆盖模式，再配合短 ID 冗余和注册 codebook 最近码字匹配。
4. 这个分支的信息安全属性很强，属于版权溯源、身份认证和多源责任追踪，可作为主方案之外的安全应用扩展。

## 输出文件

- `结果输出/wam_must_composite_tracing/wam_must_composite_tracing_metrics.csv`
- `结果输出/wam_must_composite_tracing/wam_must_composite_tracing_summary.csv`
- `结果输出/wam_must_composite_tracing/wam_must_composite_tracing_overview.csv`
- `结果输出/wam_must_composite_tracing_ecc/wam_must_composite_tracing_ecc_metrics.csv`
- `结果输出/wam_must_composite_tracing_ecc/wam_must_composite_tracing_ecc_summary.csv`
- `结果输出/wam_must_composite_tracing_ecc/wam_must_composite_tracing_ecc_overview.csv`
- `结果输出/wam_must_codebook_match/wam_must_codebook_match_metrics.csv`
- `结果输出/wam_must_codebook_match/wam_must_codebook_match_summary.csv`
- `结果输出/wam_must_codebook_match/wam_must_codebook_match_overview.csv`
