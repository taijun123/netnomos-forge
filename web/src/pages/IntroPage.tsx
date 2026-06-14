import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Brain,
  Building2,
  Calculator,
  ChevronRight,
  CheckCircle,
  ClipboardCheck,
  Code2,
  Database,
  FileCheck,
  FileText,
  GitMerge,
  Hash,
  Landmark,
  Network,
  Plug,
  Receipt,
  Scale,
  Settings,
  Shield,
  SquareFunction,
  Star,
  Truck,
  Unlink,
  Upload,
  UserCheck,
  XCircle,
  Zap,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import type { Route } from "../components/TopNav";

const GITHUB_URL = "https://github.com/taijun123/netnomos-forge";

type SessionRow = {
  source: string;
  target: string;
  proto: string;
  port: string;
  packets: string;
  bytes: string;
  flags: string;
  verdict: string;
};

type ScenarioResponse =
  | string
  | {
      summary: string;
      rows: SessionRow[];
    };

type Scenario = {
  icon: ReactNode;
  label: string;
  user: string;
  bare: ScenarioResponse;
  standard: ScenarioResponse;
  custom: ScenarioResponse;
};

const heroFeatures = [
  { icon: <Zap size={18} />, title: "即插即用", desc: "无需训练 LLM，标准规则包开箱即用，分钟级接入现有 Agent 应用" },
  { icon: <Unlink size={18} />, title: "规则与模型完全解耦", desc: "规则独立于模型版本迭代，升级模型无需重写规则逻辑" },
  { icon: <Building2 size={18} />, title: "企业级定制能力", desc: "支持自学习规则，从企业历史数据中提炼专属约束，越用越精准" },
];

const definitionPoints = [
  { wrong: "不是「更聪明的模型」", right: "是「给任何模型装的安检关卡」" },
  { wrong: "不是一次性微调", right: "是可随时替换的「规则配置文件」" },
  { wrong: "不是黑箱打分", right: "是逐条规则编号 + SMT 求解的确定性判断" },
];

const techSteps = [
  { num: "01", icon: <Database size={20} />, title: "数据与语义", desc: "样本·字段·类型·角色" },
  { num: "02", icon: <SquareFunction size={20} />, title: "语法 Γ", desc: "限定谓词搜索空间" },
  { num: "03", icon: <Hash size={20} />, title: "谓词落地", desc: "p0, p1… 支持率" },
  { num: "04", icon: <BookOpen size={20} />, title: "规则学习", desc: "最小 hitting set" },
  { num: "05", icon: <Calculator size={20} />, title: "SMT 求解", desc: "SAT / UNSAT 可行性" },
  { num: "06", icon: <Code2 size={20} />, title: "逐步解码", desc: "过滤无效 token" },
  { num: "07", icon: <CheckCircle size={20} />, title: "合规输出", desc: "规则合规结果" },
];

const techHighlights = [
  {
    dot: "#a78bfa",
    title: "规则来自数据",
    desc: "把样本看作隐藏约束的可行解；先生成候选谓词，再找到所有样本一致的最强规则。",
  },
  {
    dot: "#86efac",
    title: "规则可审计可替换",
    desc: "人工/LLM 只需选定找出的有效规则 C'；规则更新不需要重新训练模型。",
  },
  {
    dot: "#fca5a5",
    title: "即时逻辑执行",
    desc: "用 Z3/SMT 验证候选值和数字前缀，只放行仍有可行完成路径的 token。",
  },
];

const painCards = [
  { icon: <AlertTriangle size={16} />, title: "单条记录无法识别隐含错误", desc: "数字本身合法，但与上下文逻辑矛盾，裸模型无法感知" },
  { icon: <GitMerge size={16} />, title: "跨期/跨表数据关联缺失", desc: "涉及多期对比或多表关联时，LLM 容易忽略隐性约束" },
  { icon: <FileCheck size={16} />, title: "数据与报表表述不一致", desc: "正文叙述与表格数字出现偏差，难以人工逐一核对" },
];

const twoModeRows = [
  { dim: "规则来源", standard: "内置行业标准规则库", enterprise: "企业历史数据自动提炼" },
  { dim: "上手成本", standard: "零配置，即插即用", enterprise: "需上传历史数据（一次性）" },
  { dim: "适用场景", standard: "通用合规、行业标准核查", enterprise: "特定业务口径、内部标准" },
  { dim: "覆盖范围", standard: "广泛行业规则", enterprise: "精准匹配企业自身规则" },
  { dim: "典型回答", standard: "符合行业标准吗？", enterprise: "符合你的标准吗？" },
];

const personas = [
  { icon: <Settings size={18} />, title: "业务规则管理员", desc: "管理和维护规则库，确保业务合规" },
  { icon: <Code2 size={18} />, title: "AI 应用开发者", desc: "快速集成规则引擎，提升应用可靠性" },
  { icon: <ClipboardCheck size={18} />, title: "审计合规人员", desc: "自动化核查，减少人工审计负担" },
  { icon: <BarChart3 size={18} />, title: "平台运营管理者", desc: "监控 AI 输出质量，降低业务风险" },
];

const scenarios: Scenario[] = [
  {
    icon: <Receipt size={15} />,
    label: "财务报表核查",
    user: "帮我整理这份 Q1 财报数据，并生成一段可提交的报告摘要。",
    bare: "Q1 净利润 125 万元，毛利率 65%，所有者权益 13,200 千元，各项指标均正常，建议按期提交。",
    standard: "Q1 净利润 125 万元，毛利率 65%，所有者权益已修正为 12,900 千元（检测到差额 8 万元，疑似数据问题），其余指标符合行业标准。",
    custom: "Q1 净利润 125 万元，所有者权益 12,900 千元（差额 8 万元，已触发规则 R12）。毛利率 65% 处于历史区间上限，命中专属规则 C05，建议复核采购成本。",
  },
  {
    icon: <Network size={15} />,
    label: "网络分析",
    user: "分析这批 1h 遥控网络流量，细化到关键会话，并判断是否存在异常。",
    bare: {
      summary: "流量整体正常，主要集中在 DNS 查询、HTTPS 访问和遥控网关通信，未发现明显异常。",
      rows: [
        { source: "192.168.70.18", target: "8.8.8.8", proto: "TCP", port: "443", packets: "12", bytes: "8.9KB", flags: "-", verdict: "正常" },
        { source: "192.168.10.42", target: "10.0.0.53", proto: "UDP", port: "53", packets: "2", bytes: "200KB", flags: ".AP.S.", verdict: "正常" },
      ],
    },
    standard: {
      summary: "发现 1 条协议级异常：UDP 流量不应携带 TCP Flags；同时 Bytes/Packets 比例超过物理上界。",
      rows: [
        { source: "192.168.10.42", target: "10.0.0.53", proto: "UDP", port: "53", packets: "2", bytes: "200KB", flags: ".AP.S.", verdict: "异常" },
        { source: "192.168.70.18", target: "8.8.8.8", proto: "TCP", port: "443", packets: "12", bytes: "8.9KB", flags: "-", verdict: "未命中规则" },
      ],
    },
    custom: {
      summary: "发现 2 类异常：协议字段违规；设备子网绕过遥控网关直连公网，违反企业遥控链路规则。",
      rows: [
        { source: "192.168.70.18", target: "8.8.8.8", proto: "TCP", port: "443", packets: "12", bytes: "8.9KB", flags: "-", verdict: "命中 R07" },
        { source: "10.88.12.10", target: "192.168.70.18", proto: "TCP", port: "8443", packets: "96", bytes: "86.6KB", flags: "-", verdict: "合规" },
      ],
    },
  },
  {
    icon: <Scale size={15} />,
    label: "企业合规",
    user: "审查这份合同，检查是否符合最新合规要求。",
    bare: "合同条款完整，包含甲乙方信息、违约条款及保密协议，整体符合标准格式。",
    standard: "发现第 3.2 条款与行业合规标准 GF-2024 第 8 条存在冲突，建议修订责任限额约定。",
    custom: "第 3.2 条款触发合规风险 R15，且与企业历史合同模板存在偏差（规则 E03）。建议同步法务部门复核。",
  },
  {
    icon: <Truck size={15} />,
    label: "供应链排程",
    user: "根据当前库存和订单，给出本周供应链排程建议。",
    bare: "建议优先处理 A、B、C 三类订单，预计本周可完成 85% 的交付目标，物流安排正常。",
    standard: "检测到零件 X 库存低于安全阈值（规则 S07），建议紧急补货，否则将影响 C 类订单交付率。",
    custom: "零件 X 不足触发预警（规则 S07），同时命中历史延误模式 E11。相似情况下有 73% 概率造成周期性延迟，建议提前 2 天启动备货。",
  },
  {
    icon: <Landmark size={15} />,
    label: "信贷审批",
    user: "评估这位申请人的信贷风险，给出建议额度。",
    bare: "申请人信用评分 720 分，收入稳定，建议授信额度 15 万元，风险等级低。",
    standard: "信用评分 720 分通过基础阈值，但负债收入比 0.62 超出行业标准（规则 L03），建议调整额度至 10 万元。",
    custom: "负债收入比触发规则 L03，同时命中企业专属风控规则 R09。该类客户历史坏账率偏高，建议额度不超过 8 万元并增设还款提醒。",
  },
];

const engineRows = [
  { level: "01", name: "核心引擎 API", desc: "提供规则校验、SMT 求解的核心能力，以 API 形式对外输出，支持私有化部署与云端调用", status: "已实现", tone: "green" },
  { level: "02", name: "标准规则包", desc: "覆盖金融报表、合规申报、供应链排程等行业通用规则，开箱即用，持续扩充", status: "已实现", tone: "green" },
  { level: "03", name: "自定义规则学习", desc: "从企业历史数据中自动提炼专属规则，支持人工审核确认，越用越精准", status: "内测中", tone: "yellow" },
  { level: "04", name: "企业私有部署", desc: "支持完整私有化部署，数据不出域，满足金融、政务等高合规要求场景", status: "规划中", tone: "purple" },
  { level: "05", name: "规则市场/生态", desc: "开放规则包交易市场，第三方机构可发布行业规则包，构建规则生态共同体", status: "规划中", tone: "purple" },
];

export function IntroPage({ onNavigate }: { onNavigate: (route: Route) => void }) {
  const [activeScenario, setActiveScenario] = useState(0);
  const active = scenarios[activeScenario];

  const scrollTo = (id: string) => document.querySelector(id)?.scrollIntoView({ behavior: "smooth" });

  return (
    <div className="home-page">
      <div className="home-ambient" aria-hidden>
        <span className="home-glow home-glow-a" />
        <span className="home-glow home-glow-b" />
        <span className="home-glow home-glow-c" />
      </div>

      <section className="home-hero" id="hero">
        <div className="home-hero-content">
          <Pill tone="purple">
            <Shield size={12} />
            NetNomos Forge · 规则即决策的 AI 层
          </Pill>
          <h1>
            用规则约束AI
            <span>让每一次生成都可信</span>
          </h1>
          <p>
            上传你的合规数据/标准，NetNomos Forge 自动学习其中规则，再用 SMT 约束确保每一次输出，用你的规则约束 AI 生成结果的真实性。
          </p>
          <div className="home-feature-grid">
            {heroFeatures.map((item) => (
              <Card className="home-feature-card" key={item.title}>
                <span>{item.icon}</span>
                <strong>{item.title}</strong>
                <small>{item.desc}</small>
              </Card>
            ))}
          </div>
          <div className="home-hero-actions">
            <button className="home-primary-btn" type="button" onClick={() => onNavigate("workspace")}>
              联系我们的产品 +
            </button>
            <button className="home-secondary-btn" type="button" onClick={() => scrollTo("#definition")}>
              产品详细介绍
            </button>
          </div>
        </div>
      </section>

      <section className="home-section home-definition" id="definition">
        <div className="home-definition-grid">
          <div>
            <SectionLabel tone="cyan">产品核心定义</SectionLabel>
            <h2>不改模型，只加规则。让 LLM 生成的报告与数据零违规。</h2>
            <p>
              NetNomos Forge 是一个叠加在任意 LLM API 之上的「规则强约束层」。你可以把它理解为 Constraint Enforcement Layer：它不改模型本身，而是在生成路径上加入规则学习、语义过滤与 SMT 可证明约束。
            </p>
            <div className="home-definition-points">
              {definitionPoints.map((item) => (
                <div key={item.right}>
                  <span className="is-wrong">
                    <XCircle size={14} />
                    <s>{item.wrong}</s>
                  </span>
                  <span className="is-right">
                    <CheckCircle size={14} />
                    <strong>{item.right}</strong>
                  </span>
                </div>
              ))}
            </div>
          </div>
          <Architecture />
        </div>
      </section>

      <TechPrinciples />

      <section className="home-section home-pain" id="pain">
        <div className="home-section-head is-centered">
          <SectionLabel tone="purple">用户痛点场景</SectionLabel>
          <h2>
            高精确度场景中，
            <span>普通 LLM 的输出看似合理，但经不起推敲。</span>
            <em>我们可以解决这一问题。</em>
          </h2>
          <p>NetNomos Forge 相当于 AI 输出上一道智能校核关，连续输出生成报告均经过规则校验，无需人工介入。</p>
        </div>
        <PainComparison />
        <div className="home-pain-grid">
          {painCards.map((item) => (
            <Card className="home-pain-card" key={item.title}>
              <span>{item.icon}</span>
              <strong>{item.title}</strong>
              <small>{item.desc}</small>
            </Card>
          ))}
        </div>
      </section>

      <section className="home-section home-modes" id="modes">
        <div className="home-section-head is-centered">
          <h2>两种模式，按需选择</h2>
          <p>标准版面向行业通用规则，开箱即用；企业版基于你自己的历史数据学习专属规则，更适合你的业务场景。</p>
        </div>
        <TwoModes />
        <p className="home-mode-summary">
          标准版回答「符合行业标准吗？」；企业版回答「<span>符合你的标准吗？</span>」
        </p>
        <ModeTable />
        <button className="home-primary-btn home-centered-btn" type="button" onClick={() => scrollTo("#demo")}>
          查看具体场景 +
        </button>
      </section>

      <section className="home-section home-scenarios" id="demo">
        <div className="home-section-head is-centered">
          <h2>为不同行业场景，装上一道规则核查关卡</h2>
          <p>选择你的领域，看看同一个问题，AI 会给出怎样不同的回答。</p>
        </div>
        <PersonaGrid />
        <div className="home-scenario-tabs" role="tablist" aria-label="行业场景">
          {scenarios.map((scenario, index) => (
            <button
              key={scenario.label}
              className={activeScenario === index ? "is-active" : ""}
              type="button"
              role="tab"
              aria-selected={activeScenario === index}
              onClick={() => setActiveScenario(index)}
            >
              {scenario.icon}
              {scenario.label}
            </button>
          ))}
        </div>
        <ScenarioChat scenario={active} />
      </section>

      <section className="home-section home-engine" id="engine">
        <div className="home-section-head is-centered">
          <h2>从核心引擎到规则生态：五层商业化落地路径</h2>
        </div>
        <EngineTable />
        <p className="home-engine-note">
          五层路径从基础能力到生态开放逐步演进，核心引擎提供技术壁垒，规则包市场构建生态护城河，企业部署与自学习能力打通大客户商业化通道。
        </p>
        <a className="home-primary-btn home-centered-btn" href={GITHUB_URL} target="_blank" rel="noreferrer">
          联系我们了解更多 +
        </a>
        <p className="home-github-note">目前处于早期接入阶段，欢迎共建合规 AI 基础设施</p>
      </section>

      <footer className="home-footer">© 2025 NetNomos Forge · 规则即决策的 AI 层</footer>
    </div>
  );
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`home-card ${className}`}>{children}</div>;
}

function Pill({ children, tone }: { children: ReactNode; tone: "cyan" | "red" | "purple" }) {
  return <span className={`home-pill is-${tone}`}>{children}</span>;
}

function SectionLabel({ children, tone }: { children: ReactNode; tone: "cyan" | "red" | "purple" }) {
  return <div className={`home-section-label is-${tone}`}>{children}</div>;
}

function TechPrinciples() {
  return (
    <section className="home-section home-tech" id="tech">
      <div className="home-tech-inner">
        <div className="home-section-head is-centered">
          <SectionLabel tone="purple">技术原理</SectionLabel>
          <h2>让逻辑成为生成模型的控制层</h2>
          <p>从历史样本中学习可审计规则，并在推理时逐 token 拦截不合规输出</p>
        </div>

        <div className="home-tech-pipeline" aria-label="技术原理流程">
          {techSteps.map((step, index) => (
            <div className="home-tech-step-wrap" key={step.num}>
              <div className="home-tech-step">
                <strong>{step.num}</strong>
                <span>{step.icon}</span>
                <b>{step.title}</b>
                <small>{step.desc}</small>
              </div>
              {index < techSteps.length - 1 && <ChevronRight className="home-tech-arrow" size={16} aria-hidden />}
            </div>
          ))}
        </div>

        <div className="home-tech-highlights">
          {techHighlights.map((item) => (
            <Card className="home-tech-card" key={item.title}>
              <div>
                <span style={{ background: item.dot }} />
                <strong>{item.title}</strong>
              </div>
              <p>{item.desc}</p>
            </Card>
          ))}
        </div>

        <div className="home-tech-note">核心：统计模型负责「像真实数据」，符号规则负责「必然正确」。</div>
      </div>
    </section>
  );
}

function Architecture() {
  return (
    <Card className="home-arch-card">
      <div className="home-arch-layer">
        <small>你现有的</small>
        <strong>LLM / Agent 应用</strong>
        <em>不改动</em>
      </div>
      <Arrow label="叠加" />
      <div className="home-arch-layer is-active">
        <strong>NetNomos Forge</strong>
        <span>规则学习 → 语义过滤 → SMT 执行</span>
      </div>
      <Arrow label="加载" />
      <div className="home-arch-pack-grid">
        <div>
          <small>标准规则包</small>
          <span>财务 / 供应链 / 工业</span>
        </div>
        <div>
          <small>自定义规则包</small>
          <span>从你的数据中学习</span>
        </div>
      </div>
      <div className="home-arch-note">规则编号 + 版本号 + 输入哈希 → 可审计追溯</div>
    </Card>
  );
}

function Arrow({ label }: { label: string }) {
  return (
    <div className="home-arch-arrow">
      <span>{label}</span>
      <b>↓</b>
    </div>
  );
}

function PainComparison() {
  return (
    <div className="home-pain-compare">
      <Card className="home-dialog-panel">
        <small>裸模型</small>
        <div className="home-chatline is-user">帮我整理这份 Q1 财报数据，生成报告摘要。</div>
        <div className="home-chatline is-model">
          Q1 净利润 <s>125 万元</s>，毛利率 <s>65%</s>，所有者权益 <s>13,200 千元</s>，各项指标均正常。
        </div>
        <div className="home-warning">
          <AlertTriangle size={13} />
          数据存在逻辑矛盾，模型未察觉，直接输出
        </div>
      </Card>
      <Card className="home-dialog-panel is-forge">
        <small>接入 NetNomos Forge</small>
        <div className="home-chatline is-user">帮我整理这份 Q1 财报数据，生成报告摘要。</div>
        <div className="home-chatline is-model">
          净利润 <b>125 万元</b>，所有者权益已修正为 <b>12,900 千元</b>（差额 8 万元，疑似录入问题），毛利率 65% 命中规则预警。
        </div>
        <button type="button">为何错误 · 相关依据 →</button>
      </Card>
    </div>
  );
}

function TwoModes() {
  return (
    <div className="home-mode-grid">
      <Card className="home-mode-card">
        <header>
          <strong>标准版</strong>
          <span>开箱即用 · 无需训练</span>
        </header>
        <IconFlow icons={[Plug, BookOpen, CheckCircle, FileText]} />
        <p>标准规则包经过专业团队预先编写与验证，覆盖金融报表、合规申报等通用场景，无需任何配置即可运行。</p>
        <footer>适合：刚起步、规则相对标准的团队</footer>
      </Card>
      <Card className="home-mode-card is-recommended">
        <div className="home-recommend-badge">
          <Star size={9} fill="currentColor" />
          推荐
        </div>
        <header>
          <strong>企业版</strong>
          <span>支持自训练规则包 · 专属于你</span>
        </header>
        <IconFlow icons={[Upload, Brain, UserCheck, CheckCircle]} active />
        <p>从企业自己的历史数据中学习专属规则，更贴合实际执行口径。规则随业务数据更新而持续优化，越用越精准。</p>
        <footer>适合：有历史数据积累、希望规则贴合自身业务的团队</footer>
      </Card>
    </div>
  );
}

function IconFlow({ icons, active = false }: { icons: Array<typeof Plug>; active?: boolean }) {
  return (
    <div className="home-icon-flow">
      {icons.map((Icon, index) => (
        <span className={active ? "is-active" : ""} key={`${Icon.displayName ?? Icon.name}-${index}`}>
          <Icon size={14} />
        </span>
      ))}
    </div>
  );
}

function ModeTable() {
  return (
    <div className="home-mode-table">
      <div className="home-mode-row is-head">
        <span>维度</span>
        <span>标准版</span>
        <span>企业版（自学习）</span>
      </div>
      {twoModeRows.map((row) => (
        <div className="home-mode-row" key={row.dim}>
          <span>{row.dim}</span>
          <span>{row.standard}</span>
          <span>{row.enterprise}</span>
        </div>
      ))}
    </div>
  );
}

function PersonaGrid() {
  return (
    <div className="home-persona-grid">
      {personas.map((persona) => (
        <Card className="home-persona-card" key={persona.title}>
          <span>{persona.icon}</span>
          <strong>{persona.title}</strong>
          <small>{persona.desc}</small>
        </Card>
      ))}
    </div>
  );
}

function ScenarioChat({ scenario }: { scenario: Scenario }) {
  return (
    <div className="home-scenario-chat">
      <ChatBubble avatar="U" text={scenario.user} align="left" />
      <ChatBubble avatar="A" label="A 轨 · 裸模型" text={scenario.bare} align="right" muted />
      <ChatBubble avatar="N" label="NetNomos Forge · 标准规则包" text={scenario.standard} align="right" accent />
      <ChatBubble avatar="N" label="NetNomos Forge · 自学习规则包" text={scenario.custom} align="right" highlight />
    </div>
  );
}

function ChatBubble({
  avatar,
  label,
  text,
  align,
  muted = false,
  accent = false,
  highlight = false,
}: {
  avatar: string;
  label?: string;
  text: ScenarioResponse;
  align: "left" | "right";
  muted?: boolean;
  accent?: boolean;
  highlight?: boolean;
}) {
  return (
    <div className={`home-chat-bubble is-${align}${muted ? " is-muted" : ""}${accent ? " is-accent" : ""}${highlight ? " is-highlight" : ""}`}>
      <span className="home-avatar">{avatar}</span>
      <div>
        {label && <small>{label}</small>}
        <ChatContent content={text} />
      </div>
    </div>
  );
}

function ChatContent({ content }: { content: ScenarioResponse }) {
  if (typeof content === "string") {
    return <p>{content}</p>;
  }

  return (
    <div className="home-chat-response">
      <p className="home-chat-summary">{content.summary}</p>
      <div className="home-session-table-wrap">
        <table className="home-session-table">
          <thead>
            <tr>
              <th>源</th>
              <th>目的</th>
              <th>协议</th>
              <th>端口</th>
              <th>包</th>
              <th>字节</th>
              <th>Flags</th>
              <th>判定</th>
            </tr>
          </thead>
          <tbody>
            {content.rows.map((row) => (
              <tr key={`${row.source}-${row.target}-${row.port}-${row.verdict}`}>
                <td>{row.source}</td>
                <td>{row.target}</td>
                <td>{row.proto}</td>
                <td>{row.port}</td>
                <td>{row.packets}</td>
                <td>{row.bytes}</td>
                <td>{row.flags}</td>
                <td className={`home-session-verdict is-${verdictTone(row.verdict)}`}>{row.verdict}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function verdictTone(verdict: string) {
  if (verdict.includes("异常") || verdict.includes("命中")) return "bad";
  if (verdict.includes("合规") || verdict.includes("未命中")) return "good";
  return "neutral";
}

function EngineTable() {
  return (
    <div className="home-engine-table">
      {engineRows.map((row) => (
        <div className="home-engine-row" key={row.level}>
          <span>{row.level}</span>
          <div>
            <strong>{row.name}</strong>
            <p>{row.desc}</p>
          </div>
          <em className={`is-${row.tone}`}>{row.status}</em>
        </div>
      ))}
    </div>
  );
}
