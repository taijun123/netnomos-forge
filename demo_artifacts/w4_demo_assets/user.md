# W4 Demo 用户上传说明

这个目录是演示时的入口。两个 demo 分开存放，演示时只需要从对应文件夹选择标注为“上传文件”的资料；其它文件是正确数据、规则、样本和讲解参考，不要上传到页面。

## 1. 财务 Demo

打开界面：

```text
http://127.0.0.1:5173/?v=w4source#/finance
```

页面步骤：

1. 进入“训练资料预览”，点击“开始规则学习”。
2. 等“规则学习”完成。
3. 进入“资料上传”。
4. 点击“选择并上传资料”。
5. 选择下面这个文件：

```text
demo_artifacts/w4_demo_assets/finance/huaxin_audit_package.csv
```

上传后继续：

1. 页面显示文件名和 `dataSourceId` 后，点击“进入规则核查”。
2. 点击“运行资料规则核查”。
3. 进入“输入报告问题”，复制：

```text
demo_artifacts/w4_demo_assets/finance/prompts.md
```

里的“报告输入框问题”。

财务目录里的其它文件：

- `finance_training_clean_960_correct.csv`：完整 960 行仿真正确训练数据，英文列名，用于讲解“规则学习来自干净训练集”。
- `finance_training_clean_960_correct_zh.csv`：完整 960 行仿真正确训练数据，中文列名参考。
- `huaxin_clean_reference.csv`：华信咨询 8 期正确对照资料。
- `truth_table.json`：华信咨询异常注入真值表。
- `references/rules/finance_golden_rules.json`：财务 golden 规则参考。
- `README.md`：财务 demo 详细操作说明和当前 W4 限制。

## 2. 网络 Demo

打开界面：

```text
http://127.0.0.1:5173/?v=w4source#/network
```

页面步骤：

1. 进入“内置数据”，确认训练集说明。
2. 进入“规则学习”，等待 NetNomos 自发现规则加载完成。
3. 可进入“规则卡”查看“数据自发现”规则来源。
4. 进入“新资料核查”。
5. 点击“选择并上传资料”。
6. 选择下面这个文件：

```text
demo_artifacts/w4_demo_assets/network/netflow_rule_anomaly_upload.csv
```

上传后继续：

1. 页面显示文件名和 `dataSourceId` 后，点击“运行新资料核查”。
2. 进入“双轨对比”，复制：

```text
demo_artifacts/w4_demo_assets/network/prompts.md
```

里的“报告输入框问题”。

网络目录里的其它文件：

- `cidds_wk2_normal_10k_correct_training.csv`：10,000 行 CIDDS 正常训练流量，规则学习来源参考。
- `network_generated_10_reference.csv`：网络生成样本参考，不作为上传文件。
- `network_b_track_reference_sample.json`：B 轨 0 违规合规样本参考。
- `references/rules/network_golden_rules.json`：网络 NetNomos golden 自发现规则。
- `references/rules/network_golden_manifest.json`：网络规则学习元信息。
- `README.md`：网络 demo 详细操作说明和当前 W4 限制。

## 演示口径

当前 W4 已经实现：页面文件选择、上传落盘、`dataSourceId` 登记、核查/双轨 job 携带上传资料和问题。

当前 W4 仍需如实说明：上传资料用于触发流程和展示资料来源，核查与 A/B 结果仍复用稳定演示管线；尚未完成任意 CSV/PDF/PCAP 的通用逐行解析。
