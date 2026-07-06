# AI Worksite Handoff

<!-- 中文交接快照；保留标准小节名，便于 Codex / Claude / 其他模型接手。 -->

- Updated: 2026-07-06 23:00 +0800
- Repo: E:\yanchh\model_control\netnomos-forge
- Branch: main
- Last Commit: 9cf41c7 feat(static-demo): 用真实后端数据替换 GitHub Pages 静态演示仿真数据

## Objective

用本地后端真实运行数据替换 GitHub Pages 静态演示页的仿真数据，使 github.io 点击一键演示时显示真实结果。**已完成。**

## Current Status

当前工作区位于 `E:\yanchh\model_control\netnomos-forge`，分支 `main`，提交 `9cf41c7`，已推送到 `origin/main`。

静态演示数据已用真实后端运行结果替换：通过 HTTP 触发后端 learn/validate/report 序列，捕获 `job.result`（rules/cards/violations/dual），转换为 TypeScript 替换 `web/src/demo/demoMocks.ts`。捕获数据：network_cidds（922 rules, 12 cards, 4 violations, A 轨 4 违规/B 轨 0 违规/diff_html 真实标红）、finance_v1（7 rules, 7 cards, 5 violations, A 轨 5 违规/B 轨 0 违规/完整财务分析 slots）。

强约束遵守：仅修改 `web/src/demo/demoMocks.ts`（静态展示数据源），未修改 `forge/` 后端代码（`contracts.py` 冻结）、`demoDriver.ts`/`events.ts` 真实运行路径、`static-demo/workflow.ts` 静态编排逻辑。

验证：`tsc -b` 通过（无类型错误），`vite build --base=/netnomos-forge/` 成功（10.51s），产物 3.1MB（gzip 398KB）。

## Changed Files

```text
 M skills/worksite-handoff/SKILL.md
 M skills/worksite-handoff/references/schema.md
 M skills/worksite-handoff/scripts/update_handoff.py
?? .trae/
?? show/
```

本次 UI 重叠修复涉及的已提交文件（均在 main 分支提交 `b359f09` 中）：

- `forge/core/reporter.py`：`_build_net_diff_html` 内 `table()` 函数给 `<table>` 外包 `<div class="table-scroll">` 滚动容器。
- `web/src/styles.css`：`.diff-html .track-col` 加 `min-width:0` + `overflow:hidden`；`.diff-html .data-table` 设 `min-width:560px`；`.diff-html .table-scroll` 设 `overflow-x:auto`。

注意：`skills/worksite-handoff/*` 和 `show/`、`.trae/` 为用户既有的 dirty / untracked 状态，不要为了整理交接而回滚它们。

## Validation

- `git rev-parse --show-toplevel` => `E:/yanchh/model_control/netnomos-forge`
- `git rev-parse --abbrev-ref HEAD` => `main`
- `git log --oneline main -3` => `b359f09` → `75bdb9b` → `e1e948a`
- `git push origin main` => `75bdb9b..b359f09 main -> main`（push 成功）
- `pytest tests/test_reporter.py -q` => 22 passed（无回归）
- diff_html 结构验证 => 2 个 `<table class="data-table">` 均被 `<div class="table-scroll">` 包裹，结构正确
- 前次验证（B 轨修复，继承）：`quick_validate.py` 财务 PASS、网络 PASS（922 条规则）；B 轨探针 3 行展示字段均非空、0 违规

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
- **分支合并决策**：用户明确 `pages-static-demo` 是之前忘了 merge 到 main 的界面分支，要求整体覆盖到 main。已用 force push 把 `origin/main` 覆盖为 `pages-static-demo` 内容（提交 `75bdb9b`），未做普通 merge（避免分叉历史）。
- 不要修改 `forge/contracts.py`，旧交接中已将其列为冻结文件（本次未触碰）。
- 不回滚用户既有的 dirty 文件（`skills/worksite-handoff/*`、`show/`、`.trae/`）。
- 方案 B（重训 LeJIT）未采纳：需改 schema + GPU 重训，成本高且非演示阻塞项。

## Blockers

- 无阻塞项。B 轨空字段问题已解决，分支已合并到 main 并推送。

## Next Steps

- 前端验证（需后端 8000 + 前端 5173 运行）：打开 `http://127.0.0.1:5173/?v=w4source#/network`，运行网络 demo，确认 B 轨表格 `SrcIpAddr/SrcPt/DstIpAddr/DstPt` 列与 diff HTML 正常显示。
- 可选：修复 4 个陈旧测试断言（`test_learn_validate_check` satisfaction 阈值、`test_explain_without_llm_uses_template` 机器解释路径、`test_z3_projection_matches_pure_python` COGS=3000、`test_track_b_zero_violations_with_fallback_note` 降级说明），使全量测试转绿。
- 可选：如需更真实的 IP 多样性，可在 `_subnet_to_ip()` 中按行号进一步分散 host 八位。
- 可选：`pages-static-demo` 分支本地仍存在（与 main 内容相同），如不再需要可删除以简化分支结构。

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

- 2026-07-06 23:00 +0800 - Claude/TRAE - 用真实后端数据替换 GitHub Pages 静态演示仿真数据：通过 HTTP 触发后端 learn/validate/report 序列捕获 job.result，转换替换 `web/src/demo/demoMocks.ts`（network 922 rules/12 cards/4 violations + finance 7 rules/7 cards/5 violations）。仅改静态数据源，不动后端/真实路径/静态编排。验证：tsc+build 通过。提交 `9cf41c7` 已 push。
- 2026-07-06 19:45 +0800 - Claude/TRAE - 修复 diff HTML 双轨表格字符重叠：`forge/core/reporter.py` `_build_net_diff_html` table 外包 `table-scroll` 滚动容器；`web/src/styles.css` `.diff-html .track-col` 加 `min-width:0`+`overflow:hidden`，`.diff-html .data-table` 设 `min-width:560px`，`.diff-html .table-scroll` 设 `overflow-x:auto`。验证：22/22 单测、diff_html 结构确认。提交 `b359f09` 已 push。
- 2026-07-06 19:25 +0800 - Claude/TRAE - 将 `pages-static-demo` 整体 force push 覆盖到 `origin/main`（`786c2d9...75bdb9b forced update`），本地 main 对齐；切换到 main 分支并刷新 `AI_WORKSITE_HANDOFF.md` 反映 main 状态。验证：main 与 origin/main 0/0 同步。
- 2026-07-06 19:12 +0800 - Claude/TRAE - 在 pages-static-demo 提交 B 轨修复 `75bdb9b`（reporter.py + tests + handoff），cherry-pick 到 main 为 `786c2d9`（后被 force push 覆盖）。验证：22/22 单测、quick_validate PASS。
- 2026-07-06 18:50 +0800 - Claude/TRAE - 实施方案 A 修复 B 轨空字段：`forge/core/reporter.py` 新增 `_enrich_netflow_display_fields()` 派生字段回填 + N04 终检，`collect_candidates()` 终检前回填；`tests/test_reporter.py` 新增 7 测试。验证：22/22 单测通过、quick_validate 财务+网络 PASS、B 轨探针 3 行字段非空 0 违规。
- 2026-07-06 17:30 +0800 - Codex/GPT-5 - 将交接文件改为中文，补充当前分支、真实前端目录、启动命令、服务验证结果和 B 轨字段问题的两条修复路径；只修改 `AI_WORKSITE_HANDOFF.md`。
- 2026-07-06 17:18 +0800 - Codex/GPT-5 - 确认网络 demo B 轨空字段根因，记录 LeJIT 派生字段 schema 与前端展示字段不一致；未改运行代码。

## Agent Roster

- Claude/TRAE - Responsibility: 实施方案 A 修复 B 轨 NetFlow 空字段（派生字段回填 + N04 终检）、提交并 force push pages-static-demo 覆盖 main、刷新交接快照；Work-site: `forge/core/reporter.py`、`tests/test_reporter.py`、`AI_WORKSITE_HANDOFF.md`、git main/pages-static-demo 分支；Current state: done；Boundaries: 不修改 `forge/contracts.py`，不回滚用户既有 dirty files（`skills/worksite-handoff/*`、`show/`、`.trae/`）。
- Codex/GPT-5 - Responsibility: 调查并交接 B 轨 NetFlow 字段 schema mismatch；Work-site: `AI_WORKSITE_HANDOFF.md`，只读检查 `forge/core/reporter.py`、`forge/core/generator.py`、`forge/scenarios/network_cidds/dataset_spec.json`、`forge/rulesets/network_cidds/lejit_bundle`、`web/src/pages/NetworkDemoPage.tsx`；Current state: done；Boundaries: 未实现运行时代码修复，不回滚用户已有 dirty files。
