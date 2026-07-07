# WAM 水印系统优化方案集

本文档针对当前 WAM (Watermark Anything) 系统的架构特点和已知弱点，从近年顶会/顶刊论文中提炼可落地的优化方向。每个方向标注了**改进目标**（解决什么痛点）、**核心思路**、**参考论文**和**实现难度预估**。

---

> **排除说明**：本项目已基于 WAM (CVPR 2024)、DWSF (ACM MM 2023)、TrustMark (USENIX 2024)、MuST (CVPR 2023)、MBRS (ACM MM 2021)、JND、SAM、LPIPS、PatchGAN 等论文开展工作。以下方案均基于上述论文之外的独立工作，避免重复。


## 一、当前系统弱点回顾

| 弱点 | 表现 | 根因 |
|------|------|------|
| 强 JPEG 压缩 (Q≤30) | 位准确率降至 92.5% | 像素域嵌入对 DCT 量化敏感 |
| 极端缩放 (≤50%) | 位准确率降至 96.25% | 空间下采样破坏像素级水印信号 |
| 强中心裁剪 (≤50%) | 位准确率降至 95% | 水印区域被裁掉后无恢复机制 |
| 几何攻击 | 当前未充分评估旋转/透视等 | ViT 缺乏显式几何不变性 |
| 模型体积大 | ViT-large 378MB，推理慢 | SAM-ViT 骨干未压缩 |
| 多水印冲突 | 覆盖冲突时旧水印被破坏 | 无冲突解决/调度机制 |

---

## 二、架构与骨干网络优化

### 2.1 CNN + Transformer 混合解码器

- **改进目标**：增强局部细节+全局语义的联合特征提取，提升提取器对各种攻击的鲁棒性
- **核心思路**：当前提取器为纯 ViT → Pixel Decoder。可引入 CNN 分支并行处理局部纹理特征，与 Transformer 的全局特征通过多尺度注意力融合模块 (Multi-Scale Attentional Feature Fusion) 融合
- **参考论文**：
  - *WFormer: A Transformer-Based Soft Fusion Model for Robust Image Watermarking* (IEEE TNNLS 2024) — 提出 Soft Fusion Module (SFM)，用交叉注意力桥接封面图和水印特征
  - *Robust Blind Watermarking Framework Combining CNN and Transformer* (ACML 2024) — 混合解码器+多尺度注意力融合
  - *GResMark: Swin Transformer with Locally-enhanced Channel Attention* (ESWA 2025) — Swin Transformer + LeCA + 频率通道注意力，几何攻击准确率 >98%
- **实现难度**：⭐⭐⭐ (中) — 需修改 Pixel Decoder 架构并重新训练

### 2.2 可逆神经网络 (INN) 架构

- **改进目标**：增强嵌入-提取耦合，实现无损封面恢复，减少信息损失
- **核心思路**：将当前分离的 VAE 嵌入器+VIT 提取器替换为共享参数的 INN，正向嵌入水印、逆向无损恢复原图和水印。整数 INN (iIWN) 避免浮点误差，在有损通道训练噪声层保持鲁棒性
- **参考论文**：
  - *FRIH: Fully Reversible Image Hiding by Invertible Network* (Neurocomputing 2025) — 网络级+数据级双向可逆
  - *CRMark: Learning Robust Image Watermarking with Lossless Cover Recovery* (ICCV 2025) — 整数 INN，无损恢复，有 pip 包可用
  - *Deep Robust Reversible Watermarking* (arXiv 2025.03) — iIWN + overflow penalty loss，复杂度降低 55×
  - *IWFormer: Transformer-based Invertible NN for Robust Watermarking* (JVCIR 2024) — 用 Transformer 改进 INN 编码器-解码器耦合
- **实现难度**：⭐⭐⭐⭐ (高) — 架构改动大，需从预训练 VAE 迁移或从头训练

### 2.3 几何攻击免疫架构

- **改进目标**：解决旋转、透视变换等几何攻击导致的空间失同步
- **核心思路**：用 Swin Transformer + 可变形卷积 (Deformable Convolution) 替换标准 ViT，移位窗口注意力提供平移不变性，可变形卷积自适应调整感受野处理几何变形。在提取器前加入空间变换网络 (STN) 做预处理对齐
- **参考论文**：
  - *A Geometric Distortion Immunized Deep Watermarking Framework* (ECCV 2024) — Swin Transformer + DCN，几何攻击下提取准确率 100%
  - *GResMark* (ESWA 2025) — 同上方向
- **实现难度**：⭐⭐⭐⭐ (高) — 需更换骨干并重新训练

### 2.4 频域注意力引导嵌入

- **改进目标**：让模型自动学习哪些频率分量最鲁棒，自适应分配水印能量
- **核心思路**：在嵌入器 latent 层添加频域注意力模块 (MFAM)，对 DCT/DWT 系数进行通道注意力加权，使水印信号集中在 JPEG 鲁棒频段（中低频）。用信息融合模块 (IFM) 结合深浅层特征
- **参考论文**：
  - *Frequency-Domain Attention-Guided Adaptive Robust Watermarking Model* (Computers & Electrical Engineering 2025) — MFAM + IFM，JPEG Q=50 下准确率 >98.43%，PSNR >44.65 dB
- **实现难度**：⭐⭐⭐ (中) — 在现有 latent space 添加注意力和频域变换模块

---

## 三、频域水印优化

### 3.1 可微分 JPEG 层

- **改进目标**：根治 JPEG 压缩下准确率下降问题（当前最弱项）
- **核心思路**：在训练噪声层中插入可微分 JPEG 模拟器，使用傅里叶级数逼近量化取整操作：`Q(I) ≈ I - (1/π) Σ(-1)^{k+1}/k · sin(2πkI)`，使 JPEG 压缩对梯度可微，端到端优化水印的 JPEG 鲁棒性。两阶段训练：渐进增强噪声强度 → 混合强噪声泛化
- **参考论文**：
  - *Robust Cross-Image Adversarial Watermark with JPEG Resistance* (CVIU 2025) — DCT 域可微分 JPEG 模块
  - *A Robust Watermarking Scheme via Two-Stage Training and Differentiable JPEG* (Electronics 2025) — 细粒度可微 JPEG + 两阶段训练，噪声条件下 BER 接近 0%
  - *A Robust Watermarking Algorithm Against JPEG Based on Multiscale Autoencoder* (IET Image Processing 2024) — 可微 JPEG 模拟 + 多尺度自编码器，Q=50 下解码率 >99%
- **实现难度**：⭐⭐ (低-中) — 修改 `augmentation/valuemetric.py`，在现有 JPEG 增强基础上添加可微版本

### 3.2 DCT/DWT 域嵌入

- **改进目标**：在变换域而非像素域嵌入，天然抵抗 JPEG 压缩
- **核心思路**：在 WAM 的 VAE latent 层之前或之后加入 DCT/DWT 变换，将水印嵌入到频域系数的中频段。解码时反向变换回像素域。可使用 CSPNet 风格的跨阶段部分连接 (CSPNet) 减少训练开销
- **参考论文**：
  - *CINN: High-speed and JPEG-resistant Medical Image Watermarking Network* (计算机科学 2025) — DCT 低频系数嵌入 + Reed-Solomon 纠错码，Q=50 下 ~100% 恢复
  - *STDM-based Diffusion Watermarking* (JISA 2025) — 在扩散模型 latent 的 DCT 中频系数嵌入，256-bit 容量，98% 提取准确率
- **实现难度**：⭐⭐⭐ (中) — 需在 latent space 插入 DCT/DWT 层

### 3.3 色度通道增强

- **改进目标**：利用人眼对色度不敏感的特性，在 Cb/Cr 通道嵌入额外水印或转移部分水印负载
- **核心思路**：当前 WAM 在 RGB 域嵌入。可将图像转 YCbCr，在 Cb 通道嵌入辅助水印（Y 通道保持主水印），提取时融合双通道信息。Cb 通道嵌入对 HVS 更不可见，允许更高嵌入强度
- **参考论文**：
  - *WH-SVD-Cb: Robust Blind Watermarking in Cb Channel* (Traitement du Signal 2025) — Cb 通道嵌入，PSNR >52 dB, NC≈1
- **实现难度**：⭐⭐ (低) — 在训练和推理中插入颜色空间转换即可

---

## 四、训练策略优化

### 4.1 课程学习 (Curriculum Learning)

- **改进目标**：更稳定、更高效的训练，避免一次性面对强噪声导致收敛困难
- **核心思路**：按攻击破坏性从弱到强分阶段引入：先训无攻击 → 轻 JPEG → 重 JPEG → 缩放 → 裁剪 → 组合攻击。每个阶段达成收敛阈值后自动进阶。可结合 Transformer 模拟社交网络传输操作 (SNTOs)
- **参考论文**：
  - *CL-DRW: Curriculum Learning-Based Deep Robust Watermarking* (IEEE 2025) — 弱到强渐进噪声训练，SNTOs 模拟层，[代码开源](https://github.com/yingshuai-zhao/CL-DRW)
- **实现难度**：⭐⭐ (低) — 修改 `train.py` 的训练循环和增强调度策略

### 4.2 对抗性多嵌入防御训练 (AIS)

- **改进目标**：抵抗多次水印嵌入攻击（覆盖重嵌入），保护水印不被后嵌入者擦除
- **核心思路**：训练时模拟多轮水印嵌入（当前 WAM 已有 roll_probability 但仅用于多水印训练），引入 Adversarial Interference Simulation (AIS) 范式：在微调阶段用额外的嵌入器副本对已水印图像进行二次嵌入，用 resilience-driven loss 强制水印表示稀疏且稳定
- **参考论文**：
  - *Uncovering and Mitigating Destructive Multi-Embedding Attacks* (arXiv 2025.08) — AIS 即插即用训练范式，BER 从 38-50% 降至 <2%
  - *Are Watermarks Bugs for Deepfake Detectors? Rethinking Proactive Forensics* (IJCAI 2024) — AdvMark，对抗性水印微调
- **实现难度**：⭐⭐⭐ (中) — 需修改训练循环，添加二次嵌入和对抗损失

### 4.3 自监督预训练

- **改进目标**：提升特征表示的不变性，减少对大量标注的依赖
- **核心思路**：利用 CLIP 文本嵌入作为语义锚点（Text-Guided Invariant Feature Learning），或通过对比学习（ConZWNet）在弱-强增强对之间学习攻击不变特征。可替代或补充当前的 COCO 监督预训练
- **参考论文**：
  - *Text-Guided Image Invariant Feature Learning for Robust Watermarking* (IEEE 2025) — CLIP 文本引导，不变特征学习
  - *ConZWNet: Contrastive Learning-Based Zero-Watermarking* (JISA 2025) — 对比学习 + ConvNeXt，零水印
  - *SimuFreeMark* (arXiv 2025.11) — 利用图像低频固有稳定性，无需手工攻击模拟
- **实现难度**：⭐⭐⭐⭐ (高) — 需引入 CLIP 模型和新的预训练流程

### 4.4 多损失自适应平衡

- **改进目标**：更精细地平衡检测损失、解码损失、感知损失和对抗损失
- **核心思路**：当前系统使用梯度范数自适应加权。可进一步引入多目标优化 (Multi-Objective Optimization) 或 Pareto 前沿搜索，针对不同场景（质量优先/均衡/安全优先）自动选择损失权重组合
- **实现难度**：⭐⭐ (低) — 在现有 `losses/` 模块上扩展

---

## 五、载荷与编码优化

### 5.1 高级纠错码

- **改进目标**：提升极限攻击下的位恢复能力
- **核心思路**：替换当前简单的重复编码和 Hamming(7,4)，使用更强大的纠错码如 Reed-Solomon（适合对抗突发错误）、LDPC/Turbo 码（适合随机错误）、或 Polar 码。软判决解码（利用提取器的概率输出而非硬判决）可进一步提升增益
- **参考论文**：
  - *CINN* (2025) 使用 Reed-Solomon 码在 DCT 域实现接近 100% 恢复
- **实现难度**：⭐⭐ (低) — 在现有 `extensions/payload_coding/` 中添加新的编码方案

---

## 六、安全应用扩展

### 6.1 半脆弱水印

- **改进目标**：同时实现"对良性处理鲁棒"和"对恶意篡改敏感"
- **核心思路**：嵌入两层水印——鲁棒层（抵抗 JPEG/缩放等）和脆弱层（对局部篡改极度敏感）。检测时若鲁棒层完好但脆弱层破损 → 判定篡改。脆弱层可在高频分量或像素 LSB 中嵌入
- **参考论文**：
  - *Semi-Fragile Invisible Image Watermarking for Social Media Authentication* (arXiv 2024.10) — 半脆弱方案，对良性处理鲁棒、对篡改敏感
  - *A Robust Dual-Pronged Proactive Defense Framework via Adversarial Semi-Fragile Watermarking* (ESWA 2025) — 双分支框架，攻击成功率 + 水印检测成功率均接近 100%
- **实现难度**：⭐⭐⭐ (中) — 需设计双层水印嵌入/提取策略

### 6.2 可证明不可检测水印

- **改进目标**：使水印图像在统计分布上与原始图像不可区分（密码学级别安全性）
- **核心思路**：利用伪随机纠错码在 latent 空间选择初始种子，使水印嵌入等价于从真实图像分布中采样（如 Gaussian Shading）。适用于对检测不可见性要求极高的场景
- **参考论文**：
  - *An Undetectable Watermark for Generative Image Models* (ICLR 2025) — 首个可证明不可检测水印，伪随机纠错码
  - *Gaussian Shading: Provable Performance-Lossless Image Watermarking* (CVPR 2024) — 水印分布符合标准高斯，可证明不可区分
- **实现难度**：⭐⭐⭐⭐ (高) — 需重新设计嵌入机制

---

## 七、模型轻量化与部署优化

### 7.1 知识蒸馏

- **改进目标**：将 SAM-ViT 大模型（378MB）压缩为轻量学生模型，便于移动端/浏览器部署
- **核心思路**：以当前 WAM 完整模型为 Teacher，训练小型 CNN/ViT-tiny Student。蒸馏目标包括：中间特征对齐 (feature distillation)、输出 logit 对齐 (logit distillation)，以及保持水印检测/解码精度的任务蒸馏
- **参考论文**：
  - *Compressing DNN-based Image/Video Watermarking Models for Resource-Constrained Devices* (IEEE CoST 2024) — 剪枝 + 蒸馏两阶段压缩
  - *Lightweight AI Watermarking: Challenges and Research Directions* (IBIMA 2025) — 轻量化水印综述
- **实现难度**：⭐⭐⭐ (中) — 需设计蒸馏流程并收集蒸馏数据

### 7.2 混合量化

- **改进目标**：降低推理延迟和内存占用
- **核心思路**：对 VAE 嵌入器采用 INT8 量化（对精度不敏感），对 ViT 提取器采用混合精度（注意力层保留 FP16，FFN 层 INT8）。可使用 QAT (Quantization-Aware Training) 在微调中联合优化量化参数
- **实现难度**：⭐⭐ (低) — PyTorch 有成熟的量化工具链 (torch.quantization / torchao)

### 7.3 轻量化 ViT 替代

- **改进目标**：用更小的骨干网络替代 SAM-ViT，维持提取性能
- **核心思路**：使用 MobileViT、EdgeViT 或 EfficientFormer 等移动端 ViT 架构替换 SAM-ViT。或在当前 ViT 上应用 token merging/pruning 减少注意力计算量
- **实现难度**：⭐⭐⭐ (中) — 需重新训练提取器或做架构搜索

---

## 八、跨媒体与物理域扩展

### 8.1 屏摄/打印鲁棒水印

- **改进目标**：使水印在屏幕拍照或打印扫描后仍可提取（数字→模拟→数字）
- **核心思路**：训练时引入屏摄失真模拟（摩尔纹、透视变换、亮度/色偏、模糊）。使用模板神经网络 (Template-Forming NN) 做几何校正 + 颜色校正的预处理流水线
- **参考论文**：
  - *Robust Image Watermarking for Diverse Channels with Template-Forming NN* (2024) — 块神经网络水印，对抗压缩+预处理+数模转换，BER <20%
  - *Simulation of Hard-to-Formalize Distortions* (HSE 2025) — 神经网络模拟屏摄失真用于训练
- **实现难度**：⭐⭐⭐⭐ (高) — 需构建失真模拟器和新的测试流水线

---

## 九、推荐实施路线图

按投入产出比和项目周期建议分阶段实施：

### 第一阶段：低投入高回报 (2-4 周)

| 优化项 | 预期效果 |
|--------|----------|
| 可微分 JPEG 层训练 | JPEG Q=30 准确率 92.5% → 97%+ |
| 课程学习训练策略 | 训练更稳定，收敛更快 |
| 高级纠错码 (RS/LDPC) | 极限攻击下恢复率提升 2-5% |
| 色度通道辅助嵌入 | PSNR 提升 0.5-1 dB，保持鲁棒性 |
| INT8 量化推理 | 模型体积减半，推理加速 1.5-2× |

### 第二阶段：架构增强 (4-8 周)

| 优化项 | 预期效果 |
|--------|----------|
| CNN+Transformer 混合解码器 | 局部攻击（遮挡/裁剪）提升 3-5% |
| 频域注意力嵌入 (MFAM) | JPEG 鲁棒性+质量综合提升 |
| 对抗性多嵌入防御 (AIS) | 防止水印覆盖攻击 |
| 知识蒸馏轻量化 | 模型缩小至 50MB 以下 |

### 第三阶段：前沿探索 (8-12 周)

| 优化项 | 预期效果 |
|--------|----------|
| 可逆神经网络 (INN) 架构 | 无损封面恢复 + 更强嵌入-提取耦合 |
| 半脆弱水印双层方案 | 同时支持鲁棒认证和篡改定位 |
| 屏摄/打印鲁棒性 | 支持物理域水印 |
| 可证明不可检测水印 | 密码学级别安全性 |

---

## 十、备选创新方向

以下方向来自其他领域但仍可为水印系统带来启发：

| 方向 | 来源领域 | 可能的应用 |
|------|----------|-----------|
| Neural Radiance Fields (NeRF) 隐式表示 | 3D 视觉 | 将水印表示为连续隐式函数，对分辨率变化天然免疫 |
| 扩散模型反演 (DDIM Inversion) | 生成模型 | 水印嵌入→DDIM反演→加噪→去噪提取，利用扩散过程天然鲁棒性 |
| 联邦学习 + 水印 | 分布式学习 | 多方协作训练水印模型但不共享数据 |
| 元学习 (MAML) | 少样本学习 | 快速适配新攻击类型，few-shot 微调 |
| 对抗样本防御 | 鲁棒机器学习 | 对抗训练的视角反向提升水印鲁棒性 |
| Vision-Language Models (CLIP) | 多模态 | 用文本描述引导水印嵌入位置选择（如"嵌入在纹理密集区域"）|
| 神经水印攻击分析 | 对抗性 ML | NeurIPS 2024 Watermark Removal Challenge 冠军方案揭示的攻击向量可用于针对性防御 |
