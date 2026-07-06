# 工程结构

仓库采用单工程结构，模型包、扩展模块、实验入口、生成结果和文档都放在同一个项目下。

## 根目录

- `watermark_anything/`：模型包和扩展模块。
- `assets/`：示例图片和 mask。
- `configs/`：模型配置文件。
- `checkpoints/`：本地参数文件和权重。
- `notebooks/`：推理辅助工具。
- `experiments/`：可复现实验入口。
- `tools/`：项目级工具命令。
- `results_output/`：生成的指标、汇总表和部分可视化结果。
- `experiment_notes/`：实验记录和结论。
- `logs/`：本地运行日志。
- `docs/`：技术说明、结果索引和报告素材。

## 实验入口

`experiments/` 下每个目录包含一个简短的 `README.md` 和一个 `run.ps1` 包装入口。真正的实现代码位于 `watermark_anything/extensions/`。
