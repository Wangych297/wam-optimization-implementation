# 鲁棒图像水印优化实现 — 项目介绍

## 项目概述

本项目是信息安全课程的课程项目，基于 Meta AI 在 CVPR 2024 发表的 **WAM (Watermark Anything)** 模型进行实现与扩展。核心目标是构建一套鲁棒的图像水印系统，能够将不可见的二值消息（水印）嵌入数字图像，并在图像经历 JPEG 压缩、缩放、裁剪、旋转、滤波等各种攻击后仍能可靠提取。

系统支持三大高级特性：
- **局部水印**：仅在图像的特定空间区域嵌入水印，而非整幅图像
- **多重水印**：在同一图像的不同区域嵌入多个独立水印
- **安全应用扩展**：篡改定位、来源更新（重水印）、多源合成图像溯源

## 核心技术架构

系统基于双网络架构（嵌入器 + 提取器），通过数据增强和感知损失进行端到端训练。

### 嵌入器（VAE 架构）

采用改进的 VQGAN 风格 VAE 编码器-解码器：

1. **编码器**：将 256×256 RGB 图像通过多层 ResNet 下采样块压缩为 16×16 的潜在表示
2. **消息处理器** (`msg_processor.py`)：将 N 位二值消息（默认 32 位）通过可学习嵌入注入潜在空间，支持 concat（拼接，增加通道深度）和 add（相加）两种注入方式
3. **解码器**：从组合的潜在表示重建水印图像，通过镜像上采样块输出像素级调整量（delta），经 tanh 激活后缩放

### 提取器（SAM-ViT 架构）

1. **图像编码器**：基于 SAM (Segment Anything Model) 的 Vision Transformer，包含 12 个 Transformer 块、全局+窗口注意力、相对位置编码。支持三种配置：`sam_tiny` (embed_dim=192)、`sam_small` (384)、`sam_base` (768)，输出 1/16 分辨率特征图
2. **像素解码器** (`pixel_decoder.py`)：CNN 逐步上采样（4×, 2×, 2×，共 16×），恢复至全分辨率后预测：
   - 通道 0：检测掩码（水印存在位置）
   - 通道 1..N：每位预测值

### 感知掩码 (JND)

Just Noticeable Difference 模型计算逐像素可见性阈值：
- **亮度掩码**：极亮或极暗区域可隐藏更多水印失真
- **对比度掩码**：高纹理区域（边缘、渐变）隐藏更多失真
- 生成的热力图决定水印 delta 可在何处放大而不产生可见伪影

### 训练流程 (`train.py`)

分两阶段训练：
1. **预训练**（300 epochs）：COCO 数据集，基础数据增强，低水印强度 (`scaling_w=0.3`)，单水印
2. **微调**（200 epochs）：高强度 (`scaling_w=2.0`)，启用 JND 衰减，多水印训练（`roll_probability=0.2` 空间掩码交换）

损失函数由四部分组成：水印检测损失 (BCE for mask)、水印解码损失 (BCE for bits)、感知损失 (LPIPS)、对抗损失 (PatchGAN 判别器)，通过梯度范数自适应加权平衡。

## 自定义扩展（课程项目核心工作）

所有扩展位于 `watermark_anything/extensions/`，在不重新训练模型的前提下测试不同嵌入策略和后处理方法。

### 1. 空间冗余 / DWSF 实现 (`spatial_redundancy/`)

**项目核心创新**，受 DWSF (ACM MM 2023) 启发，用多个空间分散区域替代单区域水印：

| 方案 | 描述 |
|------|------|
| v1 `redundant_regions.py` | 5 个随机不重叠区域（各 10%），比较均值融合、多数投票、置信度加权 |
| v2 `distributed_layout.py` | 固定四角+中心布局，各 10%（共 50%，与基线匹配）|
| `coverage_search.py` | 系统性扫描覆盖率 Q（10%-50%）与块数（5/9）组合 |
| `region_sync.py` | 轻量级 DWSF 同步模块，通过连通组件检测+裁剪解码实现攻击后重同步 |

**关键发现**：
- **Q=30%, 5 块**：最佳质量-鲁棒性平衡 (PSNR 42.07, 平均攻击准确率 95.8%)
- **Q=50%, 5 块**：鲁棒性优先 (PSNR 39.76, 平均准确率 96.9%)
- 两者均优于单中心基线 (PSNR 39.15, 准确率 94.8%)

### 2. 攻击基准 (`attack_benchmark/`)

评估原始 WAM 模型对各类攻击的鲁棒性：JPEG 压缩 (Q=95→30)、缩放 (75%/50%/25%)、中心裁剪 (90%/75%/50%)、随机裁剪、局部遮挡 (5%/10%/20%)、部分移除。

**主要弱点**：JPEG Q=30（平均位准确率 92.5%）、极端缩放（96.25%）、强中心裁剪（95%）。

### 3. 鲁棒性配置搜索 (`robustness_profiles/`)

- `strength_search.py`：扫描 `scaling_w` (1.0–3.5)，确定关键候选点 2.5 和 3.0
- `spatial_strength_profile.py`：覆盖率与强度的二维网格联合搜索

### 4. 平台变换评估 (`transform_profiles/`)

评估候选配置对真实平台类变换的鲁棒性：JPEG Q=50/30、WebP Q=80/50、高斯模糊、中值滤波、亮度/对比度/饱和度调整、组合流水线。

### 5. 安全应用扩展

| 应用 | 目录 | 功能 |
|------|------|------|
| **篡改定位** | `tamper_localization/` | 通过比较水印掩码位准确率下降检测篡改区域 |
| **来源更新** | `provenance_update/` | 不相交空间分区方案实现重水印，双消息同时成功率达 80% |
| **多源溯源** | `source_tracing/` | 受 MuST 启发，通过 MER 重同步+码本匹配实现合成图像溯源 |

### 6. 辅助模块

- **压缩恢复** (`compression_recovery/`)：多分支 JPEG 解码（identity、真实 JPEG、DCT 低通近似），置信度/相似度候选选择
- **载荷编码** (`payload_coding/`)：重复编码、交织、Hamming(7,4) 码，用于提升载荷级恢复
- **区域选择** (`region_selection/`)：基于纹理/残差的区域选择，测试后未超越固定锚点布局

## 关键算法与技术来源

| 技术 | 来源 | 作用 |
|------|------|------|
| WAM (Watermark Anything) | Meta AI, CVPR 2024 | 核心水印架构：VAE 嵌入器 + SAM-ViT 提取器 + 局部掩码 |
| DWSF (Deep Dispersed Watermarking) | ACM MM 2023 | 空间分散：多区域冗余嵌入，覆盖率 Q 概念 |
| TrustMark | USENIX Security 2024 | 强度-质量权衡，`scaling_w` 参数，来源更新 |
| SAM (Segment Anything Model) | Meta AI | 作为水印提取器的 ViT 骨干 |
| JND (Just Noticeable Difference) | IEEE TIP | 感知掩码模型，限制可见水印失真 |
| MuST (Multi-Source Tracing) | CVPR 2023 | 多源合成图像溯源，MER 重同步 |
| MBRS | ACM MM 2021 | 多分支 JPEG 训练/恢复策略 |
| LPIPS | CVPR 2018 | 图像质量评估的感知损失 |
| PatchGAN Discriminator | Pix2Pix | 对抗训练，生成逼真水印图像 |

## 最终推荐方案

项目最终推荐三种用户可选的操作模式：

| 模式 | 覆盖率 Q | 块数 | 强度 | PSNR | 平均准确率 | 适用场景 |
|------|---------|------|------|------|-----------|----------|
| 质量优先 | 30% | 5 | 2.5 | 42.0 | 97.8% | 对图像质量要求高的场景 |
| 均衡模式 | 50% | 5 | 2.5 | 39.7 | 98.8% | 通用场景 |
| 安全优先 | 50% | 5 | 3.0 | 38.1 | 99.3% | 强攻击/平台传播场景 |

## 目录结构

```
wam-optimization-implementation/
├── watermark_anything/        # 核心模型包 (Meta 上游)
│   ├── augmentation/          # 训练时图像增强
│   ├── data/                  # 数据加载、变换、指标
│   ├── modules/               # 神经网络构建块 (VAE, ViT, JND 等)
│   ├── losses/                # 训练损失函数
│   ├── extensions/            # 自定义课程项目扩展
│   └── utils/                 # 图像工具、日志、优化器
├── configs/                   # YAML 配置文件
├── checkpoints/               # 预训练权重 (wam_mit.pth)
├── experiments/               # 可复现实验入口 (00-08)
├── notebooks/                 # Jupyter 推理笔记本
├── results_output/            # 实验指标、摘要、可视化
├── train.py                   # 训练主脚本
├── tools/                     # 统一实验运行器
├── assets/                    # 示例图像与掩码
├── docs/                      # 报告材料
└── brain/                     # 项目介绍文档
```

## 运行环境

- Python 3.x + PyTorch
- 预训练权重：`wam_mit.pth` (378MB)
- 训练数据：COCO / COCO-Stuff 数据集 (256×256)
- 测试数据：5 张示例图像 + 对应掩码
- 训练配置：8-GPU 分布式数据并行，AdamW 优化器，余弦学习率调度
