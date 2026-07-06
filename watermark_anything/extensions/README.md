# 扩展模块

本目录保存鲁棒图像水印系统的扩展功能。各模块以可运行入口为主，实验目录通过 `tools/run_experiment.ps1` 调用这些入口。

```text
baseline_reproduction/   # 基础推理复现
attack_benchmark/        # 攻击基准评测
spatial_redundancy/      # 空间冗余、覆盖搜索、区域同步
robustness_profiles/     # 强度搜索和空间强度组合
transform_profiles/      # 平台变换模式
compression_recovery/    # 压缩恢复
payload_coding/          # 载荷编码变体
region_selection/        # 自适应区域选择
tamper_localization/     # 篡改定位
provenance_update/       # 来源更新
source_tracing/          # 多源溯源
utilities/               # 辅助工具
```

统一运行入口：

```powershell
.\tools\run_experiment.ps1 -Experiment baseline_reproduction
```

新增模块的实验结果输出到 `results_output/`，结果目录说明见 `results_output/README.md`。
