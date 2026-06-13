# web_dev.ps1 — 宿主机启动 Web 产品页开发服务器
# ----------------------------------------------------------------------------
# 沙箱内 npm registry 被封锁，无法 npm install；本脚本在宿主机（可联网）执行。
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/host/web_dev.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/host/web_dev.ps1 -Build
# ----------------------------------------------------------------------------
param(
    [switch]$Build,      # 仅构建（tsc -b && vite build），不起 dev 服务
    [switch]$Typecheck   # 仅类型检查（tsc --noEmit）
)

$ErrorActionPreference = "Stop"

# 定位 web 目录（脚本位于 scripts/host/ 下，向上两级到仓库根）
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$webDir = Join-Path $repoRoot "web"

if (-not (Test-Path $webDir)) {
    Write-Error "找不到 web 目录：$webDir"
    exit 1
}

Set-Location $webDir
Write-Host "[web_dev] 工作目录：$webDir" -ForegroundColor Cyan

# 安装依赖（首次或 node_modules 缺失时）
if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
    Write-Host "[web_dev] 未发现 node_modules，执行 npm install ..." -ForegroundColor Yellow
    npm install
} else {
    Write-Host "[web_dev] 已存在 node_modules，跳过安装。" -ForegroundColor DarkGray
}

if ($Typecheck) {
    Write-Host "[web_dev] 类型检查 npm run typecheck ..." -ForegroundColor Cyan
    npm run typecheck
    exit $LASTEXITCODE
}

if ($Build) {
    Write-Host "[web_dev] 构建 npm run build ..." -ForegroundColor Cyan
    npm run build
    Write-Host "[web_dev] 构建完成，产物在 web/dist/" -ForegroundColor Green
    exit $LASTEXITCODE
}

Write-Host "[web_dev] 启动开发服务器 npm run dev（默认 http://localhost:5174）..." -ForegroundColor Green
npm run dev
