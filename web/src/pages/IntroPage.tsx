import {
  ArrowUp,
  CheckCircle,
  Code2,
  Cpu,
  FileCheck,
  FileSearch,
  Plug,
  Receipt,
  Server,
  Settings,
  Shield,
  SlidersHorizontal,
  Star,
  Truck,
  XCircle,
} from "lucide-react";
import type { ReactNode } from "react";
import type { Route } from "../components/TopNav";

const heroFeatures = [
  { icon: <Shield size={15} />, title: "规则自学习", desc: "从文档提取规则，生成可执行约束" },
  { icon: <FileCheck size={15} />, title: "输出合规校验", desc: "生成前后自动核查，拦截违背规则的结论" },
  { icon: <FileSearch size={15} />, title: "证据链可追溯", desc: "规则编号、版本、输入哈希全程留痕" },
];

const definitionPoints = [
  { wrong: "不是「更聪明的模型」", right: "是「给任何模型装的安检关卡」" },
  { wrong: "不是一次性微调", right: "是可随时替换的「规则配置文件」" },
  { wrong: "不是黑箱打分", right: "是逐条规则编号 + SMT 求解的确定性判断" },
];

const painPoints = [
  { problem: "审计/合规人员看不懂模型逻辑，无法签字背书", solution: "每条结论可追溯到规则编号" },
  { problem: "业务规则一变，模型就要重新微调，周期太长", solution: "换一份规则包配置文件即可" },
  { problem: "不同业务场景规则差异大，通用模型难以兼顾", solution: "规则包可插拔，按场景加载" },
];

const roleCards = [
  { icon: <Settings size={18} />, title: "业务规则管理员", desc: "维护和更新规则包，无需懂模型训练", tone: "cyan" },
  { icon: <Code2 size={18} />, title: "AI 应用开发者", desc: "一行代码接入约束层，降低幻觉风险", tone: "purple" },
  { icon: <FileCheck size={18} />, title: "审计合规人员", desc: "每条结论可追溯，满足留痕要求", tone: "green" },
  { icon: <Server size={18} />, title: "平台运营管理员", desc: "统一管理多套规则包，按场景分配", tone: "red" },
];

const tiers = [
  { level: "L1", name: "核心引擎 API", content: "规则强约束层基础调用", pricing: "免费 / 按用量", target: "开发者，建立生态" },
  { level: "L2", name: "标准规则包", content: "财务 / 供应链 / 工业等开箱即用规则包", pricing: "按场景订阅", target: "中小企业，垂直团队" },
  { level: "L3", name: "自定义规则学习", content: "上传数据自动生成专属规则包", pricing: "一次性服务费", target: "有特殊业务规则的企业", highlight: true },
  { level: "L4", name: "企业私有部署", content: "私有化部署 + 全部规则包", pricing: "按席位 / 年费", target: "大型企业，合规要求高" },
  { level: "L5", name: "规则包市场", content: "第三方 / 行业规则包上架分发", pricing: "平台分成", target: "行业 ISV、生态伙伴" },
];

const demoTasks = [
  { name: "2026_Q1_财务报表.csv", status: "3 违规", bad: true, time: "10分钟前" },
  { name: "供应链排程_周报.json", status: "全部通过", bad: false, time: "昨天" },
];

const demoRulePacks = [
  { icon: <Receipt size={13} />, name: "财务核查·FinGuard", meta: "标准·v1.2" },
  { icon: <Truck size={13} />, name: "供应链排程", meta: "标准·v1.0" },
  { icon: <Cpu size={13} />, name: "工业传感器阈值", meta: "标准·v0.9" },
  { icon: <Star size={13} />, name: "我的报销单规则", meta: "自定义" },
];

const jsonExample = `{
  "rule_id": "R07",
  "version": "v1.2",
  "trigger": "balance_sheet_mismatch",
  "input_hash": "a3f9c2...",
  "verdict": "BLOCKED",
  "delta": -80000,
  "message": "资产负债表不平衡，差额 80 万元"
}`;

export function IntroPage({ onNavigate }: { onNavigate: (route: Route) => void }) {
  const scrollTo = (id: string) => document.querySelector(id)?.scrollIntoView({ behavior: "smooth" });

  return (
    <div className="home-page">
      <div className="home-ambient" aria-hidden>
        <span className="home-glow home-glow-a" />
        <span className="home-glow home-glow-b" />
        <span className="home-glow home-glow-c" />
        <span className="home-glow home-glow-d" />
      </div>

      <section className="home-hero" id="hero">
        <div className="home-hero-content">
          <Pill tone="cyan">
            <Shield size={12} />
            NetNomos Forge · 规则强约束层
          </Pill>
          <h1>
            你的数据定义规则。
            <span>你的标准拦截幻觉。</span>
          </h1>
          <p>
            上传你的合规规则文档后，NetNomos Forge 自动学习其中规则，再用 SMT 约束每一次输出。每一条结论都能追溯到具体规则编号。
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
              即刻到平台 →
            </button>
            <button className="home-secondary-btn" type="button" onClick={() => scrollTo("#demo")}>
              产品操作全览
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

      <section className="home-section home-comparison" id="comparison">
        <div className="home-section-head is-centered">
          <SectionLabel tone="red">核心痛点对比</SectionLabel>
          <h2>AI 说错话的时候，它自己根本不知道</h2>
          <p>我们给任何 AI 接口装上一道「安检关卡」——错误的结论，在生成的那一刻就被拦下来，而不是等人发现。</p>
        </div>
        <ComparisonCard />
        <div className="home-pain-grid">
          {painPoints.map((item) => (
            <Card className="home-pain-card" key={item.problem}>
              <p>{item.problem}</p>
              <span>→ {item.solution}</span>
            </Card>
          ))}
        </div>
      </section>

      <section className="home-section home-demo" id="demo">
        <div className="home-section-head is-centered">
          <SectionLabel tone="purple">Demo 演示</SectionLabel>
          <h2>像使用 GPT 一样使用规则约束</h2>
        </div>
        <DemoPreview onNavigate={onNavigate} />
      </section>

      <section className="home-section home-commercial" id="commercialization">
        <div className="home-section-head is-centered">
          <SectionLabel tone="purple">目标用户与商业化</SectionLabel>
          <h2>服务谁，如何变现</h2>
        </div>
        <div className="home-role-grid">
          {roleCards.map((role) => (
            <Card className={`home-role-card is-${role.tone}`} key={role.title}>
              <span>{role.icon}</span>
              <strong>{role.title}</strong>
              <small>{role.desc}</small>
            </Card>
          ))}
        </div>
        <Card className="home-tier-table">
          <div className="home-tier-head">
            <span>层级</span>
            <span>名称</span>
            <span>内容</span>
            <span>计费方式</span>
            <span>目标客户</span>
          </div>
          {tiers.map((tier) => (
            <div className={`home-tier-row${tier.highlight ? " is-hot" : ""}`} key={tier.level}>
              <strong>{tier.level}</strong>
              <span>{tier.name}</span>
              <span>{tier.content}</span>
              <em>{tier.pricing}</em>
              <span>{tier.target}</span>
            </div>
          ))}
        </Card>
        <p className="home-footnote">地基型产品，多场景复用——规则与模型解耦，是可信 AI 落地的最后一公里。</p>
      </section>
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

function JsonTrace() {
  return (
    <div className="home-json-grid">
      <Card className="home-json-card">
        <Pill tone="cyan">规则追溯 · 实时输出</Pill>
        <pre>{jsonExample}</pre>
        <footer>
          <span>BLOCKED · R07 触发</span>
          <em>FinGuard v1.2</em>
        </footer>
      </Card>
      <div className="home-json-stats">
        {[
          ["100%", "结论可追溯", "cyan"],
          ["SMT", "确定性验证", "purple"],
          ["< 1w", "接入周期", "green"],
        ].map(([value, label, tone]) => (
          <Card className={`home-json-stat is-${tone}`} key={value}>
            <strong>{value}</strong>
            <span>{label}</span>
          </Card>
        ))}
      </div>
    </div>
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

function ComparisonCard() {
  return (
    <Card className="home-compare-card">
      <section>
        <small>普通 AI</small>
        <p>“贵公司净利润 125 万元，财务状况良好。”</p>
        <strong className="is-error">✕ 资产负债表根本不平</strong>
      </section>
      <div className="home-compare-divider">
        <span>约束层介入</span>
        <b>→</b>
      </div>
      <section className="is-forge">
        <small>装上 NetNomos Forge</small>
        <p>“净利润 125 万元，但资产负债不平衡，差额 80 万元，违反规则 <b>R07</b>。”</p>
        <strong className="is-success">✓ 当场拦截 · 给出依据</strong>
      </section>
    </Card>
  );
}

function DemoPreview({ onNavigate }: { onNavigate: (route: Route) => void }) {
  return (
    <Card className="home-demo-window">
      <aside>
        <header>NetNomos Forge</header>
        <button type="button">+ 新建核查任务</button>
        <small>最近任务</small>
        {demoTasks.map((task) => (
          <div className={`home-demo-task${task.bad ? " is-bad" : ""}`} key={task.name}>
            <strong>{task.name}</strong>
            <span>{task.bad ? "✕" : "✓"} {task.status}</span>
            <em>{task.time}</em>
          </div>
        ))}
        <small>规则包</small>
        {demoRulePacks.map((pack) => (
          <div className="home-demo-pack" key={pack.name}>
            {pack.icon}
            <span>{pack.name}</span>
            <em>{pack.meta}</em>
          </div>
        ))}
      </aside>
      <main>
        <header>2026_Q1 财务报表.csv · FinGuard v1.2</header>
        <div className="home-demo-chat">
          <div className="home-demo-user">帮我核查这份Q1财务报表，用FinGuard规则包</div>
          <div className="home-demo-result">
            <p>已对照 <b>30 条规则</b> 完成核查：</p>
            <span className="is-fail"><b>R07</b> ✕ 资产负债表不平衡，差额 80万</span>
            <span className="is-fail"><b>R14</b> ✕ 毛利率计算偏差 2.6%</span>
            <span className="is-pass"><b>27项</b> ✓ 全部通过</span>
          </div>
        </div>
        <footer>
          <button type="button">FinGuard</button>
          <button type="button">自定义规则包</button>
          <button type="button">上传数据</button>
          <button className="home-demo-send" type="button" onClick={() => onNavigate("workspace")}>
            <ArrowUp size={14} />
          </button>
        </footer>
      </main>
    </Card>
  );
}
