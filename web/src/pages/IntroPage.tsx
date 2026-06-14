import {
  CheckCircle,
  Code2,
  Cpu,
  FileCheck,
  FileSearch,
  Plug,
  Server,
  Settings,
  Shield,
  SlidersHorizontal,
  XCircle,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import type { Route } from "../components/TopNav";

const HERO_FEATURES = [
  { icon: <Plug size={15} />, title: "即插即用", desc: "叠加现有 LLM API，不改模型、不重训" },
  { icon: <SlidersHorizontal size={15} />, title: "规则与模型解耦", desc: "换一份配置文件，无需重新训练" },
  { icon: <FileSearch size={15} />, title: "每条结论可追溯", desc: "规则编号 + 版本 + 哈希，满足审计留痕" },
];

const TRUST_ITEMS = [
  { label: "金融合规", stat: "30+", unit: "条财务规则" },
  { label: "供应链", stat: "18+", unit: "排程约束" },
  { label: "医疗场景", stat: "24+", unit: "合规检查项" },
  { label: "审计可追溯", stat: "100%", unit: "条结论有据" },
];

const DEFINITION_POINTS = [
  { wrong: "不是“更聪明的模型”", right: "是“给任何模型装的安检关卡”" },
  { wrong: "不是一次性微调", right: "是可随时替换的“规则配置文件”" },
  { wrong: "不是黑盒打分", right: "是逐条规则编号 + SMT 求解的确定性判断" },
];

const PAIN_POINTS = [
  {
    problem: "审计/合规人员看不懂模型逻辑，无法签字背书",
    solution: "每条结论可追溯到规则编号",
  },
  {
    problem: "业务规则一变，模型就要重新微调，周期太长",
    solution: "换一份规则包配置文件即可",
  },
  {
    problem: "不同业务场景规则差异大，通用模型难以兼顾",
    solution: "规则包可插拔，按场景加载",
  },
];

const USER_ROLES = [
  { icon: <Settings size={18} />, title: "业务规则管理员", desc: "维护和更新规则包，无需懂模型训练", color: "#4DD9FF" },
  { icon: <Code2 size={18} />, title: "AI 应用开发者", desc: "一行代码接入约束层，降低幻觉风险", color: "#C084FC" },
  { icon: <FileCheck size={18} />, title: "审计合规人员", desc: "每条结论可追溯，满足留痕要求", color: "#34D399" },
  { icon: <Server size={18} />, title: "平台运营管理员", desc: "统一管理多套规则包，按场景分配", color: "#FF4D6D" },
];

const TIERS = [
  { level: "L1", name: "核心引擎 API", content: "规则强约束层基础调用", pricing: "免费 / 按用量", target: "开发者，建立生态" },
  { level: "L2", name: "标准规则包", content: "财务 / 供应链 / 工业等开箱即用规则包", pricing: "按场景订阅", target: "中小企业，垂直团队" },
  { level: "L3", name: "自定义规则学习", content: "上传数据自动生成专属规则包", pricing: "一次性服务费", target: "有特殊业务规则的企业", highlight: true },
  { level: "L4", name: "企业私有部署", content: "私有化部署 + 全部规则包", pricing: "按席位 / 年费", target: "大型企业，合规要求高" },
  { level: "L5", name: "规则包市场", content: "第三方 / 行业规则包上架分发", pricing: "平台分成", target: "行业 ISV、生态伙伴" },
];

const JSON_EXAMPLE = `{
  "rule_id": "R07",
  "version": "v1.2",
  "trigger": "balance_sheet_mismatch",
  "input_hash": "a3f9c2...",
  "verdict": "BLOCKED",
  "delta": -80000,
  "message": "资产负债表不平衡，\\n差额 80 万元"
}`;

export function IntroPage({ onNavigate }: { onNavigate: (r: Route) => void }) {
  return (
    <div className="landing-page">
      <div className="landing-ambient" aria-hidden>
        <span className="landing-glow landing-glow-a" />
        <span className="landing-glow landing-glow-b" />
        <span className="landing-glow landing-glow-c" />
        <span className="landing-glow landing-glow-d" />
      </div>

      <section className="landing-hero" id="hero">
        <div className="landing-hero-inner">
          <span className="landing-pill">
            <Shield size={12} />
            NetNomos Forge · 规则强约束层
          </span>
          <h1>
            你的数据定义规则。
            <br />
            <span>你的标准锁死幻觉。</span>
          </h1>
          <p>
            一周接入，零改模型：在任意 LLM 接口前后插入一层 SMT 规则校验。
            规则来自行业标准或你自己的数据，每条结论都能追溯到具体规则编号。
          </p>
          <div className="landing-actions">
            <button className="landing-primary" onClick={() => onNavigate("workspace")} type="button">
              即刻到工作台 →
            </button>
            <button className="landing-secondary" onClick={() => onNavigate("network")} type="button">
              产品操作全览
            </button>
          </div>
          <div className="landing-feature-grid">
            {HERO_FEATURES.map((feature) => (
              <article className="landing-glass landing-feature-card" key={feature.title}>
                <span>{feature.icon}</span>
                <strong>{feature.title}</strong>
                <small>{feature.desc}</small>
              </article>
            ))}
          </div>
        </div>
        <div className="landing-trust">
          <span>覆盖场景</span>
          <div>
            {TRUST_ITEMS.map((item) => (
              <article className="landing-glass" key={item.label}>
                <strong>{item.stat}</strong>
                <em>{item.unit}</em>
                <small>{item.label}</small>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section landing-definition" id="definition">
        <JsonTraceCard />
        <div className="landing-split">
          <div>
            <SectionLabel>产品核心定义</SectionLabel>
            <h2>一句话定义</h2>
            <p>
              NetNomos Forge 是一个叠加在任意 LLM API 之上的“规则强约束层”。
              它不改变模型本身，而是在生成前后插入一层基于 SMT 求解器的规则校验，
              确保输出在数学上满足预设约束。
            </p>
            <div className="definition-points">
              {DEFINITION_POINTS.map((point) => (
                <div key={point.right}>
                  <span>
                    <XCircle size={14} />
                    <s>{point.wrong}</s>
                  </span>
                  <span>
                    <CheckCircle size={14} />
                    <strong>{point.right}</strong>
                  </span>
                </div>
              ))}
            </div>
          </div>
          <ArchitectureCard />
        </div>
      </section>

      <section className="landing-section landing-comparison" id="comparison">
        <div className="landing-section-head">
          <SectionLabel tone="red">核心痛点对比</SectionLabel>
          <h2>普通 LLM 的输出合理，但经不起推敲</h2>
          <p>
            NetNomos Forge 把行业规则变成硬约束，错误的结论会在生成或落表前被拦截，
            而不是等到审计人员肉眼发现。
          </p>
        </div>
        <ComparisonCard />
        <div className="landing-pain-grid">
          {PAIN_POINTS.map((point) => (
            <article className="landing-glass landing-pain-card" key={point.problem}>
              <p>{point.problem}</p>
              <span>→ {point.solution}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section landing-demo" id="demo">
        <div className="landing-section-head">
          <SectionLabel tone="purple">Demo 演示</SectionLabel>
          <h2>像使用 GPT 一样使用规则约束</h2>
        </div>
        <WorkspacePreview onNavigate={onNavigate} />
      </section>

      <section className="landing-section landing-commercial" id="commercialization">
        <div className="landing-section-head">
          <SectionLabel tone="purple">目标用户与商业化</SectionLabel>
          <h2>服务谁，如何变现</h2>
        </div>
        <div className="landing-role-grid">
          {USER_ROLES.map((role) => (
            <article className="landing-glass landing-role-card" key={role.title}>
              <span style={{ "--role-color": role.color } as CSSProperties}>{role.icon}</span>
              <strong>{role.title}</strong>
              <small>{role.desc}</small>
            </article>
          ))}
        </div>
        <div className="landing-table landing-glass">
          <div className="landing-table-head">
            <span>层级</span>
            <span>名称</span>
            <span>内容</span>
            <span>计费方式</span>
            <span>目标客户</span>
          </div>
          {TIERS.map((tier) => (
            <div className={tier.highlight ? "is-highlight" : ""} key={tier.level}>
              <strong>{tier.level}</strong>
              <span>{tier.name}</span>
              <span>{tier.content}</span>
              <em>{tier.pricing}</em>
              <span>{tier.target}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function SectionLabel({ children, tone = "cyan" }: { children: ReactNode; tone?: "cyan" | "red" | "purple" }) {
  return <span className={`landing-label is-${tone}`}>{children}</span>;
}

function JsonTraceCard() {
  return (
    <div className="landing-json-wrap">
      <article className="landing-glass landing-json-card">
        <span>规则追踪 · 实时输出</span>
        <pre>{JSON_EXAMPLE}</pre>
        <footer>
          <strong>BLOCKED · R07 触发</strong>
          <small>FinGuard v1.2</small>
        </footer>
      </article>
    </div>
  );
}

function ArchitectureCard() {
  return (
    <article className="landing-glass landing-arch-card">
      <div className="arch-node">
        <small>你现有的</small>
        <strong>LLM / Agent 应用</strong>
        <em>不改动</em>
      </div>
      <div className="arch-arrow">
        <span>叠加</span>
        <i>↓</i>
      </div>
      <div className="arch-node is-forge">
        <strong>NetNomos Forge</strong>
        <span>规则学习 → 语义过滤 → SMT 执行</span>
      </div>
      <div className="arch-arrow">
        <span>加载</span>
        <i>↓</i>
      </div>
      <div className="arch-pack-grid">
        <div>
          <strong>标准规则包</strong>
          <span>财务 / 供应链 / 工业</span>
        </div>
        <div>
          <strong>自定义规则包</strong>
          <span>从你的数据中学习</span>
        </div>
      </div>
      <footer>规则编号 + 版本号 + 输入哈希 → 可审计追溯</footer>
    </article>
  );
}

function ComparisonCard() {
  return (
    <article className="landing-glass landing-compare-card">
      <section>
        <small>普通 AI</small>
        <p>“贵公司净利润 125 万元，财务状况良好。”</p>
        <em className="is-error">✕ 资产负债表根本不平</em>
      </section>
      <div className="compare-divider">
        <span>约束层介入</span>
        <i>→</i>
      </div>
      <section>
        <small>装上 NetNomos Forge</small>
        <p>
          “净利润 125 万元，但资产负债不平衡，差额 80 万元，违反规则 <strong>R07</strong>。”
        </p>
        <em className="is-success">✓ 当场拦截 · 给出依据</em>
      </section>
    </article>
  );
}

function WorkspacePreview({ onNavigate }: { onNavigate: (r: Route) => void }) {
  return (
    <article className="landing-glass landing-workspace-preview">
      <aside>
        <strong>NetNomos Forge</strong>
        <button type="button">+ 新建核查任务</button>
        <div className="preview-task is-active">
          <span>2026_Q1_财务报表.csv</span>
          <em>✕ 3 违规</em>
        </div>
        <div className="preview-task">
          <span>供应链排程_周报.json</span>
          <em className="is-ok">✓ 全部通过</em>
        </div>
        <small>规则包</small>
        <ul>
          <li>财务核查·FinGuard <b>标准·v1.2</b></li>
          <li>供应链排程 <b>标准·v1.0</b></li>
          <li>我的报销单规则 <b>自定义</b></li>
        </ul>
      </aside>
      <main>
        <header>
          <span />
          <strong>2026_Q1_财务报表.csv</strong>
          <em>· FinGuard v1.2</em>
        </header>
        <div className="preview-chat">
          <p className="user-msg">帮我核查这份Q1财务报表，用FinGuard规则包</p>
          <div className="assistant-msg">
            <strong>已对照 30 条规则完成核查：</strong>
            <span className="is-bad">R07　✕ 资产负债表不平衡，差额 80万</span>
            <span className="is-bad">R14　✕ 毛利率计算偏差 2.6%</span>
            <span className="is-good">27项　✓ 全部通过</span>
          </div>
        </div>
        <footer>
          <button type="button">FinGuard</button>
          <button type="button">自定义规则包</button>
          <button type="button">上传数据</button>
          <button className="send-preview" onClick={() => onNavigate("workspace")} type="button">
            进入工作台 →
          </button>
        </footer>
      </main>
    </article>
  );
}
