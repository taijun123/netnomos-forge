/**
 * src/types/api.ts
 * ----------------------------------------------------------------------------
 * 与 netnomos-forge/forge/contracts.py 一一对应的前端类型。
 * 任何字段变更必须先改 contracts.py（冻结契约），再同步本文件。
 * 行内注释标注来源 dataclass / 常量名，便于双向核对。
 * ----------------------------------------------------------------------------
 */

// === 场景（对应 contracts.Scenario）===
export type Scenario = "network_cidds" | "network_pcap" | "finance_v1" | "office_demo";

// === 规则来源（对应 contracts.RuleSource）===
export type RuleSource = "learned" | "manual";

// === 统一规则表示（对应 contracts.Rule dataclass）===
export interface Rule {
  rule_id: string; // 如 "N001" / "R01"
  formula: Record<string, unknown>; // NetNomos 结构化逻辑公式（非自由文本）
  text: string; // 人类可读公式，如 "Proto=UDP -> Flags=noflags"
  kind: string; // range/bound/implication/identity/ratio/...
  source: RuleSource;
  support?: number | null;
  confidence?: number | null;
  enabled: boolean; // 规则库侧栏“人类开关”
}

// === 规则集（对应 contracts.RuleSet dataclass）===
export interface RuleSet {
  scenario: string;
  rules: Rule[];
  rules_path?: string | null; // 落盘的 NetNomos 格式 rules.json
  run_dir?: string | null; // NetNomos 学习产物目录
  created_at: number;
}

// === 单条违规（对应 contracts.Violation dataclass）===
export interface Violation {
  row_index: number; // 数据行号（0 基；展示时 +1）
  rule_id: string;
  rule_text: string;
  fields: string[]; // 涉及字段
  observed: Record<string, unknown>; // 实际值
  expected: string; // 期望描述，如 "应为 2000（=10000+4000-12000）"
  message_zh: string; // 中文说明，前端直接展示
}

// === 校验结果（对应 contracts.ViolationReport dataclass）===
export interface ViolationReport {
  scenario: string;
  data_path: string;
  total_rows: number;
  violations: Violation[];
  satisfaction_rate: number; // 1.0 表示零违规
  by_rule: Record<string, number>; // rule_id -> 命中次数
}

// === 规则卡（对应 contracts.RuleCard dataclass，LLM+RAG 解释产物）===
export interface RuleCard {
  rule_id: string;
  title_zh: string; // 一句话标题
  explanation_zh: string; // 2-4 句中文解释（业务语言）
  formula_text: string;
  tags: string[]; // 如 ["协议蕴含", "物理上界"]
  is_coincidence: boolean; // LLM 判定的疑似巧合规则（前端置灰）
  citation: string; // 论文/领域知识引用
}

// === 双轨（对应 contracts.Track）A=裸模型；B=NetNomos 约束 ===
export type Track = "A" | "B";

// === 单轨报告（对应 contracts.TrackReport dataclass）===
export interface TrackReport {
  track: Track;
  markdown: string; // 报告正文（B 轨为槽位回填后的最终稿）
  slots: Record<string, unknown>; // B 轨数值槽位
  violations: Violation[]; // A 轨被标红的错误
  intervention_log: string[]; // B 轨干预日志
}

// === 双轨报告（对应 contracts.DualReport dataclass）===
export interface DualReport {
  scenario: string;
  title: string;
  track_a: TrackReport;
  track_b: TrackReport;
  diff_html: string; // 标红对比 HTML 片段
}

// === SSE 工作流事件 ===
// AgentCode 对应 contracts.AgentCode（"A"–"F"）；正式 demo 仅显示阶段名称。
export type AgentCode = "A" | "B" | "C" | "D" | "E" | "F";
// EventStatus 对应 contracts.EventStatus
export type EventStatus = "pending" | "running" | "done" | "blocked";

// 流水线阶段 → 演示 Agent 映射（对应 contracts.STAGE_AGENT）
export const STAGE_AGENT: Record<string, AgentCode> = {
  upload: "B", // 数据接入
  prepare: "B",
  learn: "C", // 规则学习
  explain: "D", // 规则解释
  validate: "D", // 规则验证
  project: "E", // 数值投影/修正
  report: "E", // 报告制作
  diff: "E",
  chat: "F", // 受约束聊天
  control: "A", // 流程编排
};

// WorkflowEvent 对应 contracts.WorkflowEvent dataclass
export interface WorkflowEvent {
  id: string;
  time: string; // ISO8601
  agent: AgentCode;
  stage: string; // STAGE_AGENT 的 key
  status: EventStatus;
  description: string;
}

// === REST 接口路径（对应 contracts.API_* 常量）===
export const API = {
  RULESETS_UPLOAD: "/api/rulesets/upload",
  DATA_SOURCES: "/api/data-sources",
  RULESETS_LEARN: "/api/rulesets/learn",
  RULESET_CARDS: (rulesetId: string) => `/api/rulesets/${rulesetId}/cards`,
  REPORTS_GENERATE: "/api/reports/generate",
  WORKFLOW_EVENTS: "/api/workflow/events/stream", // SSE
  CHAT_CONSTRAINED: "/api/chat/constrained",
} as const;

// === 工作流阶段元信息（前端展示用，非契约字段）===
export const AGENT_META: Record<
  AgentCode,
  { name: string; role: string; color: string }
> = {
  A: { name: "流程编排", role: "任务调度", color: "#1677ff" },
  B: { name: "数据接入", role: "上传 / 解析", color: "#f5a623" },
  C: { name: "规则学习", role: "NetNomos / Z3", color: "#22a65a" },
  D: { name: "规则核查", role: "解释 / 验证", color: "#8b5cf6" },
  E: { name: "报告生成", role: "投影 / 双轨报告", color: "#0ea5b7" },
  F: { name: "受约束问答", role: "槽位校验", color: "#e35b8f" },
};
