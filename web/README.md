# NetNomos Forge · Web 产品展示页

React + Vite + TypeScript 单页应用，包含三个页面：

- **介绍页**：hero（“不改模型，只加规则”）、痛点叙事、三大价值卡、四层架构图、双 demo 入口。
- **网络 demo**：上传数据 → 规则学习（SSE 事件流）→ 规则卡墙 → 新数据违规清单 → 双轨 NetFlow 标红对比 → 审计报告。
- **财务 demo**：960 行合成数据预览 → 规则学习 → 上传「华信咨询」错误资料 → F1–F4 命中卡 → 双轨报告标红对比 → 报告下载。

3D 多 Agent 办公室作为第四入口（占位，第五周接入 marvis product，消费同一 SSE 流）。

## 宿主机启动方法

> 沙箱内 npm registry 被封锁，无法 `npm install`。请在**宿主机**（可联网）执行：

```powershell
cd netnomos-forge/web
npm install
npm run dev          # 默认 http://localhost:5174
```

或直接运行封装脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/host/web_dev.ps1
```

构建产物：

```powershell
npm run build        # tsc -b && vite build → dist/
npm run preview      # 预览构建结果
npm run typecheck    # 仅类型检查（tsc --noEmit）
```

依赖版本与 `mult-agent-marvis/product/package.json` 对齐（react 19 / vite 7 / typescript 5.9），
便于宿主机安装一致，也便于沙箱复用 product/node_modules 做类型检查。

## 目录结构

```text
web/
├── index.html
├── package.json            # 依赖版本对齐 marvis product
├── tsconfig.json
├── vite.config.ts          # /api 代理到 127.0.0.1:8000（后端就绪后生效）
└── src/
    ├── main.tsx            # 入口
    ├── App.tsx             # hash 路由（intro / network / finance / office）
    ├── styles.css          # 全部自定义样式（深色科技感 + 毛玻璃，无外部字体）
    ├── types/
    │   └── api.ts          # 与 forge/contracts.py 一一对应的类型（含来源注释）
    ├── lib/
    │   └── events.ts       # SSE 客户端：真实 EventSource 优先，失败 fallback 到 mock
    ├── mock/
    │   ├── sse.ts          # mock SSE：setInterval 按 WorkflowEvent 推送事件序列
    │   ├── network.ts      # 网络 demo mock：规则卡 / 违规 / 双轨 NetFlow
    │   └── finance.ts      # 财务 demo mock：合成数据 / 规则卡 / F1–F4 / 双轨报告
    ├── components/
    │   ├── TopNav.tsx
    │   ├── StepRail.tsx            # 左侧步骤流
    │   ├── WorkflowLog.tsx         # 进度条 + 事件日志流
    │   ├── RuleCardWall.tsx        # 规则卡墙（公式 / 解释 / 置信度 / 开关）
    │   └── ArchitectureDiagram.tsx # CSS/SVG 四层架构图
    └── pages/
        ├── IntroPage.tsx
        ├── NetworkDemoPage.tsx
        └── FinanceDemoPage.tsx
```

## 与后端契约对齐

所有前端类型（`src/types/api.ts`）逐字段对应 `netnomos-forge/forge/contracts.py`：
`WorkflowEvent` / `Rule` / `RuleSet` / `Violation` / `ViolationReport` / `RuleCard` /
`TrackReport` / `DualReport`、`STAGE_AGENT` 映射、`API_*` 路径常量。

SSE 接入：`src/lib/events.ts` 优先连真实 `GET /api/workflow/events/stream`，
后端未就绪（连接失败 / 握手超时）时自动降级到 `src/mock/sse.ts`，纯前端可独立演示。
后端就绪后无需改前端组件，只需后端按 `WorkflowEvent.to_sse()` 推流即可。
