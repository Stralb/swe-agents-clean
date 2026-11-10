$ErrorActionPreference = 'Stop'

$BaseUrl = 'http://localhost:11434'
$PlannerModel = 'qwen3.5:4b'
$EmbeddingModel = 'nomic-embed-text:v1.5'

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'Ollama is not installed or is not on PATH. Install Ollama for Windows, reopen PowerShell, then run this script again.'
}

function Wait-ForOllama {
    param([int]$Attempts = 20)

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/tags" -TimeoutSec 3 | Out-Null
            return
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    throw "Ollama did not become available at $BaseUrl."
}

Write-Host 'Checking Ollama...'
try {
    Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/tags" -TimeoutSec 3 | Out-Null
}
catch {
    Write-Host 'Starting Ollama...'
    Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden
    Wait-ForOllama
}

Write-Host "Pulling local query planner: $PlannerModel"
ollama pull $PlannerModel
if ($LASTEXITCODE -ne 0) {
    throw "Failed to pull $PlannerModel."
}

Write-Host "Pulling semantic embedding model: $EmbeddingModel"
ollama pull $EmbeddingModel
if ($LASTEXITCODE -ne 0) {
    throw "Failed to pull $EmbeddingModel."
}

Write-Host 'Warming the embedding model...'
$embedBody = @{
    model = $EmbeddingModel
    input = @('search_query: revenue for a customer')
    truncate = $true
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/embed" -ContentType 'application/json' -Body $embedBody -TimeoutSec 120 | Out-Null

Write-Host 'Warming the query planner...'
$chatBody = @{
    model = $PlannerModel
    stream = $false
    think = $false
    messages = @(
        @{
            role = 'user'
            content = 'Return exactly this JSON object: {"ready":true}'
        }
    )
    format = @{
        type = 'object'
        additionalProperties = $false
        required = @('ready')
        properties = @{
            ready = @{ type = 'boolean' }
        }
    }
    options = @{
        temperature = 0
        num_predict = 32
    }
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/chat" -ContentType 'application/json' -Body $chatBody -TimeoutSec 180 | Out-Null

Write-Host ''
Write-Host 'Installed models:'
ollama list
Write-Host ''
Write-Host 'Smart Reports local models are ready.'
