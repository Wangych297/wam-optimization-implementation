param([string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe")
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment mbrs_multibranch -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment payload_ecc -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment payload_ecc_variants -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment adaptive_region -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment bbox_sync -Python $Python

