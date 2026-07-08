# 鲁棒图像水印优化实现

这是一个面向信息安全课程大作业的鲁棒图像水印工程。项目围绕 WAM (Watermark Anything, ICLR 2025) 的嵌入、提取、攻击恢复、篡改定位和来源追踪展开，包含基础复现、攻击评估、空间冗余、强度配置、平台变换、载荷编码、来源更新、多源溯源，以及推理侧优化（多尺度检测、纠错编码、几何攻击评估）等模块。

评测数据集从 WAM 官方 5 张示例图扩展到 COCO val2017 全量 5000 张。详细实验记录见 `docs/report_materials.md`。

## 工程结构

```text
watermark_anything/                 # 模型包、基础推理代码和扩展模块
watermark_anything/extensions/      # 本项目新增的功能模块（含优化实验）
watermark_anything/upstream_docs/   # 原始工程说明归档
assets/                             # 示例图片（5张）+ COCO 预处理缓存
configs/                            # 模型配置
checkpoints/                        # 本地参数和权重（wam_mit.pth 需手动下载）
notebooks/                          # 推理辅助工具
experiments/                        # 可复现实验入口（00-15）
results_output/                     # 指标、汇总表和可视化结果
logs/                               # 本地运行日志
docs/report_materials.md            # 报告素材
```

## 功能模块

| 模块目录 | 作用 |
| --- | --- |
| `baseline_reproduction/` | 基础推理复现，验证权重、配置和嵌入提取流程。 |
| `attack_benchmark/` | 对压缩、缩放、裁剪、局部移除等攻击做统一评估。 |
| `spatial_redundancy/` | 空间冗余嵌入、分布式布局、覆盖搜索、区域同步及 bbox 解码。 |
| `robustness_profiles/` | 搜索水印强度和空间强度配置。 |
| `transform_profiles/` | 模拟不同平台传播链路下的图像变换。 |
| `compression_recovery/` | 压缩破坏后的多分支解码恢复评估。 |
| `payload_coding/` | 重复载荷、编码变体等消息恢复策略。 |
| `region_selection/` | 根据图像内容自适应选择嵌入区域。 |
| `tamper_localization/` | 根据水印检测结果定位疑似篡改区域。 |
| `provenance_update/` | 二次水印写入和来源信息更新。 |
| `source_tracing/` | 多源合成图中的局部来源追踪。 |
| `multi_scale/` | **新增** — 多尺度检测及 ECC 组合解码（实验 10/11/14）。 |
| `spatial_coverage/` | **新增** — 覆盖率与裁剪鲁棒性扫描（实验 09）。 |
| `color_space/` | **新增** — 颜色空间切换检测（实验 12）。 |
| `utilities/` | 权重下载、几何攻击评估、诊断分析等辅助工具。 |

## 环境与权重

当前已验证环境：

```text
NVIDIA GeForce RTX 4060 Laptop GPU
Python 3.13, PyTorch 2.6, CUDA 12.4
```

```bash
conda create -n wam python=3.13 -y
conda activate wam
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
pip install pandas  # 结果合并
```

权重下载：

```bash
wget https://dl.fbaipublicfiles.com/watermark_anything/wam_mit.pth -P checkpoints/
```

## 运行实验

原项目为 Windows PowerShell，已在 Linux 上适配为 Python 直接调用。推荐在 COCO 50 上小规模验证，通过后再上 COCO 5000 全量。

```bash
# 基础复现（COCO 50）
python watermark_anything/extensions/baseline_reproduction/run.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 --out-dir results_output/coco50/baseline_reproduction --limit 50

# 多尺度检测 + ECC（当前最优方案）
python watermark_anything/extensions/multi_scale/multi_scale_ecc.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images_coco50 --out-dir results_output/multi_scale_ecc \
  --limit 50 --use-multi-scale --use-ecc --ecc-mode rep4_interleaved
```

COCO 5000 全量运行使用 15-way GPU 并行（`assets/images_coco5000_x15/chunk_00..14`），详见 `docs/report_materials.md` 末尾的命令存档。

## 实验入口

```text
00_baseline_reproduction/    01_attack_benchmark/
02_spatial_redundancy/       03_robustness_profiles/
04_transform_profiles/       05_tamper_localization/
06_provenance_update/        07_source_tracing/
08_auxiliary_modules/        09_spatial_coverage/       ← 新增
10_multi_scale/              11_ecc_combined/           ← 新增
12_color_space/              13_bbox_sync/              ← 新增
14_ecc_extension/            15_geometric_attacks/      ← 新增
```

## 关键发现

基于 COCO 5000 全量评测，修正了原 5 图实验的核心结论：

- **裁剪是 WAM 水印的最大弱点**（center_crop_0.5 从 5 图 0.95 → 实际 0.48）。JPEG 压缩在所有级别下均非威胁（Q=30 达 0.999）。
- **多尺度检测**（实验 10）将 center_crop 恢复至 0.99975，是推理侧最有效的单项优化。
- **ECC 交织编码**（实验 11/14）将 random_crop 从 0.511 → 0.815，但存在容量-鲁棒性帕累托前沿。
- **几何攻击**（旋转/翻转）是纯推理侧无法解决的绝对短板（~0.50）。
- DWSF 空间分散冗余、三档模式推荐、颜色空间切换、bbox 同步等原方案均被 COCO 验证否定或证实无效。

详见 `docs/report_materials.md`。

## 输出与素材

实验结果集中保存在 `results_output/`，按层级分为 `coco50/`（50 图）和 `coco5000/`（5000 图）。

报告写作素材集中保存在 `docs/report_materials.md`。过程记录、创新依据、结果摘要和实验笔记都已合并到这个文件中，工程目录只保留运行和维护所需的说明。
