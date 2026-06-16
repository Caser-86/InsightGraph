# InsightGraph 演示版数据备份脚本
# 用法: powershell -File scripts/backup_demo_data.ps1

param (
    [string]$BackupDir = "backups"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $projectRoot
Set-Location $projectRoot

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

# 备份 SQLite 数据库
$dbPath = "data/research_jobs.db"
if (Test-Path $dbPath) {
    $dbBackupName = Join-Path $BackupDir "research_jobs_$timestamp.db"
    Copy-Item $dbPath $dbBackupName
    Write-Host "[OK] SQLite DB 已备份: $dbBackupName"
} else {
    Write-Host "[WARN] SQLite DB 不存在: $dbPath"
}

# 备份 JSON 任务文件（如存在）
$jsonPath = "data/research_jobs.json"
if (Test-Path $jsonPath) {
    $jsonBackupName = Join-Path $BackupDir "research_jobs_$timestamp.json"
    Copy-Item $jsonPath $jsonBackupName
    Write-Host "[OK] JSON 任务文件已备份: $jsonBackupName"
}

# 清理旧备份（保留最近 10 个）
$dbBackups = Get-ChildItem $BackupDir -Filter "research_jobs_*.db" | Sort-Object LastWriteTime -Descending
if ($dbBackups.Count -gt 10) {
    $dbBackups[10..($dbBackups.Count - 1)] | ForEach-Object {
        Remove-Item $_.FullName
        Write-Host "[CLEANUP] 删除旧备份: $($_.Name)"
    }
}

Write-Host "[DONE] 备份完成"
