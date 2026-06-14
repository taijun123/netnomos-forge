# 办公室趣味 Demo 与财务/网络 Demo 后端接入技术报告

> 当前状态：已完成主集成。本文基于当前 `netnomos-forge` README、`docs/W4_DEMO_SCENARIOS.md`、`docs/SERVER.md`、当前 `server/app.py`，以及外部 `product/HANDOFF.md`、`product/docs/backend-integration.md` 编写。  
> 重要边界：办公室 UI 已迁入 `web/src/office/**` 并接入 `office_demo` 后端；抓包工作台仍由浏览器端解析 pcap/csv，RAG 文档上传当前用于前端配置和受控聊天请求上下文，尚未持久化入库。

## 1. 目标与范围

本轮交付面向三个演示面：

1. **办公室趣味 demo**：一个 3D 多智能体办公室前端，用 6 个角色表达规则接入、数据接入、规则学习、规则核查、报告生成和受控问答等流程。
2. **财务 demo**：基于 `finance_v1` 的华信咨询资料包审阅，展示财务规则核查、数值投影修正和 A/B 双轨报告差异。
3. **网络 demo**：基于 `network_cidds` 的 CIDDS NetFlow 规则核查，展示 NetNomos 归档规则、违规 NetFlow 与约束后合规输出对比。

本文覆盖当前办公室 demo 与财务/网络 demo 的主集成状态，相关交付文档包括：

- `docs/OFFICE_DEMO_TECHNICAL_REPORT.md`
- `docs/OFFICE_DEMO_USE_CASES.md`
- `docs/OFFICE_DEMO_OPERATION_GUIDE.md`

本轮代码交付同时包含后端 `office_demo` 场景、前端 `#/office` 页面接入、测试覆盖与三份演示文档。

## 2. 总体技术架构

### 2.1 分层视图

```text
办公室趣味前端 product/
  3D 办公室 / 角色状态 / 规则集面板 / 数据面板 / 产出物面板 / 手机聊天 / 抓包工作台
        │
        │ 已接入：HTTP + SSE
        ▼
netnomos-forge FastAPI 后端
  /api/data-sources
  /api/rulesets/upload
  /api/rulesets/learn
  /api/rulesets/{ruleset_id}/cards
  /api/reports/generate
  /api/workflow/events/stream
  /api/jobs/{job_id}
  /api/chat/constrained
        │
        ▼
Forge 核心管线
  NetNomos 规则发现 / 规则加载
  RuleExplainer + RAG 规则解释
  Validator 规则核查
  Projector 数值修正
  LeJIT/约束生成或稳定降级样本
  Reporter A/B 双轨报告
```

### 2.2 角色到后端职责映射

办公室 UI 的 6 个角色可作为真实工作流的可视化投影：

| 办公室角色 | UI 语义 | 后端阶段/接口映射 | 当前状态 |
|---|---|---|---|
| 主管 A / `supervisor` | 流程编排、任务监管 | `control` 阶段；`/api/rulesets/learn`、`/api/jobs/{job_id}` | 后端已有 job 与状态；办公室已接入 |
| 快递 B / `courier` | 数据接入、文件配送、抓包入口 | `/api/data-sources`；`upload` / `prepare` 阶段 | 后端已有上传/登记；办公室已接入 |
| 员工 C / `analyst` | 规则学习、数据分析 | `learn` 阶段；规则学习结果进入规则集 | 财务/网络管线已有；办公室已接入 |
| 员工 D / `validator` | 规则解释、规则核查 | `explain` / `validate` 阶段；规则卡与违规清单 | 财务/网络管线已有；办公室已接入 |
| 员工 E / `plugin` | 投影修正、报告生成、打包产出 | `project` / `report` / `diff` 阶段；双轨报告 | 财务/网络管线已有；办公室已接入 |
| 产品经理 F / `pm` | 受控模型沟通、RAG/Prompt 配置 | `/api/chat/constrained` | 后端已有数值白名单校验；办公室聊天接入待确认 |

后端 `WorkflowEvent.agent` 当前使用 `"A"` 到 `"F"` 编码，已经可以映射到办公室角色。办公室前端的 `agentId` 使用 `supervisor/courier/analyst/validator/plugin/pm`，主集成时需要增加一层编码映射。

## 3. 已有后端能力

当前 `netnomos-forge` 后端以 FastAPI 提供编排服务：

- 后台 job：`/api/rulesets/learn` 创建后台任务，`/api/jobs/{job_id}` 查询状态和结果。
- SSE 事件：`/api/workflow/events/stream` 支持 `job_id` 续接，也支持 `sequence` 触发对应场景管线。
- 数据源：`/api/data-sources` 支持 JSON 元信息登记，也支持 `multipart/form-data` 上传文件并保存到 `demo_artifacts/uploads/<scenario>/`。
- 规则集：`/api/rulesets/upload` 可加载默认规则或指定服务器本地规则路径。
- 规则卡：`/api/rulesets/{ruleset_id}/cards` 返回中文规则解释、标签、引用和疑似巧合标记。
- 双轨报告：`/api/reports/generate` 同步生成 `DualReport`，包含 A 轨、B 轨和 `diff_html`。
- 受控聊天：`/api/chat/constrained` 起草回复后用最近一次 B 轨报告槽位白名单校验数值。

### 3.1 关键数据契约

| 契约 | 说明 | 办公室接入用途 |
|---|---|---|
| `WorkflowEvent` | `id/time/agent/stage/status/description` | 右侧任务日志、流程队列、角色状态、角色动画触发 |
| `RuleSet` / `Rule` | 规则集、规则 id、文本、来源、启用状态 | 规则集面板展示和开关状态 |
| `RuleCard` | 规则解释、标签、citation、疑似巧合 | 规则卡弹窗或产出物预览 |
| `ViolationReport` / `Violation` | 违规行、命中规则、期望值、中文说明 | 规则核查结果与风险提示 |
| `DualReport` | A/B 双轨报告、槽位、干预日志、对比 HTML | 产出物面板、报告预览、下载入口 |
| `PacketRecord` | 办公室抓包工作台的标准包记录 | 当前外部前端可浏览器端解析；后端集中解析接口待定 |

## 4. 后端接口映射

### 4.1 已存在并可用于财务/网络演示的接口

| 场景 | 前端动作 | 后端接口 | 入参要点 | 出参要点 | 状态 |
|---|---|---|---|---|---|
| 财务/网络 | 上传待核查资料 | `POST /api/data-sources` | `multipart/form-data`: `scenario`, `note`, `file` | `dataSourceId`, `filename`, `path`, `size` | 已实现 |
| 财务/网络 | 登记数据源元信息 | `POST /api/data-sources` | JSON: `scenario`, `filename`, `note` | `dataSourceId`, `filename` | 已实现 |
| 财务/网络 | 加载默认规则集 | `POST /api/rulesets/upload` | JSON: `scenario`, 可选 `rules_path` | `rulesetId`, `ruleCount` | 已实现 |
| 财务/网络 | 启动学习/核查/报告工作流 | `POST /api/rulesets/learn` | `scenario`, `sequence`, 可选 `dataSourceId`, `validationDataSourceId`, `question`, `reportPrompt` | `jobId`, `status`, `request` | 已实现 |
| 财务/网络 | 订阅工作流事件 | `GET /api/workflow/events/stream?job_id=...` | `job_id` 或 `sequence` | SSE `workflow` 事件 | 已实现 |
| 财务/网络 | 拉取 job 结果 | `GET /api/jobs/{job_id}` | `job_id` | `status`, `events`, `result`, `error` | 已实现 |
| 财务/网络 | 获取规则卡 | `GET /api/rulesets/{ruleset_id}/cards` | `ruleset_id` | `cards[]` | 已实现 |
| 财务/网络 | 生成双轨报告 | `POST /api/reports/generate` | `scenario` | `jobId`, `report` | 已实现 |
| 财务/网络/办公室 | 受控聊天 | `POST /api/chat/constrained` | `message`, 可选 `scenario` | `reply`, `flagged_numbers`, `checks`, `backend` | 已实现；办公室 UI 已接入 |
| 通用 | 健康检查 | `GET /api/health` | 无 | `status`, `jobs` | 已实现 |

### 4.2 办公室前端建议接入点

| 办公室模块 | 当前实现 | 接入方式 | 后续边界 |
|---|---|---|---|
| 右侧任务日志 / 流程队列 | 当前由前端 state/mock 驱动 | 消费 `WorkflowEvent` SSE；按 `stage` 和 `agent` 更新角色状态 | 事件到 `AgentStatus` 的精确状态枚举需主集成确认 |
| 规则集面板 | 当前有规则组、启停、新增规则组 | 先读取 `/api/rulesets/upload` 与 `/api/rulesets/{id}/cards` 的结果，后续再做真实写入 | 后端当前没有通用规则启停/新建规则组持久接口 |
| 数据面板 | 当前支持 pcap/csv/xlsx/pdf 类型概念 | 上传走 `/api/data-sources`；pcap/csv 包记录可继续浏览器端解析 | 是否新增 `/api/capture/packets` 集中解析接口待确认 |
| 产出物面板 | 接收后端 job result，并保留前端追加产物 | 从 `/api/jobs/{job_id}.result` 中抽取规则卡、违规清单、双轨报告 | 产出物持久化接口待确认 |
| 手机聊天 | 调用真实受控聊天接口 | 调 `/api/chat/constrained`，展示 `reply`、`checks`、`flagged_numbers` | 对话 id、rulesetId、RAG 配置入库接口待确认 |
| 抓包工作台 | 前端已能解析 pcap/pcapng/csv | 短期维持前端解析；只把数据源上传给后端 | 后端集中解析和实时流不是当前已完成能力 |

## 5. 三场景关系

### 5.1 办公室是统一演示壳

办公室趣味 demo 的价值不是替代财务/网络 demo，而是把后端工作流拟人化、可视化：

- 用户把规则集交给主管 A。
- 快递 B 接收数据源并把任务送入分析流程。
- 员工 C 学习或加载规则。
- 员工 D 解释规则并验证新资料。
- 员工 E 做投影修正、约束生成和报告产出。
- 产品经理 F 用受控聊天解释规则、报告和数据边界。

### 5.2 财务是“数值治理”演示

财务 demo 聚焦结构化财务资料中的硬约束和风险提示：

- 典型规则：进销存勾稽、资产负债配平、现金跨期滚动、行业画像、比率背离。
- A 轨风险：裸模型照抄错误数据，把错误数值写入结论。
- B 轨控制：规则核查命中违规，Projector 修正硬勾稽错误，报告正文通过槽位回填，终检用数值白名单兜底。

### 5.3 网络是“协议/物理约束”演示

网络 demo 聚焦 NetFlow 记录的协议一致性和物理上下界：

- 典型规则：UDP 不应携带 TCP Flags、`Bytes <= 65535 * Packets`、`Bytes >= 42 * Packets`、DNS 端口身份一致。
- A 轨风险：裸模型生成看似合理但违反协议/物理规则的 NetFlow。
- B 轨控制：优先使用 LeJIT/约束路径；不可用时回退到归档合规样本，演示稳定性优先。

### 5.4 推荐讲述顺序

1. 先用办公室展示“多智能体工作流”的趣味入口，让观众理解 A-F 的职责。
2. 再切到财务 demo，展示规则如何阻止模型照抄错误数字。
3. 再切到网络 demo，展示规则如何阻止模型生成违反协议常识的记录。
4. 最后回到办公室，说明同一套 workflow、job result、报告产物和受控聊天已经接入 3D UI，用办公室统一承接财务与网络两条稳定 demo。

## 6. 已知边界

1. 办公室前端已迁入当前 `web` 应用，`#/office` 会触发 `office_demo` workflow 并消费 SSE/job result。
2. `/api/data-sources` 当前可以保存上传文件，但财务/网络管线仍主要使用稳定场景管线，不承诺逐行解析任意上传 CSV/PDF/PCAP。
3. 网络 B 轨在 LeJIT bundle 不可用时会使用归档合规样本，演示稳定但不是实时训练产物。
4. job store 和产物存储为内存实现，后端重启后任务历史会丢失；`--reload` 场景也可能出现进程内 store 不一致。
5. `/api/chat/constrained` 当前主要做数值白名单校验，不等价于完整语义级规则蕴含验证。
6. 办公室抓包工作台当前外部前端已支持浏览器端 pcap/pcapng/csv 解析；后端集中包记录查询接口仍是建议项，不属于当前已确认实现。

## 7. 已完成接入与后续优化清单

- 办公室前端是否迁入 `netnomos-forge/web`，还是保留外部 `product/` 独立运行。
- `WorkflowEvent.agent` 的 `"A"`-`"F"` 与办公室 `agentId` 的最终映射位置。
- 规则集启停、新建规则组、RAG 文档入库、产出物持久化是否需要新增后端接口。
- 抓包工作台是否继续使用浏览器端解析，还是新增 `/api/capture/packets` 由后端集中解析。
- 办公室手机聊天是否扩展请求体，携带 `conversationId`、`rulesetId`、RAG 配置或用户会话上下文。
