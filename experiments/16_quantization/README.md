# 16 混合精度（FP16）量化

## 目标

评估 FP16 半精度对 WAM 模型体积、推理速度和检测精度的影响。FP16 是 NVIDIA GPU 原生支持的半精度浮点格式，理论带宽减半、计算加速 2×。

## 参考文献

- **Mixed Precision Training** (Micikevicius et al., ICLR 2018) — FP16 训练/推理的理论基础和实践指南

## 实验设置

- 模型：WAM wam_mit.pth (FP32)
- 对比：FP32 vs FP16 (.half() + .eval())
- 指标：模型体积、单次 detect 延迟、bit accuracy
- 数据：COCO 50

## 运行命令

```bash
python watermark_anything/extensions/utilities/quantization_benchmark.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 --out-dir results_output/quantization --limit 50
```

## 结论 — 正向（体积减半，精度无损）

| 指标 | FP32 | FP16 | 变化 |
|------|:---:|:---:|:---:|
| 精度 | 0.999 | 0.999 | 无损 |
| 速度 | 10.8ms | 11.0ms | ~持平 |
| 体积 | 360MB | 180MB | **-50%** |

- 精度完全无损（0.99875→0.99875）
- 速度几乎无变化（GPU 瓶颈在注意力访存而非矩阵乘）
- 体积减半：磁盘占用和模型加载时间直接砍半
