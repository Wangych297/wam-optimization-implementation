# 报告素材

## 选题

鲁棒图像水印可用于图像内容的完整性保护、授权验证、篡改定位和来源追踪。工程主线聚焦空间冗余嵌入、强度配置和平台变换鲁棒性，并扩展到来源更新和多源合成图溯源。

## 课程关联

- 密码与认证：水印消息可作为内容认证和归属验证载荷。
- 数据完整性：攻击后提取准确率和局部置信度下降可用于完整性判断。
- 授权与访问控制：二次水印用于再授权、版本更新和来源更新。
- Web 与应用安全：平台压缩、缩放、裁剪和格式转换对应真实传播链路。
- 数据安全技术：多源合成图溯源用于内容来源追踪和证据保全。

## 已实现模块

| 模块 | 实现位置 | 结果目录 |
| --- | --- | --- |
| 基础复现 | `watermark_anything/extensions/baseline_reproduction/run.py` | `results_output/baseline_reproduction` |
| 攻击基准 | `watermark_anything/extensions/attack_benchmark/run.py` | `results_output/attack_benchmark` |
| 空间冗余 | `watermark_anything/extensions/spatial_redundancy/` | `results_output/redundant_regions`, `results_output/distributed_layout`, `results_output/coverage_search` |
| 鲁棒性配置 | `watermark_anything/extensions/robustness_profiles/` | `results_output/strength_search`, `results_output/spatial_strength_profile` |
| 平台变换 | `watermark_anything/extensions/transform_profiles/platform_modes.py` | `results_output/platform_modes` |
| 篡改定位 | `watermark_anything/extensions/tamper_localization/localizer.py` | `results_output/tamper_localization` |
| 来源更新 | `watermark_anything/extensions/provenance_update/pipeline.py` | `results_output/provenance_update` |
| 多源溯源 | `watermark_anything/extensions/source_tracing/` | `results_output/source_tracing`, `results_output/source_tracing_redundant_id`, `results_output/source_tracing_codebook_match` |

## 主要结论

- 基础复现已跑通单水印和多水印推理，关键输出在 `results_output/baseline_reproduction/baseline_reproduction_metrics.csv`。
- 攻击基线显示强 JPEG、极端缩放、强裁剪和局部移除是主要薄弱场景。
- 空间冗余嵌入在强压缩和局部破坏下提供更稳定的恢复机会，但需要控制覆盖面积和视觉质量。
- 覆盖率搜索表明 `Q=30%` 更偏画质，`Q=50%` 更偏鲁棒。
- 强度搜索表明 `scaling_w=2.5` 和 `scaling_w=3.0` 是主要候选档位。
- 平台变换评估形成三档模式：质量优先、均衡鲁棒、安全优先。
- 篡改定位在覆盖区域内效果较好，覆盖外区域需要额外检测机制。
- 来源更新可以保留双消息，但图像质量会下降。
- 多源合成图溯源需要局部裁剪和重同步；码本匹配能提升来源匹配稳定性。

## 推荐主方案

```text
空间冗余嵌入 + 强度配置 + 平台变换评估
```

推荐三档配置：

| 模式 | 覆盖率 | 区域数 | 强度 | 使用场景 |
| --- | --- | --- | --- | --- |
| 质量优先 | 30% | 5 | 2.5 | 画质优先发布 |
| 均衡鲁棒 | 50% | 5 | 2.5 | 常规鲁棒认证 |
| 安全优先 | 50% | 5 | 3.0 | 强压缩和二次传播场景 |

## 素材归档说明

原先分散在过程记录、创新思路、结果索引和实验笔记中的内容，已经统一合并到本文档后续章节。这里保留原始记录的文字内容，后续写报告时可以直接从本文档筛选材料。

---

# 追加素材归档

下面内容由原先分散的过程记录、创新思路、结果索引和实验笔记合并而来，作为报告写作素材池保留。

---

## 原始素材：docs\integration_note.md

# 集成关系

```text
watermark_anything/  -> 模型包和扩展模块
assets/              -> 示例图片和 mask
configs/             -> 模型配置
checkpoints/         -> 参数和本地权重
notebooks/           -> 推理辅助工具
train.py             -> 训练入口
requirements.txt     -> 依赖清单
```

课程扩展模块位于：

```text
watermark_anything/extensions/
```

统一运行入口使用仓库根目录作为 `ProjectRoot`。

---

## 原始素材：docs\papers_and_ideas.md

# Papers And Ideas

## 主论文

### WAM: Watermark Anything with Localized Messages

- 角色：主论文和主工程代码。
- 使用方式：直接复用作者开源代码、官方参数和 MIT 权重。
- 我们改动：不改 WAM 模型结构，在外层改变嵌入区域、强度、攻击评测、消息编码和应用场景。

## 主创新来源

### DWSF

- 借鉴点：分散区域嵌入、面积比例 Q、块数量。
- 我们实现：把 WAM 的单区域水印扩展成多区域分散嵌入，并扫描 Q=10/20/25/30/50。
- 结论：Q=30% 是质量优先折中；Q=50% 是鲁棒优先模式。

### TrustMark

- 借鉴点：水印强度和视觉质量之间的可调权衡。
- 我们实现：扫描 WAM 的 `scaling_w`，并和 DWSF 区域策略组合。
- 结论：形成质量优先、均衡鲁棒、安全优先三档模式。

### Robust-Wide / FlexMark

- 借鉴点：真实编辑链路、平台压缩、WebP/JPEG、鲁棒-质量模式选择。
- 我们实现：对最终候选模式做 brightness/contrast/saturation/sharpness、JPEG、WebP、resize+JPEG 等实用变换评测。
- 结论：三档模式选择更合理，避免只给一个死参数。

## 附加安全应用来源

### EditGuard / OmniGuard

- 借鉴点：主动取证、篡改定位、局部完整性检测。
- 我们实现：通过水印检测概率下降定位局部篡改。
- 结论：覆盖区域内定位效果好，但不能定位未覆盖区域。

### TrustMark / WAM

- 借鉴点：re-watermarking、provenance update、多局部消息。
- 我们实现：空间分区追加第二条水印消息。
- 结论：非重叠分区能保留新旧两条消息，但牺牲 PSNR。

### MuST

- 借鉴点：多源合成图追踪、MER 重同步、素材 source ID。
- 我们实现：构造多源合成图，比较整图解码、素材框裁剪、MER resize 解码，并加入 ECC 和 codebook 匹配。
- 结论：无二次压缩时 MER 很有效；复杂三源压缩仍不稳定，适合作为附加分支。

## 探索和负结果来源

### MBRS / RoSteALS

- 借鉴点：JPEG 多分支、消息冗余、ECC。
- 我们实现：多分支 JPEG 解码、rep3/rep4、Hamming 和 codebook 识别。
- 结论：可作为辅助，不能单独当主创新。

### FIN / RAIMark

- 借鉴点：可逆噪声层、INR 分辨率无关。
- 我们判断：需要结构级训练，不适合在当前 WAM 官方权重上直接硬改。

---

## 原始素材：docs\process_overview.md

# 实验概览

## 基础复现

使用本地配置、示例图片和权重运行基础嵌入与提取流程。

## 攻击基准

评估压缩、缩放、裁剪、遮挡和局部移除等攻击。

## 空间冗余

评估多区域嵌入、分散布局、覆盖率搜索和区域同步。

## 鲁棒性配置

评估嵌入强度以及空间-强度组合在画质和鲁棒性之间的取舍。

## 平台变换

评估平台式图像变换，并筛选推荐运行模式。

## 安全应用

包含篡改定位、来源更新和多源溯源。

## 辅助模块

包含压缩恢复、载荷编码变体、自适应区域选择和区域同步变体。

---

## 原始素材：docs\project_structure.md

# 工程结构

仓库采用单工程结构，模型包、扩展模块、实验入口、生成结果和文档都放在同一个项目下。

## 根目录

- `watermark_anything/`：模型包和扩展模块。
- `assets/`：示例图片和 mask。
- `configs/`：模型配置文件。
- `checkpoints/`：本地参数文件和权重。
- `notebooks/`：推理辅助工具。
- `experiments/`：可复现实验入口。
- `tools/`：项目级工具命令。
- `results_output/`：生成的指标、汇总表和部分可视化结果。
- `experiment_notes/`：实验记录和结论。
- `logs/`：本地运行日志。
- `docs/`：技术说明、结果索引和报告素材。

## 实验入口

`experiments/` 下每个目录包含一个简短的 `README.md` 和一个 `run.ps1` 包装入口。真正的实现代码位于 `watermark_anything/extensions/`。

---

## 原始素材：docs\results_index.md

# 结果索引

## 主线实验

| 方向 | 输出目录 | 目的 |
| --- | --- | --- |
| 基础复现 | `results_output/baseline_reproduction` | 跑通基础嵌入和提取流程 |
| 攻击基准评测 | `results_output/attack_benchmark` | 建立 JPEG、resize、crop 等攻击下的基线 |
| 空间冗余嵌入 | `results_output/redundant_regions` | 比较单区域和多区域冗余的鲁棒性 |
| 空间布局分散 | `results_output/distributed_layout` | 测试固定多区域布局 |
| 覆盖率搜索 | `results_output/coverage_search` | 扫描覆盖面积和区域数量 |
| 强度搜索 | `results_output/strength_search` | 搜索嵌入强度与画质的取舍 |
| 空间-强度组合 | `results_output/spatial_strength_profile` | 组合多区域嵌入和强度调节 |
| 平台变换模式 | `results_output/platform_modes` | 评估常见平台编辑变换下的推荐模式 |
| 篡改定位 | `results_output/tamper_localization` | 定位被主动移除或破坏的区域 |
| 来源更新 | `results_output/provenance_update` | 测试再授权、分区覆盖和信息保留 |
| 多源素材溯源 | `results_output/source_tracing` | 在合成图中定位并恢复不同来源信息 |
| 冗余 ID 溯源 | `results_output/source_tracing_redundant_id` | 用短 ID 冗余增强多源溯源 |
| 码本匹配溯源 | `results_output/source_tracing_codebook_match` | 用注册码本提升来源匹配 |

## 辅助实验

| 方向 | 输出目录 | 目的 |
| --- | --- | --- |
| 压缩恢复 | `results_output/compression_recovery` | 测试 JPEG 压缩后的多分支候选恢复 |
| 重复载荷 | `results_output/repetition_payload` | 测试重复编码能否提升载荷恢复 |
| 编码变体 | `results_output/coding_variants` | 比较不同冗余编码方式 |
| 自适应区域选择 | `results_output/adaptive_selector` | 测试按图像内容选择嵌入区域 |
| 区域同步 | `results_output/region_sync` | 测试裁剪后区域重同步解码 |

---

## 原始素材：experiment_notes\adaptive_selector.md

# 自适应区域选择 v1

## 目的

这轮尝试把 DWSF 的分散嵌入与 OmniGuard/WAM/TrustMark 中的感知质量思想结合：不再固定四角 + 中心，而是在同样 `Q=30%, 5 blocks, scaling_w=2.5` 条件下，根据图像内容选择水印区域。

要验证的问题是：内容自适应选择是否能在保持 DWSF 鲁棒性的同时进一步改善画质，或者改善某些裁剪/压缩攻击。

## 论文来源

- DWSF：分散嵌入、稀疏块、同一消息重复嵌入。
- OmniGuard：localized watermark 可以通过 content-aware texture 改善隐藏质量。
- WAM：JND / HVS 思想强调亮度与对比度掩蔽，高纹理区域对扰动更不敏感。
- TrustMark：强调 watermark quality 与 recovery 的权衡。

## 实验设置

- 脚本：`watermark_anything\extensions\region_selection/adaptive_selector.py`。
- 输出：`results_output/adaptive_selector/`。
- 主模型：WAM 官方 MIT 权重。
- 图像：WAM 官方 5 张示例图。
- 水印：固定随机 32-bit 消息。
- 固定变量：
  - `Q=30%`
  - `5 blocks`
  - `scaling_w=2.5`
- selector：
  - `fixed_anchor`：固定四角 + 中心。
  - `random`：从候选网格随机选择不重叠块。
  - `texture_top`：选择局部梯度/纹理最高的块。
  - `low_residual`：先生成全图水印，选择水印残差 MSE 最低的块。
  - `hybrid_texture_residual`：纹理高 + 残差低的加权组合。
- 攻击：
  - none
  - remove_center_40
  - black_center_40
  - crop_top_left_50
  - crop_bottom_right_50
  - crop_center_50
  - jpeg_q30
  - jpeg_q20
  - resize_0.25_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\region_selection/adaptive_selector.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\adaptive_selector `
  --limit 5 `
  --scale 2.5 `
  --area 30 `
  --block-count 5 `
  --grid 11
```

## 关键结果

总计 225 条逐图逐攻击记录，stderr 为空。

overview：

| scheme | selector | PSNR | selected attack mean | worst selected attack |
|---|---|---:|---:|---:|
| adaptive_q30_5block_hybrid_texture_residual | hybrid_texture_residual | 41.0139 | 0.948438 | 0.881250 |
| fixed_q30_5block | fixed_anchor | 42.0139 | 0.945312 | 0.906250 |
| adaptive_q30_5block_texture_top | texture_top | 40.1578 | 0.935937 | 0.731250 |
| adaptive_q30_5block_random | random | 41.5479 | 0.912500 | 0.706250 |
| adaptive_q30_5block_low_residual | low_residual | 43.6530 | 0.890625 | 0.675000 |

细项：

| attack | fixed_anchor | hybrid_texture_residual | low_residual | texture_top |
|---|---:|---:|---:|---:|
| crop_top_left_50 | 0.906250 | 0.925000 | 0.925000 | 0.956250 |
| crop_bottom_right_50 | 0.956250 | 0.950000 | 0.943750 | 0.981250 |
| crop_center_50 | 0.931250 | 0.968750 | 0.868750 | 0.950000 |
| jpeg_q20 | 0.906250 | 0.881250 | 0.675000 | 0.731250 |
| resize_0.25_jpeg_q50 | 0.950000 | 0.943750 | 0.900000 | 0.937500 |

## 判断

这轮不能作为最终主创新。

1. `hybrid_texture_residual` 的平均攻击准确率 0.948438 略高于固定布局 0.945312，但 PSNR 从 42.0139 降到 41.0139，worst selected attack 从 0.906250 降到 0.881250。收益太小，代价更明显。
2. `low_residual` 确实把 PSNR 提到 43.6530，但强 JPEG 与 resize+JPEG 明显退化，selected attack mean 只有 0.890625。说明只按残差最小选区域会选到水印信号弱、解码不稳的位置。
3. `texture_top` 对部分裁剪有帮助，但强 JPEG 崩得更明显，PSNR 也不如固定布局。
4. `random` 不稳定，作为 DWSF 原始思想的随机性参考可以保留，但不适合当默认策略。

## 保留价值

- 这是一轮有效的负结果：简单内容自适应区域选择不应替代当前 `Q=30%, 5 blocks` 固定布局。
- 可以在报告中作为“尝试过但淘汰”的创新探索，说明我们不是只挑好结果。
- 如果后续还有时间，可进一步做更严格的 perceptual metric 或训练式选择器；但在当前课程大作业范围内，不建议继续深挖这个分支。

## 输出文件

- `results_output/adaptive_selector/adaptive_selector_metrics.csv`
- `results_output/adaptive_selector/adaptive_selector_regions.csv`
- `results_output/adaptive_selector/adaptive_selector_summary.csv`
- `results_output/adaptive_selector/adaptive_selector_overview.csv`

---

## 原始素材：experiment_notes\attack_benchmark.md

# WAM 攻击评测基线

## 目标

在 WAM 官方流程跑通后，构建一套后续改进实验可复用的攻击评测基线，用来衡量原始 WAM 在不同失真/攻击下的消息恢复能力。

## 实验设置

- 主论文模型：WAM / Watermark Anything
- 权重：`wam_mit.pth`
- 环境：`bamboo`，RTX 4060 Laptop GPU
- 测试图像：官方 `assets/images` 中 5 张示例图
- 嵌入方式：单条 32-bit 消息，随机 50% 区域保留水印
- 固定消息：

```text
01001001101000111101110000000011
```

## 攻击类型

本轮攻击评测包含：

- no attack
- JPEG：Q=95/85/75/65/50/30
- Resize：0.75/0.5/0.25 后恢复原分辨率
- Center crop：0.9/0.75/0.5 后恢复原分辨率
- Random crop：0.9/0.75/0.5 后恢复原分辨率
- Local occlusion：遮挡 5%/10%/20% 面积
- Partial removal：将 5%/10%/20% 区域替换回原图内容，模拟局部水印移除

## 输出文件

- 评测脚本：`watermark_anything\extensions\attack_benchmark/run.py`
- 逐样本指标：`results_output\attack_benchmark\attack_benchmark_metrics.csv`
- 按攻击汇总：`results_output\attack_benchmark\attack_benchmark_summary.csv`
- 本地可视化目录：`results_output\attack_benchmark\visuals`

说明：批量攻击可视化 PNG 文件体积较大，仅本地保留，不全部提交到 git。后续需要报告配图时再挑选代表样例压缩整理。

## 汇总结果

| 攻击 | 平均 bit accuracy | 最低 bit accuracy | 图像数 |
|---|---:|---:|---:|
| none | 1.000000 | 1.000000 | 5 |
| jpeg_q95 | 1.000000 | 1.000000 | 5 |
| jpeg_q85 | 0.993750 | 0.968750 | 5 |
| jpeg_q75 | 0.987500 | 0.937500 | 5 |
| jpeg_q65 | 0.993750 | 0.968750 | 5 |
| jpeg_q50 | 0.968750 | 0.875000 | 5 |
| jpeg_q30 | 0.925000 | 0.781250 | 5 |
| resize_0.75 | 1.000000 | 1.000000 | 5 |
| resize_0.5 | 1.000000 | 1.000000 | 5 |
| resize_0.25 | 0.962500 | 0.812500 | 5 |
| center_crop_0.9 | 1.000000 | 1.000000 | 5 |
| center_crop_0.75 | 1.000000 | 1.000000 | 5 |
| center_crop_0.5 | 0.950000 | 0.906250 | 5 |
| random_crop_0.9 | 1.000000 | 1.000000 | 5 |
| random_crop_0.75 | 1.000000 | 1.000000 | 5 |
| random_crop_0.5 | 0.987500 | 0.968750 | 5 |
| occlusion_0.05 | 1.000000 | 1.000000 | 5 |
| occlusion_0.1 | 1.000000 | 1.000000 | 5 |
| occlusion_0.2 | 1.000000 | 1.000000 | 5 |
| partial_removal_0.05 | 1.000000 | 1.000000 | 5 |
| partial_removal_0.1 | 1.000000 | 1.000000 | 5 |
| partial_removal_0.2 | 1.000000 | 1.000000 | 5 |

## 暴露出的弱点

当前 WAM baseline 的主要弱点集中在：

- 强 JPEG 压缩：`jpeg_q30` 平均 0.925，最低 0.78125。
- 极端 resize：`resize_0.25` 平均 0.9625，最低 0.8125。
- 强中心裁剪：`center_crop_0.5` 平均 0.95，最低 0.90625。
- 个别图像在 JPEG Q=50/75/85 也会出现少量 bit 错误。

这说明后续改进应重点关注：

- MBRS 式 JPEG 鲁棒增强或多次解码策略。
- DWSF 式多区域冗余嵌入与融合，用来提升裁剪、极端缩放和局部破坏后的恢复率。
- TrustMark 式水印强度与图像质量权衡，观察是否能在不明显牺牲 PSNR 的情况下提升强攻击恢复率。

## 当前结论

WAM baseline 已经具备较强基础鲁棒性，但在强 JPEG、极端缩放、强裁剪下仍有可优化空间。这些弱点与 DWSF、MBRS、TrustMark 等论文的思想可以自然衔接，适合作为后续创新优化的目标。

---

## 原始素材：experiment_notes\baseline_reproduction.md

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

- WAM 官方代码目录：`.`
- 权重：`checkpoints\wam_mit.pth`
- 权重来源：`https://dl.fbaipublicfiles.com/watermark_anything/wam_mit.pth`
- 权重大小：377,825,938 bytes
- 权重 SHA256：`90ef232384e023bd63245eb0c131abd69d2afc7b8f17a71ccedceb542bf009e2`
- 参数文件：`checkpoints\params.json`
- 复现脚本：`watermark_anything\extensions\baseline_reproduction/run.py`

## 运行命令

```powershell
& "C:\Users\86155\miniconda3\envs\bamboo\python.exe" `
  "C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务\watermark_anything\extensions\baseline_reproduction/run.py" `
  --wam-root "." `
  --checkpoint ".\checkpoints\wam_mit.pth" `
  --params ".\checkpoints\params.json" `
  --image-dir ".\assets\images" `
  --out-dir "C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务\results_output\baseline_reproduction" `
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

指标文件：`results_output\baseline_reproduction\baseline_reproduction_metrics.csv`

| 模式 | 图像 | bit accuracy | PSNR | 检测到的消息数 |
|---|---|---:|---:|---:|
| single | alpaca.jpg | 1.000000 | 38.8986 | - |
| single | ducks.jpg | 1.000000 | 43.1886 | - |
| single | gauguin_256.jpg | 1.000000 | 42.0654 | - |
| multi | alpaca.jpg | 1.000000 | 42.3100 | 2 |
| multi | ducks.jpg | 1.000000 | 46.1306 | 2 |
| multi | gauguin_256.jpg | 1.000000 | 45.8596 | 2 |

## 输出文件

- 可视化输出目录：`results_output\baseline_reproduction\visuals`
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

---

## 原始素材：experiment_notes\coding_variants.md

# ECC 编码变体 v1

## 目的

上一轮 ECC 只比较了 uncoded10 与 rep3_10，结果显示重复编码能显著提升部分裁剪和 resize+JPEG 的 payload 成功率，但对强 JPEG Q=20 不稳定。本轮进一步比较多种轻量纠错/交织方案，判断是否存在更适合默认 `DWSF Q=30%, 5 blocks` 方案的 payload 编码。

## 论文来源

- RoSteALS：报告 Bit acc. (ECC)，使用 BCH/cyclic error correction code，说明纠错码能显著改善部分 noised data 的 secret recovery。
- MBRS：message processor 用于扩展 message 并实现冗余。
- TrustMark：真实使用场景是 provenance payload，需要关注 payload 级恢复，而不仅是 full bit accuracy。

## 实验设置

- 脚本：`watermark_anything\extensions\payload_coding/coding_variants.py`。
- 输出：`results_output/coding_variants/`。
- 主模型：WAM 官方 MIT 权重。
- 主方案：`DWSF Q=30%, 5 blocks, scaling_w=2.5`。
- 图像：WAM 官方 5 张示例图。
- payload：固定随机 10-bit payload。
- coding：
  - `uncoded10`
  - `rep3_adjacent10`
  - `rep3_interleaved10`
  - `hamming74_10`
  - `hamming74_interleaved10`
- 攻击：
  - none
  - crop_bottom_right_50
  - crop_center_50
  - jpeg_q30
  - jpeg_q20
  - resize_0.25_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\payload_coding/coding_variants.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\coding_variants `
  --limit 5 `
  --scale 2.5 `
  --area 30 `
  --block-count 5
```

## 关键结果

总计 150 条逐图逐攻击记录，stderr 为空。

overview：

| coding | mean selected payload success | worst selected payload success |
|---|---:|---:|
| rep3_interleaved10 | 0.760000 | 0.400000 |
| uncoded10 | 0.760000 | 0.400000 |
| rep3_adjacent10 | 0.760000 | 0.600000 |
| hamming74_10 | 0.760000 | 0.600000 |
| hamming74_interleaved10 | 0.760000 | 0.600000 |

逐攻击 success rate：

| attack | uncoded10 | rep3_adjacent10 | rep3_interleaved10 | hamming74_10 | hamming74_interleaved10 |
|---|---:|---:|---:|---:|---:|
| crop_bottom_right_50 | 0.400000 | 0.600000 | 0.800000 | 0.600000 | 0.600000 |
| crop_center_50 | 1.000000 | 1.000000 | 1.000000 | 0.800000 | 1.000000 |
| jpeg_q30 | 0.800000 | 0.800000 | 0.800000 | 0.800000 | 0.800000 |
| jpeg_q20 | 0.600000 | 0.600000 | 0.400000 | 0.600000 | 0.600000 |
| resize_0.25_jpeg_q50 | 1.000000 | 0.800000 | 0.800000 | 1.000000 | 0.800000 |

## 判断

这轮没有产生新的主线级改进。

1. 五种编码的 mean selected payload success 都是 0.760000，说明在 `Q=30%` 默认方案下，轻量 ECC 不能显著提升整体 payload 成功率。
2. `rep3_adjacent10`、`hamming74_10`、`hamming74_interleaved10` 能把 worst selected payload success 从 0.400000 提升到 0.600000，说明它们能降低最差攻击下的风险。
3. `rep3_interleaved10` 对 `crop_bottom_right_50` 最好，success 0.800000，但对 `jpeg_q20` 降到 0.400000，不稳定。
4. `hamming74_10` 在 `resize_0.25_jpeg_q50` 保持 1.000000，且 `jpeg_q20` 不比 uncoded 差；如果要保留一个“轻量 ECC 可选模式”，它比交织重复更稳。
5. 该结果与上一轮 `Q=50%` 下 rep3 明显提升不同，说明 ECC 的效果依赖底层嵌入强度/面积。默认 `Q=30%` 更偏低扰动，强 JPEG 错误可能超过轻量码纠错能力。

## 保留价值

- 不建议把 ECC 变体作为最终主创新。
- 可作为可选模块：默认方案使用 `Q=30%, 5 blocks`，若用户更关心 payload 最差成功率，可加 `hamming74_10`，代价是有效载荷容量下降到 10 bit。
- 报告里可以将它写成“来自 MBRS/RoSteALS 的消息冗余探索，实验证明只能稳住最差情况，不能根本解决强 JPEG”。

## 输出文件

- `results_output/coding_variants/coding_variants_metrics.csv`
- `results_output/coding_variants/coding_variants_summary.csv`
- `results_output/coding_variants/coding_variants_overview.csv`

---

## 原始素材：experiment_notes\compression_recovery.md

# MBRS 式多分支 JPEG 解码 v1

## 目的

WAM 攻击基线显示，强 JPEG 和 resize+JPEG 是明显弱点之一。本实验借鉴 MBRS 的 real JPEG / simulated JPEG / identity 混合思想，但不重训模型，而是在 WAM 推理阶段构造多个预处理分支，再借鉴 DWSF 的消息相似性/置信度思想选择最终解码结果。

这个实验的目标不是替代 MBRS 的训练策略，而是验证：在不重训、只做推理增强的条件下，多分支 JPEG 预处理是否能提升 WAM 的强压缩恢复率。

## 论文依据

MBRS 的关键思想：

- real JPEG 分支让 decoder 学会真实 JPEG 后的特征恢复。
- simulated JPEG-Mask 分支提供可传播的 JPEG 近似。
- identity 分支保证无压缩时的正常解码能力。
- 三者混合可以避免只适配模拟失真或只适配无失真。

DWSF 的可迁移思想：

- 多个候选解码结果之间可以通过消息相似性过滤离群结果，得到最终消息。

## 脚本

- 脚本：`watermark_anything\extensions\compression_recovery/multi_branch_decode.py`
- 输出目录：`results_output/compression_recovery/`
- 候选分支文件：`results_output/compression_recovery/compression_recovery_candidates.csv`
- 方法对比文件：`results_output/compression_recovery/compression_recovery_methods.csv`
- 汇总文件：`results_output/compression_recovery/compression_recovery_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\watermark_anything\extensions\compression_recovery/multi_branch_decode.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\results_output\compression_recovery" `
  --limit 5
```

## 实验设置

- 数据：WAM 官方 `assets/images` 中 5 张示例图。
- 消息长度：32 bit。
- baseline：攻击后直接 WAM detect/decode。
- 多分支候选：
  - identity
  - real_jpeg_q90 / real_jpeg_q70 / real_jpeg_q50
  - JPEG-Mask-like DCT low-pass：keep10 / keep8 / keep6 / keep4
- 选择策略：
  - `mbrs_confidence_select`：选择解码置信度最高的候选分支。
  - `mbrs_similarity_select`：按候选消息相似性选择一致性最高的分支。
  - `oracle_best_branch`：使用真实消息选择最优分支，只作为上界分析，不是实际可用方法。

## 关键结果

| attack | baseline mean/min | confidence mean/min | similarity mean/min | oracle mean/min | 判断 |
|---|---:|---:|---:|---:|---|
| jpeg_q95 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 持平 |
| jpeg_q85 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 持平 |
| jpeg_q75 | 0.993750 / 0.968750 | 0.993750 / 0.968750 | 0.993750 / 0.968750 | 0.993750 / 0.968750 | 持平 |
| jpeg_q65 | 0.975000 / 0.875000 | 0.975000 / 0.875000 | 0.975000 / 0.875000 | 0.981250 / 0.906250 | 有上界潜力，选择器未吃到 |
| jpeg_q50 | 0.968750 / 0.843750 | 0.968750 / 0.843750 | 0.968750 / 0.843750 | 0.975000 / 0.875000 | 有上界潜力，选择器未吃到 |
| jpeg_q30 | 0.962500 / 0.812500 | 0.962500 / 0.812500 | 0.962500 / 0.812500 | 0.962500 / 0.812500 | 持平 |
| jpeg_q20 | 0.850000 / 0.500000 | 0.868750 / 0.593750 | 0.868750 / 0.593750 | 0.881250 / 0.593750 | 小幅提升 |
| resize_0.75_jpeg_q50 | 0.962500 / 0.812500 | 0.968750 / 0.843750 | 0.962500 / 0.812500 | 0.981250 / 0.906250 | 小幅提升 |
| resize_0.5_jpeg_q50 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.981250 / 0.906250 | 0.987500 / 0.937500 | 选择器未吃到 |
| resize_0.25_jpeg_q50 | 0.943750 / 0.718750 | 0.943750 / 0.718750 | 0.943750 / 0.718750 | 0.950000 / 0.750000 | 基本持平 |
| jpeg_q50_then_q30 | 0.956250 / 0.781250 | 0.956250 / 0.781250 | 0.956250 / 0.781250 | 0.962500 / 0.812500 | 选择器未吃到 |

## 结论

v1 只能算小幅正向，不足以作为最终主创新。

正向部分：

- `jpeg_q20` 从 mean/min 0.850000/0.500000 提升到 0.868750/0.593750。
- `resize_0.75_jpeg_q50` 的 confidence select 从 0.962500/0.812500 提升到 0.968750/0.843750。
- 候选分支确实提供了部分更优解码结果，oracle 在 `jpeg_q65`、`jpeg_q50`、`resize_0.75_jpeg_q50` 等场景更高。

负向部分：

- 当前无监督选择器不够可靠，很多 oracle 能提升的场景没有被 confidence 或 similarity selector 选中。
- 对 `jpeg_q30`、`resize_0.25_jpeg_q50` 等关键弱点基本无改善。
- 仅做推理侧多分支，无法替代 MBRS 的训练侧 real JPEG / simulated JPEG / identity 混合鲁棒学习。

后续判断：

1. 该方向可以作为辅助实验，说明“多分支真实/模拟 JPEG 解码有有限帮助，但没有训练配合时收益有限”。
2. 不建议把 MBRS 式推理增强单独作为最终大创新。
3. 下一步更值得做 TrustMark 式强度-质量权衡：直接改变嵌入残差强度，测试是否能提升强 JPEG 和极端 resize 下的 bit accuracy，并与 DWSF 分散冗余结合。

---

## 原始素材：experiment_notes\coverage_search.md

# DWSF 面积比例扫描 v1

## 目的

这轮不是另起炉灶，而是回到 DWSF 论文中明确讨论过的变量：分散嵌入的总面积比例 Q 和块数上限。DWSF 主论文设置为 Q=25%、最多 20 个块，并在附录中说明更大的 Q 通常带来更高 bit accuracy，但会降低 PSNR；Q 太小则在强几何攻击下鲁棒性不足。

我们之前的 WAM+DWSF 方案实际使用 5 个区域、每个 10%，总面积约 50%，偏鲁棒优先。此实验用于判断是否存在更好的质量-鲁棒性折中点。

## 论文来源

- DWSF: Practical Deep Dispersed Watermarking with Synchronization and Fusion, ACM MM 2023。
- 借鉴点：总嵌入面积比例 Q、分散块数、稀疏嵌入带来的视觉质量与鲁棒性权衡。

## 实验设置

- 主模型：WAM 官方 MIT 权重。
- 运行环境：`bamboo` conda 环境，RTX 4060 Laptop GPU。
- 脚本：`watermark_anything\extensions\spatial_redundancy/coverage_search.py`。
- 输出：`results_output/coverage_search/`。
- 图像：WAM 官方 5 张示例图。
- 水印消息：固定随机 32-bit 消息。
- 强度：`scaling_w=2.5`。
- baseline：`single_center_50pct`，中心 50% 单区域水印。
- DWSF variants：
  - `Q=10/20/25/30/50`
  - `5 blocks` 与 `9 blocks`
  - 每个块嵌入同一消息。
- 攻击：
  - none
  - remove_center_40
  - black_center_40
  - crop_top_left_50
  - crop_bottom_right_50
  - crop_center_50
  - jpeg_q30
  - jpeg_q20
  - resize_0.25_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\spatial_redundancy/coverage_search.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\coverage_search `
  --limit 5 `
  --scale 2.5 `
  --areas 10 20 25 30 50 `
  --block-counts 5 9
```

## 关键结果

总计 495 条逐图逐攻击记录，stderr 为空。

overview：

| scheme | PSNR | selected attack mean | worst selected attack |
|---|---:|---:|---:|
| dwsf_q50_5block | 39.7612 | 0.968750 | 0.875000 |
| dwsf_q50_9block | 39.4684 | 0.964844 | 0.893750 |
| dwsf_q30_5block | 42.0691 | 0.957812 | 0.887500 |
| single_center_50pct | 39.1467 | 0.948438 | 0.737500 |
| dwsf_q25_5block | 42.9056 | 0.947656 | 0.868750 |
| dwsf_q20_5block | 43.9523 | 0.919531 | 0.812500 |
| dwsf_q10_5block | 47.2094 | 0.815625 | 0.618750 |

细项：

| attack | single_center_50pct | dwsf_q30_5block | dwsf_q50_5block |
|---|---:|---:|---:|
| remove_center_40 | 1.000000 | 1.000000 | 1.000000 |
| black_center_40 | 1.000000 | 1.000000 | 1.000000 |
| crop_top_left_50 | 1.000000 | 0.937500 | 0.962500 |
| crop_bottom_right_50 | 0.975000 | 0.962500 | 0.987500 |
| crop_center_50 | 1.000000 | 0.968750 | 1.000000 |
| jpeg_q30 | 0.943750 | 0.937500 | 0.943750 |
| jpeg_q20 | 0.737500 | 0.887500 | 0.875000 |
| resize_0.25_jpeg_q50 | 0.931250 | 0.968750 | 0.981250 |

## 判断

1. `Q=10%` 虽然 PSNR 高，但鲁棒性明显不足，不能作为主方案。
2. `Q=25%` 最接近 DWSF 原论文默认设置，PSNR 达 42.9056，但 selected attack mean 仅 0.947656，略低于单区域 0.948438；它可以作为“低扰动版本”，不适合作为最终最强版本。
3. `Q=30%, 5 blocks` 是更好的折中：PSNR 42.0691，比单区域 39.1467 高约 2.92 dB；selected attack mean 0.957812，高于单区域 0.948438；worst selected attack 0.887500，也明显高于单区域 0.737500。
4. `Q=50%, 5 blocks` 仍是鲁棒优先候选：selected attack mean 0.968750 最高，PSNR 39.7612 也略高于单区域 39.1467。
5. 9 blocks 在这套 WAM masking 实现下没有稳定优于 5 blocks，可能因为块更碎后每个局部区域可用于解码的信息不足，或者 WAM 的检测/消息聚合没有针对细碎块训练。
6. DWSF 面积扫描不能包装成全攻击胜利：在 `crop_top_left_50` 和部分中心裁剪上，单中心方案仍更强；DWSF 的主要收益在强 JPEG 最差情况和 resize+JPEG 组合攻击上更明显。

## 保留价值

这轮可以作为最终方案里的一个扎实消融：

- 主创新从“固定 50% 五区域”进一步变成“DWSF 面积比例可调 + TrustMark 强度可调”的二维质量-鲁棒权衡。
- 推荐默认方案可以写成 `Q=30%, 5 blocks, scaling_w=2.5`：比单区域更高 PSNR、更高平均鲁棒性，也避免 50% 面积带来的过重嵌入。
- 鲁棒优先模式仍可保留 `Q=50%, 5 blocks, scaling_w=2.5`。

## 输出文件

- `results_output/coverage_search/coverage_search_metrics.csv`
- `results_output/coverage_search/coverage_search_summary.csv`
- `results_output/coverage_search/coverage_search_overview.csv`

---

## 原始素材：experiment_notes\distributed_layout.md

# DWSF 式空间分散冗余 v2

## 目的

v1 使用随机多区域重复嵌入，结果不稳定。v2 改为更明确的 DWSF-style 空间分散设计：将同一 32-bit 消息嵌入四角和中心共 5 个区域，每个区域约占图像 10%，总水印面积约为 50%，与单中心 50% 区域方案控制在相近嵌入面积。

本实验重点验证：当攻击是局部大块破坏、中心区域移除、半图移除或 50% 裁剪时，空间分散是否能比单中心区域更稳。

## 脚本

- 脚本：`watermark_anything\extensions\spatial_redundancy/distributed_layout.py`
- 输出目录：`results_output/distributed_layout/`
- 指标文件：`results_output/distributed_layout/distributed_layout_metrics.csv`
- 汇总文件：`results_output/distributed_layout/distributed_layout_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\watermark_anything\extensions\spatial_redundancy/distributed_layout.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\results_output\distributed_layout" `
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

---

## 原始素材：experiment_notes\platform_modes.md

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

---

## 原始素材：experiment_notes\provenance_update.md

# 二次水印空间分区 v1

## 目的

这轮来自 TrustMark 的 re-watermarking / provenance update 场景，以及 WAM 的 multiple watermark extraction 能力。目标是验证：当一张图已经带有旧版权/来源消息 A 时，后续需要追加新来源消息 B，DWSF 式空间分区是否比直接覆盖同一区域更能保留新旧两条消息。

## 论文来源

- TrustMark：讨论 provenance metadata 更新、re-watermarking，以及直接重复加水印会带来质量与水印生命周期问题。
- WAM：支持同一图像中的多个 localized watermark，并用 mask/DBSCAN/局部解码提取多个消息。
- DWSF：分散块提供天然的空间分区载体，可把不同消息放在不同块组中，减少互相覆盖。

## 实验设置

- 脚本：`watermark_anything\extensions\provenance_update/provenance_update.py`。
- 输出：`results_output/provenance_update/`。
- 主模型：WAM 官方 MIT 权重。
- 图像：WAM 官方 5 张示例图。
- 强度：`scaling_w=2.5`。
- 消息：
  - 旧消息 `msg_a`
  - 新消息 `msg_b`
- 方案：
  - `overlap_replace_same_region`：A 先放入 `Q=30%, 5 blocks`，B 再覆盖同一组区域。
  - `disjoint_append_side_regions`：A 放入 `Q=30%, 5 blocks`，B 追加到不重叠的四个 side-mid 区域，总新增面积约 24%。
- 解码：
  - 为避免 WAM 官方 DBSCAN 在大候选像素下过慢，使用已知 slot mask 做局部解码。
  - overlap 方案 A/B 槽位相同；disjoint 方案 A/B 槽位不同。
- 攻击：
  - none
  - jpeg_q50
  - resize_0.5_jpeg_q50

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\provenance_update/provenance_update.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\provenance_update `
  --limit 5 `
  --scale 2.5
```

## 关键结果

总计 30 条逐图逐攻击记录，stderr 为空。

overview：

| scheme | mean A accuracy | mean B accuracy | both success rate | PSNR |
|---|---:|---:|---:|---:|
| disjoint_append_side_regions | 0.966667 | 0.952083 | 0.800000 | 39.0893 |
| overlap_replace_same_region | 0.522917 | 0.958333 | 0.000000 | 42.0668 |

逐攻击：

| scheme | attack | A accuracy | B accuracy | both success |
|---|---|---:|---:|---:|
| disjoint_append_side_regions | none | 1.000000 | 1.000000 | 1.000000 |
| disjoint_append_side_regions | jpeg_q50 | 0.950000 | 0.925000 | 0.600000 |
| disjoint_append_side_regions | resize_0.5_jpeg_q50 | 0.950000 | 0.931250 | 0.800000 |
| overlap_replace_same_region | none | 0.531250 | 1.000000 | 0.000000 |
| overlap_replace_same_region | jpeg_q50 | 0.518750 | 0.950000 | 0.000000 |
| overlap_replace_same_region | resize_0.5_jpeg_q50 | 0.518750 | 0.925000 | 0.000000 |

## 判断

这轮是可保留的安全场景分支。

1. 同区域覆盖更新会保留新消息 B，但旧消息 A 基本被覆盖掉；both success 始终为 0。
2. 空间分区追加可以同时保留 A/B：无攻击下 both success 为 1.0，JPEG Q=50 下为 0.6，resize+JPEG 下为 0.8。
3. 空间分区的代价是更大水印面积，PSNR 从 overlap 的 42.0668 降到 39.0893。
4. 这个分支不适合作为默认低扰动方案，但适合作为 provenance update / 多阶段授权 / 多方溯源的安全优先模式。

## 保留价值

- 与信息安全课程中的认证、溯源和完整性管理相关。
- 可以作为 WAM+DWSF 主方案的第二个附加创新：不只鲁棒恢复单一版权消息，还支持空间隔离的多消息生命周期管理。
- 报告中必须写清楚代价：为了保留多条消息，需要牺牲 PSNR 和可用嵌入面积。

## 输出文件

- `results_output/provenance_update/provenance_update_metrics.csv`
- `results_output/provenance_update/provenance_update_summary.csv`
- `results_output/provenance_update/provenance_update_overview.csv`

---

## 原始素材：experiment_notes\redundant_regions.md

# DWSF 式多区域冗余融合 v1

## 来源论文思想

来源：DWSF（Practical Deep Dispersed Watermarking with Synchronization and Fusion）。

DWSF 的核心思想包括：

- 将同一水印消息分散嵌入多个区域，避免单一区域被裁剪或破坏后无法恢复。
- 检测/定位水印区域后再解码。
- 对多个区域的解码结果进行融合，提高最终消息恢复可靠性。

## 实现方案

本轮实现了一个 WAM 上的 DWSF-style 原型：

- baseline：单区域 WAM，随机 50% 区域嵌入一条 32-bit 消息。
- dwsf_redundant_regions：5 个随机不重叠区域，每个区域 10%，重复嵌入同一条 32-bit 消息，总水印面积约等于 baseline。
- 解码方式：
  - `global_mask_average`：WAM 原始全局 mask 平均解码。
  - `component_majority`：对预测水印 mask 做连通区域分割，每个组件独立解码后多数投票。
  - `component_confidence_weighted`：对组件解码结果按置信度和组件像素数加权融合。

脚本：`watermark_anything\extensions\spatial_redundancy/redundant_regions.py`

输出：

- `results_output\redundant_regions\redundant_regions_metrics.csv`
- `results_output\redundant_regions\redundant_regions_summary.csv`

## 实验结果概述

本轮结果是混合的，不能直接包装成成功改进。

主要观察：

- 无攻击、轻度 resize、轻中度裁剪、遮挡、partial removal 下，baseline 和 DWSF 冗余方案大多都能达到 1.0。
- `random_crop_0.5` 下，DWSF 冗余方案的最低 bit accuracy 从 baseline 的 0.9375 提升到 0.96875，但平均值略低。
- `jpeg_q30` 下，DWSF 冗余全局解码最低值从 0.71875 提升到 0.75，但平均值基本不变；组件置信融合反而退化。
- JPEG Q=50、Q=65 和强中心裁剪下，多区域方案出现明显退化。

## 失败/不足分析

第一版方案没有稳定提升，原因可能是：

- 每个冗余区域只有 10%，比 baseline 的 50% 单区域可用像素少，强 JPEG 下单区域信号更弱。
- WAM 的 detection mask 本身已经会在像素级聚合信息，组件级拆分反而可能丢失全局统计优势。
- 当前攻击集里很多攻击并不会“定点摧毁一个大区域”，baseline 的 50% 单区域也能幸存，因此 DWSF 的分散优势没有充分体现。
- DWSF 的同步/融合思想更适合裁剪、局部破坏、区域丢失这类场景，而不是所有攻击通吃。

## 下一步修正方向

不要把 v1 作为最终创新。下一步继续围绕 DWSF 思想做更贴合场景的实验：

1. 构造更强的局部破坏攻击，例如 40%/60% 的局部遮挡、局部水印移除、corner crop。
2. 比较单大区域 vs 多分散区域在“局部大块破坏”下的消息存活率。
3. 尝试规则化区域布局，例如网格/四角+中心，而不是完全随机区域，增强空间分散性。
4. 保留 `global_mask_average` 作为主要解码方式，组件融合只作为消融，不强行作为最佳方案。

## 当前结论

DWSF 式多区域冗余在 WAM 上有可实现性，但 v1 方案不是稳定正向改进。它暴露了一个重要事实：多区域冗余要在“局部区域丢失/破坏”场景下验证，而不是指望它无条件提升 JPEG 或所有几何攻击。后续需要重做更贴合 DWSF 适用场景的 v2。

---

## 原始素材：experiment_notes\region_sync.md

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

- 脚本：`watermark_anything\extensions\spatial_redundancy/region_sync.py`
- 输出目录：`results_output/region_sync/`
- 候选文件：`results_output/region_sync/region_sync_candidates.csv`
- 方法文件：`results_output/region_sync/region_sync_methods.csv`
- 汇总文件：`results_output/region_sync/region_sync_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\watermark_anything\extensions\spatial_redundancy/region_sync.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\results_output\region_sync" `
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

---

## 原始素材：experiment_notes\repetition_payload.md

# ECC 消息冗余编码 v1

## 目的

TrustMark 论文提到非完美 bit accuracy 可以通过 error correcting code 改善；MBRS 论文也提出 message processor 来扩展消息并实现冗余。本实验在不改 WAM 网络的前提下，在 32-bit 消息层实现简单的 payload 冗余编码，验证“容量换鲁棒性”是否有效。

为了公平比较，本实验固定有效 payload 为 10 bit：

- `uncoded10`：直接将 10-bit payload 放入 32-bit 消息前 10 位，其余为随机填充。
- `rep3_10`：将每个 payload bit 重复 3 次，占 30 位，剩余 2 位填充；解码时对每组三重复位做多数投票。

## 脚本

- 脚本：`watermark_anything\extensions\payload_coding/repetition_payload.py`
- 输出目录：`results_output/repetition_payload/`
- 明细文件：`results_output/repetition_payload/repetition_payload_metrics.csv`
- 汇总文件：`results_output/repetition_payload/repetition_payload_summary.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\watermark_anything\extensions\payload_coding/repetition_payload.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\results_output\repetition_payload" `
  --limit 5
```

## 实验设置

- 主方案：`dwsf_5region_spatial`
- 强度：`scaling_w=2.5` 和 `3.0`
- 有效 payload：10 bit
- 攻击：
  - none
  - crop_bottom_right_50
  - crop_center_50
  - JPEG Q=30/20
  - resize 0.25 + JPEG Q=50

## 关键结果

| scaling_w | coding | attack | mean payload acc | payload success rate | mean full bit acc |
|---:|---|---|---:|---:|---:|
| 2.5 | uncoded10 | crop_bottom_right_50 | 0.980000 | 0.800000 | 0.981250 |
| 2.5 | rep3_10 | crop_bottom_right_50 | 1.000000 | 1.000000 | 0.962500 |
| 2.5 | uncoded10 | crop_center_50 | 0.940000 | 0.400000 | 0.975000 |
| 2.5 | rep3_10 | crop_center_50 | 1.000000 | 1.000000 | 0.975000 |
| 2.5 | uncoded10 | resize_0.25_jpeg_q50 | 0.960000 | 0.800000 | 0.937500 |
| 2.5 | rep3_10 | resize_0.25_jpeg_q50 | 1.000000 | 1.000000 | 0.981250 |
| 2.5 | uncoded10 | jpeg_q20 | 0.840000 | 0.600000 | 0.850000 |
| 2.5 | rep3_10 | jpeg_q20 | 0.820000 | 0.600000 | 0.837500 |
| 3.0 | uncoded10 | crop_center_50 | 0.940000 | 0.400000 | 0.975000 |
| 3.0 | rep3_10 | crop_center_50 | 1.000000 | 1.000000 | 0.962500 |
| 3.0 | uncoded10 | resize_0.25_jpeg_q50 | 0.960000 | 0.800000 | 0.962500 |
| 3.0 | rep3_10 | resize_0.25_jpeg_q50 | 1.000000 | 1.000000 | 0.981250 |
| 3.0 | uncoded10 | jpeg_q20 | 0.900000 | 0.800000 | 0.881250 |
| 3.0 | rep3_10 | jpeg_q20 | 0.880000 | 0.800000 | 0.893750 |

## 结论

ECC 消息冗余是有价值的附加创新，但不是无条件提升。

正向部分：

- 对裁剪和 resize+JPEG，`rep3_10` 显著提升 payload 成功率。
- `scaling_w=2.5` 下，`crop_center_50` 从 0.4 成功率提升到 1.0，`resize_0.25_jpeg_q50` 从 0.8 提升到 1.0。
- 即使 full 32-bit message 有若干错误，重复编码多数投票仍可恢复 10-bit payload。

负向部分：

- 对 JPEG Q=20，`rep3_10` 没有稳定提升，payload accuracy 甚至略低于 uncoded10。这说明强 JPEG 错误可能呈现成组偏差，不一定满足独立随机错误假设。
- 代价是容量下降：有效 payload 从 10 bit 直接编码仍为 10 bit，但占用 30 个 WAM bit，不能用于高容量水印。

后续判断：

- 可以作为报告中的附加改进：主方案是 DWSF 空间分散 + TrustMark 强度权衡，消息层再提供可选 ECC 模式。
- 写作时应强调容量-鲁棒性权衡，不要把它说成免费提升。

---

## 原始素材：experiment_notes\source_tracing.md

# MuST 式多源合成追踪 v1

## 目的

这一轮来自 MuST 的多源图像素材追踪思想：多个带有不同 source ID 的素材被缩放、裁剪、粘贴到同一合成图中后，系统应能从合成图里追踪各素材来源。

本实验不是把攻击列表继续加长，而是验证 WAM-DWSF 是否能扩展到一个更纯正的信息安全场景：多源版权溯源。

## 论文来源

- MuST：multi-source image tracing，核心包含 multi-source detector、minimum external rectangle (MER) 重同步和多素材 ID 提取。
- WAM：localized messages 和多水印能力，可为局部素材嵌入不同 ID。
- DWSF：分散嵌入与覆盖面积权衡。
- MBRS / RoSteALS：消息冗余和 ECC，用短 source ID 牺牲容量换鲁棒性。

## 实验设置

- 主模型：WAM 官方 MIT 权重。
- 环境：`bamboo` conda 环境，RTX 4060 Laptop GPU。
- 原始素材：WAM 官方示例图中选 3 张作为 source materials，`seabackground` 作为背景。
- 合成画布：512x512。
- 素材标准尺寸：256x256。
- 合成场景：
  - `two_sources_downsize`：两个素材缩小粘贴。
  - `three_sources_extreme_downsize`：三个素材更强缩小并裁剪。
  - `three_sources_crop_feather`：三个素材裁剪、增强对比度并羽化边缘。
- 合成后攻击：
  - none
  - JPEG Q70 / Q50
  - resize 0.5 + JPEG Q70
- 解码方法：
  - `global_full_canvas`：整张合成图直接解码。
  - `oracle_box_raw`：用已知素材框裁剪后直接解码。
  - `must_mer_resize`：用已知素材框裁剪后缩放回 256x256 再解码，模拟 MuST 的 MER 重同步。

## 脚本

- 基础多源追踪：`watermark_anything\extensions\source_tracing/composite_trace.py`
- 8-bit source ID + rep4 冗余：`watermark_anything\extensions\source_tracing/redundant_id_trace.py`
- 注册源 ID 最近码字匹配：`watermark_anything\extensions\source_tracing/codebook_match.py`

## 关键结果一：MER 重同步是必要的

在无合成后二次压缩时，`must_mer_resize` 和 `oracle_box_raw` 对所有场景都能把每个 source ID 解到 1.000000；`global_full_canvas` 基本失败。这说明多源合成图不能直接整图混合解码，必须先定位素材区域，再进行局部重同步。

代表性无攻击结果：

| scenario | scheme | global_full_canvas | must_mer_resize |
|---|---|---:|---:|
| two_sources_downsize | dwsf_q50_s2.5 | 0.000000 | 1.000000 |
| three_sources_extreme_downsize | dwsf_q50_s2.5 | 0.395833 | 1.000000 |
| three_sources_crop_feather | dwsf_q50_s2.5 | 0.468750 | 1.000000 |

## 关键结果二：小素材二次压缩下，稀疏 DWSF 不如 full-material source-trace 模式

基础 32-bit 解码的整体 overview：

| scheme | decode_method | mean_source_accuracy | source_success_rate | PSNR |
|---|---|---:|---:|---:|
| full_material_s3.0 | must_mer_resize | 0.626953 | 0.250000 | 39.1471 |
| full_material_s2.5 | must_mer_resize | 0.587891 | 0.250000 | 40.6792 |
| single_center50_s2.5 | must_mer_resize | 0.559570 | 0.250000 | 42.2053 |
| dwsf_q50_s2.5 | must_mer_resize | 0.480469 | 0.250000 | 44.2526 |
| dwsf_q50_s3.0 | must_mer_resize | 0.479492 | 0.250000 | 42.7517 |

判断：当素材会被缩小、裁剪、再压缩时，DWSF 的空间稀疏覆盖会让单个小素材内可用水印证据不足；MuST 场景更适合切换到 full-material 或 single-center 的 source-trace 模式。

## 关键结果三：rep4 ECC 有帮助，但单靠 payload 全恢复仍不够

ECC overview 中，`must_mer_resize` 的 payload success：

| code mode | scheme | payload_success_rate |
|---|---|---:|
| rep4_interleaved_8bit | dwsf_q50_s3.0 | 0.312500 |
| rep4_adjacent_8bit | dwsf_q50_s3.0 | 0.281250 |
| rep4_adjacent_8bit | full_material_s3.0 | 0.250000 |
| rep4_interleaved_8bit | full_material_s3.0 | 0.250000 |

判断：交织冗余能在个别困难场景把 bit accuracy 约 0.71875 的预测恢复成 8-bit source ID 成功，但强压缩/三源极端缩小仍不稳定，不能把 ECC 写成彻底解决方案。

## 关键结果四：注册 codebook 最近码字匹配更符合 source tracing

对 source tracing 来说，查询图通常只需要匹配到注册库中的哪个 source ID，而不一定要求逐位完美恢复。对 ECC 预测消息做最近码字匹配后，结果明显优于 payload 全恢复。

整体 overview：

| code mode | scheme | decode_method | payload_success_rate | codebook_strict_match_rate |
|---|---|---|---:|---:|
| rep4_adjacent_8bit | full_material_s2.5 | oracle_box_raw | 0.250000 | 0.562500 |
| rep4_adjacent_8bit | full_material_s3.0 | oracle_box_raw | 0.250000 | 0.562500 |
| rep4_adjacent_8bit | full_material_s2.5 | must_mer_resize | 0.250000 | 0.531250 |
| rep4_adjacent_8bit | full_material_s3.0 | must_mer_resize | 0.250000 | 0.531250 |
| rep4_adjacent_8bit | single_center50_s2.5 | must_mer_resize | 0.250000 | 0.531250 |
| rep4_adjacent_8bit | dwsf_q50_s3.0 | must_mer_resize | 0.281250 | 0.531250 |

两源缩小场景中，codebook 匹配非常有效：

| code mode | scheme | attack | payload_success_rate | codebook_strict_match_rate |
|---|---|---|---:|---:|
| rep4_adjacent_8bit | full_material_s2.5 | jpeg_q50 | 0.000000 | 1.000000 |
| rep4_adjacent_8bit | full_material_s2.5 | jpeg_q70 | 0.000000 | 1.000000 |
| rep4_adjacent_8bit | full_material_s2.5 | resize_0.5_jpeg70 | 0.000000 | 1.000000 |
| rep4_interleaved_8bit | full_material_s2.5 | resize_0.5_jpeg70 | 0.000000 | 1.000000 |
| rep4_interleaved_8bit | dwsf_q50_s3.0 | jpeg_q70 | 0.500000 | 1.000000 |

## 判断

1. MuST 思路适合作为补充分支：WAM 负责局部水印，MER/box crop 负责重同步，ECC/codebook 负责 source ID 级溯源。
2. 这个分支不能替代主线 DWSF 鲁棒水印方案，因为真实 detector 未训练，这里使用的是 oracle box；三源极端缩小 + 压缩仍不稳。
3. 对最终方案的可用启发是：当应用目标是“合成图素材来源追踪”时，不应默认用 DWSF 稀疏分散模式；更合理的是切换到 full-material/source-trace 覆盖模式，再配合短 ID 冗余和注册 codebook 最近码字匹配。
4. 这个分支的信息安全属性很强，属于版权溯源、身份认证和多源责任追踪，可作为主方案之外的安全应用扩展。

## 输出文件

- `results_output/source_tracing/source_tracing_metrics.csv`
- `results_output/source_tracing/source_tracing_summary.csv`
- `results_output/source_tracing/source_tracing_overview.csv`
- `results_output/source_tracing_redundant_id/source_tracing_redundant_id_metrics.csv`
- `results_output/source_tracing_redundant_id/source_tracing_redundant_id_summary.csv`
- `results_output/source_tracing_redundant_id/source_tracing_redundant_id_overview.csv`
- `results_output/source_tracing_codebook_match/source_tracing_codebook_match_metrics.csv`
- `results_output/source_tracing_codebook_match/source_tracing_codebook_match_summary.csv`
- `results_output/source_tracing_codebook_match/source_tracing_codebook_match_overview.csv`

---

## 原始素材：experiment_notes\spatial_strength_profile.md

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

---

## 原始素材：experiment_notes\strength_search.md

# TrustMark 式强度-质量权衡 v1

## 目的

TrustMark 论文强调在推理阶段通过残差缩放系数控制不可感知性和鲁棒性的权衡。WAM 中存在语义相近的 `scaling_w` 参数，用于控制水印残差强度。本实验扫描 `scaling_w`，观察 WAM 在不同强度下的 clean PSNR、无攻击恢复率和攻击后 bit accuracy。

这条路线比纯后处理更像对主论文方法本身的改动，因为它直接改变嵌入残差强度。

## 论文依据

TrustMark 的可迁移思想：

- 推理阶段可通过 residual scale factor 控制视觉质量和恢复率。
- 增大残差强度通常提高 bit accuracy，但会降低 PSNR。
- 应通过曲线或 Pareto 点选择折中参数，而不是只追求最高鲁棒性。

## 脚本

- 脚本：`watermark_anything\extensions\robustness_profiles/strength_search.py`
- 输出目录：`results_output/strength_search/`
- 明细文件：`results_output/strength_search/strength_search_metrics.csv`
- 汇总文件：`results_output/strength_search/strength_search_summary.csv`
- 总览文件：`results_output/strength_search/strength_search_overview.csv`

## 运行命令

```powershell
$task='C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务'
$repo='.'
$py='C:\Users\86155\miniconda3\envs\bamboo\python.exe'
& $py "$task\watermark_anything\extensions\robustness_profiles/strength_search.py" `
  --wam-root $repo `
  --checkpoint "$repo\checkpoints\wam_mit.pth" `
  --params "$repo\checkpoints\params.json" `
  --image-dir "$repo\assets\images" `
  --out-dir "$task\results_output\strength_search" `
  --limit 5
```

## 实验设置

- 数据：WAM 官方 `assets/images` 中 5 张示例图。
- 消息长度：32 bit。
- 嵌入区域：固定随机 50% 区域，同一张图在不同强度下使用同一个 mask。
- 扫描强度：`scaling_w = 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0`。
- 攻击：
  - none
  - JPEG Q=50/30/20
  - resize 0.5/0.25
  - resize 0.25 + JPEG Q=50
  - center crop 0.5

## 总览结果

| scaling_w | mean clean PSNR | selected attack mean acc | none | jpeg_q50 | jpeg_q30 | jpeg_q20 | resize_0.25 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.25 | 59.1528 | 0.353125 | 0.581250 | 0.200000 | 0.281250 | 0.375000 | 0.900000 |
| 0.50 | 53.1347 | 0.568750 | 0.937500 | 0.743750 | 0.543750 | 0.575000 | 0.943750 |
| 1.00 | 47.1218 | 0.752083 | 0.993750 | 0.912500 | 0.806250 | 0.693750 | 0.981250 |
| 1.50 | 43.6083 | 0.931250 | 0.993750 | 0.962500 | 0.925000 | 0.831250 | 0.987500 |
| 2.00 | 41.1181 | 0.948958 | 1.000000 | 0.981250 | 0.962500 | 0.812500 | 0.993750 |
| 2.50 | 39.1887 | 0.967708 | 1.000000 | 0.987500 | 0.956250 | 0.918750 | 0.993750 |
| 3.00 | 37.6142 | 0.970833 | 1.000000 | 0.987500 | 0.968750 | 0.918750 | 0.993750 |
| 4.00 | 35.1348 | 0.984375 | 1.000000 | 0.981250 | 0.987500 | 0.975000 | 0.993750 |

## 关键观察

1. `scaling_w <= 0.5` 不可用。虽然 clean PSNR 高达 53-59 dB，但 clean bit accuracy 已经不稳定，低强度水印无法保证基本恢复。
2. `scaling_w=1.5` 是高画质折中点。mean clean PSNR 为 43.6083，selected attack mean accuracy 达到 0.931250，center crop 0.5 从低强度下接近失效提升到 0.931250。
3. 官方默认附近的 `scaling_w=2.0` 是稳健折中。mean clean PSNR 为 41.1181，clean accuracy 为 1.0，selected attack mean accuracy 为 0.948958。
4. `scaling_w=2.5/3.0` 进一步提升强攻击鲁棒性，但 clean PSNR 降到 39.1887/37.6142。它们适合“安全优先”场景，但需要报告中承认画质代价。
5. `scaling_w=4.0` 鲁棒性最好，selected attack mean accuracy 为 0.984375，`jpeg_q20` 达到 0.975000，但 mean clean PSNR 只有 35.1348，视觉扰动风险明显。

## 结论

这条改进方向成立，且比 MBRS 推理多分支更适合作为主创新的一部分。

可采用的策略：

- 以 `scaling_w=2.0` 作为 WAM 官方默认强度基线。
- 将 `scaling_w=1.5` 作为高画质版本。
- 将 `scaling_w=2.5` 或 `3.0` 作为增强鲁棒版本。
- 不建议直接使用 `4.0` 作为默认方案，除非实验目标明确偏向鲁棒性而非不可感知性。

下一步最值得做的是把该强度权衡和 DWSF 式空间分散结合：比较“默认强度单区域”“高强度单区域”“默认强度多区域”“较高强度多区域”，判断能否用空间冗余降低单点强度，或用适度增强弥补多区域小块解码退化。

---

## 原始素材：experiment_notes\tamper_localization.md

# 主动篡改定位 v1

## 目的

这轮从 EditGuard / OmniGuard 的主动取证思想出发，验证 WAM+DWSF 是否不仅能恢复版权 payload，还能利用检测 mask 定位局部篡改区域。

核心问题：

1. WAM 的 watermark detection mask 在局部篡改后是否会出现可检测的缺失？
2. DWSF 的稀疏区域是否能做“覆盖区域内”的高精度篡改定位？
3. `Q=30%` 与 `Q=50%` 在定位能力上有什么差异？

## 论文来源

- EditGuard：通过比较预定义 localization watermark 与恢复的 localization watermark 得到 tamper mask，并用 F1、AUC、IoU、bit accuracy 评价。
- OmniGuard：强调主动水印 + 被动提取结合，用 artifact map / reconstructed localized watermark 辅助 tamper mask extraction。
- DWSF：分散嵌入天然只覆盖部分区域，因此定位能力会受 watermark coverage 限制。

## 实验设置

- 脚本：`watermark_anything\extensions\tamper_localization/localizer.py`。
- 输出：`results_output/tamper_localization/`。
- 主模型：WAM 官方 MIT 权重。
- 图像：WAM 官方 5 张示例图。
- 水印：固定随机 32-bit 消息。
- 强度：`scaling_w=2.5`。
- schemes：
  - `single_center_50pct`
  - `dwsf_q30_5block`
  - `dwsf_q50_5block`
- tamper：
  - remove_center_25
  - remove_center_40
  - remove_top_left_25
  - remove_bottom_right_25
  - black_center_25
- localizer：
  - `expected_missing`：已知放置 mask 中，被攻击后检测概率低的区域。
  - `clean_missing`：clean watermarked detection mask 中，被攻击后检测概率低的区域。
  - `prob_drop`：clean mask 概率相对 attacked mask 明显下降的区域。
- 指标：
  - global F1 / IoU：对完整真实 tamper mask 计算。
  - covered F1 / IoU：只对水印覆盖到的 tamper 区域计算。
  - tamper coverage：真实篡改区域中被水印参考 mask 覆盖的比例。
  - bit accuracy：篡改后版权消息恢复准确率。

## 命令

```powershell
C:\Users\86155\miniconda3\envs\bamboo\python.exe `
  watermark_anything\extensions\tamper_localization/localizer.py `
  --wam-root . `
  --checkpoint .\checkpoints\wam_mit.pth `
  --params .\checkpoints\params.json `
  --image-dir .\assets\images `
  --out-dir results_output\tamper_localization `
  --limit 5 `
  --scale 2.5
```

## 关键结果

总计 225 条逐图逐篡改逐定位器记录，stderr 为空。

overview：

| scheme | localizer | global F1 | global IoU | covered F1 | covered IoU | tamper coverage | bit accuracy |
|---|---|---:|---:|---:|---:|---:|---:|
| single_center_50pct | prob_drop | 0.695941 | 0.615839 | 0.825536 | 0.808216 | 0.802378 | 0.997500 |
| dwsf_q50_5block | prob_drop | 0.635645 | 0.466754 | 0.973085 | 0.948559 | 0.486693 | 1.000000 |
| dwsf_q30_5block | prob_drop | 0.420431 | 0.267545 | 0.985547 | 0.971861 | 0.271703 | 1.000000 |

逐篡改 `prob_drop` 结果：

| scheme | tamper | global F1 | covered F1 | tamper coverage | bit accuracy |
|---|---|---:|---:|---:|---:|
| dwsf_q30_5block | remove_center_25 | 0.416001 | 0.997476 | 0.263105 | 1.000000 |
| dwsf_q30_5block | remove_center_40 | 0.329819 | 0.963651 | 0.204362 | 1.000000 |
| dwsf_q30_5block | remove_top_left_25 | 0.471410 | 0.982671 | 0.314808 | 1.000000 |
| dwsf_q50_5block | remove_center_25 | 0.640710 | 0.975985 | 0.486801 | 1.000000 |
| dwsf_q50_5block | remove_center_40 | 0.596838 | 0.972839 | 0.439676 | 1.000000 |
| dwsf_q50_5block | remove_top_left_25 | 0.668060 | 0.988773 | 0.509149 | 1.000000 |
| single_center_50pct | remove_center_25 | 0.987527 | 0.987527 | 1.000000 | 1.000000 |
| single_center_50pct | black_center_25 | 0.184190 | 0.184190 | 1.000000 | 1.000000 |

## 判断

这轮是可保留的补充分支，但不是替代版权恢复主线。

1. DWSF 在“覆盖区域内”的篡改定位非常强：`Q=30` covered F1 约 0.985547，`Q=50` covered F1 约 0.973085，说明 WAM detection mask 的缺失确实能作为主动篡改线索。
2. 全图定位能力受水印覆盖率直接限制：`Q=30` 的 tamper coverage 只有 0.271703，因此 global F1 只有 0.420431；`Q=50` coverage 提升到 0.486693，global F1 提升到 0.635645。
3. `single_center_50pct` 在中心篡改上极强，但空间覆盖不均，且 `black_center_25` 的 global F1 只有 0.184190，说明黑块会干扰检测 mask，不能简单说单中心定位更好。
4. 版权 bit recovery 在 DWSF 两个方案下均保持 1.000000，说明增加这个定位分析分支不会损害版权恢复结果。
5. 如果报告需要一个纯信息安全色彩更强的创新点，这个分支比自适应选块/ECC 变体更有价值：它把“版权追踪”扩展到“局部完整性/篡改定位”，但必须写清它只能定位被水印覆盖的区域。

## 保留价值

- 可作为最终工作的附加创新分支：WAM+DWSF 不只恢复版权信息，还能输出 watermark survival / missing map，用于主动篡改定位。
- 推荐写法：默认主线仍是 `DWSF Q=30%, 5 blocks + scaling_w=2.5`；若要强调篡改定位覆盖率，可引入 `Q=50%` 安全优先模式。
- 这个分支能和信息安全课程的完整性保护、主动取证、认证与访问后追踪场景自然连接。

## 输出文件

- `results_output/tamper_localization/tamper_localization_metrics.csv`
- `results_output/tamper_localization/tamper_localization_summary.csv`
- `results_output/tamper_localization/tamper_localization_overview.csv`
