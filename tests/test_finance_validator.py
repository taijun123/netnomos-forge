# -*- coding: utf-8 -*-
"""FinanceValidator 测试：命中全部 F1–F4（5 项）、零误报、expected 可读修正."""
from __future__ import annotations

import unittest

try:
    import pandas as pd  # noqa: F401
    HAVE_DEPS = True
except ImportError:  # pragma: no cover
    HAVE_DEPS = False

from forge.contracts import FIN_FAULTS, ViolationReport


@unittest.skipUnless(HAVE_DEPS, "需要 pandas")
class TestFinanceValidator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from forge.scenarios.finance_v1.faults import build_clean_package, inject_faults
        from forge.scenarios.finance_v1.validator import FinanceValidator
        cls.validator = FinanceValidator()
        cls.df_clean = build_clean_package()
        cls.df_faulty, cls.truth = inject_faults()

    # ---- 对 df_clean 零违规（华信清洁基线） ----
    def test_clean_package_zero_violations(self):
        report = self.validator.validate(self.df_clean)
        self.assertIsInstance(report, ViolationReport)
        self.assertEqual(report.violations, [],
                         f"清洁基线不应有违规: {[v.message_zh for v in report.violations]}")
        self.assertEqual(report.satisfaction_rate, 1.0)
        self.assertTrue(report.ok)

    # ---- 对 960 行训练集零违规 ----
    def test_training_data_zero_violations(self):
        from forge.scenarios.finance_v1.generator import generate_training_data
        report = self.validator.validate(generate_training_data(seed=42))
        self.assertEqual(report.violations, [])
        self.assertEqual(report.satisfaction_rate, 1.0)

    # ---- 命中全部 F1–F4（5 项）且无误报 ----
    def test_faulty_package_hits_all_faults_no_false_positive(self):
        report = self.validator.validate(self.df_faulty)
        self.assertEqual(len(report.violations), len(FIN_FAULTS),
                         f"应恰好 {len(FIN_FAULTS)} 项违规: "
                         f"{[(v.rule_id, v.row_index) for v in report.violations]}")
        expected_hits = {
            (entry["row_index"], entry["rule_id"])
            for entry in self.truth["faults"].values()
        }
        actual_hits = {(v.row_index, v.rule_id) for v in report.violations}
        self.assertEqual(actual_hits, expected_hits,
                         "违规 (行号, 规则) 必须与真值表一一对应——既不漏报也不误报")
        # by_rule 与 satisfaction_rate 自洽
        self.assertEqual(sum(report.by_rule.values()), len(report.violations))
        bad_rows = len({v.row_index for v in report.violations})
        self.assertAlmostEqual(report.satisfaction_rate,
                               1.0 - bad_rows / report.total_rows)
        self.assertFalse(report.ok)

    # ---- F1 expected 文本含可读修正 "2,000" ----
    def test_f1_expected_text(self):
        report = self.validator.validate(self.df_faulty)
        v_r01 = [v for v in report.violations if v.rule_id == "R01"]
        self.assertEqual(len(v_r01), 1)
        v = v_r01[0]
        self.assertIn("2,000", v.expected)
        self.assertIn("10,000", v.expected)
        self.assertIn("4,000", v.expected)
        self.assertIn("12,000", v.expected)
        self.assertEqual(v.observed["COGS"], 3000)
        self.assertTrue(v.message_zh)

    # ---- 其余规则的 expected/observed 可读性 ----
    def test_other_violation_payloads(self):
        report = self.validator.validate(self.df_faulty)
        by_rule = {v.rule_id: v for v in report.violations}
        self.assertIn("应为 8,000", by_rule["R04"].expected)
        self.assertIn("832,000", by_rule["R02"].expected)
        self.assertIn("consulting", by_rule["R06"].expected)
        self.assertIn("+300%", by_rule["R07"].observed["应收同比增速"])
        for v in report.violations:
            self.assertTrue(v.fields)
            self.assertTrue(v.rule_text)
            self.assertTrue(v.message_zh)

    # ---- CSV 路径输入 ----
    def test_validate_from_csv_path(self):
        import tempfile
        from pathlib import Path
        from forge.scenarios.finance_v1.generator import save_csv

        with tempfile.TemporaryDirectory() as tmp:
            path = save_csv(self.df_faulty, Path(tmp) / "faulty.csv")
            report = self.validator.validate(path)
            self.assertEqual(len(report.violations), len(FIN_FAULTS))
            self.assertEqual(report.data_path, path)

    # ---- 缺字段时显式报错 ----
    def test_missing_field_raises(self):
        with self.assertRaises(ValueError):
            self.validator.validate(self.df_clean.drop(columns=["COGS"]))


if __name__ == "__main__":
    unittest.main()
