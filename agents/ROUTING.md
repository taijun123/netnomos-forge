# 多 Agent 开发编制与模型路由（Orchestrator 执行）

| Agent | 模型 | 负责目录（互斥所有权） | 产出 |
|---|---|---|---|
| Orchestrator/Architect | fable | forge/contracts.py、agents/、docs/ | 契约冻结、任务排程、模型路由、验收合并 |
| Core-Dev | fable | forge/core/{engine,llm,generator}.py、forge/scenarios/network_cidds/、scripts/host/network* | SDK 核心 + 网络场景 |
| Finance-Dev | fable | forge/scenarios/finance_v1/、forge/core/injector.py | 数据生成器 + 错误注入 + 纯 Python 校验器 |
| Server-Dev（二波） | fable | server/、forge/core/{reporter,projector,explainer}.py | FastAPI+SSE、双轨报告 |
| Web-Dev | opus | web/ | 介绍页 + 双 demo |
| Reviewer | fable | 只读全仓 | 审查报告 + 验收 |

路由规则：
- 接口契约 / 数值正确性 / Z3 逻辑 / 核心业务代码 / 审查 → **fable**
- UI / 视觉 / 交互 → **opus**
- 机械性搬运、抽样、批量转换 → **sonnet/haiku**
- 运行时推理（诱骗 A 轨、起草、规则解释）→ **ollama qwen2.5 / codex**（宿主机，见 contracts.DEFAULT_LLM_ROUTING）

约束（所有 Agent 必须遵守）：
1. forge/contracts.py 只读；变更需 Orchestrator 批准。
2. 只在自己的所有权目录内写文件。
3. 沙箱无 pip/npm 外网：第三方重依赖一律懒加载；测试用 unittest 并对缺失依赖跳过。
4. 不执行 git commit（由 Orchestrator 统一处理）。
