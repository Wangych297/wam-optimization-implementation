# Project Structure

The repository uses a single project layout for the model package, extension modules, experiment entrypoints, generated results, and documentation.

## Root Project

- `watermark_anything/`: model package and extension modules.
- `assets/`: sample images and masks.
- `configs/`: model configuration files.
- `checkpoints/`: local parameter files and checkpoints.
- `notebooks/`: inference utilities.
- `experiments/`: reproducible experiment entrypoints.
- `tools/`: project-level utility commands.
- `results_output/`: generated metrics, summaries, and selected visuals.
- `experiment_notes/`: experiment notes and conclusions.
- `logs/`: local runtime logs.
- `docs/`: technical notes, result index, and report materials.

## Experiment Entrypoints

Each directory under `experiments/` contains a short `README.md` and a `run.ps1` wrapper. Implementations live under `watermark_anything/extensions/`.
