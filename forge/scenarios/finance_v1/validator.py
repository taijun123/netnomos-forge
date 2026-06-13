# -*- coding: utf-8 -*-
"""finance_v1.validator — FinanceValidator：纯 Python（pandas）财务规则校验器.

无 z3 环境下的演示/测试主力；宿主机上 NetNomos validate 跑通后两者互为印证。

规则清单：
- R01 进销存勾稽：Inventory_End = Inventory_Begin + Purchases - COGS
- R02 资产负债配平：TotalAssets = TotalLiabilities + TotalEquity
- R03 存货跨期滚动：下期 Inventory_Begin = 本期 Inventory_End
- R04 现金跨期滚动：下期 Cash_Begin = 本期 Cash_End
- R05 毛利恒等式：GrossProfit = Revenue - COGS
- R06 行业存货区间：Inventory_End / TotalAssets（万分比）落在行业常态区间
- R07 应收/营收背离：同比（t vs t-4）应收增速与营收增速差 ≥ 100pct 且应收翻倍

设计决策：
- R01 违规的 expected 以 COGS 为修正对象（审计惯例）：给出
  "应为 2,000（=10,000+4,000-12,000）" 式可读修正；
- R06 用原始字段重算占比（不信任 Bp 派生列），口径与 generator.bp 一致；
- R03/R04 仅在同公司、期数连续（PeriodIndex 恰 +1）时检查；
- satisfaction_rate = 1 - 违规行数(去重) / 总行数，零违规即 1.0。
"""
from __future__ import annotations

from pathlib import Path

from forge.contracts import FIN_FIELDS, Violation, ViolationReport
from forge.scenarios.finance_v1.generator import SPEC_INV_BP_BAND, bp

# R07 触发阈值：应收同比增速 ≥ +100%，且超出营收同比增速 ≥ 100 个百分点。
AR_DIVERGENCE_MIN_GROWTH = 1.0
AR_DIVERGENCE_GAP = 1.0

RULE_TEXTS = {
    "R01": "Inventory_End = Inventory_Begin + Purchases - COGS（进销存勾稽）",
    "R02": "TotalAssets = TotalLiabilities + TotalEquity（资产负债配平）",
    "R03": "下期 Inventory_Begin = 本期 Inventory_End（存货跨期滚动）",
    "R04": "下期 Cash_Begin = 本期 Cash_End（现金跨期滚动）",
    "R05": "GrossProfit = Revenue - COGS（毛利恒等式）",
    "R06": "Inventory_End / TotalAssets 落在行业常态区间（行业画像）",
    "R07": "应收账款同比增速不应大幅背离营业收入增速（比率背离）",
}


def _fmt(v) -> str:
    return f"{int(v):,}"


class FinanceValidator:
    """财务规则校验器：validate(DataFrame 或 csv 路径) -> contracts.ViolationReport"""

    def validate(self, data, data_path: str | None = None) -> ViolationReport:
        import pandas as pd

        if isinstance(data, (str, Path)):
            data_path = data_path or str(data)
            df = pd.read_csv(data)
        else:
            df = data
            data_path = data_path or "<DataFrame>"

        missing = [c for c in FIN_FIELDS if c not in df.columns]
        if missing:
            raise ValueError(f"缺少字段: {missing}")

        # reset 后 RangeIndex 即 0 基行号（报告展示时 +1），itertuples 经 rec.Index 取
        df = df.copy().reset_index(drop=True)

        violations: list[Violation] = []
        for v in self._check_row_rules(df):
            violations.append(v)
        for v in self._check_cross_period(df):
            violations.append(v)
        for v in self._check_divergence(df):
            violations.append(v)

        violations.sort(key=lambda v: (v.row_index, v.rule_id))
        by_rule: dict[str, int] = {}
        for v in violations:
            by_rule[v.rule_id] = by_rule.get(v.rule_id, 0) + 1
        bad_rows = len({v.row_index for v in violations})
        total = len(df)
        return ViolationReport(
            scenario="finance_v1",
            data_path=data_path,
            total_rows=total,
            violations=violations,
            satisfaction_rate=1.0 if total == 0 else 1.0 - bad_rows / total,
            by_rule=by_rule,
        )

    # ------------------------------------------------------------------ 行内规则
    def _check_row_rules(self, df):
        for rec in df.itertuples():
            row = int(rec.Index)
            cid, period = str(rec.CompanyId), int(rec.PeriodIndex)
            ib, pu, ie, cogs = (int(rec.Inventory_Begin), int(rec.Purchases),
                                int(rec.Inventory_End), int(rec.COGS))
            rev, gp = int(rec.Revenue), int(rec.GrossProfit)
            ta, tl, te = (int(rec.TotalAssets), int(rec.TotalLiabilities),
                          int(rec.TotalEquity))

            # R01：以 COGS 为修正对象给出可读 expected
            cogs_should = ib + pu - ie
            if ie != ib + pu - cogs:
                yield Violation(
                    row_index=row, rule_id="R01", rule_text=RULE_TEXTS["R01"],
                    fields=["Inventory_Begin", "Purchases", "Inventory_End", "COGS"],
                    observed={"Inventory_Begin": ib, "Purchases": pu,
                              "Inventory_End": ie, "COGS": cogs},
                    expected=(f"应为 {_fmt(cogs_should)}"
                              f"（={_fmt(ib)}+{_fmt(pu)}-{_fmt(ie)}）"),
                    message_zh=(f"{cid} 第 {period} 期进销存勾稽不平："
                                f"按 期初存货+采购-期末存货，营业成本应为 "
                                f"{_fmt(cogs_should)}，实际记账 {_fmt(cogs)}。"),
                )

            # R02
            if ta != tl + te:
                diff = ta - (tl + te)
                yield Violation(
                    row_index=row, rule_id="R02", rule_text=RULE_TEXTS["R02"],
                    fields=["TotalAssets", "TotalLiabilities", "TotalEquity"],
                    observed={"TotalAssets": ta, "TotalLiabilities": tl,
                              "TotalEquity": te},
                    expected=(f"资产总计应为 {_fmt(tl + te)}"
                              f"（=负债 {_fmt(tl)}+权益 {_fmt(te)}）"),
                    message_zh=(f"{cid} 第 {period} 期资产负债表不配平：资产总计 "
                                f"{_fmt(ta)} 与 负债+权益 {_fmt(tl + te)} 相差 "
                                f"{diff:+,}。"),
                )

            # R05
            if gp != rev - cogs:
                yield Violation(
                    row_index=row, rule_id="R05", rule_text=RULE_TEXTS["R05"],
                    fields=["Revenue", "COGS", "GrossProfit"],
                    observed={"Revenue": rev, "COGS": cogs, "GrossProfit": gp},
                    expected=(f"毛利润应为 {_fmt(rev - cogs)}"
                              f"（={_fmt(rev)}-{_fmt(cogs)}）"),
                    message_zh=(f"{cid} 第 {period} 期毛利恒等式不成立：营业收入-"
                                f"营业成本={_fmt(rev - cogs)}，账面毛利 {_fmt(gp)}。"),
                )

            # R06：行业存货区间（用原始字段重算，口径同 generator.bp）
            band = SPEC_INV_BP_BAND.get(str(rec.Industry))
            if band and ta > 0:
                ratio_bp = bp(ie, ta)
                lo, hi = band
                if not (lo <= ratio_bp <= hi):
                    yield Violation(
                        row_index=row, rule_id="R06", rule_text=RULE_TEXTS["R06"],
                        fields=["Inventory_End", "TotalAssets", "Industry"],
                        observed={"Inventory_End": ie, "TotalAssets": ta,
                                  "InventoryToAssetsBp": ratio_bp,
                                  "Industry": str(rec.Industry)},
                        expected=(f"{rec.Industry} 行业存货占总资产应在 "
                                  f"{lo / 100:.2f}%–{hi / 100:.2f}% 区间"),
                        message_zh=(f"{cid} 第 {period} 期存货占总资产 "
                                    f"{ratio_bp / 100:.2f}%，偏离 {rec.Industry} "
                                    f"行业常态区间 {lo / 100:.2f}%–{hi / 100:.2f}%。"),
                    )

    # ------------------------------------------------------------ 跨期滚动规则
    def _check_cross_period(self, df):
        for _, g in df.groupby("CompanyId", sort=False):
            g = g.sort_values("PeriodIndex")
            prev = None
            for rec in g.itertuples():
                if prev is not None and int(rec.PeriodIndex) == int(prev.PeriodIndex) + 1:
                    cid, period = str(rec.CompanyId), int(rec.PeriodIndex)
                    # R03
                    if int(rec.Inventory_Begin) != int(prev.Inventory_End):
                        yield Violation(
                            row_index=int(rec.Index),
                            rule_id="R03", rule_text=RULE_TEXTS["R03"],
                            fields=["Inventory_Begin"],
                            observed={"Inventory_Begin": int(rec.Inventory_Begin),
                                      "上期Inventory_End": int(prev.Inventory_End)},
                            expected=(f"期初存货应为 {_fmt(prev.Inventory_End)}"
                                      f"（=上期期末存货）"),
                            message_zh=(f"{cid} 第 {period} 期期初存货 "
                                        f"{_fmt(rec.Inventory_Begin)} 与上期期末存货 "
                                        f"{_fmt(prev.Inventory_End)} 不衔接。"),
                        )
                    # R04
                    if int(rec.Cash_Begin) != int(prev.Cash_End):
                        yield Violation(
                            row_index=int(rec.Index),
                            rule_id="R04", rule_text=RULE_TEXTS["R04"],
                            fields=["Cash_Begin"],
                            observed={"Cash_Begin": int(rec.Cash_Begin),
                                      "上期Cash_End": int(prev.Cash_End)},
                            expected=(f"期初现金应为 {_fmt(prev.Cash_End)}"
                                      f"（=上期期末现金）"),
                            message_zh=(f"{cid} 第 {period} 期期初现金 "
                                        f"{_fmt(rec.Cash_Begin)} 与上期期末现金 "
                                        f"{_fmt(prev.Cash_End)} 断裂。"),
                        )
                prev = rec

    # -------------------------------------------------------- 比率背离（R07）
    def _check_divergence(self, df):
        for _, g in df.groupby("CompanyId", sort=False):
            g = g.sort_values("PeriodIndex")
            by_period = {int(r.PeriodIndex): r for r in g.itertuples()}
            for period, rec in by_period.items():
                base = by_period.get(period - 4)        # 同比基期（季度口径 t-4）
                if base is None:
                    continue
                ar0, rev0 = int(base.AccountsReceivable), int(base.Revenue)
                ar1, rev1 = int(rec.AccountsReceivable), int(rec.Revenue)
                if ar0 <= 0 or rev0 <= 0:
                    continue
                g_ar = ar1 / ar0 - 1.0
                g_rev = rev1 / rev0 - 1.0
                if g_ar >= AR_DIVERGENCE_MIN_GROWTH and \
                        g_ar - g_rev >= AR_DIVERGENCE_GAP:
                    cid = str(rec.CompanyId)
                    yield Violation(
                        row_index=int(rec.Index),
                        rule_id="R07", rule_text=RULE_TEXTS["R07"],
                        fields=["AccountsReceivable", "Revenue"],
                        observed={"AccountsReceivable": ar1, "Revenue": rev1,
                                  "应收同比增速": f"{g_ar * 100:+.0f}%",
                                  "营收同比增速": f"{g_rev * 100:+.0f}%"},
                        expected=(f"应收增速应与营收增速（{g_rev * 100:+.0f}%）"
                                  f"基本匹配（背离 < 100pct）"),
                        message_zh=(f"{cid} 第 {period} 期应收账款同比 "
                                    f"{g_ar * 100:+.0f}%，营业收入同比仅 "
                                    f"{g_rev * 100:+.0f}%，存在收入质量/虚增应收风险。"),
                    )


if __name__ == "__main__":  # pragma: no cover - 手动冒烟
    from forge.scenarios.finance_v1.faults import inject_faults

    rep = FinanceValidator().validate(inject_faults()[0])
    for v in rep.violations:
        print(v.rule_id, v.row_index, v.message_zh)
