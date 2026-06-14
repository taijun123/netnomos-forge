"""Hitting-set 规则学习器。

这个学习器把“从数据中找规则”的问题转成 hitting set 枚举问题。

核心直觉：
1. projection 阶段已经生成了一批候选谓词；
2. 对每一行数据，找出这一行满足了哪些谓词，得到一个 evidence set；
3. 如果一个谓词集合能和每个 evidence set 至少相交一次，它就是 hitting set；
4. 极小 hitting set 表示“没有多余谓词”的覆盖组合；
5. 每个 hitting set 会转成一条析取规则，例如 `p1 OR p7 OR p12`。

这里的规则更像“覆盖式规则”：
- 它不是学习 `A -> B` 形式的因果或蕴含关系；
- 它学习的是一组谓词的析取，使其覆盖尽可能多的数据证据。

模块同时支持两套后端：
- Python 回溯实现：便于调试、测试和自定义 clock；
- pybind11/C++ 原生实现：用于更快地枚举 hitting sets。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import pickle
from pathlib import Path
import time
from typing import Any

import numpy as np
from tqdm.auto import tqdm

from netnomos.ast import BoolOr, Compare, Constant, Formula, SymbolRef, formula_to_dict, formula_to_string
from netnomos.dataset import PreparedDataset
from netnomos.logging_utils import get_logger
from netnomos.projection import GroundedPredicate
from netnomos.specs import HittingSetBackend
from netnomos.theory import evaluate_formula_df

log = get_logger("hittingset")

try:
    # 原生扩展是可选依赖。
    # 如果编译失败或没有安装，系统仍可回退到 Python 后端。
    from netnomos._hittingset_native import enumerate_hitting_sets as _enumerate_hitting_sets_native
except ImportError as exc:
    _enumerate_hitting_sets_native = None
    _NATIVE_IMPORT_ERROR = exc
else:
    _NATIVE_IMPORT_ERROR = None


@dataclass(slots=True)
class LearnedRule:
    """学习器输出的统一规则结构。

    无论规则来自 hitting-set 还是 tree learner，最终都统一成这个结构，
    方便 API、artifact、validate、interpret 等后续模块复用。
    """

    # 规则编号，例如 hs00000、tree00000。
    rule_id: str
    # 结构化公式 AST。
    formula: Formula
    # 可读展示文本。
    display: str
    # 规则在当前数据上的支持率。
    support: float
    # 来源元数据，例如 learner 类型、使用了哪些 predicate。
    source: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 rules.json 的字典。

        其中 `formula` 会用 AST 的结构化 JSON 表示，
        而不是只保存 `display` 字符串，这样以后可以重新加载继续做逻辑操作。
        """
        return {
            "rule_id": self.rule_id,
            "formula": formula_to_dict(self.formula),
            "display": self.display,
            "support": self.support,
            "source": self.source,
        }


class HittingSetLearner:
    """基于极小 hitting set 枚举的规则学习器。

    主要入口是 `fit()`：
    - 先构建或加载 evidence sets；
    - 再枚举极小 hitting sets；
    - 最后把每个 hitting set 转成 `LearnedRule`。
    """

    def __init__(
        self,
        max_clause_size: int = 4,
        max_rules: int = 250,
        stall_timeout: float | None = None,
        backend: HittingSetBackend | str = HittingSetBackend.AUTO,
        clock: Callable[[], float] | None = None,
    ):
        """初始化学习器参数与可选超时控制。

        参数含义：
        - `max_clause_size`：一条析取规则最多包含多少个谓词；
        - `max_rules`：最多返回多少条规则；
        - `stall_timeout`：如果长时间没有找到新规则，提前停止搜索；
        - `backend`：auto/native/python；
        - `clock`：测试用可注入时钟，方便稳定模拟超时。
        """
        if stall_timeout is not None and stall_timeout < 0:
            raise ValueError("stall_timeout must be non-negative when provided")
        self.max_clause_size = max_clause_size
        self.max_rules = max_rules
        self.stall_timeout = stall_timeout
        self.backend = HittingSetBackend(backend)
        self._has_custom_clock = clock is not None
        self._clock = clock or time.monotonic
        self.last_fit_metadata: dict[str, Any] = {}

    def fit(
        self,
        predicates: list[GroundedPredicate],
        prepared: PreparedDataset,
        evidence_cache_path: str | Path | None = None,
    ) -> list[LearnedRule]:
        """从谓词集合和准备后的数据集中学习规则。

        `predicates` 是 projection 阶段生成的候选谓词；
        `prepared` 是标准化数据；
        `evidence_cache_path` 可用于复用“每行满足哪些谓词”的中间结果，
        避免重复运行大量谓词求值。
        """
        evidence_sets, cache_metadata = self._load_or_build_evidence_sets(
            predicates,
            prepared,
            evidence_cache_path=evidence_cache_path,
        )
        covers, search_metadata = self.enumerate_minimal_hitting_sets(evidence_sets)
        rules: list[LearnedRule] = []
        for index, cover in enumerate(covers):
            # 一个 hitting set 对应一条“若若干谓词之一成立”的析取规则。
            # cover 中保存的是 predicate 下标，而不是 predicate_id 字符串。
            formulas = tuple(predicates[predicate_index].formula for predicate_index in sorted(cover))
            # 单谓词规则无需再包一层 BoolOr。
            formula = BoolOr(formulas) if len(formulas) > 1 else formulas[0]
            display = " OR ".join(predicates[predicate_index].display for predicate_index in sorted(cover))
            support = float(evaluate_formula_df(formula, prepared).mean())
            rules.append(LearnedRule(
                rule_id=f"hs{index:05d}",
                formula=formula,
                display=display,
                support=support,
                source={
                    "learner": "hitting-set",
                    "predicate_ids": [predicates[predicate_index].predicate_id for predicate_index in sorted(cover)],
                },
            ))
        pruned_rules = self.prune_tautologies(rules)
        if search_metadata["search_stopped_early"]:
            log.warning(
                "Stopping hitting-set search after %.2fs without a new rule; returning %d partial rules.",
                search_metadata.get("stall_elapsed_seconds") or 0.0,
                len(pruned_rules),
            )
        self.last_fit_metadata = {
            # metadata 会被 API 写入 fit_metadata/artifacts，
            # 方便用户知道是否命中缓存、使用哪个后端、是否提前停止。
            **cache_metadata,
            **search_metadata,
            "rule_count_before_prune": len(rules),
            "rule_count_after_prune": len(pruned_rules),
            "evidence_set_count": len(evidence_sets),
        }
        return pruned_rules

    def enumerate_minimal_hitting_sets(self, evidence_sets: list[set[int]]) -> tuple[list[set[int]], dict[str, Any]]:
        """枚举极小 hitting sets，并返回搜索元数据。

        该函数只负责“搜索 hitting sets”，不负责把结果转成 LearnedRule。
        根据配置和运行时环境，它会选择 native 或 python 后端。
        """
        resolved_backend = self._resolve_backend()
        if not evidence_sets:
            # 没有 evidence set 说明没有任何行满足任何谓词，无法学习覆盖规则。
            return [], {
                "hitting_set_backend_requested": self.backend.value,
                "hitting_set_backend_used": resolved_backend.value,
                "hitting_set_native_available": self.native_backend_available(),
                "search_stopped_early": False,
                "stop_reason": "complete",
                "stall_timeout_seconds": self.stall_timeout,
                "stall_elapsed_seconds": 0.0,
                "search_elapsed_seconds": 0.0,
            }
        progress = tqdm(
            total=self.max_rules,
            desc="Enumerating rules",
            unit=" rule",
            disable=None,
        )
        try:
            # native 和 python 后端返回统一结构，便于上层处理。
            if resolved_backend == HittingSetBackend.NATIVE:
                solutions, metadata = self._enumerate_minimal_hitting_sets_native(evidence_sets, progress)
            else:
                solutions, metadata = self._enumerate_minimal_hitting_sets_python(evidence_sets, progress)
        finally:
            progress.close()
        return solutions, {
            "hitting_set_backend_requested": self.backend.value,
            "hitting_set_backend_used": resolved_backend.value,
            "hitting_set_native_available": self.native_backend_available(),
            **metadata,
        }

    def _load_or_build_evidence_sets(
        self,
        predicates: list[GroundedPredicate],
        prepared: PreparedDataset,
        evidence_cache_path: str | Path | None = None,
    ) -> tuple[list[set[int]], dict[str, Any]]:
        """加载或构建证据集。

        证据集的第 i 项表示“第 i 行数据满足了哪些谓词”。
        这是 hitting-set 学习的核心输入。

        举例：
        - 第 0 行满足谓词 p1、p3，则 evidence_sets[0] = {1, 3}
        - 第 1 行满足谓词 p2、p3，则 evidence_sets[1] = {2, 3}
        hitting set {3} 就能命中所有 evidence set。
        """
        cache_path = Path(evidence_cache_path) if evidence_cache_path is not None else None
        if cache_path is not None and cache_path.exists():
            # 缓存文件使用 pickle，因为 evidence_sets 是 set[int] 列表，
            # 用二进制格式读写最直接。
            with cache_path.open("rb") as handle:
                payload = pickle.load(handle)
            evidence_sets = [set(entry) for entry in payload["evidence_sets"]]
            return evidence_sets, {
                "evidence_cache_hit": True,
                "evidence_cache_path": str(cache_path),
            }

        evidence_sets: list[set[int]] = [set() for _ in range(len(prepared.dataframe))]
        for predicate_index, predicate in enumerate(tqdm(
            predicates,
            total=len(predicates),
            desc="Building evidence sets",
            unit=" predicate",
            disable=None,
        )):
            # 对每个谓词在整张表上求值，找出满足它的行。
            sat = evaluate_formula_df(predicate.formula, prepared)
            rows = np.flatnonzero(sat.to_numpy())
            for row_index in rows.tolist():
                # 记录“该行被当前谓词命中”。
                evidence_sets[row_index].add(predicate_index)

        # 空证据行对 hitting-set 搜索没有贡献，可以直接丢弃。
        evidence_sets = [evidence for evidence in evidence_sets if evidence]
        if cache_path is not None:
            # 写缓存时把 set 排序成 list，提高可重复性，也便于未来排查。
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("wb") as handle:
                pickle.dump({
                    "evidence_sets": [sorted(entry) for entry in evidence_sets],
                    "row_count": len(prepared.dataframe),
                    "predicate_count": len(predicates),
                }, handle)
        return evidence_sets, {
            "evidence_cache_hit": False,
            "evidence_cache_path": str(cache_path) if cache_path is not None else None,
        }

    def prune_tautologies(self, rules: list[LearnedRule]) -> list[LearnedRule]:
        """剔除显然永真的析取规则。

        某些析取规则可能天然永真，例如：
        - `x = 1 OR x != 1`
        - `x > 5 OR x <= 5`
        - `x >= 5 OR x < 5`

        这类规则没有信息量，应从输出中剔除。
        当前实现只处理“同一字段与同一常量”的简单互补比较。
        """
        pruned: list[LearnedRule] = []
        for rule in rules:
            if not isinstance(rule.formula, BoolOr):
                pruned.append(rule)
                continue
            signatures: dict[tuple[str, Any], set[str]] = {}
            tautology = False
            for literal in rule.formula.values:
                # 只识别最简单的 field op constant 形式。
                if not isinstance(literal, Compare):
                    continue
                if not isinstance(literal.left, SymbolRef) or not isinstance(literal.right, Constant):
                    continue
                key = (literal.left.name, literal.right.value)
                seen = signatures.setdefault(key, set())
                seen.add(literal.op)
                # 同一字段/常量上出现互补操作符，即可判断为显然永真。
                if {"=", "!="} <= seen or {">", "<="} <= seen or {">=", "<"} <= seen:
                    tautology = True
                    break
            if not tautology:
                pruned.append(rule)
        return pruned

    @staticmethod
    def native_backend_available() -> bool:
        """当前环境是否成功编译并加载了原生后端。"""
        return _enumerate_hitting_sets_native is not None

    def _resolve_backend(self) -> HittingSetBackend:
        """根据请求和运行时条件决定使用哪个后端。

        AUTO 策略：
        - 如果注入了 custom clock，必须使用 Python 后端，因为 native 后端无法使用 Python 测试时钟；
        - 如果 native 可用，则优先 native；
        - 否则回退 Python。
        """
        if self.backend == HittingSetBackend.AUTO:
            if self._has_custom_clock:
                return HittingSetBackend.PYTHON
            if self.native_backend_available():
                return HittingSetBackend.NATIVE
            return HittingSetBackend.PYTHON
        if self.backend == HittingSetBackend.NATIVE and not self.native_backend_available():
            raise RuntimeError(
                "The native hitting-set backend is unavailable. Rebuild the project so the pybind11 "
                "extension is compiled, or use `--hittingset-backend python`."
            ) from _NATIVE_IMPORT_ERROR
        if self.backend == HittingSetBackend.NATIVE and self._has_custom_clock:
            raise RuntimeError("The native hitting-set backend does not support custom clocks.")
        return self.backend

    def _enumerate_minimal_hitting_sets_native(
        self,
        evidence_sets: list[set[int]],
        progress: tqdm[Any],
    ) -> tuple[list[set[int]], dict[str, Any]]:
        """调用 pybind11/C++ 原生后端枚举 hitting sets。

        C++ 后端返回 covers 和搜索元数据。
        Python 侧负责把 list[list[int]] 转回 list[set[int]]，保持与 Python 后端一致。
        """
        if _enumerate_hitting_sets_native is None:
            raise RuntimeError("Native hitting-set backend is unavailable.") from _NATIVE_IMPORT_ERROR

        def update_progress(count: int) -> None:
            # native 后端通过回调把当前找到的规则数量同步给 tqdm。
            progress.n = count
            progress.refresh()

        payload = _enumerate_hitting_sets_native(
            [sorted(evidence) for evidence in evidence_sets],
            self.max_clause_size,
            self.max_rules,
            -1.0 if self.stall_timeout is None else float(self.stall_timeout),
            update_progress,
        )
        return [set(entry) for entry in payload["covers"]], {
            "search_stopped_early": bool(payload["search_stopped_early"]),
            "stop_reason": str(payload["stop_reason"]),
            "stall_timeout_seconds": payload["stall_timeout_seconds"],
            "stall_elapsed_seconds": float(payload["stall_elapsed_seconds"]),
            "search_elapsed_seconds": float(payload["search_elapsed_seconds"]),
        }

    def _enumerate_minimal_hitting_sets_python(
        self,
        evidence_sets: list[set[int]],
        progress: tqdm[Any],
    ) -> tuple[list[set[int]], dict[str, Any]]:
        """纯 Python 版极小 hitting set 回溯搜索。

        搜索状态：
        - `chosen`：当前已经选择的谓词集合；
        - `covered`：这些谓词已经命中的 evidence set 下标集合；
        - `universe`：所有需要覆盖的 evidence set 下标。

        目标是找到所有极小 chosen，使得 covered == universe。
        """
        # 反向索引：predicate -> 它能覆盖哪些 evidence set。
        # 搜索时可以快速更新 covered。
        idx_by_pred: dict[int, set[int]] = {}
        for evidence_index, evidence in enumerate(evidence_sets):
            for predicate_index in evidence:
                idx_by_pred.setdefault(predicate_index, set()).add(evidence_index)
        universe = set(range(len(evidence_sets)))
        solutions: list[set[int]] = []
        start_time = self._clock()
        last_solution_time = start_time
        stopped_early = False
        hit_max_rules = False

        def has_subset(candidate: set[int]) -> bool:
            """若已存在更小解覆盖 candidate，则 candidate 不可能是极小解。"""
            return any(solution <= candidate for solution in solutions)

        def is_stalled() -> bool:
            """判断从上次找到新规则起是否已经超时。"""
            if self.stall_timeout is None:
                return False
            return (self._clock() - last_solution_time) >= self.stall_timeout

        def branch(chosen: set[int], covered: set[int]) -> None:
            """回溯搜索主函数。"""
            nonlocal hit_max_rules, last_solution_time, stopped_early
            if hit_max_rules or stopped_early:
                return
            if is_stalled():
                stopped_early = True
                return
            if len(solutions) >= self.max_rules:
                hit_max_rules = True
                return
            if covered == universe:
                # 当前 chosen 已经命中所有 evidence sets，是一个候选 hitting set。
                if not has_subset(chosen):
                    # 如果 chosen 比已有解更小，则删除被它支配的更大解，保持极小性。
                    solutions[:] = [solution for solution in solutions if not chosen < solution]
                    solutions.append(set(chosen))
                    last_solution_time = self._clock()
                    progress.n = len(solutions)
                    progress.refresh()
                return
            if len(chosen) >= self.max_clause_size:
                # 超过单条规则允许的最大谓词数，停止扩展。
                return
            uncovered = universe - covered
            # 选择候选最少的未覆盖 evidence 作为 pivot，可减少分支数。
            pivot = min(uncovered, key=lambda item: len(evidence_sets[item]))
            # 优先尝试覆盖更多未覆盖 evidence 的谓词，通常能更快找到小解。
            candidates = sorted(evidence_sets[pivot], key=lambda pred: len(idx_by_pred.get(pred, set()) & uncovered), reverse=True)
            for predicate_index in candidates:
                if hit_max_rules or stopped_early:
                    return
                if is_stalled():
                    stopped_early = True
                    return
                if predicate_index in chosen:
                    continue
                next_chosen = set(chosen)
                next_chosen.add(predicate_index)
                if has_subset(next_chosen):
                    continue
                branch(next_chosen, covered | idx_by_pred.get(predicate_index, set()))

        branch(set(), set())
        end_time = self._clock()
        if stopped_early:
            stop_reason = "stall-timeout"
        elif hit_max_rules:
            stop_reason = "max-rules"
        else:
            stop_reason = "complete"
        return solutions, {
            "search_stopped_early": stopped_early,
            "stop_reason": stop_reason,
            "stall_timeout_seconds": self.stall_timeout,
            "stall_elapsed_seconds": end_time - last_solution_time,
            "search_elapsed_seconds": end_time - start_time,
        }
