# 留 git 回退点: 把当前工作区全部改动提交为 checkpoint
# 用法: powershell -File scripts\checkpoint.ps1 ["checkpoint 说明"]
# 回退: git log --oneline -5 找到 checkpoint 后 git reset --hard <sha> (现场丢失前先再跑一次本脚本)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

# 首次使用: 初始化仓库并配置本地身份
if (-not (Test-Path .git)) {
    git init
}
if (-not (git config user.name)) {
    git config user.name "dev-agent"
}
if (-not (git config user.email)) {
    git config user.email "dev-agent@local"
}

git add -A
$msg = if ($args.Count -gt 0) { $args -join ' ' } else { "checkpoint $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" }
git commit -m "[checkpoint] $msg" --no-verify
Write-Host "checkpoint 已提交: $(git rev-parse --short HEAD)"
git log --oneline -3
