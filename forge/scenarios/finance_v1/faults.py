# -*- coding: utf-8 -*-
"""finance_v1.faults — "华信咨询"待审资料包：确定性错误注入.

注入策略（与 contracts.FIN_FAULTS 对齐，且保证"单点违规、零级联误报"）：

- F1  进销存破坏（命中 R01，第 3 期）：
      清洁基线第 3 期内置 Inventory_Begin=10000、Purchases=4000、Inventory_End=12000、
      COGS=2000（规格指定的库存三元组放在干净数据里，保证 R03 跨期滚动不被连带破坏）。
      注入时把 COGS 篡改为 3000（按勾稽应为 2000 = 10000+4000-12000），并连带
      GrossProfit、InventoryNetInflow 用错误 COGS 算错——错误自洽传播，因此 R05
      不会误报，只有 R01 能抓住它。
- F2a 跨期现金断裂（命中 R04，第 2 期）：
      第 1 期 Cash_End=8000，把第 2 期 Cash_Begin 篡改为 8500。
- F2b 同期资产负债不配平（命中 R02，第 5 期）：
      现金虚增叙事：Cash_End 与 TotalAssets 同步虚增 500，使 TotalAssets 比
      TotalLiabilities+TotalEquity 多 500；第 6 期 Cash_Begin 同步虚增（造假者会让
      跨期滚动看起来正常），因此 R04 不级联误报。
- F4  应收异常增长（命中 R07，第 7 期）：
      AccountsReceivable 改为第 3 期的 4 倍（同比 +300%），而 Revenue 同比 +15%；
      虚增部分从 OtherAssets 划出（资产重分类叙事），资产合计仍配平。
- F3  行业异常（命中 R06，第 8 期）：
      consulting 公司期末存货拉到 TotalAssets 的 35%；Purchases 同步做平使 R01
      仍成立（账面自洽的存货造假），虚增部分同样从 OtherAssets 划出；选最后一期
      避免下一期 Inventory_Begin 级联破坏 R03。

输出真值表 truth_table（自动验收依据）：每个 fault 给出命中规则 id、主行号、
全部被篡改单元格（行号/字段/错误值/正确值）与中文说明。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge.contracts import FIN_FIELDS, FIN_FAULTS
from forge.scenarios.finance_v1.generator import bp

COMPANY_ID = "HX001"
COMPANY_NAME_ZH = "华信咨询"
INDUSTRY = "consulting"


# ---------------------------------------------------------------------------
# 清洁基线：华信咨询 8 期（全部硬编码主科目，派生/配平科目代码推导，确保恒等式精确）
# ---------------------------------------------------------------------------

def build_clean_package():
    """构造华信咨询 8 期干净数据（FinanceValidator 校验零违规）。"""
    import pandas as pd

    revenue = [80000, 82000, 84000, 86000, 88000, 90000, 96600, 98000]
    cogs = [2000, 2200, 2000, 2400, 2500, 2600, 2800, 3000]
    net_profit = [23400, 24000, 24600, 25100, 25700, 26200, 28100, 28500]
    cash_end = [8000, 8600, 9200, 9800, 10400, 11000, 11600, 12200]
    cash_begin_1 = 7500
    inv_end = [9500, 10000, 12000, 11500, 11800, 12000, 12200, 12400]
    inv_begin_1 = 9000
    ar = [20000, 20500, 21000, 21500, 22000, 22500, 24150, 24500]
    total_assets = [800000, 808000, 816000, 824000, 832000, 840000, 848000, 856000]
    total_equity = [440000, 444400, 448800, 453200, 457600, 462000, 466400, 470800]

    rows = []
    for i in range(8):
        ib = inv_begin_1 if i == 0 else inv_end[i - 1]          # R03
        cb = cash_begin_1 if i == 0 else cash_end[i - 1]        # R04
        purchases = cogs[i] + (inv_end[i] - ib)                 # R01 正推
        other = total_assets[i] - cash_end[i] - inv_end[i] - ar[i]  # 资产配平
        assert other > 0
        rows.append({
            "CompanyId": COMPANY_ID,
            "Industry": INDUSTRY,
            "PeriodIndex": i + 1,
            "Revenue": revenue[i],
            "COGS": cogs[i],
            "GrossProfit": revenue[i] - cogs[i],                # R05
            "NetProfit": net_profit[i],
            "Purchases": purchases,
            "Cash_Begin": cb,
            "Cash_End": cash_end[i],
            "Inventory_Begin": ib,
            "Inventory_End": inv_end[i],
            "AccountsReceivable": ar[i],
            "OtherAssets": other,
            "TotalAssets": total_assets[i],
            "TotalLiabilities": total_assets[i] - total_equity[i],  # R02
            "TotalEquity": total_equity[i],
            "InventoryNetInflow": purchases - cogs[i],
            "InventoryToAssetsBp": bp(inv_end[i], total_assets[i]),
            "ReceivableToRevenueBp": bp(ar[i], revenue[i]),
        })
    return pd.DataFrame(rows, columns=FIN_FIELDS)


# ---------------------------------------------------------------------------
# 错误注入
# ---------------------------------------------------------------------------

def inject_faults(df_clean=None):
    """注入 F1/F2a/F2b/F3/F4，返回 (df_faulty, truth_table).

    df_clean 缺省时使用 build_clean_package()；若传入，必须是"单公司 × 8 期、
    PeriodIndex 升序、恒等式干净"的 DataFrame（结构同 build_clean_package）。
    truth_table 的 cells 即 df_faulty 与 df_clean 的全部差异单元格。
    """
    if df_clean is None:
        df_clean = build_clean_package()
    df0 = df_clean.sort_values("PeriodIndex").reset_index(drop=True)
    if len(df0) != 8 or df0["CompanyId"].nunique() != 1:
        raise ValueError("inject_faults 需要单公司 × 8 期的干净 DataFrame")
    df = df0.copy()

    def row_of(period: int) -> int:
        """PeriodIndex -> 0 基行号（df 已按期排序重置索引）。"""
        return int(df.index[df["PeriodIndex"] == period][0])

    truth: dict[str, Any] = {
        "scenario": "finance_v1",
        "company_id": str(df0.at[0, "CompanyId"]),
        "company_name_zh": COMPANY_NAME_ZH,
        "amount_unit": "千元",
        "faults": {},
    }

    def _set(cells: list, r: int, field: str, wrong) -> None:
        """写入错误值并登记真值表单元格（错误值 == 正确值时跳过登记）。"""
        correct = df0.at[r, field]
        wrong = int(wrong)
        if wrong == int(correct):
            return
        df.at[r, field] = wrong
        cells.append({
            "row_index": r,
            "period_index": int(df0.at[r, "PeriodIndex"]),
            "field": field,
            "wrong_value": wrong,
            "correct_value": int(correct),
        })

    # ---- F1 进销存破坏（第 3 期，R01） ----
    r = row_of(3)
    ib, pu, ie = (int(df0.at[r, c]) for c in
                  ("Inventory_Begin", "Purchases", "Inventory_End"))
    cogs_correct = ib + pu - ie                       # = 2000
    cogs_wrong = cogs_correct + 1000                  # = 3000
    cells: list = []
    _set(cells, r, "COGS", cogs_wrong)
    _set(cells, r, "GrossProfit", int(df0.at[r, "Revenue"]) - cogs_wrong)
    _set(cells, r, "InventoryNetInflow", pu - cogs_wrong)
    truth["faults"]["F1"] = {
        "rule_id": "R01",
        "row_index": r,
        "period_index": 3,
        "cells": cells,
        "message_zh": (
            f"进销存勾稽破坏：期初存货 {ib:,} + 本期采购 {pu:,} - 期末存货 {ie:,} "
            f"= {cogs_correct:,}，但营业成本误记为 {cogs_wrong:,}，"
            f"毛利润与存货净流入连带算错（错误自洽传播，仅 R01 可识别）。"),
    }

    # ---- F2a 跨期现金断裂（第 2 期，R04） ----
    r = row_of(2)
    prev_ce = int(df0.at[row_of(1), "Cash_End"])      # = 8000
    cells = []
    _set(cells, r, "Cash_Begin", prev_ce + 500)       # = 8500
    truth["faults"]["F2a"] = {
        "rule_id": "R04",
        "row_index": r,
        "period_index": 2,
        "cells": cells,
        "message_zh": (
            f"跨期现金断裂：第 1 期期末现金 {prev_ce:,}，"
            f"第 2 期期初现金却记为 {prev_ce + 500:,}，凭空多出 500。"),
    }

    # ---- F2b 同期资产负债不配平（第 5 期，R02，现金虚增叙事） ----
    r = row_of(5)
    cells = []
    ce_new = int(df0.at[r, "Cash_End"]) + 500
    ta_new = int(df0.at[r, "TotalAssets"]) + 500
    _set(cells, r, "Cash_End", ce_new)
    _set(cells, r, "TotalAssets", ta_new)
    _set(cells, r, "InventoryToAssetsBp", bp(int(df.at[r, "Inventory_End"]), ta_new))
    r6 = row_of(6)
    _set(cells, r6, "Cash_Begin", ce_new)             # 造假者抹平跨期，防 R04 级联
    truth["faults"]["F2b"] = {
        "rule_id": "R02",
        "row_index": r,
        "period_index": 5,
        "cells": cells,
        "message_zh": (
            f"资产负债不配平：第 5 期期末现金与资产总计同步虚增 500，"
            f"资产总计 {ta_new:,} 比 负债+权益 {ta_new - 500:,} 多 500；"
            f"第 6 期期初现金被同步抹平以掩盖跨期断裂。"),
    }

    # ---- F4 应收异常增长（第 7 期，R07） ----
    r = row_of(7)
    ar_base = int(df0.at[row_of(3), "AccountsReceivable"])   # 同比基期（t-4）
    ar_new = ar_base * 4                                     # +300%
    ar_old = int(df0.at[r, "AccountsReceivable"])
    rev7, rev3 = int(df0.at[r, "Revenue"]), int(df0.at[row_of(3), "Revenue"])
    cells = []
    _set(cells, r, "AccountsReceivable", ar_new)
    _set(cells, r, "OtherAssets", int(df0.at[r, "OtherAssets"]) - (ar_new - ar_old))
    _set(cells, r, "ReceivableToRevenueBp", bp(ar_new, rev7))
    truth["faults"]["F4"] = {
        "rule_id": "R07",
        "row_index": r,
        "period_index": 7,
        "cells": cells,
        "message_zh": (
            f"应收异常增长：第 7 期应收账款 {ar_new:,}，较第 3 期 {ar_base:,} "
            f"同比 +300%，而营业收入仅 +{(rev7 / rev3 - 1) * 100:.0f}%；"
            f"虚增部分从其他资产划入，资产合计仍配平。"),
    }

    # ---- F3 行业异常（第 8 期，R06，存货占比 35%） ----
    r = row_of(8)
    ta = int(df0.at[r, "TotalAssets"])
    ie_new = int(round(ta * 0.35))
    ie_old = int(df0.at[r, "Inventory_End"])
    ib8 = int(df0.at[r, "Inventory_Begin"])
    cogs8 = int(df0.at[r, "COGS"])
    pu_new = ie_new - ib8 + cogs8                     # 做平 R01 的"自洽造假"
    cells = []
    _set(cells, r, "Inventory_End", ie_new)
    _set(cells, r, "Purchases", pu_new)
    _set(cells, r, "InventoryNetInflow", pu_new - cogs8)
    _set(cells, r, "InventoryToAssetsBp", bp(ie_new, ta))
    _set(cells, r, "OtherAssets", int(df0.at[r, "OtherAssets"]) - (ie_new - ie_old))
    truth["faults"]["F3"] = {
        "rule_id": "R06",
        "row_index": r,
        "period_index": 8,
        "cells": cells,
        "message_zh": (
            f"行业异常：consulting 公司第 8 期期末存货 {ie_new:,} 占资产总计 "
            f"{ta:,} 的 35%，远超咨询行业 <2% 的常态区间；采购额已被同步做平，"
            f"勾稽恒等式无法发现，只能靠行业画像规则识别。"),
    }

    assert set(truth["faults"]) == set(FIN_FAULTS)
    return df, truth


# ---------------------------------------------------------------------------
# 落盘：错误资料包 CSV + truth_table.json
# ---------------------------------------------------------------------------

def save_package(out_dir: str | Path, df_clean=None) -> dict[str, str]:
    """输出 华信咨询 审阅资料包：clean CSV、faulty CSV、truth_table.json。"""
    from forge.scenarios.finance_v1.generator import save_csv

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df_faulty, truth = inject_faults(df_clean)
    clean = df_clean if df_clean is not None else build_clean_package()

    paths = {
        "clean_csv": save_csv(clean, out / "huaxin_clean.csv"),
        "faulty_csv": save_csv(df_faulty, out / "huaxin_audit_package.csv"),
        "truth_table": str(out / "truth_table.json"),
    }
    (out / "truth_table.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


if __name__ == "__main__":  # pragma: no cover - 手动冒烟
    f, t = inject_faults()
    print(json.dumps(t, ensure_ascii=False, indent=2))
