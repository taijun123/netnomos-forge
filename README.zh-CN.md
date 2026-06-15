# NetNomos Forge

[English](README.md) | [中文](README.zh-CN.md)

NetNomos Forge 是一个把 **NetNomos 规则自发现**、**LeJIT 约束生成**、**RAG 规则解释** 和 **A/B 双轨合规报告** 串成产品演示链路的工程。

项目目标不是修改基础模型，而是在模型外侧建立一套可审计、可解释、可复用的规则控制层：从数据中发现规则，解释规则，核查新资料，并对比“裸模型输出”和“规则约束输出”的差异。

当前 W4 演示覆盖两个垂直场景：

- **网络流量**：CIDDS/NetFlow 规则自发现、规则卡解释、新资料核查、A/B 约束生成对比。
- **财务报表**：合成财务训练数据、华信咨询错误注入资料包、勾稽核查、数值投影修正、A/B 报告对比。

## 文档入口

- [项目架构说明](framework.md)：介绍 Web 前端、FastAPI 后端、核心 SDK、NetNomos、LeJIT、RAG/LLM 和场景工作流。
- [本地运行指南](LOCAL_RUN_GUIDE.md)：从 clone/pull 仓库到本地启动后端、前端和 demo 的详细步骤。

## 项目展示的能力

NetNomos Forge 展示一条“不改模型，只加规则”的产品路径：

1. 上传或选择数据源。
2. 从干净训练数据中发现或加载规则。
3. 用场景知识库和 citation 解释规则。
4. 上传新的待核查资料。
5. 运行规则核查并生成违规清单。
6. 输入报告问题。
7. 对比两条路径：
   - **A 轨**：裸模型或确定性 mock 输出。
   - **B 轨**：规则核查、数值投影、槽位回填后的受控输出。
8. 预览并下载报告。

核心价值是让用户看到：流畅但不受控的模型输出，和经过显式规则约束的可审计输出之间的差异。

## 当前 W4 状态

已完成：

- FastAPI 后端：后台 job、SSE 事件流、job result 查询。
- `/api/data-sources` 支持 multipart 文件上传，文件保存到 `demo_artifacts/uploads/<scenario>/`。
- workflow job 透传请求上下文：`dataSourceId`、`trainingDataSourceId`、`validationDataSourceId`、`question`、`reportPrompt`。
- 前端规则来源 badge：`learned` 显示为“数据自发现”，`manual` 显示为“人工领域规则”。
- 网络 demo 加载 NetNomos 已归档 CIDDS golden 自发现规则。
- 财务 demo 可以核查注入的财务错误，并生成 A/B 双轨报告。
- 工作流进度 UI 显示当前阶段和处理器，例如 NetNomos hitting-set/Z3、RuleExplainer/RAG、规则核查、数值投影、A/B 报告生成。
- 两个 demo 都有独立演示资产目录，包含上传文件、正确数据、prompts 和 README。

需要如实说明的 W4 边界：

- 上传文件已经会保存、登记 `dataSourceId`，并随 workflow job 传给后端。
- 当前核查结果和 A/B 输出仍复用稳定场景管线，不是对任意上传 CSV/PDF/PCAP 做通用逐行解析。
- 这是为了 W4 演示稳定性，已在演示资产 README 中明确说明。

## 目录结构

```text
netnomos-forge/
├── forge/                         核心 SDK 与场景逻辑
│   ├── contracts.py               全项目冻结契约，谨慎修改
│   ├── core/                      engine / explainer / llm / generator / projector / reporter
│   ├── scenarios/                 场景 spec、知识库、生成器、校验器
│   └── rulesets/                  学习产物、golden 规则、LeJIT bundle
├── server/                        FastAPI 编排器、SSE job、内存 store
├── web/                           React/Vite 产品演示界面
├── NetNomos/                      随仓库携带的 NetNomos 源码依赖
├── LeJIT/                         随仓库携带的 LeJIT 源码依赖
├── demo_artifacts/                演示上传资产、上传文件、报告产物
├── scripts/                       验证脚本和宿主机辅助脚本
├── tests/                         Python 测试
└── ...
```

推荐检出结构，其中 `<workspace>` 表示你自己选择的任意本地工作目录：

```text
<workspace>/
└── netnomos-forge/
    ├── NetNomos/
    ├── LeJIT/
    ├── forge/
    ├── server/
    └── web/
```

`pyproject.toml` 通过本地 editable dependency 引用仓库内的 `NetNomos` 和 `LeJIT`。

## 演示资产

演示时优先打开总说明：

```text
demo_artifacts/w4_demo_assets/user.md
```

财务 demo：

```text
demo_artifacts/w4_demo_assets/finance/
├── huaxin_audit_package.csv                  在财务“资料上传”步骤上传这个文件
├── finance_training_clean_960_correct.csv    960 行正确训练数据，英文列名
├── finance_training_clean_960_correct_zh.csv 960 行正确训练数据，中文列名
├── huaxin_clean_reference.csv                华信咨询 8 期正确对照资料
├── truth_table.json                          错误注入真值表
├── prompts.md                                可复制问题和讲解词
└── README.md                                 场景操作说明和限制
```

网络 demo：

```text
demo_artifacts/w4_demo_assets/network/
├── netflow_rule_anomaly_upload.csv             在网络“新资料核查”步骤上传这个文件
├── cidds_wk2_normal_10k_correct_training.csv  10,000 行 CIDDS 正常训练流量
├── network_generated_10_reference.csv         10 行生成样本参考
├── network_b_track_reference_sample.json      B 轨 0 违规合规样本
├── prompts.md                                 可复制问题和讲解词
└── README.md                                  场景操作说明和限制
```

## 快速启动

把仓库 clone 到任意工作目录：

```powershell
$Workspace = "C:\path\to\workspace"
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
Set-Location $Workspace
git clone https://github.com/taijun123/netnomos-forge.git
Set-Location netnomos-forge
```

安装依赖：

```powershell
uv sync
```

运行验证：

```powershell
uv run python scripts/quick_validate.py
uv run python -m pytest tests/test_pipeline.py
```

启动后端：

```powershell
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000
```

启动前端：

```powershell
cd web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

打开：

```text
http://127.0.0.1:5173/?v=w4source#/network
http://127.0.0.1:5173/?v=w4source#/finance
```

## 后端 API 概览

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/data-sources` | 登记或上传数据源；multipart 文件保存到 `demo_artifacts/uploads/<scenario>/`。 |
| `POST` | `/api/rulesets/upload` | 按场景加载默认或指定规则文件。 |
| `POST` | `/api/rulesets/learn` | 启动后台 workflow job。 |
| `GET` | `/api/rulesets/{ruleset_id}/cards` | 获取规则卡。 |
| `POST` | `/api/reports/generate` | 同步生成 A/B 双轨报告。 |
| `GET` | `/api/workflow/events/stream` | 按 `sequence` 或 `job_id` 订阅 workflow 事件。 |
| `GET` | `/api/jobs/{job_id}` | 查询 job 状态、事件、请求上下文和最终产物。 |
| `POST` | `/api/chat/constrained` | 起草回复，并用 B 轨合规槽位白名单检查数值。 |
| `GET` | `/api/health` | 健康检查。 |

支持的场景 ID：

- `finance_v1`
- `network_cidds`
- `network_pcap` 当前复用网络管线。

## 前端演示流程

财务：

1. 预览正确合成训练资料。
2. 学习/加载财务规则。
3. 上传 `huaxin_audit_package.csv`。
4. 运行资料规则核查。
5. 输入报告问题。
6. 运行 A/B 双轨对比。
7. 预览并下载报告。

网络：

1. 确认内置 CIDDS 训练资料。
2. 加载 NetNomos 已归档自发现规则。
3. 查看规则卡和规则来源。
4. 上传 `netflow_rule_anomaly_upload.csv`。
5. 运行新资料核查。
6. 输入报告问题。
7. 运行 A/B 双轨对比。
8. 预览并下载报告。

## LLM 与 RAG 配置

Ollama 是可选增强。如果 Ollama 不可用，系统会按 `ollama -> codex -> mock` 降级，保证 demo 可重复。

常用环境变量：

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `FORGE_RULECARD_LLM` | 空 | 设为 `1/true/yes/on` 才启用 LLM 规则卡润色。 |
| `FORGE_RULECARD_LLM_MAX_CARDS` | `2` | 每个 workflow 最多润色多少张规则卡。 |
| `FORGE_RAG_TOP_K` | `3` | 每条规则最多取多少个知识片段。 |
| `FORGE_RAG_MAX_SECTION_CHARS` | `1200` | 单个知识片段最大字符数。 |
| `FORGE_RAG_MAX_CONTEXT_CHARS` | `3600` | prompt 中 RAG 上下文最大字符数。 |
| `FORGE_OLLAMA_EXPLAIN_MODEL` | `gemma3:27b` | explain 角色默认 Ollama 模型。 |
| `FORGE_OLLAMA_DRAFT_MODEL` | `qwen2.5:14b-instruct` | draft 角色默认 Ollama 模型。 |
| `FORGE_OLLAMA_HOST` / `OLLAMA_HOST` | `http://localhost:11434` | Ollama 地址。 |

## 测试

常用检查：

```powershell
uv run python scripts/quick_validate.py
uv run python -m pytest tests/test_pipeline.py
cd web
npm run build
```

已知限制：

- Windows 默认编码下，部分 NetNomos 上游读取可能遇到 GBK/UTF-8 问题，需要启用 UTF-8 模式。
- W4 尚未实现任意上传 PDF/Word/PCAP/CSV 的通用逐行解析。
- 内存 job store 足够 demo 使用，但后端重启后不会持久保留 job。
- 财务完整 workflow 可能需要几十秒，因为会跑完整场景管线。

## 开发约定

- `forge/contracts.py` 是核心契约，除非明确重订契约，否则不要修改。
- 上层代码通过 `forge` API 访问能力，不直接依赖 NetNomos/LeJIT 内部实现。
- 重依赖采用懒加载，保证受限环境下仍可 import 和跑纯 Python 测试。
- B 轨报告正文应通过受控槽位生成；数值必须来自校验数据或投影修正。
