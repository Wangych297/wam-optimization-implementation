# WAM Optimization Implementation

本项目是信息安全课程大作业的工程化实现。主线以 WAM 原论文代码和官方权重为基础，复现 WAM，并在此基础上实现 DWSF、TrustMark、Robust-Wide/FlexMark、EditGuard/OmniGuard、MuST 等论文启发的鲁棒水印改进实验。

## 项目结构

```text
original_code/
  Watermark-Anything/        # WAM 原论文开源代码副本
src/
  wam_optimization/          # 我们的复现、改进和评测实现
experiments/                 # 每个创新方向一个文件夹
results_output/              # 英文别名预留；当前结果仍保存在 结果输出/
结果输出/                    # 已跑出的 CSV 指标和部分可视化
实验记录/                    # 每轮实验的过程、结论和限制
docs/                        # 论文来源、工程说明和结果索引
tools/
  run_experiment.ps1          # 统一运行入口
```

## 原论文代码

WAM 原论文代码已复制到：

```text
original_code/Watermark-Anything
```

官方权重 `wam_mit.pth` 本地也放在：

```text
original_code/Watermark-Anything/checkpoints/wam_mit.pth
```

权重文件约 360MB，已被 `.gitignore` 忽略，不会提交到 GitHub。别人 clone 仓库后，需要自行放入该文件，或按 `original_code/Watermark-Anything/checkpoints/README.md` 的说明处理。

## 环境

当前已验证环境：

```text
C:\Users\86155\miniconda3\envs\bamboo\python.exe
NVIDIA GeForce RTX 4060 Laptop GPU
```

主要依赖来自 WAM 原工程：

```text
original_code/Watermark-Anything/requirements.txt
```

本机 `bamboo` 环境已额外安装过 `omegaconf`、`einops`、`pycocotools`、`timm`、`lpips` 等 WAM 需要的轻量依赖。

## 怎么运行

推荐使用统一入口：

```powershell
.\tools\run_experiment.ps1 -Experiment wam_reproduction
.\tools\run_experiment.ps1 -Experiment dwsf_area_sweep
.\tools\run_experiment.ps1 -Experiment platform_modes
.\tools\run_experiment.ps1 -Experiment must_source_tracing
```

默认会使用项目内的 WAM 原代码：

```text
original_code/Watermark-Anything
```

也可以显式指定 Python 和 WAM 路径：

```powershell
.\tools\run_experiment.ps1 `
  -Experiment platform_modes `
  -Python C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  -WamRoot .\original_code\Watermark-Anything
```

## 创新概览

主线创新：

1. WAM 官方复现和攻击基线。
2. DWSF 式多区域分散嵌入。
3. DWSF 面积比例 `Q` 扫描。
4. TrustMark 式水印强度-画质权衡。
5. Robust-Wide/FlexMark 启发的平台编辑变换模式选择。

附加创新：

1. EditGuard/OmniGuard 启发的主动篡改定位。
2. TrustMark/WAM 启发的二次水印和 provenance update。
3. MuST 启发的多源合成图 source tracing。
4. MBRS/RoSteALS 启发的 ECC 和 codebook 溯源。

探索和负结果：

1. MBRS 式多分支 JPEG 解码。
2. 自适应区域选择。
3. bbox 同步解码。
4. 多种 ECC 编码变体。

详细说明见：

```text
docs/papers_and_ideas.md
docs/results_index.md
报告素材.md
实验记录/
```

## 当前结论

最适合作为主创新的是：

```text
WAM + DWSF 多区域分散嵌入 + TrustMark 强度调节 + 平台变换三档模式选择
```

推荐三档模式：

```text
质量优先：Q=30%, 5 blocks, scaling_w=2.5
均衡鲁棒：Q=50%, 5 blocks, scaling_w=2.5
安全优先：Q=50%, 5 blocks, scaling_w=3.0
```

MuST 多源追踪、主动篡改定位、二次水印适合作为附加安全应用分支，但需要诚实说明限制。
