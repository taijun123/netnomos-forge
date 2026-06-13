/**
 * src/mock/network.ts
 * ----------------------------------------------------------------------------
 * 网络 demo 的 mock 数据：规则卡墙、违规清单、双轨 NetFlow 对比。
 * 结构对齐 src/types/api.ts（即 contracts.py）。后端就绪后替换为真实接口数据。
 * ----------------------------------------------------------------------------
 */
import type { RuleCard, Violation } from "../types/api";

// === 规则卡墙（五类示例，含公式 / 中文解释 / 置信度 / enabled 开关）===
export interface NetworkRuleCard extends RuleCard {
  kind: string;
  confidence: number;
  enabled: boolean;
  // 结构化公式（对齐 contracts.Rule.formula），用于规则溯源展示
  formula: Record<string, unknown>;
}

export const NETWORK_RULE_CARDS: NetworkRuleCard[] = [
  {
    rule_id: "N001",
    title_zh: "字节数取值范围",
    explanation_zh:
      "单条流的字节数始终落在观测区间内。超出上界往往是统计字段错位或单位混淆，低于下界则可能是空流或采样异常。",
    formula_text: "64 ≤ Bytes ≤ 1,073,741,824",
    formula: { op: "range", field: "Bytes", min: 64, max: 1073741824 },
    kind: "range",
    tags: ["取值范围"],
    confidence: 0.99,
    is_coincidence: false,
    enabled: true,
    citation: "NetNomos NSDI'26 §4.2 区间规则",
  },
  {
    rule_id: "N002",
    title_zh: "物理上界：每包至多 65535 字节",
    explanation_zh:
      "IPv4 单包总长上限为 65535 字节，因此一条流的字节数不可能超过包数乘以 65535。违反它意味着 Bytes 与 Packets 至少有一个被写错。",
    formula_text: "65535 × Packets ≥ Bytes",
    formula: { op: "bound", lhs: ["mul", 65535, "Packets"], cmp: ">=", rhs: "Bytes" },
    kind: "bound",
    tags: ["物理上界"],
    confidence: 1.0,
    is_coincidence: false,
    enabled: true,
    citation: "RFC 791 IPv4 Total Length",
  },
  {
    rule_id: "N003",
    title_zh: "物理下界：每包至少 42 字节",
    explanation_zh:
      "以太网最小帧（含 IP/传输层头部）约 42 字节，因此字节数不可能小于包数的 42 倍。违反它通常是包数被夸大或字节数缺失。",
    formula_text: "42 × Packets ≤ Bytes",
    formula: { op: "bound", lhs: ["mul", 42, "Packets"], cmp: "<=", rhs: "Bytes" },
    kind: "bound",
    tags: ["物理下界"],
    confidence: 0.98,
    is_coincidence: false,
    enabled: true,
    citation: "IEEE 802.3 最小帧长",
  },
  {
    rule_id: "N004",
    title_zh: "协议蕴含：UDP 不应带 TCP 标志位",
    explanation_zh:
      "UDP 是无连接协议，没有 SYN/ACK/FIN 等 TCP 控制标志。若 Proto=UDP 却出现 TCP Flags，几乎可断定是协议字段与标志位张冠李戴。",
    formula_text: "Proto = UDP → Flags = noflags",
    formula: { op: "implication", if: { Proto: "UDP" }, then: { Flags: "noflags" } },
    kind: "implication",
    tags: ["协议蕴含"],
    confidence: 1.0,
    is_coincidence: false,
    enabled: true,
    citation: "RFC 768 UDP / RFC 9293 TCP Flags",
  },
  {
    rule_id: "N005",
    title_zh: "部署规律：53 端口走 DNS",
    explanation_zh:
      "本网络中源端口 53 的流量在训练集里全部是 DNS 服务。这是该部署环境的经验规律（非协议强制），可用于异常端口占用的初筛，置信度略低于物理约束。",
    formula_text: "SrcPt = 53 → AppProto = dns",
    formula: { op: "implication", if: { SrcPt: 53 }, then: { AppProto: "dns" } },
    kind: "implication",
    tags: ["部署规律"],
    confidence: 0.93,
    is_coincidence: false,
    enabled: true,
    citation: "本部署 cidds_wk2 经验观测",
  },
];

// === 违规清单（对应 Violation：行号 / 字段 / 命中规则 / 实际值 / 期望值）===
export const NETWORK_VIOLATIONS: Violation[] = [
  {
    row_index: 2,
    rule_id: "N004",
    rule_text: "Proto = UDP → Flags = noflags",
    fields: ["Proto", "Flags"],
    observed: { Proto: "UDP", Flags: ".A..S." },
    expected: "UDP 流应为 noflags（无 TCP 标志）",
    message_zh: "第 3 行 UDP 流携带了 TCP 的 SYN+ACK 标志，协议字段与标志位矛盾。",
  },
  {
    row_index: 5,
    rule_id: "N002",
    rule_text: "65535 × Packets ≥ Bytes",
    fields: ["Packets", "Bytes"],
    observed: { Packets: 2, Bytes: 204800 },
    expected: "Bytes 应 ≤ 131,070（=65535 × 2）",
    message_zh: "第 6 行 2 个包却有 204,800 字节，超过单包字节物理上界。",
  },
  {
    row_index: 8,
    rule_id: "N003",
    rule_text: "42 × Packets ≤ Bytes",
    fields: ["Packets", "Bytes"],
    observed: { Packets: 40, Bytes: 800 },
    expected: "Bytes 应 ≥ 1,680（=42 × 40）",
    message_zh: "第 9 行 40 个包却仅 800 字节，低于每包最小帧长下界。",
  },
];

// === 双轨 NetFlow 对比（10 条记录，3 条问题记录）===
export interface NetFlowRow {
  no: number;
  duration: string;
  proto: string;
  src: string;
  dst: string;
  srcPt: number;
  dstPt: number;
  packets: number;
  bytes: number;
  flags: string;
  appProto: string;
  /** A 轨命中的违规规则 id（为空表示该行合规） */
  violatedRuleIds?: string[];
  /** 该行被标红的字段 */
  badFields?: string[];
  /** 悬浮提示：命中规则的中文说明 */
  tip?: string;
}

// A 轨（裸模型）：3 条问题记录整行红底
export const TRACK_A_FLOWS: NetFlowRow[] = [
  { no: 1, duration: "0.004", proto: "TCP", src: "192.168.220.15", dst: "192.168.100.5", srcPt: 51324, dstPt: 443, packets: 12, bytes: 8432, flags: ".AP.SF", appProto: "tls" },
  { no: 2, duration: "0.001", proto: "UDP", src: "192.168.220.16", dst: "192.168.100.5", srcPt: 53124, dstPt: 53, packets: 2, bytes: 198, flags: "noflags", appProto: "dns" },
  {
    no: 3, duration: "0.002", proto: "UDP", src: "192.168.220.18", dst: "8.8.8.8", srcPt: 51777, dstPt: 53, packets: 2, bytes: 256, flags: ".A..S.", appProto: "dns",
    violatedRuleIds: ["N004"], badFields: ["proto", "flags"],
    tip: "命中 N004：UDP 流携带 TCP SYN+ACK 标志，协议与标志位矛盾。",
  },
  { no: 4, duration: "0.011", proto: "TCP", src: "192.168.220.20", dst: "192.168.210.3", srcPt: 49213, dstPt: 80, packets: 18, bytes: 14209, flags: ".AP.SF", appProto: "http" },
  {
    no: 5, duration: "0.003", proto: "TCP", src: "192.168.220.21", dst: "192.168.210.3", srcPt: 49888, dstPt: 443, packets: 2, bytes: 204800, flags: ".AP.SF", appProto: "tls",
    violatedRuleIds: ["N002"], badFields: ["packets", "bytes"],
    tip: "命中 N002：2 个包却 204,800 字节，超过 65535×Packets 物理上界。",
  },
  { no: 6, duration: "0.007", proto: "UDP", src: "192.168.220.24", dst: "224.0.0.251", srcPt: 5353, dstPt: 5353, packets: 4, bytes: 612, flags: "noflags", appProto: "mdns" },
  { no: 7, duration: "0.052", proto: "TCP", src: "192.168.220.30", dst: "192.168.100.9", srcPt: 50122, dstPt: 22, packets: 64, bytes: 9821, flags: ".AP.SF", appProto: "ssh" },
  {
    no: 8, duration: "0.004", proto: "TCP", src: "192.168.220.33", dst: "192.168.210.7", srcPt: 51002, dstPt: 443, packets: 40, bytes: 800, flags: ".AP.SF", appProto: "tls",
    violatedRuleIds: ["N003"], badFields: ["packets", "bytes"],
    tip: "命中 N003：40 个包仅 800 字节，低于 42×Packets 最小帧长下界。",
  },
  { no: 9, duration: "0.009", proto: "UDP", src: "192.168.220.40", dst: "192.168.100.5", srcPt: 53456, dstPt: 53, packets: 2, bytes: 174, flags: "noflags", appProto: "dns" },
  { no: 10, duration: "0.021", proto: "TCP", src: "192.168.220.44", dst: "192.168.210.9", srcPt: 49555, dstPt: 80, packets: 22, bytes: 17640, flags: ".AP.SF", appProto: "http" },
];

// B 轨（LeJIT 约束）：同条件生成，0 违规
export const TRACK_B_FLOWS: NetFlowRow[] = [
  { no: 1, duration: "0.004", proto: "TCP", src: "192.168.220.15", dst: "192.168.100.5", srcPt: 51324, dstPt: 443, packets: 12, bytes: 8432, flags: ".AP.SF", appProto: "tls" },
  { no: 2, duration: "0.001", proto: "UDP", src: "192.168.220.16", dst: "192.168.100.5", srcPt: 53124, dstPt: 53, packets: 2, bytes: 198, flags: "noflags", appProto: "dns" },
  { no: 3, duration: "0.002", proto: "UDP", src: "192.168.220.18", dst: "8.8.8.8", srcPt: 51777, dstPt: 53, packets: 2, bytes: 256, flags: "noflags", appProto: "dns" },
  { no: 4, duration: "0.011", proto: "TCP", src: "192.168.220.20", dst: "192.168.210.3", srcPt: 49213, dstPt: 80, packets: 18, bytes: 14209, flags: ".AP.SF", appProto: "http" },
  { no: 5, duration: "0.003", proto: "TCP", src: "192.168.220.21", dst: "192.168.210.3", srcPt: 49888, dstPt: 443, packets: 2, bytes: 1180, flags: ".AP.SF", appProto: "tls" },
  { no: 6, duration: "0.007", proto: "UDP", src: "192.168.220.24", dst: "224.0.0.251", srcPt: 5353, dstPt: 5353, packets: 4, bytes: 612, flags: "noflags", appProto: "mdns" },
  { no: 7, duration: "0.052", proto: "TCP", src: "192.168.220.30", dst: "192.168.100.9", srcPt: 50122, dstPt: 22, packets: 64, bytes: 9821, flags: ".AP.SF", appProto: "ssh" },
  { no: 8, duration: "0.004", proto: "TCP", src: "192.168.220.33", dst: "192.168.210.7", srcPt: 51002, dstPt: 443, packets: 40, bytes: 6240, flags: ".AP.SF", appProto: "tls" },
  { no: 9, duration: "0.009", proto: "UDP", src: "192.168.220.40", dst: "192.168.100.5", srcPt: 53456, dstPt: 53, packets: 2, bytes: 174, flags: "noflags", appProto: "dns" },
  { no: 10, duration: "0.021", proto: "TCP", src: "192.168.220.44", dst: "192.168.210.9", srcPt: 49555, dstPt: 80, packets: 22, bytes: 17640, flags: ".AP.SF", appProto: "http" },
];

// B 轨干预日志（每步过 Z3 的修正记录）
export const TRACK_B_INTERVENTION_LOG: string[] = [
  "第 3 行 · UDP 流标志位：Z3 拒绝候选 .A..S.，回退到约束可行解 noflags（N004）。",
  "第 5 行 · 字节数：候选 204,800 违反 65535×Packets 上界，投影到可行域 1,180（N002）。",
  "第 8 行 · 字节数：候选 800 违反 42×Packets 下界，投影到可行域 6,240（N003）。",
  "全部 10 条记录逐字段经 Z3 校验通过，满足率 1.0。",
];

export const NETWORK_REPORT_META = {
  title: "网络流量审计与遥测健康报告",
  subtitle: "基于 cidds_wk2 规则集对 wk3 新流量的复用核查",
  generatedAt: "2026-06-13",
  fileName: "网络流量审计与遥测健康报告.pdf",
};
