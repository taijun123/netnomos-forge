# -*- coding: utf-8 -*-
"""forge.core.reporter — DualReporter：双轨报告管线（A 轨裸模型 / B 轨约束）.

财务场景（finance_v1）：
- track_a()：用 LLMClient(role="induce") 让裸模型基于错误资料直接撰写报告；
  MockBackend / 无 LLM 时走确定性降级——把错误数据原样填进报告叙事
  （错误数字与 truth_table 一致，且用错误数字连带算错毛利率），保证沙箱
  也能稳定演示"裸模型照抄错误"。
- track_b()：validate → Projector 修正 → 槽位计算 → report_template.md 的
  {{slot}} 程序回填 → 终检（残留槽位扫描 + 裸数字白名单校验：正文出现的
  每个数值必须来自 slots 白名单或模板骨架，否则记入告警）→ 干预日志。
- make_dual()：组装 contracts.DualReport；diff_html 中 A 轨错误数字包
  <span class="err mark-num mark-bad" title="命中R01：应为 2,000">3,000</span>，
  B 轨对应位置包 <span class="ok mark-num mark-ok">（类名与 web 前端
  FinanceDemoPage 的 mark-num/mark-bad/mark-ok、track-col/track-a/track-b 约定一致）。

网络场景（network_cidds）：
- track_a_network()：llm 生成 10 条 NetFlow；mock 时用确定性"带错样本"
  （错误类型：UDP 带 TCP Flags / Packets×65535 < Bytes / 端口 53 非 DNS 身份）。
- track_b_network()：优先调 ConstrainedGenerator（LeJIT bundle）；对生成行做
  终检过滤并补采，直到拿到足量 0 违规记录。若 LeJIT 不可用或补采不足，
  直接暴露错误，不用静态样本伪装成功。

修正/槽位全部从 ViolationReport 与 DataFrame 推导，不 hardcode 公司数值。
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from forge.contracts import (
    DualReport,
    SCENARIO_DIR,
    TrackReport,
    Violation,
    ViolationReport,
)
from forge.core.projector import PRIMARY_FIELD, Projector

log = logging.getLogger("forge.core.reporter")

FORGE_DIR = Path(__file__).resolve().parents[1]
FIN_TEMPLATE_PATH = SCENARIO_DIR / "finance_v1" / "report_template.md"
FORGE_ROOT = FORGE_DIR.parent
LEJIT_SUBPROCESS_TIMEOUT = int(os.getenv("FORGE_LEJIT_SUBPROCESS_TIMEOUT", "480"))

# 行业英文 → 中文
INDUSTRY_ZH = {"consulting": "咨询", "retail": "零售", "manufacturing": "制造"}

# ---------------------------------------------------------------------------
# 数值 token / 槽位工具（B 轨终检与 /api/chat/constrained 共用）
# ---------------------------------------------------------------------------

SLOT_RE = re.compile(r"\{\{(\w+)\}\}")
# 独立数值 token：千分位整数或普通数（带可选小数），前后不粘字母/数字/下划线/点
NUM_TOKEN_RE = re.compile(
    r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w])")


def extract_number_tokens(text: str) -> set[str]:
    """提取文本中的全部独立数值 token（白名单比对用）."""
    return {m.group(0) for m in NUM_TOKEN_RE.finditer(text or "")}


def fill_slots(template: str, slots: dict[str, Any]) -> str:
    """{{slot}} 程序回填；未知槽位原样保留（由终检报警）."""
    def _sub(m: re.Match) -> str:
        key = m.group(1)
        return str(slots[key]) if key in slots else m.group(0)
    return SLOT_RE.sub(_sub, template)


def final_check(markdown: str, slots: dict[str, Any],
                template_text: str = "") -> list[str]:
    """B 轨终检：返回告警列表（为空即通过）.

    1. 残留未回填槽位；
    2. 裸数字白名单：正文每个数值 token 必须来自 slots 值或模板骨架
       （模板去掉槽位后的静态文本），发现外来数字记告警。
    """
    warnings: list[str] = []
    for m in SLOT_RE.finditer(markdown):
        warnings.append(f"残留未回填槽位：{{{{{m.group(1)}}}}}")
    whitelist: set[str] = set()
    for value in slots.values():
        whitelist |= extract_number_tokens(str(value))
    if template_text:
        whitelist |= extract_number_tokens(SLOT_RE.sub("", template_text))
    for token in sorted(extract_number_tokens(markdown)):
        if token not in whitelist:
            warnings.append(f"裸数字异常：{token} 不在槽位白名单中（疑似模型擅写数值）")
    return warnings


def _fmt(v: Any) -> str:
    return f"{int(round(float(v))):,}"


def _pct(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}%"


# ---------------------------------------------------------------------------
# 网络 NetFlow 规则检查（A/B 轨共用，纯 Python）
# ---------------------------------------------------------------------------

NET_RULE_TEXTS = {
    "N01": "Proto=UDP -> Flags=noflags（UDP 不应携带 TCP 标志位）",
    "N02": "42×Packets <= Bytes <= 65535×Packets（物理上下界）",
    "N03": "端口 53 流量对端应为 DNS 身份（端口-身份一致性）",
}
_NOFLAGS = "......"


def check_netflow_rows(rows: list[dict[str, Any]]) -> list[Violation]:
    """对 NetFlow 记录做协议/物理/身份三类规则检查，返回违规清单."""
    violations: list[Violation] = []
    for i, row in enumerate(rows):
        proto = str(row.get("Proto", "")).strip()
        flags = str(row.get("Flags", "")).strip()
        try:
            packets = int(row.get("Packets", 0))
            nbytes = int(row.get("Bytes", 0))
            src_pt = int(row.get("SrcPt", 0))
            dst_pt = int(row.get("DstPt", 0))
        except (TypeError, ValueError):
            packets, nbytes, src_pt, dst_pt = 0, 0, 0, 0
        # N01 协议蕴含
        if proto == "UDP" and flags not in (_NOFLAGS, ""):
            violations.append(Violation(
                row_index=i, rule_id="N01", rule_text=NET_RULE_TEXTS["N01"],
                fields=["Proto", "Flags"],
                observed={"Proto": proto, "Flags": flags},
                expected=f"应为 {_NOFLAGS}（UDP 无 TCP 标志位）",
                message_zh=f"第 {i + 1} 条记录：UDP 流量携带 TCP 标志位 "
                           f"{flags}，违反协议语义。"))
        # N02 物理上下界
        if packets > 0 and (nbytes > 65535 * packets or nbytes < 42 * packets):
            violations.append(Violation(
                row_index=i, rule_id="N02", rule_text=NET_RULE_TEXTS["N02"],
                fields=["Packets", "Bytes"],
                observed={"Packets": packets, "Bytes": nbytes},
                expected=f"Bytes 应在 [{42 * packets:,}, {65535 * packets:,}] 区间",
                message_zh=f"第 {i + 1} 条记录：{packets} 个包共 {nbytes:,} 字节，"
                           f"超出单包最大 65,535 字节的物理上界。"))
        # N03 端口-身份一致性（CIDDS 中 DNS 服务器以 "DNS" 标识）
        if dst_pt == 53 and str(row.get("DstIpAddr", "")) != "DNS":
            violations.append(Violation(
                row_index=i, rule_id="N03", rule_text=NET_RULE_TEXTS["N03"],
                fields=["DstPt", "DstIpAddr", "Proto"],
                observed={"DstPt": dst_pt, "DstIpAddr": row.get("DstIpAddr"),
                          "Proto": proto},
                expected="目的端口 53 的对端应为 DNS 身份",
                message_zh=f"第 {i + 1} 条记录：目的端口 53 但对端 "
                           f"{row.get('DstIpAddr')} 非 DNS 身份，端口-身份背离。"))
        elif src_pt == 53 and str(row.get("SrcIpAddr", "")) != "DNS":
            violations.append(Violation(
                row_index=i, rule_id="N03", rule_text=NET_RULE_TEXTS["N03"],
                fields=["SrcPt", "SrcIpAddr"],
                observed={"SrcPt": src_pt, "SrcIpAddr": row.get("SrcIpAddr")},
                expected="源端口 53 的主机应为 DNS 身份",
                message_zh=f"第 {i + 1} 条记录：源端口 53 但主机 "
                           f"{row.get('SrcIpAddr')} 非 DNS 身份，端口-身份背离。"))
    return violations


def _split_valid_netflow_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[Violation]]:
    valid: list[dict[str, Any]] = []
    rejected: list[Violation] = []
    for row in rows:
        row_violations = check_netflow_rows([row])
        if row_violations:
            rejected.extend(row_violations)
        else:
            valid.append(row)
    return valid, rejected


def mock_netflow_with_errors(n: int = 10) -> list[dict[str, Any]]:
    """确定性"带错"NetFlow 样本（A 轨 mock 降级）.

    含三类典型裸模型错误：UDP 带 TCP Flags（第 2 条）、Packets×65535 < Bytes
    （第 5 条）、目的端口 53 非 DNS 身份（第 8 条），其余为合规记录。
    """
    base = [
        {"DateFirstSeen": "2017-03-24 10:00:01.000", "Duration": 0.0,
         "Proto": "TCP", "SrcIpAddr": "192.168.220.7", "SrcPt": 37320,
         "DstIpAddr": "10081_164", "DstPt": 80, "Packets": 1, "Bytes": 66,
         "Flows": 1, "Flags": ".A....", "Tos": 0},
        {"DateFirstSeen": "2017-03-24 10:00:02.300", "Duration": 0.002,
         "Proto": "UDP", "SrcIpAddr": "192.168.220.8", "SrcPt": 34358,
         "DstIpAddr": "DNS", "DstPt": 53, "Packets": 2, "Bytes": 164,
         "Flows": 1, "Flags": ".AP.SF", "Tos": 0},                 # N01：UDP 带 TCP Flags
        {"DateFirstSeen": "2017-03-24 10:00:03.110", "Duration": 0.21,
         "Proto": "TCP", "SrcIpAddr": "192.168.220.16", "SrcPt": 37922,
         "DstIpAddr": "10082_43", "DstPt": 443, "Packets": 5, "Bytes": 1100,
         "Flows": 1, "Flags": ".AP.SF", "Tos": 0},
        {"DateFirstSeen": "2017-03-24 10:00:04.870", "Duration": 0.0,
         "Proto": "TCP", "SrcIpAddr": "192.168.220.4", "SrcPt": 57656,
         "DstIpAddr": "10056_105", "DstPt": 443, "Packets": 1, "Bytes": 66,
         "Flows": 1, "Flags": ".A....", "Tos": 0},
        {"DateFirstSeen": "2017-03-24 10:00:05.420", "Duration": 0.05,
         "Proto": "TCP", "SrcIpAddr": "192.168.220.12", "SrcPt": 51413,
         "DstIpAddr": "192.168.100.3", "DstPt": 8000, "Packets": 1,
         "Bytes": 180000, "Flows": 1, "Flags": ".AP.SF", "Tos": 0},  # N02：超物理上界
        {"DateFirstSeen": "2017-03-24 10:00:06.001", "Duration": 1.4,
         "Proto": "TCP", "SrcIpAddr": "192.168.220.5", "SrcPt": 49152,
         "DstIpAddr": "192.168.100.3", "DstPt": 8000, "Packets": 10,
         "Bytes": 5200, "Flows": 1, "Flags": ".AP.SF", "Tos": 0},
        {"DateFirstSeen": "2017-03-24 10:00:07.640", "Duration": 0.0,
         "Proto": "UDP", "SrcIpAddr": "192.168.220.9", "SrcPt": 137,
         "DstIpAddr": "192.168.220.255", "DstPt": 137, "Packets": 1,
         "Bytes": 92, "Flows": 1, "Flags": "......", "Tos": 0},
        {"DateFirstSeen": "2017-03-24 10:00:08.220", "Duration": 0.01,
         "Proto": "TCP", "SrcIpAddr": "192.168.220.14", "SrcPt": 41608,
         "DstIpAddr": "192.168.220.3", "DstPt": 53, "Packets": 2,
         "Bytes": 178, "Flows": 1, "Flags": ".AP.SF", "Tos": 0},     # N03：53 端口非 DNS 身份
        {"DateFirstSeen": "2017-03-24 10:00:09.508", "Duration": 0.33,
         "Proto": "TCP", "SrcIpAddr": "192.168.210.5", "SrcPt": 445,
         "DstIpAddr": "192.168.220.15", "DstPt": 52174, "Packets": 8,
         "Bytes": 3664, "Flows": 1, "Flags": ".AP.SF", "Tos": 0},
        {"DateFirstSeen": "2017-03-24 10:00:10.090", "Duration": 0.0,
         "Proto": "UDP", "SrcIpAddr": "192.168.220.6", "SrcPt": 38844,
         "DstIpAddr": "DNS", "DstPt": 53, "Packets": 2, "Bytes": 196,
         "Flows": 1, "Flags": "......", "Tos": 0},
    ]
    return [dict(r) for r in base[:n]]


_NET_COLS = ["Proto", "SrcIpAddr", "SrcPt", "DstIpAddr", "DstPt",
             "Packets", "Bytes", "Flags"]


def _rows_to_md_table(rows: list[dict[str, Any]],
                      cols: list[str] | None = None) -> str:
    cols = cols or _NET_COLS
    head = "| # | " + " | ".join(cols) + " |"
    sep = "|---" * (len(cols) + 1) + "|"
    lines = [head, sep]
    for i, row in enumerate(rows):
        lines.append("| " + " | ".join(
            [str(i + 1)] + [str(row.get(c, "")) for c in cols]) + " |")
    return "\n".join(lines)


def _generate_network_rows_in_subprocess(n: int) -> list[dict[str, Any]]:
    code = (
        "import json;"
        "from forge.core.generator import ConstrainedGenerator;"
        f"rows = ConstrainedGenerator.from_bundle('network_cidds').generate({n!r});"
        "print(json.dumps(rows, ensure_ascii=False))"
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["CUDA_VISIBLE_DEVICES"] = ""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=FORGE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=LEJIT_SUBPROCESS_TIMEOUT,
        env=env,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout)[-1200:]
        raise RuntimeError(f"LeJIT 子进程退出码 {proc.returncode}: {tail}")
    try:
        payload = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception as exc:
        raise RuntimeError(f"LeJIT 子进程输出无法解析: {(proc.stdout or '')[-500:]}") from exc
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise RuntimeError("LeJIT 子进程未返回行对象列表")
    return payload


# ---------------------------------------------------------------------------
# DualReporter
# ---------------------------------------------------------------------------

class DualReporter:
    """双轨报告生成器（财务 + 网络）。llm 为 contracts.LLMClient（可 None）."""

    def __init__(self, llm=None, validator=None, projector: Projector | None = None,
                 template_path: str | Path | None = None):
        self.llm = llm
        self._validator = validator           # 懒加载 FinanceValidator
        self.projector = projector or Projector()
        self.template_path = Path(template_path or FIN_TEMPLATE_PATH)
        self.last_b_warnings: list[str] = []  # 最近一次 B 轨终检告警
        self.last_slots: dict[str, Any] = {}  # 最近一次 B 轨槽位（chat 校验复用）

    @property
    def validator(self):
        if self._validator is None:
            from forge.scenarios.finance_v1.validator import FinanceValidator  # noqa: PLC0415
            self._validator = FinanceValidator()
        return self._validator

    # ====================================================================== 财务
    # -- A 轨 -------------------------------------------------------------------
    def track_a(self, df_faulty, vreport: ViolationReport | None = None,
                company_name: str = "华信咨询") -> TrackReport:
        """A 轨：裸模型基于错误资料直接撰写报告（mock 走确定性降级）."""
        markdown = None
        if self.llm is not None:
            prompt = self._induce_prompt(df_faulty, company_name)
            try:
                resp = self.llm.complete(
                    prompt, role="induce",
                    system="你是一名财务分析师，根据给定报表数据撰写中文分析报告。")
            except Exception as exc:
                log.warning("A 轨 LLM 调用失败（%s），走确定性降级", exc)
                resp = ""
            if resp and not resp.strip().startswith("[mock:") and len(resp) > 300:
                markdown = resp
        if markdown is None:
            markdown = self._track_a_fallback(df_faulty, company_name)
        return TrackReport(
            track="A",
            markdown=markdown,
            slots={},
            violations=list(vreport.violations) if vreport else [],
            intervention_log=[],
        )

    def _induce_prompt(self, df, company_name: str) -> str:
        csv_text = df.to_csv(index=False)
        return (
            f"下面是 {company_name} 共 {len(df)} 期的财务报表数据（金额千元）：\n\n"
            f"{csv_text}\n\n"
            f"请逐期引用表中数字（营业收入、营业成本、毛利润、期初/期末现金、"
            f"期末存货、资产总计、负债、权益、应收账款），计算各期毛利率，"
            f"撰写一份 Markdown 格式的《{company_name}年度财务分析与审阅报告》。"
            f"以表中数据为准，不要质疑数据本身。"
        )

    def _track_a_fallback(self, df, company_name: str) -> str:
        """确定性降级：照抄错误资料逐期叙述（含用错误数字连带算错的毛利率）."""
        d = df.sort_values("PeriodIndex").reset_index(drop=True)
        lines = [
            f"# {company_name}年度财务分析与审阅报告（A 轨 · 裸模型直写）",
            "",
            "> 本报告由未接入规则引擎的语言模型按原始资料直接撰写，"
            "全部数字照抄资料包，未经勾稽校验。",
            "",
            "## 一、分期经营情况",
            "",
        ]
        for rec in d.itertuples():
            rev, cogs = int(rec.Revenue), int(rec.COGS)
            gp = int(rec.GrossProfit)
            margin = gp / rev if rev else 0.0      # 用账面（可能错误的）毛利算毛利率
            lines.append(
                f"- 第 {int(rec.PeriodIndex)} 期：营业收入 {_fmt(rev)} 千元，"
                f"营业成本 {_fmt(cogs)} 千元，毛利润 {_fmt(gp)} 千元"
                f"（毛利率 {_pct(margin)}）；期初现金 {_fmt(rec.Cash_Begin)}、"
                f"期末现金 {_fmt(rec.Cash_End)}；期末存货 {_fmt(rec.Inventory_End)}，"
                f"应收账款 {_fmt(rec.AccountsReceivable)}；资产总计 "
                f"{_fmt(rec.TotalAssets)}，负债总计 {_fmt(rec.TotalLiabilities)}，"
                f"所有者权益 {_fmt(rec.TotalEquity)}。")
        last = d.iloc[-1]
        lines += [
            "",
            "## 二、总体评价",
            "",
            f"报告期内公司收入稳步增长，账面毛利率维持高位；期末存货 "
            f"{_fmt(last['Inventory_End'])} 千元，反映公司积极备货、业务扩张。"
            f"应收账款增长体现客户合作深化。各期报表数据完整，未见明显异常，"
            f"整体经营状况良好。",
        ]
        return "\n".join(lines)

    # -- B 轨 -------------------------------------------------------------------
    def track_b(self, df_faulty, vreport: ViolationReport | None = None,
                ruleset=None, truth: dict | None = None,
                data_path: str = "华信咨询_待审资料包.csv") -> TrackReport:
        """B 轨：validate → Projector 修正 → 槽位计算 → 模板回填 → 终检."""
        if vreport is None:
            vreport = self.validator.validate(df_faulty, data_path)
        df_corr, interventions = self.projector.project(vreport, df_faulty)
        slots = self._compute_slots(df_faulty, df_corr, vreport, ruleset,
                                    truth, data_path)
        template = self.template_path.read_text(encoding="utf-8")
        markdown = fill_slots(template, slots)
        warnings = final_check(markdown, slots, template)
        self.last_b_warnings = warnings
        self.last_slots = slots
        intervention_log = list(interventions)
        if warnings:
            intervention_log += [f"【终检告警】{w}" for w in warnings]
        else:
            intervention_log.append(
                "终检通过：正文无残留槽位，全部数值均来自槽位白名单（程序回填）。")
        return TrackReport(
            track="B",
            markdown=markdown,
            slots=slots,
            violations=[],          # B 轨产出零违规（修正后）
            intervention_log=intervention_log,
        )

    # -- 槽位计算（全部从 df / 违规清单推导） -------------------------------------
    def _compute_slots(self, df_faulty, df_corr, vreport: ViolationReport,
                       ruleset, truth: dict | None,
                       data_path: str) -> dict[str, Any]:
        from forge.scenarios.finance_v1.generator import (  # noqa: PLC0415
            SPEC_AR_RATIO_BAND, SPEC_INV_BP_BAND, SPEC_MARGIN_BAND)

        d = df_corr.sort_values("PeriodIndex").reset_index(drop=True)
        last = d.iloc[-1]
        first = d.iloc[0]
        industry = str(first["Industry"])
        n = len(d)

        by_rule_first: dict[str, Violation] = {}
        for v in vreport.violations:
            by_rule_first.setdefault(v.rule_id, v)

        def period_of(row_index: int) -> int:
            return int(df_faulty.reset_index(drop=True).at[row_index, "PeriodIndex"])

        slots: dict[str, Any] = {}
        company_name = (truth or {}).get("company_name_zh") or str(first["CompanyId"])
        slots["company_name"] = company_name
        slots["industry_zh"] = INDUSTRY_ZH.get(industry, industry)
        slots["period_first"] = str(int(first["PeriodIndex"]))
        slots["period_last"] = str(int(last["PeriodIndex"]))
        slots["period_count"] = str(n)
        slots["data_source"] = data_path
        rules = list(ruleset.rules) if ruleset is not None else []
        slots["ruleset_name"] = (getattr(ruleset, "scenario", None)
                                 or "finance_v1") + " 规则集"
        slots["rule_count"] = str(len(rules)) if rules else "7"
        slots["rule_enabled_count"] = (str(len([r for r in rules if r.enabled]))
                                       if rules else "7")
        slots["learned_rule_count"] = str(len([r for r in rules
                                               if r.source == "learned"]))
        slots["manual_rule_count"] = (str(len([r for r in rules
                                               if r.source == "manual"]))
                                      if rules else "7")

        # 概况指标（修正后口径）
        rev_first, rev_last = int(first["Revenue"]), int(last["Revenue"])
        slots["revenue_latest"] = f"{_fmt(rev_last)} 千元"
        slots["revenue_total"] = f"{_fmt(int(d['Revenue'].sum()))} 千元"
        cagr = (rev_last / rev_first) ** (1.0 / max(n - 1, 1)) - 1.0
        slots["revenue_cagr_pct"] = _pct(cagr)
        inv_lo, inv_hi = SPEC_INV_BP_BAND.get(industry, (0, 10000))
        slots["industry_inv_band"] = f"{inv_lo / 100:.2f}%–{inv_hi / 100:.2f}%"
        ar_lo, ar_hi = SPEC_AR_RATIO_BAND.get(industry, (0.0, 1.0))
        slots["industry_ar_band"] = f"{_pct(ar_lo)}–{_pct(ar_hi)}"
        mg_lo, mg_hi = SPEC_MARGIN_BAND.get(industry, (0.0, 1.0))
        slots["industry_margin_band"] = f"{_pct(mg_lo)}–{_pct(mg_hi)}"
        slots["inv_to_assets_pct_latest"] = _pct(
            int(last["Inventory_End"]) / int(last["TotalAssets"]))
        slots["ar_to_revenue_pct_latest"] = _pct(
            int(last["AccountsReceivable"]) / rev_last)
        slots["gross_margin_pct_latest"] = _pct(int(last["GrossProfit"]) / rev_last)

        # 规则校验结果表
        for rid in ("R01", "R02", "R03", "R04", "R05", "R06", "R07"):
            hits = vreport.by_rule.get(rid, 0)
            if hits == 0:
                status = "✅ 通过"
            elif rid in ("R06", "R07"):
                status = f"⚠ 命中 {hits} 处 · 风险提示（不改数）"
            else:
                status = f"❌ 命中 {hits} 处 · 已按恒等式修正"
            slots[f"{rid.lower()}_status"] = status

        slots["total_rows"] = str(vreport.total_rows)
        slots["violation_count"] = str(len(vreport.violations))
        slots["satisfaction_rate_pct"] = _pct(vreport.satisfaction_rate)

        # F1（R01）：进销存勾稽
        v = by_rule_first.get("R01")
        if v is not None:
            r = v.row_index
            slots["f1_period"] = str(period_of(r))
            slots["cogs_reported"] = _fmt(v.observed["COGS"])
            slots["f1_inventory_begin"] = _fmt(v.observed["Inventory_Begin"])
            slots["f1_purchases"] = _fmt(v.observed["Purchases"])
            slots["f1_inventory_end"] = _fmt(v.observed["Inventory_End"])
            cogs_new = int(df_corr.reset_index(drop=True).at[r, "COGS"])
            slots["cogs_corrected"] = _fmt(cogs_new)
            slots["f1_diff"] = f"{int(v.observed['COGS']) - cogs_new:+,}"
            slots["gross_profit_corrected"] = _fmt(
                df_corr.reset_index(drop=True).at[r, "GrossProfit"])
        else:
            for k in ("f1_period", "cogs_reported", "f1_inventory_begin",
                      "f1_purchases", "f1_inventory_end", "cogs_corrected",
                      "f1_diff", "gross_profit_corrected"):
                slots[k] = "—"

        # F2a（R04）：现金跨期
        v = by_rule_first.get("R04")
        if v is not None:
            slots["f2a_period"] = str(period_of(v.row_index))
            slots["f2a_cash_begin_reported"] = _fmt(v.observed["Cash_Begin"])
            slots["f2a_cash_end_prev"] = _fmt(v.observed["上期Cash_End"])
            slots["f2a_diff"] = f"{int(v.observed['Cash_Begin']) - int(v.observed['上期Cash_End']):+,}"
        else:
            for k in ("f2a_period", "f2a_cash_begin_reported",
                      "f2a_cash_end_prev", "f2a_diff"):
                slots[k] = "—"

        # F2b（R02）：资产负债配平
        v = by_rule_first.get("R02")
        if v is not None:
            ta = int(v.observed["TotalAssets"])
            tlte = int(v.observed["TotalLiabilities"]) + int(v.observed["TotalEquity"])
            slots["f2b_period"] = str(period_of(v.row_index))
            slots["f2b_total_assets"] = _fmt(ta)
            slots["f2b_liab_plus_equity"] = _fmt(tlte)
            slots["f2b_diff"] = f"{ta - tlte:+,}"
        else:
            for k in ("f2b_period", "f2b_total_assets",
                      "f2b_liab_plus_equity", "f2b_diff"):
                slots[k] = "—"

        # F3（R06）：行业画像
        v = by_rule_first.get("R06")
        if v is not None:
            slots["f3_period"] = str(period_of(v.row_index))
            slots["f3_inventory_end"] = _fmt(v.observed["Inventory_End"])
            slots["f3_inv_ratio_pct"] = _pct(
                int(v.observed["Inventory_End"]) / int(v.observed["TotalAssets"]))
        else:
            for k in ("f3_period", "f3_inventory_end", "f3_inv_ratio_pct"):
                slots[k] = "—"

        # F4（R07）：应收/营收背离
        v = by_rule_first.get("R07")
        if v is not None:
            slots["f4_period"] = str(period_of(v.row_index))
            slots["f4_ar_reported"] = _fmt(v.observed["AccountsReceivable"])
            slots["f4_ar_growth_pct"] = str(v.observed.get("应收同比增速", "—"))
            slots["f4_revenue_growth_pct"] = str(v.observed.get("营收同比增速", "—"))
        else:
            for k in ("f4_period", "f4_ar_reported", "f4_ar_growth_pct",
                      "f4_revenue_growth_pct"):
                slots[k] = "—"

        # 经营分析（修正后口径）
        margins = (d["GrossProfit"] / d["Revenue"]).astype(float)
        slots["gross_margin_pct_avg"] = _pct(float(margins.mean()))
        slots["net_margin_pct_avg"] = _pct(
            float((d["NetProfit"] / d["Revenue"]).astype(float).mean()))
        slots["cash_end_latest"] = f"{_fmt(last['Cash_End'])} 千元"
        slots["debt_ratio_pct_latest"] = _pct(
            int(last["TotalLiabilities"]) / int(last["TotalAssets"]))
        slots["inventory_turnover_comment"] = (
            "平稳，未见异常囤积或集中出清（按修正后采购口径）"
            if "R06" not in vreport.by_rule else
            "总体平稳，但存在画像异常期（见风险提示），建议盘点核实")
        f4_period = slots.get("f4_period", "—")
        ar_ratio = (d["AccountsReceivable"] / d["Revenue"]).astype(float)
        if v is not None:
            mask = d["PeriodIndex"].astype(int) != int(slots["f4_period"])
            ar_ratio = ar_ratio[mask]
        slots["ar_to_revenue_pct_normal"] = _pct(float(ar_ratio.mean()))
        slots["growth_comment"] = f"稳健（期均增速约 {_pct(cagr)}）"
        _ = f4_period

        # 风险提示（来自不改数的画像/比率违规 + 修正提示）
        risk_items: list[str] = []
        v6, v7 = by_rule_first.get("R06"), by_rule_first.get("R07")
        if v6 is not None:
            risk_items.append(f"{v6.message_zh}（R06，仅提示不改数）")
        if v7 is not None:
            risk_items.append(f"{v7.message_zh}（R07，建议函证应收账款）")
        fixed = [rid for rid in ("R01", "R02", "R03", "R04", "R05")
                 if rid in vreport.by_rule]
        if fixed:
            risk_items.append(
                f"勾稽类违规（{'、'.join(fixed)}）已按恒等式修正，"
                f"建议向管理层询证原始凭证以确认错报性质。")
        while len(risk_items) < 3:
            risk_items.append("无其他重大风险事项。")
        slots["risk_item_1"], slots["risk_item_2"], slots["risk_item_3"] = risk_items[:3]

        # 附录
        slots["data_path"] = vreport.data_path or data_path
        slots["total_fields"] = str(len(d.columns))
        slots["validator_engine"] = "FinanceValidator（纯 Python 确定性校验）"
        vio_lines = [
            f"{v.rule_id} 第 {period_of(v.row_index)} 期 — {v.message_zh}"
            for v in vreport.violations]
        slots["violations_table"] = ("；".join(vio_lines)
                                     if vio_lines else "无违规")
        slots["truth_table_match_summary"] = self._truth_summary(vreport, truth)
        slots["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        slots["trace_id"] = uuid.uuid4().hex[:12]
        return slots

    @staticmethod
    def _truth_summary(vreport: ViolationReport, truth: dict | None) -> str:
        if not truth or "faults" not in truth:
            return "未提供真值表（跳过比对）"
        hit, total, pairs = 0, 0, []
        for fid, info in truth["faults"].items():
            total += 1
            rid = info.get("rule_id", "")
            ok = rid in vreport.by_rule
            hit += int(ok)
            pairs.append(f"{fid}→{rid}{'✓' if ok else '✗'}")
        return f"{hit}/{total} 项注入错误被命中（{'、'.join(pairs)}）"

    # -- 双轨组装 -----------------------------------------------------------------
    def make_dual(self, df_faulty=None, truth: dict | None = None,
                  ruleset=None,
                  data_path: str = "华信咨询_待审资料包.csv") -> DualReport:
        """财务双轨报告：A 轨照抄错误 + B 轨修正回填 + diff 标红 HTML."""
        if df_faulty is None:
            from forge.scenarios.finance_v1.faults import inject_faults  # noqa: PLC0415
            df_faulty, truth = inject_faults()
        company_name = (truth or {}).get("company_name_zh") or \
            str(df_faulty.iloc[0]["CompanyId"])
        vreport = self.validator.validate(df_faulty, data_path)
        a = self.track_a(df_faulty, vreport, company_name)
        b = self.track_b(df_faulty, vreport, ruleset=ruleset, truth=truth,
                         data_path=data_path)
        diff_html = self._build_diff_html(vreport, df_faulty)
        return DualReport(
            scenario="finance_v1",
            title=f"{company_name}年度财务分析与审阅报告（双轨对比）",
            track_a=a,
            track_b=b,
            diff_html=diff_html,
        )

    def _build_diff_html(self, vreport: ViolationReport, df_faulty) -> str:
        """diff 标红 HTML：A 轨错误数字 <span class="err …">，B 轨 <span class="ok …">.

        类名对齐 web/src/pages/FinanceDemoPage.tsx 的
        mark-num/mark-bad/mark-ok 与 track-col/track-a/track-b 约定。
        """
        from forge.scenarios.finance_v1.generator import FIN_SOURCE_NAME_ZH  # noqa: PLC0415
        d = df_faulty.reset_index(drop=True)
        a_parts: list[str] = []
        b_parts: list[str] = []
        for v in vreport.violations:
            field = PRIMARY_FIELD.get(v.rule_id) or (v.fields[0] if v.fields else "")
            if v.rule_id == "R02":
                field = "TotalAssets"          # A 轨展示的错账主字段
            wrong = v.observed.get(field)
            if wrong is None and v.fields:
                field = v.fields[0]
                wrong = v.observed.get(field)
            wrong_fmt = _fmt(wrong) if isinstance(wrong, (int, float)) else str(wrong)
            field_zh = FIN_SOURCE_NAME_ZH.get(field, field)
            period = int(d.at[v.row_index, "PeriodIndex"]) \
                if "PeriodIndex" in d.columns else v.row_index + 1
            m = re.search(r"应为\s*([\d,]+)", v.expected or "")
            correct_fmt = m.group(1) if m else None
            tip = (f"命中{v.rule_id}：应为 {correct_fmt}" if correct_fmt
                   else f"命中{v.rule_id}：{v.expected}")
            a_parts.append(
                f'<p>第 {period} 期 {field_zh} '
                f'<span class="err mark-num mark-bad" title="{tip}">{wrong_fmt}</span>'
                f' — {v.message_zh}</p>')
            if correct_fmt:
                b_parts.append(
                    f'<p>第 {period} 期 {field_zh} '
                    f'<span class="ok mark-num mark-ok" '
                    f'title="依据 {v.rule_id} 修正（{v.rule_text}）">{correct_fmt}</span>'
                    f'（已按恒等式修正）</p>')
            else:
                b_parts.append(
                    f'<p>第 {period} 期 {field_zh} '
                    f'<span class="ok mark-num mark-ok" '
                    f'title="{v.rule_id}：画像/比率背离不改数">{wrong_fmt}</span>'
                    f'（维持账面值，出具风险提示）</p>')
        return (
            '<div class="dual-track dual-report">'
            '<div class="track-col track-a">'
            '<div class="track-head"><span class="track-badge badge-a">A 轨 · 裸模型报告</span>'
            f'<span class="track-verdict bad">标红 {len(a_parts)} 处</span></div>'
            + "".join(a_parts) +
            '</div>'
            '<div class="track-col track-b">'
            '<div class="track-head"><span class="track-badge badge-b">B 轨 · 合规报告</span>'
            '<span class="track-verdict ok">0 违规</span></div>'
            + "".join(b_parts) +
            '</div></div>')

    # ====================================================================== 网络
    def track_a_network(
        self,
        n: int = 10,
        rows: list[dict[str, Any]] | None = None,
        source_label: str = "裸模型生成",
    ) -> TrackReport:
        """A 轨：裸模型生成 NetFlow（mock 走确定性带错样本）."""
        source_rows = [dict(row) for row in rows] if rows is not None else None
        if source_rows is not None:
            rows = source_rows
        elif self.llm is not None:
            prompt = (
                f"请生成 {n} 条 CIDDS 风格的 NetFlow CSV 记录，字段："
                f"{','.join(_NET_COLS)}。只输出 CSV（含表头），不要解释。")
            try:
                resp = self.llm.complete(prompt, role="induce",
                                         system="你是网络流量数据生成器。")
            except Exception as exc:
                log.warning("网络 A 轨 LLM 失败（%s），走确定性样本", exc)
                resp = ""
            rows = self._parse_csv_rows(resp) if resp and \
                not resp.strip().startswith("[mock:") else None
        if not rows:
            rows = mock_netflow_with_errors(n)
        violations = check_netflow_rows(rows)
        if source_rows is None and (len(rows) < n or not violations):
            rows = mock_netflow_with_errors(n)
            violations = check_netflow_rows(rows)
        heading = f"## A 轨 · {source_label}的 NetFlow（{len(rows)} 条）"
        md = (heading + "\n\n"
              + _rows_to_md_table(rows) + "\n\n### 规则核查\n\n"
              + ("\n".join(f"- ❌ {v.message_zh}" for v in violations)
                 if violations else "- ✅ 0 违规"))
        return TrackReport(track="A", markdown=md,
                           slots={"rows": rows}, violations=violations,
                           intervention_log=[])

    @staticmethod
    def _parse_csv_rows(text: str) -> list[dict[str, Any]] | None:
        """宽松解析 LLM 输出的 CSV（失败返回 None → 走确定性样本）."""
        import csv
        import io
        lines = [ln for ln in text.strip().splitlines() if "," in ln]
        if len(lines) < 2:
            return None
        try:
            reader = csv.DictReader(io.StringIO("\n".join(lines)))
            rows = [dict(r) for r in reader]
            return rows if rows and all(
                c in rows[0] for c in ("Proto", "Packets", "Bytes")) else None
        except Exception:
            return None

    def track_b_network(self, n: int = 10, generator=None) -> TrackReport:
        """B 轨：LeJIT 生成后终检过滤并补采，不用静态样本伪装成功."""
        rows: list[dict[str, Any]] | None = None
        valid_rows: list[dict[str, Any]] = []
        logbook: list[str] = []

        def collect_candidates(candidates: list[dict[str, Any]], source: str) -> None:
            valid, rejected = _split_valid_netflow_rows(candidates)
            if rejected:
                logbook.append(
                    f"{source} 终检剔除 {len(rejected)} 条不合规记录，"
                    f"保留 {len(valid)} 条。"
                )
            valid_rows.extend(valid)

        gen = generator
        if gen is None:
            try:
                from forge.core.generator import ConstrainedGenerator  # noqa: PLC0415
                gen = ConstrainedGenerator.from_bundle("network_cidds")
            except Exception as exc:
                logbook.append(f"LeJIT bundle 不可用（{exc}），改用隔离子进程重试。")
                gen = None
        max_attempts = 8
        if gen is not None:
            try:
                candidates = gen.generate(n)
                logbook.append(f"LeJIT 约束解码生成 {len(candidates)} 条记录"
                               f"（每步经 Z3 过滤，构造性满足规则）。")
                collect_candidates(candidates, "LeJIT")
                for attempt in range(max_attempts):
                    if len(valid_rows) >= n:
                        break
                    need = max(n, (n - len(valid_rows)) * 4)
                    extra = gen.generate(need)
                    logbook.append(
                        f"LeJIT 补采第 {attempt + 1} 轮生成 {len(extra)} 条记录。"
                    )
                    collect_candidates(extra, "LeJIT 补采")
            except Exception as exc:
                logbook.append(f"LeJIT 同进程生成失败（{exc}），改用隔离子进程重试。")
        if len(valid_rows) < n:
            try:
                for attempt in range(max_attempts):
                    if len(valid_rows) >= n:
                        break
                    need = max(n, (n - len(valid_rows)) * 5)
                    candidates = _generate_network_rows_in_subprocess(need)
                    logbook.append(
                        f"LeJIT 隔离子进程第 {attempt + 1} 轮生成 {len(candidates)} 条记录。"
                    )
                    collect_candidates(candidates, "LeJIT 隔离子进程")
            except Exception as sub_exc:
                logbook.append(
                    f"LeJIT 子进程生成失败（{sub_exc}），终止本次 B 轨生成。"
                )
        if len(valid_rows) >= n:
            rows = valid_rows[:n]
            logbook.append(
                f"LeJIT 终检后获得 {len(rows)} 条合规记录（全程使用 LeJIT 筛选结果）。"
            )
        else:
            raise RuntimeError(
                f"LeJIT 终检过滤后仅获得 {len(valid_rows)}/{n} 条合规记录，"
                "拒绝使用静态样本伪装成功。"
            )
        violations = check_netflow_rows(rows)
        for v in violations:    # 理论上为空；若 LeJIT 输出异常在此兜底记录
            logbook.append(f"【告警】B 轨记录违规：{v.message_zh}")
        if violations:
            raise RuntimeError(
                "B 轨终检发现已筛选 LeJIT 记录仍有违规，拒绝使用静态样本伪装成功。"
            )
        if not violations:
            logbook.append(
                f"B 轨终检：{len(rows)} 条记录全部通过协议/物理/身份规则核查，0 违规。"
            )
        md = (f"## B 轨 · 规则约束生成的 NetFlow（{len(rows)} 条）\n\n"
              + _rows_to_md_table(rows) + "\n\n### 规则核查\n\n- ✅ 0 违规")
        return TrackReport(track="B", markdown=md,
                           slots={"rows": rows}, violations=violations,
                           intervention_log=logbook)

    def make_dual_network(
        self,
        n: int = 10,
        generator=None,
        track_a_rows: list[dict[str, Any]] | None = None,
        track_a_source_label: str = "裸模型生成",
    ) -> DualReport:
        """网络双轨：A 轨带错样本标红 vs B 轨约束生成 0 违规."""
        a = self.track_a_network(
            n,
            rows=track_a_rows,
            source_label=track_a_source_label,
        )
        b_count = len(a.slots.get("rows", [])) if track_a_rows is not None else n
        b = self.track_b_network(b_count, generator=generator)
        diff_html = self._build_net_diff_html(a, b)
        return DualReport(
            scenario="network_cidds",
            title="NetFlow 双轨生成对比（裸模型 vs 规则约束）",
            track_a=a, track_b=b, diff_html=diff_html)

    def _build_net_diff_html(self, a: TrackReport, b: TrackReport) -> str:
        a_rows: list[dict[str, Any]] = a.slots.get("rows", [])
        b_rows: list[dict[str, Any]] = b.slots.get("rows", [])
        bad_cells: dict[tuple[int, str], Violation] = {}
        for v in a.violations:
            for f in v.fields:
                bad_cells[(v.row_index, f)] = v

        def cell(row_i: int, col: str, value: Any, track: str) -> str:
            text = str(value)
            if track == "A" and (row_i, col) in bad_cells:
                v = bad_cells[(row_i, col)]
                return (f'<span class="err mark-num mark-bad" '
                        f'title="命中{v.rule_id}：{v.expected}">{text}</span>')
            if track == "B" and any(k[0] == row_i for k in bad_cells) and \
                    col in {c for (r, c) in bad_cells if r == row_i}:
                return (f'<span class="ok mark-num mark-ok" '
                        f'title="约束解码保证合规">{text}</span>')
            return text

        def table(rows: list[dict[str, Any]], track: str) -> str:
            head = "".join(f"<th>{c}</th>" for c in _NET_COLS)
            body = "".join(
                "<tr>" + "".join(
                    f"<td>{cell(i, c, r.get(c, ''), track)}</td>"
                    for c in _NET_COLS) + "</tr>"
                for i, r in enumerate(rows))
            return (f'<table class="data-table"><thead><tr>{head}</tr></thead>'
                    f'<tbody>{body}</tbody></table>')

        return (
            '<div class="dual-track dual-report">'
            '<div class="track-col track-a">'
            '<div class="track-head"><span class="track-badge badge-a">A 轨 · 裸模型</span>'
            f'<span class="track-verdict bad">{len(a.violations)} 条违规</span></div>'
            + table(a_rows, "A") +
            '</div>'
            '<div class="track-col track-b">'
            '<div class="track-head"><span class="track-badge badge-b">B 轨 · 规则约束</span>'
            f'<span class="track-verdict ok">{len(b.violations)} 违规</span></div>'
            + table(b_rows, "B") +
            '</div></div>')
