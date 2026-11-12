# Downloads the 42 frozen O/W/P coding-input ZIPs from the Wits HPC cluster.
# This script downloads files only; it does not execute any repositories or agent code.
$ErrorActionPreference = 'Stop'
$Destination = Join-Path $HOME 'Downloads\OWP14'
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$Remote = 'astrauss@146.141.21.100:/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/owp14_allcases_packets_job71014'
scp "$Remote/CASE_*.zip" $Destination
if ($LASTEXITCODE -ne 0) { throw 'SCP failed for ZIP packets.' }
scp "$Remote/PACKET_INDEX.csv" $Destination
if ($LASTEXITCODE -ne 0) { throw 'SCP failed for packet index.' }
scp "$Remote/READ_THIS_FIRST.txt" $Destination
if ($LASTEXITCODE -ne 0) { throw 'SCP failed for instructions.' }
$count = @(Get-ChildItem -Path $Destination -Filter 'CASE_*.zip' -File).Count
Write-Host "Packets downloaded: $count / 42" -ForegroundColor Cyan
if ($count -ne 42) { throw "Expected 42 packets; got $count. Check transfer." }
Write-Host "Saved to $Destination"
