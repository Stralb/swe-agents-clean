# Arno Research - Windows PowerShell 5.1 / 7 read-only exporter (v2)
# REQUIREMENTS: built-in Windows OpenSSH (ssh.exe), built-in tar.exe.
# REMOTE: id, pwd, find, git log, tar -czf - (stdout only). No writes, no jobs.
# LOCAL: inventory text, a source archive, SHA-256, and TAR member list.
# IMPORTANT: Review the local archive for sensitive information before upload.
param(
    [string]$Remote = 'astrauss@146.141.21.100',
    [string]$OutputDirectory = "$env:USERPROFILE\Downloads\arno_cluster_recovery"
)

$ErrorActionPreference = 'Stop'
$sshExe = (Get-Command ssh.exe -ErrorAction Stop).Source
$tarExe = (Get-Command tar.exe -ErrorAction Stop).Source
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Write-Host "Read-only cluster export v2. LOCAL output: $OutputDirectory"
Write-Host "Remote SSH target: $Remote"

Write-Host '[0/4] Confirming SSH and source-tree access...'
# No embedded shell quotes, command substitutions, or backslash escapes.
$identity = @(& $sshExe -T $Remote 'id -un; pwd')
if ($LASTEXITCODE -ne 0 -or $identity.Count -eq 0) {
    throw 'SSH failed. Check hostname, username and password.'
}
$identity | ForEach-Object { Write-Host $_ }
$exists = @(& $sshExe -T $Remote 'test -d /home-mscluster/astrauss/new/malicious-issue-miner-rate-smart && echo SOURCE_PRESENT')
if ($LASTEXITCODE -ne 0 -or $exists -notcontains 'SOURCE_PRESENT') {
    throw 'The expected miner directory is unavailable. See the SSH identity output.'
}

# Source archive comes first: a slow/partial home-inventory cannot block code recovery.

Write-Host '[1/4] Streaming miner source to a file on THIS PC only...'
$archive = Join-Path $OutputDirectory 'miner_live_source_readonly.tar.gz'
if (Test-Path -LiteralPath $archive) {
    Write-Host 'Source archive already exists. It will NOT be overwritten; skipping transfer.'
} else {
    # The command uses tar -f - and does not create an archive on the cluster.
    # Include code, tests, docs and configuration; deliberately exclude large
    # research databases, caches, credentials, logs, and binaries.
    $parts = @(
      'cd /home-mscluster/astrauss/new && tar -czf -',
      '--exclude=.git', '--exclude=.venv', '--exclude=venv',
      '--exclude=node_modules', '--exclude=__pycache__', '--exclude=.cache',
      '--exclude=.ssh', '--exclude=.aws', '--exclude=.gnupg',
      '--exclude=.env', "--exclude='.env.*'", '--exclude=secrets',
      '--exclude=credentials.json', '--exclude=secrets.toml',
      "--exclude='*.pem'", "--exclude='*.key'", "--exclude='*.p12'", "--exclude='*.pfx'",
      "--exclude='*.db'", "--exclude='*.db-*'", "--exclude='*.sqlite'", "--exclude='*.sqlite3'",
      "--exclude='*.parquet'", "--exclude='*.sarif'", "--exclude='*.tar.gz'", "--exclude='*.zip'",
      "--exclude='*.jsonl'", '--exclude=data', '--exclude=distributed_spool',
      '--exclude=repo_cache', '--exclude=logs', "--exclude='*.log'",
      'malicious-issue-miner-rate-smart'
    )
    $remoteTar = $parts -join ' '
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $sshExe
    $start.Arguments = '-T ' + $Remote + ' "' + $remoteTar + '"'
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $false
    $start.CreateNoWindow = $false

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $start
    $dest = $null
    try {
        if (-not $proc.Start()) { throw 'Could not start Windows ssh.exe.' }
        $dest = [System.IO.File]::Open($archive, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
        $proc.StandardOutput.BaseStream.CopyTo($dest)
        $dest.Flush()
        $dest.Dispose()
        $dest = $null
        $proc.WaitForExit()
        if ($proc.ExitCode -ne 0) { throw "SSH/tar transfer exited with code $($proc.ExitCode)." }
    } catch {
        if ($dest -ne $null) { $dest.Dispose() }
        if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
        throw
    } finally {
        $proc.Dispose()
    }
}

if ((Get-Item -LiteralPath $archive).Length -lt 1024) {
    throw 'Source archive is unexpectedly small. Please inspect it before trusting it.'
}
Write-Host 'Verifying local TAR contents...'
$members = @(& $tarExe -tzf $archive)
if ($LASTEXITCODE -ne 0) { throw 'Local archive verification failed.' }
$members | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'miner_live_source_archive_files.txt')
$hash = Get-FileHash -LiteralPath $archive -Algorithm SHA256
("{0}  {1}" -f $hash.Hash.ToLowerInvariant(), (Split-Path -Leaf $archive)) |
    Set-Content -Encoding ASCII -Path (Join-Path $OutputDirectory 'miner_live_source_readonly.sha256')
Write-Host '[2/4] Reading the existing miner Git history...'
$gitCmd = 'git -C /home-mscluster/astrauss/new/malicious-issue-miner-rate-smart log --all -n 500 --date=iso-strict --pretty=format:%H%x09%ad%x09%s 2>/dev/null'
$commits = @(& $sshExe -T $Remote $gitCmd)
$gitExit = $LASTEXITCODE
if ($gitExit -eq 0 -and $commits.Count -gt 0) {
    $commits | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'miner_git_log_last500.txt')
    Write-Host "Git history: $($commits.Count) lines"
} else {
    'Git log was not available; no source files were changed.' |
        Set-Content -Encoding ASCII -Path (Join-Path $OutputDirectory 'miner_git_log_last500.txt')
    Write-Warning 'Git history unavailable. The source archive may still be recovered.'
}

Write-Host '[3/4] Listing home directories (best effort)...'
$dirCmd = 'find /home-mscluster/astrauss -maxdepth 3 -type d -print 2>/dev/null'
$dirs = @(& $sshExe -T $Remote $dirCmd)
$dirExit = $LASTEXITCODE
$dirs | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'home_directories_depth3.txt')
Write-Host "Directory entries: $($dirs.Count); remote find exit: $dirExit"
if ($dirExit -ne 0) { Write-Warning 'Directory listing may be partial due to inaccessible directories.' }

Write-Host '[4/4] Listing source/archive names (best effort)...'
# The previous script used a long find expression with escaped parentheses and
# nested quotes. Windows OpenSSH could misparse it. Here find prints ordinary
# filenames; extension filtering happens LOCALLY in PowerShell.
$fileCmd = 'find /home-mscluster/astrauss -maxdepth 5 -type f -print 2>/dev/null'
$allFiles = @(& $sshExe -T $Remote $fileCmd)
$fileExit = $LASTEXITCODE
$pattern = '(?i)(\.py|\.sh|\.sbatch|\.slurm|\.ipynb|\.zip|\.tar\.gz|\.tgz|\.yml|\.yaml|\.toml|\.sql|\.ps1|\.js|\.ts|\.tsx|\.r|\.q(l|ls))$|(/requirements[^/]*\.txt$)|(/Dockerfile$)|(/Makefile$)'
$skip = '(?i)/(\.ssh|\.gnupg|\.aws|\.config|\.cache|\.venv|venv|env|node_modules|\.git|__pycache__|\.mypy_cache|\.pytest_cache)/'
$candidates = @($allFiles | Where-Object { ($_ -match $pattern) -and ($_ -notmatch $skip) } | Sort-Object -Unique)
$candidates | Set-Content -Encoding UTF8 -Path (Join-Path $OutputDirectory 'candidate_sources_archives_depth5.txt')
@("remote_find_exit=$fileExit", "total_file_paths_seen=$($allFiles.Count)", "candidate_paths=$($candidates.Count)", 'Any nonzero find exit can indicate partial coverage.') |
    Set-Content -Encoding ASCII -Path (Join-Path $OutputDirectory 'inventory_status.txt')
Write-Host "Found $($candidates.Count) candidate source/archive paths; remote find exit: $fileExit"
if ($fileExit -ne 0) {
    Write-Warning 'The inventory may be partial (permissions or transient find errors). Continuing with source export.'
}

Write-Host 'Local files created or retained:'
Get-ChildItem -LiteralPath $OutputDirectory | Select-Object Name, Length | Format-Table -AutoSize
Write-Host 'Remote cluster files were only READ. Review the archive for secrets before uploading.'
