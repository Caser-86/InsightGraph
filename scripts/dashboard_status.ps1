param()

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$runtimeDir = Join-Path $repoRoot ".runtime"
$pidPath = Join-Path $runtimeDir "insightgraph-dashboard.pid"
$metaPath = Join-Path $runtimeDir "insightgraph-dashboard.json"

function Test-Health {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
        return $response.StatusCode
    } catch {
        return $null
    }
}

if (-not (Test-Path $metaPath)) {
    Write-Output "InsightGraph dashboard status: stopped"
    exit 0
}

$meta = Get-Content -Path $metaPath -Raw | ConvertFrom-Json
$pidValue = if (Test-Path $pidPath) { [int](Get-Content -Path $pidPath -Raw).Trim() } else { $null }
$process = if ($pidValue) { Get-Process -Id $pidValue -ErrorAction SilentlyContinue } else { $null }
$health = Test-Health -Url "$($meta.url)/health"

if ($process -and $health -eq 200) {
    Write-Output "InsightGraph dashboard status: running"
    Write-Output "PID: $pidValue"
    Write-Output "URL: $($meta.url)/dashboard"
    exit 0
}

Write-Output "InsightGraph dashboard status: unhealthy"
if ($pidValue) {
    Write-Output "PID: $pidValue"
}
Write-Output "URL: $($meta.url)/dashboard"
exit 1
