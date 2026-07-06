param([string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe")
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment compression_recovery -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment repetition_payload -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment coding_variants -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment adaptive_selector -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment region_sync -Python $Python
