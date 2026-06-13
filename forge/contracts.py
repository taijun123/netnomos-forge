# -*- coding: utf-8 -*-
"""forge.contracts — netnomos-forge 全项目接口契约（v1，冻结）.

所有 Agent（Core-Dev / Finance-Dev / Server-Dev / Web-Dev）必须面向本文件开发：
- 数据结构以本文件 dataclass 为准；
- SSE 事件结构与 mult-agent-marvis/product/src/types/domain.ts 的 WorkflowEvent 对齐；
- REST 路径以 API_* 常量为准；
- 变更本文件需 Reviewer 批准（开发期由 Orchestrator 代行）。

本文件只依赖 Python 标准库，任何环境都可 import。
"""
from __future__ import annotations

import json
import time as _time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Protocol

CONTRACTS_VERSION = "1.0"

# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------

class Scenario(str, Enum):
    NETWORK_CIDDS = "network_cidds"   # CIDDS NetFlow（NetNomos 自带 10k 训练集）
    NETWORK_PCAP = "network_pcap"     # netflix/mawi pcap 演示
    FINANCE_V1 = "finance_v1"         # 合成财务报表 960 行


# 场景资源目录约定：forge/scenarios/<scenario>/
#   dataset_spec.json   NetNomos DatasetSpec
#   grammar_spec.json   NetNomos GrammarSpec（财务场景同样适用）
#   report_template.md  报告模板（正文仅允许 {{slot}} 槽位）
SCENARIO_DIR = Path(__file__).parent / "scenarios"


# ---------------------------------------------------------------------------
# 规则与规则集
# ---------------------------------------------------------------------------

RuleSource = Literal["learned", "manual"]

@dataclass
class Rule:
    """统一规则表示。formula 使用 NetNomos rules.json 内的结构化公式 dict。"""
    rule_id: str                       # 如 "N001" / "R01"
    formula: dict[str, Any]            # NetNomos 结构化逻辑公式（非自由文本）
    text: str                          # 人类可读公式，如 "Proto=UDP -> Flags=noflags"
    kind: str = ""                     # range/bound/implication/identity/ratio/...
    source: RuleSource = "learned"
    support: float | None = None
    confidence: float | None = None
    enabled: bool = True               # 规则库侧栏“人类开关”


@dataclass
class RuleSet:
    scenario: str
    rules: list[Rule]
    rules_path: str | None = None      # 落盘的 NetNomos 格式 rules.json
    run_dir: str | None = None         # NetNomos 学习产物目录
    created_at: float = field(default_factory=_time.time)

    def enabled_rules(self) -> list[Rule]:
        return [r for r in self.rules if r.enabled]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 校验结果
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    row_index: int                     # 数据行号（0 基；报告展示时 +1）
    rule_id: str
    rule_text: str
    fields: list[str]                  # 涉及字段
    observed: dict[str, Any]           # 实际值
    expected: str                      # 期望描述，如 "应为 2000（=10000+4000-12000）"
    message_zh: str                    # 中文说明，前端直接展示


@dataclass
class ViolationReport:
    scenario: str
    data_path: str
    total_rows: int
    violations: list[Violation]
    satisfaction_rate: float           # 1.0 表示零违规
    by_rule: dict[str, int] = field(default_factory=dict)  # rule_id -> 命中次数

    @property
    def ok(self) -> bool:
        return not self.violations


# ---------------------------------------------------------------------------
# 规则卡（LLM+RAG 解释产物）
# ---------------------------------------------------------------------------

@dataclass
class RuleCard:
    rule_id: str
    title_zh: str                      # 一句话标题
    explanation_zh: str                # 2-4 句中文解释（业务语言）
    formula_text: str
    tags: list[str] = field(default_factory=list)   # 如 ["协议蕴含", "物理上界"]
    is_coincidence: bool = False       # LLM 判定的疑似巧合规则（前端置灰）
    citation: str = ""                 # 论文/领域知识引用


# ---------------------------------------------------------------------------
# 双轨报告
# ---------------------------------------------------------------------------

Track = Literal["A", "B"]              # A=裸模型；B=NetNomos 约束

@dataclass
class TrackReport:
    track: Track
    markdown: str                      # 报告正文（B 轨为槽位回填后的最终稿）
    slots: dict[str, Any] = field(default_factory=dict)   # B 轨数值槽位
    violations: list[Violation] = field(default_factory=list)  # A 轨被标红的错误
    intervention_log: list[str] = field(default_factory=list)  # B 轨干预日志


@dataclass
class DualReport:
    scenario: str
    title: str
    track_a: TrackReport
    track_b: TrackReport
    diff_html: str = ""                # 标红对比 HTML 片段


# ---------------------------------------------------------------------------
# SSE 工作流事件（与 marvis WorkflowEvent 对齐）
# ---------------------------------------------------------------------------

AgentCode = Literal["A", "B", "C", "D", "E", "F"]
EventStatus = Literal["pending", "running", "done", "blocked"]

# 流水线阶段 → 演示 Agent 映射（marvis 办公室角色）
STAGE_AGENT: dict[str, AgentCode] = {
    "upload": "B",        # 快递B：数据搬运/解析
    "prepare": "B",
    "learn": "C",         # 员工C：规则生成
    "explain": "D",       # 员工D：规则解释
    "validate": "D",      # 员工D：规则验证
    "project": "E",       # 员工E：数值投影/修正
    "report": "E",        # 员工E：报告制作
    "diff": "E",
    "chat": "F",          # 产品经理F：受约束聊天
    "control": "A",       # 主管A：总控
}

@dataclass
class WorkflowEvent:
    id: str
    time: str                          # ISO8601
    agent: AgentCode
    stage: str                         # STAGE_AGENT 的 key
    status: EventStatus
    description: str

    @staticmethod
    def make(stage: str, status: EventStatus, description: str) -> "WorkflowEvent":
        return WorkflowEvent(
            id=uuid.uuid4().hex[:12],
            time=_time.strftime("%Y-%m-%dT%H:%M:%S"),
            agent=STAGE_AGENT.get(stage, "A"),
            stage=stage,
            status=status,
            description=description,
        )

    def to_sse(self) -> str:
        return f"event: workflow\ndata: {json.dumps(asdict(self), ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# REST 接口路径（沿用方案表 7）
# ---------------------------------------------------------------------------

API_RULESETS_UPLOAD = "/api/rulesets/upload"          # POST 上传/选择规则集与配置
API_DATA_SOURCES = "/api/data-sources"                # POST 上传 pcap/csv/xlsx，返回 dataSourceId
API_RULESETS_LEARN = "/api/rulesets/learn"            # POST 触发 learn
API_RULESET_CARDS = "/api/rulesets/{ruleset_id}/cards"  # GET 规则卡
API_REPORTS_GENERATE = "/api/reports/generate"        # POST 双轨报告
API_WORKFLOW_EVENTS = "/api/workflow/events/stream"   # GET SSE
API_CHAT_CONSTRAINED = "/api/chat/constrained"        # POST 受约束聊天


# ---------------------------------------------------------------------------
# LLM 路由
# ---------------------------------------------------------------------------

LLMRole = Literal[
    "induce",    # A 轨诱骗：本地 ollama qwen2.5（固定 seed/temperature）
    "draft",     # B 轨正文起草（槽位化）：ollama/codex
    "explain",   # 规则卡解释：codex 优先
]

# 默认模型路由（宿主机执行；沙箱内自动降级为 mock）
DEFAULT_LLM_ROUTING: dict[str, dict[str, Any]] = {
    "induce": {"backend": "ollama", "model": "qwen2.5:14b-instruct",
               "options": {"temperature": 0.2, "seed": 42}},
    "draft": {"backend": "ollama", "model": "qwen2.5:14b-instruct",
              "options": {"temperature": 0.3, "seed": 7}},
    "explain": {"backend": "codex", "model": "default", "options": {}},
}


class LLMClient(Protocol):
    """forge/core/llm.py 必须实现的协议。"""
    def complete(self, prompt: str, role: LLMRole, system: str | None = None) -> str: ...


# ---------------------------------------------------------------------------
# 引擎/生成器协议（Core-Dev 实现于 forge/core/engine.py、generator.py）
# ---------------------------------------------------------------------------

class RuleEngineAPI(Protocol):
    @classmethod
    def from_scenario(cls, scenario: str | Scenario, runs_dir: str | Path = "runs") -> "RuleEngineAPI": ...
    def learn(self, data_path: str | Path, learner: str = "hitting-set",
              limit: int | None = None) -> RuleSet: ...
    def validate(self, data_path: str | Path, rules: RuleSet | None = None) -> ViolationReport: ...
    def check(self, rules: RuleSet, assertion: str) -> bool: ...
    def explain(self, rules: RuleSet, llm: LLMClient | None = None,
                lang: str = "zh") -> list[RuleCard]: ...
    def add_manual_rules(self, rules: RuleSet, manual_path: str | Path) -> RuleSet: ...


class GeneratorAPI(Protocol):
    @classmethod
    def train(cls, scenario: str | Scenario, rules: RuleSet,
              base_model: str | None = None, **kw) -> "GeneratorAPI": ...
    def generate(self, n: int = 10) -> list[dict[str, Any]]: ...
    def complete(self, prefixes: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# 财务场景常量（Finance-Dev 实现 forge/scenarios/finance/）
# ---------------------------------------------------------------------------

FIN_INDUSTRIES = ["consulting", "retail", "manufacturing"]
FIN_COMPANIES_PER_INDUSTRY = 40
FIN_PERIODS = 8                        # 共 3*40*8 = 960 行
FIN_AMOUNT_UNIT = "千元"               # 全部金额为千元整数

# 字段英文规范名（中文经 source_name 映射，见 dataset_spec.json）
FIN_FIELDS = [
    "CompanyId", "Industry", "PeriodIndex",
    "Revenue", "COGS", "GrossProfit", "NetProfit", "Purchases",
    "Cash_Begin", "Cash_End",
    "Inventory_Begin", "Inventory_End",
    "AccountsReceivable", "OtherAssets",
    "TotalAssets", "TotalLiabilities", "TotalEquity",
    # 派生字段（把多元恒等式折叠成二元规则）
    "InventoryNetInflow",      # = Purchases - COGS = Inventory_End - Inventory_Begin
    "InventoryToAssetsBp",     # = Inventory_End / TotalAssets * 10000
    "ReceivableToRevenueBp",   # = AccountsReceivable / Revenue * 10000
]

# 错误注入编号（真值表 key）
FIN_FAULTS = ["F1", "F2a", "F2b", "F3", "F4"]

# 人工规则通道：必须保证存在的核心恒等式（学不出来时兜底注入）
FIN_CORE_RULES_ZH = {
    "R01": "Inventory_End = Inventory_Begin + Purchases - COGS（进销存勾稽）",
    "R02": "TotalAssets = TotalLiabilities + TotalEquity（资产负债配平）",
    "R03": "下期 Inventory_Begin = 本期 Inventory_End（跨期滚动）",
    "R04": "下期 Cash_Begin = 本期 Cash_End（现金跨期滚动）",
    "R05": "GrossProfit = Revenue - COGS（毛利恒等式）",
}
