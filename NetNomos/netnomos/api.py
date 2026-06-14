"""NetNomos 高层编程接口。

这个模块是整个项目最重要的“流程编排层”之一。
如果说：
- `dataset.py` 负责准备数据，
- `projection.py` 负责生成谓词，
- `learners/` 负责学习规则，
- `theory.py` 负责验证与蕴含推理，

那么这里负责把这些能力按正确顺序串起来，形成一个对外可调用的统一入口。

CLI 最终也是通过这里的 `NetNomosMiner` 串起整个流程。它封装了：
1. 数据准备；
2. 谓词生成；
3. 规则学习；
4. 工件写出；
5. 理论验证、解释和蕴含查询。

阅读顺序建议：
1. 先看 `MiningResult`，理解一次运行最终返回什么；
2. 再看 `NetNomosMiner.fit()`，这是完整挖掘流程的主干；
3. 然后看 `validate()` / `interpret()` / `entails()` 这些围绕最近一次运行结果的便捷方法；
4. 最后看缓存与工件落盘相关的私有辅助方法。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from netnomos.artifacts import ArtifactStore
from netnomos.ast import Formula, formula_from_dict, formula_to_dict
from netnomos.dataset import PreparedDataset, prepare_dataset
from netnomos.dsl import parse_formula
from netnomos.interpreter import interpret_formula
from netnomos.learners import EntropyTreeLearner, HittingSetLearner, LearnedRule
from netnomos.logging_utils import get_logger
from netnomos.projection import GroundedPredicate, generate_predicates
from netnomos.semantic_values import build_semantic_value_catalog
from netnomos.specs import (
    DatasetSpec,
    GrammarSpec,
    HittingSetBackend,
    LearnerKind,
    load_dataset_spec,
    load_grammar_spec,
)
from netnomos.theory import Theory

# api logger 用于报告高层流程中的警告信息，例如：
# - 用户给 tree learner 传了 hitting-set 专属参数；
# - 某些配置被忽略但不至于报错中止。
log = get_logger("api")


@dataclass(slots=True)
class MiningResult:
    """一次完整挖掘运行的结构化结果。

    这个对象不是简单的“规则列表”，而是一次学习任务的完整上下文快照。
    它包含：
    - 运行目录：方便去磁盘查看 artifacts
    - prepared：准备后的数据集
    - predicates：所有具体化后的候选谓词
    - interpreted_predicates：谓词的人类可读文本
    - rules：学习得到的规则对象
    - interpreted_rules：规则的人类可读文本
    - semantic_values：语义常量目录，如 p50 / top1 的原始值映射
    - fit_metadata：学习过程元数据，如缓存命中、后端类型、早停原因
    """

    run_dir: Path
    prepared: PreparedDataset
    predicates: list[GroundedPredicate]
    interpreted_predicates: list[str]
    rules: list[LearnedRule]
    interpreted_rules: list[str]
    semantic_values: dict[str, dict[str, dict[str, Any]]]
    fit_metadata: dict[str, Any]


class NetNomosMiner:
    """NetNomos 的统一高层入口。

    对外部调用者来说，这个类承担了“门面 / facade”角色：
    调用方不需要分别操作 dataset、projection、learner、theory 模块，
    只需要持有一个 `NetNomosMiner` 实例即可完成主要任务。

    它内部维护三类状态：
    1. `dataset_spec`：数据集配置
    2. `grammar_spec`：语法配置
    3. `last_result`：最近一次 `fit()` 的结果，便于后续直接 validate / interpret / entails
    """

    def __init__(self, dataset_spec: DatasetSpec, grammar_spec: GrammarSpec, runs_dir: str | Path = "runs"):
        """初始化 miner。

        参数说明：
        - `dataset_spec`：定义数据如何加载、解释、预处理
        - `grammar_spec`：定义允许搜索哪些谓词与规则复杂度
        - `runs_dir`：运行产物写入目录
        """

        self.dataset_spec = dataset_spec
        self.grammar_spec = grammar_spec
        self.runs_dir = Path(runs_dir)

        # 保存最近一次 fit() 的结果。
        # 这样像 validate() / interpret() / entails() 这类方法就可以在
        # “最近一次学习得到的理论”上直接继续工作。
        self.last_result: MiningResult | None = None

    @classmethod
    def from_files(
        cls,
        dataset_spec: str | Path,
        grammar_spec: str | Path,
        runs_dir: str | Path = "runs",
    ) -> "NetNomosMiner":
        """从 JSON 文件加载配置并构造 miner。

        这是 CLI 最常走的入口，因为命令行通常拿到的是配置文件路径而不是
        已经加载好的 Pydantic 对象。
        """

        return cls(
            dataset_spec=load_dataset_spec(dataset_spec),
            grammar_spec=load_grammar_spec(grammar_spec),
            runs_dir=runs_dir,
        )

    def prepare(self, input_path: str | Path | None = None, limit: int | None = None) -> PreparedDataset:
        """只执行数据准备阶段。

        这个方法是对 `prepare_dataset()` 的一层薄封装，主要作用是：
        - 自动带上当前 miner 绑定的 `dataset_spec`
        - 对外暴露一个和 `fit()` 风格一致的高层接口
        """

        return prepare_dataset(self.dataset_spec, input_path=input_path, limit=limit)

    def fit(
        self,
        input_path: str | Path | None = None,
        learner: LearnerKind | str = LearnerKind.HITTING_SET,
        limit: int | None = None,
        stall_timeout: float | None = None,
        hitting_set_backend: HittingSetBackend | str = HittingSetBackend.AUTO,
    ) -> MiningResult:
        """执行完整规则挖掘流程。

        这是整个类里最重要的方法，核心流程可以概括为：
        1. 准备数据
        2. 生成候选谓词
        3. 选择学习器并学习规则
        4. 生成语义常量目录与可读文本
        5. 把结果工件落盘
        6. 缓存到 `last_result`，并返回结构化结果

        参数说明：
        - `input_path`：可选地覆盖 dataset spec 中的默认输入路径
        - `learner`：选择 hitting-set 或 tree
        - `limit`：只加载前 N 行/包，常用于调试或冒烟测试
        - `stall_timeout`：hitting-set 搜索长时间无新规则时可提前停止
        - `hitting_set_backend`：hitting-set 的具体后端实现
        """

        # 第 1 步：准备数据。
        # prepare() 内部会做：
        # - 源类型识别
        # - CSV / PCAP 加载
        # - 预处理
        # - 字段筛选
        # - 窗口化
        # - 派生变量
        prepared = self.prepare(input_path=input_path, limit=limit)

        # 第 2 步：根据 grammar spec 把语法模板具体化为候选谓词。
        # 这些谓词是后续规则学习器的“基础原子单元”。
        predicates = generate_predicates(prepared, self.grammar_spec)

        # 统一把字符串 learner 转成枚举，便于后续分支判断与元数据输出。
        learner_kind = LearnerKind(learner)

        if learner_kind == LearnerKind.HITTING_SET:
            # hitting-set 学习器可以利用 evidence cache 来避免重复构建证据集。
            # 缓存键是“数据快照 + 谓词集合”的哈希，只要这两者语义不变，
            # 下次运行就能复用之前的证据集。
            evidence_cache_path = self._build_evidence_cache_path(input_path, limit, prepared, predicates)

            # 构造 hitting-set learner，并把 grammar 里的规则复杂度约束传进去。
            backend = HittingSetLearner(
                max_clause_size=self.grammar_spec.max_clause_size,
                max_rules=self.grammar_spec.max_rules,
                stall_timeout=stall_timeout,
                backend=hitting_set_backend,
            )

            # 真正规则学习在 learner 内部完成。
            rules = backend.fit(predicates, prepared, evidence_cache_path=evidence_cache_path)
        else:
            # tree learner 并不支持 hitting-set 专属参数。
            # 因此如果用户传了这些参数，这里记录 warning，但不报错。
            if stall_timeout is not None or HittingSetBackend(hitting_set_backend) != HittingSetBackend.AUTO:
                log.warning(
                    (
                        "Ignoring hitting-set specific options for learner '%s'; stall timeout and "
                        "hitting-set backend selection only apply to the hitting-set learner."
                    ),
                    learner_kind.value,
                )

            # tree learner 用 max_clause_size 映射为树深度上限。
            backend = EntropyTreeLearner(
                max_depth=self.grammar_spec.max_clause_size,
                max_rules=self.grammar_spec.max_rules,
            )
            rules = backend.fit(predicates, prepared)

        # learner 会把自己的运行元数据保存在 `last_fit_metadata` 中。
        # 这里统一读取出来，放入最终结果与 manifest。
        fit_metadata = getattr(backend, "last_fit_metadata", {})

        # 若当前不是 hitting-set learner，但用户仍提供了 hitting-set 专属选项，
        # 这里在元数据中显式记录“被忽略”的事实，便于复现实验和排查行为差异。
        if learner_kind != LearnerKind.HITTING_SET and (
            stall_timeout is not None or HittingSetBackend(hitting_set_backend) != HittingSetBackend.AUTO
        ):
            fit_metadata = {
                **fit_metadata,
                "stall_timeout_seconds": stall_timeout,
                "stall_timeout_ignored": stall_timeout is not None,
                "hitting_set_backend_requested": HittingSetBackend(hitting_set_backend).value,
                "hitting_set_backend_ignored": True,
            }

        # 第 3 步：从谓词来源信息里收集 profile / quantile / top-k 等语义常量。
        # 这会让后续解释文本更可读，例如把 25 显示成 p50。
        semantic_values = build_semantic_value_catalog(predicates)

        # 第 4 步：把谓词和规则都渲染成可读文本。
        # 注意：这里不是替代结构化对象，而是额外生成一层“面向人”的表示。
        interpreted_predicates = [
            interpret_formula(predicate.formula, prepared.field_specs, semantic_values)
            for predicate in predicates
        ]
        interpreted_rules = [
            interpret_formula(rule.formula, prepared.field_specs, semantic_values)
            for rule in rules
        ]

        # 第 5 步：创建新的运行目录。
        # 每次 fit() 都会产生独立的 artifacts 目录，便于保存完整实验痕迹。
        store = ArtifactStore.create(self.runs_dir, self.dataset_spec.name, self.grammar_spec.name)

        # 第 6 步：把本次运行的所有关键工件写到磁盘。
        self._write_artifacts(
            store,
            prepared,
            predicates,
            interpreted_predicates,
            rules,
            interpreted_rules,
            semantic_values,
            learner_kind,
            fit_metadata,
        )

        # 第 7 步：把所有内存中的关键信息收拢成一个统一结果对象。
        result = MiningResult(
            run_dir=store.root,
            prepared=prepared,
            predicates=predicates,
            interpreted_predicates=interpreted_predicates,
            rules=rules,
            interpreted_rules=interpreted_rules,
            semantic_values=semantic_values,
            fit_metadata=fit_metadata,
        )

        # 缓存最近一次结果，供后续 validate() / interpret() / entails() 直接复用。
        self.last_result = result
        return result

    def entails(self, query: str | Formula, rules: list[LearnedRule] | None = None) -> bool:
        """基于最近一次 `fit()` 的结果做蕴含查询。

        行为说明：
        - 若 `query` 是字符串，则先用 DSL 解析成 AST；
        - 若显式传入 `rules`，则在这组规则上做判断；
        - 否则默认使用最近一次 `fit()` 学到的规则。
        """

        if isinstance(query, str):
            query = parse_formula(query)

        formulas = [rule.formula for rule in (rules or self._require_last_result().rules)]
        prepared = self._require_last_result().prepared

        # Theory 负责把规则集合组织成可验证、可蕴含查询的逻辑理论对象。
        theory = Theory(formulas=formulas, fields=prepared.field_specs, context_families=prepared.context_families)
        return theory.entails(query)

    def validate(self, rules: list[LearnedRule] | None = None) -> dict[str, Any]:
        """基于最近一次 `fit()` 的结果验证规则满足率。

        返回值是一个摘要字典，通常包含：
        - 规则数量
        - 所有样本是否都满足
        - 平均满足率
        - 每条规则单独的满足率
        """

        result = self._require_last_result()
        formulas = [rule.formula for rule in (rules or result.rules)]
        theory = Theory(formulas=formulas, fields=result.prepared.field_specs, context_families=result.prepared.context_families)
        return theory.validate(result.prepared)

    def interpret(self, rules: list[LearnedRule] | None = None) -> list[str]:
        """基于最近一次 `fit()` 的结果解释规则文本。

        与 `validate()` 类似，如果没有显式传入规则，就默认解释最近一次学习出的规则。
        """

        result = self._require_last_result()
        return [
            interpret_formula(rule.formula, result.prepared.field_specs, result.semantic_values)
            for rule in (rules or result.rules)
        ]

    def validate_rules(
        self,
        rules: list[LearnedRule],
        input_path: str | Path | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """对外部提供的规则集合做独立验证。

        这类方法和 `validate()` 的差异在于：
        - 不依赖最近一次 `fit()`
        - 每次都会重新准备数据
        - 适合验证磁盘加载来的规则，或外部构造的规则对象
        """

        prepared = self.prepare(input_path=input_path, limit=limit)
        theory = Theory(
            formulas=[rule.formula for rule in rules],
            fields=prepared.field_specs,
            context_families=prepared.context_families,
        )
        return theory.validate(prepared)

    def entails_with_rules(
        self,
        query: str | Formula,
        rules: list[LearnedRule],
        input_path: str | Path | None = None,
        limit: int | None = None,
    ) -> bool:
        """对外部规则集合执行蕴含判断。

        这个方法适合“先从文件加载规则，再指定输入数据与查询公式”的场景。
        """

        if isinstance(query, str):
            query = parse_formula(query)
        prepared = self.prepare(input_path=input_path, limit=limit)
        theory = Theory(
            formulas=[rule.formula for rule in rules],
            fields=prepared.field_specs,
            context_families=prepared.context_families,
        )
        return theory.entails(query)

    def interpret_rules(
        self,
        rules: list[LearnedRule],
        input_path: str | Path | None = None,
        limit: int | None = None,
        semantic_values: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> list[str]:
        """对外部规则集合解释可读文本。

        这里之所以仍然需要准备数据，是因为解释时需要 `field_specs`，
        例如字段的 enum_labels、context_family 等信息都来自 prepared dataset。
        """

        prepared = self.prepare(input_path=input_path, limit=limit)
        return [interpret_formula(rule.formula, prepared.field_specs, semantic_values) for rule in rules]

    def load_semantic_values(self, path: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
        """从磁盘读取语义常量目录。"""

        return json.loads(Path(path).read_text())

    def load_semantic_values_for_rules(self, rules_path: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
        """尝试读取与规则文件同目录的 `semantic_values.json`。

        这是为了支持“解释已有规则工件”时恢复语义标签信息。
        若文件不存在，则返回空字典，调用方可以安全继续。
        """

        candidate = Path(rules_path).with_name("semantic_values.json")
        if candidate.exists():
            return self.load_semantic_values(candidate)
        return {}

    def load_rules(self, path: str | Path) -> list[LearnedRule]:
        """从 `rules.json` 工件恢复 `LearnedRule` 对象列表。

        注意这里恢复的是“结构化规则对象”，而不是只读取可读文本。
        因此后续仍然可以做：
        - validate
        - entails
        - interpret
        """

        import json

        raw = json.loads(Path(path).read_text())
        rules: list[LearnedRule] = []
        for item in raw:
            rules.append(LearnedRule(
                rule_id=item["rule_id"],
                formula=formula_from_dict(item["formula"]),
                display=item.get("display", ""),
                support=float(item.get("support", 0.0)),
                source=item.get("source", {}),
            ))
        return rules

    def _write_artifacts(
        self,
        store: ArtifactStore,
        prepared: PreparedDataset,
        predicates: list[GroundedPredicate],
        interpreted_predicates: list[str],
        rules: list[LearnedRule],
        interpreted_rules: list[str],
        semantic_values: dict[str, dict[str, dict[str, Any]]],
        learner_kind: LearnerKind,
        fit_metadata: dict[str, Any],
    ) -> None:
        """把本次运行的关键工件全部写入运行目录。

        这一步的设计目标是让一次实验可复现、可检查、可解释。
        因此保存的不只是最终规则，还包括：
        - 实际使用的配置
        - 准备后的字段元数据
        - 自动排除字段信息
        - 谓词列表
        - 语义常量目录
        - 运行摘要 manifest
        """

        # `dataset_spec.json`
        # 含义：本次运行真正使用的数据集配置快照。
        # 用途：保证实验可复现，后续查看 runs 目录时能知道数据是按什么 schema 加载的。
        store.write_json("dataset_spec.json", self.dataset_spec.model_dump(mode="json"))

        # `grammar_spec.json`
        # 含义：本次运行真正使用的语法配置快照。
        # 用途：说明谓词搜索空间、量词模板、最大规则规模等约束来自哪里。
        store.write_json("grammar_spec.json", self.grammar_spec.model_dump(mode="json"))

        # `fields.json`
        # 含义：准备后的字段元数据字典，键是字段名，值是 FieldSpec。
        # 这里保存的不是原始配置里的字段定义，而是 prepare 之后最终进入学习流程的字段定义。
        # 例如 context window 展开后的 *_ctx0 / *_ctx1 字段、自动补全的 domain 等信息都体现在这里。
        store.write_json("fields.json", {name: field.model_dump(mode="json") for name, field in prepared.field_specs.items()})

        # `derived_variables.json`
        # 含义：派生变量的来源描述，也就是 prepared.derived_provenance。
        # 用途：告诉用户某个派生字段是通过什么 operation、哪些输入字段计算出来的。
        store.write_json("derived_variables.json", prepared.derived_provenance)

        # `configured_exclude_fields.json`
        # 含义：由 dataset spec 中 `exclude_fields` 明确排除掉的字段列表。
        # 这类字段是“用户主动不想要”的，不是系统自动删掉的。
        store.write_json("configured_exclude_fields.json", prepared.configured_exclude_fields)

        # `excluded_fields.json`
        # 含义：系统在 prepare 阶段自动排除的字段及原因。
        # 典型原因包括：含 NaN、空字符串等，说明这些字段无法安全参与后续学习。
        store.write_json("excluded_fields.json", prepared.excluded_fields)

        # `semantic_values.json`
        # 含义：语义标签到原始值的映射目录。
        # 例如：
        # - p50 -> 25
        # - top1 -> "TCP"
        # 用途：后续解释规则时，可以把原始阈值显示成更有统计意义的标签。
        store.write_json("semantic_values.json", semantic_values)

        # `manifest.json`
        # 含义：本次运行的总摘要，适合快速浏览和自动化读取。
        # 下面每个字段的意义分别是：
        # - dataset：数据集逻辑名称
        # - grammar：语法逻辑名称
        # - learner：实际使用的学习器类型
        # - source_type：输入源类型，如 csv / pcap
        # - row_count：prepare 之后用于学习的样本行数
        # - configured_exclude_fields：配置中显式排除的字段
        # - auto_excluded_fields：系统自动排除的字段及原因
        # - excluded_fields：最终总共排除的字段名列表
        # - predicate_count：生成了多少个候选谓词
        # - rule_count：最终学习得到多少条规则
        # - fit_metadata：学习过程元数据，如缓存命中、后端类型、早停原因等
        store.write_json("manifest.json", {
            "dataset": self.dataset_spec.name,
            "grammar": self.grammar_spec.name,
            "learner": learner_kind.value,
            "source_type": prepared.source_type.value,
            "row_count": len(prepared.dataframe),
            "configured_exclude_fields": prepared.configured_exclude_fields,
            "auto_excluded_fields": prepared.excluded_fields,
            "excluded_fields": prepared.effective_excluded_fields,
            "predicate_count": len(predicates),
            "rule_count": len(rules),
            "fit_metadata": fit_metadata,
        })

        # `predicates.jsonl`
        # 含义：候选谓词的逐行结构化记录。
        # 之所以用 JSONL 而不是单个巨大 JSON 数组，是因为：
        # - 谓词列表可能非常大
        # - JSONL 更适合逐行流式处理和命令行工具分析
        # 每一行记录中的字段含义：
        # - predicate_id：谓词编号
        # - display：谓词的原始显示文本
        # - support：该谓词在 prepared dataframe 上的满足率
        # - formula：谓词对应的结构化 AST 字典
        # - source：该谓词是由哪个模板、哪些字段/常量具体化出来的来源信息
        store.write_jsonl("predicates.jsonl", [{
            "predicate_id": predicate.predicate_id,
            "display": predicate.display,
            "support": predicate.support,
            "formula": formula_to_dict(predicate.formula),
            "source": predicate.source,
        } for predicate in predicates])

        # `interpreted_predicates.clj`
        # 含义：候选谓词的人类可读文本版本，每行一个谓词。
        # 这里会优先使用 semantic_values 和 enum_labels，把规则写得更适合人读。
        store.write_text("interpreted_predicates.clj", "\n".join(interpreted_predicates))

        # `rules.json`
        # 含义：最终学习得到的规则对象列表，是最核心的结构化产物之一。
        # 每条规则通常包含：
        # - rule_id：规则编号
        # - formula：规则 AST
        # - display：规则显示文本
        # - support：规则满足率
        # - source：规则来源元数据，例如使用了哪些 predicate_id
        store.write_json("rules.json", [rule.to_dict() for rule in rules])

        # `interpreted_rules.clj`
        # 含义：最终规则的人类可读文本版本，每行一条规则。
        # 这个文件通常是人工阅读最频繁的工件之一，因为它比 rules.json 更直观。
        store.write_text("interpreted_rules.clj", "\n".join(interpreted_rules))

    def _require_last_result(self) -> MiningResult:
        """确保当前 miner 已经执行过至少一次 `fit()`。

        这个检查专门服务于那些默认依赖“最近一次运行结果”的方法，
        比如：
        - validate()
        - interpret()
        - entails()
        """

        if self.last_result is None:
            raise RuntimeError("No result available. Run fit() first.")
        return self.last_result

    def _build_evidence_cache_path(
        self,
        input_path: str | Path | None,
        limit: int | None,
        prepared: PreparedDataset,
        predicates: list[GroundedPredicate],
    ) -> Path:
        """根据缓存键返回 evidence cache 文件路径。

        逻辑分三步：
        1. 构造缓存键；
        2. 去索引文件中查是否已有对应缓存；
        3. 若命中则返回原路径；若未命中则分配新路径并登记到索引。
        """

        cache_key = self._build_evidence_cache_key(input_path, limit, prepared, predicates)
        cache_dir = self.runs_dir / ".cache" / "evidence"
        index_path = cache_dir / "index.json"
        index = self._load_evidence_cache_index(index_path)
        filename = index.get(cache_key)
        if filename is not None:
            cache_path = cache_dir / filename
            if cache_path.exists():
                return cache_path

            # 如果索引里有记录，但实际文件已经不存在，说明缓存状态不一致。
            # 这里直接清掉脏索引，再走新路径分配逻辑。
            index.pop(cache_key, None)

        cache_path = self._allocate_evidence_cache_path(cache_dir)
        index[cache_key] = cache_path.name
        self._write_evidence_cache_index(index_path, index)
        return cache_path

    def _build_evidence_cache_key(
        self,
        input_path: str | Path | None,
        limit: int | None,
        prepared: PreparedDataset,
        predicates: list[GroundedPredicate],
    ) -> str:
        """构造 evidence cache 的稳定哈希键。

        目标是尽量保证：
        只要“语义输入”不变，就能复用缓存；
        只要“数据内容、准备结果或谓词集合”发生变化，就会得到新键。

        当前纳入哈希的内容包括：
        - 输入文件路径、大小、修改时间
        - limit 参数
        - 准备后数据的列结构与字段定义
        - 派生变量来源信息
        - 谓词显示文本与公式结构
        """

        source_path = Path(input_path or self.dataset_spec.source.path or "")
        source_meta: dict[str, Any] = {
            "limit": limit,
        }
        if source_path.exists():
            stat = source_path.stat()
            source_meta |= {
                "path": str(source_path.resolve()),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        payload = {
            "cache_version": 1,
            "source": source_meta,
            "prepared": {
                "row_count": len(prepared.dataframe),
                "columns": list(prepared.dataframe.columns),
                "field_specs": {
                    name: field.model_dump(mode="json")
                    for name, field in prepared.field_specs.items()
                },
                "derived_provenance": prepared.derived_provenance,
            },
            "predicates": [
                {
                    "display": predicate.display,
                    "formula": formula_to_dict(predicate.formula),
                }
                for predicate in predicates
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def _allocate_evidence_cache_path(self, cache_dir: Path) -> Path:
        """为新的 evidence cache 分配一个不冲突的文件路径。

        文件名格式是：
        `<dataset_name>_<timestamp>.pkl`

        若同一秒内已存在同名文件，则自动追加 `_2`、`_3` 等后缀。
        """

        cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%y%m%d-%H%M%S")
        candidate = cache_dir / f"{self.dataset_spec.name}_{stamp}.pkl"
        if not candidate.exists():
            return candidate
        suffix = 2
        while True:
            candidate = cache_dir / f"{self.dataset_spec.name}_{stamp}_{suffix}.pkl"
            if not candidate.exists():
                return candidate
            suffix += 1

    def _load_evidence_cache_index(self, index_path: Path) -> dict[str, str]:
        """读取 evidence cache 索引文件。

        若索引文件不存在，则返回空字典，表示当前没有任何已登记缓存。
        """

        if not index_path.exists():
            return {}
        payload = json.loads(index_path.read_text())
        entries = payload.get("entries", {})
        return {
            str(key): str(value)
            for key, value in entries.items()
        }

    def _write_evidence_cache_index(self, index_path: Path, entries: dict[str, str]) -> None:
        """把 evidence cache 索引写回磁盘。

        索引文件用于维护：
        `缓存键 -> 缓存文件名`
        的映射关系。
        """

        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps({
            "version": 1,
            "entries": entries,
        }, indent=2, sort_keys=True))
