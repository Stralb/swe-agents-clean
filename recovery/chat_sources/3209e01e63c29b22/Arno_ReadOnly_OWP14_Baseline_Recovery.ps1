# Read-only remote baseline recovery for O/W/P experiments
# This script only downloads files from Wits. All new files are created on your Windows PC.
# It NEVER deletes, renames, or writes any file on the cluster.
param(
    [string]$Remote = 'astrauss@146.141.21.100',
    [string]$OutputDir = (Join-Path $env:USERPROFILE 'Downloads\arno_owp14_baseline_recovery')
)
$ErrorActionPreference = 'Stop'
$remoteFolder = '/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/screen65_codeql_job70675'

if (-not (Get-Command scp.exe -ErrorAction SilentlyContinue)) {
    throw 'Windows OpenSSH scp.exe is required.'
}
if (-not (Test-Path -LiteralPath $OutputDir -PathType Container)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$records = @'
case_id,expected_before_sarif_sha256
00668,a402cd0b8105e6f82f6738ac49bcc9a66931938efaf5fb16c6fb745676f76d40
03429,040947b0dea346bb921d6d9db4abb484b447a75ca490d4a737d3347735fea2b7
03581,406d53383bc7c6b133114ab623bfe63a2f43da6d1450b404d105f1e6d853cc9b
06104,f723dbbe81bde2ee902e59578e8acbffb54d7fba7a36c1adfdbffcf4aadc91fa
08152,9c6c68a5b8e59c9ea792da4a692a9666a225acfca7ee2639080b02c69a615026
08461,56ed78a142eaa09d51b7c9885dd0be15f82cdfaf57878480514df5850a77c0f2
12344,83f148dce104f9ffe65f912b2facc7267803c1510c4a6c7f18dca05796df859c
15151,483dd80b172ece38b672c48cdbd7c1298feacede696b0f5e88e319cd3f21028c
16633,dd58dfe4de8486e1dfe93a48a53fbca2042c6591d9120088e8508705da0c1d4a
20094,d5b0802022eec2f6853a97ad8cb066ed9cd62917def9ea4eb7dd51ce059e83f4
21682,231c7aaf0e1c52d6dfed34db54b4aae79b5d161ce25bce8d6b565c2159a2afc1
22223,4eef475106c89551daf2429ecb7cac3721c71be0bb04aac291cf6061df2a4fb7
31207,8e4b15534458601830f738e6be832d49aba3e0c9f27bf21eb00825a585404ca9
32759,e9855fd469e599b89ae579142a383dd3d1505949dd2714ba78274a4e7908e95b
'@ | ConvertFrom-Csv

$verified = New-Object System.Collections.Generic.List[string]
$receipt = New-Object System.Collections.Generic.List[object]
foreach ($record in $records) {
    $caseId = [string]$record.case_id
    $expected = [string]$record.expected_before_sarif_sha256
    $remoteFile = $Remote + ':' + $remoteFolder + '/CASE_' + $caseId + '/before.sarif'
    $localFile = Join-Path $OutputDir ('CASE_' + $caseId + '_before.sarif')
    Write-Host ('[' + $caseId + '] Checking frozen baseline SARIF')

    if (Test-Path -LiteralPath $localFile -PathType Leaf) {
        $existingHash = (Get-FileHash -LiteralPath $localFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existingHash -eq $expected) {
            Write-Host '  Existing local copy verified (no copy needed).'
            $verified.Add($localFile)
            $receipt.Add([pscustomobject]@{case_id=$caseId;result='PASS_ALREADY_EXISTS';sha256=$existingHash;local_file=$localFile})
            continue
        }
        Write-Warning ('  Existing file has the wrong SHA256. Not overwriting: ' + $localFile)
        $receipt.Add([pscustomobject]@{case_id=$caseId;result='LOCAL_HASH_CONFLICT_NOT_OVERWRITTEN';sha256=$existingHash;local_file=$localFile})
        continue
    }

    # Unique local temporary download path; nothing on Wits is changed.
    $temporary = Join-Path $OutputDir ('CASE_' + $caseId + '_before_' + ([Guid]::NewGuid().ToString('N')) + '.download')
    & scp.exe $remoteFile $temporary
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $temporary -PathType Leaf)) {
        Write-Warning ('  SCP failed for case ' + $caseId + '. Nothing was changed remotely.')
        $receipt.Add([pscustomobject]@{case_id=$caseId;result='SCP_MISSING_OR_FAILED';sha256='';local_file=''})
        continue
    }

    $actual = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        Write-Warning ('  SHA mismatch for ' + $caseId + '. Keeping untrusted downloaded temp file without publishing or overwriting: ' + $temporary)
        $receipt.Add([pscustomobject]@{case_id=$caseId;result='DOWNLOADED_SHA_MISMATCH';sha256=$actual;local_file=$temporary})
        continue
    }

    Move-Item -LiteralPath $temporary -Destination $localFile -ErrorAction Stop
    Write-Host '  SHA-256 verified.'
    $verified.Add($localFile)
    $receipt.Add([pscustomobject]@{case_id=$caseId;result='PASS_DOWNLOADED';sha256=$actual;local_file=$localFile})
}

# One unique receipt and ZIP per run, so previous local recovery attempts are preserved too.
$runLabel = (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + ([Guid]::NewGuid().ToString('N').Substring(0,8))
$receiptPath = Join-Path $OutputDir ('OWP14_baseline_receipt_' + $runLabel + '.csv')
$receipt | Export-Csv -LiteralPath $receiptPath -NoTypeInformation -Encoding UTF8
Write-Host ('Verified baselines: ' + $verified.Count + ' of ' + $records.Count)
Write-Host ('Receipt: ' + $receiptPath)
if ($verified.Count -gt 0) {
    $zipPath = Join-Path $OutputDir ('OWP14_baseline_SARIF_' + $verified.Count + '_verified_' + $runLabel + '.zip')
    $toPack = @($verified.ToArray()) + @($receiptPath)
    Compress-Archive -LiteralPath $toPack -DestinationPath $zipPath -CompressionLevel Optimal
    Write-Host ('Local ZIP for ChatGPT upload: ' + $zipPath)
} else {
    Write-Warning 'No validated baselines downloaded. Share the receipt/output for troubleshooting.'
}
Write-Host 'This script performed no writes, deletes or job operations on the Wits cluster.'
