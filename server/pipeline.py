# -*- coding: utf-8 -*-
"""server.pipeline — 编排核心（纯 Python，可脱离 HTTP 直接测试）.

两条管线：
- run_finance_pipeline(job, emit)：财务双轨。沙箱内真正端到端跑通：
  生成清洁资料包 → 错误注入（F1–F4）→ 规则集（人工通道加载 manual_rules.json
  + R06/R07 软规则）→ 规则卡（engine.explain + explainer RAG 增强）→
  validate → Projector 修正 → 双轨报告 + diff。
- run_network_pipeline(job, emit)：网络双轨。learn 在沙箱降级为加载
  golden_cidds 规则文件（仓库内 NetNomos/rules/golden_cidds/rules.json，
  纯 JSON 解析）；宿主机可传 use_netnomos=True 走真实 NetNomosMiner 学习。

emit 为 ``emit(WorkflowEvent) -> None`` 回调；事件 stage 顺序：
upload → prepare → learn → explain → validate → project → report → diff，
首尾由 control 阶段包裹（status running / done），与 contracts.STAGE_AGENT
的 agent 映射一致（WorkflowEvent.make 自动推导 agent）。
"""
from __future__ import annotations

import logging
import os
import csv
import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable

from forge.contracts import Rule, RuleCard, RuleSet, SCENARIO_DIR, ViolationReport, WorkflowEvent
from forge.contracts import FIN_FIELDS

log = logging.getLogger("server.pipeline")

FORGE_ROOT = Path(__file__).resolve().parents[1]          # netnomos-forge/
FORGE_CIDDS_RULES = FORGE_ROOT / "forge" / "rulesets" / "network_cidds" / "golden" / "rules.json"
NETNOMOS_ROOT = FORGE_ROOT / "NetNomos"
NETNOMOS_CIDDS_RULES = NETNOMOS_ROOT / "rules" / "golden_cidds" / "rules.json"
GOLDEN_CIDDS_RULES = FORGE_CIDDS_RULES if FORGE_CIDDS_RULES.exists() else NETNOMOS_CIDDS_RULES
CIDDS_TRAIN_CSV = NETNOMOS_ROOT / "data" / "cidds_wk2_normal_10k.csv"
FIN_MANUAL_RULES = SCENARIO_DIR / "finance_v1" / "manual_rules.json"
NETWORK_UPLOADS_DIR = FORGE_ROOT / "demo_artifacts" / "uploads" / "network_cidds"
FINANCE_UPLOADS_DIR = FORGE_ROOT / "demo_artifacts" / "uploads" / "finance_v1"
NETWORK_REQUIRED_FIELDS = {"Proto", "Packets", "Bytes"}

Emit = Callable[[WorkflowEvent], None]

# 网络规则卡最多展示条数（golden 规则集较大，截断保证演示节奏）
NET_MAX_CARDS = 12
ENABLE_RULECARD_LLM = os.getenv("FORGE_RULECARD_LLM", "").lower() in {"1", "true", "yes", "on"}
NETWORK_UPLOAD_SUFFIXES = {".csv", ".json", ".txt"}
FINANCE_UPLOAD_SUFFIXES = {".csv", ".json", ".txt"}


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


def _network_vreport(rows: list[dict[str, Any]], data_path: str) -> ViolationReport:
    from forge.core.reporter import check_netflow_rows  # noqa: PLC0415

    violations = check_netflow_rows(rows)
    by_rule: dict[str, int] = {}
    for violation in violations:
        by_rule[violation.rule_id] = by_rule.get(violation.rule_id, 0) + 1
    bad_rows = {violation.row_index for violation in violations}
    total_rows = len(rows)
    satisfaction_rate = 1.0 if total_rows == 0 else 1.0 - (len(bad_rows) / total_rows)
    return ViolationReport(
        scenario="network_cidds",
        data_path=data_path,
        total_rows=total_rows,
        violations=violations,
        satisfaction_rate=satisfaction_rate,
        by_rule=by_rule,
    )


def _request_params(job: Any) -> dict[str, Any]:
    return dict(getattr(job, "request_params", None) or {})


def _job_sequence(job: Any) -> str:
    return str(getattr(job, "sequence", "") or "")


def _network_data_source_id(
    params: dict[str, Any],
    sequence: str,
    purpose: str,
) -> str | None:
    if purpose == "training":
        value = params.get("trainingDataSourceId")
        if value:
            return str(value)
        if sequence == "learn-network" and params.get("dataSourceId"):
            return str(params["dataSourceId"])
    if purpose == "validation":
        value = params.get("validationDataSourceId")
        if value:
            return str(value)
        if sequence in {"validate-network", "report-network"} and params.get("dataSourceId"):
            return str(params["dataSourceId"])
    return None


def _read_network_upload_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".json" or (suffix == ".txt" and text.lstrip().startswith(("{", "["))):
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("rows")
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise RuntimeError(f"network upload JSON must be a row list or object with rows: {path.name}")
        rows = [dict(row) for row in payload]
    else:
        reader = csv.DictReader(line for line in text.splitlines() if line.strip())
        rows = [
            {
                str(key).strip(): (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
                if key is not None
            }
            for row in reader
        ]
    if not rows:
        raise RuntimeError(f"network upload is empty or cannot be parsed: {path.name}")
    missing = NETWORK_REQUIRED_FIELDS - set(rows[0])
    if missing:
        raise RuntimeError(
            f"network upload missing required fields {', '.join(sorted(missing))}: {path.name}"
        )
    return rows


def _load_network_data_source(
    data_source_id: str | None,
    *,
    purpose: str,
) -> dict[str, Any] | None:
    if not data_source_id:
        return None
    from server.store import get_store                  # noqa: PLC0415

    store = get_store()
    meta = store.data_sources.get(data_source_id)
    if meta is None:
        raise RuntimeError(
            f"上传数据源 {data_source_id} 不存在，可能服务已重启，请重新上传。"
        )
    scenario = str(meta.get("scenario") or "")
    if scenario != "network_cidds":
        raise RuntimeError(
            f"上传数据源 {data_source_id} 属于 {scenario}，不能用于 network_cidds。"
        )
    raw_path = meta.get("path")
    if not raw_path:
        raise RuntimeError(f"上传数据源 {data_source_id} 没有可读取文件路径。")
    path = Path(str(raw_path)).resolve()
    uploads_root = NETWORK_UPLOADS_DIR.resolve()
    try:
        path.relative_to(uploads_root)
    except ValueError as exc:
        raise RuntimeError(
            f"上传数据源 {data_source_id} 路径越界，拒绝读取：{path}"
        ) from exc
    if path.suffix.lower() not in NETWORK_UPLOAD_SUFFIXES:
        raise RuntimeError(
            f"网络{purpose}仅支持 CSV、JSON、TXT 文件：{path.name}"
        )
    if not path.is_file():
        raise RuntimeError(
            f"上传数据源 {data_source_id} 文件不存在，请重新上传：{path.name}"
        )
    rows = _read_network_upload_rows(path)
    return {
        "id": data_source_id,
        "meta": meta,
        "path": path,
        "rows": rows,
        "filename": str(meta.get("filename") or path.name),
        "purpose": purpose,
    }


def _read_finance_upload_frame(path: Path):
    import pandas as pd  # noqa: PLC0415

    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".json" or (suffix == ".txt" and text.lstrip().startswith(("{", "["))):
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("rows")
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise RuntimeError(f"finance upload JSON must be a row list or object with rows: {path.name}")
        df = pd.DataFrame(payload)
    else:
        df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        raise RuntimeError(f"finance upload is empty or cannot be parsed: {path.name}")
    missing = [field for field in FIN_FIELDS if field not in df.columns]
    if missing:
        raise RuntimeError(
            f"finance upload missing required fields {', '.join(missing)}: {path.name}"
        )
    df = df[FIN_FIELDS].copy()
    numeric_fields = [field for field in FIN_FIELDS if field not in {"CompanyId", "Industry"}]
    for field in numeric_fields:
        df[field] = pd.to_numeric(df[field], errors="raise")
    return df


def _load_finance_data_source(
    data_source_id: str | None,
    *,
    purpose: str,
) -> dict[str, Any] | None:
    if not data_source_id:
        return None
    from server.store import get_store  # noqa: PLC0415

    store = get_store()
    meta = store.data_sources.get(data_source_id)
    if meta is None:
        raise RuntimeError(
            f"上传数据源 {data_source_id} 不存在，可能服务已重启，请重新上传。"
        )
    scenario = str(meta.get("scenario") or "")
    if scenario != "finance_v1":
        raise RuntimeError(
            f"上传数据源 {data_source_id} 属于 {scenario}，不能用于 finance_v1。"
        )
    raw_path = meta.get("path")
    if not raw_path:
        raise RuntimeError(f"上传数据源 {data_source_id} 没有可读取文件路径。")
    path = Path(str(raw_path)).resolve()
    uploads_root = FINANCE_UPLOADS_DIR.resolve()
    try:
        path.relative_to(uploads_root)
    except ValueError as exc:
        raise RuntimeError(
            f"上传数据源 {data_source_id} 路径越界，拒绝读取：{path}"
        ) from exc
    if path.suffix.lower() not in FINANCE_UPLOAD_SUFFIXES:
        raise RuntimeError(
            f"财务{purpose}仅支持 CSV、JSON、TXT 文件：{path.name}"
        )
    if not path.is_file():
        raise RuntimeError(
            f"上传数据源 {data_source_id} 文件不存在，请重新上传：{path.name}"
        )
    frame = _read_finance_upload_frame(path)
    return {
        "id": data_source_id,
        "meta": meta,
        "path": path,
        "frame": frame,
        "filename": str(meta.get("filename") or path.name),
        "purpose": purpose,
    }


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
    params = _request_params(job)
    finance_source = _load_finance_data_source(
        str(params.get("validationDataSourceId") or params.get("dataSourceId") or "")
        or None,
        purpose="核查/报告",
    )

    # -- upload：构造华信咨询待审资料包（确定性注入 F1–F4） --------------------
    if finance_source is not None:
        _ev(emit, "upload", "running",
            f"读取上传财务资料 {finance_source['filename']}…")
        df_faulty = finance_source["frame"]
        truth = None
        data_path = str(finance_source["path"])
        data_label = finance_source["filename"]
        _ev(emit, "upload", "done",
            f"上传资料已读取：{data_label}，{len(df_faulty)} 期报表，"
            f"dataSourceId={finance_source['id']}。")
    else:
        _ev(emit, "upload", "running", "未提供 dataSourceId，使用内置「华信咨询」待审资料包…")
        df_clean = build_clean_package()
        df_faulty, truth = inject_faults(df_clean)
        data_path = "华信咨询_待审资料包.csv"
        data_label = data_path
        _ev(emit, "upload", "done",
            f"内置资料包就绪：{len(df_faulty)} 期报表，附错误清单真值表"
            f"（{len(truth['faults'])} 项注入错误）。")

    # -- prepare ---------------------------------------------------------------
    _ev(emit, "prepare", "running", "解析字段 / 中文列名映射 / 按期排序…")
    df_faulty = df_faulty.sort_values("PeriodIndex").reset_index(drop=True)
    _ev(emit, "prepare", "done",
        f"预处理完成：{len(df_faulty.columns)} 个字段（含派生折叠字段），"
        f"数据源 {data_label}。")

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
    _ev(emit, "validate", "running", f"对 {data_label} 逐项核查勾稽关系…")
    validator = FinanceValidator()
    vreport = validator.validate(df_faulty, data_path)
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
    dual = reporter.make_dual(df_faulty, truth=truth, ruleset=ruleset,
                              data_path=data_path)
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
        "data_source": {
            "validation": {
                "id": finance_source["id"],
                "filename": finance_source["filename"],
            } if finance_source else None,
        },
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
    from forge.core.reporter import (  # noqa: PLC0415
        NET_RULE_TEXTS,
        DualReporter,
    )

    _ev(emit, "control", "running", "网络规则自发现任务开始编排。")
    params = _request_params(job)
    sequence = _job_sequence(job)
    training_source = _load_network_data_source(
        _network_data_source_id(params, sequence, "training"),
        purpose="规则学习",
    )
    validation_source = _load_network_data_source(
        _network_data_source_id(params, sequence, "validation"),
        purpose="核查/报告",
    )

    data_source_id = params.get("dataSourceId")
    used_ids = {
        source["id"]
        for source in (training_source, validation_source)
        if source is not None
    }
    if data_source_id and str(data_source_id) not in used_ids:
        _load_network_data_source(str(data_source_id), purpose="dataSourceId")

    upload_target = (
        training_source["filename"] if training_source
        else validation_source["filename"] if validation_source
        else "cidds_wk2_normal_10k.csv"
    )
    _ev(emit, "upload", "running", f"接收 {upload_target}…")
    if training_source:
        data_note = (
            f"自定义训练集就绪：{training_source['filename']}，"
            f"{len(training_source['rows'])} 条 NetFlow 记录，dataSourceId={training_source['id']}"
        )
    elif validation_source:
        data_note = (
            f"待核查资料就绪：{validation_source['filename']}，"
            f"{len(validation_source['rows'])} 条 NetFlow 记录，dataSourceId={validation_source['id']}"
        )
    else:
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
    if training_source is not None:
        if find_spec("netnomos") is None:
            _ev(emit, "learn", "blocked",
                "custom network learn requires NetNomos runtime; current environment has no netnomos module")
            raise RuntimeError(
                "自定义规则学习需要 NetNomos runtime；当前环境不可用，"
                "请改用内置数据或在宿主机安装 NetNomos 后重试。"
            )
        try:
            ruleset = engine.learn(training_source["path"])
            _ev(emit, "learn", "done",
                f"stage=learn processor=NetNomos hitting-set/Z3："
                f"基于自定义数据 {training_source['filename']} 学习完成 {len(ruleset.rules)} 条规则。")
        except Exception as exc:
            _ev(emit, "learn", "blocked", f"custom network learn failed: {exc}")
            raise RuntimeError(
                f"自定义训练数据规则学习失败：{training_source['filename']}：{exc}"
            ) from exc
    elif use_netnomos and find_spec("netnomos") is not None and CIDDS_TRAIN_CSV.exists():
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

    validation_violations = []
    vreport = None
    track_a_rows = None
    track_a_source_label = "裸模型生成"
    if validation_source is not None:
        _ev(emit, "validate", "running",
            f"对上传资料 {validation_source['filename']} 逐行核查 NetFlow 规则…")
        vreport = _network_vreport(validation_source["rows"], str(validation_source["path"]))
        validation_violations = vreport.violations
        _ev(emit, "validate", "done",
            f"核查完成：{len(validation_source['rows'])} 条记录，"
            f"命中 {len(validation_violations)} 处违规。")
        track_a_rows = validation_source["rows"]
        track_a_source_label = f"上传资料 {validation_source['filename']}"

    # -- report / diff --------------------------------------------------------------
    if track_a_rows is not None:
        a_track_note = f"A 轨使用上传资料 {len(track_a_rows)} 条 NetFlow"
    else:
        a_track_note = "A 轨裸模型生成 10 条 NetFlow"
    _ev(emit, "report", "running",
        f"stage=report processor=A轨裸模型+B轨约束：{a_track_note}…")
    _ev(emit, "report", "running",
        "stage=report processor=A轨裸模型+B轨约束：B 轨使用 LeJIT 约束生成，"
        "并做终检过滤/补采；若不达标则 job 失败暴露。")
    reporter = DualReporter(llm=llm)
    dual = reporter.make_dual_network(
        10,
        track_a_rows=track_a_rows,
        track_a_source_label=track_a_source_label,
    )
    _ev(emit, "report", "done",
        f"双轨生成完毕：A 轨 {len(dual.track_a.violations)} 条违规，"
        f"B 轨 {len(dual.track_b.violations)} 条违规。")
    _ev(emit, "diff", "done", "双轨 NetFlow 对比标红完成。")
    _ev(emit, "control", "done", "网络双轨产物归档完成。")
    return {
        "ruleset": ruleset,
        "cards": cards,
        "vreport": vreport,
        "dual": dual,
        "violations": validation_violations or dual.track_a.violations,
        "data_source": {
            "training": {
                "id": training_source["id"],
                "filename": training_source["filename"],
            } if training_source else None,
            "validation": {
                "id": validation_source["id"],
                "filename": validation_source["filename"],
            } if validation_source else None,
        },
    }


# ---------------------------------------------------------------------------
# 办公室趣味 demo：复用财务/网络规则资产，输出 6 agent 工作台状态
# ---------------------------------------------------------------------------

OFFICE_AGENT_META = [
    {
        "id": "supervisor",
        "code": "A",
        "name": "主管A",
        "role": "流程编排与监管",
        "status": "supervising",
        "description": "接入规则集，监管财务与网络两条业务流水线。",
        "color": "#2563eb",
    },
    {
        "id": "courier",
        "code": "B",
        "name": "快递B",
        "role": "资料接入与派送",
        "status": "delivering",
        "description": "接收用户上传资料，并把数据派送给分析与验证工位。",
        "color": "#f59e0b",
    },
    {
        "id": "analyst",
        "code": "C",
        "name": "员工C",
        "role": "规则学习",
        "status": "analyzing",
        "description": "从 NetNomos 归档规则与财务恒等式中整理候选约束。",
        "color": "#16a34a",
    },
    {
        "id": "validator",
        "code": "D",
        "name": "员工D",
        "role": "规则解释与核查",
        "status": "validating",
        "description": "把规则转成业务可读卡片，标注人工规则、自发现规则与疑似巧合。",
        "color": "#0891b2",
    },
    {
        "id": "plugin",
        "code": "E",
        "name": "员工E",
        "role": "插件/报告制品",
        "status": "building",
        "description": "生成双轨报告、diff 片段与演示制品预览。",
        "color": "#7c3aed",
    },
    {
        "id": "pm",
        "code": "F",
        "name": "员工F",
        "role": "RAG 与受控问答",
        "status": "reviewing",
        "description": "基于上传知识库与 B 轨白名单进行受约束回答。",
        "color": "#db2777",
    },
]


def _rule_to_office_item(rule: Rule, idx: int) -> dict[str, Any]:
    source = "learned" if rule.source == "learned" else "preset"
    return {
        "id": rule.rule_id or f"RULE-{idx:03d}",
        "text": rule.text or str(rule.formula),
        "type": rule.kind or "constraint",
        "enabled": rule.enabled,
        "source": source,
        "confidence": rule.confidence if rule.confidence is not None else rule.support,
        "coincidence": False,
    }


def _load_office_rules() -> tuple[RuleSet, list[dict[str, Any]]]:
    """Load lightweight finance/network rule groups without running training."""
    from forge.core.engine import ForgeRuleEngine          # noqa: PLC0415

    finance_engine = ForgeRuleEngine.from_scenario("finance_v1")
    finance_ruleset = finance_engine.add_manual_rules(
        RuleSet(scenario="finance_v1", rules=[]), FIN_MANUAL_RULES)

    network_engine = ForgeRuleEngine.from_scenario("network_cidds")
    network_ruleset = (
        network_engine.load_netnomos_rules(GOLDEN_CIDDS_RULES)
        if GOLDEN_CIDDS_RULES.exists()
        else RuleSet(scenario="network_cidds", rules=[])
    )

    office_rules = list(finance_ruleset.rules) + list(network_ruleset.rules[:NET_MAX_CARDS])
    office_ruleset = RuleSet(scenario="office_demo", rules=office_rules)
    groups = [
        {
            "id": "grp-finance",
            "name": "财务资料核查规则组",
            "domain": "财务",
            "discovered": False,
            "from": "forge/scenarios/finance_v1/manual_rules.json",
            "rules": [_rule_to_office_item(r, i) for i, r in enumerate(finance_ruleset.rules, 1)],
        },
        {
            "id": "grp-network",
            "name": "网络流量自发现规则组",
            "domain": "网络",
            "discovered": True,
            "from": str(GOLDEN_CIDDS_RULES),
            "rules": [_rule_to_office_item(r, i) for i, r in enumerate(network_ruleset.rules[:NET_MAX_CARDS], 1)],
        },
    ]
    return office_ruleset, groups


def _office_cards(ruleset: RuleSet) -> list[RuleCard]:
    cards: list[RuleCard] = []
    for rule in ruleset.rules[:18]:
        title = "自发现规则" if rule.source == "learned" else "人工/领域规则"
        cards.append(RuleCard(
            rule_id=rule.rule_id,
            title_zh=f"{title}：{rule.rule_id}",
            explanation_zh=rule.text or "该规则来自当前演示规则库，可用于办公室工作台的规则墙展示。",
            formula_text=rule.text or str(rule.formula),
            tags=[rule.kind or "constraint", rule.source],
            is_coincidence=False,
            citation="NetNomos Forge office_demo aggregation",
        ))
    return cards


def run_office_pipeline(job: Any, emit: Emit, llm=None,
                        use_netnomos: bool = False) -> dict[str, Any]:
    """Office control-room pipeline that exposes real backend state to the 3D UI."""
    _ev(emit, "control", "running", "办公室多智能体工作台开始编排。")
    _ev(emit, "upload", "running", "快递B读取当前财务/网络演示资料与用户上传记录。")

    store_sources = []
    try:
        from server.store import get_store                 # noqa: PLC0415
        store_sources = list(get_store().data_sources.values())
    except Exception:
        store_sources = []

    data_sources = [
        {
            "id": "finance-demo",
            "name": "huaxin_audit_package.csv",
            "kind": "csv",
            "meta": "财务待审资料包，含注入错误样例",
            "status": "已加载",
            "source": "preset",
        },
        {
            "id": "network-demo",
            "name": "netflow_rule_anomaly_upload.csv",
            "kind": "csv",
            "meta": "网络新规则核查上传样例",
            "status": "已加载",
            "source": "preset",
        },
    ]
    for i, meta in enumerate(store_sources[-6:], 1):
        filename = str(meta.get("filename") or meta.get("stored_filename") or f"uploaded-{i}")
        suffix = Path(filename).suffix.lower().lstrip(".")
        data_sources.append({
            "id": f"upload-{i}",
            "name": filename,
            "kind": suffix if suffix in {"csv", "pcap", "xlsx", "pdf"} else "csv",
            "meta": f"{meta.get('size', 0)} bytes · {meta.get('scenario', 'unknown')}",
            "status": "已加载",
            "source": "upload",
        })
    _ev(emit, "upload", "done", f"办公室资料池就绪：{len(data_sources)} 个资料源。")

    _ev(emit, "learn", "running", "员工C汇总财务人工规则与网络自发现规则。")
    ruleset, rule_groups = _load_office_rules()
    _ev(emit, "learn", "done",
        f"员工C完成规则汇总：财务 {len(rule_groups[0]['rules'])} 条，网络 {len(rule_groups[1]['rules'])} 条。")

    _ev(emit, "explain", "running", "员工D生成规则卡并区分人工规则与自发现规则。")
    cards = _office_cards(ruleset)
    _ev(emit, "explain", "done", f"员工D生成 {len(cards)} 张办公室规则卡。")

    _ev(emit, "report", "running", "员工E整理财务/网络双轨演示产物索引。")
    artifacts = [
        {
            "id": "art-finance",
            "title": "财务双轨报告摘要",
            "producer": "plugin",
            "kind": "双轨报告",
            "time": "实时",
            "preview": "A轨按上传资料直接撰写，B轨依据规则投影修正 COGS、资产负债、跨期滚动等字段。",
        },
        {
            "id": "art-network",
            "title": "网络规则自发现摘要",
            "producer": "validator",
            "kind": "规则卡",
            "time": "实时",
            "preview": "网络规则来自 CIDDS 10k 训练流量的 NetNomos 归档规则，办公室中标记为自发现规则组。",
        },
        {
            "id": "art-rag",
            "title": "F 受控问答说明",
            "producer": "pm",
            "kind": "对话留痕",
            "time": "实时",
            "preview": "F 通过 /api/chat/constrained 调用后端；若已有 B 轨报告，则用数值白名单标注未经核实数字。",
        },
    ]
    _ev(emit, "report", "done", f"员工E归档 {len(artifacts)} 个办公室演示产物。")
    _ev(emit, "chat", "done", "员工F已连接受规则约束问答接口。")
    _ev(emit, "control", "done", "办公室多智能体工作台后端状态已归档。")

    return {
        "ruleset": ruleset,
        "cards": cards,
        "office": {
            "agents": OFFICE_AGENT_META,
            "ruleGroups": rule_groups,
            "dataSources": data_sources,
            "artifacts": artifacts,
            "summary": {
                "scenario": "office_demo",
                "ruleGroupCount": len(rule_groups),
                "dataSourceCount": len(data_sources),
                "artifactCount": len(artifacts),
                "backend": "real",
            },
        },
    }


# Real office_demo composite pipeline.
def run_office_demo_pipeline(job: Any, emit: Emit, llm=None,
                             use_netnomos: bool = False) -> dict[str, Any]:
    """Build the office demo from real finance and network backend outputs."""
    from forge.scenarios.office_demo import build_office_state  # noqa: PLC0415

    office_events: list[WorkflowEvent] = []

    def office_emit(stage: str, status: str, desc: str) -> None:
        event = WorkflowEvent.make(stage, status, desc)
        office_events.append(event)
        emit(event)

    office_emit("control", "running", "office_demo orchestration started for six office agents.")
    office_emit("upload", "running", "Courier B registers finance CSV and CIDDS NetFlow sources.")
    finance = run_finance_pipeline(job, lambda _event: None, llm=llm,
                                   use_netnomos=use_netnomos)
    office_emit("upload", "done", "Finance source validated and queued for rule-card packaging.")
    office_emit("learn", "running", "Analyst C loads finance controls and network learned-rule archive.")
    network = run_network_pipeline(job, lambda _event: None, llm=llm,
                                   use_netnomos=use_netnomos)
    office_emit("learn", "done", "Finance and network rule libraries are ready for the office wall.")

    office_emit("explain", "running", "Validator D builds grouped rule cards for finance, network, and PM output constraints.")
    finance_ruleset: RuleSet = finance["ruleset"]
    network_ruleset: RuleSet = network["ruleset"]
    network_rules = network_ruleset.rules[:NET_MAX_CARDS]
    combined_ruleset = RuleSet(
        scenario="office_demo",
        rules=[*finance_ruleset.rules, *network_rules],
        rules_path="composite:finance_v1+network_cidds",
    )
    combined_cards = [*finance["cards"], *network["cards"]]
    office_emit("explain", "done",
                f"Validator D packaged {len(combined_cards)} rule cards across finance and network groups.")
    office_emit("validate", "done",
                f"Finance validation found {len(finance['vreport'].violations)} violations; network B-track remains constrained.")
    office_emit("report", "running", "Plugin E packages dual-track reports and UI artifacts.")
    office_state = build_office_state(
        finance=finance,
        network=network,
        combined_ruleset=combined_ruleset,
        combined_cards=combined_cards,
        events=office_events,
        request_params=getattr(job, "request_params", None),
    )
    office_emit("report", "done",
                f"Office artifacts ready: {len(office_state['artifacts'])} artifacts, "
                f"{len(office_state['dataSources'])} data sources.")
    office_emit("chat", "done", "PM F constrained chat context is ready.")
    office_emit("control", "done", "office_demo backend state is ready.")

    office_state = build_office_state(
        finance=finance,
        network=network,
        combined_ruleset=combined_ruleset,
        combined_cards=combined_cards,
        events=office_events,
        request_params=getattr(job, "request_params", None),
    )
    return {
        "ruleset": combined_ruleset,
        "cards": combined_cards,
        "vreport": finance["vreport"],
        "dual": finance["dual"],
        "finance": finance,
        "network": network,
        "office_state": office_state,
        "office": office_state,
        "agents": office_state["agents"],
        "ruleGroups": office_state["ruleGroups"],
        "dataSources": office_state["dataSources"],
        "artifacts": office_state["artifacts"],
        "workflowEvents": office_state["workflowEvents"],
    }


# 前端 MockSequenceId → (场景, 管线函数)
SEQUENCE_PIPELINES: dict[str, tuple[str, Callable[..., dict[str, Any]]]] = {
    "learn-finance": ("finance_v1", run_finance_pipeline),
    "validate-finance": ("finance_v1", run_finance_pipeline),
    "report-finance": ("finance_v1", run_finance_pipeline),
    "learn-network": ("network_cidds", run_network_pipeline),
    "validate-network": ("network_cidds", run_network_pipeline),
    "report-network": ("network_cidds", run_network_pipeline),
    "office-overview": ("office_demo", run_office_demo_pipeline),
    "learn-office": ("office_demo", run_office_demo_pipeline),
    "validate-office": ("office_demo", run_office_demo_pipeline),
    "report-office": ("office_demo", run_office_demo_pipeline),
}
