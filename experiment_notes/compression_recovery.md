# MBRS 式多分支 JPEG 解码 v1

## 目的

WAM 攻击基线显示，强 JPEG 和 resize+JPEG 是明显弱点之一。本实验借鉴 MBRS 的 real JPEG / simulated JPEG / identity 混合思想，但不重训模型，而是在 WAM 推理阶段构造多个预处理分支，再借鉴 DWSF 的消息相似性/置信度思想选择最终解码结果。

这个实验的目标不是替代 MBRS 的训练策略，而是验证：在不重训、只做推理增强的条件下，多分支 JPEG 预处理是否能提升 WAM 的强压缩恢复率。

## 论文依据

MBRS 的关键思想：

- real JPEG 分支让 decoder 学会真实 JPEG 后的特征恢复。
- simulated JPEG-Mask 分支提供可传播的 JPEG 近似。
- identity 分支保证无压缩时的正常解码能力。
- 三者混合可以避免只适配模拟失真或只适配无失真。

DWSF 的可迁移思想：

- 多个候选解码结果之间可以通过消息相似性过滤离群结果，得到最终消息。

## 脚本

- 脚本：`watermark_anything\extensions\compression_recovery/multi_branch_decode.py`
- 输出目录：`results_output/compression_recovery/`
- 候选分支文件：`results_output/compression_recovery/compression_recovery_candidates.csv`
- 方法对比文件：`results_output/compression_recovery/compression_recovery_methods.csv`
- 汇总文件：`results_output/compression_recovery/compression_recovery_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\watermark_anything\extensions\compression_recovery/multi_branch_decode.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\results_output\compression_recovery" `
  --limit 5
```

## 实验设置

- 数据：WAM 官方 `assets/images` 中 5 张示例图。
- 消息长度：32 bit。
- baseline：攻击后直接 WAM detect/decode。
- 多分支候选：
  - identity
  - real_jpeg_q90 / real_jpeg_q70 / real_jpeg_q50
  - JPEG-Mask-like DCT low-pass：keep10 / keep8 / keep6 / keep4
- 选择策略：
  - `mbrs_confidence_select`：选择解码置信度最高的候选分支。
  - `mbrs_similarity_select`：按候选消息相似性选择一致性最高的分支。
  - `oracle_best_branch`：使用真实消息选择最优分支，只作为上界分析，不是实际可用方法。

## 关键结果

| attack | baseline mean/min | confidence mean/min | similarity mean/min | oracle mean/min | 判断 |
|---|---:|---:|---:|---:|---|
| jpeg_q95 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 持平 |
| jpeg_q85 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 持平 |
| jpeg_q75 | 0.993750 / 0.968750 | 0.993750 / 0.968750 | 0.993750 / 0.968750 | 0.993750 / 0.968750 | 持平 |
| jpeg_q65 | 0.975000 / 0.875000 | 0.975000 / 0.875000 | 0.975000 / 0.875000 | 0.981250 / 0.906250 | 有上界潜力，选择器未吃到 |
| jpeg_q50 | 0.968750 / 0.843750 | 0.968750 / 0.843750 | 0.968750 / 0.843750 | 0.975000 / 0.875000 | 有上界潜力，选择器未吃到 |
| jpeg_q30 | 0.962500 / 0.812500 | 0.962500 / 0.812500 | 0.962500 / 0.812500 | 0.962500 / 0.812500 | 持平 |
| jpeg_q20 | 0.850000 / 0.500000 | 0.868750 / 0.593750 | 0.868750 / 0.593750 | 0.881250 / 0.593750 | 小幅提升 |
| resize_0.75_jpeg_q50 | 0.962500 / 0.812500 | 0.968750 / 0.843750 | 0.962500 / 0.812500 | 0.981250 / 0.906250 | 小幅提升 |
| resize_0.5_jpeg_q50 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.987500 / 0.937500 | 选择器未吃到 |
| resize_0.25_jpeg_q50 | 0.943750 / 0.718750 | 0.943750 / 0.718750 | 0.943750 / 0.718750 | 0.950000 / 0.750000 | 基本持平 |
| jpeg_q50_then_q30 | 0.956250 / 0.781250 | 0.956250 / 0.781250 | 0.956250 / 0.781250 | 0.962500 / 0.812500 | 选择器未吃到 |

## 结论

v1 只能算小幅正向，不足以作为最终主创新。

正向部分：

- `jpeg_q20` 从 mean/min 0.850000/0.500000 提升到 0.868750/0.593750。
- `resize_0.75_jpeg_q50` 的 confidence select 从 0.962500/0.812500 提升到 0.968750/0.843750。
- 候选分支确实提供了部分更优解码结果，oracle 在 `jpeg_q65`、`jpeg_q50`、`resize_0.75_jpeg_q50` 等场景更高。

负向部分：

- 当前无监督选择器不够可靠，很多 oracle 能提升的场景没有被 confidence 或 similarity selector 选中。
- 对 `jpeg_q30`、`resize_0.25_jpeg_q50` 等关键弱点基本无改善。
- 仅做推理侧多分支，无法替代 MBRS 的训练侧 real JPEG / simulated JPEG / identity 混合鲁棒学习。

后续判断：

1. 该方向可以作为辅助实验，说明“多分支真实/模拟 JPEG 解码有有限帮助，但没有训练配合时收益有限”。
2. 不建议把 MBRS 式推理增强单独作为最终大创新。
3. 下一步更值得做 TrustMark 式强度-质量权衡：直接改变嵌入残差强度，测试是否能提升强 JPEG 和极端 resize 下的 bit accuracy，并与 DWSF 分散冗余结合。
