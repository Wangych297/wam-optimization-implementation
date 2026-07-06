param([string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe")
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment strength_search -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment spatial_strength_profile -Python $Python
