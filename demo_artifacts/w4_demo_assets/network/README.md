# W4 网络 Demo 资产包

本目录用于 W4 叙事演示的 network demo。演示时从这里选择上传文件，报告问题和讲解词也放在同一目录。

## 目录内容

| 文件 | 用途 |
|---|---|
| `netflow_rule_anomaly_upload.csv` | 演示上传文件，CIDDS 风格 NetFlow 摘要，故意包含 UDP Flags、Packets/Bytes 和 DNS 身份异常。 |
| `cidds_wk2_normal_10k_correct_training.csv` | 10,000 行 CIDDS 正常训练流量，用于讲解 NetNomos 规则自发现来源。 |
| `network_generated_10_reference.csv` | 网络生成样本参考，不作为上传文件。 |
| `network_b_track_reference_sample.json` | 从 `forge/rulesets/network_cidds/sample_b.json` 复制的 B 轨合规参考样本，不作为上传文件。 |
| `prompts.md` | 可直接复制的中文问题、A/B 双轨讲解词和报告生成口径。 |
| `references/` | 从网络场景、知识库和 golden 规则集复制的相关说明、规则控制参考。 |

## 演示流程

1. 打开 `http://127.0.0.1:5173/#/network`。
2. 在“内置数据”确认 CIDDS 训练集用于规则学习，进入“规则学习”。
3. 等待后端加载归档 NetNomos 自发现 golden 规则，查看规则来源 badge。
4. 进入“新资料核查”，选择并上传本目录的 `netflow_rule_anomaly_upload.csv`。
5. 确认页面显示文件名与 `dataSourceId`，点击“运行新资料核查”。
6. 到“双轨对比”步骤，复制 `prompts.md` 里的“报告输入框问题”或保留页面预填问题。
7. 点击“运行实时 A/B 双轨”，查看 A 轨违规 NetFlow、B 轨 0 违规记录和干预日志。
8. 到“报告预览/下载”查看 Markdown 报告。

## 报告输入框问题

```text
请基于我上传的待核查 NetFlow 资料，生成或抽取 10 条 CIDDS 风格记录，并说明哪些记录违反 UDP Flags、Packets/Bytes 物理上下界或 DNS 端口身份规则；同时给出规则约束后的合规版本。
```

## 上传文件内的异常

- `anomaly_udp_with_tcp_flags`：`Proto=UDP` 却带 `.AP.SF` TCP flags。
- `anomaly_bytes_above_packet_upper_bound`：`Packets=1`，`Bytes=90000`，超过 `65535 * Packets` 上界。
- `anomaly_bytes_below_packet_lower_bound`：`Packets=10`，`Bytes=200`，低于 `42 * Packets` 下界。
- `anomaly_dns_port_identity_mismatch`：目标端口是 `53`，但目标身份不是 `DNS`。

## 当前 W4 限制

- 上传文件会被后端保存到 `demo_artifacts/uploads/network_cidds/` 并登记 `dataSourceId`。
- 当前 W4 管线仍复用稳定网络演示结果：规则学习加载归档 NetNomos 自发现规则，A/B 双轨使用内置生成/合规样本路径，尚未逐行解析任意上传 NetFlow 文件并把每行异常映射到最终表格。
- 因此演示口径应说“上传用于触发新资料核查流程并展示资料来源，核查和双轨结果复用 W4 稳定管线”，不要说系统已经完成通用 PCAP/NetFlow 文件解析。
