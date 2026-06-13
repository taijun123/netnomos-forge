# -*- coding: utf-8 -*-
"""财务数据生成器测试（stdlib unittest；缺 pandas/numpy 时整体跳过）."""
from __future__ import annotations

import unittest

try:
    import pandas as pd  # noqa: F401
    import numpy as np  # noqa: F401
    HAVE_DEPS = True
except ImportError:  # pragma: no cover
    HAVE_DEPS = False

from forge.contracts import (
    FIN_COMPANIES_PER_INDUSTRY,
    FIN_FIELDS,
    FIN_INDUSTRIES,
    FIN_PERIODS,
)


@unittest.skipUnless(HAVE_DEPS, "需要 pandas/numpy")
class TestFinanceGenerator(unittest.TestCase):
    """生成器：规模 / 字段 / 恒等式 / 跨期滚动 / 行业区间 / 可复现性."""

    @classmethod
    def setUpClass(cls):
        from forge.scenarios.finance_v1.generator import generate_training_data
        cls.df = generate_training_data(seed=42)

    # ---- 规模与字段 ----
    def test_shape_960_rows_all_fields(self):
        expected_rows = len(FIN_INDUSTRIES) * FIN_COMPANIES_PER_INDUSTRY * FIN_PERIODS
        self.assertEqual(len(self.df), 960)
        self.assertEqual(len(self.df), expected_rows)
        self.assertEqual(list(self.df.columns), FIN_FIELDS)
        self.assertEqual(self.df["CompanyId"].nunique(), 120)
        # 金额/计数字段全部为整数（千元整数约定）
        for col in FIN_FIELDS:
            if col in ("CompanyId", "Industry"):
                continue
            self.assertTrue(
                pd.api.types.is_integer_dtype(self.df[col]),
                f"{col} 应为整数类型，实际 {self.df[col].dtype}")

    # ---- 校验器全绿 ----
    def test_validator_satisfaction_rate_is_one(self):
        from forge.scenarios.finance_v1.validator import FinanceValidator
        report = FinanceValidator().validate(self.df)
        self.assertEqual(report.violations, [])
        self.assertEqual(report.satisfaction_rate, 1.0)
        self.assertTrue(report.ok)

    # ---- 行内恒等式（R01/R02/R05 + 资产构成 + 派生字段口径） ----
    def test_row_identities(self):
        df = self.df
        self.assertTrue((df["Inventory_End"] ==
                         df["Inventory_Begin"] + df["Purchases"] - df["COGS"]).all())
        self.assertTrue((df["TotalAssets"] ==
                         df["TotalLiabilities"] + df["TotalEquity"]).all())
        self.assertTrue((df["GrossProfit"] == df["Revenue"] - df["COGS"]).all())
        self.assertTrue((df["TotalAssets"] ==
                         df["Cash_End"] + df["Inventory_End"]
                         + df["AccountsReceivable"] + df["OtherAssets"]).all())
        self.assertTrue((df["InventoryNetInflow"] ==
                         df["Purchases"] - df["COGS"]).all())
        # Bp 派生字段与原始字段口径一致
        from forge.scenarios.finance_v1.generator import bp
        for rec in df.sample(50, random_state=0).itertuples():
            self.assertEqual(rec.InventoryToAssetsBp,
                             bp(rec.Inventory_End, rec.TotalAssets))
            self.assertEqual(rec.ReceivableToRevenueBp,
                             bp(rec.AccountsReceivable, rec.Revenue))

    # ---- 跨期滚动全对（R03/R04） ----
    def test_cross_period_rolling(self):
        for cid, g in self.df.groupby("CompanyId"):
            g = g.sort_values("PeriodIndex")
            self.assertEqual(list(g["PeriodIndex"]), list(range(1, FIN_PERIODS + 1)),
                             f"{cid} 期数应为 1..{FIN_PERIODS}")
            self.assertTrue(
                (g["Inventory_Begin"].iloc[1:].values ==
                 g["Inventory_End"].iloc[:-1].values).all(),
                f"{cid} 存货跨期滚动断裂")
            self.assertTrue(
                (g["Cash_Begin"].iloc[1:].values ==
                 g["Cash_End"].iloc[:-1].values).all(),
                f"{cid} 现金跨期滚动断裂")

    # ---- 行业差异化区间 ----
    def test_industry_bands(self):
        from forge.scenarios.finance_v1.generator import (
            SPEC_AR_RATIO_BAND, SPEC_INV_BP_BAND, SPEC_MARGIN_BAND)
        for industry, g in self.df.groupby("Industry"):
            self.assertIn(industry, FIN_INDUSTRIES)
            inv_bp = g["Inventory_End"] / g["TotalAssets"] * 10000
            lo, hi = SPEC_INV_BP_BAND[industry]
            self.assertTrue(((inv_bp > lo - 1e-9) & (inv_bp <= hi)).all(),
                            f"{industry} 存货占比越界: [{inv_bp.min():.1f}, "
                            f"{inv_bp.max():.1f}] bp")
            margin = g["GrossProfit"] / g["Revenue"]
            mlo, mhi = SPEC_MARGIN_BAND[industry]
            self.assertTrue(((margin >= mlo) & (margin <= mhi)).all(),
                            f"{industry} 毛利率越界: [{margin.min():.3f}, "
                            f"{margin.max():.3f}]")
            ar = g["AccountsReceivable"] / g["Revenue"]
            alo, ahi = SPEC_AR_RATIO_BAND[industry]
            self.assertTrue(((ar >= alo) & (ar <= ahi)).all(),
                            f"{industry} 应收/营收越界: [{ar.min():.3f}, "
                            f"{ar.max():.3f}]")
        # consulting 存货占比 < 2% 的字面口径
        cons = self.df[self.df["Industry"] == "consulting"]
        self.assertTrue(
            (cons["Inventory_End"] / cons["TotalAssets"] < 0.02).all())

    # ---- 数值健康度 ----
    def test_values_sane(self):
        df = self.df
        for col in ("Revenue", "COGS", "Purchases", "Cash_End", "Inventory_End",
                    "AccountsReceivable", "OtherAssets", "TotalAssets",
                    "TotalLiabilities", "TotalEquity"):
            self.assertTrue((df[col] > 0).all(), f"{col} 应为正数")
        self.assertTrue((df["NetProfit"] <= df["GrossProfit"]).all())

    # ---- 同 seed 可复现 ----
    def test_reproducible_same_seed(self):
        from forge.scenarios.finance_v1.generator import generate_training_data
        df2 = generate_training_data(seed=42)
        pd.testing.assert_frame_equal(self.df, df2)

    # ---- 落盘工具 ----
    def test_save_csv_and_source_name_map(self):
        import json
        import tempfile
        from pathlib import Path
        from forge.scenarios.finance_v1.generator import (
            FIN_SOURCE_NAME_ZH, save_csv, save_source_name_map)

        self.assertEqual(set(FIN_SOURCE_NAME_ZH), set(FIN_FIELDS))
        with tempfile.TemporaryDirectory() as tmp:
            p_en = save_csv(self.df.head(8), Path(tmp) / "en.csv")
            p_zh = save_csv(self.df.head(8), Path(tmp) / "zh.csv",
                            use_source_names=True)
            p_map = save_source_name_map(Path(tmp) / "map.json")
            self.assertEqual(list(pd.read_csv(p_en).columns), FIN_FIELDS)
            self.assertEqual(list(pd.read_csv(p_zh).columns),
                             [FIN_SOURCE_NAME_ZH[c] for c in FIN_FIELDS])
            loaded = json.loads(Path(p_map).read_text(encoding="utf-8"))
            self.assertEqual(loaded, FIN_SOURCE_NAME_ZH)


if __name__ == "__main__":
    unittest.main()
