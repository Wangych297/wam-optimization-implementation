# 13 多尺度检测 + 区域同步解码

## 目标

实验 10 的多尺度检测能将 center_crop 提升至 0.99975，但对 random_crop 仅到 0.701。随机裁剪不仅改变尺度，还改变了水印区域的几何位置。本实验在多尺度检测基础上叠加 bbox 区域同步：先通过 WAM detection mask 定位存活水印区域，对区域做精确裁剪和重采样，然后解码。

## 参考文献

- **DWSF: Practical Deep Dispersed Watermarking with Synchronization and Fusion** (ACM MM 2023) — 借鉴 watermark synchronization module 的 bbox 定位+重采样+分别解码思路
- 本项目 `region_sync.py` — 已有 bbox 同步解码的工程实现，本实验在其基础上添加多尺度支持

## 实验设置

- 模型：WAM wam_mit.pth, scaling_w=2.5, mask_ratio=0.5
- 流程：攻击图 → 多尺度检测 → 获取 watermask → 提取最大连通域 bbox → 裁剪+resize 到 256×256 → 二次解码 → 取多尺度和 bbox 的最佳结果
- 攻击：center_crop_0.5, center_crop_0.75, random_crop_0.5, none, jpeg_q30
- 数据：COCO 50
- 实现：`watermark_anything/extensions/spatial_redundancy/multi_scale_bbox.py`
- 参数：`--use-bbox-sync`（默认关）

## 运行命令

```bash
# 对照组（多尺度，无 bbox 同步）
python watermark_anything/extensions/spatial_redundancy/multi_scale_bbox.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/bbox_sync/control \
  --limit 50 --use-multi-scale

# 实验组（多尺度 + bbox 同步）
python watermark_anything/extensions/spatial_redundancy/multi_scale_bbox.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 \
  --out-dir results_output/bbox_sync/experimental \
  --limit 50 --use-multi-scale --use-bbox-sync
```

## 结论 — 负向

bbox sync 无增量，random_crop_0.5 恒为 0.698。crop+resize 后 watermask 本身失真，提取的 bbox 不可靠。
