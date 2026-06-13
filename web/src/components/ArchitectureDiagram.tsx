interface Layer {
  id: string;
  name: string;
  sub: string;
  items: string[];
  accent: string;
}

const LAYERS: Layer[] = [
  {
    id: "ui",
    name: "前端展示层",
    sub: "Web 产品页 · 3D 办公室",
    items: ["介绍页", "网络 / 财务 demo", "双轨标红对比", "SSE 实时事件"],
    accent: "var(--accent)",
  },
  {
    id: "orchestrate",
    name: "编排服务层",
    sub: "FastAPI · SSE 事件流",
    items: ["REST 接口", "WorkflowEvent 推送", "LLM 路由", "双轨报告生成"],
    accent: "var(--accent-2)",
  },
  {
    id: "engine",
    name: "规则引擎层",
    sub: "NetNomos + Z3",
    items: ["规则挖掘 learn", "Z3 约束校验 validate", "数值投影 project", "规则解释 explain"],
    accent: "var(--accent-3)",
  },
  {
    id: "assets",
    name: "规则资产层",
    sub: "rules.json · 规则卡 · AST",
    items: ["结构化公式", "中文规则卡", "人工规则通道", "可复用规则集"],
    accent: "var(--accent-4)",
  },
];

export function ArchitectureDiagram() {
  return (
    <div className="arch">
      <div className="arch-stack">
        {LAYERS.map((layer, i) => (
          <div className="arch-row" key={layer.id}>
            <div
              className="arch-layer glass"
              style={{ ["--layer-accent" as string]: layer.accent }}
            >
              <div className="arch-layer-head">
                <span className="arch-layer-dot" />
                <div>
                  <strong>{layer.name}</strong>
                  <em>{layer.sub}</em>
                </div>
              </div>
              <div className="arch-chips">
                {layer.items.map((it) => (
                  <span className="arch-chip" key={it}>
                    {it}
                  </span>
                ))}
              </div>
            </div>
            {i < LAYERS.length - 1 && (
              <svg className="arch-connector" viewBox="0 0 40 36" aria-hidden>
                <defs>
                  <linearGradient id={`flow-${i}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.7" />
                    <stop offset="100%" stopColor="var(--accent-3)" stopOpacity="0.7" />
                  </linearGradient>
                </defs>
                <line
                  x1="20"
                  y1="2"
                  x2="20"
                  y2="26"
                  stroke={`url(#flow-${i})`}
                  strokeWidth="2.5"
                  strokeDasharray="4 4"
                  className="arch-flow-line"
                />
                <path d="M20 34 L14 24 L26 24 Z" fill="var(--accent-3)" opacity="0.8" />
              </svg>
            )}
          </div>
        ))}
      </div>
      <p className="arch-caption">
        规则在四层之间双向流动：资产层沉淀规则，引擎层校验生成，编排层调度推送，展示层让人类看见每一条约束。
      </p>
    </div>
  );
}
