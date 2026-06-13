/**
 * src/mock/sse.ts
 * ----------------------------------------------------------------------------
 * 本地 mock SSE：用 setInterval 按 contracts 的 WorkflowEvent 结构逐条推送
 * upload → prepare → learn → explain（→ validate → project → report → diff）
 * 事件序列。供 events.ts 在真实后端未就绪时 fallback，保证纯前端可独立演示。
 *
 * 事件结构严格对齐 contracts.WorkflowEvent：id/time/agent/stage/status/description，
 * agent 由 STAGE_AGENT 推导。
 * ----------------------------------------------------------------------------
 */
import { STAGE_AGENT } from "../types/api";
import type { WorkflowEvent } from "../types/api";

export type MockSequenceId =
  | "learn-network"
  | "validate-network"
  | "report-network"
  | "learn-finance"
  | "validate-finance"
  | "report-finance";

interface StepSpec {
  stage: keyof typeof STAGE_AGENT | string;
  status: WorkflowEvent["status"];
  description: string;
}

// 各场景的事件脚本。description 为中文，直接展示。
const SEQUENCES: Record<MockSequenceId, StepSpec[]> = {
  "learn-network": [
    { stage: "control", status: "running", description: "工作流接到「规则自发现」任务，开始调度数据接入。" },
    { stage: "upload", status: "running", description: "接收 cidds_wk2_normal_10k.csv（10,000 行 NetFlow）。" },
    { stage: "upload", status: "done", description: "上传完成，校验列名与编码通过。" },
    { stage: "prepare", status: "running", description: "解析字段 / 归一类型，构建 DatasetSpec 与文法。" },
    { stage: "prepare", status: "done", description: "预处理完成，进入规则挖掘。" },
    { stage: "learn", status: "running", description: "调用 NetNomos（hitting-set 学习器）挖掘候选规则…" },
    { stage: "learn", status: "running", description: "Z3 逐条校验候选规则在训练集上的满足率。" },
    { stage: "learn", status: "done", description: "学出 5 类共 18 条规则，训练集满足率 1.0。" },
    { stage: "explain", status: "running", description: "调用 RAG + LLM 为规则生成中文规则卡。" },
    { stage: "explain", status: "done", description: "规则卡生成完毕，标注 1 条疑似巧合规则。" },
    { stage: "control", status: "done", description: "规则集归档完成。" },
  ],
  "validate-network": [
    { stage: "upload", status: "running", description: "接收 wk3 抽样新流量（50,000 行）。" },
    { stage: "prepare", status: "done", description: "对齐 schema，准备复用既有规则集核查。" },
    { stage: "validate", status: "running", description: "用规则集对新数据逐行 Z3 校验…" },
    { stage: "validate", status: "done", description: "核查完成，命中 3 类违规，满足率 99.4%。" },
  ],
  "report-network": [
    { stage: "control", status: "running", description: "发起双轨对比生成。" },
    { stage: "report", status: "running", description: "A 轨：裸模型（qwen2.5）用相同 prompt 生成 10 条 NetFlow。" },
    { stage: "report", status: "running", description: "B 轨：LeJIT bundle 按字段拓扑序逐步过 Z3 生成。" },
    { stage: "diff", status: "running", description: "比对双轨，标红 A 轨违规记录。" },
    { stage: "diff", status: "done", description: "对比完成：A 轨 3 条违规，B 轨 0 违规。" },
  ],
  "learn-finance": [
    { stage: "control", status: "running", description: "工作流接到财务「规则自发现」任务。" },
    { stage: "upload", status: "running", description: "接收合成训练集（3 行业 × 40 公司 × 8 期 = 960 行）。" },
    { stage: "upload", status: "done", description: "中文列名经 source_name 映射为英文规范名。" },
    { stage: "prepare", status: "done", description: "派生 GrossProfit / InventoryNetInflow 等折叠字段。" },
    { stage: "learn", status: "running", description: "挖掘勾稽与行业蕴含规则…" },
    { stage: "learn", status: "running", description: "核心恒等式 R01/R02/R05 经人工通道兜底注入。" },
    { stage: "learn", status: "done", description: "规则库就绪：5 条核心恒等式 + 行业占比区间。" },
    { stage: "explain", status: "done", description: "生成中文规则卡（含勾稽 / 配平 / 毛利）。" },
    { stage: "control", status: "done", description: "财务规则集归档完成。" },
  ],
  "validate-finance": [
    { stage: "upload", status: "running", description: "接收「华信咨询」待审资料包。" },
    { stage: "validate", status: "running", description: "对资料包逐项核查勾稽关系…" },
    { stage: "validate", status: "blocked", description: "命中 F1 进销存恒等式破坏（成本 3,000 应为 2,000）。" },
    { stage: "validate", status: "blocked", description: "命中 F2b 资产负债表不配平（差额 500）。" },
    { stage: "validate", status: "done", description: "核查完成，F1–F4 共 4 项错误全部命中。" },
  ],
  "report-finance": [
    { stage: "report", status: "running", description: "A 轨：裸模型照抄错误资料撰写财务分析报告。" },
    { stage: "validate", status: "running", description: "B 轨：先 validate 命中 F1–F4。" },
    { stage: "project", status: "running", description: "用 Z3 求最近可行解修正口径（营业成本→2,000）。" },
    { stage: "report", status: "running", description: "B 轨：衍生指标按修正值程序回填，正文引用规则卡。" },
    { stage: "diff", status: "done", description: "双轨报告就绪：A 轨标红 4 处，B 轨 0 违规。" },
  ],
};

let counter = 0;
function makeId(): string {
  counter += 1;
  return `mock-${Date.now().toString(36)}-${counter.toString(36)}`;
}

function isoNow(): string {
  // 与后端 contracts.WorkflowEvent.make 一致的 ISO8601（秒精度）。
  return new Date().toISOString().slice(0, 19);
}

export interface MockStreamCallbacks {
  onEvent: (event: WorkflowEvent) => void;
  onDone?: () => void;
}

/** 推送间隔（毫秒）。可按需调速；演示节奏约 0.7s/条。 */
export const MOCK_STEP_INTERVAL_MS = 720;

/**
 * 启动一条 mock 工作流。返回可 close 的 handle（卸载组件时调用避免泄漏）。
 */
export function mockWorkflowStream(
  sequence: MockSequenceId,
  cb: MockStreamCallbacks
): { close: () => void } {
  const steps = SEQUENCES[sequence] ?? [];
  let i = 0;

  const timer = setInterval(() => {
    if (i >= steps.length) {
      clearInterval(timer);
      cb.onDone?.();
      return;
    }
    const step = steps[i];
    const event: WorkflowEvent = {
      id: makeId(),
      time: isoNow(),
      agent: STAGE_AGENT[step.stage] ?? "A",
      stage: step.stage,
      status: step.status,
      description: step.description,
    };
    cb.onEvent(event);
    i += 1;
  }, MOCK_STEP_INTERVAL_MS);

  return {
    close: () => clearInterval(timer),
  };
}

/** 该序列的总步数（用于进度条估算）。 */
export function sequenceLength(sequence: MockSequenceId): number {
  return (SEQUENCES[sequence] ?? []).length;
}
