# DWSF 面积比例扫描 v1

## 目的

这轮不是另起炉灶，而是回到 DWSF 论文中明确讨论过的变量：分散嵌入的总面积比例 Q 和块数上限。DWSF 主论文设置为 Q=25%、最多 20 个块，并在附录中说明更大的 Q 通常带来更高 bit accuracy，但会降低 PSNR；Q 太小则在强几何攻击下鲁棒性不足。

我们之前的 WAM+DWSF 方案实际使用 5 个区域、每个 10%，总面积约 50%，偏鲁棒优先。此实验用于判断是否存在更好的质量-鲁棒性折中点。

## 论文来源

- DWSF: Practical Deep Dispersed Watermarking with Synchronization and Fusion, ACM MM 2023。
- 借鉴点：总嵌入面积比例 Q、分散块数、稀疏嵌入带来的视觉质量与鲁棒性权衡。

## 实验设置

- 主模型：WAM 官方 MIT 权重。
- 运行环境：`bamboo` conda 环境，RTX 4060 Laptop GPU。
- 脚本：`watermark_anything\extensions\spatial_redundancy/coverage_search.py`。
- 输出：`results_output/coverage_search/`。
- 图像：WAM 官方 5 张示例图。
- 水印消息：固定随机 32-bit 消息。
- 强度：`scaling_w=2.5`。
- baseline：`single_center_50pct`，中心 50% 单区域水印。
- DWSF variants：
  - `Q=10/20/25/30/50`
  - `5 blocks` 与 `9 blocks`
  - 每个块嵌入同一消息。
- 攻击：
  - none
  - remove_center_40
  - black_center_40
  - crop_top_left_50
  - crop_bottom_right_50
  - crop_center_50
  - jpeg_q30
  - jpeg_q20
  - resize_0.25_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\spatial_redundancy/coverage_search.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\coverage_search `
  --limit 5 `
  --scale 2.5 `
  --areas 10 20 25 30 50 `
  --block-counts 5 9
```

## 关键结果

总计 495 条逐图逐攻击记录，stderr 为空。

overview：

| scheme | PSNR | selected attack mean | worst selected attack |
|---|---:|---:|---:|
| dwsf_q50_5block | 39.7612 | 0.968750 | 0.875000 |
| dwsf_q50_9block | 39.4684 | 0.964844 | 0.893750 |
| dwsf_q30_5block | 42.0691 | 0.957812 | 0.887500 |
| single_center_50pct | 39.1467 | 0.948438 | 0.737500 |
| dwsf_q25_5block | 42.9056 | 0.947656 | 0.868750 |
| dwsf_q20_5block | 43.9523 | 0.919531 | 0.812500 |
| dwsf_q10_5block | 47.2094 | 0.815625 | 0.618750 |

细项：

| attack | single_center_50pct | dwsf_q30_5block | dwsf_q50_5block |
|---|---:|---:|---:|
| remove_center_40 | 1.000000 | 1.000000 | 1.000000 |
| black_center_40 | 1.000000 | 1.000000 | 1.000000 |
| crop_top_left_50 | 1.000000 | 0.937500 | 0.962500 |
| crop_bottom_right_50 | 0.975000 | 0.962500 | 0.987500 |
| crop_center_50 | 1.000000 | 0.968750 | 1.000000 |
| jpeg_q30 | 0.943750 | 0.937500 | 0.943750 |
| jpeg_q20 | 0.737500 | 0.887500 | 0.875000 |
| resize_0.25_jpeg_q50 | 0.931250 | 0.968750 | 0.981250 |

## 判断

1. `Q=10%` 虽然 PSNR 高，但鲁棒性明显不足，不能作为主方案。
2. `Q=25%` 最接近 DWSF 原论文默认设置，PSNR 达 42.9056，但 selected attack mean 仅 0.947656，略低于单区域 0.948438；它可以作为“低扰动版本”，不适合作为最终最强版本。
3. `Q=30%, 5 blocks` 是更好的折中：PSNR 42.0691，比单区域 39.1467 高约 2.92 dB；selected attack mean 0.957812，高于单区域 0.948438；worst selected attack 0.887500，也明显高于单区域 0.737500。
4. `Q=50%, 5 blocks` 仍是鲁棒优先候选：selected attack mean 0.968750 最高，PSNR 39.7612 也略高于单区域 39.1467。
5. 9 blocks 在这套 WAM masking 实现下没有稳定优于 5 blocks，可能因为块更碎后每个局部区域可用于解码的信息不足，或者 WAM 的检测/消息聚合没有针对细碎块训练。
6. DWSF 面积扫描不能包装成全攻击胜利：在 `crop_top_left_50` 和部分中心裁剪上，单中心方案仍更强；DWSF 的主要收益在强 JPEG 最差情况和 resize+JPEG 组合攻击上更明显。

## 保留价值

这轮可以作为最终方案里的一个扎实消融：

- 主创新从“固定 50% 五区域”进一步变成“DWSF 面积比例可调 + TrustMark 强度可调”的二维质量-鲁棒权衡。
- 推荐默认方案可以写成 `Q=30%, 5 blocks, scaling_w=2.5`：比单区域更高 PSNR、更高平均鲁棒性，也避免 50% 面积带来的过重嵌入。
- 鲁棒优先模式仍可保留 `Q=50%, 5 blocks, scaling_w=2.5`。

## 输出文件

- `results_output/coverage_search/coverage_search_metrics.csv`
- `results_output/coverage_search/coverage_search_summary.csv`
- `results_output/coverage_search/coverage_search_overview.csv`
