# Network Flow Security and Audit Knowledge

> 用于规则卡 RAG 的网络流量审计知识库。资料来自 NIST SP 800-92、IETF RFC 7011/7012、CIDDS/NetFlow 场景资料和项目内 NetNomos/LeJIT 约束说明。

## 日志管理与可追溯性

NIST SP 800-92 强调安全日志管理需要覆盖采集、传输、存储、分析和维护全过程，日志不只是事后排障材料，也是发现异常、支撑审计和响应事件的证据链。对 NetFlow 场景，规则卡应说明一条异常流量为什么会影响可追溯性：例如字段缺失、协议与端口不一致、时间或计数异常，都会降低日志作为审计证据的可靠性。

Source: NIST SP 800-92, Guide to Computer Security Log Management, https://csrc.nist.gov/pubs/sp/800/92/final

## IPFIX/NetFlow 字段语义

RFC 7011 将 IPFIX 定义为在网络中交换流量流信息的标准协议，核心是用模板记录描述字段，再用数据记录承载具体流。规则卡解释 Proto、Packets、Bytes、端口、地址等字段时，应把它们当作结构化测量值而不是自然语言文本；一旦字段组合违反协议或物理约束，通常说明生成、采集或解析链路存在问题。

Source: RFC 7011, Specification of the IP Flow Information Export Protocol, https://www.rfc-editor.org/rfc/rfc7011

## IPFIX 信息元素与类型边界

RFC 7012 定义了 IPFIX 信息模型，说明流记录中的信息元素具有明确类型和含义。Packets、Bytes 这类计数值应保持非负并与链路层/网络层物理边界一致；端口号属于有限范围，协议字段和 TCP flags 也有明确语义边界。规则卡遇到上下界或类型规则时，应解释为“字段语义边界”而不是经验性阈值。

Source: RFC 7012, Information Model for IP Flow Information Export, https://www.rfc-editor.org/rfc/rfc7012

## 协议蕴含：UDP 与 TCP Flags

UDP 是无连接传输协议，不使用 TCP 的 SYN、ACK、FIN 等连接状态标志。若一条 NetFlow 记录显示 Proto=UDP 却携带 TCP Flags，通常意味着模型伪造了不可能组合，或采集/字段映射环节把不同协议的属性混在一起。规则卡可把这类规则解释为协议语义约束，违反时应优先检查数据生成器、解析器和协议字段映射。

Source: RFC 7011/7012 field semantics and standard TCP/UDP protocol semantics, https://www.rfc-editor.org/rfc/rfc7011

## Packets 与 Bytes 的物理上下界

一条流的 Bytes 必须与 Packets 在物理上相容：总字节数不应超过单包最大长度乘以包数，也不应低于合理的最小帧/包开销乘以包数。NetNomos 学到的 `Bytes <= 65535 * Packets` 和 `Bytes >= 42 * Packets` 属于物理边界规则；它们不是业务偏好，而是生成或采集数据必须满足的基本可行域。

Source: IPFIX counter semantics plus project NetNomos network rules, https://www.rfc-editor.org/rfc/rfc7012

## DNS 端口与服务身份

端口 53 通常对应 DNS 服务。CIDDS 风格数据中若出现 DstPt=53 或 SrcPt=53，但主机/应用身份与 DNS 不一致，就可能是端口-身份背离。规则卡应说明这类规则更接近部署规律：在同一网络或数据集内很有价值，但跨组织迁移时需要结合资产台账和服务部署清单复核。

Source: CIDDS NetFlow scenario assumptions and common DNS service convention, https://www.rfc-editor.org/rfc/rfc7012
