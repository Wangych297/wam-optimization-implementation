# DWSF 与 TrustMark 强度组合 v1

## 目的

前面两个实验分别说明：

- DWSF 式空间分散冗余对中心大块破坏有效，但对角落/中心 50% 裁剪不稳定。
- TrustMark 式强度扫描能显著提升鲁棒性，但高强度会降低 PSNR。

本实验将二者组合：比较单中心 50% 区域和 DWSF 五区域空间分散，在 `scaling_w=1.5/2.0/2.5/3.0` 下的质量与鲁棒性，判断是否能形成“适度强度 + 空间分散”的主创新方案。

## 脚本

- 脚本：`watermark_anything\extensions\robustness_profiles/spatial_strength_profile.py`
- 输出目录：`results_output/spatial_strength_profile/`
- 明细文件：`results_output/spatial_strength_profile/spatial_strength_profile_metrics.csv`
- 汇总文件：`results_output/spatial_strength_profile/spatial_strength_profile_summary.csv`
- 总览文件：`results_output/spatial_strength_profile/spatial_strength_profile_overview.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\watermark_anything\extensions\robustness_profiles/spatial_strength_profile.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\results_output\spatial_strength_profile" `
  --limit 5
```

## 实验设置

- 数据：WAM 官方 `assets/images` 中 5 张示例图。
- 消息长度：32 bit。
- 对比方案：
  - `single_center_50pct`：单个中心区域，占图像约 50%。
  - `dwsf_5region_spatial`：四角 + 中心共 5 个区域，每个约 10%，总面积约 50%。
- 强度：`scaling_w=1.5/2.0/2.5/3.0`。
- 攻击：
  - none
  - remove_center_40
  - black_center_40
  - crop_top_left_50 / crop_bottom_right_50 / crop_center_50
  - JPEG Q=30/20
  - resize 0.25 + JPEG Q=50

## 总览结果

| scheme | scaling_w | mean PSNR | selected attack mean acc |
|---|---:|---:|---:|
| dwsf_5region_spatial | 1.5 | 44.1913 | 0.897656 |
| dwsf_5region_spatial | 2.0 | 41.7007 | 0.938281 |
| dwsf_5region_spatial | 2.5 | 39.7711 | 0.964063 |
| dwsf_5region_spatial | 3.0 | 38.1964 | 0.973437 |
| single_center_50pct | 1.5 | 43.5495 | 0.875000 |
| single_center_50pct | 2.0 | 41.0591 | 0.916406 |
| single_center_50pct | 2.5 | 39.1293 | 0.957812 |
| single_center_50pct | 3.0 | 37.5542 | 0.963281 |

## 关键细节

在同一强度下，DWSF 五区域方案的平均攻击准确率都高于单中心方案，并且 mean PSNR 也略高。

最有价值的对比是：

- `dwsf_5region_spatial + scaling_w=2.5`：mean PSNR 39.7711，selected attack mean accuracy 0.964063。
- `single_center_50pct + scaling_w=3.0`：mean PSNR 37.5542，selected attack mean accuracy 0.963281。

也就是说，DWSF+2.5 用更低强度达到了略高于单中心+3.0 的平均鲁棒性，同时 PSNR 高约 2.2 dB。这说明空间分散可以部分替代单点强度增加，形成“空间冗余换取较低扰动”的解释。

但也必须承认：

- 对 `crop_bottom_right_50`，单中心方案在多个强度下更强。例如 `single_center_50pct + 2.5` 为 0.968750/0.937500，而 `dwsf_5region_spatial + 2.5` 为 0.943750/0.875000。
- 对 `jpeg_q20` 和 `resize_0.25_jpeg_q50`，DWSF 组合更有优势。例如 `dwsf_5region_spatial + 2.5` 的 `resize_0.25_jpeg_q50` 为 0.975000/0.875000，高于单中心 2.5 的 0.956250/0.781250。
- 对中心大块破坏，DWSF 方案稳定满分：`remove_center_40` 和 `black_center_40` 在所有强度下均为 1.000000/1.000000。

## 结论

目前最适合作为最终主创新版本的是：

> WAM 主论文复现 + DWSF 式五区域空间分散 + TrustMark 式强度-质量权衡。

推荐报告里的主要改进方案可以写成：

1. 先复现 WAM 的局部水印嵌入与检测。
2. 借鉴 DWSF，将同一消息分散嵌入多个空间区域，提升局部破坏和部分压缩/缩放后的恢复率。
3. 借鉴 TrustMark，扫描并选择更合适的残差强度，使系统在 PSNR 和鲁棒性之间达到折中。
4. 实验表明 `DWSF + scaling_w=2.5` 可以在接近 `single + scaling_w=3.0` 的鲁棒性下保留更高 PSNR。

下一步如果继续优化，应优先解决 DWSF 组合在角落裁剪上的退化问题，可以从 EditGuard/OmniGuard 的篡改定位或 DWSF 的同步定位思想里找“候选区域重定位/区域级解码”的实现方向。
