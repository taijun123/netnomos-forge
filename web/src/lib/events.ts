/**
 * src/lib/events.ts
 * ----------------------------------------------------------------------------
 * SSE 客户端封装。只连接真实后端 EventSource（contracts.API_WORKFLOW_EVENTS =
 * /api/workflow/events/stream）。正式 demo 不再自动 fallback 到本地模拟事件，
 * 连接失败时直接暴露错误，让页面呈现真实运行状态。
 *
 * 用法：
 *   const handle = subscribeWorkflow("learn-network", {
 *     onEvent: (ev) => ...,
 *     onMode:  (mode) => ...,   // "live" | "mock"
 *     onDone:  () => ...,
 *   });
 *   handle.close();
 * ----------------------------------------------------------------------------
 */
import type { WorkflowEvent } from "../types/api";
import { fetchWorkflowJob, startWorkflowJob, workflowEventsUrl } from "./apiClient";
import type { WorkflowJobStatus, WorkflowStartPayload } from "./apiClient";
export type { WorkflowJobResult, WorkflowJobStatus, WorkflowStartPayload } from "./apiClient";
import type { MockSequenceId } from "../mock/sse";
import { logger } from "./logger";

export type StreamMode = "live" | "mock";

export interface WorkflowSubscription {
  onEvent: (event: WorkflowEvent) => void;
  onJobStart?: (jobId: string) => void;
  onMode?: (mode: StreamMode) => void;
  onDone?: (job?: WorkflowJobStatus) => void;
  onError?: (err: unknown) => void;
}

export interface WorkflowHandle {
  close: () => void;
}

// EventSource 首包慢时关闭 SSE，保留 REST 轮询读取真实 job 状态。
const LIVE_HANDSHAKE_TIMEOUT_MS = 1500;

/**
 * 订阅某条真实工作流序列。sequence 会映射到后端场景并启动 job。
 */
export function subscribeWorkflow(
  sequence: MockSequenceId,
  sub: WorkflowSubscription,
  payload: WorkflowStartPayload = {}
): WorkflowHandle {
  let closed = false;
  let source: EventSource | null = null;
  let handshakeTimer: ReturnType<typeof setTimeout> | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let liveJobId: string | null = null;
  let completed = false;
  const seenEventIds = new Set<string>();

  const emitEvent = (ev: WorkflowEvent) => {
    if (seenEventIds.has(ev.id)) return;
    seenEventIds.add(ev.id);
    sub.onEvent(ev);
  };

  const finishLive = (job: WorkflowJobStatus) => {
    if (completed || closed) return;
    completed = true;
    if (handshakeTimer) {
      clearTimeout(handshakeTimer);
      handshakeTimer = null;
    }
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    source?.close();
    source = null;
    sub.onMode?.("live");
    sub.onDone?.(job);
  };

  const pollJob = async (jobId: string) => {
    try {
      const job = await fetchWorkflowJob(jobId);
      if (closed) return;
      sub.onMode?.("live");
      job.events.forEach(emitEvent);
      if (job.status === "done" || job.status === "failed") {
        finishLive(job);
      }
    } catch (err) {
      if (!closed) sub.onError?.(err);
    }
  };

  // 浏览器不支持 EventSource（极少见）或无 window：直接报错，不走 mock。
  if (typeof window === "undefined" || typeof EventSource === "undefined") {
    sub.onError?.(new Error("EventSource is not available in this browser"));
    return { close: () => undefined };
  }

  const connectLive = async () => {
    try {
      logger.sseConnection('connecting', undefined);
      const jobId = await startWorkflowJob(sequence, payload);
      if (closed) return;
      liveJobId = jobId;
      logger.sseConnection('connected', undefined);
      sub.onMode?.("live");
      sub.onJobStart?.(jobId);
      void pollJob(jobId);
      if (!pollTimer) {
        pollTimer = setInterval(() => {
          if (liveJobId && !completed) void pollJob(liveJobId);
        }, 1000);
      }

      const url = workflowEventsUrl(jobId);
      // In development, if using proxy, SSE needs full URL
      // Use 127.0.0.1 instead of localhost to avoid IPv6 issues
      const sseUrl = url.startsWith('/') ? `http://127.0.0.1:8000${url}` : url;
      source = new EventSource(sseUrl);
      let gotFirst = false;

      handshakeTimer = setTimeout(() => {
        if (!gotFirst && !closed) {
          // SSE 首包慢时保留 job 轮询，避免代理/浏览器缓冲导致 UI 卡住。
          logger.warn('SSE handshake timeout, falling back to polling');
          source?.close();
          source = null;
        }
      }, LIVE_HANDSHAKE_TIMEOUT_MS);

      const handleMessage = (raw: MessageEvent) => {
        gotFirst = true;
        if (handshakeTimer) {
          clearTimeout(handshakeTimer);
          handshakeTimer = null;
        }
        sub.onMode?.("live");
        try {
          const ev = JSON.parse(raw.data) as WorkflowEvent;
          logger.sseEvent('workflow', ev);
          emitEvent(ev);
        } catch (err) {
          logger.error('Failed to parse SSE event', err);
          sub.onError?.(err);
        }
      };

      // 后端用 `event: workflow` 命名事件；同时兼容默认 message 事件。
      source.addEventListener("job", ((raw: MessageEvent) => {
        gotFirst = true;
        if (handshakeTimer) {
          clearTimeout(handshakeTimer);
          handshakeTimer = null;
        }
        sub.onMode?.("live");
        try {
          const payload = JSON.parse(raw.data) as { jobId?: string; job_id?: string };
          const jobId = payload.jobId ?? payload.job_id;
          if (!jobId) return;
          liveJobId = jobId;
          logger.sseEvent('job', { jobId });
          sub.onJobStart?.(jobId);
        } catch (err) {
          logger.error('Failed to parse job event', err);
          sub.onError?.(err);
        }
      }) as EventListener);
      source.addEventListener("workflow", handleMessage as EventListener);
      source.onmessage = handleMessage;

      source.onerror = (err) => {
        logger.error('SSE connection error', err);
        if (closed) return;
        if (!gotFirst) {
          if (handshakeTimer) {
            clearTimeout(handshakeTimer);
            handshakeTimer = null;
          }
          source?.close();
          source = null;
          if (!liveJobId) sub.onError?.(err);
      } else {
        // 后端完成后会关闭 SSE；浏览器通常以 error 事件告知关闭。
        logger.sseConnection('disconnected', undefined);
        source?.close();
        source = null;
          if (liveJobId) void pollJob(liveJobId);
      }
      };
    } catch (err) {
      logger.error('Failed to connect to SSE', err);
      sub.onError?.(err);
    }
  };

  void connectLive();

  return {
    close: () => {
      logger.sseConnection('disconnected', undefined);
      closed = true;
      if (handshakeTimer) clearTimeout(handshakeTimer);
      if (pollTimer) clearInterval(pollTimer);
      source?.close();
    },
  };
}
