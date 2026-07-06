# 主动篡改定位 v1

## 目的

这轮从 EditGuard / OmniGuard 的主动取证思想出发，验证 WAM+DWSF 是否不仅能恢复版权 payload，还能利用检测 mask 定位局部篡改区域。

核心问题：

1. WAM 的 watermark detection mask 在局部篡改后是否会出现可检测的缺失？
2. DWSF 的稀疏区域是否能做“覆盖区域内”的高精度篡改定位？
3. `Q=30%` 与 `Q=50%` 在定位能力上有什么差异？

## 论文来源

- EditGuard：通过比较预定义 localization watermark 与恢复的 localization watermark 得到 tamper mask，并用 F1、AUC、IoU、bit accuracy 评价。
- OmniGuard：强调主动水印 + 被动提取结合，用 artifact map / reconstructed localized watermark 辅助 tamper mask extraction。
- DWSF：分散嵌入天然只覆盖部分区域，因此定位能力会受 watermark coverage 限制。

## 实验设置

- 脚本：`watermark_anything\extensions\tamper_localization/localizer.py`。
- 输出：`results_output/tamper_localization/`。
- 主模型：WAM 官方 MIT 权重。
- 图像：WAM 官方 5 张示例图。
- 水印：固定随机 32-bit 消息。
- 强度：`scaling_w=2.5`。
- schemes：
  - `single_center_50pct`
  - `dwsf_q30_5block`
  - `dwsf_q50_5block`
- tamper：
  - remove_center_25
  - remove_center_40
  - remove_top_left_25
  - remove_bottom_right_25
  - black_center_25
- localizer：
  - `expected_missing`：已知放置 mask 中，被攻击后检测概率低的区域。
  - `clean_missing`：clean watermarked detection mask 中，被攻击后检测概率低的区域。
  - `prob_drop`：clean mask 概率相对 attacked mask 明显下降的区域。
- 指标：
  - global F1 / IoU：对完整真实 tamper mask 计算。
  - covered F1 / IoU：只对水印覆盖到的 tamper 区域计算。
  - tamper coverage：真实篡改区域中被水印参考 mask 覆盖的比例。
  - bit accuracy：篡改后版权消息恢复准确率。

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\tamper_localization/localizer.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\tamper_localization `
  --limit 5 `
  --scale 2.5
```

## 关键结果

总计 225 条逐图逐篡改逐定位器记录，stderr 为空。

overview：

| scheme | localizer | global F1 | global IoU | covered F1 | covered IoU | tamper coverage | bit accuracy |
|---|---|---:|---:|---:|---:|---:|---:|
| single_center_50pct | prob_drop | 0.695941 | 0.615839 | 0.825536 | 0.808216 | 0.802378 | 0.997500 |
| dwsf_q50_5block | prob_drop | 0.635645 | 0.466754 | 0.973085 | 0.948559 | 0.486693 | 1.000000 |
| dwsf_q30_5block | prob_drop | 0.420431 | 0.267545 | 0.985547 | 0.971861 | 0.271703 | 1.000000 |

逐篡改 `prob_drop` 结果：

| scheme | tamper | global F1 | covered F1 | tamper coverage | bit accuracy |
|---|---|---:|---:|---:|---:|
| dwsf_q30_5block | remove_center_25 | 0.416001 | 0.997476 | 0.263105 | 1.000000 |
| dwsf_q30_5block | remove_center_40 | 0.329819 | 0.963651 | 0.204362 | 1.000000 |
| dwsf_q30_5block | remove_top_left_25 | 0.471410 | 0.982671 | 0.314808 | 1.000000 |
| dwsf_q50_5block | remove_center_25 | 0.640710 | 0.975985 | 0.486801 | 1.000000 |
| dwsf_q50_5block | remove_center_40 | 0.596838 | 0.972839 | 0.439676 | 1.000000 |
| dwsf_q50_5block | remove_top_left_25 | 0.668060 | 0.988773 | 0.509149 | 1.000000 |
| single_center_50pct | remove_center_25 | 0.987527 | 0.987527 | 1.000000 | 1.000000 |
| single_center_50pct | black_center_25 | 0.184190 | 0.184190 | 1.000000 | 1.000000 |

## 判断

这轮是可保留的补充分支，但不是替代版权恢复主线。

1. DWSF 在“覆盖区域内”的篡改定位非常强：`Q=30` covered F1 约 0.985547，`Q=50` covered F1 约 0.973085，说明 WAM detection mask 的缺失确实能作为主动篡改线索。
2. 全图定位能力受水印覆盖率直接限制：`Q=30` 的 tamper coverage 只有 0.271703，因此 global F1 只有 0.420431；`Q=50` coverage 提升到 0.486693，global F1 提升到 0.635645。
3. `single_center_50pct` 在中心篡改上极强，但空间覆盖不均，且 `black_center_25` 的 global F1 只有 0.184190，说明黑块会干扰检测 mask，不能简单说单中心定位更好。
4. 版权 bit recovery 在 DWSF 两个方案下均保持 1.000000，说明增加这个定位分析分支不会损害版权恢复结果。
5. 如果报告需要一个纯信息安全色彩更强的创新点，这个分支比自适应选块/ECC 变体更有价值：它把“版权追踪”扩展到“局部完整性/篡改定位”，但必须写清它只能定位被水印覆盖的区域。

## 保留价值

- 可作为最终工作的附加创新分支：WAM+DWSF 不只恢复版权信息，还能输出 watermark survival / missing map，用于主动篡改定位。
- 推荐写法：默认主线仍是 `DWSF Q=30%, 5 blocks + scaling_w=2.5`；若要强调篡改定位覆盖率，可引入 `Q=50%` 安全优先模式。
- 这个分支能和信息安全课程的完整性保护、主动取证、认证与访问后追踪场景自然连接。

## 输出文件

- `results_output/tamper_localization/tamper_localization_metrics.csv`
- `results_output/tamper_localization/tamper_localization_summary.csv`
- `results_output/tamper_localization/tamper_localization_overview.csv`
