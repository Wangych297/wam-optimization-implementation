# 08 辅助模块

## 目的

保存已经实现的扩展模块，包括压缩恢复、载荷编码、自适应区域选择和区域同步。

## 实现位置

```text
watermark_anything/extensions/compression_recovery/multi_branch_decode.py
watermark_anything/extensions/payload_coding/repetition_payload.py
watermark_anything/extensions/payload_coding/coding_variants.py
watermark_anything/extensions/region_selection/adaptive_selector.py
watermark_anything/extensions/spatial_redundancy/region_sync.py
```

## 输出目录

```text
results_output/compression_recovery
results_output/repetition_payload
results_output/coding_variants
results_output/adaptive_selector
results_output/region_sync
```

## 运行方式

```powershell
.\experiments\08_auxiliary_modules\run.ps1
```
