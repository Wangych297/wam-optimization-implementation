# 12 颜色空间切换对饱和度攻击的鲁棒性

## 目标

COCO 5000 评测显示 saturation_1.5 是真实弱项（mean=0.968）。饱和度变换改变了 RGB 通道的相对比例，可能干扰 WAM 检测器对水印模式的识别。本实验测试在检测前对图像做颜色空间预处理（roundtrip through YCbCr/LAB/HSV），利用感知均匀颜色空间的归一化特性来抵抗饱和度失真。

## 参考文献

- **WH-SVD-Cb: Robust Blind Watermarking in Cb Channel** (Traitement du Signal 2025) — 借鉴色度通道嵌入思想，说明 Cb 通道对 HVS 更不敏感
- **Color Constancy and Perceptual Color Spaces** (计算机视觉基础) — YCbCr/LAB 等感知均匀颜色空间对色彩变换具有更好的数值稳定性

## 实验设置

- 模型：WAM wam_mit.pth, scaling_w=2.5, mask_ratio=0.5
- 颜色空间：rgb（基线）, ycbcr, lab, hsv
- 处理方式：攻击后图像 → 转换到目标颜色空间 → 转换回 RGB → WAM 检测
- 攻击：saturation_1.5, brightness_1.5, contrast_1.5, none, jpeg_q30
- 数据：COCO 50
- 实现：`watermark_anything/extensions/color_space/color_space_detect.py`
- 参数：`--color-space`（默认 rgb）

## 运行命令

```bash
# 对照组（RGB，无颜色空间切换）
python watermark_anything/extensions/color_space/color_space_detect.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/color_space/control \
  --limit 50

# 实验组（YCbCr 颜色空间）
python watermark_anything/extensions/color_space/color_space_detect.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/color_space/experimental \
  --limit 50 --color-space ycbcr
```

## 结论 — 负向

YCbCr roundtrip 与 RGB 结果完全一致，所有攻击下无差异。COCO 50 样本饱和度攻击本身即为满分（不含 COCO 5000 中的难图）。
