import { useEffect, useRef, useState } from "react";
import {
  subscribeWorkflow,
  type StreamMode,
  type WorkflowHandle,
  type WorkflowJobResult,
  type WorkflowJobStatus,
} from "../lib/events";
import type { WorkflowStartPayload } from "../lib/apiClient";
import type { MockSequenceId } from "../mock/sse";
import { sequenceLength } from "../mock/sse";
import { AGENT_META } from "../types/api";
import type { WorkflowEvent } from "../types/api";

const STAGE_META: Record<string, { label: string; processor: string }> = {
  control: { label: "流程编排", processor: "FastAPI Orchestrator" },
  upload: { label: "上传资料", processor: "Upload parser / DataSource registry" },
  prepare: { label: "字段准备", processor: "DatasetSpec / GrammarSpec" },
  learn: { label: "规则学习", processor: "NetNomos hitting-set / Z3" },
  explain: { label: "规则解释", processor: "RAG / RuleExplainer / LLM optional" },
  validate: { label: "新资料核查", processor: "RuleSet validate / Z3 check" },
  project: { label: "修正投影", processor: "Projector + nearest feasible values" },
  report: { label: "双轨报告", processor: "A 裸模型 / B 约束" },
  diff: { label: "报告预览", processor: "Diff highlighter / final check" },
};

const WORKFLOW_MILESTONES = ["upload", "learn", "explain", "validate", "report", "diff"];

function stageState(stage: string, events: WorkflowEvent[]): WorkflowEvent["status"] {
  const stageEvents = events.filter((event) => event.stage === stage);
  return stageEvents[stageEvents.length - 1]?.status ?? "pending";
}

function stageMeta(stage: string): { label: string; processor: string } {
  return STAGE_META[stage] ?? { label: stage, processor: "后端处理器" };
}

function previewValue(value: unknown): string {
  const text = String(value);
  return text.length > 52 ? `${text.slice(0, 52)}…` : text;
}

/**
 * 规则学习面板：进度条 + WorkflowEvent 日志流。
 * 通过 events.ts 订阅真实后端 SSE/轮询；失败时直接显示错误。
 */
export function WorkflowLog({
  sequence,
  autoStart = true,
  title = "工作流事件流",
  payload,
  requestPayload,
  onResult,
  onDone,
  onError,
}: {
  sequence: MockSequenceId;
  autoStart?: boolean;
  title?: string;
  payload?: WorkflowStartPayload;
  requestPayload?: WorkflowStartPayload;
  onResult?: (result: WorkflowJobResult, job: WorkflowJobStatus) => void;
  onDone?: (job?: WorkflowJobStatus) => void;
  onError?: (err: unknown, job?: WorkflowJobStatus) => void;
}) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [mode, setMode] = useState<StreamMode | null>(null);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const expectedTotal = sequenceLength(sequence);
  const total = Math.max(expectedTotal, events.length || expectedTotal);
  const listRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);
  const startingRef = useRef(false);
  const runningRef = useRef(false);
  const handleRef = useRef<WorkflowHandle | null>(null);
  const effectivePayload = requestPayload ?? payload ?? {};

  const start = () => {
    if (startingRef.current || runningRef.current) return handleRef.current;
    startingRef.current = true;
    runningRef.current = true;
    handleRef.current?.close();
    setEvents([]);
    setMode(null);
    setJobId(null);
    setJobStatus(null);
    setError(null);
    setDone(false);
    setRunning(true);
    const handle = subscribeWorkflow(sequence, {
      onEvent: (ev) => setEvents((prev) => [...prev, ev]),
      onJobStart: (id) => setJobId(id),
      onMode: (m) => setMode(m),
      onDone: (job) => {
        startingRef.current = false;
        runningRef.current = false;
        handleRef.current = null;
        setRunning(false);
        setDone(true);
        setJobStatus(job?.status ?? null);
        if (job?.status === "failed") {
          const err = new Error(job.error || "workflow job failed");
          setError(err.message);
          onError?.(err, job);
        }
        if (job?.result) onResult?.(job.result, job);
        onDone?.(job);
      },
      onError: (err) => {
        startingRef.current = false;
        runningRef.current = false;
        handleRef.current = null;
        setRunning(false);
        setError(err instanceof Error ? err.message : String(err));
        onError?.(err);
      },
    }, effectivePayload);
    handleRef.current = handle;
    return handle;
  };

  useEffect(() => {
    if (!autoStart || startedRef.current) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled || startedRef.current) return;
      startedRef.current = true;
      start();
    }, 25);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      handleRef.current?.close();
      handleRef.current = null;
      startingRef.current = false;
      runningRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [events]);

  const progress = total > 0 ? Math.min(100, (events.length / total) * 100) : 0;
  const currentEvent = events[events.length - 1];
  const currentStage = currentEvent?.stage ?? "control";
  const currentMeta = currentEvent
    ? stageMeta(currentStage)
    : { label: "等待后端事件", processor: "SSE / REST polling" };
  const requestEntries = Object.entries(effectivePayload).filter(
    ([, value]) => value !== undefined && value !== ""
  );

  return (
    <div className="workflow-log glass">
      <div className="workflow-head">
        <div>
          <h3>{title}</h3>
          <span className="workflow-sub">
            后端按上传、规则学习、核查、投影和报告生成阶段执行；事件经 SSE 实时推送。
          </span>
        </div>
        <div className="workflow-meta">
          {mode && (
            <span className={`stream-pill is-${mode}`}>
              {mode === "live" ? "● 实时后端" : "○ 非真实事件流"}
            </span>
          )}
          {jobId && <span className="stream-pill is-job">job {jobId}</span>}
          {jobStatus === "failed" && (
            <span className="stream-pill is-blocked">后端失败</span>
          )}
          {error && !running && (
            <span className="stream-pill is-blocked">后端不可用</span>
          )}
          {done ? (
            <span className="stream-pill is-done">已完成</span>
          ) : (
            <button className="btn btn-ghost btn-sm" disabled={running} onClick={start}>
              {running ? "运行中…" : "重新运行"}
            </button>
          )}
        </div>
      </div>

      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <div className="progress-caption">
        {events.length}/{total} 步 · {Math.round(progress)}%
      </div>
      <div className="workflow-stage-list">
        {WORKFLOW_MILESTONES.map((stage) => {
          const meta = stageMeta(stage);
          const state = stageState(stage, events);
          return (
            <div className={`workflow-stage-step is-${state}`} key={stage}>
              <span>{meta.label}</span>
              <strong>{meta.processor}</strong>
            </div>
          );
        })}
      </div>
      <div className="workflow-current">
        <div>
          <span>当前阶段</span>
          <strong>{currentMeta.label}</strong>
          <em>{currentMeta.processor}</em>
        </div>
        {requestEntries.length > 0 && (
          <div>
            <span>本次输入</span>
            <strong>{requestEntries.map(([key]) => key).join(" / ")}</strong>
            <em>
              {requestEntries
                .map(([key, value]) => `${key}=${previewValue(value)}`)
                .join("；")}
            </em>
          </div>
        )}
      </div>
      {error && (
        <div className="workflow-error">
          真实后端结果不可用，页面不会使用本地模拟结果：{error}
        </div>
      )}

      <div className="event-stream" ref={listRef}>
        {events.length === 0 && (
          <div className="event-empty">等待事件推送…</div>
        )}
        {events.map((ev) => {
          const meta = AGENT_META[ev.agent];
          const stage = stageMeta(ev.stage);
          return (
            <div className="event-line" key={ev.id}>
              <span className={`event-dot is-${ev.status}`} />
              <div className="event-content">
                <div className="event-top">
                  <span
                    className="event-agent"
                    style={{ ["--c" as string]: meta.color }}
                  >
                    {meta.name}
                  </span>
                  <span className="event-stage">{ev.stage}</span>
                  <span className={`event-status is-${ev.status}`}>{ev.status}</span>
                  <time>{ev.time.slice(11)}</time>
                </div>
                <div className="event-stage-detail">
                  <strong>{stage.label}</strong>
                  <span>{stage.processor}</span>
                </div>
                <p>{ev.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
