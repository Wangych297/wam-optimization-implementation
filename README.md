# 鲁棒图像水印优化实现

这是一个面向信息安全课程大作业的鲁棒图像水印工程。项目围绕图像水印的嵌入、提取、攻击恢复、篡改定位和来源追踪展开，包含基础复现、攻击评估、空间冗余、强度配置、平台变换、载荷编码、来源更新和多源溯源等模块。

## 工程结构

```text
watermark_anything/                 # 模型包、基础推理代码和扩展模块
watermark_anything/extensions/      # 本项目新增的功能模块
watermark_anything/upstream_docs/   # 原始工程说明归档
assets/                             # 示例图片和 mask
configs/                            # 模型配置
checkpoints/                        # 本地参数和权重
notebooks/                          # 推理辅助工具
experiments/                        # 可复现实验入口
tools/run_experiment.ps1            # 统一实验运行入口
results_output/                     # 指标、汇总表和可视化结果
logs/                               # 本地运行日志
docs/report_materials.md            # 报告素材池
```

## 功能模块

| 模块目录 | 作用 |
| --- | --- |
| `baseline_reproduction/` | 基础推理复现，验证权重、配置和嵌入提取流程。 |
| `attack_benchmark/` | 对压缩、缩放、裁剪、局部移除等攻击做统一评估。 |
| `spatial_redundancy/` | 实现空间冗余嵌入、分布式布局、覆盖搜索和区域同步。 |
| `robustness_profiles/` | 搜索水印强度和空间强度配置，生成鲁棒性候选档位。 |
| `transform_profiles/` | 模拟不同平台传播链路下的图像变换。 |
| `compression_recovery/` | 对压缩破坏后的恢复和多分支解码进行评估。 |
| `payload_coding/` | 实现重复载荷、编码变体等消息恢复策略。 |
| `region_selection/` | 根据图像内容选择更适合嵌入的区域。 |
| `tamper_localization/` | 根据局部水印提取结果定位疑似篡改区域。 |
| `provenance_update/` | 支持二次水印写入和来源信息更新。 |
| `source_tracing/` | 支持多源合成图中的局部来源追踪。 |
| `utilities/` | 权重下载和通用辅助工具。 |

## 环境与权重

当前已验证环境：

```text
C:\Users\86155\miniconda3\envs\bamboo\python.exe
NVIDIA GeForce RTX 4060 Laptop GPU
```

依赖入口：

```text
requirements.txt
```

主权重文件放在：

```text
checkpoints/wam_mit.pth
```

权重文件体积较大，已通过 `.gitignore` 排除；`checkpoints/params.json` 保留在仓库中。

## 运行实验

统一入口：

```powershell
.\tools\run_experiment.ps1 -Experiment baseline_reproduction
.\tools\run_experiment.ps1 -Experiment attack_benchmark
.\tools\run_experiment.ps1 -Experiment coverage_search
.\tools\run_experiment.ps1 -Experiment platform_modes
.\tools\run_experiment.ps1 -Experiment source_tracing
```

也可以显式指定 Python：

```powershell
.\tools\run_experiment.ps1 `
  -Experiment platform_modes `
  -Python C:\Users\86155\miniconda3\envs\bamboo\python.exe
```

## 实验入口

`experiments/` 下每个目录对应一组可复现实验，目录内的 `README.md` 说明了该组实验调用的模块、运行命令和输出位置。

```text
00_baseline_reproduction/
01_attack_benchmark/
02_spatial_redundancy/
03_robustness_profiles/
04_transform_profiles/
05_tamper_localization/
06_provenance_update/
07_source_tracing/
08_auxiliary_modules/
```

## 输出与素材

实验结果集中保存在 `results_output/`，该目录的 `README.md` 记录了各模块的输出位置。

报告写作素材集中保存在 `docs/report_materials.md`。过程记录、创新依据、结果摘要和实验笔记都已合并到这个文件中，工程目录只保留运行和维护所需的说明。
