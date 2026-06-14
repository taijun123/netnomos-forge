import { useEffect, useState } from "react";
import { WorkflowLog } from "./WorkflowLog";
import {
  workflowPayloadFromLatestDataSource,
  type WorkflowStartPayload,
} from "../lib/apiClient";
import type { WorkflowJobResult, WorkflowJobStatus } from "../lib/events";
import type { MockSequenceId } from "../mock/sse";

export function ScenarioRunPanel({
  title,
  uploadLabel,
  recommendedQuestion,
  sequence,
  evidence,
  requestPayload,
  autoRunToken,
  onResult,
  onError,
}: {
  title: string;
  uploadLabel: string;
  recommendedQuestion: string;
  sequence: MockSequenceId;
  evidence: string[];
  requestPayload?: WorkflowStartPayload;
  autoRunToken?: number;
  onResult: (result: WorkflowJobResult, job: WorkflowJobStatus) => void;
  onError?: (err: unknown, job?: WorkflowJobStatus) => void;
}) {
  const [question, setQuestion] = useState(recommendedQuestion);
  const [runId, setRunId] = useState<number | null>(null);
  const [runPayload, setRunPayload] = useState<WorkflowStartPayload | null>(null);
  const [running, setRunning] = useState(false);

  const runScenario = () => {
    const prompt = question.trim() || recommendedQuestion;
    setRunPayload({
      ...workflowPayloadFromLatestDataSource(sequence, "validation"),
      ...(requestPayload ?? {}),
      question: prompt,
      reportPrompt: prompt,
    });
    setRunId(Date.now());
    setRunning(true);
  };

  // 一键演示：autoRunToken 自增即「模拟真人点运行实时 A/B 双轨」（问题用默认推荐值，无需输入）
  useEffect(() => {
    if (!autoRunToken) return;
    const t = setTimeout(() => runScenario(), 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRunToken]);

  return (
    <section className="scenario-run-panel">
      <div className="scenario-input-band">
        <div className="scenario-copy">
          <span className="scenario-label">稳定触发场景</span>
          <h3>{title}</h3>
          <p>
            资料：<strong>{uploadLabel}</strong>。输入下方问题后运行实时 A/B 双轨，
            系统会把问题、资料登记和规则集一起提交给后端 job。
          </p>
          <div className="scenario-evidence">
            {evidence.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
        <label className="scenario-question">
          <span>输入给模型的问题</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
            spellCheck={false}
          />
        </label>
        <button className="btn btn-primary" disabled={running} onClick={runScenario}>
          {running ? "实时双轨运行中…" : "运行实时 A/B 双轨"}
        </button>
      </div>
      {runId !== null && (
        <WorkflowLog
          key={`${sequence}-${runId}`}
          sequence={sequence}
          requestPayload={runPayload ?? undefined}
          title="实时 A/B 双轨执行"
          onResult={onResult}
          onError={onError}
          onDone={() => setRunning(false)}
        />
      )}
    </section>
  );
}
