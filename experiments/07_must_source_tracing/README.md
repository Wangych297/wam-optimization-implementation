# 07 MuST Source Tracing

## 做什么

模拟多源合成图素材追踪：多张素材分别嵌入 source ID，再被缩放、裁剪、粘贴进一张合成图。然后用 MER/crop resize、短 ID 冗余和 codebook 匹配追踪来源。

## 论文来源

- MuST
- WAM localized messages
- MBRS / RoSteALS message redundancy

## 对应实现

```text
src/wam_optimization/wam_must_composite_tracing.py
src/wam_optimization/wam_must_composite_tracing_ecc.py
src/wam_optimization/wam_must_codebook_match.py
```

## 输出

```text
结果输出/wam_must_composite_tracing
结果输出/wam_must_composite_tracing_ecc
结果输出/wam_must_codebook_match
实验记录/MuST式多源合成追踪_v1.md
```

## 运行

```powershell
.\experiments\07_must_source_tracing\run.ps1
```
