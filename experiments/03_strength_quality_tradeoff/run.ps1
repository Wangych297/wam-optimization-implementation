param([string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe")
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment strength_sweep -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment dwsf_strength_combo -Python $Python

