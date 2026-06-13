# -*- coding: utf-8 -*-
"""forge.core.projector — Projector：数值投影与修正（B 轨核心）.

输入 contracts.ViolationReport + 待修 DataFrame，输出 (df_corrected, interventions)。
interventions 为中文干预日志（list[str]），逐条记录"哪一行哪个字段按哪条规则
从 X 修正为 Y"，供 B 轨报告的核查与干预日志直接展示。

财务修正策略（纯 Python，确定性；全部从 Violation.observed/expected 推导，
不 hardcode 任何公司具体数值）：

- R01 进销存勾稽：以 COGS 为修正对象（审计惯例，与 FinanceValidator 的
  expected 口径一致）：COGS := Inventory_Begin + Purchases - Inventory_End；
  连带修正 GrossProfit = Revenue - COGS、InventoryNetInflow = Purchases - COGS。
- R02 资产负债配平：以恒等式重算 TotalLiabilities := TotalAssets - TotalEquity。
- R03 存货跨期滚动：Inventory_Begin := 上期 Inventory_End（observed 携带上期值）。
- R04 现金跨期滚动：Cash_Begin := 上期 Cash_End。
- R05 毛利恒等式：GrossProfit := Revenue - COGS（R01 修正后顺序重算，避免二次错）。
- R06/R07（行业画像 / 比率背离，F3/F4 类）：属于"账面自洽但业务异常"，
  无唯一恒等式解，**只产生风险提示，不改数**。

宿主机增强路径（z3）：
- project_with_z3() 懒加载 z3-solver，对恒等式违规行求"最近可行解"
  （z3.Optimize 最小化改动量）。沙箱无 z3 时抛带中文指引的 RuntimeError；
  宿主机 `cd netnomos-forge && uv sync` 后即可用（z3-solver 经 netnomos 依赖带入）。
"""
from __future__ import annotations

import logging
from typing import Any

from forge.contracts import Violation, ViolationReport

log = logging.getLogger("forge.core.projector")

# 各规则的"修正对象"主字段（与 FinanceValidator 的 expected 口径一致）
PRIMARY_FIELD: dict[str, str] = {
    "R01": "COGS",
    "R02": "TotalLiabilities",
    "R03": "Inventory_Begin",
    "R04": "Cash_Begin",
    "R05": "GrossProfit",
    "R06": "Inventory_End",          # 仅提示，不修
    "R07": "AccountsReceivable",     # 仅提示，不修
}

# 修正顺序：先勾稽（R01）再毛利（R05），后配平（R02），最后跨期（R03/R04）；
# R06/R07 永远只出提示。
_RULE_ORDER = ["R01", "R05", "R02", "R03", "R04", "R06", "R07"]

_Z3_HINT = (
    "无法导入 z3（z3-solver）。当前环境（如沙箱）无外网 pip，请在宿主机操作：\n"
    "  1. cd <workspace>/netnomos-forge && uv sync（z3-solver 随 netnomos 依赖安装）；\n"
    "  2. 以 `uv run python ...` 调用 Projector.project_with_z3()；\n"
    "  3. 沙箱/演示环境请改用纯 Python 的 Projector.project()（结果确定性等价）。"
)


def _fmt(v: Any) -> str:
    return f"{int(v):,}"


def _order_key(v: Violation) -> tuple[int, int]:
    try:
        ridx = _RULE_ORDER.index(v.rule_id)
    except ValueError:
        ridx = len(_RULE_ORDER)
    return (ridx, v.row_index)


class Projector:
    """数值投影器：把违规数据投影回规则可行域（最小改动、确定性）."""

    # ------------------------------------------------------------------ 纯 Python
    def project(self, report: ViolationReport, df) -> tuple[Any, list[str]]:
        """按违规清单修正 DataFrame，返回 (df_corrected, 中文干预日志).

        df 不会被原地修改；行号以 report 中的 row_index（0 基）为准，
        要求 df 与 validate 时同序（FinanceValidator 内部 reset_index 后 0 基）。
        """
        out = df.copy().reset_index(drop=True)
        interventions: list[str] = []

        for v in sorted(report.violations, key=_order_key):
            handler = getattr(self, f"_fix_{v.rule_id.lower()}", None)
            if handler is not None:
                handler(out, v, interventions)
            else:
                interventions.append(
                    f"【未处理】规则 {v.rule_id} 暂无修正策略：{v.message_zh}")
        if not interventions:
            interventions.append("未发现违规，无需数值修正。")
        return out, interventions

    # -- R01：COGS = Inventory_Begin + Purchases - Inventory_End ----------------
    def _fix_r01(self, df, v: Violation, logbook: list[str]) -> None:
        r = v.row_index
        ib = int(v.observed["Inventory_Begin"])
        pu = int(v.observed["Purchases"])
        ie = int(v.observed["Inventory_End"])
        cogs_old = int(v.observed["COGS"])
        cogs_new = ib + pu - ie
        if cogs_old != cogs_new:
            df.at[r, "COGS"] = cogs_new
            logbook.append(
                f"[R01] 第 {r + 1} 行 营业成本 由 {_fmt(cogs_old)} 修正为 "
                f"{_fmt(cogs_new)}（= 期初存货 {_fmt(ib)} + 采购 {_fmt(pu)} "
                f"- 期末存货 {_fmt(ie)}）。")
        # 连带修正毛利与存货净流入（用修正后的 COGS 重算）
        rev = int(df.at[r, "Revenue"])
        gp_new = rev - cogs_new
        gp_old = int(df.at[r, "GrossProfit"])
        if gp_old != gp_new:
            df.at[r, "GrossProfit"] = gp_new
            logbook.append(
                f"[R01→R05] 第 {r + 1} 行 毛利润 连带修正 {_fmt(gp_old)} → "
                f"{_fmt(gp_new)}（= 营业收入 {_fmt(rev)} - 修正后营业成本 "
                f"{_fmt(cogs_new)}）。")
        if "InventoryNetInflow" in df.columns:
            inflow_new = pu - cogs_new
            if int(df.at[r, "InventoryNetInflow"]) != inflow_new:
                df.at[r, "InventoryNetInflow"] = inflow_new
                logbook.append(
                    f"[R01] 第 {r + 1} 行 存货净流入 连带重算为 {_fmt(inflow_new)}。")

    # -- R02：TotalLiabilities = TotalAssets - TotalEquity ----------------------
    def _fix_r02(self, df, v: Violation, logbook: list[str]) -> None:
        r = v.row_index
        ta = int(df.at[r, "TotalAssets"])
        te = int(df.at[r, "TotalEquity"])
        tl_old = int(df.at[r, "TotalLiabilities"])
        tl_new = ta - te
        if tl_old != tl_new:
            df.at[r, "TotalLiabilities"] = tl_new
            logbook.append(
                f"[R02] 第 {r + 1} 行 负债总计 按配平恒等式重算 {_fmt(tl_old)} → "
                f"{_fmt(tl_new)}（= 资产总计 {_fmt(ta)} - 所有者权益 {_fmt(te)}）；"
                f"提示：差额 {ta - te - tl_old:+,} 与期末现金虚增记账痕迹一致，"
                f"建议追查原始凭证。")

    # -- R03：Inventory_Begin = 上期 Inventory_End ------------------------------
    def _fix_r03(self, df, v: Violation, logbook: list[str]) -> None:
        r = v.row_index
        prev = int(v.observed["上期Inventory_End"])
        old = int(df.at[r, "Inventory_Begin"])
        if old != prev:
            df.at[r, "Inventory_Begin"] = prev
            logbook.append(
                f"[R03] 第 {r + 1} 行 期初存货 由 {_fmt(old)} 修正为 "
                f"{_fmt(prev)}（以上期期末存货为准，跨期滚动）。")

    # -- R04：Cash_Begin = 上期 Cash_End ----------------------------------------
    def _fix_r04(self, df, v: Violation, logbook: list[str]) -> None:
        r = v.row_index
        prev = int(v.observed["上期Cash_End"])
        old = int(df.at[r, "Cash_Begin"])
        if old != prev:
            df.at[r, "Cash_Begin"] = prev
            logbook.append(
                f"[R04] 第 {r + 1} 行 期初现金 由 {_fmt(old)} 修正为 "
                f"{_fmt(prev)}（以上期期末现金为准，跨期滚动）。")

    # -- R05：GrossProfit = Revenue - COGS（按当前 df 重算，R01 之后执行） -------
    def _fix_r05(self, df, v: Violation, logbook: list[str]) -> None:
        r = v.row_index
        rev = int(df.at[r, "Revenue"])
        cogs = int(df.at[r, "COGS"])
        gp_old = int(df.at[r, "GrossProfit"])
        gp_new = rev - cogs
        if gp_old != gp_new:
            df.at[r, "GrossProfit"] = gp_new
            logbook.append(
                f"[R05] 第 {r + 1} 行 毛利润 由 {_fmt(gp_old)} 修正为 "
                f"{_fmt(gp_new)}（= 营业收入 - 营业成本）。")

    # -- R06/R07：比率背离 / 行业画像 → 只提示不改数 ----------------------------
    def _fix_r06(self, df, v: Violation, logbook: list[str]) -> None:
        logbook.append(f"【风险提示·R06】{v.message_zh}（行业画像背离属业务异常，"
                       f"无唯一恒等式解，不做数值修正，仅出具风险提示。）")

    def _fix_r07(self, df, v: Violation, logbook: list[str]) -> None:
        logbook.append(f"【风险提示·R07】{v.message_zh}（比率背离不改数，"
                       f"建议函证应收账款并核查收入确认。）")

    # ------------------------------------------------------------------ z3 增强
    def project_with_z3(self, report: ViolationReport, df) -> tuple[Any, list[str]]:
        """宿主机增强：对恒等式违规行用 z3.Optimize 求最近可行解.

        与 project() 的差异：不指定"修正对象"，而是把违规行涉及字段全部设为
        整数变量，约束恒等式成立，最小化 Σ|新值-账面值|——当账面错在 COGS 之外
        的字段时也能找到最小改动解。R06/R07 类画像/比率规则同样只提示不改数。

        沙箱（无 z3-solver）调用本方法会抛 RuntimeError 中文指引；
        请改用纯 Python 的 project()（演示场景两者结果一致）。
        """
        try:
            import z3  # noqa: PLC0415
        except Exception as exc:
            raise RuntimeError(_Z3_HINT) from exc

        out = df.copy().reset_index(drop=True)
        interventions: list[str] = []

        # 恒等式定义：rule_id -> (等式左字段, 右侧线性组合 [(系数, 字段)])
        identities: dict[str, tuple[str, list[tuple[int, str]]]] = {
            "R01": ("Inventory_End", [(1, "Inventory_Begin"), (1, "Purchases"),
                                      (-1, "COGS")]),
            "R02": ("TotalAssets", [(1, "TotalLiabilities"), (1, "TotalEquity")]),
            "R05": ("GrossProfit", [(1, "Revenue"), (-1, "COGS")]),
        }

        for v in sorted(report.violations, key=_order_key):
            ident = identities.get(v.rule_id)
            if ident is None:
                # 跨期/画像规则沿用纯 Python 策略
                handler = getattr(self, f"_fix_{v.rule_id.lower()}", None)
                if handler is not None:
                    handler(out, v, interventions)
                continue
            r = v.row_index
            lhs_field, terms = ident
            fields = [lhs_field] + [f for _, f in terms]
            opt = z3.Optimize()
            zvars = {f: z3.Int(f) for f in fields}
            devs = []
            for f in fields:
                book = int(out.at[r, f])
                d = z3.Int(f"dev_{f}")
                opt.add(d >= zvars[f] - book, d >= book - zvars[f])
                devs.append(d)
            opt.add(zvars[lhs_field] ==
                    z3.Sum([c * zvars[f] for c, f in terms]))
            opt.minimize(z3.Sum(devs))
            if opt.check() != z3.sat:  # 理论上线性恒等式必有解
                interventions.append(
                    f"【z3】第 {r + 1} 行规则 {v.rule_id} 求解失败，保留账面值。")
                continue
            model = opt.model()
            for f in fields:
                new = model[zvars[f]].as_long()
                old = int(out.at[r, f])
                if new != old:
                    out.at[r, f] = new
                    interventions.append(
                        f"[z3·{v.rule_id}] 第 {r + 1} 行 {f} 由 {_fmt(old)} "
                        f"修正为 {_fmt(new)}（最近可行解，最小化改动量）。")
        if not interventions:
            interventions.append("未发现违规，无需数值修正。")
        return out, interventions
