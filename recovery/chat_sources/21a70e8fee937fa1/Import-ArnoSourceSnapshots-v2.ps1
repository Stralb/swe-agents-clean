# Create a new local import branch and optionally push to Stralb private GitHub.
# Does not access the Wits cluster, delete original source files, or overwrite
# anything in the checked-out repository. Windows PowerShell 5.1 compatible.
param(
    [string]$ZipPath = (Join-Path $PSScriptRoot 'arno_code_history_source_only_20261020_v2.zip'),
    [switch]$Push
)
$ErrorActionPreference = 'Stop'
$ExpectedHash = 'fc63d5137ebbd4bab15fe42a748ed8f15cc0ec062d4cd62b65a25ea904dc94ec'
$Repository = 'https://github.com/Stralb/arno-research-reproducibility.git'

if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) { throw "ZIP not found: $ZipPath" }
$ActualHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualHash -ne $ExpectedHash) { throw "ZIP hash mismatch: $ActualHash" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is not installed or not on PATH.' }

$Id = [Guid]::NewGuid().ToString('N').Substring(0,8)
$Base = Join-Path $env:USERPROFILE ("Downloads\arno_recovery_import_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + $Id)
New-Item -ItemType Directory -Path $Base -ErrorAction Stop | Out-Null
$Stage = Join-Path $Base 'staging'
$Checkout = Join-Path $Base 'repo'
New-Item -ItemType Directory -Path $Stage -ErrorAction Stop | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $Stage -ErrorAction Stop

& git clone --depth 1 $Repository $Checkout
if ($LASTEXITCODE -ne 0) { throw 'Could not clone the private repo. Authenticate with your own Stralb account using Git Credential Manager.' }
$Branch = 'recovery/source-snapshots-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $Id
& git -C $Checkout switch -c $Branch
if ($LASTEXITCODE -ne 0) { throw 'Failed to create new local source-import branch.' }

$StagePrefix = $Stage + [IO.Path]::DirectorySeparatorChar
$Count=0
Get-ChildItem -LiteralPath $Stage -File -Recurse | ForEach-Object {
    $Rel = $_.FullName.Substring($StagePrefix.Length)
    $Target = Join-Path $Checkout $Rel
    if (Test-Path -LiteralPath $Target) { throw "Destination already exists; refusing to overwrite: $Rel" }
    $Parent = Split-Path -Parent $Target
    if (-not (Test-Path -LiteralPath $Parent)) { New-Item -ItemType Directory -Path $Parent -Force -ErrorAction Stop | Out-Null }
    Copy-Item -LiteralPath $_.FullName -Destination $Target -ErrorAction Stop
    $Count++
}
if ($Count -ne 1079) { throw "Expected 1079 staged source and manifest files, got $Count; abort before commit." }

& git -C $Checkout add -- historical provenance
if ($LASTEXITCODE -ne 0) { throw 'Git staging failed.' }
& git -C $Checkout diff --cached --stat
if ($LASTEXITCODE -ne 0) { throw 'Git diff validation failed.' }
& git -C $Checkout commit -m 'archive(source): preserve verified miner and experiment code snapshots'
if ($LASTEXITCODE -ne 0) { throw 'Git commit failed. Verify Git author configuration.' }

Write-Host "Created local import branch: $Branch"
Write-Host "Local clone: $Checkout"
Write-Host "Files imported: $Count"
if ($Push) {
    & git -C $Checkout push -u origin $Branch
    if ($LASTEXITCODE -ne 0) { throw 'Git push failed. Local committed branch is preserved.' }
    Write-Host "Branch pushed: https://github.com/Stralb/arno-research-reproducibility/tree/$Branch"
} else {
    Write-Host 'Nothing has been pushed. Re-run with -Push to push a new branch, or inspect the local clone first.'
    Write-Host "To push manually: git -C `"$Checkout`" push -u origin $Branch"
}
