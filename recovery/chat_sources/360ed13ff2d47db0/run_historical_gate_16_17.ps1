# Windows PowerShell launcher; all research code and archiving run on Slurm batch nodes.
$ErrorActionPreference = 'Stop'
$cluster = 'astrauss@146.141.21.100'
$remoteRoot = '/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2'
$scanner = Join-Path $PSScriptRoot 'historical_gate_16_17_batch.sbatch'
$collector = Join-Path $PSScriptRoot 'historical_gate_16_17_collect_batch.sbatch'
foreach ($file in @($scanner, $collector)) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Required file is missing: $file" }
}

Write-Host '[1/4] Upload two worker-only Slurm scripts'
& scp.exe $scanner "${cluster}:${remoteRoot}/historical_gate_16_17_batch.sbatch"
if ($LASTEXITCODE -ne 0) { throw 'Scanner upload failed' }
& scp.exe $collector "${cluster}:${remoteRoot}/historical_gate_16_17_collect_batch.sbatch"
if ($LASTEXITCODE -ne 0) { throw 'Collector upload failed' }

Write-Host '[2/4] Submit frozen historical base/head scans to batch'
$scanSubmission = & ssh.exe -o ServerAliveInterval=30 $cluster "sbatch --parsable --partition=batch ${remoteRoot}/historical_gate_16_17_batch.sbatch"
if ($LASTEXITCODE -ne 0) { throw "Scan submission failed: $scanSubmission" }
$scanMatch = [regex]::Match(($scanSubmission -join "`n"), '(?m)\b([0-9]{4,})(?:;[A-Za-z0-9_-]+)?\b')
if (-not $scanMatch.Success) { throw "Scan job ID not detected: $scanSubmission" }
$scanJob = $scanMatch.Groups[1].Value
Write-Host "SCAN_JOB=$scanJob"

Write-Host '[3/4] Submit dependent collector to batch (also no compute on login)'
$packSubmission = & ssh.exe -o ServerAliveInterval=30 $cluster "sbatch --wait --parsable --partition=batch --dependency=afterany:${scanJob} --export=ALL,GATE_JOBID=${scanJob} ${remoteRoot}/historical_gate_16_17_collect_batch.sbatch"
$packExit = $LASTEXITCODE
$packText = ($packSubmission -join "`n").Trim()
$packMatch = [regex]::Match($packText, '(?m)\b([0-9]{4,})(?:;[A-Za-z0-9_-]+)?\b')
if ($packMatch.Success) {
    $packJob = $packMatch.Groups[1].Value
    Write-Host "COLLECTOR_JOB=$packJob"
} else {
    Write-Warning "Collector output: $packText"
}
if ($packExit -ne 0) {
    Write-Warning 'Collector returned nonzero or SSH disconnected. The Slurm jobs may have continued. Checking for archive.'
}

Write-Host '[4/4] Download all four results and detailed scanner logs'
$archive = "historical_gate_16_17_job${scanJob}.tar.gz"
& scp.exe "${cluster}:${remoteRoot}/${archive}" $PSScriptRoot
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Archive unavailable. Collect job logs and states for diagnosis.'
    & ssh.exe $cluster "sacct -j ${scanJob} -X -P -o JobID,JobName,State,ExitCode,Elapsed"
    throw "Archive download failed: $archive. Scan job: $scanJob"
}
$localArchive = Join-Path $PSScriptRoot $archive
if (-not (Test-Path -LiteralPath $localArchive)) { throw "Missing downloaded archive $localArchive" }
Write-Host "DONE: $localArchive"
Write-Host 'Upload this .tar.gz file to ChatGPT for evidence-based CodeQL comparison.'
