# NetNomos Forge 本地运行指南

本文面向第一次从 Git 仓库拉取项目的同学，目标是在本地把后端、前端和两个主要 demo 跑起来。

以下命令以 Windows PowerShell 为主，因为当前仓库自带的辅助脚本是 PowerShell。macOS/Linux 也可以运行，但需要把 PowerShell 脚本步骤改成等价的 shell 命令。

## 1. 本地环境要求

必需软件：

| 软件 | 建议版本 | 用途 |
|---|---:|---|
| Git | 2.40+ | 拉取仓库 |
| Python | 3.10+ | 后端和核心 SDK |
| uv | 最新稳定版 | Python 依赖同步和运行 |
| Node.js | 20 LTS 或更新 | 前端开发服务器 |
| npm | 随 Node 安装 | 安装前端依赖 |

可选软件：

| 软件 | 用途 |
|---|---|
| Ollama | 规则解释或报告草稿的本地 LLM 增强 |
| NVIDIA CUDA 环境 | 真实 LeJIT 训练或 GPU 推理 |

确认命令：

```powershell
git --version
python --version
uv --version
node --version
npm --version
```

如果没有 `uv`，可任选一种方式安装：

```powershell
winget install astral-sh.uv
```

或：

```powershell
pip install uv
```

## 2. 推荐工作区结构

`netnomos-forge` 已经把 `NetNomos` 和 `LeJIT` 源码目录纳入仓库根目录。请先建一个统一工作区，例如：

```powershell
mkdir E:\model_control
cd E:\model_control
```

最终目录应该长这样：

```text
E:\model_control\
  netnomos-forge\
    NetNomos\
    LeJIT\
    forge\
    server\
    web\
```

原因是 `netnomos-forge/pyproject.toml` 中写了：

```toml
[tool.uv.sources]
netnomos = { path = "NetNomos", editable = true }
lejit = { path = "LeJIT", editable = true }
```

如果目录不按这个结构放，`uv sync` 会找不到仓库内源码依赖。

## 3. Clone 或 pull 代码

第一次拉取：

```powershell
cd E:\model_control

git clone <netnomos-forge 仓库地址> netnomos-forge
```

如果你已经有目录，只是更新到最新代码：

```powershell
cd E:\model_control\netnomos-forge
git pull
```

拉取后请确认仓库根目录里存在 `NetNomos` 和 `LeJIT` 两个目录。如果缺失，说明仓库内容不完整，后端依赖同步会失败。

## 4. 进入项目根目录

```powershell
cd E:\model_control\netnomos-forge
```

后面所有后端命令默认都在这个目录执行。

## 5. 配置环境变量

仓库提供了 `.env.example`。第一次运行可以复制一份：

```powershell
Copy-Item .env.example .env
```

默认配置已经能跑 mock/稳定 demo。常用配置说明：

| 变量 | 默认/建议 | 说明 |
|---|---|---|
| `LOG_LEVEL` | `INFO` | 后端日志级别 |
| `LOG_DIR` | `logs` | 后端日志目录 |
| `VITE_API_BASE` | 留空 | 前端使用同源 `/api`，由 Vite proxy 转发 |
| `FORGE_RULECARD_LLM` | 不设置 | 默认不启用规则卡 LLM 润色 |
| `FORGE_OLLAMA_HOST` | `http://localhost:11434` | 可选 Ollama 地址 |

本地开发建议先不要打开 Ollama 增强，确保基础链路跑通后再加。

## 6. 安装 Python 依赖

在 `netnomos-forge` 根目录执行：

```powershell
uv sync
```

这一步会：

- 创建或更新 `.venv`。
- 安装 FastAPI、uvicorn、pandas、numpy 等后端依赖。
- 以 editable 方式安装仓库内的 `NetNomos` 和 `LeJIT`。
- 按 `pyproject.toml` 拉取 PyTorch CUDA 相关 wheel。

如果这一步报错，优先检查：

1. `NetNomos` 是否存在。
2. `LeJIT` 是否存在。
3. 当前网络是否能访问 PyPI、npm registry 和 PyTorch wheel index。
4. Python 版本是否满足 `>=3.10`。

## 7. 运行后端快速验证

先跑一个不依赖浏览器的快速验证：

```powershell
uv run python scripts/quick_validate.py
```

预期结果：

- 财务链路显示 PASS。
- 网络 pipeline 显示 PASS。
- 最后一行提示全部验证通过。

再跑核心 pipeline 测试：

```powershell
uv run python -m pytest tests/test_pipeline.py
```

如果要跑完整 Python 测试：

```powershell
uv run python -m pytest
```

## 8. 启动后端服务

推荐命令：

```powershell
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000
```

开发时如果需要热更新，可加 `--reload`：

```powershell
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

演示录屏时建议不加 `--reload`，因为后端 job store 是内存态，reload 可能造成状态不一致。

后端启动成功后，打开：

```text
http://127.0.0.1:8000/api/health
```

预期返回类似：

```json
{"status":"ok","jobs":0}
```

也可以打开 FastAPI 文档：

```text
http://127.0.0.1:8000/docs
```

## 9. 安装前端依赖

新开一个 PowerShell 窗口，进入前端目录：

```powershell
cd E:\model_control\netnomos-forge\web
npm install
```

如果之前安装过但依赖异常，可以删除 `node_modules` 后重装：

```powershell
Remove-Item -Recurse -Force node_modules
npm install
```

不要删除 `package-lock.json`，除非你明确要重新锁定依赖版本。

## 10. 启动前端服务

继续在 `web/` 目录执行：

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

启动后打开：

```text
http://127.0.0.1:5173/
```

常用页面：

```text
http://127.0.0.1:5173/?v=w4source#/finance
http://127.0.0.1:5173/?v=w4source#/network
http://127.0.0.1:5173/?v=office#/office
http://127.0.0.1:5173/#/workspace
http://127.0.0.1:5173/#/log-demo
```

前端访问 `/api` 时会通过 `web/vite.config.ts` 自动代理到 `http://127.0.0.1:8000`。如果你手动设置了 `VITE_API_BASE`，请确保它指向正确后端，例如：

```powershell
$env:VITE_API_BASE = "http://127.0.0.1:8000"
npm run dev -- --host 127.0.0.1 --port 5173
```

## 11. 一键启动方式

仓库根目录有一个快速脚本：

```powershell
cd E:\model_control\netnomos-forge
powershell -ExecutionPolicy Bypass -File .\QUICK_START.ps1
```

这个脚本会依次执行：

1. `uv sync`
2. `uv run python scripts\quick_validate.py`
3. 启动 FastAPI 后端到 `8000`
4. 启动 Web 前端到 `5173`

如果是第一次跑项目，建议先按本文第 6 到第 10 步手动跑一遍。手动跑通后，再用一键脚本更容易定位问题。

## 12. 跑通财务 demo

确认后端和前端都已启动。

打开：

```text
http://127.0.0.1:5173/?v=w4source#/finance
```

操作步骤：

1. 查看训练资料预览。
2. 点击规则学习或加载规则。
3. 上传演示文件：

   ```text
   demo_artifacts/w4_demo_assets/finance/huaxin_audit_package.csv
   ```

4. 运行资料规则核查。
5. 输入或复制财务报告问题。
6. 运行 A/B 双轨对比。
7. 查看 A 轨错误数字、B 轨修正结果、违规明细和报告预览。

如果页面提示后端连接失败，先访问：

```text
http://127.0.0.1:8000/api/health
```

如果 health 不通，说明后端没有启动或端口不对。

## 13. 跑通网络 demo

打开：

```text
http://127.0.0.1:5173/?v=w4source#/network
```

操作步骤：

1. 确认内置 CIDDS 训练资料。
2. 加载归档 NetNomos 规则。
3. 查看规则卡。
4. 上传演示文件：

   ```text
   demo_artifacts/w4_demo_assets/network/netflow_rule_anomaly_upload.csv
   ```

5. 运行新资料规则核查。
6. 输入或复制网络报告问题。
7. 运行 A/B 双轨对比。
8. 查看 A 轨违规 NetFlow、B 轨合规样本和报告预览。

## 14. 跑通办公室 demo

打开：

```text
http://127.0.0.1:5173/?v=office#/office
```

操作建议：

1. 点击办公室成员或工作区元素。
2. 打开规则集或产物面板。
3. 触发 office workflow。
4. 等待工作流事件完成。
5. 在聊天区域提问，检查 `/api/chat/constrained` 是否基于后端缓存状态返回回答。

办公室 demo 更偏产品化演示，财务和网络 demo 更适合展示底层规则控制能力。

## 15. 常用开发命令

后端：

```powershell
cd E:\model_control\netnomos-forge
uv sync
uv run python scripts/quick_validate.py
uv run python -m pytest
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000
```

前端：

```powershell
cd E:\model_control\netnomos-forge\web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
npm run typecheck
npm run build
```

检查 API：

```powershell
curl http://127.0.0.1:8000/api/health
```

上传财务演示文件：

```powershell
curl -X POST http://127.0.0.1:8000/api/data-sources `
  -F "scenario=finance_v1" `
  -F "note=demo upload" `
  -F "file=@demo_artifacts/w4_demo_assets/finance/huaxin_audit_package.csv"
```

启动财务 workflow：

```powershell
curl -X POST http://127.0.0.1:8000/api/rulesets/learn `
  -H "Content-Type: application/json" `
  -d "{\"scenario\":\"finance_v1\",\"sequence\":\"learn-finance\"}"
```

## 16. 可选 Ollama 配置

基础 demo 不要求 Ollama。需要本地 LLM 增强时，再执行：

```powershell
ollama serve
ollama pull qwen2.5:14b-instruct
ollama pull gemma3:27b
```

在另一个 PowerShell 中设置：

```powershell
$env:FORGE_OLLAMA_HOST = "http://localhost:11434"
$env:FORGE_RULECARD_LLM = "true"
$env:FORGE_RULECARD_LLM_MAX_CARDS = "2"
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000
```

如果 Ollama 不可用，系统会按 `ollama -> codex -> mock` 降级，不影响基础演示跑通。

## 17. 常见问题排查

### 17.1 `uv sync` 找不到 NetNomos 或 LeJIT

检查目录：

```powershell
Get-ChildItem E:\model_control\netnomos-forge
```

必须能看到：

```text
NetNomos
LeJIT
```

如果目录名不一致，要么重命名目录，要么修改 `pyproject.toml` 的 `[tool.uv.sources]`。

### 17.2 后端启动后前端仍然报 API 错误

检查：

1. 后端是否在 `8000`：

   ```text
   http://127.0.0.1:8000/api/health
   ```

2. 前端是否在 `5173`：

   ```text
   http://127.0.0.1:5173/
   ```

3. 是否错误设置了 `VITE_API_BASE`。
4. 浏览器控制台是否有 CORS 或 404。

### 17.3 端口被占用

查看端口：

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

换端口启动后端：

```powershell
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8010
```

如果后端不是 `8000`，前端需要设置：

```powershell
$env:VITE_API_BASE = "http://127.0.0.1:8010"
npm run dev -- --host 127.0.0.1 --port 5173
```

### 17.4 上传失败

检查：

1. 上传请求是否是 `multipart/form-data`。
2. 表单字段名是否为 `file`。
3. `scenario` 是否为 `finance_v1`、`network_cidds`、`network_pcap` 或 `office_demo`。
4. 后端是否能写入：

   ```text
   demo_artifacts/uploads/<scenario>/
   ```

### 17.5 workflow 一直 running

处理步骤：

1. 打开后端控制台，看是否有异常。
2. 查询 job：

   ```text
   http://127.0.0.1:8000/api/jobs/<jobId>
   ```

3. 如果后端异常退出，重启后端并重新跑 demo。当前 job store 不持久化，旧 job 无法恢复。

### 17.6 Windows 中文或编码显示异常

可以在 PowerShell 中启用 UTF-8：

```powershell
$env:PYTHONUTF8 = "1"
chcp 65001
```

然后重新运行后端或测试命令。

## 18. 停止服务

如果是前台启动的服务，直接在对应 PowerShell 窗口按 `Ctrl+C`。

如果用了 `QUICK_START.ps1`，它会用 PowerShell background job 启动服务。停止方式：

```powershell
Get-Job
Get-Job | Stop-Job
Get-Job | Remove-Job
```

## 19. 最小成功标准

本地环境算跑通，需要满足：

1. `uv run python scripts/quick_validate.py` 通过。
2. `http://127.0.0.1:8000/api/health` 返回 `status: ok`。
3. `http://127.0.0.1:5173/?v=w4source#/finance` 能打开。
4. 财务 demo 能上传 `huaxin_audit_package.csv` 并跑出 A/B 报告。
5. 网络 demo 能上传 `netflow_rule_anomaly_upload.csv` 并跑出规则核查结果。
