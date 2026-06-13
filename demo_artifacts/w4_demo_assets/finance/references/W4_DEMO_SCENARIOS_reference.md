# W4 Demo Scenarios

本文档定义两个 W4 稳定演示场景。演示目标是让用户按真实产品流程完成：预览或确认训练资料、学习规则、手工上传待核查资料、查看规则核查、输入报告问题、运行实时 A/B 双轨、预览并下载报告。

## 演示资产目录

- 财务 demo：`demo_artifacts/w4_demo_assets/finance/`
- 网络 demo：`demo_artifacts/w4_demo_assets/network/`

两个目录都包含可上传样本、`README.md`、`prompts.md` 和相关参考资料。演示时优先从这两个目录选择上传文件和复制报告问题。

## 财务 Demo：华信咨询资料包审阅

### 稳定触发场景

- 训练资料：页面“训练资料预览”展示 `finance_v1` 合成财务训练集，完整训练集为 960 行，天然满足进销存、资产负债配平、现金跨期和比率画像规则。
- 待核查资料：演示时手工选择 `demo_artifacts/w4_demo_assets/finance/huaxin_audit_package.csv` 上传。
- 真值表：`demo_artifacts/w4_demo_assets/finance/truth_table.json`。
- 相关文案：`demo_artifacts/w4_demo_assets/finance/prompts.md`。
- 生成方式：原始资料由 `forge.scenarios.finance_v1.faults.save_package("demo_artifacts/finance")` 生成，本轮已复制到 W4 专用资产目录。
- 触发条件：必须先完成资料上传，页面拿到 `filename` 和 `dataSourceId` 后，才展示规则核查结果、A/B 双轨和报告预览。

### 用户输入问题

在“输入报告问题”步骤使用以下问题，或保持页面预填内容：

```text
请基于华信咨询待审资料包，生成一份年度财务分析与审阅报告，并指出营业成本、资产负债配平、现金跨期、存货占比和应收增长是否存在异常。
```

问题应明确三件事：要基于上传资料、要生成年度财务分析与审阅报告、要核查营业成本/配平/现金/存货/应收等异常。

### 预期规则

- `R01` 进销存勾稽：第 3 期营业成本写为 3,000，按期初存货 10,000 + 采购 4,000 - 期末存货 12,000 应为 2,000。
- `R02` 资产负债配平：第 5 期资产总计比负债加权益多 500。
- `R04` 现金跨期滚动：第 1 期期末现金 8,000，第 2 期期初现金写为 8,500。
- `R06` 行业画像：咨询公司第 8 期期末存货占资产 35%，明显偏离咨询业低存货常态。
- `R07` 比率背离：第 7 期应收账款同比 +300%，收入只增长约 15%。

### A/B 双轨预期

- A 轨：裸模型直接按上传资料写报告，可能照抄营业成本 3,000、错误资产总计、异常存货和应收数据，并把问题数字写进分析结论。
- B 轨：先由规则核查命中违规，再由 Projector 修正硬勾稽错误；报告正文用槽位回填，营业成本修正为 2,000，终检确保关键数值来自合规白名单。

### 操作步骤

1. 打开前端 `http://127.0.0.1:5173/#/finance`。
2. 在“训练资料预览”查看合成训练集样例，点击“开始规则学习”。
3. 等“规则学习”事件流完成，确认规则卡来自后端 live result。
4. 进入“资料上传”，点击“选择并上传资料”，手工选择 `demo_artifacts/w4_demo_assets/finance/huaxin_audit_package.csv`。
5. 确认页面显示上传文件名和 `dataSourceId`，再点击“进入规则核查”。
6. 在“规则核查”点击“运行资料规则核查”，等待事件流完成。
7. 查看违规命中，确认说明里显示上传资料名和 `dataSourceId`。
8. 点击“输入报告问题”，确认或编辑建议问题。
9. 进入“A/B 双轨”，确认稳定触发场景说明里显示上传资料名和 `dataSourceId`，再点击“运行实时 A/B 双轨”。
10. 等实时工作流完成后，查看 A 轨标红报告、B 轨合规报告和干预日志。
11. 进入“报告预览/下载”，预览报告并点击“下载报告 Markdown”。

## 网络 Demo：CIDDS NetFlow 上传资料核查与双轨对比

### 稳定触发场景

- 内置训练资料：`E:\yanchh\model_control\NetNomos\data\cidds_wk2_normal_10k.csv`，用于“规则学习”步骤，不需要用户上传。
- 归档规则库：`forge/rulesets/network_cidds/golden/rules.json`，稳定加载 NetNomos 自发现规则。
- 待核查资料：演示时手工选择 `demo_artifacts/w4_demo_assets/network/netflow_rule_anomaly_upload.csv` 上传。
- B 轨兜底样本：`demo_artifacts/w4_demo_assets/network/network_b_track_reference_sample.json`（从 `forge/rulesets/network_cidds/sample_b.json` 复制）。
- 相关文案：`demo_artifacts/w4_demo_assets/network/prompts.md`。
- 触发条件：未上传待核查资料时，不展示核查表，不运行双轨对比，不展示报告预览。

### 用户输入问题

在“双轨对比”步骤使用以下问题，或保持页面预填内容：

```text
请基于我上传的待核查 NetFlow 资料，生成或抽取 10 条 CIDDS 风格记录，并说明哪些记录违反 UDP Flags、Packets/Bytes 物理上下界或 DNS 端口身份规则；同时给出规则约束后的合规版本。
```

问题应明确三件事：要基于上传的待核查资料、要核查 UDP Flags/Packets/Bytes/DNS 身份规则、要同时输出约束后的合规版本。

### 预期规则

- 协议蕴含：`Proto=UDP` 时不应携带 TCP Flags。
- 物理上界：`Bytes <= 65535 * Packets`。
- 物理下界：`Bytes >= 42 * Packets`。
- 部署规律：端口 53/DNS 身份应保持一致。

### A/B 双轨预期

- A 轨：裸模型生成或抽取 10 条 NetFlow，稳定出现 UDP 带 TCP Flags、Bytes 超出 Packets 物理上界、DNS 端口身份不一致等问题，页面整行标红。
- B 轨：LeJIT/规则约束路径按字段生成并过 Z3；若本机 LeJIT bundle 不可用，回退到归档的 0 违规合规样本，演示仍保持稳定。

### 操作步骤

1. 打开前端 `http://127.0.0.1:5173/#/network`。
2. 在“内置数据”确认训练集 `cidds_wk2_normal_10k.csv` 已作为规则学习资料加载。
3. 进入“规则学习”，等待 live 后端加载归档 NetNomos 自发现规则。
4. 可进入“规则卡”查看规则来源和规则画像。
5. 进入“新资料核查”，点击“选择并上传资料”，手工选择 `demo_artifacts/w4_demo_assets/network/netflow_rule_anomaly_upload.csv`。
6. 确认页面显示上传文件名和 `dataSourceId`；未上传时页面只显示上传提示，不展示核查表。
7. 点击“运行新资料核查”，等待事件流完成。
8. 查看规则核查表，确认说明里显示上传资料名和 `dataSourceId`。
9. 进入“双轨对比”，确认稳定触发场景说明里显示上传资料名和 `dataSourceId`。
10. 使用页面预填问题，点击“运行实时 A/B 双轨”。
11. 等实时工作流完成后，查看 A 轨违规 NetFlow、B 轨 0 违规记录和干预日志。
12. 进入“报告预览/下载”，预览报告并点击“下载报告 Markdown”。
