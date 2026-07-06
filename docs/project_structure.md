# Project Structure

## original_code

原论文代码副本。目前包含 WAM 官方开源工程。

## src/wam_optimization

我们的实验实现。每个文件对应一个可运行实验模块：

- `wam_official_repro.py`
- `wam_attack_eval.py`
- `wam_dwsf_area_sweep.py`
- `wam_trustmark_strength_sweep.py`
- `wam_combined_dwsf_strength.py`
- `wam_practical_transform_modes.py`
- `wam_tamper_localization_eval.py`
- `wam_rewatermarking_eval.py`
- `wam_must_composite_tracing.py`
- `wam_must_composite_tracing_ecc.py`
- `wam_must_codebook_match.py`

## experiments

面向阅读和复现的实验入口。每个创新方向一个文件夹，包含：

- `README.md`：说明做了什么、来自哪篇论文、结论是什么。
- `run.ps1`：调用 `tools/run_experiment.ps1` 的快捷入口。

## 结果输出

已跑出的 CSV 指标和少量可视化。

## 实验记录

每轮实验的过程记录、关键表格、成功点和失败点。

## docs

工程说明、论文思路、结果索引。
