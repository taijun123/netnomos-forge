# -*- coding: utf-8 -*-
"""错误注入器测试：真值表完备性 + 注入差异精确性（stdlib unittest）."""
from __future__ import annotations

import unittest

try:
    import pandas as pd  # noqa: F401
    HAVE_DEPS = True
except ImportError:  # pragma: no cover
    HAVE_DEPS = False

from forge.contracts import FIN_FAULTS, FIN_FIELDS


@unittest.skipUnless(HAVE_DEPS, "需要 pandas")
class TestFinanceFaults(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from forge.scenarios.finance_v1.faults import build_clean_package, inject_faults
        cls.df_clean = build_clean_package()
        cls.df_faulty, cls.truth = inject_faults()

    # ---- 真值表含全部 5 个 fault，且结构完整 ----
    def test_truth_table_contains_all_faults(self):
        faults = self.truth["faults"]
        self.assertEqual(set(faults), set(FIN_FAULTS))
        for fid, entry in faults.items():
            for key in ("rule_id", "row_index", "period_index", "cells",
                        "message_zh"):
                self.assertIn(key, entry, f"{fid} 缺少 {key}")
            self.assertTrue(entry["cells"], f"{fid} cells 不应为空")
            for cell in entry["cells"]:
                for key in ("row_index", "field", "wrong_value", "correct_value"):
                    self.assertIn(key, cell, f"{fid} 单元格缺少 {key}")
                self.assertIn(cell["field"], FIN_FIELDS)
                self.assertNotEqual(cell["wrong_value"], cell["correct_value"])

    # ---- F1 叙事数值与 contracts 规格一致 ----
    def test_f1_matches_spec_numbers(self):
        f1 = self.truth["faults"]["F1"]
        r = f1["row_index"]
        row = self.df_faulty.iloc[r]
        self.assertEqual(int(row["Inventory_Begin"]), 10000)
        self.assertEqual(int(row["Purchases"]), 4000)
        self.assertEqual(int(row["Inventory_End"]), 12000)
        self.assertEqual(int(row["COGS"]), 3000)              # 错误值
        cogs_cell = next(c for c in f1["cells"] if c["field"] == "COGS")
        self.assertEqual(cogs_cell["wrong_value"], 3000)
        self.assertEqual(cogs_cell["correct_value"], 2000)    # 正确值
        # GrossProfit 用错误 COGS 连带算错（错误自洽，R05 不应命中）
        self.assertEqual(int(row["GrossProfit"]), int(row["Revenue"]) - 3000)
        self.assertEqual(f1["rule_id"], "R01")

    # ---- 其余 fault 的关键数值 ----
    def test_f2a_f2b_f3_f4_numbers(self):
        faults = self.truth["faults"]
        # F2a：第 1 期 Cash_End=8000，第 2 期 Cash_Begin 误记 8500
        self.assertEqual(int(self.df_faulty.iloc[0]["Cash_End"]), 8000)
        cell = next(c for c in faults["F2a"]["cells"] if c["field"] == "Cash_Begin")
        self.assertEqual((cell["wrong_value"], cell["correct_value"]), (8500, 8000))
        self.assertEqual(faults["F2a"]["rule_id"], "R04")
        # F2b：TotalAssets 比 TL+TE 多 500
        r = faults["F2b"]["row_index"]
        row = self.df_faulty.iloc[r]
        self.assertEqual(int(row["TotalAssets"])
                         - int(row["TotalLiabilities"]) - int(row["TotalEquity"]),
                         500)
        self.assertEqual(faults["F2b"]["rule_id"], "R02")
        # F3：consulting 公司存货占总资产 35%
        r = faults["F3"]["row_index"]
        row = self.df_faulty.iloc[r]
        ratio = int(row["Inventory_End"]) / int(row["TotalAssets"])
        self.assertAlmostEqual(ratio, 0.35, places=3)
        self.assertEqual(faults["F3"]["rule_id"], "R06")
        # F4：应收同比 +300%，营收同比 +15%
        r = faults["F4"]["row_index"]
        row = self.df_faulty.iloc[r]
        base = self.df_clean.iloc[r - 4]
        self.assertAlmostEqual(
            int(row["AccountsReceivable"]) / int(base["AccountsReceivable"]) - 1,
            3.0, places=6)
        self.assertAlmostEqual(
            int(row["Revenue"]) / int(base["Revenue"]) - 1, 0.15, places=6)
        self.assertEqual(faults["F4"]["rule_id"], "R07")

    # ---- df_faulty 与 df_clean 恰好在真值表标注处不同 ----
    def test_diff_cells_exactly_match_truth_table(self):
        marked = set()
        for entry in self.truth["faults"].values():
            for cell in entry["cells"]:
                marked.add((cell["row_index"], cell["field"]))
                # 真值表记录的错误值/正确值与两份数据一致
                self.assertEqual(
                    int(self.df_faulty.iloc[cell["row_index"]][cell["field"]]),
                    cell["wrong_value"])
                self.assertEqual(
                    int(self.df_clean.iloc[cell["row_index"]][cell["field"]]),
                    cell["correct_value"])
        actual = set()
        for r in range(len(self.df_clean)):
            for col in FIN_FIELDS:
                if self.df_clean.iloc[r][col] != self.df_faulty.iloc[r][col]:
                    actual.add((r, col))
        self.assertEqual(actual, marked,
                         "df_faulty 与 df_clean 的差异必须与真值表标注完全一致")

    # ---- 清洁基线本身干净 / 注入可复现 / 通用入口一致 ----
    def test_clean_baseline_and_reproducibility(self):
        from forge.scenarios.finance_v1.faults import inject_faults
        df2, truth2 = inject_faults()
        pd.testing.assert_frame_equal(self.df_faulty, df2)
        self.assertEqual(self.truth, truth2)
        # 清洁基线 8 期、字段齐全、单公司 consulting
        self.assertEqual(len(self.df_clean), 8)
        self.assertEqual(list(self.df_clean.columns), FIN_FIELDS)
        self.assertEqual(self.df_clean["Industry"].unique().tolist(), ["consulting"])

    def test_core_injector_wrapper(self):
        from forge.core.injector import inject, supported_scenarios
        self.assertIn("finance_v1", supported_scenarios())
        df_w, truth_w = inject("finance_v1")
        pd.testing.assert_frame_equal(df_w, self.df_faulty)
        self.assertEqual(truth_w, self.truth)
        with self.assertRaises(NotImplementedError):
            inject("no_such_scenario")

    # ---- 落盘产物 ----
    def test_save_package(self):
        import json
        import tempfile
        from pathlib import Path
        from forge.scenarios.finance_v1.faults import save_package

        with tempfile.TemporaryDirectory() as tmp:
            paths = save_package(tmp)
            faulty = pd.read_csv(paths["faulty_csv"])
            self.assertEqual(len(faulty), 8)
            self.assertEqual(list(faulty.columns), FIN_FIELDS)
            truth = json.loads(Path(paths["truth_table"]).read_text("utf-8"))
            self.assertEqual(set(truth["faults"]), set(FIN_FAULTS))
            self.assertEqual(truth["company_name_zh"], "华信咨询")


if __name__ == "__main__":
    unittest.main()
