# 03 鲁棒性配置

## 目的

把嵌入强度作为可调参数，比较画质和鲁棒性的取舍，并与空间冗余策略组合成可选安全档位。

## 实现位置

```text
watermark_anything/extensions/robustness_profiles/strength_search.py
watermark_anything/extensions/robustness_profiles/spatial_strength_profile.py
```

## 输出目录

```text
results_output/strength_search
results_output/spatial_strength_profile
```

## 运行方式

```powershell
.\experiments\03_robustness_profiles\run.ps1
```
