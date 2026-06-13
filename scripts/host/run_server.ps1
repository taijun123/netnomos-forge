# run_server.ps1 — 宿主机一键启动 FastAPI 编排服务
# 用法：powershell -ExecutionPolicy Bypass -File scripts\host\run_server.ps1
# 目录约定：<workspace>\netnomos-forge 与 NetNomos、LeJIT 同级（uv.sources 本地路径依赖）
param(
    [int]$Port = 8000,
    [switch]$NoReload                          # 演示录屏时可关掉热重载
)
$ErrorActionPreference = "Stop"

$ForgeRoot = (Resolve-Path "$PSScriptRoot\..\..").Path          # netnomos-forge\
$Workspace = (Resolve-Path "$ForgeRoot\..").Path                 # <workspace>\

foreach ($repo in @("NetNomos", "LeJIT")) {
    if (-not (Test-Path (Join-Path $Workspace $repo))) {
        throw "未找到本地依赖仓库：$Workspace\$repo（需与 netnomos-forge 同级，见 pyproject.toml [tool.uv.sources]）"
    }
}

Push-Location $ForgeRoot
try {
    # 1) 同步依赖（fastapi/uvicorn/sse-starlette/pandas/jinja2 + 本地 netnomos/lejit）
    Write-Host "==> uv sync（netnomos-forge）" -ForegroundColor Cyan
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync 失败" }

    # 2) 启动 uvicorn（--factory：server.app:create_app 为应用工厂）
    Write-Host "==> 启动编排服务 http://localhost:$Port（CORS 已放开 localhost:5173）" -ForegroundColor Cyan
    $args = @("run", "uvicorn", "server.app:create_app", "--factory",
              "--host", "0.0.0.0", "--port", $Port)
    if (-not $NoReload) { $args += "--reload" }
    & uv @args
}
finally { Pop-Location }
