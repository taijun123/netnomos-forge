# -*- coding: utf-8 -*-
"""RuleExplainer RAG tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forge.contracts import Rule, RuleCard, RuleSet
from forge.core.explainer import RuleExplainer


def _rule(rule_id: str = "R01", text: str | None = None) -> Rule:
    return Rule(
        rule_id=rule_id,
        formula={"fields": ["Inventory_End", "Inventory_Begin", "Purchases", "COGS"]},
        text=text or "Inventory_End = Inventory_Begin + Purchases - COGS",
        kind="identity",
        source="manual",
        support=1.0,
    )


def _card(rule_id: str = "R01") -> RuleCard:
    return RuleCard(
        rule_id=rule_id,
        title_zh="模板标题",
        explanation_zh="模板解释",
        formula_text="Inventory_End = Inventory_Begin + Purchases - COGS",
    )


class _CountingLLM:
    def __init__(self):
        self.calls: list[dict[str, str]] = []

    def complete(self, prompt: str, role: str, system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "role": role, "system": system or ""})
        return "这是经过 RAG 知识增强后的解释。"


class TestRuleExplainerRAG(unittest.TestCase):
    def test_loads_markdown_and_json_from_multiple_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = root / "core"
            scenario = root / "scenario"
            core.mkdir()
            scenario.mkdir()
            (core / "core.md").write_text(
                "# Core Doc\n\n## NetNomos 规则\nInventory 和 COGS 可用于解释财务恒等式。",
                encoding="utf-8",
            )
            (scenario / "finance.json").write_text(
                """{
                  "doc_title": "Finance JSON",
                  "tags": ["finance"],
                  "sections": [{
                    "heading": "存货滚动",
                    "tags": ["Inventory", "COGS", "R01"],
                    "body": "存货滚动把采购、营业成本和期末存货连接起来。"
                  }]
                }""",
                encoding="utf-8",
            )

            explainer = RuleExplainer(knowledge_dirs=[core, scenario])
            citations = [section.citation for section in explainer.sections]

        self.assertIn("Core Doc · NetNomos 规则", citations)
        self.assertIn("Finance JSON · 存货滚动", citations)

    def test_retrieve_prefers_scenario_tags_and_heading(self):
        explainer = RuleExplainer.for_scenario("finance_v1")
        hits = explainer.retrieve(_rule(), context="财务报表审阅", k=1)
        self.assertEqual(len(hits), 1)
        self.assertIn("存货", hits[0].heading)

    def test_network_scenario_json_is_retrievable(self):
        rule = Rule(
            rule_id="N01",
            formula={"fields": ["Proto", "Flags"]},
            text="Proto = UDP -> Flags = noflags",
            kind="implication",
            source="manual",
            support=1.0,
        )
        hits = RuleExplainer.for_scenario("network_cidds").retrieve(
            rule,
            context="NetFlow 流量审计",
            k=1,
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("UDP", hits[0].heading)

    def test_build_prompt_clips_knowledge_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            large_body = "Inventory COGS " + ("长正文 " * 500)
            (knowledge_dir / "large.json").write_text(
                f"""{{
                  "doc_title": "Large Doc",
                  "sections": [{{
                    "heading": "Inventory COGS",
                    "tags": ["Inventory", "COGS"],
                    "body": "{large_body}"
                  }}]
                }}""",
                encoding="utf-8",
            )
            prompt = RuleExplainer(
                knowledge_dir=knowledge_dir,
                max_section_chars=80,
                max_context_chars=180,
            ).build_prompt(_rule(), context="财务报表审阅")

        self.assertIn("...", prompt)
        self.assertLess(len(prompt), 900)

    def test_enhance_caps_llm_calls_and_keeps_citations(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / "finance.json").write_text(
                """{
                  "doc_title": "Finance JSON",
                  "sections": [{
                    "heading": "存货滚动",
                    "tags": ["Inventory", "COGS", "R01", "R02"],
                    "body": "Inventory、COGS 与 Purchases 的勾稽解释。"
                  }]
                }""",
                encoding="utf-8",
            )
            ruleset = RuleSet(scenario="finance_v1", rules=[
                _rule("R01"),
                _rule("R02", "Inventory_End = Inventory_Begin + Purchases - COGS"),
            ])
            cards = [_card("R01"), _card("R02")]
            llm = _CountingLLM()
            enhanced = RuleExplainer(knowledge_dir=knowledge_dir).enhance(
                cards,
                ruleset,
                llm=llm,
                context="财务报表审阅",
                max_llm_cards=1,
            )

        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(enhanced[0].explanation_zh, "这是经过 RAG 知识增强后的解释。")
        self.assertEqual(enhanced[1].explanation_zh, "模板解释")
        self.assertTrue(enhanced[0].citation)
        self.assertTrue(enhanced[1].citation)


if __name__ == "__main__":
    unittest.main()
