# AI Worksite Handoff

<!-- 中文交接快照；保留标准小节名，便于 Codex / Claude / 其他模型接手。 -->

- Updated: 2026-07-06 18:50 +0800
- Repo: E:\yanchh\model_control\netnomos-forge
- Branch: pages-static-demo
- Last Commit: e1e948a Update required copyright notice

## Objective

修复网络 demo B 轨表格 `SrcIpAddr` / `SrcPt` / `DstIpAddr` / `DstPt` 为空的问题（方案 A：派生字段回填展示字段 + 加强终检）。**已完成实现与验证。**

## Current Status

当前工作区位于 `E:\yanchh\model_control\netnomos-forge`，分支 `pages-static-demo`，提交 `e1e948a`。

B 轨空字段问题已通过方案 A 修复：在 `forge/core/reporter.py` 新增 `_enrich_netflow_display_fields()` 后处理器，依据 `dataset_spec.json` preprocessing map_rules 的逆映射把 LeJIT 派生字段（`SrcSubnet`/`DstSubnet`/`SrcPortClass`/`DstPortClass`）回填为展示字段（`SrcIpAddr`/`SrcPt`/`DstIpAddr`/`DstPt`），保留派生字段用于审计；端口类 53 时强制对应 IP 为 "DNS" 以保证 N03 身份一致。同时在 `check_netflow_rows()` 增加 N04 检查，缺失必填展示字段即判违规。回填在 `collect_candidates()` 中、终检过滤前执行，确保终检 N04 正确验证已回填行。

验证已通过：22/22 单测通过（含 7 个新增）；`quick_validate.py` 财务 PASS、网络 PASS（922 条规则）；B 轨探针确认 3 行展示字段均非空、0 违规。`forge/contracts.py` 未修改。

## Changed Files

```text
M AI_WORKSITE_HANDOFF.md
M forge/core/reporter.py
M skills/worksite-handoff/SKILL.md
M skills/worksite-handoff/references/schema.md
M skills/worksite-handoff/scripts/update_handoff.py
M tests/test_reporter.py
?? show/
```

本次方案 A 修改的运行代码与测试：

- `forge/core/reporter.py`：新增 `_SUBNET_IP_PREFIX`/`_PORTCLASS_TO_PORT` 常量、`_subnet_to_ip()`、`_enrich_netflow_display_fields()`；`check_netflow_rows()` 增加 N04 缺失展示字段检查；`NET_RULE_TEXTS` 增加 N04 文案；`track_b_network()` 内 `collect_candidates()` 在终检前回填派生字段。
- `tests/test_reporter.py`：新增 `TestNetFlowDisplayEnrichment` 共 7 个测试（回填、端口类映射、端口 53 身份一致性、不覆盖已有字段、N04 触发、N04 不误报、track_b_network 字段非空）。

注意：`skills/worksite-handoff/*` 和 `show/` 在本次中文交接前已经是 dirty / untracked 状态，不要为了整理交接而回滚它们。

## Validation

- `git rev-parse --show-toplevel` => `E:/yanchh/model_control/netnomos-forge`
- `git rev-parse --abbrev-ref HEAD` => `pages-static-demo`
- `git show-ref --heads pages-static-demo` => `e1e948a... refs/heads/pages-static-demo`
- `Get-NetTCPConnection -LocalPort 8000,5173` => 后端 8000 监听，前端 5173 监听
- `Invoke-RestMethod http://127.0.0.1:8000/api/health` => `{"status":"ok","jobs":24}`
- `Invoke-WebRequest http://127.0.0.1:5173/` => HTTP 200
- `uv run python -c "from forge.core.generator import ConstrainedGenerator; rows=ConstrainedGenerator.from_bundle('network_cidds').generate(2); print([list(r.keys()) for r in rows])"` => 仅返回 `Duration, Proto, SrcSubnet, DstSubnet, SrcPortClass, DstPortClass, Packets, Bytes, Flags, Tos`
- `uv run python -c "from forge.core.reporter import check_netflow_rows; ..."` => 对缺失展示字段的 LeJIT 生成行仍返回 `[]`，说明当前终检没有把必填展示字段缺失当作违规
- **方案 A 修复后验证（2026-07-06 18:50）**：
  - `pytest tests/test_reporter.py -v` => 22 passed（含 7 个新增 `TestNetFlowDisplayEnrichment`）
  - `python scripts/quick_validate.py` => 财务 PASS、网络 PASS（规则集 922 条、SSE 事件 16 个）
  - B 轨探针 `DualReporter().track_b_network(3)` => 3 行，每行 `SrcIpAddr/SrcPt/DstIpAddr/DstPt` 均非空，`violations == []`

## Services

- 后端 FastAPI: `http://127.0.0.1:8000`
- 后端健康检查: `http://127.0.0.1:8000/api/health`
- 后端 OpenAPI 文档: `http://127.0.0.1:8000/docs`
- 前端 Vite: `http://127.0.0.1:5173/`
- 网络 demo: `http://127.0.0.1:5173/?v=w4source#/network`
- 财务 demo: `http://127.0.0.1:5173/?v=w4source#/finance`
- 办公 demo: `http://127.0.0.1:5173/?v=office#/office`

## Decisions And Boundaries

- **已采纳方案 A 并实施**：在 B 轨返回前，把 `SrcSubnet/DstSubnet/SrcPortClass/DstPortClass` 映射回可展示的 `SrcIpAddr/DstIpAddr/SrcPt/DstPt`，保留派生字段用于审计。回填在 `collect_candidates()` 中、终检过滤前执行。
- 端口-身份一致性：端口类 53 时对应 IP 强制为 "DNS"，保证 N03 不被回填破坏。
- 端口类 70000/71000/72000 选代表端口 22/8080/50000，仅影响展示可读性，不触发 N03。
- 不要修改 `forge/contracts.py`，旧交接中已将其列为冻结文件（本次未触碰）。
- 不回滚用户既有的 dirty 文件（`skills/worksite-handoff/*`、`show/`）。
- 方案 B（重训 LeJIT）未采纳：需改 schema + GPU 重训，成本高且非演示阻塞项。

## Blockers

- B 轨空字段问题已解决，无阻塞项。
- 待办（非阻塞）：宿主机有 4 个陈旧测试断言失败（见 CLAUDE_HANDOFF.md 第 12 节），不影响本次 B 轨修复，但全量 `pytest tests/` 仍会红。

## Next Steps

- 前端验证（需后端 8000 + 前端 5173 运行）：打开 `http://127.0.0.1:5173/?v=w4source#/network`，运行网络 demo，确认 B 轨表格 `SrcIpAddr/SrcPt/DstIpAddr/DstPt` 列与 diff HTML 正常显示。
- 可选：修复 4 个陈旧测试断言（`test_learn_validate_check` satisfaction 阈值、`test_explain_without_llm_uses_template` 机器解释路径、`test_z3_projection_matches_pure_python` COGS=3000、`test_track_b_zero_violations_with_fallback_note` 降级说明），使全量测试转绿。
- 可选：如需更真实的 IP 多样性，可在 `_subnet_to_ip()` 中按行号进一步分散 host 八位。

## Agent Notes

本地启动命令：

```powershell
cd E:\yanchh\model_control\netnomos-forge
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000
```

另开一个 PowerShell：

```powershell
cd E:\yanchh\model_control\netnomos-forge\web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

如果已有服务在跑，直接访问 `http://127.0.0.1:5173/?v=w4source#/network`。若端口被占用，先用 `Get-NetTCPConnection -LocalPort 8000,5173` 查 PID，再决定是否停掉旧进程。

根因证据位置：

- `forge/scenarios/network_cidds/dataset_spec.json`：`include_fields` 使用派生字段 `SrcSubnet/DstSubnet/SrcPortClass/DstPortClass`
- `forge/rulesets/network_cidds/lejit_bundle/manifest.json`：当前 bundle 的 `field_order` 不包含 `SrcIpAddr/SrcPt/DstIpAddr/DstPt`
- `forge/core/generator.py`：`ConstrainedGenerator.generate()` 直接 `frame.to_dict(orient="records")`
- `forge/core/reporter.py`：`track_b_network()` 原样把 generated rows 放进 `track_b.slots.rows`
- `web/src/pages/NetworkDemoPage.tsx`：`toNetFlowRows()` 读取 `SrcIpAddr/SrcPt/DstIpAddr/DstPt`

## Development History

- 2026-07-06 18:50 +0800 - Claude/TRAE - 实施方案 A 修复 B 轨空字段：`forge/core/reporter.py` 新增 `_enrich_netflow_display_fields()` 派生字段回填 + N04 终检，`collect_candidates()` 终检前回填；`tests/test_reporter.py` 新增 7 测试。验证：22/22 单测通过、quick_validate 财务+网络 PASS、B 轨探针 3 行字段非空 0 违规。
- 2026-07-06 17:30 +0800 - Codex/GPT-5 - 将交接文件改为中文，补充当前分支、真实前端目录、启动命令、服务验证结果和 B 轨字段问题的两条修复路径；只修改 `AI_WORKSITE_HANDOFF.md`。
- 2026-07-06 17:18 +0800 - Codex/GPT-5 - 确认网络 demo B 轨空字段根因，记录 LeJIT 派生字段 schema 与前端展示字段不一致；未改运行代码。

## Agent Roster

- Claude/TRAE - Responsibility: 实施方案 A 修复 B 轨 NetFlow 空字段（派生字段回填 + N04 终检）并验证；Work-site: `forge/core/reporter.py`、`tests/test_reporter.py`、`AI_WORKSITE_HANDOFF.md`；Current state: done；Boundaries: 不修改 `forge/contracts.py`，不回滚用户既有 dirty files。
- Codex/GPT-5 - Responsibility: 调查并交接 B 轨 NetFlow 字段 schema mismatch；Work-site: `AI_WORKSITE_HANDOFF.md`，只读检查 `forge/core/reporter.py`、`forge/core/generator.py`、`forge/scenarios/network_cidds/dataset_spec.json`、`forge/rulesets/network_cidds/lejit_bundle`、`web/src/pages/NetworkDemoPage.tsx`；Current state: done；Boundaries: 未实现运行时代码修复，不回滚用户已有 dirty files。
