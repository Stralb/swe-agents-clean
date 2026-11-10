# Run on Windows PowerShell. The research computation executes only on a Slurm batch node.
$ErrorActionPreference = 'Stop'
$cluster = 'astrauss@146.141.21.100'
$remoteRoot = '/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2'
$sbatchFile = Join-Path $PSScriptRoot 'case_prepr_audit_batch_v2.sbatch'
if (-not (Test-Path -LiteralPath $sbatchFile)) {
    throw 'Save case_prepr_audit_batch_v2.sbatch in the same folder as this PowerShell script.'
}

Write-Host '[1/3] Upload batch job (no computation on login node)'
& scp.exe $sbatchFile "${cluster}:${remoteRoot}/case_prepr_audit_batch_v2.sbatch"
if ($LASTEXITCODE -ne 0) { throw 'SCP upload failed.' }

Write-Host '[2/3] Submit Slurm batch job and wait for its exit status'
$submission = & ssh.exe -o ServerAliveInterval=30 -o ServerAliveCountMax=10 $cluster "sbatch --wait --parsable ${remoteRoot}/case_prepr_audit_batch_v2.sbatch"
$exitCode = $LASTEXITCODE
$submissionText = ($submission -join "`n").Trim()
$match = [regex]::Match($submissionText, '(?m)\b([0-9]{4,})(?:;[A-Za-z0-9_-]+)?\b')
if (-not $match.Success) {
    Write-Host $submissionText
    throw 'Could not identify the Slurm job ID. If SSH disconnected, the job may still exist; check squeue -u astrauss.'
}
$jobId = $match.Groups[1].Value
Write-Host "Slurm job: $jobId"

if ($exitCode -ne 0) {
    Write-Host 'Job failed or SSH disconnected. Trying to download job log files.'
    & scp.exe "${cluster}:${remoteRoot}/p2prepraudit_${jobId}.out" $PSScriptRoot
    & scp.exe "${cluster}:${remoteRoot}/p2prepraudit_${jobId}.err" $PSScriptRoot
    throw "Job $jobId did not report success. Upload the .out/.err logs."
}

Write-Host '[3/3] Download audit archive and job log'
$archiveName = "case_prepr_audit_job${jobId}.tar.gz"
& scp.exe "${cluster}:${remoteRoot}/${archiveName}" $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw "Could not download $archiveName" }
& scp.exe "${cluster}:${remoteRoot}/p2prepraudit_${jobId}.out" $PSScriptRoot
if ($LASTEXITCODE -ne 0) { Write-Warning 'Archive downloaded; job log download failed.' }

$archive = Join-Path $PSScriptRoot $archiveName
if (-not (Test-Path -LiteralPath $archive)) { throw 'Archive is missing after download.' }
Write-Host "DONE: $archive"
Write-Host 'Upload the .tar.gz archive here for interpretation.'
