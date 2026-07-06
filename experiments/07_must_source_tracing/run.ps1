param([string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe")
& "$PSScriptRoot\..\..\tools\run_experiment.ps1" -Experiment must_source_tracing -Python $Python

