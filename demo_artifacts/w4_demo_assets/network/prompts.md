# 网络 Demo 可复制文案

## 报告输入框问题

```text
请基于我上传的待核查 NetFlow 资料，生成或抽取 10 条 CIDDS 风格记录，并说明哪些记录违反 UDP Flags、Packets/Bytes 物理上下界或 DNS 端口身份规则；同时给出规则约束后的合规版本。
```

## A/B 双轨讲解词

A 轨讲法：

```text
A 轨是不加规则约束的裸模型路径。它会生成或复述 CIDDS 风格 NetFlow，但可能出现 UDP 带 TCP Flags、Bytes 和 Packets 物理关系不成立、DNS 端口身份不一致等问题，所以页面会把违规行标红。
```

B 轨讲法：

```text
B 轨是规则约束路径。优先走 LeJIT/规则约束生成并经过终检；如果本机 LeJIT bundle 不可用，就使用归档的 0 违规合规样本兜底。演示重点是：同样的报告目标，B 轨会把协议、物理边界和端口身份规则放进生成闭环。
```

## 报告生成口径

```text
网络报告按“NetNomos 自发现规则 -> 新资料核查 -> A/B 违规对比 -> 合规样本说明”的顺序组织。A 轨用于暴露裸生成风险，B 轨用于展示规则约束后可交付的合规版本。
```

## 页面交互提示

```text
现在我上传的是 demo_artifacts/w4_demo_assets/network/netflow_rule_anomaly_upload.csv。这个文件里故意放了 UDP Flags、Bytes/Packets 上下界和 DNS 身份不一致的问题，便于讲解规则为什么需要进入生成流程。
```

```text
注意当前 W4 版本保存了上传文件并登记 dataSourceId，但核查和双轨表格仍复用稳定演示管线；这保证演示稳定，也如实说明通用 NetFlow/PCAP 解析还不是本轮能力边界。
```
