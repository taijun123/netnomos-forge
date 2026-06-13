# -*- coding: utf-8 -*-
"""test_projector — Projector 数值投影与修正单测（恒等式逐条验证）.

策略：以 finance_v1 的确定性清洁基线为底，逐条破坏单个恒等式字段，
经 FinanceValidator 产出 ViolationReport 后交 Projector 修正，断言：
- 被破坏字段恢复为恒等式解（与清洁基线一致或满足恒等式）；
- 干预日志为中文且引用规则号；
- R06/R07 类画像/比率违规只产生风险提示、不改数。
"""
from __future__ import annotations

import unittest
from importlib.util import find_spec

from forge.core.projector import Projector
from forge.scenarios.finance_v1.faults import build_clean_package, inject_faults
from forge.scenarios.finance_v1.validator import FinanceValidator


def _validate(df):
    return FinanceValidator().validate(df, "<unit-test>")


class TestProjectorIdentities(unittest.TestCase):
    """构造小 DataFrame 单测各恒等式修正."""

    def setUp(self):
        self.clean = build_clean_package()
        self.projector = Projector()

    def test_r01_cogs_correction_with_cascade(self):
        """R01：COGS 被篡改 → 按勾稽恢复，毛利连带重算（恢复 = 清洁值）."""
        df = self.clean.copy()
        row = 2
        df.at[row, "COGS"] = int(df.at[row, "COGS"]) + 700   # 只破坏 COGS
        report = _validate(df)
        self.assertIn("R01", report.by_rule)
        self.assertIn("R05", report.by_rule)                  # GP 未同步 → R05 也命中
        out, logs = self.projector.project(report, df)
        self.assertEqual(int(out.at[row, "COGS"]), int(self.clean.at[row, "COGS"]))
        self.assertEqual(int(out.at[row, "GrossProfit"]),
                         int(self.clean.at[row, "GrossProfit"]))
        self.assertTrue(any("[R01]" in line and "修正" in line for line in logs))
        # 修正后复验：零违规
        self.assertTrue(_validate(out).ok)

    def test_r02_total_liabilities_recomputed(self):
        """R02：资产虚增 → 以恒等式重算 TotalLiabilities（配平恢复）."""
        df = self.clean.copy()
        row = 4
        df.at[row, "TotalAssets"] = int(df.at[row, "TotalAssets"]) + 300
        report = _validate(df)
        self.assertIn("R02", report.by_rule)
        out, logs = self.projector.project(report, df)
        ta = int(out.at[row, "TotalAssets"])
        self.assertEqual(ta, int(out.at[row, "TotalLiabilities"])
                         + int(out.at[row, "TotalEquity"]))
        self.assertTrue(any("[R02]" in line for line in logs))

    def test_r03_r04_cross_period_rollforward(self):
        """R03/R04：跨期断裂 → 以上期期末为准修正."""
        df = self.clean.copy()
        row = 3
        df.at[row, "Inventory_Begin"] = int(df.at[row, "Inventory_Begin"]) + 111
        df.at[row, "Cash_Begin"] = int(df.at[row, "Cash_Begin"]) + 222
        report = _validate(df)
        self.assertIn("R03", report.by_rule)
        self.assertIn("R04", report.by_rule)
        out, logs = self.projector.project(report, df)
        prev = row - 1
        self.assertEqual(int(out.at[row, "Inventory_Begin"]),
                         int(self.clean.at[prev, "Inventory_End"]))
        self.assertEqual(int(out.at[row, "Cash_Begin"]),
                         int(self.clean.at[prev, "Cash_End"]))
        self.assertTrue(any("[R03]" in line for line in logs))
        self.assertTrue(any("[R04]" in line for line in logs))

    def test_r06_r07_hint_only_no_mutation(self):
        """R06/R07（F3/F4 类）：只产生风险提示，不改数."""
        df_faulty, truth = inject_faults()
        report = _validate(df_faulty)
        out, logs = self.projector.project(report, df_faulty)
        # F3（R06）/F4（R07）涉及的账面值保持原样
        r6 = truth["faults"]["F3"]["row_index"]
        r7 = truth["faults"]["F4"]["row_index"]
        self.assertEqual(int(out.at[r6, "Inventory_End"]),
                         int(df_faulty.at[r6, "Inventory_End"]))
        self.assertEqual(int(out.at[r7, "AccountsReceivable"]),
                         int(df_faulty.at[r7, "AccountsReceivable"]))
        self.assertTrue(any(line.startswith("【风险提示·R06】") for line in logs))
        self.assertTrue(any(line.startswith("【风险提示·R07】") for line in logs))

    def test_full_package_projection_values_derived_not_hardcoded(self):
        """华信资料包端到端：修正值由 observed 推导（COGS 恢复 2000 等）."""
        df_faulty, truth = inject_faults()
        report = _validate(df_faulty)
        out, logs = self.projector.project(report, df_faulty)
        f1 = truth["faults"]["F1"]
        cell = next(c for c in f1["cells"] if c["field"] == "COGS")
        self.assertEqual(int(out.at[f1["row_index"], "COGS"]), cell["correct_value"])
        f2a = truth["faults"]["F2a"]
        cell = next(c for c in f2a["cells"] if c["field"] == "Cash_Begin")
        self.assertEqual(int(out.at[f2a["row_index"], "Cash_Begin"]),
                         cell["correct_value"])
        # 修正后复验：勾稽类（R01–R05）零违规，仅剩画像/比率提示类
        after = _validate(out)
        self.assertFalse(set(after.by_rule) & {"R01", "R02", "R03", "R04", "R05"})
        self.assertTrue(logs)

    def test_no_violation_no_change(self):
        """零违规：原样返回 + 提示性日志."""
        report = _validate(self.clean)
        self.assertTrue(report.ok)
        out, logs = self.projector.project(report, self.clean)
        self.assertTrue((out == self.clean).all().all())
        self.assertEqual(logs, ["未发现违规，无需数值修正。"])


class TestProjectorZ3(unittest.TestCase):
    """z3 增强接口：沙箱抛中文指引；有 z3 时结果与纯 Python 等价."""

    def test_z3_unavailable_raises_chinese_hint(self):
        if find_spec("z3") is not None:
            self.skipTest("本环境有 z3，跳过缺失指引测试")
        df_faulty, _ = inject_faults()
        report = _validate(df_faulty)
        with self.assertRaises(RuntimeError) as ctx:
            Projector().project_with_z3(report, df_faulty)
        self.assertIn("z3", str(ctx.exception))
        self.assertIn("宿主机", str(ctx.exception))

    @unittest.skipUnless(find_spec("z3") is not None, "需要 z3-solver（宿主机）")
    def test_z3_projection_matches_pure_python(self):
        df_faulty, truth = inject_faults()
        report = _validate(df_faulty)
        out, _ = Projector().project_with_z3(report, df_faulty)
        f1 = truth["faults"]["F1"]
        cell = next(c for c in f1["cells"] if c["field"] == "COGS")
        self.assertEqual(int(out.at[f1["row_index"], "COGS"]), cell["correct_value"])


if __name__ == "__main__":
    unittest.main()
