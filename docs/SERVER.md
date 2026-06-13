# SERVER.md — 编排服务与双轨报告管线（二波 / Server-Dev）

本文档覆盖 `server/`（FastAPI 编排器）、`forge/core/{projector,reporter,explainer}.py`
（双轨报告管线）、根 `pyproject.toml` 与 `scripts/host/run_server.ps1`。

---

## 1. 宿主机启动步骤

目录约定：`<workspace>/netnomos-forge` 与 `NetNomos`、`LeJIT` 同级
（根 `pyproject.toml` 的 `[tool.uv.sources]` 用本地路径依赖引用两仓库）。

```powershell
# 一键（推荐）
powershell -ExecutionPolicy Bypass -File scripts\host\run_server.ps1

# 或手动
cd <workspace>\netnomos-forge
uv sync
uv run uvicorn server.app:create_app --factory --port 8000 --reload
```

- CORS 已放开 `http://localhost:5173`（web 前端 `scripts/host/web_dev.ps1`）。
- 可选增强：本地 `ollama serve`（A 轨诱骗 / B 轨起草用 qwen2.5；
  规则卡解释默认 `gemma3:27b`）。Ollama 不可用时按 `ollama → codex → mock`
  降级；mock 保持确定性。
- 规则卡 RAG 采用“英文控制、最终中文输出”：prompt 用英文约束输出格式和任务，
  模型最终只返回 2-4 句简体中文解释，降低中文长 prompt 的模板不稳定性。
- W4 UI 不卡死策略：规则卡 LLM 默认关闭，只做 RAG citation；设置
  `FORGE_RULECARD_LLM=1` 才会润色规则卡，且 `FORGE_RULECARD_LLM_MAX_CARDS`
  默认只润色 2 张。
- 沙箱 / 未 `uv sync` 环境：`import server.app` 安全，调用 `create_app()`
  抛中文指引（fastapi 全懒加载）；管线函数 `server.pipeline.run_*` 不依赖
  fastapi，可直接调用。

冒烟（不起 HTTP）：

```bash
python -m server.app
# → {"events": 18, "violations": 5, "diff_html_bytes": ...}
```

## 2. REST 端点表（contracts API_* 全部 7 个）

| 方法 | 路径 | 入参（JSON） | 出参 | 说明 |
|---|---|---|---|---|
| POST | `/api/data-sources` | `{scenario, filename?, note?}` | `{dataSourceId}` | 登记数据源。演示数据由管线内部确定性构造，不落盘大文件 |
| POST | `/api/rulesets/upload` | `{scenario, rules_path?}` | `{rulesetId, ruleCount}` | 上传/选择规则集；缺省加载场景默认规则（财务 manual_rules.json / 网络 golden_cidds） |
| POST | `/api/rulesets/learn` | `{scenario, sequence?}` | `{jobId, status}` | 后台线程跑完整管线，事件入 SSE 流 |
| GET | `/api/rulesets/{ruleset_id}/cards` | — | `{rulesetId, cards[]}` | 规则卡（RuleCard JSON，含 is_coincidence / citation） |
| POST | `/api/reports/generate` | `{scenario}` | `{jobId, report}` | 同步生成 DualReport（track_a/track_b/diff_html），秒级 |
| GET | `/api/workflow/events/stream` | `?sequence=` 或 `?job_id=` | SSE | `sequence` 取前端 MockSequenceId（learn-finance 等），自动启动对应管线；`job_id` 续接已有任务（历史回放 + 实时） |
| GET | `/api/jobs/{job_id}` | — | `{job_id, jobId, scenario, sequence, status, error, events, result}` | 查询后台任务状态、历史事件与完成产物；供 W4 Web 在 SSE 结束后拉取真实规则卡/报告 |
| POST | `/api/chat/constrained` | `{message, scenario?}` | `{reply, flagged_numbers, checks, backend}` | llm 起草 + 回复数值过 B 轨槽位白名单校验 |

辅助端点：`GET /api/health`。

`scenario` 取值：`finance_v1` / `network_cidds`（`network_pcap` 暂复用网络管线）。

## 3. SSE 事件示例

事件结构 = `contracts.WorkflowEvent.to_sse()`，与 `web/src/lib/events.ts` 兼容
（命名事件 `workflow`，前端同时兼容默认 message）：

```text
GET /api/workflow/events/stream?sequence=report-finance

event: workflow
data: {"id": "a1b2c3d4e5f6", "time": "2026-06-13T10:00:01", "agent": "A", "stage": "control", "status": "running", "description": "财务双轨报告任务开始编排。"}

event: workflow
data: {"id": "...", "time": "...", "agent": "B", "stage": "upload", "status": "running", "description": "接收「华信咨询」待审资料包…"}

: ping        ← 空闲心跳（2s）

event: workflow
data: {"id": "...", "time": "...", "agent": "E", "stage": "project", "status": "done", "description": "投影完成：5 处数值修正，2 条风险提示。"}
```

财务管线 stage 顺序：`control → upload → prepare → learn → explain →
validate → project → report → diff → control(done)`；
网络管线无 validate/project 段。agent 由 `contracts.STAGE_AGENT` 推导
（upload/prepare=B、learn=C、explain/validate=D、project/report/diff=E、control=A）。

## 4. 双轨报告管线

```
finance_v1:
  build_clean_package → inject_faults(F1–F4, 真值表)
    ├─ A 轨 track_a()：LLM(role=induce) 照抄错误资料写报告
    │     mock 降级 → 确定性叙事（逐期照抄错误数字 + 用错数连带算错毛利率）
    └─ B 轨 track_b()：FinanceValidator.validate（命中 R01/R02/R04/R06/R07）
          → Projector.project（R01→修 COGS+连带毛利；R02→重算负债总计；
             R03/R04→以上期期末为准；R06/R07→仅风险提示不改数）
          → 槽位计算（70 个槽位全部由违规清单/修正后 DataFrame 推导）
          → report_template.md {{slot}} 程序回填
          → 终检：残留槽位扫描 + 裸数字白名单（正文每个数值必须来自槽位）
  diff_html：A 轨错误数字 <span class="err mark-num mark-bad" title="命中R01：应为 2,000">3,000</span>
             B 轨对应   <span class="ok mark-num mark-ok">2,000</span>
             （类名对齐 web FinanceDemoPage：mark-num/mark-bad/mark-ok、track-col/track-a/track-b）

network_cidds:
  A 轨：LLM 生成 10 条 NetFlow；mock 降级 → 确定性带错样本
        （UDP 带 TCP Flags / Packets×65535 < Bytes / 端口 53 非 DNS 身份）
  B 轨：ConstrainedGenerator(LeJIT bundle).generate(10)
        降级 → forge/rulesets/network_cidds/sample_b.json（人工合规样本，
        来源见文件 meta.source_zh，待宿主机 LeJIT 实跑替换）
```

宿主机 z3 增强：`Projector.project_with_z3()` 对恒等式违规行用
`z3.Optimize` 求最近可行解（最小化改动量）；沙箱调用抛中文指引，
请用纯 Python `project()`（演示场景结果一致）。

## 5. demo 模式降级行为表（无 ollama / netnomos / lejit / fastapi 时）

| 环节 | 宿主机完整模式 | 沙箱/缺依赖降级行为 |
|---|---|---|
| 财务 learn | NetNomos 真学（`use_netnomos=True`）+ 人工恒等式合并 | 人工通道加载 `manual_rules.json`（R01–R05）+ R06/R07 软规则，确定性 |
| 网络 learn | NetNomosMiner.fit（hitting-set） | 一级：加载 `../NetNomos/rules/golden_cidds/rules.json`（纯 JSON）；二级：内置 N01–N03 三条人工规则 |
| 规则卡 explain | engine 模板卡 + `RuleExplainer.for_scenario` 加载 Markdown/JSON RAG；`FORGE_RULECARD_LLM=1` 时用 Ollama `gemma3:27b` 通过 `/api/chat` 润色前 N 张卡；prompt 为英文控制、最终中文 | engine 模板卡 + RAG citation（核心 knowledge + 场景 knowledge），不调用 LLM；巧合过滤照常 |
| 财务 A 轨 | ollama qwen2.5（role=induce，固定 seed）写报告 | 确定性降级叙事：照抄错误数字（3,000、8,500…）+ 连带算错毛利率（96.43%），与真值表一致 |
| 财务 B 轨 | 同左（B 轨本就是确定性程序回填，不依赖 LLM） | 完整可用：validate → Projector → 槽位回填 → 终检零告警 |
| 网络 A 轨 | ollama 生成 10 条 NetFlow（预期犯错） | 确定性带错样本（3 类错误各 ≥1 条） |
| 网络 B 轨 | LeJIT bundle 约束解码生成 | 读预置合规样本 sample_b.json（干预日志注明降级与替换路径） |
| 数值投影 | 可选 `project_with_z3()`（最近可行解） | 纯 Python `project()`（确定性恒等式求解） |
| chat 受约束 | ollama/codex 起草 + 槽位白名单校验 | mock 起草（确定性模板）+ 同一套白名单校验 |
| HTTP 服务 | uvicorn + FastAPI + SSE | `import server.app` 安全；`create_app()` 抛中文指引；pipeline/store 可直接单测 |

### 5.1 RAG / LLM 环境变量

| 变量 | 默认 | 说明 |
|---|---:|---|
| `FORGE_RULECARD_LLM` | 空 | 设为 `1/true/yes/on` 才对规则卡调用 LLM；否则只补 citation |
| `FORGE_RULECARD_LLM_MAX_CARDS` | `2` | 每个 pipeline 最多润色多少张规则卡 |
| `FORGE_RAG_KNOWLEDGE_DIRS` | 空 | 追加本地知识库目录；Windows 用 `;` 分隔 |
| `FORGE_RAG_TOP_K` | `3` | 每条规则最多取多少个知识片段 |
| `FORGE_RAG_MAX_SECTION_CHARS` | `1200` | 单个知识片段最大正文字符数 |
| `FORGE_RAG_MAX_CONTEXT_CHARS` | `3600` | 进入 prompt 的知识区最大字符数 |
| `FORGE_OLLAMA_EXPLAIN_MODEL` | `gemma3:27b` | explain 角色默认 Ollama 模型；实测英文控制→中文输出优于当前 qwen3 tags |
| `FORGE_OLLAMA_DRAFT_MODEL` | `qwen2.5:14b-instruct` | draft 角色默认 Ollama 模型 |
| `FORGE_OLLAMA_HOST` / `OLLAMA_HOST` | `http://localhost:11434` | Ollama HTTP 地址 |
| `FORGE_OLLAMA_TIMEOUT` | `120` | 生成请求超时秒数 |
| `FORGE_OLLAMA_PROBE_TIMEOUT` | `2` | 探测 `/api/tags` 超时秒数 |

## 6. 测试

```bash
python -m unittest discover tests -v
```

W4 RAG/LLM/pipeline 快速验证：

```bash
PYTHONUTF8=1 python -m unittest tests.test_explainer tests.test_llm tests.test_pipeline -v
# 当前通过：30 tests, OK
```

二波新增：

- `tests/test_projector.py`：各恒等式修正单测（R01 级联、R02 重算、R03/R04
  跨期、R06/R07 不改数）、z3 接口缺失指引；
- `tests/test_reporter.py`：A 轨含错误值 "3,000"、diff_html 含 `class="err"`
  与 "应为 2,000"、B 轨 cogs 修正值=2000、干预日志非空、终检零告警、
  网络双轨 A≥3 类错误 / B 0 违规；
- `tests/test_pipeline.py`：事件 stage 顺序与 STAGE_AGENT 映射、首尾
  control running/done、端到端产物断言、server.app 沙箱 import 安全、
  JobStore 回放/哨兵语义。
- `tests/test_explainer.py`：Markdown/JSON 知识库加载、多目录、finance/network
  场景检索、prompt 预算、LLM 卡片数量上限。

## 7. 已知限制 / 遗留

- 任务与产物全内存（重启即失；`--reload` 双进程各持一份 store），演示够用；
- `/api/data-sources` 只登记元信息，不接收 multipart 文件（避免引入
  python-multipart 依赖；演示数据由管线确定性构造）；
- 网络管线的真实 learn / LeJIT 生成需宿主机执行
  `run_network_learn.ps1` / `train_network_lejit.ps1` 后替换降级产物；
- chat 校验只对"数值白名单"做核查，未做语义级规则蕴含（可接 engine.check 的
  Z3 entails，留待三波）。
