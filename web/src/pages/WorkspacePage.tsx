import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  Check,
  CheckCircle2,
  CheckSquare,
  ChevronDown,
  Circle,
  Cpu,
  FileText,
  Info,
  Loader2,
  Paperclip,
  Pencil,
  Plus,
  Receipt,
  Shield,
  Sparkles,
  Square,
  Star,
  Truck,
  Upload,
  X,
} from "lucide-react";
import {
  fetchWorkflowJob,
  sendConstrainedChatMessage,
  startOfficeWorkflow,
  startWorkflowJob,
  uploadOfficeDataSource,
  uploadDataSource,
  waitForWorkflowJob,
  type ConstrainedChatResult,
  type DataSourceUploadResult,
  type WorkflowJobStatus,
} from "../lib/apiClient";
import { useDemo } from "../demo/DemoContext";
import { demoQuestion, makeDemoFile } from "../demo/demoAssets";
import type { MockSequenceId } from "../mock/sse";
import type { Scenario, Violation, WorkflowEvent } from "../types/api";

type RulePackKind = "standard" | "custom";
type WorkspaceDemoScenario = "network" | "finance";
type AgentStatus = "pending" | "running" | "done";
type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  result?: ConstrainedChatResult;
};
type LearnStep = 1 | 2 | 3 | 4;

interface TaskItem {
  id: string;
  name: string;
  status: "bad" | "ok";
  summary: string;
  time: string;
}

interface RulePack {
  id: string;
  name: string;
  kind: RulePackKind;
  version: string;
  icon: "finance" | "supply" | "sensor" | "custom";
  rules: string[];
}

interface DemoAgent {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  output?: string;
}

interface WorkspaceDemoConfig {
  title: string;
  sequence: MockSequenceId;
  scenario: Scenario;
  taskName: string;
  pack: RulePack;
  dataNote: string;
}

const DEFAULT_TASKS: TaskItem[] = [
  { id: "task-finance-q1", name: "2026_Q1_财务报表.csv", status: "bad", summary: "3 违规", time: "10分钟前" },
  { id: "task-supply", name: "供应链排程_周报.json", status: "ok", summary: "全部通过", time: "昨天" },
  { id: "task-sensor", name: "设备传感器日志_0610.csv", status: "bad", summary: "1 违规", time: "3天前" },
];

const DEFAULT_PACKS: RulePack[] = [
  {
    id: "finguard",
    name: "财务核查·FinGuard",
    kind: "standard",
    version: "v1.2",
    icon: "finance",
    rules: ["资产负债表配平", "进销存勾稽", "毛利率偏差核查"],
  },
  {
    id: "supply-chain",
    name: "供应链排程",
    kind: "standard",
    version: "v1.0",
    icon: "supply",
    rules: ["交付日期不倒挂", "库存安全线", "供应商产能上限"],
  },
  {
    id: "sensor",
    name: "工业传感器阈值",
    kind: "standard",
    version: "v0.9",
    icon: "sensor",
    rules: ["温度阈值", "连续采样间隔", "异常峰值过滤"],
  },
  {
    id: "expense-custom",
    name: "我的报销单规则",
    kind: "custom",
    version: "v1.0",
    icon: "custom",
    rules: ["差旅住宿单价不超过 800 元/晚", "报销金额 > 5000 元时审批人不能为空"],
  },
];

const LEARNED_RULES = [
  {
    id: 1,
    text: "差旅住宿单价不超过 800 元/晚",
    basis: "依据：296/312 条样本符合 · 置信度 高",
    high: true,
    checked: true,
  },
  {
    id: 2,
    text: "报销金额 > 5000 元时，审批人字段不能为空",
    basis: "依据：87/87 条大额样本均满足 · 置信度 高",
    high: true,
    checked: true,
  },
  {
    id: 3,
    text: "交通费用类目仅限：高铁 / 飞机经济舱 / 出租车",
    basis: "依据：301/312 条样本符合 · 置信度 中",
    high: false,
    checked: true,
  },
  {
    id: 4,
    text: "提交时间集中在每月最后 3 天",
    basis: "依据：仅反映提交习惯，与合规性无关 · 建议忽略",
    high: false,
    checked: false,
  },
];

const INITIAL_MESSAGES: Message[] = [
  {
    id: "seed-user",
    role: "user",
    content: "帮我核查这份Q1财务报表，用FinGuard规则包",
  },
  {
    id: "seed-assistant",
    role: "assistant",
    content: "已对照 30 条规则完成核查：\nR07 资产负债表不平衡，差额 80万\nR14 毛利率计算偏差 2.6%\n27项 全部通过",
  },
];

const RULE_RESULTS = [
  { id: "R07", text: "资产负债表不平衡，差额 80万", pass: false },
  { id: "R14", text: "毛利率计算偏差 2.6%", pass: false },
  { id: "27项", text: "全部通过", pass: true },
];

const NETWORK_DEMO_PACK: RulePack = {
  id: "netflow-guard",
  name: "网络流量·NetFlowGuard",
  kind: "standard",
  version: "v1.1",
  icon: "sensor",
  rules: ["端口策略白名单", "异常出站流量阈值", "CIDR 资产归属核查"],
};

const WORKSPACE_DEMOS: Record<WorkspaceDemoScenario, WorkspaceDemoConfig> = {
  finance: {
    title: "财务报表核查",
    sequence: "validate-finance",
    scenario: "finance_v1",
    taskName: "huaxin_audit_package.csv",
    pack: DEFAULT_PACKS[0],
    dataNote: "workspace-finance-one-click-demo",
  },
  network: {
    title: "网络流量核查",
    sequence: "validate-network",
    scenario: "network_cidds",
    taskName: "netflow_rule_anomaly_upload.csv",
    pack: NETWORK_DEMO_PACK,
    dataNote: "workspace-network-one-click-demo",
  },
};

const DEMO_AGENT_TEMPLATE: Omit<DemoAgent, "status" | "output">[] = [
  { id: "agent-upload", name: "数据接入 Agent", role: "真实上传 demo CSV 并登记 dataSourceId" },
  { id: "agent-learn", name: "规则学习 Agent", role: "后端 NetNomos / Z3 学习或加载规则" },
  { id: "agent-validate", name: "规则核查 Agent", role: "后端按规则集验证上传资料" },
  { id: "agent-report", name: "报告生成 Agent", role: "后端生成 A/B 双轨与修正依据" },
  { id: "agent-answer", name: "回答生成 Agent", role: "前端展示真实 job result，不编造结果" },
];

function makeId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function resultViolations(job: WorkflowJobStatus): Violation[] {
  const result = job.result;
  return result?.violations?.length
    ? result.violations
    : result?.dual?.track_a.violations?.length
      ? result.dual.track_a.violations
      : [];
}

function uniqueRuleIds(violations: Violation[]): string[] {
  return Array.from(new Set(violations.map((violation) => violation.rule_id).filter(Boolean)));
}

function buildResultFromJob(job: WorkflowJobStatus, config: WorkspaceDemoConfig, dataSource: DataSourceUploadResult): ConstrainedChatResult {
  const violations = resultViolations(job);
  const ruleIds = uniqueRuleIds(violations);
  const dual = job.result?.dual;
  const checks = violations.length
    ? violations.slice(0, 5).map((violation) => `${violation.rule_id} 失败：${violation.message_zh}`)
    : ["后端真实核查完成：本次 job 未返回违规项。"];
  const citations = [
    `job:${job.jobId}`,
    `dataSource:${dataSource.dataSourceId}`,
    ...(job.result?.ruleset_id ? [`ruleset:${job.result.ruleset_id}`] : []),
    ...(dual?.title ? [dual.title] : []),
  ];
  const summary = violations.length
    ? `后端真实核查完成：${config.title} 命中 ${violations.length} 条违规，涉及 ${ruleIds.join("、") || "规则项"}。`
    : `后端真实核查完成：${config.title} 未返回违规项。`;
  const reportHint = dual?.track_b?.intervention_log?.length
    ? ` B 轨修正日志：${dual.track_b.intervention_log.slice(0, 2).join("；")}`
    : "";
  return {
    content: `${summary}${reportHint}`,
    constrained: true,
    matchedRules: ruleIds,
    checks,
    citations,
    flagged_numbers: violations.flatMap((violation) =>
      Object.values(violation.observed ?? {})
        .map((value) => String(value))
        .filter(Boolean)
    ).slice(0, 8),
    backend: "real-workflow",
  };
}

function agentIdForEvent(event: WorkflowEvent): DemoAgent["id"] | null {
  if (event.stage === "upload" || event.stage === "prepare") return "agent-upload";
  if (event.stage === "learn" || event.stage === "explain") return "agent-learn";
  if (event.stage === "validate") return "agent-validate";
  if (event.stage === "project" || event.stage === "report" || event.stage === "diff") return "agent-report";
  if (event.stage === "chat" || event.stage === "control") return "agent-answer";
  return null;
}

function statusFromEvent(status: WorkflowEvent["status"]): AgentStatus {
  if (status === "done") return "done";
  if (status === "running") return "running";
  return "pending";
}

function agentsFromJobEvents(events: WorkflowEvent[], current: DemoAgent[]): DemoAgent[] {
  const next = current.map((agent) => ({ ...agent }));
  for (const event of events) {
    const agentId = agentIdForEvent(event);
    if (!agentId) continue;
    const agent = next.find((item) => item.id === agentId);
    if (!agent) continue;
    const eventStatus = statusFromEvent(event.status);
    if (agent.status !== "done" || eventStatus === "done") {
      agent.status = eventStatus;
      agent.output = event.description;
    }
  }
  return next;
}

function finalizeAgents(events: WorkflowEvent[], current: DemoAgent[], result: ConstrainedChatResult): DemoAgent[] {
  const next = agentsFromJobEvents(events, current);
  return next.map((agent) => {
    if (agent.id === "agent-answer") {
      return { ...agent, status: "done", output: result.content ?? "真实后端结果已返回。" };
    }
    if (agent.status === "done") return agent;
    return { ...agent, status: "done", output: agent.output ?? "真实后端阶段已完成。" };
  });
}


export function WorkspacePage() {
  const { mode, officeScenario, runToken, setStatus } = useDemo();
  const [tasks, setTasks] = useState(DEFAULT_TASKS);
  const [selectedTaskId, setSelectedTaskId] = useState(DEFAULT_TASKS[0].id);
  const [rulePacks, setRulePacks] = useState(DEFAULT_PACKS);
  const [selectedPackId, setSelectedPackId] = useState(DEFAULT_PACKS[0].id);
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [ragFiles, setRagFiles] = useState<DataSourceUploadResult[]>([]);
  const [backgroundFiles, setBackgroundFiles] = useState<DataSourceUploadResult[]>([]);
  const [isUploading, setIsUploading] = useState<"rag" | "background" | null>(null);
  const [isLearning, setIsLearning] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [learnJob, setLearnJob] = useState<WorkflowJobStatus | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [showLearnModal, setShowLearnModal] = useState(false);
  const [showManualModal, setShowManualModal] = useState(false);
  const [demoScenario, setDemoScenario] = useState<WorkspaceDemoScenario>("finance");
  const [isAutoDemo, setIsAutoDemo] = useState(false);
  const [demoAgents, setDemoAgents] = useState<DemoAgent[]>([]);
  const ragInputRef = useRef<HTMLInputElement>(null);
  const backgroundInputRef = useRef<HTMLInputElement>(null);
  const lastDemoTokenRef = useRef(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const selectedPack = rulePacks.find((pack) => pack.id === selectedPackId) ?? rulePacks[0];
  const selectedTask = tasks.find((task) => task.id === selectedTaskId) ?? tasks[0];
  const uploadedNames = useMemo(
    () => [...ragFiles, ...backgroundFiles].map((file) => file.filename),
    [backgroundFiles, ragFiles]
  );

  useEffect(() => {
    if (mode !== "workspace" || runToken === 0 || lastDemoTokenRef.current === runToken) return;
    lastDemoTokenRef.current = runToken;
    void runWorkspaceDemo(officeScenario === "finance" ? "finance" : "network");
  }, [mode, officeScenario, runToken]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, demoAgents, isAutoDemo, isChatting]);

  async function runWorkspaceDemo(scenario: WorkspaceDemoScenario = demoScenario) {
    if (isAutoDemo) return;
    const config = WORKSPACE_DEMOS[scenario];
    const agents = DEMO_AGENT_TEMPLATE.map((agent) => ({ ...agent, status: "pending" as AgentStatus }));
    const question = demoQuestion(scenario);
    setStatus("running");
    setWorkspaceError(null);
    setDemoScenario(scenario);
    setIsAutoDemo(true);
    setIsChatting(false);
    setIsLearning(false);
    setDemoAgents(agents);
    setInput(question);
    setRulePacks((cur) => (cur.some((pack) => pack.id === config.pack.id) ? cur : [config.pack, ...cur]));
    setSelectedPackId(config.pack.id);
    const task: TaskItem = {
      id: `real-workspace-${scenario}`,
      name: config.taskName,
      status: "ok",
      summary: "真实后端运行中",
      time: "刚刚",
    };
    setTasks((cur) => [task, ...cur.filter((item) => item.id !== task.id)]);
    setSelectedTaskId(task.id);
    setRagFiles([]);
    setBackgroundFiles([]);
    setLearnJob(null);
    setMessages([
      {
        id: makeId("system"),
        role: "system",
        content: `一键演示 · ${config.title}：正在上传真实 demo 数据，并提交后端 ${config.sequence} workflow。`,
      },
    ]);

    try {
      setDemoAgents((cur) => cur.map((agent) => agent.id === "agent-upload" ? { ...agent, status: "running", output: "正在通过 /api/data-sources 上传真实 demo CSV..." } : agent));
      const dataSource = await uploadDataSource(config.scenario, makeDemoFile(scenario), config.dataNote);
      setRagFiles([dataSource]);
      setBackgroundFiles([dataSource]);
      setDemoAgents((cur) => cur.map((agent) => agent.id === "agent-upload" ? { ...agent, status: "done", output: `已上传 ${dataSource.filename} · dataSourceId ${dataSource.dataSourceId}` } : agent));
      setMessages((cur) => [
        ...cur,
        {
          id: makeId("system"),
          role: "system",
          content: `真实资料已上传：${dataSource.filename} · dataSourceId ${dataSource.dataSourceId}`,
        },
      ]);

      const jobId = await startWorkflowJob(config.sequence, {
        dataSourceId: dataSource.dataSourceId,
        validationDataSourceId: dataSource.dataSourceId,
        question,
        reportPrompt: question,
      });
      setMessages((cur) => [...cur, { id: makeId("system"), role: "system", content: `后端 job 已创建：${jobId}` }]);

      let job = await fetchWorkflowJob(jobId);
      for (let attempt = 0; attempt < 80; attempt += 1) {
        job = await fetchWorkflowJob(jobId);
        setLearnJob(job);
        setDemoAgents((cur) => agentsFromJobEvents(job.events, cur));
        if (job.status === "done" || job.status === "failed") break;
        await new Promise((resolve) => window.setTimeout(resolve, 650));
      }
      setLearnJob(job);
      if (job.status === "failed") {
        throw new Error(job.error || "workflow failed");
      }
      if (job.status !== "done" || !job.result) {
        throw new Error(`workflow did not finish: ${job.status}`);
      }

      const realResult = buildResultFromJob(job, config, dataSource);
      setDemoAgents((cur) => finalizeAgents(job.events, cur, realResult));

      const userMessage: Message = { id: makeId("user"), role: "user", content: question };
      setMessages((cur) => [...cur, userMessage]);
      setMessages((cur) => [
        ...cur,
        {
          id: makeId("assistant"),
          role: "assistant",
          content: realResult.content || "真实后端 workflow 已完成。",
          result: realResult,
        },
      ]);
      const violations = resultViolations(job);
      setTasks((cur) =>
        cur.map((task) =>
          task.id === `real-workspace-${scenario}`
            ? { ...task, status: violations.length ? "bad" : "ok", summary: violations.length ? `${violations.length} 违规` : "全部通过", time: "刚刚" }
            : task
        )
      );
      setInput("");
      setStatus("done");
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setWorkspaceError(text);
      setStatus("error");
      setMessages((cur) => [...cur, { id: makeId("system"), role: "system", content: `工作台一键演示失败：${text}` }]);
    } finally {
      setIsAutoDemo(false);
      setIsChatting(false);
    }
  }

  const startLearning = async () => {
    setWorkspaceError(null);
    setIsLearning(true);
    setMessages((cur) => [
      ...cur,
      {
        id: makeId("system"),
        role: "system",
        content: "已启动 office_demo 规则学习与资料归档工作流，完成后会把规则组和资料源同步到工作台。",
      },
    ]);
    try {
      const dataSourceId = ragFiles[0]?.dataSourceId ?? backgroundFiles[0]?.dataSourceId;
      const jobId = await startOfficeWorkflow({
        dataSourceId,
        validationDataSourceId: dataSourceId,
        question: input || "基于当前规则包与上传资料生成核查上下文。",
      });
      const job = await waitForWorkflowJob(jobId, { attempts: 40, delayMs: 800 });
      setLearnJob(job);
      if (job.status === "failed") {
        throw new Error(job.error || "office workflow failed");
      }
      const nextPackName = job.result?.ruleset_id
        ? `办公室综合规则包·${job.result.ruleset_id.slice(0, 6)}`
        : "办公室综合规则包";
      const nextPack: RulePack = {
        id: `office-${job.jobId}`,
        name: nextPackName,
        kind: "custom",
        version: "v1.0",
        icon: "custom",
        rules: (job.result?.rules ?? []).slice(0, 5).map((rule) => rule.text || rule.rule_id),
      };
      setRulePacks((cur) => [nextPack, ...cur]);
      setSelectedPackId(nextPack.id);
      setMessages((cur) => [
        ...cur,
        {
          id: makeId("assistant"),
          role: "assistant",
          content: `规则学习完成：${job.result?.rules?.length ?? 0} 条规则、${job.result?.cards?.length ?? 0} 张规则卡已归档。现在可以用 ${nextPack.name} 提问。`,
        },
      ]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setWorkspaceError(text);
      setMessages((cur) => [
        ...cur,
        { id: makeId("system"), role: "system", content: `规则学习失败：${text}` },
      ]);
    } finally {
      setIsLearning(false);
    }
  };

  const uploadFile = async (file: File, kind: "rag" | "background") => {
    setWorkspaceError(null);
    setIsUploading(kind);
    try {
      const result = await uploadOfficeDataSource(file, kind === "rag" ? "workspace-rag" : "workspace-background");
      if (kind === "rag") setRagFiles((cur) => [result, ...cur]);
      else setBackgroundFiles((cur) => [result, ...cur]);
      setMessages((cur) => [
        ...cur,
        {
          id: makeId("system"),
          role: "system",
          content: `${kind === "rag" ? "RAG资料" : "背景资料"}已上传：${result.filename} · dataSourceId ${result.dataSourceId}`,
        },
      ]);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setWorkspaceError(text);
    } finally {
      setIsUploading(null);
    }
  };

  const sendMessage = async () => {
    const message = input.trim();
    if (!message || isChatting) return;
    setWorkspaceError(null);
    setInput("");
    setIsChatting(true);
    const userMessage: Message = { id: makeId("user"), role: "user", content: message };
    setMessages((cur) => [...cur, userMessage]);
    try {
      const result = await sendConstrainedChatMessage({
        conversationId: selectedTask.id,
        rulesetId: learnJob?.result?.ruleset_id ?? selectedPack.id,
        message,
        systemPrompt: `当前规则包：${selectedPack.name}。RAG资料：${uploadedNames.join("、") || "未上传"}`,
        ragFiles: uploadedNames,
      });
      setMessages((cur) => [
        ...cur,
        {
          id: result.messageId || makeId("assistant"),
          role: "assistant",
          content: result.content || result.reply || "后端已完成受约束回答，但没有返回正文。",
          result,
        },
      ]);
      if (!tasks.some((task) => task.name === selectedTask.name && task.id !== selectedTask.id)) {
        setTasks((cur) =>
          cur.map((task) =>
            task.id === selectedTask.id
              ? { ...task, time: "刚刚", summary: result.flagged_numbers?.length ? `${result.flagged_numbers.length} 待核实` : task.summary }
              : task
          )
        );
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setWorkspaceError(text);
      setMessages((cur) => [
        ...cur,
        { id: makeId("system"), role: "system", content: `受约束问答失败：${text}` },
      ]);
    } finally {
      setIsChatting(false);
    }
  };

  const addManualRulePack = (name: string, rules: string[]) => {
    const pack: RulePack = {
      id: makeId("manual-pack"),
      name,
      kind: "custom",
      version: "v1.0",
      icon: "custom",
      rules,
    };
    setRulePacks((cur) => [pack, ...cur]);
    setSelectedPackId(pack.id);
    setShowManualModal(false);
  };

  const addLearnedRulePack = (name: string, rules: string[]) => {
    const pack: RulePack = {
      id: makeId("learn-pack"),
      name,
      kind: "custom",
      version: "v1.0",
      icon: "custom",
      rules,
    };
    setRulePacks((cur) => [pack, ...cur]);
    setSelectedPackId(pack.id);
    setShowLearnModal(false);
  };

  return (
    <div className="workspace-page">
      <div className="workspace-ambient" aria-hidden />
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <span>
            <Shield size={17} />
          </span>
          <strong>NetNomos Forge</strong>
        </div>
        <button className="workspace-new-task" type="button" onClick={() => setInput("请帮我核查新上传资料，并生成规则命中摘要。")}>
          <Plus size={15} />
          新建核查任务
        </button>
        <SidebarLabel>最近任务</SidebarLabel>
        <div className="workspace-task-list">
          {tasks.map((task) => (
            <button
              className={`workspace-task${task.id === selectedTaskId ? " is-active" : ""}`}
              key={task.id}
              onClick={() => setSelectedTaskId(task.id)}
              type="button"
            >
              <span>{task.name}</span>
              <small className={task.status === "ok" ? "is-ok" : ""}>
                {task.status === "ok" ? "✓" : "✕"} {task.summary}
              </small>
              <em>{task.time}</em>
            </button>
          ))}
        </div>
        <SidebarLabel>规则包</SidebarLabel>
        <div className="workspace-pack-list">
          {rulePacks.map((pack) => (
            <button
              className={`workspace-pack${pack.id === selectedPackId ? " is-active" : ""}`}
              key={pack.id}
              onClick={() => setSelectedPackId(pack.id)}
              type="button"
            >
              <PackIcon icon={pack.icon} />
              <span>{pack.name}</span>
              <em>{pack.kind === "custom" ? "自定义" : `标准·${pack.version}`}</em>
            </button>
          ))}
        </div>
        <div className="workspace-sidebar-actions">
          <button type="button" onClick={() => setShowLearnModal(true)}>
            <Sparkles size={14} />
            学习规则包
          </button>
          <button type="button" onClick={() => setShowManualModal(true)}>
            <Plus size={14} />
            新增规则
          </button>
        </div>
      </aside>

      <section className="workspace-chat-shell">
        <header className="workspace-chat-top">
          <div className="workspace-chat-title">
            <span className="workspace-live-dot" />
            <strong>{selectedTask.name}</strong>
            <em>· {selectedPack.name} {selectedPack.version}</em>
            {learnJob && <small>job {learnJob.jobId.slice(0, 8)} · {learnJob.status}</small>}
          </div>
          <div className="workspace-demo-controls">
            <label>
              <span>演示场景</span>
              <select value={demoScenario} onChange={(event) => setDemoScenario(event.target.value as WorkspaceDemoScenario)} disabled={isAutoDemo}>
                <option value="finance">财务场景</option>
                <option value="network">网络场景</option>
              </select>
            </label>
            <button type="button" onClick={() => void runWorkspaceDemo()} disabled={isAutoDemo}>
              {isAutoDemo ? <Loader2 size={13} /> : <Sparkles size={13} />}
              {isAutoDemo ? "演示中" : "一键演示"}
            </button>
          </div>
        </header>

        <div className="workspace-messages">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} selectedPack={selectedPack} />
          ))}
          {demoAgents.length > 0 && <WorkspaceAgentRun agents={demoAgents} />}
          {(isChatting || isAutoDemo) && (
            <div className="workspace-thinking">
              <Loader2 size={16} />
              {isAutoDemo ? "多 Agent 正在自动执行..." : "正在调用受约束问答..."}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <footer className="workspace-composer">
          {workspaceError && (
            <div className="workspace-error">
              <X size={13} />
              {workspaceError}
            </div>
          )}
          <div className="workspace-context-row">
            <label>
              <span>规则集</span>
              <select value={selectedPackId} onChange={(event) => setSelectedPackId(event.target.value)}>
                {rulePacks.map((pack) => (
                  <option key={pack.id} value={pack.id}>
                    {pack.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" onClick={() => ragInputRef.current?.click()}>
              <Paperclip size={13} />
              {isUploading === "rag" ? "上传中..." : `RAG资料 ${ragFiles.length}`}
            </button>
            <button type="button" onClick={() => backgroundInputRef.current?.click()}>
              <FileText size={13} />
              {isUploading === "background" ? "上传中..." : `背景资料 ${backgroundFiles.length}`}
            </button>
            <button type="button" onClick={startLearning} disabled={isLearning}>
              {isLearning ? <Loader2 size={13} /> : <Sparkles size={13} />}
              {isLearning ? "学习中" : "学习规则"}
            </button>
          </div>
          <input
            ref={ragInputRef}
            hidden
            type="file"
            accept=".csv,.json,.txt,.md,.pdf,.doc,.docx"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.currentTarget.value = "";
              if (file) void uploadFile(file, "rag");
            }}
          />
          <input
            ref={backgroundInputRef}
            hidden
            type="file"
            accept=".csv,.json,.txt,.md,.pdf,.doc,.docx"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.currentTarget.value = "";
              if (file) void uploadFile(file, "background");
            }}
          />
          <div className="workspace-file-row">
            {[...ragFiles.map((file) => ({ ...file, kind: "RAG" })), ...backgroundFiles.map((file) => ({ ...file, kind: "背景" }))].map((file) => (
              <span key={`${file.kind}-${file.dataSourceId}`}>{file.kind}: {file.filename}</span>
            ))}
          </div>
          <div className="workspace-input-row">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
              placeholder="选择规则集 + RAG资料 + 背景资料后提问..."
            />
            <button type="button" onClick={sendMessage} disabled={!input.trim() || isChatting}>
              <ArrowUp size={17} />
            </button>
          </div>
        </footer>
      </section>

      {showLearnModal && (
        <RulePackLearnModal
          onClose={() => setShowLearnModal(false)}
          onCreate={addLearnedRulePack}
        />
      )}
      {showManualModal && (
        <ManualRuleModal
          onClose={() => setShowManualModal(false)}
          onCreate={addManualRulePack}
        />
      )}
    </div>
  );
}

function SidebarLabel({ children }: { children: string }) {
  return <div className="workspace-side-label">{children}</div>;
}

function PackIcon({ icon }: { icon: RulePack["icon"] }) {
  const props = { size: 14 };
  if (icon === "finance") return <Receipt {...props} />;
  if (icon === "supply") return <Truck {...props} />;
  if (icon === "sensor") return <Cpu {...props} />;
  return <Star {...props} />;
}

function WorkspaceAgentRun({ agents }: { agents: DemoAgent[] }) {
  return (
    <div className="workspace-agent-run">
      <header>
        <span>
          <Sparkles size={13} />
        </span>
        <strong>多 Agent 执行链路</strong>
        <em>真实后端 workflow 事件映射到前端 Agent 分工</em>
      </header>
      <div>
        {agents.map((agent) => (
          <article className={`workspace-agent-card is-${agent.status}`} key={agent.id}>
            <span>{agent.status === "done" ? <Check size={13} /> : agent.status === "running" ? <Loader2 size={13} /> : <Circle size={13} />}</span>
            <div>
              <strong>{agent.name}</strong>
              <small>{agent.output || agent.role}</small>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function ChatMessage({ message, selectedPack }: { message: Message; selectedPack: RulePack }) {
  if (message.role === "system") {
    return <div className="workspace-system-msg">{message.content}</div>;
  }
  if (message.role === "user") {
    return (
      <div className="workspace-user-msg">
        <p>{message.content}</p>
      </div>
    );
  }
  const isSeed = message.id === "seed-assistant";
  return (
    <div className="workspace-assistant-msg">
      <div className="workspace-assistant-id">
        <span>
          <Shield size={12} />
        </span>
        <strong>NetNomos Forge</strong>
        <em>· {selectedPack.name}</em>
      </div>
      {isSeed ? (
        <article className="workspace-result-card">
          <p>
            已对照 <strong>30 条规则</strong> 完成核查：
          </p>
          {RULE_RESULTS.map((item) => (
            <div className={item.pass ? "is-pass" : "is-fail"} key={item.id}>
              <strong>{item.id}</strong>
              <span>{item.pass ? "✓" : "✕"} {item.text}</span>
            </div>
          ))}
        </article>
      ) : (
        <article className="workspace-result-card">
          <p>{message.content}</p>
          {message.result?.checks?.length ? (
            <ul>
              {message.result.checks.map((check) => (
                <li key={check}>{check}</li>
              ))}
            </ul>
          ) : null}
          {message.result?.citations?.length ? (
            <small>引用：{message.result.citations.join("、")}</small>
          ) : null}
        </article>
      )}
    </div>
  );
}

function RulePackLearnModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string, rules: string[]) => void;
}) {
  const [step, setStep] = useState<LearnStep>(1);
  const [rules, setRules] = useState(LEARNED_RULES);
  const [packName, setPackName] = useState("我的报销单规则");
  const checked = rules.filter((rule) => rule.checked);

  return (
    <div className="workspace-modal-backdrop" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="workspace-modal">
        <header>
          <div className="workspace-step-pills">
            {[
              [1, "上传数据"],
              [2, "自动推断"],
              [3, "确认规则"],
              [4, "生成完成"],
            ].map(([id, label]) => (
              <button
                className={step === id ? "is-active" : step > Number(id) ? "is-done" : ""}
                key={id}
                onClick={() => Number(id) < step && setStep(id as LearnStep)}
                type="button"
              >
                {step > Number(id) && <Check size={10} />}
                {label}
              </button>
            ))}
          </div>
          <button className="workspace-close" onClick={onClose} type="button">
            <X size={16} />
          </button>
        </header>
        <main>
          {step === 1 && <LearnUploadStep onNext={() => setStep(2)} />}
          {step === 2 && <LearnInferStep onNext={() => setStep(3)} />}
          {step === 3 && (
            <LearnConfirmStep
              rules={rules}
              checkedCount={checked.length}
              onToggle={(id) => setRules((cur) => cur.map((rule) => rule.id === id ? { ...rule, checked: !rule.checked } : rule))}
              onNext={() => setStep(4)}
            />
          )}
          {step === 4 && (
            <LearnDoneStep
              checkedCount={checked.length}
              packName={packName}
              onPackNameChange={setPackName}
              onCreate={() => onCreate(packName.trim() || "我的规则包", checked.map((rule) => rule.text))}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function LearnUploadStep({ onNext }: { onNext: () => void }) {
  return (
    <section className="workspace-learn-step">
      <h2>上传你认为「正确 / 无问题」的历史数据</h2>
      <p>系统会从这些样本中提取共同遵守的逻辑约束，作为你的专属规则包。</p>
      <div className="workspace-dropzone">
        <Upload size={24} />
        <strong>拖拽文件到此处，或点击上传</strong>
        <span>支持 CSV / JSON，建议 ≥ 50 条样本</span>
      </div>
      <div className="workspace-uploaded-file">
        <FileText size={15} />
        <span>报销单_2025年度_已审核通过.csv</span>
        <strong>312 条</strong>
      </div>
      <small>
        <Info size={12} />
        不确定怎么准备数据？下载示例文件
      </small>
      <button className="workspace-grad-btn" onClick={onNext} type="button">开始学习规则 →</button>
    </section>
  );
}

function LearnInferStep({ onNext }: { onNext: () => void }) {
  return (
    <section className="workspace-learn-step">
      <h2>正在从 312 条样本中提取规则</h2>
      <p>这个过程通常需要几分钟，你可以先看看下面的进展。</p>
      <div className="workspace-stage-list">
        <StageCard state="done" title="规则学习" desc="已从样本中提取出 18 条候选逻辑约束" />
        <StageCard state="loading" title="语义过滤" desc="正在剔除偶然相关、缺乏业务意义的规则..." />
        <StageCard state="pending" title="生成规则包" desc="整理为可执行的 SMT 约束配置" />
      </div>
      <button className="workspace-grad-btn" onClick={onNext} type="button">查看推断出的规则 →</button>
    </section>
  );
}

function StageCard({ state, title, desc }: { state: "done" | "loading" | "pending"; title: string; desc: string }) {
  return (
    <div className={`workspace-stage-card is-${state}`}>
      {state === "done" && <CheckCircle2 size={18} />}
      {state === "loading" && <Loader2 size={18} />}
      {state === "pending" && <Circle size={18} />}
      <span>
        <strong>{title}</strong>
        <small>{desc}</small>
      </span>
    </div>
  );
}

function LearnConfirmStep({
  rules,
  checkedCount,
  onToggle,
  onNext,
}: {
  rules: typeof LEARNED_RULES;
  checkedCount: number;
  onToggle: (id: number) => void;
  onNext: () => void;
}) {
  return (
    <section className="workspace-learn-step">
      <h2>从数据中学到了 12 条规则</h2>
      <p>逐条确认是否采纳，可勾选 / 取消，或点击调整阈值。</p>
      <div className="workspace-learn-rules">
        {rules.map((rule) => (
          <button className={rule.checked ? "is-checked" : ""} key={rule.id} onClick={() => onToggle(rule.id)} type="button">
            {rule.checked ? <CheckSquare size={16} /> : <Square size={16} />}
            <span>
              <strong>{rule.text}</strong>
              <small>{rule.basis}</small>
            </span>
            {rule.high && <em>高</em>}
            <Pencil size={13} />
          </button>
        ))}
      </div>
      <small>已选中 <b>{checkedCount}</b> / 12 条 · 其余规则可展开查看</small>
      <button className="workspace-grad-btn" onClick={onNext} type="button">确认并生成规则包 →</button>
    </section>
  );
}

function LearnDoneStep({
  checkedCount,
  packName,
  onPackNameChange,
  onCreate,
}: {
  checkedCount: number;
  packName: string;
  onPackNameChange: (value: string) => void;
  onCreate: () => void;
}) {
  return (
    <section className="workspace-learn-step is-done">
      <span className="workspace-success-mark">
        <Check size={30} />
      </span>
      <h2>规则包已生成</h2>
      <p>已采纳 <b>{checkedCount}</b> 条规则，随时可在“我的规则包”中查看、编辑或重新学习。</p>
      <label>
        规则包名称
        <input value={packName} onChange={(event) => onPackNameChange(event.target.value)} />
      </label>
      <div className="workspace-pack-preview">
        <Star size={14} />
        <strong>{packName}</strong>
        <span>自定义 · {checkedCount} 条规则 · v1.0</span>
      </div>
      <button className="workspace-grad-btn" onClick={onCreate} type="button">用这个规则包核查新数据 →</button>
    </section>
  );
}

function ManualRuleModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string, rules: string[]) => void;
}) {
  const [name, setName] = useState("人工录入规则包");
  const [rawRules, setRawRules] = useState("R01：报销金额必须大于 0\nR02：审批人不能为空");
  const rules = rawRules.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  return (
    <div className="workspace-modal-backdrop" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="workspace-modal is-manual">
        <header>
          <div>
            <strong>新增规则（人工录入）</strong>
            <small>第一版保存在前端状态中，不做后端持久化。</small>
          </div>
          <button className="workspace-close" onClick={onClose} type="button">
            <X size={16} />
          </button>
        </header>
        <main className="workspace-manual-form">
          <label>
            规则包名称
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            规则内容
            <textarea value={rawRules} onChange={(event) => setRawRules(event.target.value)} rows={8} />
          </label>
          <div className="workspace-manual-preview">
            <strong>预览</strong>
            {rules.map((rule) => <span key={rule}>{rule}</span>)}
          </div>
          <button className="workspace-grad-btn" disabled={!name.trim() || rules.length === 0} onClick={() => onCreate(name, rules)} type="button">
            保存为自定义规则包
          </button>
        </main>
      </div>
    </div>
  );
}
