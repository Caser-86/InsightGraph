param(
    [string]$HostAddress = "127.0.0.1",
    [int]$PreferredPort = 8000,
    [int]$MaxPort = 8010,
    [int]$StartupTimeoutSeconds = 25
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$runtimeDir = Join-Path $repoRoot ".runtime"
$pidPath = Join-Path $runtimeDir "insightgraph-dashboard.pid"
$metaPath = Join-Path $runtimeDir "insightgraph-dashboard.json"
$launcherPath = Join-Path $scriptRoot "local_dashboard_server.py"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Test-Health {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-PortListening {
    param([int]$Port)
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($HostAddress), $Port)
    try {
        $listener.Start()
        return $false
    } catch {
        return $true
    } finally {
        try {
            $listener.Stop()
        } catch {
        }
    }
}

function Get-FreePort {
    for ($port = $PreferredPort; $port -le $MaxPort; $port++) {
        if (-not (Test-PortListening -Port $port)) {
            return $port
        }
    }
    throw "No free port found between $PreferredPort and $MaxPort."
}

function Read-Metadata {
    if (-not (Test-Path $metaPath)) {
        return $null
    }
    try {
        return Get-Content -Path $metaPath -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Remove-StateFiles {
    Remove-Item -Force -ErrorAction SilentlyContinue $pidPath, $metaPath
}

$existingMeta = Read-Metadata
if ($existingMeta -and $existingMeta.url -and (Test-Health -Url "$($existingMeta.url)/health")) {
    Write-Output "InsightGraph dashboard already running at $($existingMeta.url)/dashboard"
    exit 0
}

if (Test-Path $pidPath) {
    try {
        $existingPid = [int](Get-Content -Path $pidPath -Raw).Trim()
        $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existingProcess) {
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    } catch {
    }
    Remove-StateFiles
}

$selectedPort = Get-FreePort
$baseUrl = "http://$HostAddress`:$selectedPort"
$healthUrl = "$baseUrl/health"
$dashboardUrl = "$baseUrl/dashboard"

$process = Start-Process `
    -FilePath python `
    -ArgumentList @($launcherPath, "--host", $HostAddress, "--port", "$selectedPort") `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidPath -Value $process.Id -Encoding ascii

$meta = @{
    pid = $process.Id
    host = $HostAddress
    port = $selectedPort
    url = $baseUrl
    started_at = (Get-Date).ToString("o")
} | ConvertTo-Json
Set-Content -Path $metaPath -Value $meta -Encoding utf8

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        $logTail = ""
        Remove-StateFiles
        throw "InsightGraph dashboard exited during startup.`n$logTail"
    }
    if (Test-Health -Url $healthUrl) {
        Write-Output "InsightGraph dashboard ready at $dashboardUrl"
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

try {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
} catch {
}
Remove-StateFiles
throw "InsightGraph dashboard did not become healthy within $StartupTimeoutSeconds seconds."
