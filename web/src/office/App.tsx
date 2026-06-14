import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import type { Agent, AgentId, Artifact, ChatMessage, DataSource, RuleGroup, WorkflowEvent } from "./types/domain";
import type { AgentCode, Rule, RuleCard, WorkflowEvent as ForgeWorkflowEvent } from "../types/api";
import {
  fetchWorkflowJob,
  registerOfficeDemoDataSource,
  startOfficeWorkflow,
  startWorkflowJob,
  uploadOfficeDataSource,
  uploadOfficeRuleset,
  waitForWorkflowJob,
  workflowEventsUrl,
} from "../lib/apiClient";
import { useDemo } from "../demo/DemoContext";
import { makeDemoFile, NETWORK_QUESTION, FINANCE_QUESTION, type DemoScenario } from "../demo/demoAssets";
import { autoUpload, makeAbortableDelay, runWithFallback } from "../demo/demoDriver";
import { DUAL_MOCK } from "../demo/demoMocks";
import {
  agents as baseAgents,
  buildDiscoveredGroup,
  initialEvents,
  seedArtifacts,
  seedDataSources,
  seedRuleGroups,
} from "./data/mockData";
import { DataModal } from "./components/DataModal";
import { MemberSettingsModal } from "./components/MemberSettingsModal";
import { OfficeScene } from "./components/OfficeScene";
import { OutputsModal } from "./components/OutputsModal";
import { PacketCapture } from "./components/PacketCapture";
import { PhoneChat } from "./components/PhoneChat";
import { RulesModal } from "./components/RulesModal";
import { Sidebar } from "./components/Sidebar";
import { StatusPanel } from "./components/StatusPanel";

type PanelKind = "rules" | "data" | "outputs" | null;

const AGENT_CODE_TO_OFFICE: Record<AgentCode, AgentId> = {
  A: "supervisor",
  B: "courier",
  C: "analyst",
  D: "validator",
  E: "plugin",
  F: "pm",
};

const F_DEFAULT_PROMPT =
  "你是接入了规则集与企业知识库的产品助理。回答必须先给规则依据，再给可执行步骤，最后标注需验证的数据来源；涉及敏感数据时优先脱敏。";

function kindFromName(name: string): DataSource["kind"] {
  const n = name.toLowerCase();
  if (n.endsWith(".pcap") || n.endsWith(".pcapng")) return "pcap";
  if (n.endsWith(".xlsx") || n.endsWith(".xls")) return "xlsx";
  if (n.endsWith(".pdf")) return "pdf";
  return "csv";
}

function rulesToGroup(rules: Rule[]): RuleGroup {
  return {
    id: "forge-office-rules",
    name: "Forge 后端规则",
    domain: "office_demo",
    rules: rules.map((rule) => ({
      id: rule.rule_id,
      text: rule.text,
      type: rule.kind || "约束",
      enabled: rule.enabled,
      source: rule.source === "learned" ? "learned" : "custom",
      confidence: rule.confidence ?? undefined,
    })),
  };
}

function artifactsFromResult(cards: RuleCard[], dual: unknown): Artifact[] {
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const cardArtifacts = cards.slice(0, 12).map((card) => ({
    id: `forge-card-${card.rule_id}`,
    title: card.title_zh || `规则卡 ${card.rule_id}`,
    producer: "validator" as AgentId,
    kind: "规则卡",
    time,
    preview: `${card.explanation_zh}\n\n${card.formula_text}\n\n引用：${card.citation}`,
  }));
  if (!dual || typeof dual !== "object") return cardArtifacts;
  const report = dual as { title?: string; track_a?: { markdown?: string }; track_b?: { markdown?: string } };
  return [
    {
      id: "forge-dual-report",
      title: report.title || "Forge 双轨报告",
      producer: "plugin",
      kind: "双轨报告",
      time,
      preview: [report.track_a?.markdown, report.track_b?.markdown].filter(Boolean).join("\n\n---\n\n"),
    },
    ...cardArtifacts,
  ];
}

export default function App() {
  const [rulesLoaded, setRulesLoaded] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [events, setEvents] = useState<WorkflowEvent[]>(initialEvents);
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [phoneConversation, setPhoneConversation] = useState<AgentId | "group">("group");
  const [phoneGroupChat, setPhoneGroupChat] = useState(false); // 一键演示结束时直接进群聊看结果
  const [packetOpen, setPacketOpen] = useState(false);
  const [panel, setPanel] = useState<PanelKind>(null);
  const [settingsAgent, setSettingsAgent] = useState<AgentId | null>(null);
  const [ruleGroups, setRuleGroups] = useState<RuleGroup[]>(seedRuleGroups);
  const [dataSources, setDataSources] = useState<DataSource[]>(seedDataSources);
  const [artifacts, setArtifacts] = useState<Artifact[]>(seedArtifacts);
  const [fConfig, setFConfig] = useState<{ files: string[]; prompt: string }>({ files: [], prompt: F_DEFAULT_PROMPT });
  const [backendError, setBackendError] = useState<string | null>(null);
  const [rulesetId, setRulesetId] = useState<string | undefined>();
  const [dataSourceId, setDataSourceId] = useState<string | undefined>();
  const [workflowJobId, setWorkflowJobId] = useState<string | null>(null);
  const [workflowRunning, setWorkflowRunning] = useState(false);
  const ruleSequence = useRef(0);
  const eventSequence = useRef(0);
  const bootstrapped = useRef(false);

  // —— 一键傻瓜演示（办公室）——
  const { mode, officeScenario, runToken, startDemo, setStatus, setOfficeSummary } = useDemo();
  const [chatInjections, setChatInjections] = useState<ChatMessage[]>([]);
  const injectSeq = useRef(0);
  const demoAbortRef = useRef<AbortController | null>(null);
  const lastOfficeRun = useRef(0);

  const agents = useMemo<Agent[]>(
    () =>
      baseAgents.map((agent) => {
        if (agent.id === "supervisor" && rulesLoaded) return { ...agent, status: "supervising" };
        if (agent.id === "courier" && dataLoaded) return { ...agent, status: "delivering" };
        return agent;
      }),
    [rulesLoaded, dataLoaded]
  );

  function nowLabel() {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function addEvent(event: Omit<WorkflowEvent, "id" | "time">) {
    setEvents((current) => [
      { ...event, id: `evt-${Date.now()}-${eventSequence.current++}`, time: nowLabel() },
      ...current,
    ]);
  }

  function showBackendError(stage: string, error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    setBackendError(`${stage}：${message}`);
    addEvent({
      agent: "supervisor",
      stage,
      status: "blocked",
      description: `Forge 后端调用失败：${message}`,
    });
  }

  function ingestWorkflowResult(result: Awaited<ReturnType<typeof fetchWorkflowJob>>["result"]) {
    if (!result) return;
    if (result.rules?.length) {
      const group = rulesToGroup(result.rules);
      setRuleGroups((groups) => [group, ...groups.filter((item) => item.id !== group.id)]);
      setRulesLoaded(true);
    }
    const nextArtifacts = artifactsFromResult(result.cards ?? [], result.dual);
    if (nextArtifacts.length) {
      setArtifacts((current) => [
        ...nextArtifacts.filter((item) => !current.some((existing) => existing.id === item.id)),
        ...current,
      ]);
    }
  }

  async function syncWorkflowJob(jobId: string) {
    try {
      const job = await fetchWorkflowJob(jobId);
      ingestWorkflowResult(job.result);
      if (job.error) showBackendError("workflow result", job.error);
    } catch (error) {
      showBackendError("workflow result", error);
    }
  }

  async function triggerWorkflow(payload: { dataSourceId?: string } = {}) {
    setWorkflowRunning(true);
    try {
      const nextDataSourceId = payload.dataSourceId ?? dataSourceId;
      const jobId = await startOfficeWorkflow({
        dataSourceId: nextDataSourceId,
        validationDataSourceId: nextDataSourceId,
      });
      setWorkflowJobId(jobId);
      setBackendError(null);
      addEvent({
        agent: "supervisor",
        stage: "office_demo workflow",
        status: "running",
        description: `已触发 Forge workflow：${jobId}`,
      });
    } catch (error) {
      showBackendError("office_demo workflow", error);
    } finally {
      setWorkflowRunning(false);
    }
  }

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    if (mode === "office") return; // 一键演示由 runOfficeDemo 负责触发，避免重复 office_demo
    void triggerWorkflow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // —— 一键演示：把一句话往「群聊」里塞（PhoneChat 去重合并）——
  function appendGroupMessage(sender: AgentId | "system", content: string, constrained = false) {
    const msg: ChatMessage = {
      id: `demo-grp-${runToken}-${injectSeq.current++}`,
      conversationId: "group",
      sender,
      content,
      time: nowLabel(),
      constrained,
    };
    setChatInjections((cur) => [...cur, msg]);
  }

  // —— 一键演示：执行所选场景，跑「专用场景管线」(network_cidds/finance_v1，与两个 demo 页同一套)，
  //    真实结果同时喂【左侧产出物/规则集】+【手机群聊】；超时/失败统一回落内置 mock，演示永不卡死。——
  async function runOfficeDemo(scenario: DemoScenario) {
    demoAbortRef.current?.abort();
    const ac = new AbortController();
    demoAbortRef.current = ac;
    const delay = makeAbortableDelay(ac.signal);
    const label = scenario === "network" ? "网络流量" : "财务报表";
    const seq = scenario === "network" ? "learn-network" : "learn-finance";
    const question = scenario === "network" ? NETWORK_QUESTION : FINANCE_QUESTION;
    const file = makeDemoFile(scenario);

    try {
      setPhoneOpen(false);
      appendGroupMessage("supervisor", `【一键演示 · ${label}】主管A接入 Forge 规则集，监管扫描开始。`);
      await loadRules({ triggerBackend: false }); // 视觉：主管「监管中」+ 规则集登记（演示自跑专用管线，不触发 office_demo）
      await delay(1300);

      appendGroupMessage("courier", `快递B收到《${file.name}》，开始往返派送数据到分析工位。`);
      const ds = await autoUpload(scenario); // 真实上传到 network_cidds/finance_v1（失败回落 mock 数据源）
      await loadData(file.name, file, { triggerBackend: false, dataSourceId: ds.dataSourceId }); // 视觉：数据「已加载」+ 自发现组（复用上传 id，不二次上传）
      appendGroupMessage("analyst", "员工C从已加载数据抽取候选规则，员工D规则学习进行中…");
      if (ac.signal.aborted) return;

      // 真实跑专用场景管线：单 job 一次性返回 rules/cards/violations/dual；超时/失败回落 mock
      const result = await runWithFallback(
        `office-${scenario}`,
        async () => {
          const jobId = await startWorkflowJob(seq, {
            dataSourceId: ds.dataSourceId,
            validationDataSourceId: ds.dataSourceId,
            question,
            reportPrompt: question,
          });
          const job = await waitForWorkflowJob(jobId, { attempts: 36, delayMs: 600 });
          if (!job.result || job.status === "failed") throw new Error("office workflow 无结果");
          return job.result;
        },
        () => DUAL_MOCK[scenario],
        23000
      );
      if (ac.signal.aborted) return;

      // 真实结果喂左侧面板（产出物/规则集），受控聊天绑到本场景规则集
      ingestWorkflowResult(result);
      if (result.ruleset_id) setRulesetId(result.ruleset_id);

      const dual = result.dual ?? DUAL_MOCK[scenario].dual!;
      const learnedRules = result.rules?.length ?? 0;
      const cardCount = result.cards?.length ?? 0;
      const violations = result.violations?.length ?? dual.track_a.violations.length;
      const trackA = dual.track_a.violations.length;
      const trackB = dual.track_b.violations.length;

      appendGroupMessage("analyst", `员工D 学得 ${learnedRules} 条规则 / ${cardCount} 张规则卡。`);
      await delay(1300);
      appendGroupMessage("validator", `员工D对新资料逐行核查：检出 ${violations} 处违规（已标注行号与字段）。`);
      await delay(1300);
      appendGroupMessage("plugin", `员工E实时 A/B 双轨：A轨(裸模型) ${trackA} 处违规，B轨(规则约束) ${trackB} 违规。`);
      await delay(1300);
      appendGroupMessage("pm", `产品经理F汇总《${dual.title}》：B轨已按规则修正/标注，可交付，详见左侧产出物。`, true);
      if (ac.signal.aborted) return;

      setOfficeSummary({
        scenario,
        learnedRules,
        cardCount,
        violations,
        trackAViolations: trackA,
        trackBViolations: trackB,
        dualTitle: dual.title,
      });
      setPhoneConversation("group");
      setPhoneGroupChat(true);
      setPhoneOpen(true);
      setStatus("done");
    } catch {
      /* abort：被新的一轮演示打断，静默退出 */
    }
  }

  // —— 一键演示：mode=office 且 runToken 自增即触发本场景脚本 ——
  useEffect(() => {
    if (mode !== "office" || !officeScenario) return;
    if (runToken === lastOfficeRun.current) return;
    lastOfficeRun.current = runToken;
    bootstrapped.current = true; // 双保险：跳过 bootstrap 的自动 triggerWorkflow
    setChatInjections([]);
    injectSeq.current = 0;
    void runOfficeDemo(officeScenario);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, officeScenario, runToken]);

  useEffect(() => {
    if (!workflowJobId) return;
    const source = new EventSource(workflowEventsUrl(workflowJobId));
    source.addEventListener("workflow", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as ForgeWorkflowEvent;
        addEvent({
          agent: AGENT_CODE_TO_OFFICE[payload.agent] ?? "supervisor",
          stage: payload.stage,
          status: payload.status,
          description: payload.description,
        });
        if (payload.status === "done") void syncWorkflowJob(workflowJobId);
      } catch (error) {
        showBackendError("workflow event parse", error);
      }
    });
    source.onerror = () => {
      void syncWorkflowJob(workflowJobId);
      source.close();
    };
    return () => source.close();
  }, [workflowJobId]);

  // —— 规则集（分组）——
  function toggleRule(groupId: string, ruleId: string) {
    setRuleGroups((groups) =>
      groups.map((g) =>
        g.id === groupId
          ? { ...g, rules: g.rules.map((r) => (r.id === ruleId ? { ...r, enabled: !r.enabled } : r)) }
          : g
      )
    );
  }

  function addRule(groupId: string, text: string, type: string) {
    const id = `U${String(++ruleSequence.current).padStart(2, "0")}`;
    setRuleGroups((groups) =>
      groups.map((g) =>
        g.id === groupId ? { ...g, rules: [...g.rules, { id, text, type, enabled: true, source: "custom" }] } : g
      )
    );
  }

  function addGroup(name: string, domain: string) {
    const id = `grp-${Date.now()}`;
    setRuleGroups((groups) => [...groups, { id, name, domain, rules: [] }]);
  }

  // —— 主管接入规则集 / 快递上传数据 ——
  // opts.triggerBackend=false：只做视觉/登记，不触发后端 office_demo（一键演示自己跑专用场景管线）
  async function loadRules(opts: { triggerBackend?: boolean } = {}) {
    try {
      const result = await uploadOfficeRuleset();
      setRulesetId(result.rulesetId);
      setBackendError(null);
      if (!rulesLoaded) {
      setRulesLoaded(true);
        addEvent({ agent: "supervisor", stage: "规则集接入", status: "done", description: `主管A已接入 Forge 规则集 ${result.rulesetId}（${result.ruleCount} 条），监管扫描开始。` });
      addEvent({ agent: "validator", stage: "验证排队", status: "running", description: "规则集验证员工D开始准备样例与反例。" });
    }
      if (opts.triggerBackend !== false) void triggerWorkflow();
    } catch (error) {
      showBackendError("规则集接入", error);
    }
  }

  // opts.dataSourceId：复用外部已上传的数据源 id（一键演示用 autoUpload 上传到专用场景，避免二次上传）
  async function loadData(filename: string, file?: File, opts: { triggerBackend?: boolean; dataSourceId?: string } = {}) {
    const name = filename === "demo-pcap-csv-source" ? "demo-pcap-csv-source.csv" : filename;
    try {
      let dataSourceId = opts.dataSourceId;
      let path = "Forge 已登记";
      if (!dataSourceId) {
        const result = file ? await uploadOfficeDataSource(file) : await registerOfficeDemoDataSource(name);
        dataSourceId = result.dataSourceId;
        path = result.path || "Forge 已登记";
      }
      setDataSourceId(dataSourceId);
      setBackendError(null);
    setDataSources((cur) =>
      cur.some((s) => s.name === name)
        ? cur
          : [{ id: dataSourceId, name, kind: kindFromName(name), meta: path, status: "已加载", source: "upload" }, ...cur]
    );
    if (!dataLoaded) {
      setDataLoaded(true);
      addEvent({ agent: "courier", stage: "数据派送", status: "running", description: `快递B已接收 ${name}，开始向分析工位往返派送数据。` });
      addEvent({ agent: "analyst", stage: "规则发现", status: "running", description: "数据分析员工C开始从已加载数据中抽取候选规则。" });

      // 员工D 从数据自发现候选规则 → 自动生成「自发现规则组」（疑似巧合默认不启用，待人工勾选）
      const group = buildDiscoveredGroup(name, kindFromName(name));
      setRuleGroups((cur) => (cur.some((g) => g.id === group.id) ? cur : [group, ...cur]));
      const usable = group.rules.filter((r) => !r.coincidence).length;
      const suspect = group.rules.length - usable;
      addEvent({
        agent: "validator",
        stage: "规则自发现",
        status: "done",
        description: `员工D 从 ${name} 自发现 ${group.rules.length} 条候选规则：${usable} 条可用，${suspect} 条疑似巧合待确认。`,
      });
      addEvent({ agent: "plugin", stage: "插件制品等待", status: "pending", description: "规则插件制作员工E等待人工确认后的规则集。" });

      // 产出物：员工D 的自发现规则候选
      const preview = group.rules
        .map((r) => `${r.id} ${r.text}\n  置信 ${r.confidence?.toFixed(2)}　${r.coincidence ? "疑似巧合 → 建议 drop" : "建议 keep"}`)
        .join("\n\n");
      setArtifacts((cur) => [
        {
          id: `art-disc-${Date.now()}`,
          title: `自发现规则候选 · ${group.domain}`,
          producer: "validator",
          kind: "规则卡",
          time: nowLabel(),
          preview,
        },
        ...cur,
      ]);
    }
      if (opts.triggerBackend !== false) void triggerWorkflow({ dataSourceId });
    } catch (error) {
      showBackendError("数据源接入", error);
    }
  }

  // —— 员工F 知识库配置 ——
  function addRagFiles(list: FileList | null) {
    if (!list || !list.length) return;
    const names = Array.from(list).map((f) => f.name);
    setFConfig((c) => ({ ...c, files: [...c.files, ...names].slice(0, 20) }));
  }
  function removeRagFile(name: string) {
    setFConfig((c) => ({ ...c, files: c.files.filter((f) => f !== name) }));
  }

  // —— 交互路由 ——
  function openSettings(agentId: AgentId) {
    setSettingsAgent(agentId);
  }

  function handleNav(key: string) {
    if (key === "rules") setPanel("rules");
    else if (key === "data") setPanel("data");
    else if (key === "outputs") setPanel("outputs");
    else if (key === "phone") {
      setPhoneGroupChat(false);
      setPhoneConversation("group");
      setPhoneOpen(true);
    } else {
      setPanel(null);
      setSettingsAgent(null);
    }
  }

  const settingsAgentObj = settingsAgent ? agents.find((a) => a.id === settingsAgent) ?? null : null;

  return (
    <div className="app">
      <AnimatePresence mode="wait">
        {packetOpen ? (
          <PacketCapture open={packetOpen} onBack={() => setPacketOpen(false)} />
        ) : (
          <div className="workspace">
            {backendError ? (
              <div className="office-backend-banner" role="alert">
                <strong>Forge 后端状态异常</strong>
                <span>{backendError}</span>
              </div>
            ) : workflowRunning ? (
              <div className="office-backend-banner office-backend-banner--ok">
                <strong>Forge workflow</strong>
                <span>正在触发 office_demo workflow...</span>
              </div>
            ) : null}
            <Sidebar
              agents={agents}
              activeAgentId={settingsAgent}
              onSelectAgent={openSettings}
              onNav={handleNav}
            />
            <OfficeScene
              agents={agents}
              rulesLoaded={rulesLoaded}
              dataLoaded={dataLoaded}
              onAgentDoubleClick={openSettings}
              onLaunchDemo={(scenario) => startDemo("office", scenario)}
            />
            <StatusPanel
              agents={agents}
              events={events}
              ruleGroups={ruleGroups}
              rulesLoaded={rulesLoaded}
              dataLoaded={dataLoaded}
              onOpenPacket={() => dataLoaded && setPacketOpen(true)}
              onOpenRules={() => setPanel("rules")}
            />
            <PhoneChat
              open={phoneOpen}
              focusConversation={phoneConversation}
              fConfig={fConfig}
              rulesetId={rulesetId}
              injectedMessages={chatInjections}
              groupAsChat={phoneGroupChat}
              onOpen={() => {
                setPhoneGroupChat(false);
                setPhoneConversation("group");
                setPhoneOpen(true);
              }}
              onClose={() => setPhoneOpen(false)}
            />
          </div>
        )}
      </AnimatePresence>

      <RulesModal
        open={panel === "rules"}
        groups={ruleGroups}
        onClose={() => setPanel(null)}
        onToggle={toggleRule}
        onAddRule={addRule}
        onAddGroup={addGroup}
      />

      <DataModal open={panel === "data"} sources={dataSources} onClose={() => setPanel(null)} />

      <OutputsModal open={panel === "outputs"} artifacts={artifacts} onClose={() => setPanel(null)} />

      <MemberSettingsModal
        open={settingsAgent !== null}
        agent={settingsAgentObj}
        rulesLoaded={rulesLoaded}
        dataLoaded={dataLoaded}
        fConfig={fConfig}
        onClose={() => setSettingsAgent(null)}
        onLoadRules={loadRules}
        onLoadData={loadData}
        onOpenPacket={() => {
          setSettingsAgent(null);
          setPacketOpen(true);
        }}
        onAddRagFiles={addRagFiles}
        onRemoveRagFile={removeRagFile}
        onPrompt={(p) => setFConfig((c) => ({ ...c, prompt: p }))}
      />
    </div>
  );
}
