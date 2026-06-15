import { API } from "../types/api";
import type { DualReport, Rule, RuleCard, Scenario, Violation, WorkflowEvent } from "../types/api";
import type { MockSequenceId } from "../mock/sse";
import { logger, wasLogged } from "./logger";
import { STATIC_DEMO } from "../static-demo/config";
import {
  staticFetchWorkflowJob,
  staticHealthDataUrl,
  staticRegisterDataSource,
  staticSendConstrainedChatMessage,
  staticStartOfficeWorkflow,
  staticStartWorkflowJob,
  staticUploadDataSource,
  staticUploadOfficeRuleset,
  staticWaitForWorkflowJob,
} from "../static-demo/workflow";

export interface WorkflowJobResult {
  ruleset_id?: string;
  dual?: DualReport | null;
  cards?: RuleCard[];
  rules?: Rule[];
  violations?: Violation[];
  request?: WorkflowStartPayload;
  requestParams?: WorkflowStartPayload;
  dataSourceId?: string;
  trainingDataSourceId?: string;
  validationDataSourceId?: string;
  data_source?: WorkflowResultDataSources;
  dataSource?: WorkflowResultDataSources;
}

export interface WorkflowJobStatus {
  jobId: string;
  job_id?: string;
  scenario: Scenario;
  sequence: string;
  status: "pending" | "running" | "done" | "failed";
  createdAt?: number;
  created_at?: number;
  request?: WorkflowStartPayload;
  requestParams?: WorkflowStartPayload;
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

export interface WorkflowResultDataSourceRef {
  id?: string;
  dataSourceId?: string;
  filename?: string;
  name?: string;
}

export interface WorkflowResultDataSources {
  training?: WorkflowResultDataSourceRef | string | null;
  validation?: WorkflowResultDataSourceRef | string | null;
  primary?: WorkflowResultDataSourceRef | string | null;
  [key: string]: WorkflowResultDataSourceRef | string | null | undefined;
}

export interface WorkflowDataSourceUsage {
  request: Pick<WorkflowStartPayload, "dataSourceId" | "trainingDataSourceId" | "validationDataSourceId">;
  requestIds: string[];
  resultRefs: Array<{ purpose: string; id: string; filename?: string }>;
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
  jobId?: string;
  dataSourceId?: string;
  dualTitle?: string;
  trackAMarkdown?: string;
  trackBMarkdown?: string;
  interventionLog?: string[];
}

function stripTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "");
}

function normalizeApiBase(value: string | undefined): string {
  const trimmed = stripTrailingSlashes((value ?? "").trim());
  if (!trimmed) return "";

  try {
    const url = new URL(trimmed);
    if (url.hostname === "localhost" || url.hostname === "::1" || url.hostname === "[::1]") {
      url.hostname = "127.0.0.1";
    }
    return stripTrailingSlashes(url.toString());
  } catch {
    return trimmed
      .replace(/^(https?:\/\/)localhost(?=[:/]|$)/i, (_match, scheme: string) => `${scheme}127.0.0.1`)
      .replace(/^(https?:\/\/)\[::1\](?=[:/]|$)/i, (_match, scheme: string) => `${scheme}127.0.0.1`)
      .replace(/^(\/\/)localhost(?=[:/]|$)/i, (_match, prefix: string) => `${prefix}127.0.0.1`)
      .replace(/^localhost(?=[:/]|$)/i, "127.0.0.1");
  }
}

const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE);

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
  if (STATIC_DEMO && path === "/api/health") {
    return staticHealthDataUrl();
  }
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

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? value as Record<string, unknown> : null;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function dataSourcePayloadFrom(value: unknown): WorkflowDataSourceUsage["request"] {
  const record = asRecord(value);
  if (!record) return {};
  return {
    dataSourceId: stringValue(record.dataSourceId),
    trainingDataSourceId: stringValue(record.trainingDataSourceId),
    validationDataSourceId: stringValue(record.validationDataSourceId),
  };
}

function mergeDataSourcePayloads(
  ...payloads: Array<WorkflowDataSourceUsage["request"]>
): WorkflowDataSourceUsage["request"] {
  return payloads.reduce<WorkflowDataSourceUsage["request"]>(
    (merged, payload) => ({
      dataSourceId: payload.dataSourceId ?? merged.dataSourceId,
      trainingDataSourceId: payload.trainingDataSourceId ?? merged.trainingDataSourceId,
      validationDataSourceId: payload.validationDataSourceId ?? merged.validationDataSourceId,
    }),
    {}
  );
}

function appendResultRef(
  refs: WorkflowDataSourceUsage["resultRefs"],
  purpose: string,
  value: unknown
) {
  if (!value) return;
  if (typeof value === "string") {
    if (value.trim()) refs.push({ purpose, id: value });
    return;
  }
  const record = asRecord(value);
  if (!record) return;
  const id = stringValue(record.dataSourceId) ?? stringValue(record.id);
  if (!id) return;
  refs.push({
    purpose,
    id,
    filename: stringValue(record.filename) ?? stringValue(record.name),
  });
}

export function collectWorkflowDataSourceUsage(
  jobOrResult: WorkflowJobStatus | WorkflowJobResult | null | undefined
): WorkflowDataSourceUsage {
  const root = asRecord(jobOrResult);
  const result = asRecord(root?.result) ?? root;
  const request = mergeDataSourcePayloads(
    dataSourcePayloadFrom(result?.request),
    dataSourcePayloadFrom(result?.requestParams),
    dataSourcePayloadFrom(root?.request),
    dataSourcePayloadFrom(root?.requestParams),
    dataSourcePayloadFrom(result)
  );
  const requestIds = Array.from(new Set([
    request.dataSourceId,
    request.trainingDataSourceId,
    request.validationDataSourceId,
  ].filter((id): id is string => Boolean(id))));

  const resultRefs: WorkflowDataSourceUsage["resultRefs"] = [];
  appendResultRef(resultRefs, "result", result?.dataSourceId);
  appendResultRef(resultRefs, "training", result?.trainingDataSourceId);
  appendResultRef(resultRefs, "validation", result?.validationDataSourceId);
  const dataSources = asRecord(result?.data_source) ?? asRecord(result?.dataSource);
  if (dataSources) {
    Object.entries(dataSources).forEach(([purpose, value]) => appendResultRef(resultRefs, purpose, value));
  }

  const seen = new Set<string>();
  return {
    request,
    requestIds,
    resultRefs: resultRefs.filter((ref) => {
      const key = `${ref.purpose}:${ref.id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }),
  };
}

function summarizeBody(body: BodyInit | null | undefined): unknown {
  if (!body) return undefined;
  if (typeof FormData !== "undefined" && body instanceof FormData) {
    const fields: string[] = [];
    body.forEach((_value, key) => fields.push(key));
    return { formFields: fields };
  }
  if (typeof body === "string") {
    try {
      return JSON.parse(body);
    } catch {
      return body.slice(0, 500);
    }
  }
  return { bodyType: Object.prototype.toString.call(body) };
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const url = apiUrl(path);
  const startedAt = performance.now();
  logger.apiRequest(method, url, summarizeBody(init.body));
  try {
    const res = await fetch(url, init);
    return await readJson<T>(res, { method, url, startedAt });
  } catch (error) {
    if (!wasLogged(error)) {
      logger.apiError(method, url, error, Math.round(performance.now() - startedAt));
    }
    throw error;
  }
}

async function readJson<T>(
  res: Response,
  meta: { method: string; url: string; startedAt: number }
): Promise<T> {
  const text = await res.text();
  const duration = Math.round(performance.now() - meta.startedAt);
  if (!res.ok) {
    const detail = text ? `: ${text.slice(0, 180)}` : "";
    const error = new Error(`API ${res.status}${detail}`);
    logger.apiError(meta.method, meta.url, error, duration);
    throw error;
  }
  try {
    const data = (text ? JSON.parse(text) : {}) as T;
    logger.apiResponse(meta.method, meta.url, res.status, duration);
    return data;
  } catch (error) {
    logger.apiError(meta.method, meta.url, error, duration);
    throw error;
  }
}

export async function startWorkflowJob(
  sequence: MockSequenceId,
  requestPayload: WorkflowStartPayload = {}
): Promise<string> {
  if (STATIC_DEMO) {
    return staticStartWorkflowJob(sequence, requestPayload);
  }
  const responsePayload = await requestJson<{ jobId?: string; job_id?: string }>(API.RULESETS_LEARN, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario: SEQUENCE_SCENARIO[sequence],
      sequence,
      ...compactWorkflowPayload(requestPayload),
    }),
  });
  const jobId = responsePayload.jobId ?? responsePayload.job_id;
  if (!jobId) throw new Error("start workflow returned no job id");
  return jobId;
}

export async function uploadDataSource(
  scenario: Scenario,
  file: File,
  note = ""
): Promise<DataSourceUploadResult> {
  if (STATIC_DEMO) {
    const result = await staticUploadDataSource(scenario, file, note);
    latestDataSources.set(scenario, {
      ...result,
      scenario,
      note,
      uploadedAt: Date.now(),
    });
    return result;
  }
  const form = new FormData();
  form.append("scenario", scenario);
  form.append("note", note);
  form.append("file", file, file.name);
  const raw = await requestJson<Partial<DataSourceUploadResult>>(API.DATA_SOURCES, {
    method: "POST",
    body: form,
  });
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
  if (STATIC_DEMO) {
    return staticUploadOfficeRuleset();
  }
  const raw = await requestJson<Partial<RuleSetUploadResult>>(API.RULESETS_UPLOAD, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario: "office_demo" satisfies Scenario }),
  });
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
  if (STATIC_DEMO) {
    const result = await staticRegisterDataSource("office_demo", filename, note);
    latestDataSources.set("office_demo", {
      ...result,
      scenario: "office_demo",
      note,
      uploadedAt: Date.now(),
    });
    return result;
  }
  const raw = await requestJson<Partial<DataSourceUploadResult>>(API.DATA_SOURCES, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario: "office_demo" satisfies Scenario, filename, note }),
  });
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
  if (STATIC_DEMO) {
    return staticStartOfficeWorkflow(requestPayload);
  }
  const responsePayload = await requestJson<{ jobId?: string; job_id?: string }>(API.RULESETS_LEARN, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario: "office_demo" satisfies Scenario,
      sequence: "office-demo",
      ...compactWorkflowPayload(requestPayload),
    }),
  });
  const jobId = responsePayload.jobId ?? responsePayload.job_id;
  if (!jobId) throw new Error("start office workflow returned no job id");
  return jobId;
}

export async function sendConstrainedChatMessage(payload: {
  conversationId: string;
  scenario?: Scenario;
  rulesetId?: string;
  message: string;
  systemPrompt?: string;
  ragFiles?: string[];
  dataSourceId?: string;
  validationDataSourceId?: string;
}): Promise<ConstrainedChatResult> {
  if (STATIC_DEMO) {
    return staticSendConstrainedChatMessage(payload);
  }
  return requestJson<ConstrainedChatResult>(API.CHAT_CONSTRAINED, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario: payload.scenario ?? ("office_demo" satisfies Scenario),
      conversationId: payload.conversationId,
      rulesetId: payload.rulesetId,
      message: payload.message,
      systemPrompt: payload.systemPrompt,
      ragFiles: payload.ragFiles ?? [],
      dataSourceId: payload.dataSourceId,
      validationDataSourceId: payload.validationDataSourceId,
    }),
  });
}

export async function fetchWorkflowJob(jobId: string): Promise<WorkflowJobStatus> {
  if (STATIC_DEMO) {
    return staticFetchWorkflowJob(jobId);
  }
  return normalizeJob(await requestJson<WorkflowJobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`));
}

export async function waitForWorkflowJob(
  jobId: string,
  options: { attempts?: number; delayMs?: number } = {}
): Promise<WorkflowJobStatus> {
  if (STATIC_DEMO) {
    return staticWaitForWorkflowJob(jobId, options);
  }
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
