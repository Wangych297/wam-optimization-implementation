# 07 Source Tracing

## Purpose

面向多素材合成图，测试不同来源素材的信息恢复、局部重同步、短 ID 冗余和码本匹配。

## Implementation

```text
watermark_anything/extensions/source_tracing/composite_trace.py
watermark_anything/extensions/source_tracing/redundant_id_trace.py
watermark_anything/extensions/source_tracing/codebook_match.py
```

## Output

```text
results_output/source_tracing
results_output/source_tracing_redundant_id
results_output/source_tracing_codebook_match
```

## Run

```powershell
.\experiments\07_source_tracing\run.ps1
```
