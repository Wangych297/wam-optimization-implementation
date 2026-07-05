# TrustMark 式强度-质量权衡 v1

## 目的

TrustMark 论文强调在推理阶段通过残差缩放系数控制不可感知性和鲁棒性的权衡。WAM 中存在语义相近的 `scaling_w` 参数，用于控制水印残差强度。本实验扫描 `scaling_w`，观察 WAM 在不同强度下的 clean PSNR、无攻击恢复率和攻击后 bit accuracy。

这条路线比纯后处理更像对主论文方法本身的改动，因为它直接改变嵌入残差强度。

## 论文依据

TrustMark 的可迁移思想：

- 推理阶段可通过 residual scale factor 控制视觉质量和恢复率。
- 增大残差强度通常提高 bit accuracy，但会降低 PSNR。
- 应通过曲线或 Pareto 点选择折中参数，而不是只追求最高鲁棒性。

## 脚本

- 脚本：`脚本草稿/wam_trustmark_strength_sweep.py`
- 输出目录：`结果输出/wam_trustmark_strength/`
- 明细文件：`结果输出/wam_trustmark_strength/wam_trustmark_strength_metrics.csv`
- 汇总文件：`结果输出/wam_trustmark_strength/wam_trustmark_strength_summary.csv`
- 总览文件：`结果输出/wam_trustmark_strength/wam_trustmark_strength_overview.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\脚本草稿\wam_trustmark_strength_sweep.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\结果输出\wam_trustmark_strength" `
  --limit 5
```

## 实验设置

- 数据：WAM 官方 `assets/images` 中 5 张示例图。
- 消息长度：32 bit。
- 嵌入区域：固定随机 50% 区域，同一张图在不同强度下使用同一个 mask。
- 扫描强度：`scaling_w = 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0`。
- 攻击：
  - none
  - JPEG Q=50/30/20
  - resize 0.5/0.25
  - resize 0.25 + JPEG Q=50
  - center crop 0.5

## 总览结果

| scaling_w | mean clean PSNR | selected attack mean acc | none | jpeg_q50 | jpeg_q30 | jpeg_q20 | resize_0.25 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.25 | 59.1528 | 0.353125 | 0.581250 | 0.200000 | 0.281250 | 0.375000 | 0.900000 |
| 0.50 | 53.1347 | 0.568750 | 0.937500 | 0.743750 | 0.543750 | 0.575000 | 0.943750 |
| 1.00 | 47.1218 | 0.752083 | 0.993750 | 0.912500 | 0.806250 | 0.693750 | 0.981250 |
| 1.50 | 43.6083 | 0.931250 | 0.993750 | 0.962500 | 0.925000 | 0.831250 | 0.987500 |
| 2.00 | 41.1181 | 0.948958 | 1.000000 | 0.981250 | 0.962500 | 0.812500 | 0.993750 |
| 2.50 | 39.1887 | 0.967708 | 1.000000 | 0.987500 | 0.956250 | 0.918750 | 0.993750 |
| 3.00 | 37.6142 | 0.970833 | 1.000000 | 0.987500 | 0.968750 | 0.918750 | 0.993750 |
| 4.00 | 35.1348 | 0.984375 | 1.000000 | 0.981250 | 0.987500 | 0.975000 | 0.993750 |

## 关键观察

1. `scaling_w <= 0.5` 不可用。虽然 clean PSNR 高达 53-59 dB，但 clean bit accuracy 已经不稳定，低强度水印无法保证基本恢复。
2. `scaling_w=1.5` 是高画质折中点。mean clean PSNR 为 43.6083，selected attack mean accuracy 达到 0.931250，center crop 0.5 从低强度下接近失效提升到 0.931250。
3. 官方默认附近的 `scaling_w=2.0` 是稳健折中。mean clean PSNR 为 41.1181，clean accuracy 为 1.0，selected attack mean accuracy 为 0.948958。
4. `scaling_w=2.5/3.0` 进一步提升强攻击鲁棒性，但 clean PSNR 降到 39.1887/37.6142。它们适合“安全优先”场景，但需要报告中承认画质代价。
5. `scaling_w=4.0` 鲁棒性最好，selected attack mean accuracy 为 0.984375，`jpeg_q20` 达到 0.975000，但 mean clean PSNR 只有 35.1348，视觉扰动风险明显。

## 结论

这条改进方向成立，且比 MBRS 推理多分支更适合作为主创新的一部分。

可采用的策略：

- 以 `scaling_w=2.0` 作为 WAM 官方默认强度基线。
- 将 `scaling_w=1.5` 作为高画质版本。
- 将 `scaling_w=2.5` 或 `3.0` 作为增强鲁棒版本。
- 不建议直接使用 `4.0` 作为默认方案，除非实验目标明确偏向鲁棒性而非不可感知性。

下一步最值得做的是把该强度权衡和 DWSF 式空间分散结合：比较“默认强度单区域”“高强度单区域”“默认强度多区域”“较高强度多区域”，判断能否用空间冗余降低单点强度，或用适度增强弥补多区域小块解码退化。
