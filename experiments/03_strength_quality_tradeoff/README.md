# 03 Strength Quality Tradeoff

## 做什么

参考 TrustMark，把水印强度变成可调参数，比较画质和鲁棒性的取舍，并和 DWSF 多区域策略组合。

## 论文来源

- TrustMark
- DWSF
- WAM

## 对应实现

```text
src/wam_optimization/wam_trustmark_strength_sweep.py
src/wam_optimization/wam_combined_dwsf_strength.py
```

## 输出

```text
结果输出/wam_trustmark_strength
结果输出/wam_combined_dwsf_strength
实验记录/TrustMark式强度质量权衡_v1.md
实验记录/DWSF与TrustMark强度组合_v1.md
```

## 运行

```powershell
.\experiments\03_strength_quality_tradeoff\run.ps1
```
