# generate_network.ps1 — 宿主机用已训练 LeJIT bundle 生成受约束 NetFlow 行
# 用法：powershell -ExecutionPolicy Bypass -File scripts\host\generate_network.ps1 -N 1000
#       powershell -File ...\generate_network.ps1 -N 200 -Gpu 0 -Device cuda
# 前置：先运行 train_network_lejit.ps1 产出 bundle
param(
    [int]$N = 1000,
    [string]$Device = "cpu",     # cpu | cuda
    [string]$Gpu = "",           # 如 "0"，配合 -Device cuda
    [string]$Output = ""         # 缺省 forge\rulesets\network_cidds\generated.csv
)
$ErrorActionPreference = "Stop"

$ForgeRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$LeJIT     = Join-Path $ForgeRoot "LeJIT"
$BundleDir = Join-Path $ForgeRoot "forge\rulesets\network_cidds\lejit_bundle"
$ConfigToml = Join-Path $ForgeRoot "forge\rulesets\network_cidds\lejit_train.toml"
if ($Output -eq "") { $Output = Join-Path $ForgeRoot "forge\rulesets\network_cidds\generated.csv" }

if (-not (Test-Path $BundleDir))  { throw "未找到 bundle：$BundleDir（请先运行 train_network_lejit.ps1）" }
if (-not (Test-Path $ConfigToml)) { throw "未找到配置：$ConfigToml（train_network_lejit.ps1 会生成）" }

# CUDA 设备选择示例
if ($Gpu -ne "") {
    $env:CUDA_VISIBLE_DEVICES = $Gpu
    Write-Host "==> CUDA_VISIBLE_DEVICES=$Gpu" -ForegroundColor Yellow
}

Write-Host "==> lejit generate（n=$N, device=$Device）" -ForegroundColor Cyan
Push-Location $LeJIT
try {
    uv run lejit generate --config $ConfigToml --model-bundle $BundleDir `
        --output $Output --n-samples $N --device $Device
    if ($LASTEXITCODE -ne 0) { throw "lejit generate 失败" }
}
finally { Pop-Location }
Write-Host "==> 完成：生成数据已写入 $Output" -ForegroundColor Green
