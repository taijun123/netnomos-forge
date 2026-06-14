# START_W3.ps1 — netnomos-forge W3 一键启动
# 用法：在 netnomos-forge 目录里 PowerShell 执行: .\START_W3.ps1
# 需要：uv（pip install uv 或 winget install astral-sh.uv）、ollama 已安装
#
# 会依次做：
#   Step1  uv sync          安装 forge + NetNomos + LeJIT + 依赖
#   Step2  netn learn       学习 CIDDS 网络规则（约2-5min）
#   Step3  ollama pull      拉取 A 轨诱骗模型
#   Step4  lejit train      训练 B 轨 LeJIT bundle（约30-60min，单卡4090）
#   Step5  uvicorn          启动后端服务（port 8000）
#   Step6  npm install+dev  启动前端（port 5173）

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot          # = E:\yanchh\model_control\netnomos-forge
$Parent = Split-Path $Root

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  netnomos-forge W3 启动脚本" -ForegroundColor Cyan
Write-Host "  工作目录: $Root" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# ---------- Step 1: uv sync ----------
Write-Host "[Step 1/6] uv sync — 安装所有依赖..." -ForegroundColor Yellow
Set-Location $Root
uv sync
Write-Host "[Step 1] 完成`n" -ForegroundColor Green

# ---------- Step 2: NetNomos learn CIDDS ----------
Write-Host "[Step 2/6] NetNomos learn — 学习 CIDDS 网络规则..." -ForegroundColor Yellow
$RuleOut = "$Root\forge\rulesets\network_cidds\golden"
New-Item -ItemType Directory -Force -Path $RuleOut | Out-Null
$DatasetSpec = "$Root\forge\scenarios\network_cidds\dataset_spec.json"
$GrammarSpec = "$Root\forge\scenarios\network_cidds\grammar_spec.json"
if (Test-Path $DatasetSpec) {
    uv run netn learn `
        --dataset $DatasetSpec `
        --grammar $GrammarSpec `
        --learner hitting-set `
        --output "$Root\runs\cidds_golden"
    # 把 rules.json 归档到规则资产目录
    $RunLatest = Get-ChildItem "$Root\runs\cidds_golden" -Directory | Sort-Object LastWriteTime | Select-Object -Last 1
    if ($RunLatest) {
        Copy-Item "$($RunLatest.FullName)\rules.json" "$RuleOut\rules.json" -Force
        Write-Host "  规则归档: $RuleOut\rules.json" -ForegroundColor DarkGray
    }
    Write-Host "[Step 2] 完成`n" -ForegroundColor Green
} else {
    Write-Host "[Step 2] 跳过：dataset_spec.json 不存在（请先确认 forge/scenarios/network_cidds/）" -ForegroundColor Red
}

# ---------- Step 3: ollama 拉模型 ----------
Write-Host "[Step 3/6] ollama pull — 拉取 A 轨诱骗模型（qwen2.5:14b-instruct）..." -ForegroundColor Yellow
try {
    ollama pull qwen2.5:14b-instruct
    Write-Host "[Step 3] 完成`n" -ForegroundColor Green
} catch {
    Write-Host "[Step 3] 警告：ollama 不可用或已有模型，跳过（演示将用 mock 模式）`n" -ForegroundColor DarkYellow
}

# ---------- Step 4: LeJIT train ----------
Write-Host "[Step 4/6] LeJIT train — 训练 B 轨约束生成 bundle（4090 GPU）..." -ForegroundColor Yellow
Write-Host "  预计时间：CIDDS 10k 行 × 10 epoch ≈ 30-60 分钟（单卡）" -ForegroundColor DarkGray
$RulesJson = "$RuleOut\rules.json"
$BundleOut = "$Root\forge\rulesets\network_cidds\lejit_bundle"
New-Item -ItemType Directory -Force -Path $BundleOut | Out-Null
if (Test-Path $RulesJson) {
    $env:CUDA_VISIBLE_DEVICES = "0"
    uv run lejit train `
        --dataset $DatasetSpec `
        --rules $RulesJson `
        --output $BundleOut `
        --epochs 10 `
        --batch-size 32
    Write-Host "[Step 4] LeJIT bundle 训练完成: $BundleOut`n" -ForegroundColor Green
} else {
    Write-Host "[Step 4] 跳过：rules.json 未生成（Step 2 需先成功）`n" -ForegroundColor DarkYellow
}

# ---------- Step 5: 启动后端 ----------
Write-Host "[Step 5/6] 启动 FastAPI 后端 (port 8000)..." -ForegroundColor Yellow
$BackendJob = Start-Job -ScriptBlock {
    param($r)
    Set-Location $r
    uv run uvicorn "server.app:create_app" --factory --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $Root
Write-Host "  后端 PID: $($BackendJob.Id)（后台 Job）" -ForegroundColor DarkGray
Start-Sleep 3
Write-Host "[Step 5] 后端已启动 http://127.0.0.1:8000`n" -ForegroundColor Green

# ---------- Step 6: 启动前端 ----------
Write-Host "[Step 6/6] 启动 Web 前端 (port 5173)..." -ForegroundColor Yellow
$WebDir = "$Root\web"
if (Test-Path "$WebDir\package.json") {
    Set-Location $WebDir
    if (-not (Test-Path "$WebDir\node_modules")) {
        Write-Host "  npm install..." -ForegroundColor DarkGray
        npm install
    }
    $env:VITE_API_BASE = "http://127.0.0.1:8000"
    $FrontendJob = Start-Job -ScriptBlock {
        param($w)
        Set-Location $w
        npm run dev
    } -ArgumentList $WebDir
    Write-Host "  前端 PID: $($FrontendJob.Id)（后台 Job）" -ForegroundColor DarkGray
    Start-Sleep 3
    Write-Host "[Step 6] 前端已启动 http://127.0.0.1:5173`n" -ForegroundColor Green
} else {
    Write-Host "[Step 6] 跳过：web/package.json 不存在`n" -ForegroundColor DarkYellow
}

Set-Location $Root
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  所有服务已启动！" -ForegroundColor Cyan
Write-Host "  后端：http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  前端：http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "  停止后台服务：Get-Job | Stop-Job ; Get-Job | Remove-Job" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
