# 17 消融实验 — 最终管线汇总

## 目标

逐一测量各优化模块的独立贡献，确认核心组合方案。

## 实验设置

- 6 个消融模式，两列独立对比（32-bit  vs 8-bit ECC）
- 7 种攻击：none, center_crop_0.5, random_crop_0.5, jpeg_q30, resize_0.25, rotate_73, flip_h
- 数据：COCO 50
- 实现：`watermark_anything/extensions/utilities/ablation_study.py`

## 运行命令

```bash
python watermark_anything/extensions/utilities/ablation_study.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 --out-dir results_output/ablation --limit 50
```

## 结论

| Attack           | A_base | B_ms   | C_ms_geo | D_ecc | E_ms_ecc | F_full |
|------------------|:------:|:------:|:--------:|:-----:|:--------:|:------:|
| center_crop_0.5  | 0.503  | 0.999  | 0.999    | 0.978 | **1.000** | 1.000  |
| random_crop_0.5  | 0.494  | 0.713  | 0.713    | 0.920 | **1.000** | 1.000  |
| rotate_73        | 0.429  | 0.506  | 0.867    | 1.000 | 1.000    | 1.000  |
| flip_h           | 0.639  | 0.639  | 0.639    | 0.885 | **1.000** | 1.000  |
| resize_0.25      | 0.946  | 0.946  | 0.946    | 0.870 | **1.000** | 1.000  |
| jpeg_q30         | 0.998  | 0.998  | 0.998    | 1.000 | 1.000    | 1.000  |
| none             | 1.000  | 1.000  | 1.000    | 1.000 | 1.000    | 1.000  |

**核心发现**：

- **A→B**：多尺度检测独自解决中心裁剪（+0.496）
- **B→C**：几何盲扫描独自解决旋转（+0.361）
- **D→E**：多尺度在 ECC 基础上补齐随机裁剪和翻转
- **E vs F**：在 MS+ECC 组合下，几何扫描无额外收益
- **最终管线**：**多尺度检测 + rep4_interleaved ECC = 全覆盖**（E 模式所有攻击达 1.000）
