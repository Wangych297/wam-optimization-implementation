param([string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe")
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment redundant_regions -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment distributed_layout -Python $Python
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment coverage_search -Python $Python
