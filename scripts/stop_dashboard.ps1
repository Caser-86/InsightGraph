param()

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$runtimeDir = Join-Path $repoRoot ".runtime"
$pidPath = Join-Path $runtimeDir "insightgraph-dashboard.pid"
$metaPath = Join-Path $runtimeDir "insightgraph-dashboard.json"

if (-not (Test-Path $pidPath)) {
    Write-Output "InsightGraph dashboard is not running."
    exit 0
}

try {
    $pidValue = [int](Get-Content -Path $pidPath -Raw).Trim()
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        Write-Output "Stopped InsightGraph dashboard process $pidValue."
    } else {
        Write-Output "Removed stale InsightGraph dashboard PID file."
    }
} finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $pidPath, $metaPath
}
