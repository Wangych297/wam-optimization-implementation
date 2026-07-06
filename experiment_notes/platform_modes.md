# 实用编辑与平台变换下的模式选择 v1

## 目的

这一轮不是为了单独增加攻击类型，而是参考 Robust-Wide 和 FlexMark 对真实编辑、平台压缩、容量-鲁棒权衡的关注，把已有 WAM+DWSF 参数组合放到更接近日常传播链路的变换下比较，判断主方案应该保留哪些推荐模式。

## 论文来源

- Robust-Wide：关注 instruction-driven image editing 后水印仍能恢复，强调真实编辑链路比单一 JPEG/裁剪更复杂。
- FlexMark：强调 watermarking 在容量、鲁棒性和不可感知性之间存在可调权衡，且实际平台会引入 WebP/JPEG 等格式转换。
- TrustMark：强度-质量权衡和 provenance 场景，支持按安全需求提高嵌入强度。
- DWSF：分散嵌入面积比例 Q 与鲁棒性/PSNR 的权衡。

## 实验设置

- 主模型：WAM 官方 MIT 权重。
- 环境：`bamboo` conda 环境，RTX 4060 Laptop GPU。
- 脚本：`watermark_anything\extensions\transform_profiles/platform_modes.py`。
- 输出：`results_output/platform_modes/`。
- 图像：WAM 官方 5 张示例图。
- 消息：固定随机 32-bit 消息。
- 对比模式：
  - `single_center50_s2.5`
  - `single_center50_s3.0`
  - `dwsf_default_q30_s2.5`
  - `dwsf_robust_q50_s2.5`
  - `dwsf_strong_q30_s3.0`
  - `dwsf_robust_strong_q50_s3.0`
- 变换：
  - JPEG Q=50/30
  - WebP Q=80/50
  - Gaussian blur、median filter
  - brightness/contrast/saturation/sharpness
  - brightness+contrast+JPEG80
  - resize 0.5 + JPEG50
  - saturation+sharpness+WebP80

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\transform_profiles/platform_modes.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\platform_modes `
  --limit 5
```

## 关键结果

overview：

| scheme | PSNR | selected attack mean | worst selected attack | jpeg_q30 | webp_q50 | resize_0.5_jpeg50 | bright_contrast_jpeg80 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dwsf_default_q30_s2.5 | 42.0144 | 0.977885 | 0.912500 | 0.918750 | 0.912500 | 0.943750 | 0.987500 |
| dwsf_robust_q50_s2.5 | 39.7046 | 0.988462 | 0.943750 | 0.943750 | 0.943750 | 0.975000 | 1.000000 |
| dwsf_robust_strong_q50_s3.0 | 38.1298 | 0.992788 | 0.950000 | 0.950000 | 0.968750 | 0.993750 | 1.000000 |
| dwsf_strong_q30_s3.0 | 40.4399 | 0.981731 | 0.900000 | 0.931250 | 0.900000 | 0.962500 | 1.000000 |
| single_center50_s2.5 | 39.1000 | 0.987981 | 0.937500 | 0.937500 | 0.943750 | 0.987500 | 0.993750 |
| single_center50_s3.0 | 37.5249 | 0.992788 | 0.956250 | 0.956250 | 0.956250 | 0.993750 | 1.000000 |

## 判断

1. `dwsf_default_q30_s2.5` 仍是高画质默认模式，PSNR 达 42.0144，但在 `jpeg_q30` 和 `webp_q50` 下最弱，说明它不适合作为安全优先配置。
2. `dwsf_robust_q50_s2.5` 是更稳的均衡鲁棒模式：PSNR 39.7046，selected attack mean 0.988462，明显高于 q30 默认模式，且 worst selected attack 从 0.912500 提升到 0.943750。
3. `dwsf_robust_strong_q50_s3.0` 与 `single_center50_s3.0` 的 mean selected attack accuracy 同为 0.992788，但 PSNR 为 38.1298，高于 single 的 37.5249；它的 worst selected attack 略低于 single，但保留了 DWSF 的空间分散优势，后续能和篡改定位/多阶段授权分支合并。
4. `dwsf_strong_q30_s3.0` 不推荐。只提高强度但不增加覆盖面积，WebP Q50 下反而只有 0.900000，低于 `dwsf_robust_q50_s2.5`。
5. 这轮实验把最终方案从单一推荐扩展为三档模式：
   - 质量优先：`Q=30%, 5 blocks, scaling_w=2.5`。
   - 均衡鲁棒：`Q=50%, 5 blocks, scaling_w=2.5`。
   - 安全/平台鲁棒优先：`Q=50%, 5 blocks, scaling_w=3.0`。

## 输出文件

- `results_output/platform_modes/platform_modes_metrics.csv`
- `results_output/platform_modes/platform_modes_summary.csv`
- `results_output/platform_modes/platform_modes_overview.csv`
