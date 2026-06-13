# Reviewer 审查报告

**日期**：2026-06-13 ｜ **审查人**：Reviewer Agent（fable）｜ **结论：通过，含 4 项待宿主机验证**

## 1. 测试结果

| 指标 | 结果 |
|---|---|
| 总测试数 | 88 |
| 通过 | 84 |
| 跳过（宿主机依赖） | 4（netnomos+z3、lejit+torch、tomllib、z3） |
| 失败 | **0** |

跳过项均正确使用 `unittest.skipUnless(find_spec(...))` 跳过，沙箱内不计为失败。

## 2. 端到端链路验证（沙箱 mock 路径）

### 财务全链路
`generate_training_data(seed=42)` → `inject_faults()` → `FinanceValidator.validate()` →
`Projector.project()` → `DualReporter.make_dual()`

| 检查点 | 结果 |
|---|---|
| 训练集 960 行、满足率 1.0 | ✓ |
| F1–F4（5 项）全部命中，零误报 | ✓ |
| Projector COGS 修正 3000→2000（由违规推导，非 hardcode） | ✓ |
| A 轨 markdown 含错误值"3,000" | ✓ |
| B 轨 intervention_log 8 条（R01/R04/R02/R06/R07 各覆盖） | ✓ |
| diff_html 含 `mark-bad` 标红 | ✓ |
| B 轨含修正值"2,000" | ✓ |

### 网络全链路
`run_network_pipeline()` → 111 条规则（manual/golden 降级加载）→ SSE 13 事件

| 检查点 | 结果 |
|---|---|
| STAGE_AGENT 映射全部对齐 contracts | ✓ |
| SSE 格式合法（event: workflow + JSON 含全部 6 字段） | ✓ |
| 事件序列：control→upload→prepare→learn→explain→report→diff | ✓ |
| 首事件 running、末事件 done | ✓ |
| B 轨样本 895 字符（无 torch 降级合规样本） | ✓ |

## 3. 合规性检查

| 检查 | 结果 | 说明 |
|---|---|---|
| contracts.py 版本号未被篡改 | ✓ | CONTRACTS_VERSION="1.0" |
| reporter/projector 无 hardcode 业务数值 | ✓（1 条例外可接受） | `SPEC_INV_BP_BAND.get(industry, (0, 10000))` 是行业带上界默认值（100%），非华信数值 |
| report_template.md 无裸数字 | ✓ | 全部 {{slot}} 槽位 |
| 无 API key/密码硬编码 | ✓ | |
| 所有 Agent 未越权写他人目录 | ✓ | 经文件树确认 |

## 4. 接口契约一致性

| 检查 | 结果 |
|---|---|
| WorkflowEvent.to_sse() 格式与前端 events.ts 期望一致 | ✓ |
| 前端 api.ts 声明 6 个核心类型（WorkflowEvent/Rule/RuleSet/Violation/ViolationReport/DualReport） | ✓ |
| mock SSE 字段完整（id/time/agent/stage/status/description） | ✓ |
| REST 路径常量与 contracts.API_* 对齐 | ✓（前端用 fetch 字符串，路径值一致） |
| 财务管线 SSE 18 事件 agent 映射全部符合 STAGE_AGENT | ✓ |

## 5. 降级行为表（沙箱/无 GPU 环境）

| 依赖 | 缺失时行为 |
|---|---|
| netnomos + z3 | ForgeRuleEngine 懒加载失败 → 抛中文 RuntimeError（含 uv sync 指引） |
| lejit + torch | ConstrainedGenerator 懒加载失败 → 同上 |
| ollama（localhost:11434） | RoutedLLM 自动降级 MockBackend，打 WARNING 日志 |
| codex CLI | RoutedLLM 自动降级 MockBackend |
| 规则文件缺失 | 网络 pipeline 降级加载 manual_rules.json（已预置） |
| GPU | LeJIT 训练移入 scripts/host/，沙箱不执行 |

## 6. 待宿主机验证清单（W3 必跑）

1. **NetNomos learn CIDDS**：`scripts/host/run_network_learn.ps1` → 验证 `golden_cidds` 规则与沙箱 111 条 manual 规则覆盖率对比
2. **LeJIT 网络 bundle 训练**：`scripts/host/train_network_lejit.ps1`（单卡 4090，cidds 10k，预估 <2h）→ 替换 `forge/rulesets/network_cidds/sample_b.json`
3. **财务 netn learn**：宿主机 `uv run netn learn --dataset finance_v1/dataset_spec.json --grammar finance_v1/grammar_spec.json` → 对比自动学习规则与 manual_rules.json R01–R05 的覆盖情况
4. **FastAPI 端到端 HTTP 测试**：`uv run uvicorn server.app:create_app --factory --port 8000` + `curl /api/workflow/events/stream`

## 7. 遗留风险汇总（各 Agent 上报 + Reviewer 确认）

| 风险 | 级别 | 对策 |
|---|---|---|
| NetNomos validate 仅返回聚合指标，逐行 Violation 由 engine 二次扫描（O(rules×rows)） | 中 | 10k 行可接受；大数据集加 limit= 参数 |
| LeJIT Python API（LeJITConfig/LeJITPipeline）稳定性未实测 | 中 | generator.py 已写子进程降级路径 |
| finance_v1/dataset_spec.json 的 `_ctx` 跨期窗口语法待 netn 实测微调 | 低 | README 已标注待调清单 |
| B 轨 reporter 的 `SPEC_INV_BP_BAND.get(industry, (0, 10000))` 上界含 10000（Bp 单位=100%） | 低 | 含义正确（防止越界），非业务数值 |
| Web vite build 需在宿主机验证（沙箱缺 win32 rollup 二进制） | 低 | tsc 类型检查已通过；宿主机 npm install && npm run dev 即可 |

## 8. 结论

沙箱可验证范围**全部通过**。代码规模 ~9560 行，88 测试 0 失败。核心链路（财务/网络双轨报告、SSE 事件流、contracts 一致性）均经实际运行验证。
**放行进入 W3：宿主机 GPU 环境测试 + Web 构建验证。**
