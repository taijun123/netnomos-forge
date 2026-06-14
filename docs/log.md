# NetNomos Forge 日志系统

本文件记录从 Jack 分支提取并移植的日志能力。当前 UI 分支没有合并 Jack 分支，只按需引入日志功能与说明。

## Jack 分支做了什么

- 新增后端统一日志模块：`forge/utils/logging_config.py`
- 在 `server/app.py` 的 `create_app()` 内初始化日志系统
- 新增前端日志库：`web/src/lib/logger.ts`
- 新增日志面板：`web/src/components/LogPanel.tsx`
- 新增日志演示页：`web/src/pages/LogDemoPage.tsx`
- 在 `web/src/lib/apiClient.ts` 和 `web/src/lib/events.ts` 中记录 API、SSE、工作流日志
- 新增环境变量示例：`.env.example`
- Jack 分支还改过 `pyproject.toml`、`uv.lock`、`web/package-lock.json`，但主要是依赖锁和 torch 约束调整；本次没有移植这些依赖改动，避免影响当前真实工作流分支。

## 后端配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | 文件日志级别 |
| `LOG_DIR` | `logs` | 日志目录 |
| `LOG_JSON` | `false` | 是否输出 JSON 日志 |
| `LOG_MAX_BYTES` | `10485760` | 单个日志文件最大字节数 |
| `LOG_BACKUP_COUNT` | `5` | 轮转保留文件数 |
| `LOG_CONSOLE_LEVEL` | 同 `LOG_LEVEL` | 控制台日志级别 |

启动后端后会生成 `logs/forge.log`，并使用 `RotatingFileHandler` 做按大小轮转。

## 前端配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |
| `VITE_ENABLE_FRONTEND_LOGS` | 开发环境自动开启 | 生产构建中如需面板日志可设为 `true` |

前端日志保存在内存中，刷新页面后清空，最多保留 500 条。

## 使用入口

- 页面入口：`#/log-demo`
- 顶部导航：`日志演示`
- 右下角：`显示日志` / `隐藏日志`

日志演示页包含：

- 基础前端日志
- 真实 `/api/health` 健康检查
- 工作流阶段日志
- SSE 事件日志
- 异常路径日志

## 当前移植边界

- 没有合并 Jack 分支
- 没有修改 `forge/contracts.py`
- 没有引入 Tailwind/MUI/Radix
- 没有移植 Jack 的 torch/lockfile 变更
- 当前网络/财务/工作台的一键演示仍沿用真实后端工作流，不回退到本地模拟结果
