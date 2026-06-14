# 办公室趣味 Demo 与财务/网络 Demo 操作指南

> 当前状态：已完成主集成。本文面向现场演示操作者。办公室前端已迁入当前 `web` 应用并接入 `office_demo` 后端；财务和网络流程以 `netnomos-forge` 当前后端与 W4 前端为准。

## 1. 演示前准备

### 1.1 仓库与目录

推荐工作区结构：

```text
E:\yanchh\model_control\
  NetNomos\
  LeJIT\
  netnomos-forge\
```

外部办公室前端目录：

```text
E:\yanchh\AI模型控制和可解释性\product\
```

注意：外部 `product/` 是本轮迁入来源；当前演示请使用 `netnomos-forge/web` 内的 `#/office` 页面，外部目录只作为历史源与参考。

### 1.2 后端启动

在 `netnomos-forge` 根目录执行：

```powershell
cd E:\yanchh\model_control\netnomos-forge
uv sync
uv run uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000
```

或使用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\host\run_server.ps1
```

健康检查：

```powershell
curl http://127.0.0.1:8000/api/health
```

预期返回类似：

```json
{"status":"ok","jobs":0}
```

### 1.3 W4 前端启动

在 `netnomos-forge\web` 下执行：

```powershell
cd E:\yanchh\model_control\netnomos-forge\web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

打开：

```text
http://127.0.0.1:5173/?v=w4source#/finance
http://127.0.0.1:5173/?v=w4source#/network
```

### 1.4 办公室前端入口

当前办公室 UI 已迁入 `netnomos-forge/web`，推荐直接打开：
```text
http://127.0.0.1:5173/?v=office#/office
```

如需对照历史来源，可在外部目录单独启动：

```powershell
cd "E:\yanchh\AI模型控制和可解释性\product"
npm install
npm run dev
```

外部交接文档说明该前端默认端口可能为 5173，被占用时会顺延。正式演示以当前仓库的 `#/office` 为准，可将其定位为“三场景统一体验壳和趣味工作流入口”。

## 2. 演示资料

### 2.1 财务资料

目录：

```text
demo_artifacts/w4_demo_assets/finance/
```

关键文件：

- `huaxin_audit_package.csv`：演示上传的待审资料包。
- `finance_training_clean_960_correct.csv`：干净训练参考。
- `finance_training_clean_960_correct_zh.csv`：中文表头训练参考。
- `huaxin_clean_reference.csv`：干净参考包。
- `truth_table.json`：注入错误真值表。
- `prompts.md`：推荐提问和讲述词。

### 2.2 网络资料

目录：

```text
demo_artifacts/w4_demo_assets/network/
```

关键文件：

- `netflow_rule_anomaly_upload.csv`：演示上传的待核查 NetFlow。
- `cidds_wk2_normal_10k_correct_training.csv`：CIDDS 训练参考。
- `network_generated_10_reference.csv`：生成样本参考。
- `network_b_track_reference_sample.json`：B 轨合规参考样本。
- `prompts.md`：推荐提问和讲述词。

## 3. 办公室趣味 Demo 操作

> 当前状态：办公室 UI 已接入 `office_demo` 后端；以下操作用于展示产品体验和后端联动。

1. 打开办公室前端页面。
2. 观察 3D 俯视办公室和 6 个角色。
3. 点击左侧名册或 3D 角色，展示成员设置。
4. 打开“规则集”面板，说明财务组、网络组、输出约束组如何对应后端规则。
5. 双击或点击快递 B/门外收发区，使用演示数据或选择本地文件，确认数据源注册到 `/api/data-sources`。
6. 打开“产出物”面板，说明规则卡、违规报告和双轨报告来自 office_demo job result。
7. 打开产品经理 F 的手机聊天，发送问题，确认 `/api/chat/constrained` 返回基于 `finance_v1 + network_cidds` 后端状态的回答。
8. 明确说明：当前办公室前端不是财务/网络稳定 demo 的唯一入口；财务/网络请切回 `netnomos-forge` W4 页面演示。

## 4. 财务 Demo 操作步骤

### 4.1 入口

打开：

```text
http://127.0.0.1:5173/?v=w4source#/finance
```

### 4.2 标准流程

1. 在“训练资料预览”查看 `finance_v1` 合成训练集样例。
2. 点击“开始规则学习”。
3. 等待工作流事件完成，确认规则卡或规则学习结果来自后端 live result。
4. 进入“资料上传”。
5. 选择并上传：

   ```text
   demo_artifacts/w4_demo_assets/finance/huaxin_audit_package.csv
   ```

6. 确认页面显示上传文件名和 `dataSourceId`。
7. 进入“规则核查”，点击“运行资料规则核查”。
8. 等待事件流完成。
9. 查看违规命中，重点确认：
   - `R01` 营业成本 3,000 应为 2,000；
   - `R02` 资产负债配平差异；
   - `R04` 现金跨期不一致；
   - `R06` 存货占比异常；
   - `R07` 应收增长和收入增长背离。
10. 进入“输入报告问题”，使用或复制以下问题：

    ```text
    请基于华信咨询待审资料包，生成一份年度财务分析与审阅报告，并指出营业成本、资产负债配平、现金跨期、存货占比和应收增长是否存在异常。
    ```

11. 进入“A/B 双轨”，点击“运行实时 A/B 双轨”。
12. 等待工作流完成。
13. 查看 A 轨标红报告、B 轨合规报告和干预日志。
14. 进入“报告预览/下载”，预览并下载 Markdown 报告。

### 4.3 讲述重点

- 上传文件本身会保存并传递 `dataSourceId`。
- 当前稳定输出仍复用财务场景管线，不承诺任意 CSV 都会逐行解析成同等质量结果。
- A 轨展示风险：模型可能照抄错误数字。
- B 轨展示控制：规则核查、投影修正、槽位回填和终检白名单。

## 5. 网络 Demo 操作步骤

### 5.1 入口

打开：

```text
http://127.0.0.1:5173/?v=w4source#/network
```

### 5.2 标准流程

1. 在“内置数据”确认 CIDDS 训练资料已作为规则学习资料加载。
2. 进入“规则学习”，等待后端加载归档 NetNomos 自发现规则。
3. 查看规则卡，确认规则来源和规则画像。
4. 进入“新资料核查”。
5. 选择并上传：

   ```text
   demo_artifacts/w4_demo_assets/network/netflow_rule_anomaly_upload.csv
   ```

6. 确认页面显示上传文件名和 `dataSourceId`。
7. 点击“运行新资料核查”。
8. 等待事件流完成。
9. 查看规则核查表，重点确认：
   - UDP 不应携带 TCP Flags；
   - `Bytes <= 65535 * Packets`；
   - `Bytes >= 42 * Packets`；
   - 端口 53/DNS 身份一致。
10. 进入“双轨对比”，使用或复制以下问题：

    ```text
    请基于我上传的待核查 NetFlow 资料，生成或抽取 10 条 CIDDS 风格记录，并说明哪些记录违反 UDP Flags、Packets/Bytes 物理上下界或 DNS 端口身份规则；同时给出规则约束后的合规版本。
    ```

11. 点击“运行实时 A/B 双轨”。
12. 等待工作流完成。
13. 查看 A 轨违规 NetFlow、B 轨 0 违规记录和干预日志。
14. 进入“报告预览/下载”，预览并下载 Markdown 报告。

### 5.3 讲述重点

- 网络规则来自归档的 NetNomos 自发现规则或稳定降级规则。
- A 轨展示结构化记录生成中的协议/物理错误。
- B 轨优先使用 LeJIT/约束生成；不可用时使用归档合规样本，干预日志应说明降级路径。

## 6. 后端接口快速检查

### 6.1 上传数据源

```powershell
curl -X POST http://127.0.0.1:8000/api/data-sources `
  -F "scenario=finance_v1" `
  -F "note=demo upload" `
  -F "file=@demo_artifacts/w4_demo_assets/finance/huaxin_audit_package.csv"
```

预期包含：

```json
{
  "dataSourceId": "...",
  "filename": "huaxin_audit_package.csv",
  "path": "...",
  "size": 123
}
```

### 6.2 启动工作流

```powershell
curl -X POST http://127.0.0.1:8000/api/rulesets/learn `
  -H "Content-Type: application/json" `
  -d "{\"scenario\":\"finance_v1\",\"sequence\":\"learn-finance\"}"
```

预期包含：

```json
{"jobId":"...","status":"running"}
```

### 6.3 查询 job

```powershell
curl http://127.0.0.1:8000/api/jobs/<jobId>
```

关注字段：

- `status`: `running` / `done` / `failed`
- `events`: 工作流事件
- `result.ruleset_id`: 规则集 id
- `result.cards`: 规则卡
- `result.violations`: 违规清单
- `result.dual`: 双轨报告

## 7. 已知边界

1. 办公室前端已接入真实后端 workflow；抓包解析和部分 RAG 文档管理仍保留前端侧能力。
2. W4 财务/网络 demo 以稳定场景资产为主，上传文件会保存并传递 id，但不承诺任意文件逐行解析。
3. 后端 job store 是内存实现，重启后历史任务和产物会丢失。
4. `uvicorn --reload` 可能产生多个进程，各自持有内存 store；正式演示建议不用 `--reload`。
5. Ollama 可选；不可用时系统按 `ollama -> codex -> mock` 或确定性降级路径保证演示稳定。
6. 网络真实 learn / LeJIT 生成依赖宿主机环境和 bundle；不可用时使用归档规则或合规样本。
7. `/api/chat/constrained` 当前主要校验回复中的数值是否命中最近一次 B 轨槽位白名单，不是完整语义级规则推理。

## 8. 故障排查

### 8.1 前端连不上后端

检查：

- 后端是否运行在 `http://127.0.0.1:8000`。
- 前端 `VITE_API_BASE` 是否为空或指向正确后端。
- 浏览器控制台是否有 CORS 错误。当前后端默认放开 `http://localhost:5173` 和 `http://127.0.0.1:5173`。

### 8.2 上传失败

检查：

- 请求是否为 `multipart/form-data`，字段名是否为 `file`。
- 文件是否为空。
- 后端进程是否有权限写入 `demo_artifacts/uploads/<scenario>/`。
- `scenario` 是否为 `finance_v1`、`network_cidds` 或 `network_pcap`。

### 8.3 SSE 没有事件

检查：

- 是否已经拿到 `jobId`。
- SSE URL 是否为 `/api/workflow/events/stream?job_id=<jobId>`。
- 如果用 `sequence` 触发，sequence 是否为 W4 前端支持的值，例如 `learn-finance`、`validate-finance`、`report-finance`、`learn-network`、`validate-network`、`report-network`。
- 后端日志是否出现管线异常。

### 8.4 job 一直 running

处理：

1. 查询 `/api/jobs/<jobId>` 看 `events` 是否还在增长。
2. 查看后端控制台日志。
3. 如果后端异常但 job 未更新，重启后端并重新演示；当前 store 不持久化。

### 8.5 规则卡或报告为空

检查：

- 工作流是否已完成。
- `/api/jobs/<jobId>` 的 `result.ruleset_id`、`result.cards`、`result.dual` 是否存在。
- 是否先上传了资料并把 `dataSourceId` 传入后续验证/报告流程。

### 8.6 办公室 UI 动画或截图异常

外部交接文档记录过两个常见点：

- Windows 或浏览器的 reduced motion 设置不能把动画幅度归零，否则角色会看起来静止。
- Three.js 清理时需要释放 renderer 和 WebGL context，否则 HMR/重挂可能导致画面变黑。

这些属于外部 `product/` 前端维护事项；当前 `netnomos-forge` 文档只记录排查方向。

## 9. 演示结束后检查

1. 关闭前端 dev server。
2. 关闭后端 uvicorn。
3. 如需保留上传文件，检查：

   ```text
   demo_artifacts/uploads/<scenario>/
   ```

4. 如需复盘，保存下载的 Markdown 报告和现场截图。
