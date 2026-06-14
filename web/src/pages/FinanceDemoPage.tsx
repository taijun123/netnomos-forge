import { useEffect, useMemo, useRef, useState } from "react";
import { StepRail, type StepDef } from "../components/StepRail";
import { WorkflowLog } from "../components/WorkflowLog";
import { RuleCardWall } from "../components/RuleCardWall";
import { MarkdownBlock } from "../components/MarkdownBlock";
import { ScenarioRunPanel } from "../components/ScenarioRunPanel";
import { DataSourceUploadBox, type UploadedDataSource } from "../components/DataSourceUploadBox";
import { mergeRuleCards } from "../lib/resultAdapters";
import {
  collectWorkflowDataSourceUsage,
  type WorkflowJobStatus,
  type WorkflowStartPayload,
} from "../lib/apiClient";
import type { WorkflowJobResult } from "../lib/events";
import type { DualReport as ApiDualReport, Violation } from "../types/api";
import {
  FINANCE_SAMPLE_ROWS,
  FINANCE_DATASET_META,
} from "../mock/finance";
import { useDemo } from "../demo/DemoContext";
import { DEMO_PACING, makeAbortableDelay, createGate, awaitGate, autoUpload, type Gate } from "../demo/demoDriver";
import { FINANCE_QUESTION } from "../demo/demoAssets";

const STEPS: StepDef[] = [
  { id: "preview", label: "训练资料预览", hint: "合成财务 960 行" },
  { id: "learn", label: "规则学习", hint: "勾稽 / 配平" },
  { id: "upload", label: "资料上传", hint: "华信咨询" },
  { id: "faults", label: "规则核查", hint: "违规命中" },
  { id: "question", label: "输入报告问题", hint: "审阅范围" },
  { id: "dual", label: "A/B 双轨", hint: "标红 vs 修正" },
  { id: "report", label: "报告预览/下载", hint: "live result" },
];

const FINANCE_SCENARIO_QUESTION =
  "请基于华信咨询待审资料包，生成一份年度财务分析与审阅报告，并指出营业成本、资产负债配平、现金跨期、存货占比和应收增长是否存在异常。";

export function FinanceDemoPage() {
  const [step, setStep] = useState<string>("preview");
  const [liveResult, setLiveResult] = useState<WorkflowJobResult | null>(null);
  const [validationResult, setValidationResult] = useState<WorkflowJobResult | null>(null);
  const [dualResult, setDualResult] = useState<WorkflowJobResult | null>(null);
  const [validationJob, setValidationJob] = useState<WorkflowJobStatus | null>(null);
  const [dualJob, setDualJob] = useState<WorkflowJobStatus | null>(null);
  const [auditSource, setAuditSource] = useState<UploadedDataSource | null>(null);
  const [reportQuestion, setReportQuestion] = useState(FINANCE_SCENARIO_QUESTION);
  const [demoError, setDemoError] = useState<string | null>(null);

  // 一键演示：自动驱动整条财务流程
  const { mode, runToken, setStatus } = useDemo();
  const [faultToken, setFaultToken] = useState(0);
  const [dualToken, setDualToken] = useState(0);
  const gatesRef = useRef<{
    learn: Gate<WorkflowJobResult>;
    validate: Gate<WorkflowJobResult>;
    dual: Gate<WorkflowJobResult>;
  } | null>(null);

  useEffect(() => {
    if (mode !== "finance") return;
    const ac = new AbortController();
    const delay = makeAbortableDelay(ac.signal);
    const gates = { learn: createGate<WorkflowJobResult>(), validate: createGate<WorkflowJobResult>(), dual: createGate<WorkflowJobResult>() };
    gatesRef.current = gates;
    (async () => {
      try {
        setDemoError(null);
        setStep("preview");
        await delay(DEMO_PACING.stepBeat);
        setStep("learn");
        const learn = await awaitGate(gates.learn, delay, "finance learn workflow");
        setLiveResult(learn);
        await delay(DEMO_PACING.afterLearn);
        setStep("upload");
        const ds = await autoUpload("finance");
        setAuditSource(ds);
        setValidationResult(null);
        setDualResult(null);
        setValidationJob(null);
        setDualJob(null);
        await delay(DEMO_PACING.afterUpload);
        setStep("faults");
        await delay(DEMO_PACING.beforeValidate);
        setFaultToken((x) => x + 1); // 触发资料规则核查
        const val = await awaitGate(gates.validate, delay, "finance validation workflow");
        setValidationResult(val);
        setLiveResult(val);
        await delay(DEMO_PACING.afterValidate);
        setStep("question");
        setReportQuestion(FINANCE_QUESTION);
        await delay(DEMO_PACING.stepBeat * 1.6);
        setStep("dual");
        await delay(DEMO_PACING.beforeDual);
        setDualToken((x) => x + 1); // 触发 A/B 双轨
        const dual = await awaitGate(gates.dual, delay, "finance report workflow");
        setDualResult(dual);
        setLiveResult(dual);
        await delay(DEMO_PACING.afterDual);
        setStep("report");
        await delay(DEMO_PACING.reportDwell);
        setStatus("done");
      } catch (err) {
        if (isAbortError(err)) return;
        setStatus("error");
        setDemoError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, runToken]);

  const ruleCards = useMemo(
    () => mergeRuleCards(liveResult?.cards, liveResult?.rules, []),
    [liveResult]
  );
  const liveViolations =
    validationResult?.violations?.length
      ? validationResult.violations
      : validationResult?.dual?.track_a.violations ?? [];
  const auditSourceLabel = formatUploadedSource(auditSource);
  const hasLiveValidation = Boolean(auditSource && validationResult);
  const hasReportQuestion = reportQuestion.trim().length > 0;

  return (
    <div className="demo-layout">
      <StepRail steps={STEPS} active={step} onSelect={setStep} />
      <div className="demo-stage">
        <DemoHeader />
        <LiveResultBanner result={liveResult} />
        {demoError && (
          <div className="workflow-error">
            一键演示已停止，未使用本地模拟结果：{demoError}
          </div>
        )}
        {step === "preview" && <PreviewStep onNext={() => setStep("learn")} />}
        {step === "learn" && (
          <>
            <WorkflowLog
              sequence="learn-finance"
              title="规则学习 · 事件流"
              onResult={(result) => {
                setLiveResult(result);
                gatesRef.current?.learn.resolve(result);
              }}
              onError={(err) => gatesRef.current?.learn.reject(err)}
            />
            {ruleCards.length > 0 ? (
              <RuleCardWall cards={ruleCards} />
            ) : (
              <EmptyLiveState
                title="还没有真实规则卡"
                detail="请等待后端 job 完成。页面已移除静态规则卡，不再用模拟数据顶替。"
              />
            )}
          </>
        )}
        {step === "upload" && (
          <UploadMaterialStep
            uploaded={auditSource}
            onUploaded={(source) => {
              setAuditSource(source);
              setValidationResult(null);
              setDualResult(null);
              setValidationJob(null);
              setDualJob(null);
            }}
            onNext={() => setStep("faults")}
          />
        )}
        {step === "faults" && (
          auditSource ? (
            <FaultCards
              violations={liveViolations}
              isLive={hasLiveValidation}
              sourceLabel={auditSourceLabel}
              autoStartToken={faultToken}
              requestPayload={{
                dataSourceId: auditSource.dataSourceId,
                validationDataSourceId: auditSource.dataSourceId,
              }}
              dataSourceNotice={formatDataSourceJobNotice(validationJob ?? validationResult, auditSource)}
              onResult={(result, job) => {
                setValidationJob(job);
                setValidationResult(result);
                setDualResult(null);
                setDualJob(null);
                setLiveResult(result);
                gatesRef.current?.validate.resolve(result);
              }}
              onError={(err) => gatesRef.current?.validate.reject(err)}
              onNext={() => setStep("question")}
            />
          ) : (
            <EmptyLiveState
              title="请先上传待审资料"
              detail="未选择资料时不会展示规则核查结果。请回到“资料上传”步骤，通过文件选择框上传待审资料。"
            />
          )
        )}
        {step === "question" && (
          auditSource ? (
            <ReportQuestionStep
              sourceLabel={auditSourceLabel}
              question={reportQuestion}
              onQuestionChange={setReportQuestion}
              onNext={() => setStep("dual")}
            />
          ) : (
            <EmptyLiveState
              title="请先上传待审资料"
              detail="报告问题必须绑定到一个已上传资料包，页面才会进入 A/B 双轨。"
            />
          )
        )}
        {step === "dual" && (
          auditSource && validationResult && hasReportQuestion ? (
          <div>
            <ScenarioRunPanel
              key={`${auditSource.dataSourceId}-${reportQuestion}`}
              title="华信咨询资料包审阅"
              uploadLabel={auditSourceLabel}
              recommendedQuestion={reportQuestion}
              sequence="report-finance"
              evidence={[
                "R01 进销存勾稽",
                "R02 资产负债配平",
                "R04 现金跨期",
                "R06/R07 软规则",
              ]}
              requestPayload={{
                dataSourceId: auditSource.dataSourceId,
                validationDataSourceId: auditSource.dataSourceId,
              }}
              autoRunToken={dualToken}
              onResult={(result, job) => {
                setDualJob(job);
                setDualResult(result);
                setLiveResult(result);
                gatesRef.current?.dual.resolve(result);
              }}
              onError={(err) => gatesRef.current?.dual.reject(err)}
            />
            <DualReport dual={dualResult?.dual} />
          </div>
          ) : (
            <EmptyLiveState
              title={!auditSource ? "请先上传待审资料" : !validationResult ? "请先运行资料核查" : "请先输入报告问题"}
              detail="A/B 双轨必须先绑定上传资料、完成一次规则核查，并在问题框里写清要模型审阅哪些科目、异常和报告输出。"
            />
          )
        )}
        {step === "report" && (
          auditSource ? (
            <ReportStep
              dual={dualResult?.dual}
              sourceLabel={auditSourceLabel}
              question={reportQuestion}
              dataSourceNotice={formatDataSourceJobNotice(dualJob ?? dualResult, auditSource)}
            />
          ) : (
            <EmptyLiveState
              title="请先上传待审资料"
              detail="报告预览和下载只展示已上传资料对应的 A/B 双轨结果。"
            />
          )
        )}
      </div>
    </div>
  );
}

function formatUploadedSource(source: UploadedDataSource | null): string {
  if (!source) return "尚未上传待审资料";
  return `${source.filename} · dataSourceId ${source.dataSourceId}`;
}

function formatDataSourceJobNotice(
  jobOrResult: WorkflowJobStatus | WorkflowJobResult | null | undefined,
  source: UploadedDataSource | null
): string {
  const usage = collectWorkflowDataSourceUsage(jobOrResult ?? null);
  const requestEntries = [
    ["dataSourceId", usage.request.dataSourceId],
    ["trainingDataSourceId", usage.request.trainingDataSourceId],
    ["validationDataSourceId", usage.request.validationDataSourceId],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]));
  if (requestEntries.length > 0) {
    return `后端 job request 已携带上传资料 ID：${requestEntries.map(([key, value]) => `${key}=${value}`).join("；")}。该 dataSourceId 参与了本次任务入参；页面不额外声称文件内容已被解析。`;
  }
  if (usage.resultRefs.length > 0) {
    return `后端 result 返回数据源引用：${usage.resultRefs.map((ref) => `${ref.purpose}=${ref.id}${ref.filename ? ` (${ref.filename})` : ""}`).join("；")}。`;
  }
  if (source) {
    return `文件已上传并登记为 dataSourceId ${source.dataSourceId}；运行核查后再根据 job request/result 确认它是否参与本次任务。`;
  }
  return "尚未选择待审资料。";
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function LiveResultBanner({ result }: { result: WorkflowJobResult | null }) {
  if (!result) return null;
  const violationCount =
    result.violations?.length ?? result.dual?.track_a.violations?.length ?? 0;
  return (
    <div className="live-result-banner">
      <span>live result</span>
      <strong>{result.rules?.length ?? 0}</strong> rules
      <strong>{result.cards?.length ?? 0}</strong> cards
      <strong>{violationCount}</strong> violations
    </div>
  );
}

function DemoHeader() {
  return (
    <div className="demo-header">
      <div>
        <span className="demo-kicker">财务报表 demo</span>
        <h1>勾稽规则学习与双轨合规报告</h1>
      </div>
      <span className="demo-source-pill">数据源 · 合成财务报表 960 行</span>
    </div>
  );
}

function EmptyLiveState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-live-state glass">
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

function PreviewStep({ onNext }: { onNext: () => void }) {
  const m = FINANCE_DATASET_META;
  return (
    <div className="preview-step glass">
      <div className="preview-stats">
        <div>
          <strong>{m.totalRows}</strong>
          <span>总行数</span>
        </div>
        <div>
          <strong>{m.industries.join(" / ")}</strong>
          <span>3 个行业</span>
        </div>
        <div>
          <strong>{m.companiesPerIndustry} × {m.periods}</strong>
          <span>公司 × 报告期</span>
        </div>
        <div>
          <strong>{m.unit}</strong>
          <span>金额单位（整数）</span>
        </div>
      </div>
      <p className="preview-desc">{m.description}</p>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>公司</th>
              <th>行业</th>
              <th>期</th>
              <th>营业收入</th>
              <th>营业成本</th>
              <th>毛利</th>
              <th>期末存货</th>
              <th>资产总计</th>
              <th>负债</th>
              <th>所有者权益</th>
            </tr>
          </thead>
          <tbody>
            {FINANCE_SAMPLE_ROWS.map((r) => (
              <tr key={`${r.companyId}-${r.period}`}>
                <td className="mono">{r.companyId}</td>
                <td>{r.industry}</td>
                <td className="mono">{r.period}</td>
                <td className="mono">{r.revenue.toLocaleString()}</td>
                <td className="mono">{r.cogs.toLocaleString()}</td>
                <td className="mono">{r.grossProfit.toLocaleString()}</td>
                <td className="mono">{r.inventoryEnd.toLocaleString()}</td>
                <td className="mono">{r.totalAssets.toLocaleString()}</td>
                <td className="mono">{r.totalLiab.toLocaleString()}</td>
                <td className="mono">{r.totalEquity.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="preview-foot">示例 8 行 · 完整训练集 {m.totalRows} 行天然满足全部勾稽与配平规则。</p>
      <button className="btn btn-primary" onClick={onNext}>
        开始规则学习 →
      </button>
    </div>
  );
}

function UploadMaterialStep({
  uploaded,
  onUploaded,
  onNext,
}: {
  uploaded: UploadedDataSource | null;
  onUploaded: (dataSource: UploadedDataSource) => void;
  onNext: () => void;
}) {
  return (
    <div className="upload-step glass">
      <div className="upload-drop">
        <span className="upload-icon">⇪</span>
        <strong>上传待审资料</strong>
        <em>用户不需要预先知道资料是否正确；B 轨会按规则核查并给出修正依据</em>
      </div>
      <DataSourceUploadBox
        scenario="finance_v1"
        title="选择财务资料文件"
        description="支持 CSV、JSON、TXT 结构化财务资料。上传成功只表示文件已保存并登记 dataSourceId；核查是否使用该 ID 以 job request/result 为准。"
        accept=".csv,.json,.txt"
        note="finance-audit-material"
        uploaded={uploaded}
        onUploaded={onUploaded}
      />
      <p className="upload-note">
        {formatDataSourceJobNotice(null, uploaded)}
      </p>
      <button className="btn btn-primary" disabled={!uploaded} onClick={onNext}>
        {uploaded ? "进入规则核查 →" : "请先上传资料"}
      </button>
    </div>
  );
}

function FaultCards({
  violations,
  isLive,
  sourceLabel,
  autoStartToken,
  requestPayload,
  dataSourceNotice,
  onResult,
  onError,
  onNext,
}: {
  violations: Violation[];
  isLive: boolean;
  sourceLabel: string;
  autoStartToken?: number;
  requestPayload: WorkflowStartPayload;
  dataSourceNotice: string;
  onResult: (result: WorkflowJobResult, job: WorkflowJobStatus) => void;
  onError?: (err: unknown) => void;
  onNext: () => void;
}) {
  const [runId, setRunId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const startValidation = () => {
    setRunId(Date.now());
    setRunning(true);
  };

  // 一键演示：autoStartToken 自增即「模拟真人点运行资料规则核查」
  useEffect(() => {
    if (!autoStartToken) return;
    const t = setTimeout(() => startValidation(), 600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStartToken]);

  return (
    <div className="fault-panel">
      <div className="panel-head">
        <h3>后端 live result · 违规命中</h3>
        <span className="panel-sub">
          {sourceLabel} · {violations.length} 条违规来自 contracts.Violation
        </span>
      </div>
      <p className="upload-note">{dataSourceNotice}</p>
      <div className="workflow-actions">
        <button className="btn btn-primary" disabled={running} onClick={startValidation}>
          {running ? "规则核查运行中…" : "运行资料规则核查"}
        </button>
        <button className="btn btn-outline" disabled={!isLive} onClick={onNext}>
          输入报告问题 →
        </button>
      </div>
      {runId !== null && (
        <WorkflowLog
          key={`validate-finance-${runId}`}
          sequence="validate-finance"
          title="资料核查 · 事件流"
          requestPayload={requestPayload}
          onResult={onResult}
          onError={onError}
          onDone={() => setRunning(false)}
        />
      )}
      {!isLive ? (
        <EmptyLiveState
          title="还没有真实违规命中"
          detail="资料已上传，但还没有执行核查。点击“运行资料规则核查”后，后端 job 会带着 dataSourceId 与 validationDataSourceId 返回核查结果。"
        />
      ) : violations.length > 0 ? (
        <div className="fault-grid">
          {violations.map((v) => (
            <article className="fault-card glass" key={`${v.row_index}-${v.rule_id}`}>
              <header>
                <span className="fault-id-lg">#{v.row_index + 1}</span>
                <span className="fault-rule">命中 {v.rule_id}</span>
              </header>
              <h4>{v.message_zh}</h4>
              <div className="fault-field">{v.fields.join(" / ")}</div>
              <div className="fault-compare">
                <div className="fault-observed">
                  <span>实际值</span>
                  <strong>
                    {Object.entries(v.observed)
                      .map(([key, value]) => `${key}=${value}`)
                      .join(", ")}
                  </strong>
                </div>
                <span className="fault-arrow">→</span>
                <div className="fault-expected">
                  <span>期望</span>
                  <strong>{v.expected}</strong>
                </div>
              </div>
              <code className="fault-rule-text">{v.rule_text}</code>
            </article>
          ))}
        </div>
      ) : (
        <EmptyLiveState
          title="核查完成，未命中违规"
          detail="本次后端 job 没有返回 violations。可继续进入报告问题步骤生成 A/B 双轨。"
        />
      )}
    </div>
  );
}

function ReportQuestionStep({
  sourceLabel,
  question,
  onQuestionChange,
  onNext,
}: {
  sourceLabel: string;
  question: string;
  onQuestionChange: (question: string) => void;
  onNext: () => void;
}) {
  const canContinue = question.trim().length > 0;
  return (
    <section className="scenario-run-panel">
      <div className="scenario-input-band">
        <div className="scenario-copy">
          <span className="scenario-label">输入报告问题</span>
          <h3>告诉模型要审阅什么</h3>
          <p>
            资料：<strong>{sourceLabel}</strong>。请在问题里写清要核查的科目、异常类型和希望生成的报告形式，
            例如“生成年度财务分析与审阅报告，并指出营业成本、配平、现金、存货和应收是否异常”。
          </p>
          <div className="scenario-evidence">
            <span>营业成本</span>
            <span>资产负债配平</span>
            <span>现金跨期</span>
            <span>存货/应收异常</span>
          </div>
        </div>
        <label className="scenario-question">
          <span>输入给模型的问题</span>
          <textarea
            value={question}
            onChange={(event) => onQuestionChange(event.target.value)}
            rows={5}
            spellCheck={false}
          />
        </label>
        <button className="btn btn-primary" disabled={!canContinue} onClick={onNext}>
          进入 A/B 双轨 →
        </button>
      </div>
    </section>
  );
}

function DualReport({ dual }: { dual?: ApiDualReport | null }) {
  if (dual) {
    const trackBViolationCount = dual.track_b.violations.length;
    return (
      <div className="dual-track dual-report">
        <div className="track-col track-a glass">
          <div className="track-head">
            <span className="track-badge badge-a">A 轨 · 后端报告</span>
            <span className="track-verdict bad">标红 {dual.track_a.violations.length} 处</span>
          </div>
          <MarkdownBlock text={dual.track_a.markdown} />
        </div>
        <div className="track-col track-b glass">
          <div className="track-head">
            <span className="track-badge badge-b">B 轨 · 合规报告</span>
            <span className="track-verdict ok">{trackBViolationCount} 违规</span>
          </div>
          <MarkdownBlock text={dual.track_b.markdown} />
          <aside className="intervention-log inline">
            <h4>核查与干预日志</h4>
            <ul>
              {dual.track_b.intervention_log.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    );
  }

  return (
    <EmptyLiveState
      title="还没有真实双轨报告"
      detail="点击上方“运行实时 A/B 双轨”，等后端 job 完成后再展示 A/B 报告。"
    />
  );
}

function ReportStep({
  dual,
  sourceLabel,
  question,
  dataSourceNotice,
}: {
  dual?: ApiDualReport | null;
  sourceLabel: string;
  question: string;
  dataSourceNotice: string;
}) {
  if (dual) {
    const href = buildReportDownloadHref(dual, sourceLabel, question);
    return (
      <div className="report-step glass">
        <div className="report-paper is-wide">
          <span className="report-tag">live result · 后端双轨</span>
          <h2>{dual.title}</h2>
          <p className="upload-note">
            资料：{sourceLabel}。报告问题：{question}
          </p>
          <p className="upload-note">{dataSourceNotice}</p>
          <a className="btn btn-outline" href={href} download="finance-dual-report.md">
            下载报告 Markdown
          </a>
          <div className="live-report-grid">
            <section>
              <h3>A 轨 · 标红对照</h3>
              <MarkdownBlock text={dual.track_a.markdown} />
            </section>
            <section>
              <h3>B 轨 · 槽位回填</h3>
              <MarkdownBlock text={dual.track_b.markdown} />
            </section>
          </div>
          <div className="diff-html" dangerouslySetInnerHTML={{ __html: dual.diff_html }} />
        </div>
      </div>
    );
  }

  return (
    <EmptyLiveState
      title="还没有真实报告"
      detail="请先在 A/B 双轨步骤运行实时流程。报告生成后，这里会展示预览并提供 Markdown 下载。"
    />
  );
}

function buildReportDownloadHref(
  dual: ApiDualReport,
  sourceLabel: string,
  question: string
): string {
  const markdown = [
    `# ${dual.title}`,
    "",
    `资料：${sourceLabel}`,
    `报告问题：${question}`,
    "",
    "## A 轨 · 标红对照",
    dual.track_a.markdown,
    "",
    "## B 轨 · 合规报告",
    dual.track_b.markdown,
    "",
    "## B 轨干预日志",
    ...dual.track_b.intervention_log.map((line) => `- ${line}`),
  ].join("\n");
  return `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
}
