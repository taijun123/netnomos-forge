# -*- coding: utf-8 -*-
"""server.pipeline — 编排核心（纯 Python，可脱离 HTTP 直接测试）.

两条管线：
- run_finance_pipeline(job, emit)：财务双轨。沙箱内真正端到端跑通：
  生成清洁资料包 → 错误注入（F1–F4）→ 规则集（人工通道加载 manual_rules.json
  + R06/R07 软规则）→ 规则卡（engine.explain + explainer RAG 增强）→
  validate → Projector 修正 → 双轨报告 + diff。
- run_network_pipeline(job, emit)：网络双轨。learn 在沙箱降级为加载
  golden_cidds 规则文件（NetNomos 仓库 rules/golden_cidds/rules.json，
  纯 JSON 解析）；宿主机可传 use_netnomos=True 走真实 NetNomosMiner 学习。

emit 为 ``emit(WorkflowEvent) -> None`` 回调；事件 stage 顺序：
upload → prepare → learn → explain → validate → project → report → diff，
首尾由 control 阶段包裹（status running / done），与 contracts.STAGE_AGENT
的 agent 映射一致（WorkflowEvent.make 自动推导 agent）。
"""
from __future__ import annotations

import logging
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable

from forge.contracts import Rule, RuleSet, SCENARIO_DIR, WorkflowEvent

log = logging.getLogger("server.pipeline")

FORGE_ROOT = Path(__file__).resolve().parents[1]          # netnomos-forge/
FORGE_CIDDS_RULES = FORGE_ROOT / "forge" / "rulesets" / "network_cidds" / "golden" / "rules.json"
NETNOMOS_CIDDS_RULES = FORGE_ROOT.parent / "NetNomos" / "rules" / "golden_cidds" / "rules.json"
GOLDEN_CIDDS_RULES = FORGE_CIDDS_RULES if FORGE_CIDDS_RULES.exists() else NETNOMOS_CIDDS_RULES
CIDDS_TRAIN_CSV = FORGE_ROOT.parent / "NetNomos" / "data" / "cidds_wk2_normal_10k.csv"
FIN_MANUAL_RULES = SCENARIO_DIR / "finance_v1" / "manual_rules.json"

Emit = Callable[[WorkflowEvent], None]

# 网络规则卡最多展示条数（golden 规则集较大，截断保证演示节奏）
NET_MAX_CARDS = 12
ENABLE_RULECARD_LLM = os.getenv("FORGE_RULECARD_LLM", "").lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        log.warning("环境变量 %s=%r 不是整数，使用默认值 %s", name, raw, default)
        return default


RULECARD_LLM_MAX_CARDS = _env_int("FORGE_RULECARD_LLM_MAX_CARDS", 2)


def _ev(emit: Emit, stage: str, status: str, desc: str) -> None:
    emit(WorkflowEvent.make(stage, status, desc))


# ---------------------------------------------------------------------------
# 财务管线（沙箱端到端可跑）
# ---------------------------------------------------------------------------

def run_finance_pipeline(job: Any, emit: Emit, llm=None,
                         use_netnomos: bool = False) -> dict[str, Any]:
    """财务双轨管线。返回 {ruleset, cards, vreport, dual, truth}。

    use_netnomos=True（宿主机）时 learn 阶段尝试真实 NetNomosMiner 学习并与
    人工规则合并；沙箱保持 False，规则集来自人工通道（确定性、零外部依赖）。
    """
    from forge.core.engine import ForgeRuleEngine          # noqa: PLC0415
    from forge.core.explainer import RuleExplainer         # noqa: PLC0415
    from forge.core.reporter import DualReporter           # noqa: PLC0415
    from forge.scenarios.finance_v1.faults import (        # noqa: PLC0415
        build_clean_package, inject_faults)
    from forge.scenarios.finance_v1.validator import (     # noqa: PLC0415
        FinanceValidator, RULE_TEXTS)

    _ev(emit, "control", "running", "财务双轨报告任务开始编排。")

    # -- upload：构造华信咨询待审资料包（确定性注入 F1–F4） --------------------
    _ev(emit, "upload", "running", "接收「华信咨询」待审资料包…")
    df_clean = build_clean_package()
    df_faulty, truth = inject_faults(df_clean)
    _ev(emit, "upload", "done",
        f"资料包就绪：{len(df_faulty)} 期报表，附错误清单真值表"
        f"（{len(truth['faults'])} 项注入错误）。")

    # -- prepare ---------------------------------------------------------------
    _ev(emit, "prepare", "running", "解析字段 / 中文列名映射 / 按期排序…")
    df_faulty = df_faulty.sort_values("PeriodIndex").reset_index(drop=True)
    _ev(emit, "prepare", "done",
        f"预处理完成：{len(df_faulty.columns)} 个字段（含派生折叠字段）。")

    # -- learn：规则集（人工通道兜底；宿主机可叠加真实学习） ---------------------
    _ev(emit, "learn", "running",
        "stage=learn processor=NetNomos hitting-set/Z3 + finance manual rule loader：装载财务规则集…")
    engine = ForgeRuleEngine.from_scenario("finance_v1")
    ruleset = RuleSet(scenario="finance_v1", rules=[])
    if use_netnomos and find_spec("netnomos") is not None:
        try:
            ruleset = engine.learn(None)   # dataset_spec 默认训练集
            _ev(emit, "learn", "running",
                f"stage=learn processor=NetNomos hitting-set/Z3：学习完成 {len(ruleset.rules)} 条，合并人工恒等式…")
        except Exception as exc:
            log.warning("真实学习失败（%s），仅用人工规则通道", exc)
    ruleset = engine.add_manual_rules(ruleset, FIN_MANUAL_RULES)
    # R06/R07 软规则（行业画像 / 比率背离）：由 FinanceValidator 内置实现
    for rid, kind in (("R06", "range"), ("R07", "ratio")):
        if not any(r.rule_id == rid for r in ruleset.rules):
            ruleset.rules.append(Rule(
                rule_id=rid, formula={}, text=RULE_TEXTS[rid], kind=kind,
                source="manual", support=1.0))
    _ev(emit, "learn", "done",
        f"stage=learn processor=NetNomos hitting-set/Z3 + manual rules：规则库就绪 {len(ruleset.rules)} 条（核心恒等式 R01–R05 经人工通道注入，"
        f"R06/R07 为画像/比率软规则）。")

    # -- explain：规则卡 + RAG 增强 ----------------------------------------------
    _ev(emit, "explain", "running",
        "stage=explain processor=RuleExplainer/RAG/gemma3 optional：生成中文规则卡…")
    cards = engine.explain(ruleset, llm=None)              # 确定性模板卡
    explainer = RuleExplainer.for_scenario("finance_v1")
    cards = explainer.enhance(
        cards,
        ruleset,
        llm=llm if ENABLE_RULECARD_LLM else None,
        context="财务报表审阅",
        max_llm_cards=RULECARD_LLM_MAX_CARDS,
    )
    coincidences = sum(1 for c in cards if c.is_coincidence)
    _ev(emit, "explain", "done",
        f"规则卡 {len(cards)} 张生成完毕（疑似巧合 {coincidences} 张）。")

    # -- validate ----------------------------------------------------------------
    _ev(emit, "validate", "running", "对资料包逐项核查勾稽关系…")
    validator = FinanceValidator()
    vreport = validator.validate(df_faulty, "华信咨询_待审资料包.csv")
    hit_rules = "、".join(sorted(vreport.by_rule))
    _ev(emit, "validate", "done",
        f"核查完成：{len(vreport.violations)} 处违规，命中规则 {hit_rules}，"
        f"满足率 {vreport.satisfaction_rate:.2%}。")

    # -- project -----------------------------------------------------------------
    _ev(emit, "project", "running", "数值投影：按恒等式求修正值…")
    reporter = DualReporter(llm=llm, validator=validator)
    df_corr, interventions = reporter.projector.project(vreport, df_faulty)
    fixes = sum(1 for line in interventions if not line.startswith("【"))
    _ev(emit, "project", "done",
        f"投影完成：{fixes} 处数值修正，"
        f"{sum(1 for l in interventions if l.startswith('【风险提示'))} 条风险提示。")

    # -- report：双轨 -------------------------------------------------------------
    _ev(emit, "report", "running",
        "stage=report processor=A轨裸模型+B轨约束：A 轨裸模型照抄错误资料撰写报告…")
    _ev(emit, "report", "running",
        "stage=report processor=A轨裸模型+B轨约束：B 轨修正口径槽位回填 + 终检扫描…")
    dual = reporter.make_dual(df_faulty, truth=truth, ruleset=ruleset)
    _ev(emit, "report", "done",
        f"双轨报告就绪：A 轨标红 {len(dual.track_a.violations)} 处，"
        f"B 轨终检告警 {len(reporter.last_b_warnings)} 条。")

    # -- diff ---------------------------------------------------------------------
    _ev(emit, "diff", "done", "双轨对比 diff 标红 HTML 生成完毕。")
    _ev(emit, "control", "done", "双轨报告归档完成。")
    return {
        "ruleset": ruleset,
        "cards": cards,
        "vreport": vreport,
        "dual": dual,
        "truth": truth,
        "interventions": interventions,
        "df_corrected": df_corr,
    }


# ---------------------------------------------------------------------------
# 网络管线（learn 沙箱降级为加载 golden 规则文件）
# ---------------------------------------------------------------------------

def run_network_pipeline(job: Any, emit: Emit, llm=None,
                         use_netnomos: bool = False) -> dict[str, Any]:
    """网络双轨管线。返回 {ruleset, cards, dual}。

    learn 阶段三级降级：真实 NetNomos 学习（宿主机 use_netnomos=True）→
    加载 golden_cidds 规则文件（纯 JSON）→ 内置 3 条人工核心规则。
    """
    from forge.core.engine import ForgeRuleEngine          # noqa: PLC0415
    from forge.core.explainer import RuleExplainer         # noqa: PLC0415
    from forge.core.reporter import NET_RULE_TEXTS, DualReporter  # noqa: PLC0415

    _ev(emit, "control", "running", "网络规则自发现任务开始编排。")
    _ev(emit, "upload", "running", "接收 cidds_wk2_normal_10k.csv…")
    data_note = (f"训练集就绪：{CIDDS_TRAIN_CSV.name}"
                 if CIDDS_TRAIN_CSV.exists()
                 else "训练集文件不在本机（仅影响真实学习，不影响降级演示）")
    _ev(emit, "upload", "done", data_note)
    _ev(emit, "prepare", "done", "DatasetSpec / GrammarSpec 解析完成。")

    # -- learn（三级降级） --------------------------------------------------------
    _ev(emit, "learn", "running",
        "stage=learn processor=NetNomos hitting-set/Z3：准备 CIDDS 规则集…")
    engine = ForgeRuleEngine.from_scenario("network_cidds")
    ruleset: RuleSet | None = None
    if use_netnomos and find_spec("netnomos") is not None and CIDDS_TRAIN_CSV.exists():
        try:
            ruleset = engine.learn(CIDDS_TRAIN_CSV)
            _ev(emit, "learn", "done",
                f"stage=learn processor=NetNomos hitting-set/Z3：学习完成 {len(ruleset.rules)} 条规则。")
        except Exception as exc:
            log.warning("真实学习失败（%s），降级加载 golden 规则", exc)
    if ruleset is None and GOLDEN_CIDDS_RULES.exists():
        ruleset = engine.load_netnomos_rules(GOLDEN_CIDDS_RULES)
        _ev(emit, "learn", "done",
            f"stage=learn processor=NetNomos hitting-set/Z3：加载已归档 golden 规则 {len(ruleset.rules)} 条"
            f"（hitting-set，来自 10k CIDDS 训练流量）。")
    if ruleset is None:
        ruleset = RuleSet(scenario="network_cidds", rules=[
            Rule(rule_id=rid, formula={}, text=text, kind=kind,
                 source="manual", support=1.0)
            for rid, text, kind in (
                ("N01", NET_RULE_TEXTS["N01"], "implication"),
                ("N02", NET_RULE_TEXTS["N02"], "bound"),
                ("N03", NET_RULE_TEXTS["N03"], "implication"),
            )])
        _ev(emit, "learn", "done",
            "stage=learn processor=manual fallback：golden 规则文件缺失，使用内置 3 条人工核心规则。")

    # -- explain ------------------------------------------------------------------
    _ev(emit, "explain", "running",
        "stage=explain processor=RuleExplainer/RAG/gemma3 optional：生成规则卡（截取前若干条演示）…")
    subset = RuleSet(scenario=ruleset.scenario,
                     rules=ruleset.rules[:NET_MAX_CARDS],
                     rules_path=ruleset.rules_path, run_dir=ruleset.run_dir)
    cards = engine.explain(subset, llm=None)
    explainer = RuleExplainer.for_scenario("network_cidds")
    cards = explainer.enhance(
        cards,
        subset,
        llm=llm if ENABLE_RULECARD_LLM else None,
        context="NetFlow 流量审计",
        max_llm_cards=RULECARD_LLM_MAX_CARDS,
    )
    _ev(emit, "explain", "done",
        f"规则卡 {len(cards)} 张（疑似巧合 "
        f"{sum(1 for c in cards if c.is_coincidence)} 张）。")

    # -- report / diff --------------------------------------------------------------
    _ev(emit, "report", "running",
        "stage=report processor=A轨裸模型+B轨约束：A 轨裸模型生成 10 条 NetFlow…")
    _ev(emit, "report", "running",
        "stage=report processor=A轨裸模型+B轨约束：B 轨 LeJIT 约束生成（沙箱降级读预置合规样本）…")
    reporter = DualReporter(llm=llm)
    dual = reporter.make_dual_network(10)
    _ev(emit, "report", "done",
        f"双轨生成完毕：A 轨 {len(dual.track_a.violations)} 条违规，"
        f"B 轨 {len(dual.track_b.violations)} 条违规。")
    _ev(emit, "diff", "done", "双轨 NetFlow 对比标红完成。")
    _ev(emit, "control", "done", "网络双轨产物归档完成。")
    return {"ruleset": ruleset, "cards": cards, "dual": dual}


# 前端 MockSequenceId → (场景, 管线函数)
SEQUENCE_PIPELINES: dict[str, tuple[str, Callable[..., dict[str, Any]]]] = {
    "learn-finance": ("finance_v1", run_finance_pipeline),
    "validate-finance": ("finance_v1", run_finance_pipeline),
    "report-finance": ("finance_v1", run_finance_pipeline),
    "learn-network": ("network_cidds", run_network_pipeline),
    "validate-network": ("network_cidds", run_network_pipeline),
    "report-network": ("network_cidds", run_network_pipeline),
}
