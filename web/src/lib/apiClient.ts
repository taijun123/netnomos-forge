import { API } from "../types/api";
import type { DualReport, Rule, RuleCard, Scenario, Violation, WorkflowEvent } from "../types/api";
import type { MockSequenceId } from "../mock/sse";
import { logger } from "./logger";

export interface WorkflowJobResult {
  ruleset_id?: string;
  dual?: DualReport | null;
  cards?: RuleCard[];
  rules?: Rule[];
  violations?: Violation[];
  request?: WorkflowStartPayload;
  requestParams?: WorkflowStartPayload;
}

export interface WorkflowJobStatus {
  jobId: string;
  job_id?: string;
  scenario: Scenario;
  sequence: string;
  status: "pending" | "running" | "done" | "failed";
  createdAt?: number;
  created_at?: number;
  events: WorkflowEvent[];
  result: WorkflowJobResult | null;
  error?: string | null;
}

export interface DataSourceUploadResult {
  dataSourceId: string;
  filename: string;
  path: string;
  size: number;
}

export interface WorkflowStartPayload {
  dataSourceId?: string;
  trainingDataSourceId?: string;
  validationDataSourceId?: string;
  question?: string;
  reportPrompt?: string;
}

export interface UploadedDataSourceRecord extends DataSourceUploadResult {
  scenario: Scenario;
  note?: string;
  uploadedAt: number;
}

export interface RuleSetUploadResult {
  rulesetId: string;
  ruleCount: number;
}

export interface ConstrainedChatResult {
  reply?: string;
  content?: string;
  messageId?: string;
  constrained?: boolean;
  matchedRules?: string[];
  citations?: string[];
  checks?: string[];
  flagged_numbers?: string[];
  backend?: string;
}

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

const SEQUENCE_SCENARIO: Record<MockSequenceId, Scenario> = {
  "learn-network": "network_cidds",
  "validate-network": "network_cidds",
  "report-network": "network_cidds",
  "learn-finance": "finance_v1",
  "validate-finance": "finance_v1",
  "report-finance": "finance_v1",
};

const latestDataSources = new Map<Scenario, UploadedDataSourceRecord>();

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function workflowEventsUrl(jobId: string): string {
  return apiUrl(`${API.WORKFLOW_EVENTS}?job_id=${encodeURIComponent(jobId)}`);
}

export function workflowEventsBySequenceUrl(sequence: MockSequenceId): string {
  return apiUrl(`${API.WORKFLOW_EVENTS}?sequence=${encodeURIComponent(sequence)}`);
}

export function scenarioForSequence(sequence: MockSequenceId): Scenario {
  return SEQUENCE_SCENARIO[sequence];
}

export function getLatestDataSource(scenario: Scenario): UploadedDataSourceRecord | null {
  return latestDataSources.get(scenario) ?? null;
}

export function workflowPayloadFromLatestDataSource(
  sequence: MockSequenceId,
  purpose: "training" | "validation" = "validation"
): WorkflowStartPayload {
  const dataSource = getLatestDataSource(scenarioForSequence(sequence));
  if (!dataSource) return {};
  return purpose === "training"
    ? {
        dataSourceId: dataSource.dataSourceId,
        trainingDataSourceId: dataSource.dataSourceId,
      }
    : {
        dataSourceId: dataSource.dataSourceId,
        validationDataSourceId: dataSource.dataSourceId,
      };
}

async function readJson<T>(res: Response): Promise<T> {
  const startTime = performance.now();
  const url = res.url;

  try {
    const text = await res.text();
    const duration = performance.now() - startTime;

    if (!res.ok) {
      const detail = text ? `: ${text.slice(0, 180)}` : "";
      const error = new Error(`API ${res.status}${detail}`);
      logger.apiError('UNKNOWN', url || res.url, error);
      throw error;
    }

    const data = (text ? JSON.parse(text) : {}) as T;
    logger.apiResponse('UNKNOWN', url || res.url, res.status, Math.round(duration));
    return data;
  } catch (err) {
    if (err instanceof Error) {
      logger.apiError('UNKNOWN', url || res.url, err);
    }
    throw err;
  }
}

export async function startWorkflowJob(
  sequence: MockSequenceId,
  requestPayload: WorkflowStartPayload = {}
): Promise<string> {
  const res = await fetch(apiUrl(API.RULESETS_LEARN), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario: SEQUENCE_SCENARIO[sequence],
      sequence,
      ...compactWorkflowPayload(requestPayload),
    }),
  });
  const responsePayload = await readJson<{ jobId?: string; job_id?: string }>(res);
  const jobId = responsePayload.jobId ?? responsePayload.job_id;
  if (!jobId) throw new Error("start workflow returned no job id");
  return jobId;
}

export async function uploadDataSource(
  scenario: Scenario,
  file: File,
  note = ""
): Promise<DataSourceUploadResult> {
  const form = new FormData();
  form.append("scenario", scenario);
  form.append("note", note);
  form.append("file", file, file.name);
  const res = await fetch(apiUrl(API.DATA_SOURCES), {
    method: "POST",
    body: form,
  });
  const raw = await readJson<Partial<DataSourceUploadResult>>(res);
  const dataSourceId = raw.dataSourceId;
  if (!dataSourceId) throw new Error("upload data source returned no dataSourceId");
  const result: DataSourceUploadResult = {
    dataSourceId,
    filename: raw.filename || file.name,
    path: raw.path || "",
    size: raw.size ?? file.size,
  };
  latestDataSources.set(scenario, {
    ...result,
    scenario,
    note,
    uploadedAt: Date.now(),
  });
  return result;
}

export async function uploadOfficeRuleset(): Promise<RuleSetUploadResult> {
  const res = await fetch(apiUrl(API.RULESETS_UPLOAD), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario: "office_demo" satisfies Scenario }),
  });
  const raw = await readJson<Partial<RuleSetUploadResult>>(res);
  const rulesetId = raw.rulesetId;
  if (!rulesetId) throw new Error("upload ruleset returned no rulesetId");
  return { rulesetId, ruleCount: raw.ruleCount ?? 0 };
}

export async function uploadOfficeDataSource(
  file: File,
  note = "office demo data source"
): Promise<DataSourceUploadResult> {
  return uploadDataSource("office_demo", file, note);
}

export async function registerOfficeDemoDataSource(
  filename = "demo-pcap-csv-source.csv",
  note = "office demo registered data source"
): Promise<DataSourceUploadResult> {
  const res = await fetch(apiUrl(API.DATA_SOURCES), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario: "office_demo" satisfies Scenario, filename, note }),
  });
  const raw = await readJson<Partial<DataSourceUploadResult>>(res);
  const dataSourceId = raw.dataSourceId;
  if (!dataSourceId) throw new Error("register data source returned no dataSourceId");
  return {
    dataSourceId,
    filename: raw.filename || filename,
    path: raw.path || "",
    size: raw.size ?? 0,
  };
}

export async function startOfficeWorkflow(
  requestPayload: WorkflowStartPayload = {}
): Promise<string> {
  const res = await fetch(apiUrl(API.RULESETS_LEARN), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario: "office_demo" satisfies Scenario,
      sequence: "office-demo",
      ...compactWorkflowPayload(requestPayload),
    }),
  });
  const responsePayload = await readJson<{ jobId?: string; job_id?: string }>(res);
  const jobId = responsePayload.jobId ?? responsePayload.job_id;
  if (!jobId) throw new Error("start office workflow returned no job id");
  return jobId;
}

export async function sendConstrainedChatMessage(payload: {
  conversationId: string;
  rulesetId?: string;
  message: string;
  systemPrompt?: string;
  ragFiles?: string[];
}): Promise<ConstrainedChatResult> {
  const res = await fetch(apiUrl(API.CHAT_CONSTRAINED), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario: "office_demo" satisfies Scenario,
      conversationId: payload.conversationId,
      rulesetId: payload.rulesetId,
      message: payload.message,
      systemPrompt: payload.systemPrompt,
      ragFiles: payload.ragFiles ?? [],
    }),
  });
  return readJson<ConstrainedChatResult>(res);
}

export async function fetchWorkflowJob(jobId: string): Promise<WorkflowJobStatus> {
  const res = await fetch(apiUrl(`/api/jobs/${encodeURIComponent(jobId)}`));
  return normalizeJob(await readJson<WorkflowJobStatus>(res));
}

export async function waitForWorkflowJob(
  jobId: string,
  options: { attempts?: number; delayMs?: number } = {}
): Promise<WorkflowJobStatus> {
  const attempts = options.attempts ?? 6;
  const delayMs = options.delayMs ?? 350;
  let lastJob: WorkflowJobStatus | null = null;
  for (let i = 0; i < attempts; i += 1) {
    const job = await fetchWorkflowJob(jobId);
    lastJob = job;
    if (job.status === "done" || job.status === "failed") return job;
    await new Promise((resolve) => globalThis.setTimeout(resolve, delayMs));
  }
  if (lastJob) return lastJob;
  throw new Error("workflow job result was not available");
}

function normalizeJob(raw: WorkflowJobStatus): WorkflowJobStatus {
  return {
    ...raw,
    jobId: raw.jobId ?? raw.job_id ?? "",
    result: raw.result ?? null,
    events: normalizeEvents(raw.events),
  };
}

function normalizeEvents(events: WorkflowEvent[] | undefined): WorkflowEvent[] {
  return Array.isArray(events) ? events : [];
}

function compactWorkflowPayload(payload: WorkflowStartPayload): WorkflowStartPayload {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined && value !== "")
  ) as WorkflowStartPayload;
}
