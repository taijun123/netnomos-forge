import type { Rule, RuleCard } from "../types/api";
import type { DisplayRuleCard } from "../components/RuleCardWall";

function clamp01(value: number): number {
  if (Number.isNaN(value)) return 1;
  return Math.max(0, Math.min(1, value));
}

export function mergeRuleCards(
  cards: RuleCard[] | undefined,
  rules: Rule[] | undefined,
  fallback: DisplayRuleCard[]
): DisplayRuleCard[] {
  if ((!cards || cards.length === 0) && (!rules || rules.length === 0)) {
    return fallback;
  }

  const fallbackById = new Map(fallback.map((card) => [card.rule_id, card]));
  const rulesById = new Map((rules ?? []).map((rule) => [rule.rule_id, rule]));
  const sourceCards =
    cards && cards.length > 0
      ? cards
      : (rules ?? []).map((rule) => ({
          rule_id: rule.rule_id,
          title_zh: rule.rule_id,
          explanation_zh: rule.text,
          formula_text: rule.text,
          tags: [rule.kind || rule.source],
          is_coincidence: false,
          citation: "NetNomos rule result",
        }));

  return sourceCards.map((card) => {
    const rule = rulesById.get(card.rule_id);
    const fallbackCard = fallbackById.get(card.rule_id);
    const confidence = clamp01(
      Number(rule?.confidence ?? rule?.support ?? fallbackCard?.confidence ?? 1)
    );
    return {
      ...card,
      kind: rule?.kind ?? fallbackCard?.kind ?? "rule",
      confidence,
      enabled: rule?.enabled ?? fallbackCard?.enabled ?? true,
      formula: rule?.formula ?? fallbackCard?.formula ?? null,
      source: rule?.source ?? fallbackCard?.source,
      support: rule?.support ?? fallbackCard?.support ?? null,
    };
  });
}
