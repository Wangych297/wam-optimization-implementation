# 07 多源溯源

## 目标

本实验面向多素材合成图的来源追踪。很多图像不是单一来源，而是由多个局部素材拼接、裁剪或合成得到；如果只给整张图写入一个水印，就无法说明每个局部区域来自哪里。

## 创新设计

多源溯源的核心创新是把来源信息局部化。不同来源区域写入不同身份信息，合成后再尝试从局部区域恢复对应来源，从而回答“这张合成图的某一部分来自哪个源”。

本组实验包含三类机制：

- 局部合成追踪：构造多来源合成图，并分别提取局部来源信息。
- 冗余身份编码：用较短但重复度更高的身份信息提升局部恢复机会。
- 码本匹配：当提取结果有少量错误时，不直接判失败，而是和候选身份表进行近似匹配。

## 工程实现

`composite_trace.py` 负责构造和评估多源合成场景。

`redundant_id_trace.py` 负责测试冗余身份编码在局部破坏下的稳定性。

`codebook_match.py` 负责把提取出的不完整或带错误身份信息映射回最接近的候选来源。

## 结果解读

重点看局部来源能否被正确恢复，以及错误恢复是否集中在边界、重叠或压缩较重的区域。如果码本匹配显著提升来源识别率，说明系统在实际噪声下具有更强可用性；如果误匹配增加，则需要扩大身份间隔或改进置信度阈值。

## 实现位置

```text
watermark_anything/extensions/source_tracing/composite_trace.py
watermark_anything/extensions/source_tracing/redundant_id_trace.py
watermark_anything/extensions/source_tracing/codebook_match.py
```

## 输出目录

```text
results_output/source_tracing
results_output/source_tracing_redundant_id
results_output/source_tracing_codebook_match
```

## 运行方式

```powershell
.\experiments\07_source_tracing\run.ps1
```
