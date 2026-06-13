# -*- coding: utf-8 -*-
"""finance_v1.generator — 确定性合成财务训练数据（960 行）.

设计要点：
- 3 行业（consulting/retail/manufacturing）× 各 40 家公司 × 8 期 = 960 行；
- 全部金额为千元整数（contracts.FIN_AMOUNT_UNIT）；
- 恒等式正向推导，保证 R01–R05 与跨期滚动在生成端 100% 成立：
    COGS          = round(Revenue * (1 - 毛利率))
    Purchases     = COGS + (目标期末存货 - 期初存货)
    Inventory_End = Inventory_Begin + Purchases - COGS
    GrossProfit   = Revenue - COGS
    TotalAssets   = Cash_End + Inventory_End + AccountsReceivable + OtherAssets
    TotalLiabilities = TotalAssets - TotalEquity
    下期 Inventory_Begin = 本期 Inventory_End；下期 Cash_Begin = 本期 Cash_End
- 行业差异化参数（存货占比 / 毛利率 / 应收营收比）取在验收区间的"安全内圈"，
  叠加小幅抖动与整数化后仍严格落在验收区间内；
- 同一 seed 两次生成逐位相同（numpy default_rng + 固定遍历顺序）。

派生字段（把多元恒等式折叠成二元规则，供 NetNomos 语法搜索）：
    InventoryNetInflow   = Purchases - COGS（== Inventory_End - Inventory_Begin）
    InventoryToAssetsBp  = round(Inventory_End / TotalAssets * 10000)   万分比取整
    ReceivableToRevenueBp= round(AccountsReceivable / Revenue * 10000)  万分比取整
"""
from __future__ import annotations

from pathlib import Path

from forge.contracts import (
    FIN_COMPANIES_PER_INDUSTRY,
    FIN_FIELDS,
    FIN_INDUSTRIES,
    FIN_PERIODS,
)

# ---------------------------------------------------------------------------
# 行业参数
# ---------------------------------------------------------------------------

# 验收区间（spec 口径）：生成数据必须严格落在其中，validator R06 也用同一区间。
# InventoryToAssetsBp：万分比（bp）。consulting < 2% → (0, 200]。
SPEC_INV_BP_BAND: dict[str, tuple[int, int]] = {
    "consulting": (0, 200),
    "retail": (1500, 3000),
    "manufacturing": (800, 2000),
}
# 毛利率验收区间
SPEC_MARGIN_BAND: dict[str, tuple[float, float]] = {
    "consulting": (0.35, 0.55),
    "retail": (0.18, 0.30),
    "manufacturing": (0.22, 0.38),
}
# 应收 / 营收 验收区间
SPEC_AR_RATIO_BAND: dict[str, tuple[float, float]] = {
    "consulting": (0.15, 0.35),
    "retail": (0.02, 0.10),
    "manufacturing": (0.10, 0.25),
}

# 生成端"安全内圈"参数：base 区间 + 抖动幅度，叠加后仍在验收区间内。
_GEN_PARAMS: dict[str, dict] = {
    "consulting": dict(
        prefix="CONS",
        margin_base=(0.37, 0.53), margin_jit=0.008,
        inv_bp_base=(75.0, 165.0), inv_bp_jit=8.0,
        ar_base=(0.17, 0.33), ar_jit=0.01,
        rev_base=(8000, 60000),
    ),
    "retail": dict(
        prefix="RETL",
        margin_base=(0.195, 0.285), margin_jit=0.008,
        inv_bp_base=(1650.0, 2850.0), inv_bp_jit=40.0,
        ar_base=(0.03, 0.09), ar_jit=0.005,
        rev_base=(20000, 200000),
    ),
    "manufacturing": dict(
        prefix="MANU",
        margin_base=(0.235, 0.365), margin_jit=0.008,
        inv_bp_base=(950.0, 1850.0), inv_bp_jit=40.0,
        ar_base=(0.115, 0.235), ar_jit=0.01,
        rev_base=(15000, 150000),
    ),
}

# 英文规范名 -> 中文列名（与 dataset_spec.json 的 source_name 一一对应）
FIN_SOURCE_NAME_ZH: dict[str, str] = {
    "CompanyId": "公司编号",
    "Industry": "行业",
    "PeriodIndex": "期数",
    "Revenue": "营业收入",
    "COGS": "营业成本",
    "GrossProfit": "毛利润",
    "NetProfit": "净利润",
    "Purchases": "本期采购额",
    "Cash_Begin": "期初现金",
    "Cash_End": "期末现金",
    "Inventory_Begin": "期初存货",
    "Inventory_End": "期末存货",
    "AccountsReceivable": "应收账款",
    "OtherAssets": "其他资产",
    "TotalAssets": "资产总计",
    "TotalLiabilities": "负债总计",
    "TotalEquity": "所有者权益",
    "InventoryNetInflow": "存货净流入",
    "InventoryToAssetsBp": "存货资产占比万分比",
    "ReceivableToRevenueBp": "应收营收占比万分比",
}


def bp(numer: int | float, denom: int | float) -> int:
    """万分比取整（四舍五入）。生成器 / 注入器 / 校验器共用，保证口径一致。"""
    return int(round(numer / denom * 10000))


# ---------------------------------------------------------------------------
# 生成主流程
# ---------------------------------------------------------------------------

def generate_training_data(seed: int = 42):
    """确定性生成 960 行干净训练数据，返回 pandas.DataFrame（列序 = FIN_FIELDS）。"""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    for industry in FIN_INDUSTRIES:            # 固定遍历顺序保证可复现
        p = _GEN_PARAMS[industry]
        for ci in range(1, FIN_COMPANIES_PER_INDUSTRY + 1):
            company_id = f"{p['prefix']}{ci:03d}"

            # ---- 公司级常量（一次性抽取） ----
            margin0 = rng.uniform(*p["margin_base"])      # 基准毛利率
            inv_bp0 = rng.uniform(*p["inv_bp_base"])      # 基准存货占比（bp）
            ar0 = rng.uniform(*p["ar_base"])              # 基准应收/营收
            rev = float(rng.uniform(*p["rev_base"]))      # 首期营收规模
            asset_k = rng.uniform(0.95, 1.35)             # 总资产/营收 倍数
            eq_ratio = rng.uniform(0.36, 0.64)            # 权益占比
            growth = rng.uniform(0.00, 0.06)              # 初始增速（之后平滑演化）

            inv_begin: int | None = None                  # 首期期初存货，后面补
            cash_begin: int | None = None                 # 首期期初现金，后面补

            for t in range(1, FIN_PERIODS + 1):
                if t > 1:
                    # 增速平滑：60% 惯性 + 40% 新抽样，幅度 [-2%, +8%]
                    growth = 0.6 * growth + 0.4 * rng.uniform(-0.02, 0.08)
                    rev = rev * (1.0 + growth)
                revenue = int(round(rev))

                # 期内比率 = 公司基准 + 小幅抖动（仍在验收区间内圈）
                margin = margin0 + rng.uniform(-p["margin_jit"], p["margin_jit"])
                inv_bp_t = inv_bp0 + rng.uniform(-p["inv_bp_jit"], p["inv_bp_jit"])
                ar_ratio = ar0 + rng.uniform(-p["ar_jit"], p["ar_jit"])

                # ---- 利润表 ----
                cogs = int(round(revenue * (1.0 - margin)))
                gross_profit = revenue - cogs
                net_profit = int(round(gross_profit * rng.uniform(0.25, 0.55)))

                # ---- 资产负债表目标 ----
                total_assets = int(round(revenue * asset_k))
                inv_end_target = int(round(total_assets * inv_bp_t / 10000.0))
                accounts_receivable = int(round(revenue * ar_ratio))

                if inv_begin is None:
                    # 首期期初存货：略低于首期目标期末存货
                    inv_begin = int(round(inv_end_target * rng.uniform(0.85, 1.0)))

                # ---- 进销存正向推导（R01 精确成立） ----
                purchases = cogs + (inv_end_target - inv_begin)
                if purchases < 0:  # 理论上不可达（存货变动 << COGS），防御性兜底
                    raise ValueError(
                        f"{company_id} 第 {t} 期 Purchases<0，参数区间设置有误")
                inventory_end = inv_begin + purchases - cogs   # == inv_end_target

                # ---- 资产端配平：现金 + 其他资产 吸收余量 ----
                remaining = total_assets - inventory_end - accounts_receivable
                if remaining < 2:
                    raise ValueError(
                        f"{company_id} 第 {t} 期资产余量不足，参数区间设置有误")
                cash_end = int(round(remaining * rng.uniform(0.15, 0.45)))
                other_assets = remaining - cash_end            # 配平到 total_assets

                if cash_begin is None:
                    cash_begin = int(round(cash_end * rng.uniform(0.85, 1.05)))

                # ---- 负债与权益（R02 精确成立） ----
                total_equity = int(round(total_assets * eq_ratio))
                total_liabilities = total_assets - total_equity

                rows.append({
                    "CompanyId": company_id,
                    "Industry": industry,
                    "PeriodIndex": t,
                    "Revenue": revenue,
                    "COGS": cogs,
                    "GrossProfit": gross_profit,
                    "NetProfit": net_profit,
                    "Purchases": purchases,
                    "Cash_Begin": cash_begin,
                    "Cash_End": cash_end,
                    "Inventory_Begin": inv_begin,
                    "Inventory_End": inventory_end,
                    "AccountsReceivable": accounts_receivable,
                    "OtherAssets": other_assets,
                    "TotalAssets": total_assets,
                    "TotalLiabilities": total_liabilities,
                    "TotalEquity": total_equity,
                    "InventoryNetInflow": purchases - cogs,
                    "InventoryToAssetsBp": bp(inventory_end, total_assets),
                    "ReceivableToRevenueBp": bp(accounts_receivable, revenue),
                })

                # 跨期滚动（R03 / R04 精确成立）
                inv_begin = inventory_end
                cash_begin = cash_end

    df = pd.DataFrame(rows, columns=FIN_FIELDS)
    return df


# ---------------------------------------------------------------------------
# 落盘工具
# ---------------------------------------------------------------------------

def save_csv(df, path: str | Path, use_source_names: bool = False) -> str:
    """输出 CSV。默认英文列名；use_source_names=True 输出中文列名
    （与 dataset_spec.json 的 source_name 一致，供 NetNomos 中文表头摄入）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.rename(columns=FIN_SOURCE_NAME_ZH) if use_source_names else df
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def save_source_name_map(path: str | Path) -> str:
    """输出 英文列名 -> 中文列名 映射表 JSON（与 dataset_spec.json 一致）。"""
    import json

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(FIN_SOURCE_NAME_ZH, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)


if __name__ == "__main__":  # pragma: no cover - 手动冒烟
    d = generate_training_data()
    print(d.shape)
    print(d.head(3).to_string())
