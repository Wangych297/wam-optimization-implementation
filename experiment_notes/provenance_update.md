# 二次水印空间分区 v1

## 目的

这轮来自 TrustMark 的 re-watermarking / provenance update 场景，以及 WAM 的 multiple watermark extraction 能力。目标是验证：当一张图已经带有旧版权/来源消息 A 时，后续需要追加新来源消息 B，DWSF 式空间分区是否比直接覆盖同一区域更能保留新旧两条消息。

## 论文来源

- TrustMark：讨论 provenance metadata 更新、re-watermarking，以及直接重复加水印会带来质量与水印生命周期问题。
- WAM：支持同一图像中的多个 localized watermark，并用 mask/DBSCAN/局部解码提取多个消息。
- DWSF：分散块提供天然的空间分区载体，可把不同消息放在不同块组中，减少互相覆盖。

## 实验设置

- 脚本：`watermark_anything\extensions\provenance_update/provenance_update.py`。
- 输出：`results_output/provenance_update/`。
- 主模型：WAM 官方 MIT 权重。
- 图像：WAM 官方 5 张示例图。
- 强度：`scaling_w=2.5`。
- 消息：
  - 旧消息 `msg_a`
  - 新消息 `msg_b`
- 方案：
  - `overlap_replace_same_region`：A 先放入 `Q=30%, 5 blocks`，B 再覆盖同一组区域。
  - `disjoint_append_side_regions`：A 放入 `Q=30%, 5 blocks`，B 追加到不重叠的四个 side-mid 区域，总新增面积约 24%。
- 解码：
  - 为避免 WAM 官方 DBSCAN 在大候选像素下过慢，使用已知 slot mask 做局部解码。
  - overlap 方案 A/B 槽位相同；disjoint 方案 A/B 槽位不同。
- 攻击：
  - none
  - jpeg_q50
  - resize_0.5_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\provenance_update/provenance_update.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\provenance_update `
  --limit 5 `
  --scale 2.5
```

## 关键结果

总计 30 条逐图逐攻击记录，stderr 为空。

overview：

| scheme | mean A accuracy | mean B accuracy | both success rate | PSNR |
|---|---:|---:|---:|---:|
| disjoint_append_side_regions | 0.966667 | 0.952083 | 0.800000 | 39.0893 |
| overlap_replace_same_region | 0.522917 | 0.958333 | 0.000000 | 42.0668 |

逐攻击：

| scheme | attack | A accuracy | B accuracy | both success |
|---|---|---:|---:|---:|
| disjoint_append_side_regions | none | 1.000000 | 1.000000 | 1.000000 |
| disjoint_append_side_regions | jpeg_q50 | 0.950000 | 0.925000 | 0.600000 |
| disjoint_append_side_regions | resize_0.5_jpeg_q50 | 0.950000 | 0.931250 | 0.800000 |
| overlap_replace_same_region | none | 0.531250 | 1.000000 | 0.000000 |
| overlap_replace_same_region | jpeg_q50 | 0.518750 | 0.950000 | 0.000000 |
| overlap_replace_same_region | resize_0.5_jpeg_q50 | 0.518750 | 0.925000 | 0.000000 |

## 判断

这轮是可保留的安全场景分支。

1. 同区域覆盖更新会保留新消息 B，但旧消息 A 基本被覆盖掉；both success 始终为 0。
2. 空间分区追加可以同时保留 A/B：无攻击下 both success 为 1.0，JPEG Q=50 下为 0.6，resize+JPEG 下为 0.8。
3. 空间分区的代价是更大水印面积，PSNR 从 overlap 的 42.0668 降到 39.0893。
4. 这个分支不适合作为默认低扰动方案，但适合作为 provenance update / 多阶段授权 / 多方溯源的安全优先模式。

## 保留价值

- 与信息安全课程中的认证、溯源和完整性管理相关。
- 可以作为 WAM+DWSF 主方案的第二个附加创新：不只鲁棒恢复单一版权消息，还支持空间隔离的多消息生命周期管理。
- 报告中必须写清楚代价：为了保留多条消息，需要牺牲 PSNR 和可用嵌入面积。

## 输出文件

- `results_output/provenance_update/provenance_update_metrics.csv`
- `results_output/provenance_update/provenance_update_summary.csv`
- `results_output/provenance_update/provenance_update_overview.csv`
