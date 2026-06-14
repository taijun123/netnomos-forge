# -*- coding: utf-8 -*-
"""forge.core.engine — ForgeRuleEngine（实现 contracts.RuleEngineAPI）.

对仓库内 NetNomos 源码目录做薄封装：
- 所有 netnomos import 全部懒加载（方法内部），沙箱缺 pydantic/z3 时只在真正调用
  挖掘/验证功能的方法处抛出带中文指引的 RuntimeError；
- 纯 Python 的部分（场景加载、RuleSet 落盘/加载、人工规则合并、explain 降级模板）
  在任何环境都可用。

关键事实（读 NetNomos 源码确认）：
- ``NetNomosMiner.validate_rules`` / ``Theory.validate`` 只返回聚合指标::

      {"rule_count": int, "all_rows_satisfied": bool,
       "mean_satisfaction": float, "per_rule_satisfaction": [float, ...]}

  没有逐行违规明细。因此 validate() 先用该聚合结果，再对满足率 < 1 的规则调
  ``netnomos.theory.evaluate_formula_df`` 取逐行布尔序列，自行定位违规行号。
- ``prepare_dataset`` 把相对 source.path 按【当前工作目录】解析，所以引擎统一把
  dataset_spec.json 内的相对路径按 spec 所在目录解析为绝对路径后经 input_path 传入。
"""
from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from forge.contracts import (
    Rule,
    RuleCard,
    RuleSet,
    Scenario,
    SCENARIO_DIR,
    Violation,
    ViolationReport,
)

log = logging.getLogger("forge.core.engine")

# 规则集落盘根目录：forge/rulesets/
RULESETS_DIR = Path(__file__).resolve().parents[1] / "rulesets"

# 每条规则最多在报告里展开多少条违规明细（by_rule 仍统计全量）
MAX_VIOLATIONS_PER_RULE = 50

_NETNOMOS_HINT = (
    "无法导入 netnomos（或其依赖 pydantic/z3-solver）。当前环境（如沙箱）无外网 pip，"
    "请在宿主机操作：\n"
    "  1. cd <workspace>/netnomos-forge/NetNomos && uv sync\n"
    "  2. 以 `uv run python ...` 或激活 .venv 后运行 forge 代码；\n"
    "  3. 一键学习可直接执行 scripts/host/run_network_learn.ps1。"
)

# 规则 kind 中文标签（explain 模板用）
_KIND_TAGS_ZH = {
    "implication": "条件蕴含",
    "identity": "恒等式",
    "exclusion": "取值排除",
    "bound": "数值上下界",
    "composite": "复合约束",
    "quantified": "量化规则",
    "range": "取值范围",
    "": "未分类",
}


def _require_netnomos():
    """懒加载 netnomos.api，失败时给出中文指引."""
    try:
        from netnomos.api import NetNomosMiner  # noqa: PLC0415
        return NetNomosMiner
    except Exception as exc:  # ImportError / pydantic 缺失等
        raise RuntimeError(_NETNOMOS_HINT) from exc


# ---------------------------------------------------------------------------
# 纯 Python 工具：公式 dict 处理 / RuleSet 落盘与加载
# ---------------------------------------------------------------------------

def classify_kind(formula: dict[str, Any]) -> str:
    """根据 NetNomos 结构化公式 dict 推断规则类别（contracts.Rule.kind）."""
    kind = formula.get("kind", "")
    if kind == "implies":
        return "implication"
    if kind == "compare":
        op = formula.get("op", "")
        if op == "=":
            return "identity"
        if op == "!=":
            return "exclusion"
        return "bound"  # < <= > >=
    if kind in ("and", "or", "not"):
        return "composite"
    if kind in ("forall", "exists"):
        return "quantified"
    return kind or ""


def collect_fields(formula: dict[str, Any]) -> list[str]:
    """递归收集公式 dict 涉及的字段名（symbol/indexed 节点）."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            kind = node.get("kind")
            if kind == "symbol" and isinstance(node.get("name"), str):
                found.append(node["name"])
            elif kind == "indexed" and isinstance(node.get("base"), str):
                found.append(node["base"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(formula)
    # 去重保序
    seen: set[str] = set()
    return [f for f in found if not (f in seen or seen.add(f))]


def rules_to_netnomos_json(rules: list[Rule]) -> list[dict[str, Any]]:
    """contracts.Rule 列表 → NetNomos rules.json 格式（list[dict]）."""
    return [{
        "rule_id": r.rule_id,
        "formula": r.formula,
        "display": r.text,
        "support": r.support if r.support is not None else 0.0,
        "source": {"origin": r.source, "kind": r.kind,
                   **({"confidence": r.confidence} if r.confidence is not None else {})},
    } for r in rules]


def save_ruleset(ruleset: RuleSet, out_dir: str | Path | None = None) -> RuleSet:
    """把 RuleSet 落盘为 NetNomos 格式 rules.json + contracts 格式 ruleset.json.

    out_dir 缺省为 forge/rulesets/<scenario>/<时间戳>/，返回更新了 rules_path 的 RuleSet。
    """
    if out_dir is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out_dir = RULESETS_DIR / ruleset.scenario / stamp
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rules_path = out_dir / "rules.json"
    rules_path.write_text(
        json.dumps(rules_to_netnomos_json(ruleset.rules), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ruleset.rules_path = str(rules_path)
    (out_dir / "ruleset.json").write_text(ruleset.to_json(), encoding="utf-8")
    return ruleset


def load_ruleset(path: str | Path) -> RuleSet:
    """从 save_ruleset 产物目录（或 ruleset.json 文件）恢复 RuleSet."""
    path = Path(path)
    if path.is_dir():
        path = path / "ruleset.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = [Rule(**item) for item in payload["rules"]]
    return RuleSet(
        scenario=payload["scenario"],
        rules=rules,
        rules_path=payload.get("rules_path"),
        run_dir=payload.get("run_dir"),
        created_at=payload.get("created_at", time.time()),
    )


# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------

class ForgeRuleEngine:
    """contracts.RuleEngineAPI 实现：场景驱动的规则学习/验证/解释引擎."""

    def __init__(self, scenario: str, dataset_spec_path: str | Path,
                 grammar_spec_path: str | Path, runs_dir: str | Path = "runs"):
        self.scenario = scenario
        self.dataset_spec_path = Path(dataset_spec_path)
        self.grammar_spec_path = Path(grammar_spec_path)
        self.runs_dir = Path(runs_dir)
        self._miner = None                       # 懒加载的 NetNomosMiner
        self.last_ruleset: RuleSet | None = None
        # 读 dataset_spec.json（纯 stdlib）拿默认数据路径，按 spec 所在目录解析相对路径
        spec_payload = json.loads(self.dataset_spec_path.read_text(encoding="utf-8"))
        raw = (spec_payload.get("source") or {}).get("path")
        self.default_data_path: Path | None = None
        if raw:
            p = Path(raw)
            self.default_data_path = p if p.is_absolute() else (self.dataset_spec_path.parent / p).resolve()

    # -- 构造 ----------------------------------------------------------------
    @classmethod
    def from_scenario(cls, scenario: str | Scenario, runs_dir: str | Path = "runs") -> "ForgeRuleEngine":
        name = scenario.value if isinstance(scenario, Scenario) else str(scenario)
        scen_dir = SCENARIO_DIR / name
        dataset_spec = scen_dir / "dataset_spec.json"
        grammar_spec = scen_dir / "grammar_spec.json"
        for p in (dataset_spec, grammar_spec):
            if not p.exists():
                raise FileNotFoundError(
                    f"场景 {name} 缺少 {p.name}：请确认 forge/scenarios/{name}/ 下已放置 "
                    f"dataset_spec.json 与 grammar_spec.json（参考该目录 README.md）"
                )
        return cls(name, dataset_spec, grammar_spec, runs_dir=runs_dir)

    # -- 内部 ----------------------------------------------------------------
    def _get_miner(self):
        if self._miner is None:
            NetNomosMiner = _require_netnomos()
            self._miner = NetNomosMiner.from_files(
                dataset_spec=self.dataset_spec_path,
                grammar_spec=self.grammar_spec_path,
                runs_dir=self.runs_dir,
            )
        return self._miner

    def _resolve_data_path(self, data_path: str | Path | None) -> str | None:
        """显式数据路径优先；否则用 spec 默认路径（已按 spec 目录解析为绝对路径）."""
        if data_path is not None:
            return str(Path(data_path))
        if self.default_data_path is not None:
            if not self.default_data_path.exists():
                raise FileNotFoundError(
                    f"默认数据文件不存在：{self.default_data_path}\n"
                    f"（dataset_spec.json 的 source.path 按 spec 所在目录解析，"
                    f"请确认 NetNomos 仓库与 netnomos-forge 同级，或显式传 data_path）"
                )
            return str(self.default_data_path)
        return None

    def _to_learned(self, rules: list[Rule]):
        """contracts.Rule → NetNomos LearnedRule（懒加载 netnomos.ast）."""
        _require_netnomos()
        from netnomos.ast import formula_from_dict  # noqa: PLC0415
        from netnomos.learners import LearnedRule   # noqa: PLC0415
        return [LearnedRule(
            rule_id=r.rule_id,
            formula=formula_from_dict(r.formula),
            display=r.text,
            support=float(r.support or 0.0),
            source={"origin": r.source, "kind": r.kind},
        ) for r in rules]

    def _ruleset_or_last(self, rules: RuleSet | None) -> RuleSet:
        ruleset = rules or self.last_ruleset
        if ruleset is None:
            raise RuntimeError("尚无规则集：请先调用 learn()，或显式传入 rules 参数")
        return ruleset

    # -- RuleEngineAPI --------------------------------------------------------
    def learn(self, data_path: str | Path, learner: str = "hitting-set",
              limit: int | None = None) -> RuleSet:
        """挖掘规则并落盘到 forge/rulesets/<scenario>/<时间戳>/rules.json."""
        miner = self._get_miner()
        from netnomos.ast import formula_to_dict  # noqa: PLC0415
        input_path = self._resolve_data_path(data_path)
        result = miner.fit(input_path=input_path, learner=learner, limit=limit)
        rules: list[Rule] = []
        for learned in result.rules:
            formula = formula_to_dict(learned.formula)
            rules.append(Rule(
                rule_id=learned.rule_id,
                formula=formula,
                text=learned.display,
                kind=classify_kind(formula),
                source="learned",
                support=learned.support,
            ))
        ruleset = RuleSet(scenario=self.scenario, rules=rules, run_dir=str(result.run_dir))
        ruleset = save_ruleset(ruleset)
        # 把 semantic_values.json 复制到 rules.json 旁，供 interpret_rules 语义着色
        sv = Path(result.run_dir) / "semantic_values.json"
        if sv.exists() and ruleset.rules_path:
            shutil.copy2(sv, Path(ruleset.rules_path).with_name("semantic_values.json"))
        self.last_ruleset = ruleset
        log.info("learn 完成：%d 条规则 → %s", len(rules), ruleset.rules_path)
        return ruleset

    def validate(self, data_path: str | Path, rules: RuleSet | None = None) -> ViolationReport:
        """规则集 × 数据 → 逐行违规报告.

        聚合指标来自 miner.validate_rules（NetNomos Theory.validate），逐行明细由
        evaluate_formula_df 补算（NetNomos 原生只给 per_rule_satisfaction）。
        """
        ruleset = self._ruleset_or_last(rules)
        miner = self._get_miner()
        active = ruleset.enabled_rules()
        learned = self._to_learned(active)
        input_path = self._resolve_data_path(data_path)
        agg = miner.validate_rules(learned, input_path=input_path)
        sats: list[float] = list(agg.get("per_rule_satisfaction", []))

        violations: list[Violation] = []
        by_rule: dict[str, int] = {}
        # validate_rules 内部已 prepare 过一次但不返回 prepared，这里为拿行数/明细再准备一次
        prepared = miner.prepare(input_path=input_path)
        total_rows = len(prepared.dataframe)
        if any(s < 1.0 for s in sats):
            from netnomos.theory import evaluate_formula_df  # noqa: PLC0415
            for rule, lr, sat in zip(active, learned, sats):
                if sat >= 1.0:
                    continue
                mask = ~evaluate_formula_df(lr.formula, prepared).astype(bool)
                bad_positions = [int(i) for i in mask.to_numpy().nonzero()[0]]
                by_rule[rule.rule_id] = len(bad_positions)
                fields = collect_fields(rule.formula)
                for pos in bad_positions[:MAX_VIOLATIONS_PER_RULE]:
                    row = prepared.dataframe.iloc[pos]
                    observed = {f: _jsonable(row[f]) for f in fields if f in prepared.dataframe.columns}
                    violations.append(Violation(
                        row_index=pos,
                        rule_id=rule.rule_id,
                        rule_text=rule.text,
                        fields=fields,
                        observed=observed,
                        expected=f"应满足：{rule.text}",
                        message_zh=f"第 {pos + 1} 行违反规则 {rule.rule_id}（{rule.text}），"
                                   f"实际值 {observed}",
                    ))
        return ViolationReport(
            scenario=self.scenario,
            data_path=str(input_path or ""),
            total_rows=total_rows,
            violations=violations,
            satisfaction_rate=float(agg.get("mean_satisfaction", 1.0)),
            by_rule=by_rule,
        )

    def check(self, rules: RuleSet, assertion: str) -> bool:
        """Z3 蕴含检查：规则集是否蕴含给定断言（NetNomos DSL 公式字符串）."""
        miner = self._get_miner()
        learned = self._to_learned(rules.enabled_rules())
        return bool(miner.entails_with_rules(
            assertion, learned, input_path=self._resolve_data_path(None)))

    def explain(self, rules: RuleSet, llm=None, lang: str = "zh") -> list[RuleCard]:
        """规则 → 规则卡。先取 NetNomos 机器解释，再经 LLM 润色；llm=None 或
        netnomos 不可用时用确定性模板降级，保证任何环境都能出卡."""
        active = rules.enabled_rules()
        interpreted = self._machine_interpret(rules, active)
        cards: list[RuleCard] = []
        for rule, interp in zip(active, interpreted):
            if llm is not None:
                cards.append(self._card_via_llm(rule, interp, llm))
            else:
                cards.append(self._card_template(rule, interp))
        return cards

    def add_manual_rules(self, rules: RuleSet, manual_path: str | Path) -> RuleSet:
        """读 NetNomos 格式人工 rules.json，合并进规则集（source="manual"）.

        纯 stdlib 实现，沙箱可用；rule_id 冲突时人工规则覆盖同名旧规则。
        """
        manual = self._read_netnomos_rules(manual_path, source_override="manual")
        manual_ids = {r.rule_id for r in manual}
        merged = [r for r in rules.rules if r.rule_id not in manual_ids] + manual
        out = RuleSet(scenario=rules.scenario, rules=merged,
                      rules_path=rules.rules_path, run_dir=rules.run_dir)
        log.info("合并人工规则 %d 条（覆盖同名 %d 条）",
                 len(manual), len(rules.rules) + len(manual) - len(merged))
        return out

    def load_netnomos_rules(self, rules_path: str | Path) -> RuleSet:
        """读取 NetNomos rules.json，并尽量保留原始来源语义.

        归档的 NetNomos 学习结果通常带有 ``source.learner``，应标为
        ``learned``；人工兜底 rules.json 继续走 add_manual_rules()。
        """
        path = Path(rules_path)
        return RuleSet(
            scenario=self.scenario,
            rules=self._read_netnomos_rules(path),
            rules_path=str(path),
        )

    def _read_netnomos_rules(
        self,
        rules_path: str | Path,
        source_override: str | None = None,
    ) -> list[Rule]:
        path = Path(rules_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"规则文件 {rules_path} 应为 NetNomos rules.json 列表格式")

        rules: list[Rule] = []
        for item in payload:
            formula = item.get("formula") or {}
            source_meta = item.get("source")
            origin = ""
            if isinstance(source_meta, dict):
                origin = str(source_meta.get("origin") or "")
            if source_override:
                source = source_override
            elif origin in ("learned", "manual"):
                source = origin
            elif isinstance(source_meta, dict) and (
                source_meta.get("learner") or source_meta.get("predicate_ids")
            ):
                source = "learned"
            else:
                source = "manual"

            confidence = None
            if isinstance(source_meta, dict) and source_meta.get("confidence") is not None:
                confidence = float(source_meta["confidence"])
            rules.append(Rule(
                rule_id=item["rule_id"],
                formula=formula,
                text=item.get("display", ""),
                kind=classify_kind(formula),
                source=source,  # type: ignore[arg-type]
                support=item.get("support"),
                confidence=confidence,
            ))
        return rules

    # -- explain 内部 ----------------------------------------------------------
    def _machine_interpret(self, ruleset: RuleSet, active: list[Rule]) -> list[str]:
        """优先 miner.interpret_rules；netnomos/数据缺失时降级为 rule.text."""
        try:
            miner = self._get_miner()
            learned = self._to_learned(active)
            semantic_values = None
            if ruleset.rules_path:
                semantic_values = miner.load_semantic_values_for_rules(ruleset.rules_path) or None
            return miner.interpret_rules(
                learned,
                input_path=self._resolve_data_path(None),
                semantic_values=semantic_values,
            )
        except Exception as exc:
            log.warning("机器解释不可用（%s），降级为 display 文本", exc)
            return [r.text for r in active]

    def _card_via_llm(self, rule: Rule, interp: str, llm) -> RuleCard:
        prompt = (
            f"你是网络/业务规则分析专家。请用中文为下面这条由 NetNomos 从数据中学到的规则写一张规则卡：\n"
            f"- 规则编号：{rule.rule_id}\n"
            f"- 公式：{rule.text}\n"
            f"- 机器解释：{interp}\n"
            f"- 类别：{rule.kind}；支持度：{rule.support}\n\n"
            f"输出 2-4 句业务语言解释（不要复述公式符号）。如果你判断这条规则只是数据"
            f"采样巧合而非真实领域约束，请在末尾单独一行输出“【疑似巧合】”。"
        )
        try:
            text = llm.complete(prompt, role="explain",
                                system="用简体中文回答，面向网络运维/业务人员。").strip()
        except Exception as exc:
            log.warning("LLM 解释失败（%s），降级为模板", exc)
            return self._card_template(rule, interp)
        is_coincidence = "疑似巧合" in text
        explanation = text.replace("【疑似巧合】", "").strip() or self._template_explanation(rule, interp)
        return RuleCard(
            rule_id=rule.rule_id,
            title_zh=self._template_title(rule),
            explanation_zh=explanation,
            formula_text=rule.text,
            tags=self._tags(rule),
            is_coincidence=is_coincidence,
        )

    def _card_template(self, rule: Rule, interp: str) -> RuleCard:
        """确定性模板规则卡（无 LLM 也能出卡）."""
        return RuleCard(
            rule_id=rule.rule_id,
            title_zh=self._template_title(rule),
            explanation_zh=self._template_explanation(rule, interp),
            formula_text=rule.text,
            tags=self._tags(rule),
            is_coincidence=False,
        )

    def _template_title(self, rule: Rule) -> str:
        fields = collect_fields(rule.formula)
        label = _KIND_TAGS_ZH.get(rule.kind, rule.kind or "规则")
        target = "、".join(fields[:3]) if fields else "若干字段"
        return f"{target} 的{label}"

    def _template_explanation(self, rule: Rule, interp: str) -> str:
        fields = collect_fields(rule.formula)
        src = "从训练数据自动学习得到" if rule.source == "learned" else "由人工注入"
        sup = f"，在训练集上的支持度为 {rule.support:.4f}" if rule.support is not None else ""
        return (
            f"该规则{src}{sup}。它约束字段 {('、'.join(fields) or '（未识别）')} 之间的关系："
            f"{interp or rule.text}。所有生成或回填的数据都必须满足这一约束，"
            f"违反即视为异常并在报告中标红。"
        )

    def _tags(self, rule: Rule) -> list[str]:
        tags = [_KIND_TAGS_ZH.get(rule.kind, rule.kind or "未分类")]
        tags.append("数据学习" if rule.source == "learned" else "人工规则")
        return tags


def _jsonable(value: Any) -> Any:
    """numpy/pandas 标量 → 原生 Python 类型，保证 Violation 可 JSON 序列化."""
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return value
