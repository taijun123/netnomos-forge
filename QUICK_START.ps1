# QUICK_START.ps1 - mock 模式演示（无 GPU/ollama）
# 用法: cd E:\yanchh\model_control\netnomos-forge; .\QUICK_START.ps1

$Root = $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "[1/4] uv sync..." -ForegroundColor Yellow
uv sync
Write-Host "[1/4] 完成" -ForegroundColor Green

Write-Host ""
Write-Host "[2/4] 全链路验证..." -ForegroundColor Yellow
uv run python scripts\quick_validate.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "验证失败，请检查输出" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[3/4] 启动 FastAPI 后端 (port 8000)..." -ForegroundColor Yellow
$BackendJob = Start-Job -ScriptBlock {
    param($r)
    Set-Location $r
    uv run uvicorn "server.app:create_app" --factory --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $Root
Start-Sleep 4
Write-Host "[3/4] 后端已启动" -ForegroundColor Green

Write-Host ""
Write-Host "[4/4] 启动 Web 前端 (port 5173)..." -ForegroundColor Yellow
$WebDir = "$Root\web"
if (Test-Path "$WebDir\package.json") {
    # 删除软链接（沙箱遗留），确保 npm install 装到本目录
    $nm = "$WebDir\node_modules"
    if (Test-Path $nm) {
        $item = Get-Item $nm -Force
        if ($item.LinkType -ne $null) {
            Write-Host "  检测到 node_modules 软链接，正在移除..." -ForegroundColor DarkGray
            Remove-Item $nm -Force
        }
    }
    if (-not (Test-Path $nm)) {
        Write-Host "  npm install..." -ForegroundColor DarkGray
        npm install --prefix $WebDir
    }
    $env:VITE_API_BASE = "http://localhost:8000"
    Start-Job -ScriptBlock {
        param($w)
        Set-Location $w
        npm run dev
    } -ArgumentList $WebDir | Out-Null
    Start-Sleep 3
    Write-Host "[4/4] 前端已启动" -ForegroundColor Green
} else {
    Write-Host "[4/4] 跳过：web/package.json 不存在" -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  演示就绪 (mock 模式)" -ForegroundColor Cyan
Write-Host "  前端: http://localhost:5173" -ForegroundColor Cyan
Write-Host "  API:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  停止: Get-Job | Stop-Job | Remove-Job" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
