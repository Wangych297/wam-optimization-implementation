# WAM 官方复现记录

## 目标

跑通 Watermark Anything with Localized Messages 的官方推理流程，验证其作为主论文候选的可复现性。

## 环境

- Python：`C:\Users\86155\miniconda3\envs\bamboo\python.exe`
- Python 版本：3.10
- GPU：NVIDIA GeForce RTX 4060 Laptop GPU
- CUDA：可用
- PyTorch/torchvision：已在现有环境中安装
- 补装依赖：omegaconf、einops、pycocotools、timm、lpips

## 代码与权重

- WAM 官方代码目录：`C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything`
- 权重：`checkpoints\wam_mit.pth`
- 权重来源：`https://dl.fbaipublicfiles.com/watermark_anything/wam_mit.pth`
- 权重大小：377,825,938 bytes
- 权重 SHA256：`90ef232384e023bd63245eb0c131abd69d2afc7b8f17a71ccedceb542bf009e2`
- 参数文件：`checkpoints\params.json`
- 复现脚本：`脚本草稿\wam_official_repro.py`

## 运行命令

```powershell
& "C:\Users\86155\miniconda3\envs\bamboo\python.exe" `
  "C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务\脚本草稿\wam_official_repro.py" `
  --wam-root "C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything" `
  --checkpoint "C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything\checkpoints\wam_mit.pth" `
  --params "C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything\checkpoints\params.json" `
  --image-dir "C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything\assets\images" `
  --out-dir "C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务\结果输出\wam_official_repro" `
  --limit 3 `
  --mask-ratio 0.5 `
  --multi-count 2 `
  --multi-mask-ratio 0.1
```

## 实验内容

### 单水印

对 `alpaca.jpg`、`ducks.jpg`、`gauguin_256.jpg` 三张示例图嵌入同一条 32-bit 消息，仅在 50% 随机区域中保留水印，随后使用 WAM 提取 detection mask 和 bit message。

固定消息：

```text
11001100011110100101101111001011
```

### 多水印

对同三张示例图嵌入两条 32-bit 消息，每条消息使用 10% 随机区域，随后使用 WAM 的 detection mask + DBSCAN 聚类恢复多个局部水印。

消息：

```text
11000100101010100111001001011010
10110101100111000110001100111001
```

## 结果

指标文件：`结果输出\wam_official_repro\wam_official_repro_metrics.csv`

| 模式 | 图像 | bit accuracy | PSNR | 检测到的消息数 |
|---|---|---:|---:|---:|
| single | alpaca.jpg | 1.000000 | 38.8986 | - |
| single | ducks.jpg | 1.000000 | 43.1886 | - |
| single | gauguin_256.jpg | 1.000000 | 42.0654 | - |
| multi | alpaca.jpg | 1.000000 | 42.3100 | 2 |
| multi | ducks.jpg | 1.000000 | 46.1306 | 2 |
| multi | gauguin_256.jpg | 1.000000 | 45.8596 | 2 |

## 输出文件

- 可视化输出目录：`结果输出\wam_official_repro\visuals`
- 单水印输出：
  - 原图
  - 水印图
  - 预测 mask
  - 目标 mask
  - 差分图 x10
- 多水印输出：
  - 多水印图
  - 预测 mask
  - 每个水印区域的目标 mask

## 当前结论

WAM 官方推理流程已在现有 `bamboo` 环境和 RTX 4060 Laptop GPU 上跑通。单水印和多水印均能在官方示例图上稳定恢复消息，说明 WAM 作为主论文候选具备较好的复现基础。

下一步应进入攻击评测基线，验证在 JPEG、resize、crop、local occlusion、splicing 等攻击下的恢复能力，并为 DWSF 式多区域冗余融合提供 baseline。
