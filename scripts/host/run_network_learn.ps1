# run_network_learn.ps1 — 宿主机一键：NetNomos uv sync → netn learn（cidds）→ 归档黄金规则集
# 用法：powershell -ExecutionPolicy Bypass -File scripts\host\run_network_learn.ps1
# 目录约定：NetNomos 随本仓库放在 netnomos-forge 根目录下
param(
    [string]$Learner = "hitting-set",          # hitting-set | tree
    [int]$Limit = 0,                            # 0 = 全量 10k 行
    [string]$Backend = "auto"                   # hitting-set 后端：auto | native | python
)
$ErrorActionPreference = "Stop"

$ForgeRoot = (Resolve-Path "$PSScriptRoot\..\..").Path          # netnomos-forge\
$NetNomos  = Join-Path $ForgeRoot "NetNomos"
$ScenDir   = Join-Path $ForgeRoot "forge\scenarios\network_cidds"
$DataCsv   = Join-Path $NetNomos "data\cidds_wk2_normal_10k.csv"
$RunsDir   = Join-Path $ForgeRoot "forge\rulesets\network_cidds\runs"
$GoldenDir = Join-Path $ForgeRoot "forge\rulesets\network_cidds\golden"

if (-not (Test-Path $NetNomos)) { throw "未找到 NetNomos 源码目录：$NetNomos（需位于 netnomos-forge 根目录）" }
if (-not (Test-Path $DataCsv))  { throw "未找到训练数据：$DataCsv" }

# 1) 同步 NetNomos 依赖（z3-solver / pydantic 等）
Write-Host "==> uv sync（NetNomos）" -ForegroundColor Cyan
Push-Location $NetNomos
try {
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync 失败" }

    # 2) netn learn（用 forge 场景的 spec；--input 显式传绝对路径，避开相对路径按 cwd 解析的问题）
    Write-Host "==> netn learn（cidds，learner=$Learner）" -ForegroundColor Cyan
    $args = @(
        "run", "netn", "learn",
        "--dataset-spec", (Join-Path $ScenDir "dataset_spec.json"),
        "--grammar-spec", (Join-Path $ScenDir "grammar_spec.json"),
        "--input", $DataCsv,
        "--learner", $Learner,
        "--hittingset-backend", $Backend,
        "--runs-dir", $RunsDir
    )
    if ($Limit -gt 0) { $args += @("--limit", $Limit) }
    & uv @args
    if ($LASTEXITCODE -ne 0) { throw "netn learn 失败" }
}
finally { Pop-Location }

# 3) 把最新 run 的产物复制进 forge/rulesets/network_cidds/golden/
$latest = Get-ChildItem $RunsDir -Directory |
    Where-Object { $_.Name -notmatch "^\." } |
    Sort-Object Name -Descending | Select-Object -First 1
if (-not $latest) { throw "未在 $RunsDir 找到学习产物目录" }

New-Item -ItemType Directory -Force -Path $GoldenDir | Out-Null
foreach ($f in @("rules.json", "semantic_values.json", "interpreted_rules.clj", "manifest.json")) {
    $src = Join-Path $latest.FullName $f
    if (Test-Path $src) { Copy-Item $src -Destination $GoldenDir -Force }
}
Write-Host "==> 完成：黄金规则集已归档到 $GoldenDir（来源 run：$($latest.Name)）" -ForegroundColor Green
