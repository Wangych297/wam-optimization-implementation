# 02 DWSF Region Redundancy

## 做什么

把 WAM 的单区域水印改成 DWSF 式多区域分散水印，相当于把证据分散埋在多个位置。

## 论文来源

- DWSF: Practical Deep Dispersed Watermarking with Synchronization and Fusion
- WAM: localized messages

## 对应实现

```text
src/wam_optimization/wam_dwsf_redundant_eval.py
src/wam_optimization/wam_dwsf_spatial_v2.py
src/wam_optimization/wam_dwsf_area_sweep.py
```

## 输出

```text
结果输出/wam_dwsf_redundant
结果输出/wam_dwsf_spatial_v2
结果输出/wam_dwsf_area_sweep
实验记录/DWSF式多区域冗余融合_v1.md
实验记录/DWSF式空间分散冗余_v2.md
实验记录/DWSF面积比例扫描_v1.md
```

## 运行

```powershell
.\experiments\02_dwsf_region_redundancy\run.ps1
```
