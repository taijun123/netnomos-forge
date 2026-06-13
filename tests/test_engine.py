# -*- coding: utf-8 -*-
"""forge.core.engine 单元测试.

不依赖 netnomos 的部分实测；依赖 netnomos/z3 的端到端用 skipUnless 跳过（宿主机执行）。
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from forge.contracts import Rule, RuleSet
from forge.core.engine import (
    ForgeRuleEngine,
    classify_kind,
    collect_fields,
    load_ruleset,
    save_ruleset,
)
from forge.core.llm import RoutedLLM

HAS_NETNOMOS = bool(importlib.util.find_spec("netnomos") and importlib.util.find_spec("z3"))

# 示例公式：Proto=UDP(2) -> Flags=noflags(0)
IMPLIES_FORMULA = {
    "kind": "implies",
    "left": {"kind": "compare", "op": "=",
             "left": {"kind": "symbol", "name": "Proto"},
             "right": {"kind": "constant", "value": 2}},
    "right": {"kind": "compare", "op": "=",
              "left": {"kind": "symbol", "name": "Flags"},
              "right": {"kind": "constant", "value": 0}},
}
BOUND_FORMULA = {
    "kind": "compare", "op": "<=",
    "left": {"kind": "symbol", "name": "Bytes"},
    "right": {"kind": "constant", "value": 1500},
}


def make_ruleset() -> RuleSet:
    return RuleSet(scenario="network_cidds", rules=[
        Rule(rule_id="N001", formula=IMPLIES_FORMULA,
             text="Proto=UDP -> Flags=noflags", kind="implication", support=0.98),
        Rule(rule_id="N002", formula=BOUND_FORMULA,
             text="Bytes <= 1500", kind="bound", source="manual"),
        Rule(rule_id="N003", formula=BOUND_FORMULA,
             text="（已禁用）", kind="bound", enabled=False),
    ])


class TestFormulaHelpers(unittest.TestCase):
    def test_classify_kind(self):
        self.assertEqual(classify_kind(IMPLIES_FORMULA), "implication")
        self.assertEqual(classify_kind(BOUND_FORMULA), "bound")
        self.assertEqual(classify_kind({"kind": "compare", "op": "="}), "identity")
        self.assertEqual(classify_kind({"kind": "compare", "op": "!="}), "exclusion")
        self.assertEqual(classify_kind({"kind": "and", "values": []}), "composite")
        self.assertEqual(classify_kind({"kind": "forall"}), "quantified")
        self.assertEqual(classify_kind({}), "")

    def test_collect_fields_dedup_ordered(self):
        self.assertEqual(collect_fields(IMPLIES_FORMULA), ["Proto", "Flags"])
        nested = {"kind": "and", "values": [IMPLIES_FORMULA, BOUND_FORMULA, BOUND_FORMULA]}
        self.assertEqual(collect_fields(nested), ["Proto", "Flags", "Bytes"])


class TestRuleSetPersistence(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        rs = make_ruleset()
        with tempfile.TemporaryDirectory() as tmp:
            saved = save_ruleset(rs, out_dir=tmp)
            # NetNomos 格式 rules.json 可被 stdlib 读回
            payload = json.loads((Path(tmp) / "rules.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload), 3)
            self.assertEqual(payload[0]["rule_id"], "N001")
            self.assertEqual(payload[0]["formula"], IMPLIES_FORMULA)
            self.assertEqual(payload[0]["display"], "Proto=UDP -> Flags=noflags")
            # contracts 格式 ruleset.json round-trip
            loaded = load_ruleset(tmp)
            self.assertEqual(loaded.scenario, "network_cidds")
            self.assertEqual([r.rule_id for r in loaded.rules], ["N001", "N002", "N003"])
            self.assertEqual(loaded.rules_path, saved.rules_path)
            self.assertFalse(loaded.rules[2].enabled)
            self.assertEqual(len(loaded.enabled_rules()), 2)


class TestEngineWithoutNetNomos(unittest.TestCase):
    def setUp(self):
        self.engine = ForgeRuleEngine.from_scenario("network_cidds")

    def test_from_scenario_reads_specs(self):
        self.assertEqual(self.engine.scenario, "network_cidds")
        self.assertTrue(self.engine.dataset_spec_path.exists())
        self.assertTrue(self.engine.grammar_spec_path.exists())
        # 默认数据路径按 spec 所在目录解析为绝对路径
        self.assertIsNotNone(self.engine.default_data_path)
        self.assertTrue(self.engine.default_data_path.is_absolute())
        self.assertEqual(self.engine.default_data_path.name, "cidds_wk2_normal_10k.csv")

    def test_from_scenario_missing_raises_friendly(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            ForgeRuleEngine.from_scenario("no_such_scenario")
        self.assertIn("dataset_spec.json", str(ctx.exception))

    @unittest.skipIf(HAS_NETNOMOS, "宿主机已装 netnomos，缺依赖报错路径不适用")
    def test_learn_without_netnomos_raises_with_hint(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.engine.learn(None)
        self.assertIn("uv sync", str(ctx.exception))
        self.assertIn("netnomos", str(ctx.exception))

    def test_add_manual_rules_merges_and_overrides(self):
        rs = make_ruleset()
        manual = [
            {"rule_id": "M001", "formula": BOUND_FORMULA, "display": "Bytes <= 1500",
             "support": 1.0},
            # 与 N001 同名 → 人工覆盖
            {"rule_id": "N001", "formula": IMPLIES_FORMULA, "display": "人工改写版"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_rules.json"
            path.write_text(json.dumps(manual), encoding="utf-8")
            merged = self.engine.add_manual_rules(rs, path)
        self.assertEqual(len(merged.rules), 4)
        by_id = {r.rule_id: r for r in merged.rules}
        self.assertEqual(by_id["M001"].source, "manual")
        self.assertEqual(by_id["M001"].kind, "bound")
        self.assertEqual(by_id["N001"].source, "manual")
        self.assertEqual(by_id["N001"].text, "人工改写版")
        # 原集不被原地修改
        self.assertEqual(len(rs.rules), 3)

    def test_add_manual_rules_rejects_non_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.engine.add_manual_rules(make_ruleset(), path)

    def test_load_netnomos_rules_preserves_learned_source(self):
        learned = [
            {"rule_id": "hs00001", "formula": BOUND_FORMULA, "display": "Bytes <= 1500",
             "support": 1.0, "source": {"learner": "hitting-set", "predicate_ids": ["p1"]}},
            {"rule_id": "M001", "formula": BOUND_FORMULA, "display": "Manual domain rule",
             "support": 1.0, "source": {"original_file": "manual_rules.json"}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(json.dumps(learned), encoding="utf-8")
            ruleset = self.engine.load_netnomos_rules(path)
        by_id = {r.rule_id: r for r in ruleset.rules}
        self.assertEqual(by_id["hs00001"].source, "learned")
        self.assertEqual(by_id["M001"].source, "manual")
        self.assertEqual(ruleset.rules_path, str(path))

    def test_explain_without_llm_uses_template(self):
        """llm=None：确定性模板降级，任何环境都能出卡（禁用规则不出卡）."""
        cards = self.engine.explain(make_ruleset(), llm=None)
        self.assertEqual(len(cards), 2)  # N003 已禁用
        card = cards[0]
        self.assertEqual(card.rule_id, "N001")
        self.assertTrue(card.title_zh)
        self.assertIn("Proto", card.title_zh)
        self.assertIn("Proto=UDP -> Flags=noflags", card.explanation_zh)
        self.assertIn("支持度", card.explanation_zh)
        self.assertEqual(card.formula_text, "Proto=UDP -> Flags=noflags")
        self.assertIn("数据学习", card.tags)
        self.assertFalse(card.is_coincidence)
        # 人工规则的标签
        self.assertIn("人工规则", cards[1].tags)
        # 确定性：再跑一次结果一致
        again = self.engine.explain(make_ruleset(), llm=None)
        self.assertEqual(card.explanation_zh, again[0].explanation_zh)

    def test_explain_with_mock_llm(self):
        cards = self.engine.explain(make_ruleset(), llm=RoutedLLM(force_backend="mock"))
        self.assertEqual(len(cards), 2)
        self.assertIn("[mock:explain]", cards[0].explanation_zh)

    def test_validate_without_ruleset_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.engine.validate(None, rules=None)
        self.assertIn("learn", str(ctx.exception))


@unittest.skipUnless(HAS_NETNOMOS, "需要 netnomos + z3（宿主机 uv sync 后执行）")
class TestEngineEndToEnd(unittest.TestCase):
    """宿主机端到端：小样本 learn → validate → check（沙箱自动跳过）."""

    def test_learn_validate_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = ForgeRuleEngine.from_scenario("network_cidds", runs_dir=tmp)
            ruleset = engine.learn(None, limit=300)
            self.assertGreater(len(ruleset.rules), 0)
            self.assertTrue(Path(ruleset.rules_path).exists())
            report = engine.validate(None, ruleset)
            self.assertEqual(report.scenario, "network_cidds")
            self.assertGreater(report.total_rows, 0)
            # 学到的规则对训练数据应当全满足
            self.assertAlmostEqual(report.satisfaction_rate, 1.0, places=6)
            self.assertTrue(report.ok)
            # 蕴含检查：任一已学规则的 display 应被规则集蕴含
            self.assertTrue(engine.check(ruleset, ruleset.rules[0].text))


if __name__ == "__main__":
    unittest.main()
