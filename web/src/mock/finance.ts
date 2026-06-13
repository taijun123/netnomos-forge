/**
 * src/mock/finance.ts
 * ----------------------------------------------------------------------------
 * 财务 demo 的 mock 数据：合成训练集预览、规则卡、F1–F4 命中、双轨报告段落。
 * 金额单位千元（contracts.FIN_AMOUNT_UNIT），规则编号对齐 contracts.FIN_CORE_RULES_ZH。
 * ----------------------------------------------------------------------------
 */
import type { RuleCard } from "../types/api";

// === 合成训练集预览（示例 8 行，说明 960 行）===
export interface FinanceSampleRow {
  companyId: string;
  industry: string;
  period: number;
  revenue: number;
  cogs: number;
  grossProfit: number;
  inventoryEnd: number;
  totalAssets: number;
  totalLiab: number;
  totalEquity: number;
}

export const FINANCE_SAMPLE_ROWS: FinanceSampleRow[] = [
  { companyId: "CONS-007", industry: "咨询", period: 1, revenue: 12000, cogs: 4200, grossProfit: 7800, inventoryEnd: 180, totalAssets: 21500, totalLiab: 8600, totalEquity: 12900 },
  { companyId: "CONS-007", industry: "咨询", period: 2, revenue: 12600, cogs: 4410, grossProfit: 8190, inventoryEnd: 195, totalAssets: 22340, totalLiab: 8900, totalEquity: 13440 },
  { companyId: "RETL-013", industry: "零售", period: 1, revenue: 30000, cogs: 22500, grossProfit: 7500, inventoryEnd: 6200, totalAssets: 41000, totalLiab: 24600, totalEquity: 16400 },
  { companyId: "RETL-013", industry: "零售", period: 2, revenue: 31500, cogs: 23200, grossProfit: 8300, inventoryEnd: 6480, totalAssets: 42700, totalLiab: 25100, totalEquity: 17600 },
  { companyId: "MANU-021", industry: "制造", period: 1, revenue: 48000, cogs: 33600, grossProfit: 14400, inventoryEnd: 11800, totalAssets: 76500, totalLiab: 46300, totalEquity: 30200 },
  { companyId: "MANU-021", industry: "制造", period: 2, revenue: 49200, cogs: 34100, grossProfit: 15100, inventoryEnd: 12050, totalAssets: 78200, totalLiab: 46900, totalEquity: 31300 },
  { companyId: "CONS-018", industry: "咨询", period: 1, revenue: 8800, cogs: 3080, grossProfit: 5720, inventoryEnd: 95, totalAssets: 15400, totalLiab: 5900, totalEquity: 9500 },
  { companyId: "RETL-002", industry: "零售", period: 1, revenue: 26500, cogs: 19600, grossProfit: 6900, inventoryEnd: 5400, totalAssets: 36800, totalLiab: 21700, totalEquity: 15100 },
];

export const FINANCE_DATASET_META = {
  totalRows: 960,
  description:
    "合成训练集：3 行业（咨询 / 零售 / 制造）× 40 公司 × 8 报告期 = 960 行，金额千元整数。生成器按恒等式正向推导，训练集天然满足全部勾稽与配平规则；行业参数差异化让模型学出行业蕴含式。",
  industries: ["咨询", "零售", "制造"],
  companiesPerIndustry: 40,
  periods: 8,
  unit: "千元",
};

// === 规则卡（R01–R05，对应 contracts.FIN_CORE_RULES_ZH）===
export interface FinanceRuleCard extends RuleCard {
  kind: string;
  confidence: number;
  enabled: boolean;
  // 结构化公式（对齐 contracts.Rule.formula），用于规则溯源展示
  formula: Record<string, unknown>;
}

export const FINANCE_RULE_CARDS: FinanceRuleCard[] = [
  {
    rule_id: "R01",
    title_zh: "进销存勾稽",
    explanation_zh:
      "期末存货 = 期初存货 + 本期采购 − 营业成本。这是存货的恒等式，被结转成本一旦虚增或虚减，等式立刻失衡。",
    formula_text: "Inventory_End = Inventory_Begin + Purchases − COGS",
    formula: { op: "identity", lhs: "Inventory_End", rhs: ["+", "Inventory_Begin", "Purchases", ["neg", "COGS"]] },
    kind: "identity",
    tags: ["勾稽恒等式"],
    confidence: 1.0,
    is_coincidence: false,
    enabled: true,
    citation: "存货核算准则",
  },
  {
    rule_id: "R02",
    title_zh: "资产负债配平",
    explanation_zh:
      "资产总计 = 负债总计 + 所有者权益。会计恒等式的基石，任何一方录入错误都会让报表无法配平。",
    formula_text: "TotalAssets = TotalLiabilities + TotalEquity",
    formula: { op: "identity", lhs: "TotalAssets", rhs: ["+", "TotalLiabilities", "TotalEquity"] },
    kind: "identity",
    tags: ["配平恒等式"],
    confidence: 1.0,
    is_coincidence: false,
    enabled: true,
    citation: "会计基本恒等式",
  },
  {
    rule_id: "R03",
    title_zh: "存货跨期滚动",
    explanation_zh:
      "下期期初存货 = 本期期末存货。跨期连续性约束，断裂往往意味着期间数据被人为拼接或漏记。",
    formula_text: "Inventory_Begin(t+1) = Inventory_End(t)",
    formula: { op: "identity", lhs: "Inventory_Begin_next", rhs: "Inventory_End" },
    kind: "identity",
    tags: ["跨期滚动"],
    confidence: 0.99,
    is_coincidence: false,
    enabled: true,
    citation: "期间连续性",
  },
  {
    rule_id: "R04",
    title_zh: "现金跨期滚动",
    explanation_zh:
      "下期期初现金 = 本期期末现金。现金流的跨期连续性，断裂常见于现金科目被错误结转。",
    formula_text: "Cash_Begin(t+1) = Cash_End(t)",
    formula: { op: "identity", lhs: "Cash_Begin_next", rhs: "Cash_End" },
    kind: "identity",
    tags: ["跨期滚动"],
    confidence: 0.99,
    is_coincidence: false,
    enabled: true,
    citation: "期间连续性",
  },
  {
    rule_id: "R05",
    title_zh: "毛利恒等式",
    explanation_zh:
      "毛利 = 营业收入 − 营业成本。营业成本一旦写错，毛利及其衍生的毛利率、净利率会连环算错。",
    formula_text: "GrossProfit = Revenue − COGS",
    formula: { op: "identity", lhs: "GrossProfit", rhs: ["+", "Revenue", ["neg", "COGS"]] },
    kind: "identity",
    tags: ["毛利恒等式"],
    confidence: 1.0,
    is_coincidence: false,
    enabled: true,
    citation: "利润表口径",
  },
];

// === F1–F4 命中卡（每个 fault：错误值 / 正确值 / 命中规则）===
export interface FinanceFault {
  faultId: string; // F1 / F2a / F2b / F3 / F4
  title: string;
  field: string;
  observed: string; // 错误值
  expected: string; // 正确值
  ruleId: string; // 命中规则 R01–R05
  ruleText: string;
  message: string;
}

export const FINANCE_FAULTS: FinanceFault[] = [
  {
    faultId: "F1",
    title: "进销存恒等式破坏",
    field: "营业成本 COGS",
    observed: "3,000 千元",
    expected: "2,000 千元（=10,000 + 4,000 − 12,000）",
    ruleId: "R01",
    ruleText: "Inventory_End = Inventory_Begin + Purchases − COGS",
    message:
      "营业成本虚增 1,000 千元，导致期末存货勾稽不平。按期初 12,000 + 采购 ⋯ 推算，成本应为 2,000 千元。",
  },
  {
    faultId: "F2a",
    title: "跨期现金断裂",
    field: "期初现金 Cash_Begin",
    observed: "8,500 千元",
    expected: "8,000 千元（=上期期末现金）",
    ruleId: "R04",
    ruleText: "Cash_Begin(t+1) = Cash_End(t)",
    message: "本期期初现金 8,500 与上期期末现金 8,000 不一致，跨期现金滚动断裂。",
  },
  {
    faultId: "F2b",
    title: "资产负债表不配平",
    field: "资产总计 / 负债+权益",
    observed: "差额 500 千元",
    expected: "差额应为 0",
    ruleId: "R02",
    ruleText: "TotalAssets = TotalLiabilities + TotalEquity",
    message: "资产总计与负债加所有者权益相差 500 千元，会计恒等式不成立。",
  },
  {
    faultId: "F3",
    title: "行业异常：存货占比畸高",
    field: "存货 / 资产总计",
    observed: "35%",
    expected: "咨询业典型 < 2%",
    ruleId: "R01",
    ruleText: "行业蕴含：咨询业存货占比区间",
    message: "咨询公司存货占资产 35%，远超行业经验区间（< 2%），疑似科目归类错误。",
  },
  {
    faultId: "F4",
    title: "应收异常增长",
    field: "应收账款 / 营业收入",
    observed: "应收 +300% vs 营收 +15%",
    expected: "应收增速应与营收大体匹配",
    ruleId: "R05",
    ruleText: "应收—营收比率区间",
    message: "应收账款同比 +300%，而营业收入仅 +15%，回款质量异常，存在虚增收入风险。",
  },
];

// === 双轨报告段落（A 轨错误数字 / B 轨修正数字）===
export interface ReportSegment {
  /** 段落富文本片段：text 普通文本，markValue 为需标注的数字 */
  parts: Array<
    | { type: "text"; text: string }
    | {
        type: "mark";
        text: string; // 显示的数字
        // A 轨：错误（红标下划线 + 批注气泡）；B 轨：修正（绿标 + 规则引用）
        note: string; // 批注内容
        ruleId?: string; // B 轨引用的规则卡
      }
  >;
}

export const FINANCE_TRACK_A_REPORT: ReportSegment[] = [
  {
    parts: [
      { type: "text", text: "报告期内，华信咨询实现营业收入 12,000 千元，营业成本 " },
      { type: "mark", text: "3,000", note: "营业成本应为 2,000（F1 进销存勾稽不平）" },
      { type: "text", text: " 千元，毛利 " },
      { type: "mark", text: "9,000", note: "毛利连带算错，应为 10,000" },
      { type: "text", text: " 千元，毛利率 " },
      { type: "mark", text: "75.0%", note: "毛利率连带算错，应为 83.3%" },
      { type: "text", text: "，盈利能力较上期稳中有升。" },
    ],
  },
  {
    parts: [
      { type: "text", text: "资产负债方面，资产总计与负债及所有者权益合计存在 " },
      { type: "mark", text: "500", note: "F2b：资产负债表不配平，差额应为 0" },
      { type: "text", text: " 千元差异，报告未作说明；期初现金 " },
      { type: "mark", text: "8,500", note: "F2a：与上期期末现金 8,000 不符" },
      { type: "text", text: " 千元延续上期口径。" },
    ],
  },
  {
    parts: [
      { type: "text", text: "存货占资产总计 " },
      { type: "mark", text: "35%", note: "F3：咨询业存货占比远超 <2% 经验区间" },
      { type: "text", text: "，应收账款同比增长 " },
      { type: "mark", text: "300%", note: "F4：应收增速远超营收 +15%，回款质量存疑" },
      { type: "text", text: "，公司经营稳健，建议维持现有信用政策。" },
    ],
  },
];

export const FINANCE_TRACK_B_REPORT: ReportSegment[] = [
  {
    parts: [
      { type: "text", text: "报告期内，华信咨询实现营业收入 12,000 千元，营业成本经勾稽核验修正为 " },
      { type: "mark", text: "2,000", note: "由 R01 进销存恒等式投影修正", ruleId: "R01" },
      { type: "text", text: " 千元，毛利 " },
      { type: "mark", text: "10,000", note: "按修正成本由 R05 程序回填", ruleId: "R05" },
      { type: "text", text: " 千元，毛利率 " },
      { type: "mark", text: "83.3%", note: "衍生指标按修正值重算", ruleId: "R05" },
      { type: "text", text: "。" },
    ],
  },
  {
    parts: [
      { type: "text", text: "资产负债表经配平核验，资产总计与负债及所有者权益合计 " },
      { type: "mark", text: "完全配平", note: "由 R02 配平恒等式校验通过", ruleId: "R02" },
      { type: "text", text: "；期初现金按跨期滚动校正为 " },
      { type: "mark", text: "8,000", note: "由 R04 现金跨期滚动校正", ruleId: "R04" },
      { type: "text", text: " 千元，与上期期末一致。" },
    ],
  },
  {
    parts: [
      { type: "text", text: "存货占比与应收增速经行业区间核查后已在附录列示异常提示，正文不采用未经核实的口径，所有数值均由程序按规则回填，" },
      { type: "mark", text: "零违规", note: "终检正则扫描无残留裸数字", ruleId: "R02" },
      { type: "text", text: "。" },
    ],
  },
];

export const FINANCE_TRACK_B_INTERVENTION_LOG: string[] = [
  "F1 · 营业成本 3,000 违反 R01，Z3 求最近可行解修正为 2,000。",
  "F1 衍生 · 毛利 / 毛利率按修正成本经 R05 程序回填（10,000 / 83.3%）。",
  "F2a · 期初现金 8,500 违反 R04，校正为上期期末 8,000。",
  "F2b · 资产负债差额 500 违反 R02，按修正口径重新配平。",
  "F3 / F4 · 行业占比与应收增速异常移入附录提示，正文不采信。",
  "终检 · 正则扫描正文无残留裸数字，满足率 1.0。",
];

export const FINANCE_REPORT_META = {
  title: "年度财务分析与审阅报告",
  company: "华信咨询",
  generatedAt: "2026-06-13",
  fileName: "华信咨询_年度财务分析与审阅报告.pdf",
};
