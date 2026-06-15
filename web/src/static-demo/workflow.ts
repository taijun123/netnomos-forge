import type {
  ConstrainedChatResult,
  DataSourceUploadResult,
  RuleSetUploadResult,
  WorkflowJobResult,
  WorkflowJobStatus,
  WorkflowStartPayload,
} from "../lib/apiClient";
import type { WorkflowSubscription } from "../lib/events";
import { DUAL_MOCK, LEARN_MOCK, VALIDATE_MOCK } from "../demo/demoMocks";
import { mockWorkflowStream, type MockSequenceId } from "../mock/sse";
import type { Scenario, WorkflowEvent } from "../types/api";

type StaticJobHandle = { close: () => void };

type StaticSequence = MockSequenceId | "office-demo";

const SEQUENCE_SCENARIO: Record<MockSequenceId, Scenario> = {
  "learn-network": "network_cidds",
  "validate-network": "network_cidds",
  "report-network": "network_cidds",
  "learn-finance": "finance_v1",
  "validate-finance": "finance_v1",
  "report-finance": "finance_v1",
};

const OFFICE_EVENTS: Array<Omit<WorkflowEvent, "id" | "time">> = [
  { agent: "A", stage: "office_demo", status: "running", description: "静态演示：主管 A 接入规则集并编排 office_demo workflow。" },
  { agent: "B", stage: "upload", status: "done", description: "静态演示：快递员 B 登记示例数据源，不保存真实文件。" },
  { agent: "C", stage: "learn", status: "running", description: "静态演示：员工 C 复刻规则学习流程，读取内置样例规则。" },
  { agent: "D", stage: "validate", status: "blocked", description: "静态演示：员工 D 命中样例违规并生成规则卡。" },
  { agent: "E", stage: "report", status: "running", description: "静态演示：员工 E 生成 A/B 双轨报告样例。" },
  { agent: "F", stage: "chat", status: "done", description: "静态演示：产品经理 F 汇总受约束问答与引用。" },
];

const jobs = new Map<string, WorkflowJobStatus>();
const handles = new Map<string, StaticJobHandle>();
let jobCounter = 0;
let dataSourceCounter = 0;

function nextJobId(): string {
  jobCounter += 1;
  return `static-job-${Date.now().toString(36)}-${jobCounter.toString(36)}`;
}

function nextDataSourceId(): string {
  dataSourceCounter += 1;
  return `static-ds-${Date.now().toString(36)}-${dataSourceCounter.toString(36)}`;
}

function isoNow(): string {
  return new Date().toISOString().slice(0, 19);
}

function eventId(jobId: string, index: number): string {
  return `${jobId}-ev-${String(index).padStart(2, "0")}`;
}

function cloneJob(job: WorkflowJobStatus): WorkflowJobStatus {
  return {
    ...job,
    events: [...job.events],
    result: job.result ? { ...job.result } : null,
  };
}

function demoKeyFor(sequence: MockSequenceId): "network" | "finance" {
  return sequence.endsWith("network") ? "network" : "finance";
}

function resultFor(sequence: StaticSequence, payload: WorkflowStartPayload): WorkflowJobResult {
  if (sequence === "office-demo") {
    return withDataSourceRefs(DUAL_MOCK.finance, payload);
  }
  const key = demoKeyFor(sequence);
  if (sequence.startsWith("learn-")) return withDataSourceRefs(LEARN_MOCK[key], payload);
  if (sequence.startsWith("validate-")) return withDataSourceRefs(VALIDATE_MOCK[key], payload);
  return withDataSourceRefs(DUAL_MOCK[key], payload);
}

function withDataSourceRefs(base: WorkflowJobResult, payload: WorkflowStartPayload): WorkflowJobResult {
  const dataSourceId = payload.validationDataSourceId ?? payload.dataSourceId ?? payload.trainingDataSourceId;
  return {
    ...base,
    request: payload,
    requestParams: payload,
    dataSourceId,
    validationDataSourceId: payload.validationDataSourceId ?? dataSourceId,
    trainingDataSourceId: payload.trainingDataSourceId,
    data_source: dataSourceId
      ? {
          primary: { id: dataSourceId, filename: "static-demo-source.csv" },
          validation: { id: dataSourceId, filename: "static-demo-validation.csv" },
        }
      : undefined,
  };
}

function createJob(
  sequence: StaticSequence,
  scenario: Scenario,
  requestPayload: WorkflowStartPayload,
  sub?: WorkflowSubscription
): string {
  const jobId = nextJobId();
  const job: WorkflowJobStatus = {
    jobId,
    job_id: jobId,
    scenario,
    sequence,
    status: "running",
    createdAt: Date.now(),
    created_at: Date.now(),
    request: requestPayload,
    requestParams: requestPayload,
    events: [],
    result: null,
    error: null,
  };
  jobs.set(jobId, job);
  sub?.onMode?.("mock");
  sub?.onJobStart?.(jobId);

  const finish = () => {
    const current = jobs.get(jobId);
    if (!current || current.status === "done") return;
    current.status = "done";
    current.result = resultFor(sequence, requestPayload);
    jobs.set(jobId, current);
    sub?.onMode?.("mock");
    sub?.onDone?.(cloneJob(current));
  };

  const pushEvent = (event: WorkflowEvent) => {
    const current = jobs.get(jobId);
    if (!current) return;
    current.events = [...current.events, event];
    current.status = "running";
    jobs.set(jobId, current);
    sub?.onMode?.("mock");
    sub?.onEvent(event);
  };

  if (sequence === "office-demo") {
    let index = 0;
    const timer = window.setInterval(() => {
      const spec = OFFICE_EVENTS[index];
      if (!spec) {
        window.clearInterval(timer);
        finish();
        return;
      }
      pushEvent({ ...spec, id: eventId(jobId, index + 1), time: isoNow() });
      index += 1;
    }, 650);
    handles.set(jobId, { close: () => window.clearInterval(timer) });
    return jobId;
  }

  const handle = mockWorkflowStream(sequence, {
    onEvent: pushEvent,
    onDone: finish,
  });
  handles.set(jobId, handle);
  return jobId;
}

export function staticStartWorkflowJob(
  sequence: MockSequenceId,
  requestPayload: WorkflowStartPayload = {}
): Promise<string> {
  return Promise.resolve(createJob(sequence, SEQUENCE_SCENARIO[sequence], requestPayload));
}

export function staticStartOfficeWorkflow(requestPayload: WorkflowStartPayload = {}): Promise<string> {
  return Promise.resolve(createJob("office-demo", "office_demo", requestPayload));
}

export function staticFetchWorkflowJob(jobId: string): Promise<WorkflowJobStatus> {
  const job = jobs.get(jobId);
  if (!job) return Promise.reject(new Error(`static workflow job not found: ${jobId}`));
  return Promise.resolve(cloneJob(job));
}

export async function staticWaitForWorkflowJob(
  jobId: string,
  options: { attempts?: number; delayMs?: number } = {}
): Promise<WorkflowJobStatus> {
  const attempts = options.attempts ?? 20;
  const delayMs = options.delayMs ?? 250;
  let lastJob: WorkflowJobStatus | null = null;
  for (let i = 0; i < attempts; i += 1) {
    const job = await staticFetchWorkflowJob(jobId);
    lastJob = job;
    if (job.status === "done" || job.status === "failed") return job;
    await new Promise((resolve) => window.setTimeout(resolve, delayMs));
  }
  if (lastJob) return lastJob;
  throw new Error("static workflow job result was not available");
}

export function subscribeStaticWorkflow(
  sequence: MockSequenceId,
  sub: WorkflowSubscription,
  requestPayload: WorkflowStartPayload = {}
): { close: () => void } {
  const jobId = createJob(sequence, SEQUENCE_SCENARIO[sequence], requestPayload, sub);
  return {
    close: () => {
      handles.get(jobId)?.close();
      handles.delete(jobId);
    },
  };
}

export function staticUploadDataSource(
  scenario: Scenario,
  file: File,
  note = ""
): Promise<DataSourceUploadResult> {
  const dataSourceId = nextDataSourceId();
  return Promise.resolve({
    dataSourceId,
    filename: file.name,
    path: `static-demo://${scenario}/${encodeURIComponent(file.name)}${note ? `?note=${encodeURIComponent(note)}` : ""}`,
    size: file.size,
  });
}

export function staticRegisterDataSource(
  scenario: Scenario,
  filename: string,
  note = ""
): Promise<DataSourceUploadResult> {
  const dataSourceId = nextDataSourceId();
  return Promise.resolve({
    dataSourceId,
    filename,
    path: `static-demo://${scenario}/${encodeURIComponent(filename)}${note ? `?note=${encodeURIComponent(note)}` : ""}`,
    size: 0,
  });
}

export function staticUploadOfficeRuleset(): Promise<RuleSetUploadResult> {
  return Promise.resolve({
    rulesetId: "static-ruleset-office-demo",
    ruleCount: 5,
  });
}

export function staticSendConstrainedChatMessage(payload: {
  conversationId: string;
  scenario?: Scenario;
  rulesetId?: string;
  message: string;
  systemPrompt?: string;
  ragFiles?: string[];
  dataSourceId?: string;
  validationDataSourceId?: string;
}): Promise<ConstrainedChatResult> {
  const scenario = payload.scenario ?? "office_demo";
  const reply =
    scenario === "network_cidds"
      ? "静态演示回答：该 NetFlow 样例会先检查 UDP 标志位、Bytes/Packets 物理边界和 DNS 端口身份。命中规则时应优先输出规则依据，再给出需要复核的字段。"
      : scenario === "finance_v1"
        ? "静态演示回答：该财务样例会先核对毛利、资产负债配平、进销存勾稽和现金跨期滚动。报告数值必须引用规则卡，不能直接照抄待审错误数。"
        : "静态演示回答：办公室流程中，A 负责编排，B 登记数据，C/D 学习与核查规则，E 生成双轨报告，F 只基于规则集和已登记知识库回答。";

  return Promise.resolve({
    reply,
    content: reply,
    messageId: `static-chat-${Date.now().toString(36)}`,
    constrained: true,
    matchedRules: [payload.rulesetId ?? "static-ruleset-office-demo", `${scenario}:static-rule-card`],
    citations: ["NetNomos Forge 静态规则卡样例", "GitHub Pages static adapter"],
    checks: ["已使用静态规则约束", "未连接后端", "未持久化用户文件"],
    flagged_numbers: [],
    backend: "static-demo",
    dataSourceId: payload.validationDataSourceId ?? payload.dataSourceId,
  });
}

export function staticHealthDataUrl(): string {
  const body = encodeURIComponent(JSON.stringify({ status: "static-demo", jobs: jobs.size }));
  return `data:application/json,${body}`;
}
