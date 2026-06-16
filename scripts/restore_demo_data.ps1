# InsightGraph 演示版数据恢复脚本
# 用法: powershell -File scripts/restore_demo_data.ps1 -BackupFile backups/research_jobs_20260101T000000Z.db

param (
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $projectRoot
Set-Location $projectRoot

if (-not (Test-Path $BackupFile)) {
    Write-Host "[ERROR] 备份文件不存在: $BackupFile"
    exit 1
}

# 停止服务
Write-Host "[INFO] 停止服务..."
docker compose down 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] docker compose down 失败或服务未运行，继续恢复"
}

# 恢复 SQLite 数据库
$dbPath = "data/research_jobs.db"
$targetDir = Split-Path $dbPath -Parent
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

Copy-Item $BackupFile $dbPath -Force
Write-Host "[OK] SQLite DB 已恢复: $BackupFile -> $dbPath"

# 启动服务
Write-Host "[INFO] 启动服务..."
docker compose up -d

# 等待启动
Start-Sleep -Seconds 5

# 健康检查
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 10
    Write-Host "[OK] 服务健康检查通过: $($response.Content)"
} catch {
    Write-Host "[WARN] 服务健康检查失败，请检查日志"
}

Write-Host "[DONE] 恢复完成"
