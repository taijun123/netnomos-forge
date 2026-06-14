import { useMemo, useState } from "react";
import { StepRail, type StepDef } from "../components/StepRail";
import { WorkflowLog } from "../components/WorkflowLog";
import { RuleCardWall } from "../components/RuleCardWall";
import { MarkdownBlock } from "../components/MarkdownBlock";
import { ScenarioRunPanel } from "../components/ScenarioRunPanel";
import { DataSourceUploadBox, type UploadedDataSource } from "../components/DataSourceUploadBox";
import { mergeRuleCards } from "../lib/resultAdapters";
import type { WorkflowStartPayload } from "../lib/apiClient";
import type { WorkflowJobResult } from "../lib/events";
import type { DualReport, Violation } from "../types/api";

interface NetFlowRow {
  no: number;
  duration: string;
  proto: string;
  src: string;
  dst: string;
  srcPt: number;
  dstPt: number;
  packets: number;
  bytes: number;
  flags: string;
  appProto: string;
  violatedRuleIds?: string[];
  badFields?: string[];
  tip?: string;
}

const STEPS: StepDef[] = [
  { id: "upload", label: "内置数据", hint: "cidds_wk2 NetFlow" },
  { id: "learn", label: "规则学习", hint: "NetNomos + Z3" },
  { id: "cards", label: "规则卡", hint: "五类规则画像" },
  { id: "validate", label: "新资料核查", hint: "手工上传" },
  { id: "dual", label: "双轨对比", hint: "上传资料 + 问题" },
  { id: "report", label: "报告预览/下载", hint: "审计报告" },
];

const NETWORK_SCENARIO_QUESTION =
  "请基于我上传的待核查 NetFlow 资料，生成或抽取 10 条 CIDDS 风格记录，并说明哪些记录违反 UDP Flags、Packets/Bytes 物理上下界或 DNS 端口身份规则；同时给出规则约束后的合规版本。";

export function NetworkDemoPage() {
  const [step, setStep] = useState<string>("upload");
  const [liveResult, setLiveResult] = useState<WorkflowJobResult | null>(null);
  const [validationResult, setValidationResult] = useState<WorkflowJobResult | null>(null);
  const [dualResult, setDualResult] = useState<WorkflowJobResult | null>(null);
  const [validationSource, setValidationSource] = useState<UploadedDataSource | null>(null);
  const [learningSource, setLearningSource] = useState<UploadedDataSource | null>(null);
  const [useBuiltIn, setUseBuiltIn] = useState<boolean>(true);
  const ruleCards = useMemo(
    () => mergeRuleCards(liveResult?.cards, liveResult?.rules, []),
    [liveResult]
  );
  const violations =
    validationResult?.violations?.length
      ? validationResult.violations
      : validationResult?.dual?.track_a.violations?.length
        ? validationResult.dual.track_a.violations
        : [];
  const validationSourceLabel = formatUploadedSource(validationSource);

  return (
    <div className="demo-layout">
      <StepRail steps={STEPS} active={step} onSelect={setStep} />
      <div className="demo-stage">
        <DemoHeader />
        <LiveResultBanner result={liveResult} />
        {step === "upload" && (
          <UploadStep
            useBuiltIn={useBuiltIn}
            learningSource={learningSource}
            onUseBuiltInChange={setUseBuiltIn}
            onLearningSourceChange={setLearningSource}
            onClear={() => {
              setLearningSource(null);
              setLiveResult(null);
              setValidationResult(null);
              setDualResult(null);
            }}
            onNext={() => setStep("learn")}
          />
        )}
        {step === "learn" && (
          <WorkflowLog
            sequence="learn-network"
            title="规则学习 · 事件流"
            requestPayload={
              useBuiltIn
                ? {}
                : learningSource
                  ? { dataSourceId: learningSource.dataSourceId }
                  : {}
            }
            onResult={(result) => setLiveResult(result)}
          />
        )}
        {step === "cards" && (
          ruleCards.length > 0
            ? <RuleCardWall cards={ruleCards} />
            : <EmptyLiveState title="还没有真实规则卡" detail="请先运行「规则学习」。后端返回 cards/rules 后，这里才会展示规则卡墙。" />
        )}
        {step === "validate" && (
          <NetworkValidationStep
            uploaded={validationSource}
            onUploaded={(source) => {
              setValidationSource(source);
              setValidationResult(null);
              setDualResult(null);
            }}
            requestPayload={
              validationSource
                ? {
                    dataSourceId: validationSource.dataSourceId,
                    validationDataSourceId: validationSource.dataSourceId,
                  }
                : {}
            }
            violations={violations}
            hasValidationResult={Boolean(validationResult)}
            onResult={(result) => {
              setValidationResult(result);
              setLiveResult(result);
            }}
          />
        )}
        {step === "dual" && (
          validationSource && validationResult ? (
          <div>
            <ScenarioRunPanel
              key={validationSource.dataSourceId}
              title="CIDDS NetFlow 上传资料核查与双轨对比"
              uploadLabel={validationSourceLabel}
              recommendedQuestion={NETWORK_SCENARIO_QUESTION}
              sequence="learn-network"
              evidence={[
                "UDP -> noflags",
                "Bytes <= 65535 * Packets",
                "Bytes >= 42 * Packets",
                "DNS 端口身份一致",
              ]}
              requestPayload={{
                dataSourceId: validationSource.dataSourceId,
                validationDataSourceId: validationSource.dataSourceId,
              }}
              onResult={(result) => {
                setDualResult(result);
                setLiveResult(result);
              }}
            />
            <DualTrackFlows dual={dualResult?.dual} />
          </div>
          ) : (
            <EmptyLiveState
              title={!validationSource ? "请先上传待核查网络资料" : "请先运行新资料核查"}
              detail="双轨对比必须绑定「新资料核查」步骤上传的文件，并完成一次核查 job；未核查时不会运行或展示 A/B 表。"
            />
          )
        )}
        {step === "report" && (
          validationSource ? (
            <ReportStep dual={dualResult?.dual} sourceLabel={validationSourceLabel} />
          ) : (
            <EmptyLiveState
              title="请先上传待核查网络资料"
              detail="报告预览和下载只展示已上传资料对应的 A/B 双轨结果。"
            />
          )
        )}
      </div>
    </div>
  );
}

function formatUploadedSource(source: UploadedDataSource | null): string {
  if (!source) return "尚未上传待核查资料";
  return `${source.filename} · dataSourceId ${source.dataSourceId}`;
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
        <span className="demo-kicker">网络流量 demo</span>
        <h1>NetFlow 规则自发现与复用核查</h1>
      </div>
      <span className="demo-source-pill">数据源 · CIDDS NetFlow</span>
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

function UploadStep({
  useBuiltIn,
  learningSource,
  onUseBuiltInChange,
  onLearningSourceChange,
  onClear,
  onNext,
}: {
  useBuiltIn: boolean;
  learningSource: UploadedDataSource | null;
  onUseBuiltInChange: (useBuiltIn: boolean) => void;
  onLearningSourceChange: (source: UploadedDataSource) => void;
  onClear: () => void;
  onNext: () => void;
}) {
  return (
    <div className="upload-step glass">
      <div className="upload-options">
        <div className="upload-option-tabs">
          <button
            className={`upload-tab ${useBuiltIn ? 'active' : ''}`}
            onClick={() => onUseBuiltInChange(true)}
          >
            使用内置数据
          </button>
          <button
            className={`upload-tab ${!useBuiltIn ? 'active' : ''}`}
            onClick={() => onUseBuiltInChange(false)}
          >
            上传自定义数据
          </button>
        </div>
      </div>

      {useBuiltIn ? (
        <>
          <div className="upload-drop">
            <span className="upload-icon">⇪</span>
            <strong>cidds_wk2_normal_10k.csv</strong>
            <em>10,000 行正常 NetFlow · 已加载（演示数据）</em>
          </div>
          <div className="upload-meta">
            <div>
              <span>记录数</span>
              <strong>10,000</strong>
            </div>
            <div>
              <span>字段</span>
              <strong>Proto / SrcPt / Packets / Bytes / Flags …</strong>
            </div>
            <div>
              <span>用途</span>
              <strong>规则自发现训练集</strong>
            </div>
          </div>
          <p className="upload-note">
            规则学习使用内置正常流量；复用核查阶段请在"新资料核查"步骤手工上传待核查流量文件。
          </p>
        </>
      ) : (
        <DataSourceUploadBox
          scenario="network_cidds"
          title="选择规则学习数据"
          description="上传用于规则学习的 NetFlow 数据文件（CSV、JSON、TXT 格式）。系统将从此数据中自动发现和提取规则。"
          accept=".csv,.json,.txt"
          note="network-learning-data"
          uploaded={learningSource}
          onUploaded={onLearningSourceChange}
        />
      )}

      <div className="upload-actions">
        <button className="btn btn-primary" onClick={onNext}>
          开始规则学习 →
        </button>
        {(learningSource || !useBuiltIn) && (
          <button className="btn btn-outline" onClick={onClear}>
            清空数据
          </button>
        )}
      </div>
    </div>
  );
}

function NetworkValidationStep({
  uploaded,
  onUploaded,
  requestPayload,
  violations,
  hasValidationResult,
  onResult,
}: {
  uploaded: UploadedDataSource | null;
  onUploaded: (dataSource: UploadedDataSource) => void;
  requestPayload: WorkflowStartPayload;
  violations: Violation[];
  hasValidationResult: boolean;
  onResult: (result: WorkflowJobResult) => void;
}) {
  const [runId, setRunId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const startValidation = () => {
    if (!uploaded) return;
    setRunId(Date.now());
    setRunning(true);
  };

  return (
    <div className="validation-step">
      <DataSourceUploadBox
        scenario="network_cidds"
        title="选择待核查网络资料"
        description="支持 CSV、JSON、TXT、PCAP/PCAPNG 摘要文件。文件会保存并随核查 job 传入；W4 核查引擎当前复用稳定 CIDDS 演示管线。"
        accept=".csv,.json,.txt,.pcap,.pcapng"
        note="network-validation-material"
        uploaded={uploaded}
        onUploaded={onUploaded}
      />
      <div className="workflow-actions">
        <button className="btn btn-primary" disabled={!uploaded || running} onClick={startValidation}>
          {running ? "新资料核查运行中…" : "运行新资料核查"}
        </button>
      </div>
      {runId !== null && (
        <WorkflowLog
          key={`validate-network-${runId}`}
          sequence="validate-network"
          title="新资料核查 · 事件流"
          requestPayload={requestPayload}
          onResult={onResult}
          onDone={() => setRunning(false)}
        />
      )}
      {!uploaded && (
        <EmptyLiveState
          title="请先上传待核查资料"
          detail="选择文件后，页面才会展示规则核查结果；不再直接用内置资料自动核查。"
        />
      )}
      {uploaded && !hasValidationResult && (
        <EmptyLiveState
          title="还没有核查结果"
          detail="资料已上传，但还没有执行核查。点击「运行新资料核查」后，后端 job 会带着 dataSourceId 与 validationDataSourceId 返回违规清单。"
        />
      )}
      {uploaded && hasValidationResult && violations.length > 0 && (
        <ViolationTable violations={violations} sourceLabel={formatUploadedSource(uploaded)} />
      )}
      {uploaded && hasValidationResult && violations.length === 0 && (
        <EmptyLiveState
          title="核查完成，未命中违规"
          detail="本次后端 job 没有返回 violations。可继续进入双轨对比，按问题框生成 A/B 结果。"
        />
      )}
    </div>
  );
}

function ViolationTable({
  violations,
  sourceLabel,
}: {
  violations: Violation[];
  sourceLabel: string;
}) {
  return (
    <div className="violation-panel glass">
      <div className="panel-head">
        <h3>违规清单 · wk3 新流量核查</h3>
        <span className="panel-sub">
          后端 live result · {sourceLabel} · 命中 {violations.length} 条违规
        </span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>行号</th>
              <th>字段</th>
              <th>命中规则</th>
              <th>实际值</th>
              <th>期望值</th>
            </tr>
          </thead>
          <tbody>
            {violations.map((v) => (
              <tr key={`${v.row_index}-${v.rule_id}`} className="row-bad">
                <td className="mono">{v.row_index + 1}</td>
                <td>
                  {v.fields.map((f) => (
                    <span className="field-chip" key={f}>
                      {f}
                    </span>
                  ))}
                </td>
                <td>
                  <span className="rule-ref">{v.rule_id}</span>
                  <em className="rule-ref-text">{v.rule_text}</em>
                </td>
                <td className="mono">
                  {Object.entries(v.observed)
                    .map(([k, val]) => `${k}=${val}`)
                    .join(", ")}
                </td>
                <td className="expected">{v.expected}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="violation-note">
        清单逐行对应 contracts.Violation：行号 / 字段 / 命中规则 / 实际值 / 期望值，可点击规则卡溯源。
      </p>
    </div>
  );
}

type RawNetFlow = Record<string, unknown>;

function rawValue(row: RawNetFlow, ...keys: string[]): unknown {
  for (const key of keys) {
    if (row[key] !== undefined && row[key] !== null) return row[key];
  }
  return undefined;
}

function rawNumber(row: RawNetFlow, fallback: number, ...keys: string[]): number {
  const value = rawValue(row, ...keys);
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

function rawText(row: RawNetFlow, fallback: string, ...keys: string[]): string {
  const value = rawValue(row, ...keys);
  return value === undefined ? fallback : String(value);
}

function toNetFlowRows(
  rows: unknown,
  violations: Violation[] = []
): NetFlowRow[] | null {
  if (!Array.isArray(rows)) return null;
  const byRow = new Map<number, Violation[]>();
  for (const violation of violations) {
    const list = byRow.get(violation.row_index) ?? [];
    list.push(violation);
    byRow.set(violation.row_index, list);
  }
  return rows.map((raw, index) => {
    const row = raw as RawNetFlow;
    const rowViolations = byRow.get(index) ?? [];
    const dstPt = rawNumber(row, 0, "DstPt", "dstPt");
    const dst = rawText(row, "", "DstIpAddr", "dst", "dstIp");
    return {
      no: index + 1,
      duration: rawText(row, "", "Duration", "duration"),
      proto: rawText(row, "", "Proto", "proto"),
      src: rawText(row, "", "SrcIpAddr", "src", "srcIp"),
      dst,
      srcPt: rawNumber(row, 0, "SrcPt", "srcPt"),
      dstPt,
      packets: rawNumber(row, 0, "Packets", "packets"),
      bytes: rawNumber(row, 0, "Bytes", "bytes"),
      flags: rawText(row, "", "Flags", "flags"),
      appProto: rawText(row, dst === "DNS" || dstPt === 53 ? "dns" : "netflow", "AppProto", "appProto"),
      violatedRuleIds: rowViolations.map((v) => v.rule_id),
      badFields: rowViolations.flatMap((v) => v.fields.map((field) => field.toLowerCase())),
      tip: rowViolations.map((v) => v.message_zh).join("；"),
    };
  });
}

function FlowTable({ rows, track }: { rows: NetFlowRow[]; track: "A" | "B" }) {
  return (
    <table className="data-table flow-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Proto</th>
          <th>Src → Dst</th>
          <th>SrcPt</th>
          <th>Packets</th>
          <th>Bytes</th>
          <th>Flags</th>
          <th>App</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const bad = track === "A" && r.violatedRuleIds && r.violatedRuleIds.length > 0;
          const isBadField = (f: string) =>
            track === "A" && r.badFields?.includes(f);
          return (
            <tr key={r.no} className={bad ? "row-bad" : ""} title={bad ? r.tip : undefined}>
              <td className="mono">{r.no}</td>
              <td className={isBadField("proto") ? "cell-bad" : ""}>{r.proto}</td>
              <td className="mono cell-flow">
                {r.src} → {r.dst}
              </td>
              <td className="mono">{r.srcPt}</td>
              <td className={`mono${isBadField("packets") ? " cell-bad" : ""}`}>{r.packets}</td>
              <td className={`mono${isBadField("bytes") ? " cell-bad" : ""}`}>
                {r.bytes.toLocaleString()}
              </td>
              <td className={`mono${isBadField("flags") ? " cell-bad" : ""}`}>{r.flags}</td>
              <td>{r.appProto}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function DualTrackFlows({ dual }: { dual?: DualReport | null }) {
  if (!dual) {
    return (
      <EmptyLiveState
        title="还没有真实双轨结果"
        detail="点击上方「运行实时 A/B 双轨」，等后端 job 完成后再展示 A/B NetFlow。"
      />
    );
  }

  const trackA = toNetFlowRows(dual.track_a.slots?.rows, dual.track_a.violations) ?? [];
  const trackB = toNetFlowRows(dual.track_b.slots?.rows, dual.track_b.violations) ?? [];
  const bLog = dual.track_b.intervention_log ?? [];
  const trackAViolations = dual.track_a.violations.length;
  const trackBViolations = dual.track_b.violations.length;

  return (
    <div className="dual-track">
      <div className="track-col track-a glass">
        <div className="track-head">
          <span className="track-badge badge-a">A 轨 · 裸模型</span>
          <span className="track-verdict bad">{trackAViolations} 条违规</span>
        </div>
        <p className="track-desc">
          qwen2.5 用相同 prompt 生成，照常犯协议 / 物理错误。问题行整行标红，悬浮可见命中规则。
        </p>
        <div className="table-scroll">
          <FlowTable rows={trackA} track="A" />
        </div>
      </div>

      <div className="track-col track-b glass">
        <div className="track-head">
          <span className="track-badge badge-b">B 轨 · NetNomos 约束</span>
          <span className="track-verdict ok">{trackBViolations} 违规</span>
        </div>
        <p className="track-desc">
          LeJIT bundle 按字段拓扑序生成，每步过 Z3。右侧为逐步干预日志。
        </p>
        <div className="track-b-body">
          <div className="table-scroll">
            <FlowTable rows={trackB} track="B" />
          </div>
          <aside className="intervention-log">
            <h4>干预日志</h4>
            <ul>
              {bLog.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    </div>
  );
}

function ReportStep({
  dual,
  sourceLabel,
}: {
  dual?: DualReport | null;
  sourceLabel: string;
}) {
  if (dual) {
    const href = buildReportDownloadHref(dual, sourceLabel);
    return (
      <div className="report-step glass">
        <div className="report-paper is-wide">
          <span className="report-tag">live result · 后端双轨</span>
          <h2>{dual.title}</h2>
          <p className="upload-note">
            资料：{sourceLabel}。问题框请填写要生成几条 NetFlow、要核查哪些规则，以及是否需要给出约束后的合规版本。
          </p>
          <a className="btn btn-outline" href={href} download="network-dual-report.md">
            下载报告 Markdown
          </a>
          <div className="live-report-grid">
            <section>
              <h3>A 轨 · 裸模型</h3>
              <MarkdownBlock text={dual.track_a.markdown} />
            </section>
            <section>
              <h3>B 轨 · NetNomos 约束</h3>
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
      detail="请先在双轨对比步骤运行实时流程。报告生成后，这里会展示预览并提供 Markdown 下载。"
    />
  );
}

function buildReportDownloadHref(dual: DualReport, sourceLabel: string): string {
  const markdown = [
    `# ${dual.title}`,
    "",
    `资料：${sourceLabel}`,
    `建议问题：${NETWORK_SCENARIO_QUESTION}`,
    "",
    "## A 轨 · 裸模型",
    dual.track_a.markdown,
    "",
    "## B 轨 · NetNomos 约束",
    dual.track_b.markdown,
    "",
    "## B 轨干预日志",
    ...dual.track_b.intervention_log.map((line) => `- ${line}`),
  ].join("\n");
  return `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
}
