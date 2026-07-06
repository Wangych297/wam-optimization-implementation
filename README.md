# Robust Watermarking Optimization

Robust image watermarking project for information security coursework. The project provides baseline inference, attack benchmarking, spatially redundant embedding, robustness profiling, transform evaluation, tamper localization, provenance update, and source tracing modules.

## Project Layout

```text
watermark_anything/                 # Model package and extension modules
assets/                             # Sample images and masks
configs/                            # Model configs
checkpoints/                        # Local parameters and checkpoints
notebooks/                          # Inference utilities
experiments/                        # Reproducible experiment entrypoints
tools/run_experiment.ps1            # Unified experiment runner
results_output/                     # Metrics, summaries, selected visuals
experiment_notes/                   # Experiment notes and conclusions
logs/                               # Local runtime logs
docs/                               # Technical notes and result index
```

## Extension Modules

```text
baseline_reproduction/              # Baseline inference reproduction
attack_benchmark/                   # Attack benchmark
spatial_redundancy/                 # Spatial redundancy and region sync
robustness_profiles/                # Strength and robustness profiles
transform_profiles/                 # Platform transform profiles
compression_recovery/               # Compression recovery
payload_coding/                     # Payload coding variants
region_selection/                   # Adaptive region selection
tamper_localization/                # Tamper localization
provenance_update/                  # Provenance update
source_tracing/                     # Multi-source tracing
utilities/                          # Utility helpers
```

## Checkpoint

Place the local checkpoint at:

```text
checkpoints/wam_mit.pth
```

The checkpoint is ignored by Git. Keep `checkpoints/params.json` with the repository.

## Environment

Verified local environment:

```text
C:\Users\86155\miniconda3\envs\bamboo\python.exe
NVIDIA GeForce RTX 4060 Laptop GPU
```

Install dependencies from:

```text
requirements.txt
```

## Run

```powershell
.\tools\run_experiment.ps1 -Experiment baseline_reproduction
.\tools\run_experiment.ps1 -Experiment coverage_search
.\tools\run_experiment.ps1 -Experiment platform_modes
.\tools\run_experiment.ps1 -Experiment source_tracing
```

Specify Python explicitly:

```powershell
.\tools\run_experiment.ps1 `
  -Experiment platform_modes `
  -Python C:\Users\86155\miniconda3\envs\bamboo\python.exe
```

## Main Direction

The main implementation combines spatial redundancy, embedding strength profiling, and platform transform evaluation for robust watermark verification under compression, scaling, cropping, local removal, and multi-source composition scenarios.
