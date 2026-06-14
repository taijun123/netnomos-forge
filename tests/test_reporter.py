# -*- coding: utf-8 -*-
"""test_reporter — DualReporter 双轨报告单测（财务 + 网络，mock LLM 确定性）."""
from __future__ import annotations

import unittest

from forge.core.llm import RoutedLLM
from forge.core.reporter import (
    DualReporter,
    check_netflow_rows,
    extract_number_tokens,
    final_check,
    mock_netflow_with_errors,
)
from forge.scenarios.finance_v1.faults import inject_faults


def _int(slot_value: str) -> int:
    return int(str(slot_value).replace(",", "").replace("+", ""))


class TestNumberScan(unittest.TestCase):
    """终检工具：数值 token 提取与白名单扫描."""

    def test_extract_number_tokens(self):
        tokens = extract_number_tokens(
            "营业成本 2,000 千元，毛利率 96.43%，R01 命中 1 处，编号 a3f9。")
        self.assertIn("2,000", tokens)
        self.assertIn("96.43", tokens)
        self.assertIn("1", tokens)
        # 字母粘连的数字（R01 / a3f9）不是独立 token
        self.assertNotIn("01", tokens)
        self.assertNotIn("3", tokens)

    def test_final_check_flags_foreign_number(self):
        warnings = final_check("成本为 9,999 千元", {"cogs": "2,000"}, "")
        self.assertTrue(any("9,999" in w for w in warnings))

    def test_final_check_flags_residual_slot(self):
        warnings = final_check("成本为 {{cogs}} 千元", {}, "")
        self.assertTrue(any("残留" in w for w in warnings))

    def test_final_check_passes_whitelisted(self):
        self.assertEqual(
            final_check("成本为 2,000 千元", {"cogs": "2,000"}, ""), [])


class TestFinanceDualReport(unittest.TestCase):
    """财务双轨：A 轨照抄错误 / B 轨修正回填 / diff 标红."""

    @classmethod
    def setUpClass(cls):
        cls.df_faulty, cls.truth = inject_faults()
        cls.reporter = DualReporter(llm=RoutedLLM(force_backend="mock"))
        cls.dual = cls.reporter.make_dual(cls.df_faulty, truth=cls.truth)

    def test_track_a_contains_wrong_values(self):
        """A 轨文本照抄错误数字（3,000），且毛利率被连带算错."""
        md = self.dual.track_a.markdown
        self.assertIn("3,000", md)            # F1 错误 COGS
        self.assertIn("8,500", md)            # F2a 错误期初现金
        self.assertIn("96.43%", md)           # 用错误 COGS 连带算错的毛利率
        self.assertTrue(self.dual.track_a.violations)   # 标红依据

    def test_diff_html_err_and_ok_spans(self):
        html = self.dual.diff_html
        self.assertIn('class="err', html)
        self.assertIn('class="ok', html)
        self.assertIn("应为 2,000", html)              # R01 修正提示
        self.assertIn("3,000", html)                   # A 轨错误值被包裹
        # 类名对齐 web FinanceDemoPage 约定
        self.assertIn("mark-num", html)
        self.assertIn("mark-bad", html)
        self.assertIn("track-col track-a", html)
        self.assertIn("track-col track-b", html)

    def test_track_b_slots_corrected(self):
        slots = self.dual.track_b.slots
        self.assertEqual(_int(slots["cogs_corrected"]), 2000)
        self.assertEqual(_int(slots["cogs_reported"]), 3000)
        # 毛利按修正后 COGS 重算：84,000 - 2,000 = 82,000（值来自资料包推导）
        self.assertEqual(_int(slots["gross_profit_corrected"]), 82000)
        self.assertEqual(slots["f1_period"], "3")
        self.assertEqual(_int(slots["f2a_cash_end_prev"]), 8000)

    def test_track_b_intervention_log_and_final_check(self):
        self.assertTrue(self.dual.track_b.intervention_log)
        self.assertEqual(self.reporter.last_b_warnings, [])     # 终检零告警
        self.assertFalse(any(line.startswith("【终检告警】")
                             for line in self.dual.track_b.intervention_log))
        self.assertNotIn("{{", self.dual.track_b.markdown)      # 无残留槽位
        self.assertEqual(self.dual.track_b.violations, [])      # B 轨零违规

    def test_truth_table_match_summary(self):
        self.assertTrue(
            self.dual.track_b.slots["truth_table_match_summary"].startswith("5/5"))

    def test_values_derived_from_violations_not_hardcoded(self):
        """换一家公司数据（清洁 → 自定义破坏），槽位随数据变化."""
        from forge.scenarios.finance_v1.faults import build_clean_package
        df = build_clean_package()
        row = 5
        df.at[row, "COGS"] = int(df.at[row, "COGS"]) + 250
        dual = DualReporter(llm=RoutedLLM(force_backend="mock")).make_dual(df)
        slots = dual.track_b.slots
        self.assertEqual(slots["f1_period"], str(int(df.at[row, "PeriodIndex"])))
        self.assertEqual(_int(slots["f1_diff"]), 250)


class TestNetworkDualReport(unittest.TestCase):
    """网络双轨：A 轨确定性带错样本 / B 轨 LeJIT 或预置合规样本."""

    @classmethod
    def setUpClass(cls):
        cls.reporter = DualReporter(llm=RoutedLLM(force_backend="mock"))
        cls.dual = cls.reporter.make_dual_network(10)

    def test_mock_sample_has_three_error_kinds(self):
        violations = check_netflow_rows(mock_netflow_with_errors(10))
        self.assertEqual({v.rule_id for v in violations}, {"N01", "N02", "N03"})

    def test_track_a_violations_marked(self):
        self.assertGreaterEqual(len(self.dual.track_a.violations), 3)
        self.assertIn('class="err', self.dual.diff_html)

    def test_track_b_zero_violations_with_fallback_note(self):
        self.assertEqual(self.dual.track_b.violations, [])
        log_text = "\n".join(self.dual.track_b.intervention_log)
        self.assertTrue(
            "sample_b.json" in log_text or "LeJIT 约束解码生成" in log_text,
            log_text,
        )
        self.assertIn("0 违规", log_text)

    def test_sample_b_rows_compliant(self):
        rows = self.dual.track_b.slots["rows"]
        self.assertEqual(len(rows), 10)
        self.assertEqual(check_netflow_rows(rows), [])

    def test_track_a_uses_supplied_rows_without_mock_replacement(self):
        rows = [
            {
                "Proto": "UDP",
                "SrcIpAddr": "192.168.220.8",
                "SrcPt": 34358,
                "DstIpAddr": "DNS",
                "DstPt": 53,
                "Packets": 2,
                "Bytes": 164,
                "Flags": "......",
            },
            {
                "Proto": "TCP",
                "SrcIpAddr": "192.168.220.16",
                "SrcPt": 37922,
                "DstIpAddr": "10082_43",
                "DstPt": 443,
                "Packets": 5,
                "Bytes": 1100,
                "Flags": ".AP.SF",
            },
        ]
        dual = self.reporter.make_dual_network(
            10,
            track_a_rows=rows,
            track_a_source_label="uploaded clean sample",
        )
        self.assertEqual(dual.track_a.slots["rows"], rows)
        self.assertEqual(dual.track_a.violations, [])
        self.assertEqual(len(dual.track_b.slots["rows"]), len(rows))
        self.assertIn("uploaded clean sample", dual.track_a.markdown)


if __name__ == "__main__":
    unittest.main()
