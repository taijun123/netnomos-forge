# train_network_lejit.ps1 — 宿主机训练 LeJIT bundle（network_cidds 场景）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\host\train_network_lejit.ps1
#       powershell -File ...\train_network_lejit.ps1 -Gpu 0          # 用 0 号 GPU
#       powershell -File ...\train_network_lejit.ps1 -RulesJson <自定义 rules.json>
# 目录约定：LeJIT、NetNomos 随本仓库放在 netnomos-forge 根目录下
param(
    [string]$RulesJson = "",      # 缺省用 forge\rulesets\network_cidds\golden\rules.json
    [string]$Gpu = "",            # 如 "0"；留空 = 不设 CUDA_VISIBLE_DEVICES（CPU 或默认 GPU）
    [int]$Epochs = 3
)
$ErrorActionPreference = "Stop"

$ForgeRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$LeJIT     = Join-Path $ForgeRoot "LeJIT"
$NetNomos  = Join-Path $ForgeRoot "NetNomos"
$ScenDir   = Join-Path $ForgeRoot "forge\scenarios\network_cidds"
$BundleDir = Join-Path $ForgeRoot "forge\rulesets\network_cidds\lejit_bundle"
$ConfigOut = Join-Path $ForgeRoot "forge\rulesets\network_cidds\lejit_train.toml"

if ($RulesJson -eq "") { $RulesJson = Join-Path $ForgeRoot "forge\rulesets\network_cidds\golden\rules.json" }
if (-not (Test-Path $LeJIT))     { throw "未找到 LeJIT 源码目录：$LeJIT" }
if (-not (Test-Path $RulesJson)) { throw "未找到规则文件：$RulesJson（请先运行 run_network_learn.ps1）" }

# CUDA 设备选择示例：-Gpu 0 → 只暴露 0 号卡给 torch
if ($Gpu -ne "") {
    $env:CUDA_VISIBLE_DEVICES = $Gpu
    Write-Host "==> CUDA_VISIBLE_DEVICES=$Gpu" -ForegroundColor Yellow
}

# 生成训练配置（绝对路径，cwd 无关）
$DataCsv     = Join-Path $NetNomos "data\cidds_wk2_normal_10k.csv"
$DatasetSpec = Join-Path $ScenDir "dataset_spec.json"
# TOML 路径用正斜杠，避免反斜杠转义问题
function ToToml([string]$p) { return $p -replace "\\", "/" }
@"
[dataset]
dataset_spec = "$(ToToml $DatasetSpec)"
input_path = "$(ToToml $DataCsv)"
rules_path = "$(ToToml $RulesJson)"

[model]
mode = "config"
architecture = "gpt2"

[model.config_overrides]
n_positions = 512
n_ctx = 512
n_embd = 256
n_layer = 6
n_head = 8

[serialization]
numeric_precision = 6

[training]
epochs = $Epochs
batch_size = 16
learning_rate = 0.0005
logging_steps = 10
save_steps = 100
seed = 42

[decoding]
temperature = 1.0
do_sample = true

[run]
n_samples = 100
batch_size = 1
samples_per_prompt = 1
"@ | Set-Content -Encoding UTF8 $ConfigOut

Write-Host "==> uv sync + lejit train（LeJIT，输出 $BundleDir）" -ForegroundColor Cyan
Push-Location $LeJIT
try {
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync 失败" }
    uv run lejit train --config $ConfigOut --output $BundleDir
    if ($LASTEXITCODE -ne 0) { throw "lejit train 失败" }
}
finally { Pop-Location }
Write-Host "==> 完成：bundle 已写入 $BundleDir" -ForegroundColor Green
