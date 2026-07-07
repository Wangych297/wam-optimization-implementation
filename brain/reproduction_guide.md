# WAM 项目复现指南

本文档指导你在 macOS 上从零复现本项目的所有实验。

---

## 环境概况

| 项目 | 当前状态 |
|------|----------|
| 操作系统 | macOS (Darwin) |
| Python | 3.9.6 (系统自带) |
| GPU | Apple Silicon (MPS) 或无 GPU |
| Conda | 未安装 |
| 权重文件 | **缺失，需下载** `wam_mit.pth` |

原项目在 Windows + NVIDIA GPU 上开发，所有脚本为 PowerShell (`.ps1`)。本指南提供 macOS 适配方案。

---

## 第一步：创建虚拟环境

```bash
cd /Users/linsh/Documents/Courses/Year_3/Spring/lec2_security/project/wam-optimization-implementation

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate
```

---

## 第二步：安装依赖

```bash
# 确保已激活虚拟环境
pip install --upgrade pip
pip install -r requirements.txt
```

需要安装的依赖列表：
- `omegaconf==2.3.0` — 配置管理
- `einops==0.8.0` — 张量操作
- `pycocotools==2.0.8` — COCO 数据集工具
- `timm==1.0.11` — PyTorch 图像模型库
- `opencv-python==4.10.0.84` — 图像处理
- `lpips==0.1.4` — 感知相似度
- `scikit-image==0.24.0` — 图像处理
- `scikit-learn==1.5.2` — DBSCAN 聚类

此外需要安装 PyTorch（`requirements.txt` 未列出，因为原项目假定已有）：

```bash
# macOS Apple Silicon
pip install torch torchvision

# 如果需要在 Intel Mac 或无 GPU 上运行
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

---

## 第三步：下载模型权重

权重文件 `wam_mit.pth` 约 378MB，需下载到 `checkpoints/` 目录：

### 方式 A：直接下载（推荐）

```bash
curl -L -o checkpoints/wam_mit.pth \
  https://dl.fbaipublicfiles.com/watermark_anything/wam_mit.pth
```

### 方式 B：使用项目自带的下载工具

```bash
python watermark_anything/extensions/utilities/download_checkpoint.py \
  --url https://dl.fbaipublicfiles.com/watermark_anything/wam_mit.pth \
  --dest checkpoints/wam_mit.pth \
  --log logs/download_checkpoint.log
```

### 方式 C：从 Hugging Face 下载

```bash
pip install huggingface_hub
python -c "
from huggingface_hub import hf_hub_download
ckpt = hf_hub_download(
    repo_id='facebook/watermark-anything',
    filename='checkpoint.pth'
)
import shutil
shutil.copy(ckpt, 'checkpoints/wam_mit.pth')
print('Downloaded successfully')
"
```

### 验证下载

```bash
ls -lh checkpoints/wam_mit.pth
# 应显示约 378MB 的文件

python -c "
import torch
ckpt = torch.load('checkpoints/wam_mit.pth', map_location='cpu')
print(f'Checkpoint loaded, {len(ckpt)} keys')
"
```

---

## 第四步：运行基线复现实验

原项目通过 PowerShell 脚本 `tools/run_experiment.ps1` 统一管理实验入口。在 macOS 上直接调用 Python 即可。

### 实验 00 — 基础复现

```bash
# 激活环境并进入项目根目录
cd /Users/linsh/Documents/Courses/Year_3/Spring/lec2_security/project/wam-optimization-implementation
source venv/bin/activate

python watermark_anything/extensions/baseline_reproduction/run.py \
  --checkpoint checkpoints/wam_mit.pth \
  --params checkpoints/params.json \
  --image-dir assets/images \
  --out-dir results_output/baseline_reproduction \
  --limit 5
```

**参数说明**：

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `--checkpoint` | 模型权重路径 | (必填) |
| `--params` | 模型超参数 JSON | (必填) |
| `--image-dir` | 测试图片目录 | (必填) |
| `--out-dir` | 结果输出目录 | (必填) |
| `--limit` | 处理图片数量上限 | 3 |
| `--seed` | 随机种子 | 42 |
| `--mask-ratio` | 水印掩码覆盖率 | 0.5 |
| `--multi-count` | 多水印数量 | 2 |
| `--multi-mask-ratio` | 多水印每个掩码覆盖率 | 0.1 |

**预期输出**：

```
results_output/baseline_reproduction/
├── baseline_reproduction_metrics.csv    # 指标表格
└── visuals/                             # 可视化图像
    ├── alpaca_single_original.png
    ├── alpaca_single_watermarked.png
    ├── alpaca_single_pred_mask.png
    ├── alpaca_single_target_mask.png
    ├── alpaca_single_diff_x10.png
    └── ...（每张图 × 5 个可视化 + 多水印版本）
```

---

## 第五步：运行所有实验

`tools/run_experiment.ps1` 将实验列表映射为 Python 命令。以下是每个实验的等效 macOS 命令。

### 实验总览

| 编号 | 实验 | 模块路径 | 输出目录 |
|------|------|----------|----------|
| 00 | 基础复现 | `baseline_reproduction/run.py` | `baseline_reproduction` |
| 01 | 攻击基准 | `attack_benchmark/run.py` | `attack_benchmark` |
| 02 | 空间冗余 | `spatial_redundancy/` | `redundant_regions` 等 |
| 03 | 鲁棒性配置 | `robustness_profiles/` | `strength_search` 等 |
| 04 | 平台变换 | `transform_profiles/platform_modes.py` | `platform_modes` |
| 05 | 篡改定位 | `tamper_localization/localizer.py` | `tamper_localization` |
| 06 | 来源更新 | `provenance_update/pipeline.py` | `provenance_update` |
| 07 | 多源溯源 | `source_tracing/` | `source_tracing` 等 |
| 08 | 辅助模块 | `compression_recovery/`, `payload_coding/`, `region_selection/` | 各对应目录 |

### 01 — 攻击基准评估

```bash
python watermark_anything/extensions/attack_benchmark/run.py \
  --checkpoint checkpoints/wam_mit.pth \
  --params checkpoints/params.json \
  --image-dir assets/images \
  --out-dir results_output/attack_benchmark \
  --limit 5 \
  --mask-ratio 0.5
```

### 02 — 空间冗余 / 覆盖搜索（核心实验）

```bash
# 冗余区域
python watermark_anything/extensions/spatial_redundancy/redundant_regions.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/redundant_regions --limit 5

# 分布式布局
python watermark_anything/extensions/spatial_redundancy/distributed_layout.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/distributed_layout --limit 5

# 覆盖率搜索（运行时间较长）
python watermark_anything/extensions/spatial_redundancy/coverage_search.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/coverage_search --limit 5 \
  --scale 2.5 --areas 10 20 25 30 50 --block-counts 5 9
```

### 03 — 鲁棒性配置搜索

```bash
# 强度搜索
python watermark_anything/extensions/robustness_profiles/strength_search.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/strength_search --limit 5 \
  --scales 1.5 2.0 2.5 3.0 4.0

# 空间-强度联合搜索
python watermark_anything/extensions/robustness_profiles/spatial_strength_profile.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/spatial_strength_profile --limit 5 \
  --scales 1.5 2.0 2.5 3.0
```

### 04 — 平台变换评估

```bash
python watermark_anything/extensions/transform_profiles/platform_modes.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/platform_modes --limit 5
```

### 05 — 篡改定位

```bash
python watermark_anything/extensions/tamper_localization/localizer.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/tamper_localization --limit 5
```

### 06 — 来源更新

```bash
python watermark_anything/extensions/provenance_update/pipeline.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/provenance_update --limit 5
```

### 07 — 多源溯源

```bash
# 合成图溯源
python watermark_anything/extensions/source_tracing/composite_trace.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/source_tracing --limit 5

# 冗余 ID 溯源
python watermark_anything/extensions/source_tracing/redundant_id_trace.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/source_tracing_redundant_id --limit 5

# 码本匹配（依赖上一步的输出）
python watermark_anything/extensions/source_tracing/codebook_match.py \
  --metrics results_output/source_tracing_redundant_id/source_tracing_redundant_id_metrics.csv \
  --out-dir results_output/source_tracing_codebook_match
```

### 08 — 辅助模块

```bash
# 压缩恢复
python watermark_anything/extensions/compression_recovery/multi_branch_decode.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/compression_recovery --limit 5

# 载荷编码 — 重复载荷
python watermark_anything/extensions/payload_coding/repetition_payload.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/repetition_payload --limit 5

# 载荷编码 — 编码变体
python watermark_anything/extensions/payload_coding/coding_variants.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/coding_variants --limit 5

# 自适应区域选择
python watermark_anything/extensions/region_selection/adaptive_selector.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/adaptive_selector --limit 5

# 区域同步
python watermark_anything/extensions/spatial_redundancy/region_sync.py \
  --checkpoint checkpoints/wam_mit.pth --params checkpoints/params.json \
  --image-dir assets/images --out-dir results_output/region_sync --limit 5
```

---

## 快速一键复现脚本

macOS 用户可复制以下脚本保存为 `run_all.sh`：

```bash
#!/bin/bash
set -e
cd /Users/linsh/Documents/Courses/Year_3/Spring/lec2_security/project/wam-optimization-implementation
source venv/bin/activate

CKPT=checkpoints/wam_mit.pth
PARAMS=checkpoints/params.json
IMAGES=assets/images
RESULT=results_output
LIMIT=5

# 基础复现
python watermark_anything/extensions/baseline_reproduction/run.py \
  --checkpoint $CKPT --params $PARAMS --image-dir $IMAGES \
  --out-dir $RESULT/baseline_reproduction --limit $LIMIT

# 攻击基准
python watermark_anything/extensions/attack_benchmark/run.py \
  --checkpoint $CKPT --params $PARAMS --image-dir $IMAGES \
  --out-dir $RESULT/attack_benchmark --limit $LIMIT --mask-ratio 0.5

# 覆盖率搜索
python watermark_anything/extensions/spatial_redundancy/coverage_search.py \
  --checkpoint $CKPT --params $PARAMS --image-dir $IMAGES \
  --out-dir $RESULT/coverage_search --limit $LIMIT \
  --scale 2.5 --areas 10 20 25 30 50 --block-counts 5 9

# 平台模式
python watermark_anything/extensions/transform_profiles/platform_modes.py \
  --checkpoint $CKPT --params $PARAMS --image-dir $IMAGES \
  --out-dir $RESULT/platform_modes --limit $LIMIT

echo "All experiments completed."
```

---

## 常见问题

### Q: MPS (Apple Silicon GPU) 兼容性
项目使用的 `torch.load(ckpt_path, map_location='cpu')` 会自动加载到 CPU。如需使用 MPS 加速，部分算子可能不支持（尤其是 `torch.fft` 相关操作）。建议先用 CPU 跑通，后续考虑 MPS 适配。

### Q: CUDA 相关报错
macOS 无 CUDA，代码会自动 fallback 到 CPU：`torch.device("cuda" if torch.cuda.is_available() else "cpu")`。推理在 CPU 上可正常运行，速度稍慢。

### Q: `import omegaconf` 失败
`omegaconf` 需要 `pip install omegaconf==2.3.0`。如果版本冲突，可以尝试 `pip install omegaconf` 装最新版。

### Q: `ModuleNotFoundError: No module named 'watermark_anything'`
确保在项目根目录运行命令。`run.py` 通过 `sys.path.insert(0, str(run_root))` 添加项目根目录到 Python 路径。

### Q: 运行某个实验时参数报错
每个实验模块支持不同的 CLI 参数。查看对应 `.py` 文件的 `argparse` 定义获取完整参数列表。运行 `python <module.py> --help` 获取帮助。
