param(
    [switch]$PapersOnly,
    [switch]$SourceKitsOnly,
    [switch]$Force,
    [switch]$IncludeOptionalLargeKits,
    [switch]$OptionalOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$paperDir = Join-Path $root "resources/predicar/papers"
$sourceDir = Join-Path $root "resources/predicar/source"
New-Item -ItemType Directory -Force -Path $paperDir, $sourceDir | Out-Null

$papers = @(
    @{ Name = "rfs-glmb-multi-scan.pdf"; Url = "https://arxiv.org/pdf/1805.10038" },
    @{ Name = "neural-maximum-entropy.pdf"; Url = "https://arxiv.org/pdf/1612.02807" },
    @{ Name = "fixed-magnetization-ising.pdf"; Url = "https://arxiv.org/pdf/2111.03033" },
    @{ Name = "hawkes-stochastic-excitations.pdf"; Url = "http://proceedings.mlr.press/v48/leea16.pdf" },
    @{ Name = "weighted-model-counting.pdf"; Url = "https://countinglogic.github.io/files/wmc_aaai_2022.pdf" }
)

$sourceKits = @(
    @{ Name = "stone-soup-main.zip"; Url = "https://github.com/dstl/Stone-Soup/archive/refs/heads/main.zip" },
    @{ Name = "aff3ct-master.zip"; Url = "https://github.com/aff3ct/aff3ct/archive/refs/heads/master.zip" },
    @{ Name = "or-tools-stable.zip"; Url = "https://github.com/google/or-tools/archive/refs/heads/stable.zip" }
)

$optionalLargeKits = @(
    @{ Name = "allensdk-master.zip"; Url = "https://github.com/AllenInstitute/AllenSDK/archive/refs/heads/master.zip" }
)

function Save-Resource($item, $directory) {
    $target = Join-Path $directory $item.Name
    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        Write-Output "exists: $target"
        return
    }
    Write-Output "download: $($item.Url) -> $target"
    try {
        Invoke-WebRequest -Uri $item.Url -OutFile $target
    } catch {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Force
        }
        Write-Warning "download failed: $($item.Url) :: $($_.Exception.Message)"
    }
}

if (-not $SourceKitsOnly -and -not $OptionalOnly) {
    foreach ($item in $papers) { Save-Resource $item $paperDir }
}
if (-not $PapersOnly -and -not $OptionalOnly) {
    foreach ($item in $sourceKits) { Save-Resource $item $sourceDir }
}
if ($IncludeOptionalLargeKits) {
    foreach ($item in $optionalLargeKits) { Save-Resource $item $sourceDir }
}

Write-Output "Resource preparation complete. No dataset or model execution was performed."
