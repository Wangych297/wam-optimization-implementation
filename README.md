# 鲁棒图像水印优化实现

这是信息安全课程大作业的鲁棒图像水印工程。项目包含基础推理复现、攻击基准评测、空间冗余嵌入、鲁棒性参数配置、平台变换评估、篡改定位、来源更新和多源溯源等模块。

## 工程结构

```text
watermark_anything/                 # 模型包与扩展模块
assets/                             # 示例图片和 mask
configs/                            # 模型配置
checkpoints/                        # 本地参数和权重
notebooks/                          # 推理辅助工具
experiments/                        # 可复现实验入口
tools/run_experiment.ps1            # 统一实验运行入口
results_output/                     # 指标、汇总表和部分可视化结果
experiment_notes/                   # 实验记录和结论
logs/                               # 本地运行日志
docs/                               # 技术说明和结果索引
```

## 扩展模块

```text
baseline_reproduction/              # 基础推理复现
attack_benchmark/                   # 攻击基准评测
spatial_redundancy/                 # 空间冗余和区域同步
robustness_profiles/                # 强度配置和鲁棒性曲线
transform_profiles/                 # 平台变换评估
compression_recovery/               # 压缩恢复
payload_coding/                     # 载荷编码变体
region_selection/                   # 自适应区域选择
tamper_localization/                # 篡改定位
provenance_update/                  # 来源更新
source_tracing/                     # 多源溯源
utilities/                          # 辅助工具
```

## 权重文件

本地权重放在：

```text
checkpoints/wam_mit.pth
```

权重文件已被 Git 忽略。`checkpoints/params.json` 保留在仓库中。

## 环境

当前验证环境：

```text
C:\Users\86155\miniconda3\envs\bamboo\python.exe
NVIDIA GeForce RTX 4060 Laptop GPU
```

依赖入口：

```text
requirements.txt
```

## 运行

```powershell
.\tools\run_experiment.ps1 -Experiment baseline_reproduction
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

## 主线方向

主线方案结合空间冗余嵌入、嵌入强度配置和平台变换评估，用于压缩、缩放、裁剪、局部移除和多源合成场景下的鲁棒水印验证。
