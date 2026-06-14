// 后端不可用/超时时的降级结果：让 liveResult/validation/dual 能填、群聊能汇总、报告能预览，
// 演示永远跑得完。形态对齐 contracts（types/api 的 Rule/Violation/DualReport）。
import type { WorkflowJobResult } from "../lib/events";
import type { UploadedDataSource } from "../components/DataSourceUploadBox";
import type { Rule, RuleCard, Violation, DualReport } from "../types/api";
import { NETWORK_FILENAME, FINANCE_FILENAME, type DemoScenario } from "./demoAssets";

export const DEMO_MOCK_DATASOURCE: Record<DemoScenario, UploadedDataSource> = {
  network: { dataSourceId: "demo-net-ds", filename: NETWORK_FILENAME, path: "(demo offline)", size: 1019 },
  finance: { dataSourceId: "demo-fin-ds", filename: FINANCE_FILENAME, path: "(demo offline)", size: 1212 },
};

const rule = (rule_id: string, text: string, kind: string, confidence: number): Rule => ({
  rule_id,
  formula: {},
  text,
  kind,
  source: "learned",
  confidence,
  enabled: true,
});

const card = (rule_id: string, title_zh: string, explanation_zh: string, formula_text: string, tags: string[]): RuleCard => ({
  rule_id,
  title_zh,
  explanation_zh,
  formula_text,
  tags,
  is_coincidence: false,
  citation: "NetNomos 自发现",
});

// ===================== 网络 =====================
const NET_RULES: Rule[] = [
  rule("N01", "Proto=UDP → Flags=noflags", "蕴含", 0.99),
  rule("N02", "Bytes ≤ 65535 × Packets（物理上界）", "范围", 0.97),
  rule("N03", "Bytes ≥ 42 × Packets（物理下界）", "范围", 0.96),
  rule("N04", "DstPt=53 ↔ Proto=UDP 且 DNS 身份一致", "蕴含", 0.94),
];
const NET_CARDS: RuleCard[] = [
  card("N01", "UDP 无标志位", "正常 UDP 流不应携带 TCP 标志位（SYN/ACK/FIN 等）。", "UDP ⇒ noflags", ["协议蕴含"]),
  card("N02", "字节数物理上界", "单流字节数不能超过包数 × 最大帧长 65535。", "Bytes ≤ 65535·Packets", ["物理上界"]),
  card("N03", "字节数物理下界", "单流字节数不能低于包数 × 最小帧长 42。", "Bytes ≥ 42·Packets", ["物理下界"]),
  card("N04", "DNS 端口身份", "53 端口流量应为 UDP 且 DNS 身份一致。", "DstPt=53 ⇒ UDP·DNS", ["端口身份"]),
];
const NET_VIOLATIONS: Violation[] = [
  { row_index: 1, rule_id: "N01", rule_text: "Proto=UDP → Flags=noflags", fields: ["Flags"], observed: { Proto: "UDP", Flags: ".AP.SF" }, expected: "noflags（......）", message_zh: "UDP 流出现 TCP 标志位 .AP.SF" },
  { row_index: 2, rule_id: "N02", rule_text: "Bytes ≤ 65535 × Packets", fields: ["Bytes", "Packets"], observed: { Packets: 1, Bytes: 90000 }, expected: "≤ 65535", message_zh: "1 个包却有 90000 字节，超物理上界" },
  { row_index: 3, rule_id: "N03", rule_text: "Bytes ≥ 42 × Packets", fields: ["Bytes", "Packets"], observed: { Packets: 10, Bytes: 200 }, expected: "≥ 420", message_zh: "10 个包仅 200 字节，低于物理下界" },
  { row_index: 4, rule_id: "N04", rule_text: "DstPt=53 ↔ DNS 身份", fields: ["DstPt", "DstIpAddr"], observed: { DstPt: 53, DstIpAddr: "10081_164" }, expected: "DNS 身份一致", message_zh: "53 端口目标身份与 DNS 不一致" },
];
const NET_DUAL: DualReport = {
  scenario: "network_cidds",
  title: "CIDDS NetFlow 双轨对比",
  track_a: {
    track: "A",
    markdown: "A 轨（裸模型）按相同 prompt 生成 NetFlow，出现 UDP 带 TCP 标志位、Bytes/Packets 物理关系不成立、DNS 端口身份不一致等问题，问题行已标红。",
    slots: {},
    violations: NET_VIOLATIONS,
    intervention_log: [],
  },
  track_b: {
    track: "B",
    markdown: "B 轨经 LeJIT/规则约束生成并过终检：UDP 一律 noflags、Bytes 落在 [42·Packets, 65535·Packets]、53 端口保持 DNS 身份，0 违规可交付。",
    slots: {},
    violations: [],
    intervention_log: ["按字段拓扑序生成", "每步过 Z3 约束检查", "UDP 标志位归零", "字节数夹到物理可行域"],
  },
  diff_html: "<div class='demo-diff'>A 轨 4 处违规已在 B 轨修正为合规版本。</div>",
};
export const NETWORK_LEARN_MOCK: WorkflowJobResult = { ruleset_id: "net-demo", rules: NET_RULES, cards: NET_CARDS };
export const NETWORK_VALIDATE_MOCK: WorkflowJobResult = { ...NETWORK_LEARN_MOCK, violations: NET_VIOLATIONS };
export const NETWORK_DUAL_MOCK: WorkflowJobResult = { ...NETWORK_VALIDATE_MOCK, dual: NET_DUAL };

// ===================== 财务 =====================
const FIN_RULES: Rule[] = [
  rule("R01", "GrossProfit = Revenue − COGS（毛利恒等式）", "恒等式", 0.99),
  rule("R02", "TotalAssets = TotalLiabilities + TotalEquity（资产负债配平）", "恒等式", 0.99),
  rule("R03", "Inventory_End = Inventory_Begin + Purchases − COGS（进销存勾稽）", "恒等式", 0.98),
  rule("R04", "下期 Cash_Begin = 本期 Cash_End（现金跨期滚动）", "恒等式", 0.97),
  rule("R05", "存货占比 / 应收增长落在行业分位区间", "范围", 0.85),
];
const FIN_CARDS: RuleCard[] = [
  card("R01", "毛利恒等式", "毛利必须等于营收减营业成本。", "GrossProfit = Revenue − COGS", ["恒等式"]),
  card("R02", "资产负债配平", "总资产必须等于负债加所有者权益。", "Assets = Liab + Equity", ["恒等式"]),
  card("R03", "进销存勾稽", "期末存货 = 期初 + 采购 − 营业成本。", "Inv_End = Inv_Begin + Purchases − COGS", ["恒等式"]),
  card("R04", "现金跨期滚动", "下期期初现金等于本期期末现金。", "Cash_Begin(t+1) = Cash_End(t)", ["跨期"]),
  card("R05", "行业画像/比率背离", "存货占比与应收增长应落在行业分位带内。", "ratio ∈ industry band", ["范围", "风险提示"]),
];
const FIN_VIOLATIONS: Violation[] = [
  { row_index: 2, rule_id: "R03", rule_text: "进销存勾稽", fields: ["COGS"], observed: { COGS: 3000 }, expected: "应为 2000（=10000+12000−... 进销存反推）", message_zh: "第 3 期营业成本应为 2,000，实际 3,000" },
  { row_index: 7, rule_id: "R03", rule_text: "进销存勾稽", fields: ["Inventory_End", "Purchases"], observed: { Inventory_End: 299600, Purchases: 290400 }, expected: "存货异常突增", message_zh: "第 8 期存货/采购异常突增" },
  { row_index: 6, rule_id: "R05", rule_text: "应收增长", fields: ["AccountsReceivable"], observed: { AccountsReceivable: 84000 }, expected: "应收占比异常", message_zh: "第 7 期应收账款异常上升" },
  { row_index: 7, rule_id: "R02", rule_text: "资产负债配平", fields: ["TotalAssets"], observed: { TotalAssets: 856000 }, expected: "配平差异", message_zh: "第 8 期资产负债存在配平差异" },
];
const FIN_DUAL: DualReport = {
  scenario: "finance_v1",
  title: "华信咨询财务双轨审阅报告",
  track_a: {
    track: "A",
    markdown: "A 轨（裸模型）直接读待审资料数值，把第 3 期营业成本 3,000、异常资产总计、异常存货与应收原样写进报告，结论看似流畅但带错数。",
    slots: {},
    violations: FIN_VIOLATIONS,
    intervention_log: [],
  },
  track_b: {
    track: "B",
    markdown: "B 轨先跑规则核查，再由 Projector 对硬勾稽错误做数值修正：营业成本从 3,000 修正为 2,000，资产负债配平与现金跨期被标出，行业画像与比率背离作为风险提示进入审阅口径。",
    slots: { "period3.COGS": 2000 },
    violations: [],
    intervention_log: ["命中 R03：COGS 3000 → 2000", "命中 R02：资产负债配平校正", "R05 行业画像背离 → 风险提示"],
  },
  diff_html: "<div class='demo-diff'>A 轨 4 处错数已在 B 轨修正/标注。</div>",
};
export const FINANCE_LEARN_MOCK: WorkflowJobResult = { ruleset_id: "fin-demo", rules: FIN_RULES, cards: FIN_CARDS };
export const FINANCE_VALIDATE_MOCK: WorkflowJobResult = { ...FINANCE_LEARN_MOCK, violations: FIN_VIOLATIONS };
export const FINANCE_DUAL_MOCK: WorkflowJobResult = { ...FINANCE_VALIDATE_MOCK, dual: FIN_DUAL };

export const LEARN_MOCK: Record<DemoScenario, WorkflowJobResult> = { network: NETWORK_LEARN_MOCK, finance: FINANCE_LEARN_MOCK };
export const VALIDATE_MOCK: Record<DemoScenario, WorkflowJobResult> = { network: NETWORK_VALIDATE_MOCK, finance: FINANCE_VALIDATE_MOCK };
export const DUAL_MOCK: Record<DemoScenario, WorkflowJobResult> = { network: NETWORK_DUAL_MOCK, finance: FINANCE_DUAL_MOCK };
