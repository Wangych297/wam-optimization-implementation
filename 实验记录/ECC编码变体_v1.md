# ECC 编码变体 v1

## 目的

上一轮 ECC 只比较了 uncoded10 与 rep3_10，结果显示重复编码能显著提升部分裁剪和 resize+JPEG 的 payload 成功率，但对强 JPEG Q=20 不稳定。本轮进一步比较多种轻量纠错/交织方案，判断是否存在更适合默认 `DWSF Q=30%, 5 blocks` 方案的 payload 编码。

## 论文来源

- RoSteALS：报告 Bit acc. (ECC)，使用 BCH/cyclic error correction code，说明纠错码能显著改善部分 noised data 的 secret recovery。
- MBRS：message processor 用于扩展 message 并实现冗余。
- TrustMark：真实使用场景是 provenance payload，需要关注 payload 级恢复，而不仅是 full bit accuracy。

## 实验设置

- 脚本：`脚本草稿/wam_payload_ecc_variants.py`。
- 输出：`结果输出/wam_payload_ecc_variants/`。
- 主模型：WAM 官方 MIT 权重。
- 主方案：`DWSF Q=30%, 5 blocks, scaling_w=2.5`。
- 图像：WAM 官方 5 张示例图。
- payload：固定随机 10-bit payload。
- coding：
  - `uncoded10`
  - `rep3_adjacent10`
  - `rep3_interleaved10`
  - `hamming74_10`
  - `hamming74_interleaved10`
- 攻击：
  - none
  - crop_bottom_right_50
  - crop_center_50
  - jpeg_q30
  - jpeg_q20
  - resize_0.25_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  脚本草稿\wam_payload_ecc_variants.py `
  --wam-root C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything `
  --checkpoint C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything\checkpoints\wam_mit.pth `
  --params C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything\checkpoints\params.json `
  --image-dir C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything\assets\images `
  --out-dir 结果输出\wam_payload_ecc_variants `
  --limit 5 `
  --scale 2.5 `
  --area 30 `
  --block-count 5
```

## 关键结果

总计 150 条逐图逐攻击记录，stderr 为空。

overview：

| coding | mean selected payload success | worst selected payload success |
|---|---:|---:|
| rep3_interleaved10 | 0.760000 | 0.400000 |
| uncoded10 | 0.760000 | 0.400000 |
| rep3_adjacent10 | 0.760000 | 0.600000 |
| hamming74_10 | 0.760000 | 0.600000 |
| hamming74_interleaved10 | 0.760000 | 0.600000 |

逐攻击 success rate：

| attack | uncoded10 | rep3_adjacent10 | rep3_interleaved10 | hamming74_10 | hamming74_interleaved10 |
|---|---:|---:|---:|---:|---:|
| crop_bottom_right_50 | 0.400000 | 0.600000 | 0.800000 | 0.600000 | 0.600000 |
| crop_center_50 | 1.000000 | 1.000000 | 1.000000 | 0.800000 | 1.000000 |
| jpeg_q30 | 0.800000 | 0.800000 | 0.800000 | 0.800000 | 0.800000 |
| jpeg_q20 | 0.600000 | 0.600000 | 0.400000 | 0.600000 | 0.600000 |
| resize_0.25_jpeg_q50 | 1.000000 | 0.800000 | 0.800000 | 1.000000 | 0.800000 |

## 判断

这轮没有产生新的主线级改进。

1. 五种编码的 mean selected payload success 都是 0.760000，说明在 `Q=30%` 默认方案下，轻量 ECC 不能显著提升整体 payload 成功率。
2. `rep3_adjacent10`、`hamming74_10`、`hamming74_interleaved10` 能把 worst selected payload success 从 0.400000 提升到 0.600000，说明它们能降低最差攻击下的风险。
3. `rep3_interleaved10` 对 `crop_bottom_right_50` 最好，success 0.800000，但对 `jpeg_q20` 降到 0.400000，不稳定。
4. `hamming74_10` 在 `resize_0.25_jpeg_q50` 保持 1.000000，且 `jpeg_q20` 不比 uncoded 差；如果要保留一个“轻量 ECC 可选模式”，它比交织重复更稳。
5. 该结果与上一轮 `Q=50%` 下 rep3 明显提升不同，说明 ECC 的效果依赖底层嵌入强度/面积。默认 `Q=30%` 更偏低扰动，强 JPEG 错误可能超过轻量码纠错能力。

## 保留价值

- 不建议把 ECC 变体作为最终主创新。
- 可作为可选模块：默认方案使用 `Q=30%, 5 blocks`，若用户更关心 payload 最差成功率，可加 `hamming74_10`，代价是有效载荷容量下降到 10 bit。
- 报告里可以将它写成“来自 MBRS/RoSteALS 的消息冗余探索，实验证明只能稳住最差情况，不能根本解决强 JPEG”。

## 输出文件

- `结果输出/wam_payload_ecc_variants/wam_payload_ecc_variants_metrics.csv`
- `结果输出/wam_payload_ecc_variants/wam_payload_ecc_variants_summary.csv`
- `结果输出/wam_payload_ecc_variants/wam_payload_ecc_variants_overview.csv`
