import type { Route } from "../components/TopNav";
import { ArchitectureDiagram } from "../components/ArchitectureDiagram";

const PAIN_POINTS = [
  {
    tag: "网络 · 协议矛盾",
    bad: "Proto = UDP，Flags = .A..S.",
    why: "UDP 无连接协议却携带 TCP 的 SYN+ACK 标志，协议字段与标志位自相矛盾。",
  },
  {
    tag: "网络 · 物理越界",
    bad: "Packets = 2，Bytes = 204,800",
    why: "65535 × Packets < Bytes，违反 IPv4 单包字节物理上界，统计必然算错。",
  },
  {
    tag: "财务 · 勾稽不平",
    bad: "期末存货 ≠ 期初 + 采购 − 成本",
    why: "进销存恒等式失衡，营业成本被虚增，毛利与毛利率连环算错。",
  },
  {
    tag: "财务 · 资产不配平",
    bad: "资产总计 ≠ 负债 + 所有者权益",
    why: "会计基本恒等式不成立，差额 500 千元，报表无法配平。",
  },
];

const VALUE_CARDS = [
  {
    icon: "◈",
    title: "规则自发现",
    desc: "从正常数据自动挖掘逻辑规则——取值范围、物理上下界、协议蕴含、勾稽恒等式，无需人工逐条编写。",
    points: ["NetNomos 学习器（hitting-set / tree）", "Z3 逐条校验满足率", "训练集满足率 1.0"],
  },
  {
    icon: "▣",
    title: "合规生成",
    desc: "把规则编译为 Z3 硬约束，LLM 每步生成都过约束过滤，报告与数据零违规——不改模型，只加规则。",
    points: ["逐步解码 + Z3 可行域过滤", "数值由程序回填", "终检正则扫描裸数字"],
  },
  {
    icon: "⟳",
    title: "规则复用核查",
    desc: "既有规则集对新上传数据逐行核查，秒出违规清单：行号、字段、命中规则、实际值与期望值一目了然。",
    points: ["规则资产沉淀复用", "违规清单可追溯", "人类开关随时增删"],
  },
];

export function IntroPage({ onNavigate }: { onNavigate: (r: Route) => void }) {
  return (
    <div className="intro">
      {/* HERO */}
      <section className="hero">
        <div className="hero-bg" aria-hidden>
          <span className="orb orb-1" />
          <span className="orb orb-2" />
          <span className="grid-overlay" />
        </div>
        <div className="hero-inner">
          <span className="hero-eyebrow">领域规则 · 一等公民</span>
          <h1 className="hero-title">
            不改模型，<br />
            只加<span className="grad">规则</span>。
          </h1>
          <p className="hero-lead">
            NetNomos 把领域规则提升为一等公民：从正常数据自动挖掘逻辑规则，用 Z3 把规则
            变成硬约束，让 LLM 生成的报告与数据零违规。
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary btn-lg" onClick={() => onNavigate("network")}>
              体验网络 demo
            </button>
            <button className="btn btn-outline btn-lg" onClick={() => onNavigate("finance")}>
              体验财务 demo
            </button>
          </div>
          <div className="hero-stats">
            <div>
              <strong>1.0</strong>
              <span>训练集规则满足率</span>
            </div>
            <div>
              <strong>0</strong>
              <span>B 轨生成违规</span>
            </div>
            <div>
              <strong>2</strong>
              <span>场景：网络 / 财务</span>
            </div>
          </div>
        </div>
      </section>

      {/* 痛点叙事 */}
      <section className="section">
        <div className="section-head">
          <span className="section-eyebrow">问题</span>
          <h2>AI 输出看似正确，却在违反领域规则</h2>
          <p>
            大模型的文字与数字读起来通顺，可它不懂协议物理约束，也不会做勾稽配平。
            下面四类错误，肉眼很难第一时间发现——但规则引擎一眼看穿。
          </p>
        </div>
        <div className="pain-grid">
          {PAIN_POINTS.map((p) => (
            <article className="pain-card glass" key={p.tag}>
              <span className="pain-tag">{p.tag}</span>
              <code className="pain-bad">{p.bad}</code>
              <p>{p.why}</p>
              <span className="pain-verdict">规则引擎判定：违规</span>
            </article>
          ))}
        </div>
      </section>

      {/* 三大价值 */}
      <section className="section section-tint">
        <div className="section-head">
          <span className="section-eyebrow">价值</span>
          <h2>三件事，构成完整闭环</h2>
        </div>
        <div className="value-grid">
          {VALUE_CARDS.map((v) => (
            <article className="value-card glass" key={v.title}>
              <span className="value-icon">{v.icon}</span>
              <h3>{v.title}</h3>
              <p>{v.desc}</p>
              <ul>
                {v.points.map((pt) => (
                  <li key={pt}>{pt}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      {/* 四层架构 */}
      <section className="section">
        <div className="section-head">
          <span className="section-eyebrow">架构</span>
          <h2>四层架构，规则贯穿始终</h2>
          <p>从前端展示到规则资产，规则在每一层都是可见、可校验、可复用的一等公民。</p>
        </div>
        <ArchitectureDiagram />
      </section>

      {/* demo 入口 */}
      <section className="section section-tint">
        <div className="section-head">
          <span className="section-eyebrow">演示</span>
          <h2>挑一个场景，走完整闭环</h2>
        </div>
        <div className="demo-entry-grid">
          <button className="demo-entry glass entry-network" onClick={() => onNavigate("network")}>
            <span className="entry-kicker">场景一</span>
            <h3>网络流量 demo</h3>
            <p>
              NetFlow 规则自发现 → 规则卡 → wk3 新数据核查 → A/B 双轨 NetFlow 标红对比 →
              审计报告。
            </p>
            <span className="entry-go">进入 demo →</span>
          </button>
          <button className="demo-entry glass entry-finance" onClick={() => onNavigate("finance")}>
            <span className="entry-kicker">场景二</span>
            <h3>财务报表 demo</h3>
            <p>
              960 行合成数据 → 勾稽规则学习 → 「华信咨询」错误资料 → F1–F4 命中 →
              双轨报告标红对比。
            </p>
            <span className="entry-go">进入 demo →</span>
          </button>
        </div>
      </section>

      <footer className="intro-footer">
        <div>
          <strong>NetNomos Forge</strong>
          <span>不改模型，只加规则 · 规则即一等公民</span>
        </div>
        <span className="foot-note">演示工程 · 产品页 + 网络 / 财务双场景 + 3D 办公室（即将上线）</span>
      </footer>
    </div>
  );
}
