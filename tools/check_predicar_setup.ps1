$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$required = @(
    "docs/predicar/protocol-v0.md",
    "docs/predicar/research-map.md",
    "docs/predicar/data-contract.md",
    "corpus/predicar/protocol-v0.json",
    "references/predicar/resource-manifest.json",
    "src/predicar/spec.py",
    "src/predicar/contracts.py",
    "src/predicar/bootstrap.py"
)

foreach ($relative in $required) {
    $path = Join-Path $root $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing preparation file: $relative"
    }
}

$null = Get-Content -Raw -LiteralPath (Join-Path $root "corpus/predicar/protocol-v0.json") | ConvertFrom-Json
$null = Get-Content -Raw -LiteralPath (Join-Path $root "references/predicar/resource-manifest.json") | ConvertFrom-Json
Write-Output "PREDICAR preparation files and manifests are present."
Write-Output "This check does not import models, load datasets, fit, forecast, or score."
