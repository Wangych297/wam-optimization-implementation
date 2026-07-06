# 02 空间冗余

## 目的

把水印从单一区域扩展到多个空间区域，测试冗余嵌入、固定布局、覆盖率搜索和区域同步对鲁棒性的影响。

## 实现位置

```text
watermark_anything/extensions/spatial_redundancy/redundant_regions.py
watermark_anything/extensions/spatial_redundancy/distributed_layout.py
watermark_anything/extensions/spatial_redundancy/coverage_search.py
watermark_anything/extensions/spatial_redundancy/region_sync.py
```

## 输出目录

```text
results_output/redundant_regions
results_output/distributed_layout
results_output/coverage_search
results_output/region_sync
```

## 运行方式

```powershell
.\experiments\02_spatial_redundancy\run.ps1
```
