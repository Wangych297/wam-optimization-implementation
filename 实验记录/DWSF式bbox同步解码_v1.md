# DWSF 式 bbox 同步解码 v1

## 目的

DWSF 论文中的同步模块核心流程是：先用预测 mask 定位水印块，再取最小外接矩形，得到同步后的 encoded blocks，最后分别解码并融合。前面的组合实验显示 DWSF 五区域方案在角落裁剪上仍有退化，因此本实验实现一个轻量近似版：

1. 对攻击图做 WAM detection，得到 watermark mask。
2. 对 mask 做连通区域分析，取 union bbox 和若干主要连通域 bbox。
3. 将 bbox 区域裁剪并 resize 回原图大小，作为 synchronized candidate。
4. 对 global candidate 与 bbox candidates 分别解码。
5. 用置信度选择、消息相似性选择和 oracle 上界进行比较。

## 论文依据

- DWSF：watermark synchronization module，利用预测 mask 的 minimal bounding rectangles 定位并校正 encoded blocks。
- EditGuard / OmniGuard：均强调利用 mask / tamper extractor 获得局部定位，再服务于版权信息和篡改区域判断。

## 脚本

- 脚本：`src\wam_optimization/wam_dwsf_bbox_sync_decode.py`
- 输出目录：`结果输出/wam_dwsf_bbox_sync/`
- 候选文件：`结果输出/wam_dwsf_bbox_sync/wam_dwsf_bbox_sync_candidates.csv`
- 方法文件：`结果输出/wam_dwsf_bbox_sync/wam_dwsf_bbox_sync_methods.csv`
- 汇总文件：`结果输出/wam_dwsf_bbox_sync/wam_dwsf_bbox_sync_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.\original_code\Watermark-Anything'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\src\wam_optimization\wam_dwsf_bbox_sync_decode.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\结果输出\wam_dwsf_bbox_sync" `
  --limit 5
```

## 关键结果

### DWSF 五区域

| scaling_w | attack | global mean/min | bbox similarity mean/min | oracle mean/min |
|---:|---|---:|---:|---:|
| 2.5 | crop_bottom_right_50 | 0.975000 / 0.906250 | 0.975000 / 0.906250 | 0.981250 / 0.937500 |
| 2.5 | crop_center_50 | 0.981250 / 0.937500 | 0.981250 / 0.937500 | 0.993750 / 0.968750 |
| 2.5 | crop_top_left_50 | 0.987500 / 0.937500 | 0.987500 / 0.937500 | 0.987500 / 0.937500 |
| 3.0 | crop_bottom_right_50 | 0.968750 / 0.906250 | 0.975000 / 0.906250 | 0.987500 / 0.968750 |
| 3.0 | crop_center_50 | 0.987500 / 0.937500 | 0.987500 / 0.937500 | 1.000000 / 1.000000 |
| 3.0 | crop_top_left_50 | 0.987500 / 0.937500 | 0.987500 / 0.937500 | 0.993750 / 0.968750 |
| 3.0 | jpeg_q20 | 0.918750 / 0.656250 | 0.925000 / 0.687500 | 0.925000 / 0.687500 |

### 单中心区域

| scaling_w | attack | global mean/min | bbox confidence mean/min | oracle mean/min |
|---:|---|---:|---:|---:|
| 2.5 | crop_bottom_right_50 | 0.993750 / 0.968750 | 1.000000 / 1.000000 | 1.000000 / 1.000000 |
| 2.5 | crop_top_left_50 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 1.000000 / 1.000000 |
| 2.5 | jpeg_q20 | 0.712500 / 0.000000 | 0.812500 / 0.500000 | 0.812500 / 0.500000 |
| 3.0 | crop_bottom_right_50 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 1.000000 / 1.000000 |
| 3.0 | resize_0.25_jpeg_q50 | 0.943750 / 0.781250 | 0.950000 / 0.781250 | 0.950000 / 0.781250 |

## 结论

这个轻量同步方案有价值，但不适合作为主创新。

正向部分：

- 对单中心区域，bbox candidate 能修复部分场景。例如 `single + 2.5 + crop_bottom_right_50` 从 0.993750/0.968750 提升到 1.000000/1.000000；`single + 2.5 + jpeg_q20` 从 0.712500/0.000000 提升到 0.812500/0.500000。
- 对 DWSF 五区域，`scaling_w=3.0 + crop_bottom_right_50` 从 0.968750 提升到 0.975000，`jpeg_q20` 从 0.918750 提升到 0.925000，属于小幅正向。
- oracle 显示部分场景仍有可挖掘空间，例如 DWSF 3.0 的 `crop_center_50` oracle 可到 1.000000/1.000000。

负向部分：

- 对 DWSF 的角落裁剪，实际 bbox confidence/similarity 选择器大多只能持平或小幅提升，没有根本解决同步退化。
- bbox 裁剪后 resize 的候选有时会引入新的尺度失真，置信度选择也不总是选到最优候选。
- 真正接近 DWSF 论文效果的同步模块需要专门训练 segmentation / synchronization，而当前只是基于 WAM mask 的轻量后处理。

后续判断：

- 保留该实验作为“同步定位方向的工程尝试和局限分析”。
- 最终主创新仍建议采用 `DWSF 五区域空间分散 + TrustMark 式 scaling_w=2.5`。
- 若继续深挖同步，应从候选选择策略或训练轻量区域评分器入手，但这会增加工程风险。
