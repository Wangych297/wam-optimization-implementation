param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(
        "wam_reproduction",
        "attack_baseline",
        "dwsf_redundancy_v1",
        "dwsf_spatial_v2",
        "dwsf_area_sweep",
        "strength_sweep",
        "dwsf_strength_combo",
        "platform_modes",
        "tamper_localization",
        "rewatermarking",
        "must_source_tracing",
        "mbrs_multibranch",
        "payload_ecc",
        "payload_ecc_variants",
        "adaptive_region",
        "bbox_sync"
    )]
    [string]$Experiment,

    [string]$Python = "C:\Users\86155\miniconda3\envs\bamboo\python.exe",
    [string]$WamRoot = "",
    [int]$Limit = 5
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($WamRoot)) {
    $WamRoot = Join-Path $ProjectRoot "original_code\Watermark-Anything"
}
$WamRoot = (Resolve-Path $WamRoot).Path

$Checkpoint = Join-Path $WamRoot "checkpoints\wam_mit.pth"
$Params = Join-Path $WamRoot "checkpoints\params.json"
$ImageDir = Join-Path $WamRoot "assets\images"
$SrcDir = Join-Path $ProjectRoot "src\wam_optimization"
$OutRoot = Join-Path $ProjectRoot "结果输出"

if (!(Test-Path $Python)) {
    throw "Python not found: $Python"
}
if (!(Test-Path $Checkpoint)) {
    throw "WAM checkpoint not found: $Checkpoint. Put wam_mit.pth under original_code\Watermark-Anything\checkpoints."
}
if (!(Test-Path $Params)) {
    throw "WAM params.json not found: $Params"
}

function Invoke-WamExperiment {
    param(
        [string]$Script,
        [string]$OutName,
        [string[]]$ExtraArgs = @()
    )
    $scriptPath = Join-Path $SrcDir $Script
    $outDir = Join-Path $OutRoot $OutName
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    & $Python $scriptPath `
        --wam-root $WamRoot `
        --checkpoint $Checkpoint `
        --params $Params `
        --image-dir $ImageDir `
        --out-dir $outDir `
        --limit $Limit `
        @ExtraArgs
}

switch ($Experiment) {
    "wam_reproduction" {
        Invoke-WamExperiment "wam_official_repro.py" "wam_official_repro" @("--save-visuals")
    }
    "attack_baseline" {
        Invoke-WamExperiment "wam_attack_eval.py" "wam_attack_eval" @("--mask-ratio", "0.5")
    }
    "dwsf_redundancy_v1" {
        Invoke-WamExperiment "wam_dwsf_redundant_eval.py" "wam_dwsf_redundant"
    }
    "dwsf_spatial_v2" {
        Invoke-WamExperiment "wam_dwsf_spatial_v2.py" "wam_dwsf_spatial_v2"
    }
    "dwsf_area_sweep" {
        Invoke-WamExperiment "wam_dwsf_area_sweep.py" "wam_dwsf_area_sweep" @("--scale", "2.5", "--areas", "10", "20", "25", "30", "50", "--block-counts", "5", "9")
    }
    "strength_sweep" {
        Invoke-WamExperiment "wam_trustmark_strength_sweep.py" "wam_trustmark_strength" @("--scales", "1.5", "2.0", "2.5", "3.0", "4.0")
    }
    "dwsf_strength_combo" {
        Invoke-WamExperiment "wam_combined_dwsf_strength.py" "wam_combined_dwsf_strength" @("--scales", "1.5", "2.0", "2.5", "3.0")
    }
    "platform_modes" {
        Invoke-WamExperiment "wam_practical_transform_modes.py" "wam_practical_transform_modes"
    }
    "tamper_localization" {
        Invoke-WamExperiment "wam_tamper_localization_eval.py" "wam_tamper_localization"
    }
    "rewatermarking" {
        Invoke-WamExperiment "wam_rewatermarking_eval.py" "wam_rewatermarking"
    }
    "mbrs_multibranch" {
        Invoke-WamExperiment "wam_mbrs_multibranch_decode.py" "wam_mbrs_multibranch"
    }
    "payload_ecc" {
        Invoke-WamExperiment "wam_payload_ecc_eval.py" "wam_payload_ecc"
    }
    "payload_ecc_variants" {
        Invoke-WamExperiment "wam_payload_ecc_variants.py" "wam_payload_ecc_variants"
    }
    "adaptive_region" {
        Invoke-WamExperiment "wam_adaptive_region_select.py" "wam_adaptive_region_select"
    }
    "bbox_sync" {
        Invoke-WamExperiment "wam_dwsf_bbox_sync_decode.py" "wam_dwsf_bbox_sync"
    }
    "must_source_tracing" {
        Invoke-WamExperiment "wam_must_composite_tracing.py" "wam_must_composite_tracing"
        Invoke-WamExperiment "wam_must_composite_tracing_ecc.py" "wam_must_composite_tracing_ecc"
        $metrics = Join-Path $OutRoot "wam_must_composite_tracing_ecc\wam_must_composite_tracing_ecc_metrics.csv"
        $outDir = Join-Path $OutRoot "wam_must_codebook_match"
        New-Item -ItemType Directory -Force -Path $outDir | Out-Null
        & $Python (Join-Path $SrcDir "wam_must_codebook_match.py") --metrics $metrics --out-dir $outDir
    }
}
