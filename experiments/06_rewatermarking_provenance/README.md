# 06 Rewatermarking Provenance

## 做什么

模拟 provenance update：一张图先有旧水印，再追加新水印，检查能否同时保留旧来源和新来源。

## 论文来源

- TrustMark
- WAM multiple localized messages
- DWSF spatial partition

## 对应实现

```text
src/wam_optimization/wam_rewatermarking_eval.py
```

## 输出

```text
结果输出/wam_rewatermarking
实验记录/二次水印空间分区_v1.md
```

## 运行

```powershell
.\experiments\06_rewatermarking_provenance\run.ps1
```
