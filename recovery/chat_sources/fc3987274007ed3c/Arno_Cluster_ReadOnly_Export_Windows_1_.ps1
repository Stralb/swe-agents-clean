# Read-only Wits research source recovery; runs from Windows PowerShell (no WSL).
# Remote operations: SSH identity, find, git log, tar writing to STDOUT only.
# Local operations: create text reports and a local tar.gz archive.
# Never prints or collects secrets files by deliberate exclusion, but review contents before sharing.
param(
    [string]$Remote = 'astrauss@146.141.21.100',
    [string]$OutputDirectory = "$env:USERPROFILE\Downloads\arno_cluster_recovery"
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$sshExe = (Get-Command ssh.exe -ErrorAction Stop).Source
$sourcePath = '/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart'
$parentPath = '/home-mscluster/astrauss/new'

Write-Host "Read-only cluster inspection; output ONLY on this Windows computer: $OutputDirectory"
Write-Host "Remote target: $Remote"
Write-Host 'Checking SSH authentication...'
& $sshExe -T $Remote 'id -un; printf "HOME=%s\n" "$HOME"'
if ($LASTEXITCODE -ne 0) { throw 'SSH authentication failed. Check the username/host/password and retry.' }

# These are text files, so ordinary PowerShell redirection is safe.
Write-Host '[1/4] Reading home-directory inventory...'
$dirCommand = 'find /home-mscluster/astrauss -maxdepth 3 -type d -print 2>/dev/null'
$dirs = & $sshExe -T $Remote $dirCommand
if ($LASTEXITCODE -ne 0) { throw 'Remote directory inventory failed.' }
$dirs | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'home_directories_depth3.txt')

Write-Host '[2/4] Reading source-code and archive pathname inventory...'
$fileCommand = 'find /home-mscluster/astrauss -maxdepth 5 \( -type d \( -name .git -o -name .venv -o -name node_modules -o -name __pycache__ -o -name .cache \) -prune \) -o \( -type f \( -name "*.py" -o -name "*.sh" -o -name "*.sbatch" -o -name "*.slurm" -o -name "*.ipynb" -o -name "*.zip" -o -name "*.tar.gz" -o -name "pyproject.toml" -o -name "requirements*.txt" -o -name "*.yml" -o -name "*.yaml" \) -print \) 2>/dev/null'
$files = & $sshExe -T $Remote $fileCommand
if ($LASTEXITCODE -ne 0) { throw 'Remote source/archive inventory failed.' }
$files | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'candidate_sources_archives_depth5.txt')

Write-Host '[3/4] Reading miner Git commit history, where present...'
$gitCommand = 'git -C /home-mscluster/astrauss/new/malicious-issue-miner-rate-smart log --all -n 500 --date=iso-strict --pretty=format:%H%x09%ad%x09%s 2>/dev/null'
$commits = & $sshExe -T $Remote $gitCommand
if ($LASTEXITCODE -eq 0) {
    $commits | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'miner_git_log_last500.txt')
} else {
    'Git log unavailable or this tree is not a Git working copy.' | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'miner_git_log_last500.txt')
}

Write-Host '[4/4] Copying a source-only TAR stream to a LOCAL file...'
$archive = Join-Path $OutputDirectory 'miner_live_source_readonly.tar.gz'
if (Test-Path -LiteralPath $archive) {
    throw "Refusing to overwrite an existing source archive: $archive (move/rename it first)."
}

# Do not include actual .env files, auth secrets, caches, databases, or generated bulk data.
# The remote tar uses '-f -' (STDOUT). It writes NOTHING on the Wits cluster.
$remoteTar = 'cd /home-mscluster/astrauss/new && tar -czf - ' +
    '--exclude=.git --exclude=.venv --exclude=node_modules --exclude=__pycache__ ' +
    '--exclude=.cache --exclude=.env --exclude=.env.* --exclude=secrets.toml ' +
    '--exclude=*.pem --exclude=*.key --exclude=*.p12 --exclude=*.pfx ' +
    '--exclude=*.db --exclude=*.db-* --exclude=*.sqlite --exclude=*.sqlite3 ' +
    '--exclude=*.parquet --exclude=*.zip --exclude=*.tar.gz --exclude=*.sarif ' +
    '--exclude=data --exclude=distributed_spool --exclude=repo_cache --exclude=logs ' +
    '--exclude=credentials* --exclude=*token* --exclude=*.log ' +
    'malicious-issue-miner-rate-smart'

$start = New-Object System.Diagnostics.ProcessStartInfo
$start.FileName = $sshExe
$start.Arguments = '-T ' + $Remote + ' "' + $remoteTar + '"'
$start.UseShellExecute = $false
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $false
$start.CreateNoWindow = $false

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $start
$destinationStream = $null
try {
    if (-not $process.Start()) { throw 'OpenSSH could not start.' }
    $destinationStream = [System.IO.File]::Open($archive, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    # Stream native process bytes directly. Does not use PowerShell 5.x's text pipeline.
    $process.StandardOutput.BaseStream.CopyTo($destinationStream)
    $destinationStream.Flush()
    $destinationStream.Dispose()
    $destinationStream = $null
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "SSH/tar exited with code $($process.ExitCode)." }
} catch {
    if ($destinationStream -ne $null) { $destinationStream.Dispose() }
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
    throw
} finally {
    $process.Dispose()
}

if ((Get-Item -LiteralPath $archive).Length -lt 1024) {
    Remove-Item -LiteralPath $archive -Force
    throw 'Received an unexpectedly small archive; not keeping it.'
}

Write-Host 'Validating the local TAR archive...'
& tar.exe -tzf $archive *> (Join-Path $OutputDirectory 'miner_live_source_archive_files.txt')
if ($LASTEXITCODE -ne 0) { throw 'The downloaded archive did not pass local TAR integrity checking.' }

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $archive
("{0}  {1}" -f $hash.Hash.ToLowerInvariant(), (Split-Path -Leaf $archive)) | Set-Content -Encoding ASCII -Path (Join-Path $OutputDirectory 'miner_live_source_readonly.sha256')
Write-Host 'LOCAL output:'
Get-ChildItem -LiteralPath $OutputDirectory | Select-Object Name, Length | Format-Table -AutoSize
Write-Host 'Before uploading, review the archive for accidentally included secrets. No remote files were modified.'
