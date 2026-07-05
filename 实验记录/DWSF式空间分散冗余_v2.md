# DWSF 式空间分散冗余 v2

## 目的

v1 使用随机多区域重复嵌入，结果不稳定。v2 改为更明确的 DWSF-style 空间分散设计：将同一 32-bit 消息嵌入四角和中心共 5 个区域，每个区域约占图像 10%，总水印面积约为 50%，与单中心 50% 区域方案控制在相近嵌入面积。

本实验重点验证：当攻击是局部大块破坏、中心区域移除、半图移除或 50% 裁剪时，空间分散是否能比单中心区域更稳。

## 脚本

- 脚本：`脚本草稿/wam_dwsf_spatial_v2.py`
- 输出目录：`结果输出/wam_dwsf_spatial_v2/`
- 指标文件：`结果输出/wam_dwsf_spatial_v2/wam_dwsf_spatial_v2_metrics.csv`
- 汇总文件：`结果输出/wam_dwsf_spatial_v2/wam_dwsf_spatial_v2_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\脚本草稿\wam_dwsf_spatial_v2.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\结果输出\wam_dwsf_spatial_v2" `
  --limit 5
```

## 实验设置

- 数据：WAM 官方 `assets/images` 中 5 张示例图。
- 消息长度：32 bit。
- baseline：单个中心矩形区域，占图像面积约 50%。
- DWSF-style v2：四角 + 中心共 5 个矩形区域，每个约 10%，总面积约 50%。
- 攻击：
  - no attack
  - remove_center_25 / remove_center_40
  - black_center_25 / black_center_40
  - remove_left_half / remove_right_half
  - crop_top_left_50 / crop_bottom_right_50 / crop_center_50

## 关键结果

| attack | single mean/min | dwsf v2 mean/min | 判断 |
|---|---:|---:|---|
| none | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 持平 |
| remove_center_25 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 持平 |
| remove_center_40 | 0.975000 / 0.875000 | 1.000000 / 1.000000 | v2 明显提升 |
| black_center_25 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 持平 |
| black_center_40 | 0.981250 / 0.906250 | 1.000000 / 1.000000 | v2 明显提升 |
| remove_left_half | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 持平 |
| remove_right_half | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 持平 |
| crop_top_left_50 | 0.981250 / 0.937500 | 0.943750 / 0.906250 | v2 退化 |
| crop_bottom_right_50 | 0.975000 / 0.937500 | 0.931250 / 0.750000 | v2 明显退化 |
| crop_center_50 | 0.987500 / 0.968750 | 0.975000 / 0.937500 | v2 小幅退化 |

## 结论

v2 不是一个可以直接作为最终创新的稳定方案。

正向部分：空间分散冗余对“中心大块破坏”有效。`remove_center_40` 和 `black_center_40` 中，单中心 baseline 会因为水印主体被破坏而出现 bit 错误，五区域分散方案可以依靠四角残留区域恢复消息。

负向部分：对 50% 裁剪，五区域固定布局反而更差。原因可能是裁剪后图像被 resize 回原大小，角落区域的几何位置和尺度发生明显变化；当前方案只做重复嵌入，没有真正实现 DWSF 中的同步/定位校正，也没有对多个候选区域做更细的区域级重采样解码。

下一步不能继续只堆空间位置。更合理的方向是：

1. 引入多尺度/多预处理解码，借鉴 MBRS 对真实 JPEG/模拟失真的鲁棒处理思路。
2. 扫描嵌入强度，借鉴 TrustMark 的强度-质量权衡，观察是否能在不明显牺牲 PSNR 的前提下弥补分散区域变小带来的解码退化。
3. 若继续 DWSF 线，应做“候选区域同步 + 区域级解码融合”，而不是简单全图一次解码。
