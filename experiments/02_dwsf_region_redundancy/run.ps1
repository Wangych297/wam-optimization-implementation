param([string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe")
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment dwsf_redundancy_v1 -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment dwsf_spatial_v2 -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment dwsf_area_sweep -Python $Python

