param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(
        "baseline_reproduction",
        "attack_benchmark",
        "redundant_regions",
        "distributed_layout",
        "coverage_search",
        "strength_search",
        "spatial_strength_profile",
        "platform_modes",
        "tamper_localization",
        "provenance_update",
        "compression_recovery",
        "repetition_payload",
        "coding_variants",
        "adaptive_selector",
        "region_sync",
        "source_tracing"
    )]
    [string]$Experiment,

    [string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe",
    [string]$ProjectRootPath = "",
    [int]$Limit = 5
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($ProjectRootPath)) {
    $ProjectRootPath = $ProjectRoot
}
$RunRoot = (Resolve-Path $ProjectRootPath).Path

$Checkpoint = Join-Path $RunRoot "checkpoints\wam_mit.pth"
$Params = Join-Path $RunRoot "checkpoints\params.json"
$ImageDir = Join-Path $RunRoot "assets\images"
$ModuleRoot = Join-Path $ProjectRoot "watermark_anything\extensions"
$OutRoot = Join-Path $ProjectRoot "results_output"

if (!(Test-Path $Python)) {
    throw "Python not found: $Python"
}
if (!(Test-Path $Checkpoint)) {
    throw "WAM checkpoint not found: $Checkpoint. Put wam_mit.pth under checkpoints."
}
if (!(Test-Path $Params)) {
    throw "WAM params.json not found: $Params"
}

function Invoke-WatermarkModule {
    param(
        [string]$ModulePath,
        [string]$OutName,
        [string[]]$ExtraArgs = @()
    )
    $moduleFile = Join-Path $ModuleRoot $ModulePath
    $outDir = Join-Path $OutRoot $OutName
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    & $Python $moduleFile `
        --project-root $RunRoot `
        --checkpoint $Checkpoint `
        --params $Params `
        --image-dir $ImageDir `
        --out-dir $outDir `
        --limit $Limit `
        @ExtraArgs
}

switch ($Experiment) {
    "baseline_reproduction" {
        Invoke-WatermarkModule "baseline_reproduction\run.py" "baseline_reproduction" @("--save-visuals")
    }
    "attack_benchmark" {
        Invoke-WatermarkModule "attack_benchmark\run.py" "attack_benchmark" @("--mask-ratio", "0.5")
    }
    "redundant_regions" {
        Invoke-WatermarkModule "spatial_redundancy\redundant_regions.py" "redundant_regions"
    }
    "distributed_layout" {
        Invoke-WatermarkModule "spatial_redundancy\distributed_layout.py" "distributed_layout"
    }
    "coverage_search" {
        Invoke-WatermarkModule "spatial_redundancy\coverage_search.py" "coverage_search" @("--scale", "2.5", "--areas", "10", "20", "25", "30", "50", "--block-counts", "5", "9")
    }
    "strength_search" {
        Invoke-WatermarkModule "robustness_profiles\strength_search.py" "strength_search" @("--scales", "1.5", "2.0", "2.5", "3.0", "4.0")
    }
    "spatial_strength_profile" {
        Invoke-WatermarkModule "robustness_profiles\spatial_strength_profile.py" "spatial_strength_profile" @("--scales", "1.5", "2.0", "2.5", "3.0")
    }
    "platform_modes" {
        Invoke-WatermarkModule "transform_profiles\platform_modes.py" "platform_modes"
    }
    "tamper_localization" {
        Invoke-WatermarkModule "tamper_localization\localizer.py" "tamper_localization"
    }
    "provenance_update" {
        Invoke-WatermarkModule "provenance_update\pipeline.py" "provenance_update"
    }
    "compression_recovery" {
        Invoke-WatermarkModule "compression_recovery\multi_branch_decode.py" "compression_recovery"
    }
    "repetition_payload" {
        Invoke-WatermarkModule "payload_coding\repetition_payload.py" "repetition_payload"
    }
    "coding_variants" {
        Invoke-WatermarkModule "payload_coding\coding_variants.py" "coding_variants"
    }
    "adaptive_selector" {
        Invoke-WatermarkModule "region_selection\adaptive_selector.py" "adaptive_selector"
    }
    "region_sync" {
        Invoke-WatermarkModule "spatial_redundancy\region_sync.py" "region_sync"
    }
    "source_tracing" {
        Invoke-WatermarkModule "source_tracing\composite_trace.py" "source_tracing"
        Invoke-WatermarkModule "source_tracing\redundant_id_trace.py" "source_tracing_redundant_id"
        $metrics = Join-Path $OutRoot "source_tracing_redundant_id\source_tracing_redundant_id_metrics.csv"
        $outDir = Join-Path $OutRoot "source_tracing_codebook_match"
        New-Item -ItemType Directory -Force -Path $outDir | Out-Null
        & $Python (Join-Path $ModuleRoot "source_tracing\codebook_match.py") --metrics $metrics --out-dir $outDir
    }
}
