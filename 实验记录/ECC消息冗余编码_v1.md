# ECC 消息冗余编码 v1

## 目的

TrustMark 论文提到非完美 bit accuracy 可以通过 error correcting code 改善；MBRS 论文也提出 message processor 来扩展消息并实现冗余。本实验在不改 WAM 网络的前提下，在 32-bit 消息层实现简单的 payload 冗余编码，验证“容量换鲁棒性”是否有效。

为了公平比较，本实验固定有效 payload 为 10 bit：

- `uncoded10`：直接将 10-bit payload 放入 32-bit 消息前 10 位，其余为随机填充。
- `rep3_10`：将每个 payload bit 重复 3 次，占 30 位，剩余 2 位填充；解码时对每组三重复位做多数投票。

## 脚本

- 脚本：`src\wam_optimization/wam_payload_ecc_eval.py`
- 输出目录：`结果输出/wam_payload_ecc/`
- 明细文件：`结果输出/wam_payload_ecc/wam_payload_ecc_metrics.csv`
- 汇总文件：`结果输出/wam_payload_ecc/wam_payload_ecc_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.\original_code\Watermark-Anything'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\src\wam_optimization\wam_payload_ecc_eval.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\结果输出\wam_payload_ecc" `
  --limit 5
```

## 实验设置

- 主方案：`dwsf_5region_spatial`
- 强度：`scaling_w=2.5` 和 `3.0`
- 有效 payload：10 bit
- 攻击：
  - none
  - crop_bottom_right_50
  - crop_center_50
  - JPEG Q=30/20
  - resize 0.25 + JPEG Q=50

## 关键结果

| scaling_w | coding | attack | mean payload acc | payload success rate | mean full bit acc |
|---:|---|---|---:|---:|---:|
| 2.5 | uncoded10 | crop_bottom_right_50 | 0.980000 | 0.800000 | 0.981250 |
| 2.5 | rep3_10 | crop_bottom_right_50 | 1.000000 | 1.000000 | 0.962500 |
| 2.5 | uncoded10 | crop_center_50 | 0.940000 | 0.400000 | 0.975000 |
| 2.5 | rep3_10 | crop_center_50 | 1.000000 | 1.000000 | 0.975000 |
| 2.5 | uncoded10 | resize_0.25_jpeg_q50 | 0.960000 | 0.800000 | 0.937500 |
| 2.5 | rep3_10 | resize_0.25_jpeg_q50 | 1.000000 | 1.000000 | 0.981250 |
| 2.5 | uncoded10 | jpeg_q20 | 0.840000 | 0.600000 | 0.850000 |
| 2.5 | rep3_10 | jpeg_q20 | 0.820000 | 0.600000 | 0.837500 |
| 3.0 | uncoded10 | crop_center_50 | 0.940000 | 0.400000 | 0.975000 |
| 3.0 | rep3_10 | crop_center_50 | 1.000000 | 1.000000 | 0.962500 |
| 3.0 | uncoded10 | resize_0.25_jpeg_q50 | 0.960000 | 0.800000 | 0.962500 |
| 3.0 | rep3_10 | resize_0.25_jpeg_q50 | 1.000000 | 1.000000 | 0.981250 |
| 3.0 | uncoded10 | jpeg_q20 | 0.900000 | 0.800000 | 0.881250 |
| 3.0 | rep3_10 | jpeg_q20 | 0.880000 | 0.800000 | 0.893750 |

## 结论

ECC 消息冗余是有价值的附加创新，但不是无条件提升。

正向部分：

- 对裁剪和 resize+JPEG，`rep3_10` 显著提升 payload 成功率。
- `scaling_w=2.5` 下，`crop_center_50` 从 0.4 成功率提升到 1.0，`resize_0.25_jpeg_q50` 从 0.8 提升到 1.0。
- 即使 full 32-bit message 有若干错误，重复编码多数投票仍可恢复 10-bit payload。

负向部分：

- 对 JPEG Q=20，`rep3_10` 没有稳定提升，payload accuracy 甚至略低于 uncoded10。这说明强 JPEG 错误可能呈现成组偏差，不一定满足独立随机错误假设。
- 代价是容量下降：有效 payload 从 10 bit 直接编码仍为 10 bit，但占用 30 个 WAM bit，不能用于高容量水印。

后续判断：

- 可以作为报告中的附加改进：主方案是 DWSF 空间分散 + TrustMark 强度权衡，消息层再提供可选 ECC 模式。
- 写作时应强调容量-鲁棒性权衡，不要把它说成免费提升。
