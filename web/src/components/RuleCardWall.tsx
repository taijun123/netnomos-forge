import { useEffect, useMemo, useState } from "react";
import type { Rule, RuleCard } from "../types/api";

export interface DisplayRuleCard extends RuleCard {
  kind: string;
  confidence: number;
  enabled: boolean;
  formula?: Record<string, unknown> | null;
  source?: Rule["source"];
  support?: number | null;
}

function sourceLabel(source?: Rule["source"]): string {
  return source === "learned" ? "数据自发现" : "人工领域规则";
}

function sourceClass(source?: Rule["source"]): string {
  return source === "learned" ? "is-learned" : "is-manual";
}

/**
 * 规则卡墙：每张卡含公式 / 中文解释 / 置信度 / enabled 开关（“人类开关”）。
 * is_coincidence 的疑似巧合规则置灰。
 */
export function RuleCardWall({ cards: initial }: { cards: DisplayRuleCard[] }) {
  const [cards, setCards] = useState(initial);
  const [selectedId, setSelectedId] = useState<string | null>(
    initial[0]?.rule_id ?? null
  );

  useEffect(() => {
    setCards(initial);
    setSelectedId(initial[0]?.rule_id ?? null);
  }, [initial]);

  const toggle = (ruleId: string) =>
    setCards((prev) =>
      prev.map((c) => (c.rule_id === ruleId ? { ...c, enabled: !c.enabled } : c))
    );

  const enabledCount = cards.filter((c) => c.enabled).length;
  const learnedCount = cards.filter((c) => c.source === "learned").length;
  const manualCount = cards.length - learnedCount;
  const selected = useMemo(
    () => cards.find((c) => c.rule_id === selectedId) ?? cards[0],
    [cards, selectedId]
  );

  return (
    <div className="rulewall">
      <div className="rulewall-head">
        <h3>规则卡墙</h3>
        <div className="rulewall-summary">
          <span className="rulewall-count">
            已启用 {enabledCount}/{cards.length} 条规则
          </span>
          <span className="source-pill is-learned">数据自发现 {learnedCount}</span>
          <span className="source-pill is-manual">人工领域 {manualCount}</span>
        </div>
      </div>
      <div className="rulewall-body">
        <div className="rulewall-grid">
          {cards.map((card) => (
            <article
              key={card.rule_id}
              className={`rulecard glass${card.enabled ? "" : " is-off"}${
                card.is_coincidence ? " is-coincidence" : ""
              }${selected?.rule_id === card.rule_id ? " is-selected" : ""}`}
            >
              <header>
                <span className="rulecard-id">{card.rule_id}</span>
                <span className={`source-pill ${sourceClass(card.source)}`}>
                  {sourceLabel(card.source)}
                </span>
                <div className="rulecard-tags">
                  {card.tags.map((t) => (
                    <span className="tag" key={t}>
                      {t}
                    </span>
                  ))}
                </div>
                <button
                  className={`switch${card.enabled ? " is-on" : ""}`}
                  role="switch"
                  aria-checked={card.enabled}
                  onClick={() => toggle(card.rule_id)}
                  title={card.enabled ? "点击停用" : "点击启用"}
                >
                  <i />
                </button>
              </header>
              <h4>{card.title_zh}</h4>
              <code className="rulecard-formula">{card.formula_text}</code>
              <p>{card.explanation_zh}</p>
              <footer>
                <div className="conf">
                  <div className="conf-bar">
                    <div
                      className="conf-fill"
                      style={{ width: `${Math.round(card.confidence * 100)}%` }}
                    />
                  </div>
                  <span>置信度 {(card.confidence * 100).toFixed(0)}%</span>
                </div>
                <button
                  className="btn btn-ghost btn-xs"
                  onClick={() => setSelectedId(card.rule_id)}
                >
                  AST
                </button>
                {card.is_coincidence && (
                  <span className="coincidence-flag">疑似巧合</span>
                )}
              </footer>
            </article>
          ))}
        </div>
        {selected && (
          <aside className="rule-detail glass">
            <div className="rule-detail-head">
              <span className="rulecard-id">{selected.rule_id}</span>
              <strong>{selected.kind}</strong>
            </div>
            <h4>{selected.title_zh}</h4>
            <p>{selected.explanation_zh}</p>
            <div className="rule-detail-meta">
              <span>来源: {sourceLabel(selected.source)}</span>
              <span>support: {selected.support ?? "n/a"}</span>
            </div>
            <pre>{JSON.stringify(selected.formula ?? {}, null, 2)}</pre>
            <small>{selected.citation}</small>
          </aside>
        )}
      </div>
    </div>
  );
}
