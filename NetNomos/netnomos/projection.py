"""谓词投影与实例化。

这个模块位于 NetNomos 的“配置语法 -> 候选谓词”转换环节。

可以把它理解成一个“规则候选生成器”：
1. `specs.py` 负责定义 `GrammarSpec`、谓词模板、字段选择器、常量选择器等配置结构；
2. `dataset.py` 负责把原始数据整理成 `PreparedDataset`，里面包含 DataFrame、字段元数据、值目录和上下文字段族；
3. 本模块读取 `PreparedDataset + GrammarSpec`，把抽象模板真正展开成一批可计算的 `GroundedPredicate`；
4. 每个 `GroundedPredicate` 都包含一棵 AST 公式、可读展示文本、支持率和来源元数据；
5. 后续 learner 会基于这些候选谓词继续学习规则。

这里的“投影 / projection”不是机器学习里的降维投影，而是指：
- 把 grammar 中的抽象模板投影到当前数据集的具体字段、常量和上下文窗口上；
- 把 `forall/exists` 这类量词模板投影成当前有限窗口字段上的普通公式。

本文件的主线阅读顺序建议：
1. `generate_predicates()`：总入口，串起普通谓词、算术项谓词和量词谓词；
2. `generate_terms()`：把字段、常量、乘法项、加法项展开成可比较的表达式项；
3. `select_fields()` / `select_constants()`：根据配置选择字段和常量；
4. `compatible_*()`：过滤语义上不合理的比较组合；
5. `project_quantified_family()`：把量词模板变成有限 AST 公式。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import pandas as pd
from tqdm.auto import tqdm

from netnomos.ast import BinaryTerm, BoolAnd, BoolOr, Compare, Constant, Formula, FuncCall, SymbolRef, formula_to_string
from netnomos.dataset import PreparedDataset
from netnomos.semantic_values import quantile_label
from netnomos.specs import (
    Comparator,
    ConstantKind,
    ConstantSelectorSpec,
    FieldRole,
    FieldSpec,
    GrammarSpec,
    PredicateTermKind,
    QuantifierTemplateSpec,
    TermTemplateSpec,
    ValueType,
    VariableSelectorSpec,
)
from netnomos.theory import evaluate_formula_df


@dataclass(slots=True)
class GroundedPredicate:
    """已经具体化完成、可直接评估的谓词。

    “Grounded” 的意思是：它不再只是 grammar 里的抽象模板，而是已经绑定到了
    当前数据集中的具体字段、具体常量和具体操作符。

    例如 grammar 里可能只有一个抽象模板：
    - `numeric_field >= profile_quantile`

    投影后会变成很多具体谓词：
    - `frame.len >= 60`
    - `tcp.window_size >= 8192`
    - `ip.ttl >= 64`

    这些具体谓词可以直接交给 `evaluate_formula_df()` 在 DataFrame 上逐行求值。
    """

    # 谓词编号，生成顺序稳定后形如 p00000、p00001，便于规则和 artifact 引用。
    predicate_id: str
    # 结构化 AST 公式，例如 Compare(">=", SymbolRef("frame.len"), Constant(60))。
    formula: Formula
    # 面向用户或 artifact 的可读表达式；默认来自 formula_to_string()。
    display: str
    # 支持率：该谓词在当前数据集中为 True 的行占比。
    support: float
    # 来源元数据：记录来自哪个模板、哪个字段、哪个常量，便于解释和回溯。
    source: dict[str, Any]


@dataclass(slots=True)
class GeneratedTerm:
    """由项模板展开出的中间结果。

    除了表达式本身，还携带可比较性、字段来源、值类型等元信息，
    以便后续筛除语义上不合理的候选。

    “term / 项”是比谓词更小的表达式单元，可以出现在比较符左右两侧。
    例如下面这些都是 term：
    - 字段项：`Bytes`
    - 常量项：`100`
    - 乘法项：`Packets * 65535`
    - 加法项：`tcp.seq + tcp.len`

    生成 term 时必须同时记录它的语义属性，否则后续会生成很多荒谬比较，
    例如把字节长度和时间戳直接比较。
    """

    # AST 表达式节点，可直接作为 Compare(lhs, rhs) 的一侧。
    expr: Any
    # 人类可读展示文本，例如 "Bytes + Header"。
    display: str
    # 这个项引用到的字段名集合；常量项没有字段引用，因此为空元组。
    field_names: tuple[str, ...]
    # 是否引用了真实数据字段。常量项为 False，字段/算术项通常为 True。
    has_field_reference: bool
    # 是否是可以做大小比较的有序数值项。
    ordered_numeric: bool
    # 数值语义组，例如 size/count/time/sequence；用于避免跨语义比较。
    comparison_group: str | None
    # 项的值类型，用来判断比较兼容性。
    value_type: ValueType
    # 来源元数据，后续会写入 GroundedPredicate.source。
    source: dict[str, Any]


@dataclass(slots=True)
class SelectedConstant:
    """常量选择器选出的单个常量及其可选语义标签。

    这个类本身不负责“计算常量”或“给字段赋值”，它只是一个轻量数据容器。
    真正的赋值逻辑发生在下面两个函数中：
    - `select_constants()`：为普通字段选择常量；
    - `select_quantifier_constants()`：为上下文字段族选择常量。

    这两个函数会根据 `ConstantSelectorSpec.mode` 不同，构造不同来源的
    `SelectedConstant(value=..., label=...)`。

    常量可能来自多种来源：
    - explicit：配置中直接写死的值；
    - field_constants：字段元数据中声明的常量；
    - domain：字段值域；
    - profile：从当前数据分布中统计出来的分位数或 top-k。

    `label` 用来保留 profile 常量的语义来源，例如 p50、top1。
    后续解释阶段可以把“64”说明成“ip.ttl 的 p50”，而不是一个孤立数字。
    """

    # 实际参与 AST 比较的常量值。
    # 例如 explicit/domain/field_constants 会直接把配置值放到这里；
    # profile 数值字段会把分位数计算结果放到这里；
    # profile 非数值字段会把 top-k 高频值放到这里。
    value: Any
    # 可选语义标签，例如 p50、p95、top1。
    # 普通 explicit/domain/field_constants 常量通常没有标签，因此为 None；
    # profile 常量会带标签，供 interpreter 把原始值解释回 p50/top1。
    label: str | None


def generate_predicates(prepared: PreparedDataset, grammar: GrammarSpec) -> list[GroundedPredicate]:
    """根据语法配置生成所有候选谓词，并计算支持率。

    这是本模块的总入口，输入来自两个上游：
    - `prepared`：由 `dataset.prepare_dataset()` 得到，提供数据表、字段元数据和值目录；
    - `grammar`：由 `GrammarSpec` 表示，提供“允许生成哪些谓词”的模板。

    输出是一批 `GroundedPredicate`，每个谓词都已经：
    - 绑定具体字段/常量/上下文字段族；
    - 构造成 AST 公式；
    - 在当前 DataFrame 上计算过 support。

    生成过程分三大类：
    1. term-comparison：左右两侧是 term，可支持字段、常量、乘法、加法等算术项；
    2. field-field / field-constant：旧版或简单模板，直接做字段-字段或字段-常量比较；
    3. quantifier：把 forall/exists 上下文窗口模板投影成有限公式。
    """
    # candidates 用公式字符串作为 key 去重。
    # value 保存三样东西：
    # - Formula：真正可求值的 AST
    # - display：可读表达式
    # - source：来源元数据
    #
    # 先收集到 dict 而不是 list，是因为不同模板路径可能生成同一个公式。
    candidates: dict[str, tuple[Formula, str, dict[str, Any]]] = {}
    for template in grammar.predicate_templates:
        # 新版模板可以直接声明 lhs_term / rhs_term。
        # 这种模式比旧版 lhs/rhs_field/rhs_constant 更通用，因为 term 可以是：
        # - 字段
        # - 常量
        # - 字段 * 常量
        # - 字段 + 字段
        # - 字段 + 常量
        if template.lhs_term is not None or template.rhs_term is not None:
            # 算术模板需要先把左右两侧都实例化为“项”，再做笛卡尔组合。
            lhs_terms = generate_terms(prepared, template.lhs_term or TermTemplateSpec(kind=PredicateTermKind.FIELD, field=template.lhs))
            rhs_terms = generate_terms(
                prepared,
                template.rhs_term or build_legacy_rhs_term(template),
            )
            for lhs_term in lhs_terms:
                for rhs_term in rhs_terms:
                    # 如果模板不允许同字段比较，就过滤掉左右两侧引用字段有交集的组合。
                    # 这不只处理 `x == x`，也处理 `x + y` 与 `x` 这种共享字段的算术项。
                    if (not template.allow_same_field) and set(lhs_term.field_names) & set(rhs_term.field_names):
                        continue
                    # 可比较性检查很重要，用来阻止 Bytes <= Duration 这类语义错误组合。
                    if not compatible_terms(lhs_term, rhs_term, template.operators):
                        continue
                    for op in template.operators:
                        # 把左右 term 和操作符组装成比较公式。
                        # 例如 Compare(">=", SymbolRef("Bytes"), Constant(100))。
                        formula = Compare(op.value, lhs_term.expr, rhs_term.expr)
                        append_candidate(candidates, formula, {
                            "kind": "term-comparison",
                            "template": template.name,
                            "lhs_term": lhs_term.source,
                            "rhs_term": rhs_term.source,
                            "semantic_constants": [
                                *lhs_term.source.get("semantic_constants", []),
                                *rhs_term.source.get("semantic_constants", []),
                            ],
                        })
            continue
        # 走到这里说明当前模板没有使用新版 term 结构，
        # 因此使用传统字段选择器作为左侧。
        lhs_fields = select_fields(prepared, template.lhs)
        if template.rhs_field is not None:
            # 字段-字段谓词：
            # 从 lhs selector 和 rhs selector 各自选出字段，然后做笛卡尔组合。
            # 例如 lhs=[tcp.seq], rhs=[tcp.ack]，operators=[<=]，
            # 会生成 tcp.seq <= tcp.ack。
            rhs_fields = select_fields(prepared, template.rhs_field)
            for lhs in lhs_fields:
                for rhs in rhs_fields:
                    if lhs == rhs and not template.allow_same_field:
                        continue
                    # 字段级兼容性比 term 兼容性简单：
                    # - 大小比较要求两边都是同语义组的有序数值字段；
                    # - 等值比较允许同类型，或 categorical/string 之间比较。
                    if not compatible_fields(prepared.field_specs[lhs], prepared.field_specs[rhs], template.operators):
                        continue
                    for op in template.operators:
                        formula = Compare(op.value, SymbolRef(lhs), SymbolRef(rhs))
                        append_candidate(candidates, formula, {
                            "kind": "field-field",
                            "template": template.name,
                            "lhs": lhs,
                            "rhs": rhs,
                            "semantic_constants": [],
                        })
        if template.rhs_constant is not None:
            # 字段-常量谓词：
            # 先按 lhs selector 选字段，再按 rhs_constant selector 为每个字段选常量。
            # 常量来源可能是 explicit/domain/profile/top-k/field_constants。
            for lhs in lhs_fields:
                field = prepared.field_specs[lhs]
                for constant in select_constants(prepared, lhs, field, template.rhs_constant):
                    # 对大小比较来说，字段必须是有序数值字段，常量不能是字符串。
                    # 对等值/不等值比较来说，兼容性更宽松。
                    if not compatible_constant(field, constant.value, template.operators):
                        continue
                    for op in template.operators:
                        formula = Compare(op.value, SymbolRef(lhs), Constant(constant.value))
                        append_candidate(candidates, formula, {
                            "kind": "field-constant",
                            "template": template.name,
                            "lhs": lhs,
                            "constant": constant.value,
                            "semantic_constants": build_semantic_entries("field", lhs, constant),
                        })
    for template in grammar.quantifier_templates:
        # 量词模板不是直接保留 ForAll/Exists，而是投影成有限聚合形式。
        # 这里的量词只作用于当前数据里已经展开好的上下文字段族。
        # 例如 family `tcp.seq` 可能包含：
        # - tcp.seq_ctx0
        # - tcp.seq_ctx1
        # - tcp.seq_ctx2
        families = select_context_families(prepared, template)
        for family_name, family_fields in families.items():
            # 量词常量的统计范围不是单个字段，而是整个 family 的所有窗口列。
            # 例如 p50 会基于 tcp.seq_ctx0/1/2 合并后的分布计算。
            constants = select_quantifier_constants(prepared, family_fields, template.constant)
            for constant in constants:
                for op in template.operators:
                    formula, display = project_quantified_family(family_name, family_fields, template, op, constant)
                    append_candidate(candidates, formula, {
                        "kind": "quantifier",
                        "template": template.name,
                        "family": family_name,
                        "fields": family_fields,
                        "constant": constant.value,
                        "quantifier": template.quantifier,
                        "semantic_constants": build_semantic_entries("family", family_name, constant),
                    }, display=display)
    predicates: list[GroundedPredicate] = []
    # 排序保证输出稳定：同一份输入和配置下，谓词编号 p00000/p00001 不随 dict 插入路径波动。
    ordered_candidates = sorted(candidates.values(), key=lambda item: item[1])
    for formula, display, source in tqdm(
        ordered_candidates,
        desc="Evaluating predicate support",
        unit=" predicate",
        disable=None,
    ):
        # evaluate_formula_df 返回每一行的布尔结果。
        # mean() 会把 True 当作 1、False 当作 0，因此得到该谓词在数据上的支持率。
        support = float(evaluate_formula_df(formula, prepared).mean())
        predicates.append(GroundedPredicate(
            predicate_id=f"p{len(predicates):05d}",
            formula=formula,
            display=display,
            support=support,
            source=source,
        ))
    return predicates


def append_candidate(
    candidates: dict[str, tuple[Formula, str, dict[str, Any]]],
    formula: Formula,
    source: dict[str, Any],
    display: str | None = None,
) -> None:
    """按字符串签名去重，避免不同模板路径生成同一个公式。

    为什么要去重：
    - 一个谓词可能被多个模板同时生成；
    - 同一个模板中不同选择路径也可能落到同一个公式；
    - learner 只需要看到一次这个候选，否则会重复计算支持率并污染输出。

    这里用 `formula_to_string()` 作为稳定签名，而不是直接用 AST 对象身份。
    """
    key = formula_to_string(formula)
    if key in candidates:
        # 已存在则直接跳过，保留第一次出现时记录的 source。
        return
    candidates[key] = (formula, display or key, source)


def build_legacy_rhs_term(template: Any) -> TermTemplateSpec:
    """把旧版 rhs_field / rhs_constant 配置兼容转换为 rhs_term。

    早期 grammar 写法把右侧拆成两个字段：
    - `rhs_field`：右侧是字段；
    - `rhs_constant`：右侧是常量。

    新版 term 模板把这些都统一成 `rhs_term`：
    - field term
    - constant term
    - scalar term
    - addition term

    这个函数让旧配置继续可用，同时让后续逻辑只处理统一的 TermTemplateSpec。
    """
    if template.rhs_field is not None:
        return TermTemplateSpec(kind=PredicateTermKind.FIELD, field=template.rhs_field)
    if template.rhs_constant is not None:
        return TermTemplateSpec(kind=PredicateTermKind.CONSTANT, constant=template.rhs_constant)
    raise ValueError(f"Predicate template {template.name} must define a right-hand side")


def generate_terms(prepared: PreparedDataset, template: TermTemplateSpec) -> list[GeneratedTerm]:
    """把项模板展开成具体项。

    例如：
    - field -> Bytes
    - scalar -> Packets * 65535
    - addition -> Bytes + Header

    这个函数只生成“比较符左右两侧的表达式项”，还不会形成完整谓词。
    完整谓词会在 `generate_predicates()` 中用 `Compare(op, lhs_term, rhs_term)` 组装。

    返回值里的 `GeneratedTerm` 不只是 AST 表达式，还包含类型、字段来源和语义组。
    这些元信息会被 `compatible_terms()` 用来过滤不合理组合。
    """
    if template.kind == PredicateTermKind.FIELD:
        # FIELD：字段项。
        #
        # 如果 template.field 没有显式给选择器，则使用空 VariableSelectorSpec，
        # 表示从 prepared.field_specs 中选择所有可用字段。
        selector = template.field or VariableSelectorSpec()
        return [
            GeneratedTerm(
                # SymbolRef 表示“引用 DataFrame 中某一列”。
                expr=SymbolRef(name),
                display=name,
                field_names=(name,),
                has_field_reference=True,
                ordered_numeric=is_ordered_numeric_field(prepared.field_specs[name]),
                comparison_group=numeric_comparison_group(prepared.field_specs[name]),
                value_type=prepared.field_specs[name].value_type or ValueType.STRING,
                source={"kind": "field", "field": name, "semantic_constants": []},
            )
            for name in select_fields(prepared, selector)
        ]
    if template.kind == PredicateTermKind.CONSTANT:
        # CONSTANT：常量项。
        #
        # 这里目前只允许 explicit 常量，因为一个不依附字段的常量项没有上下文，
        # 无法合理使用 domain/profile/top-k 这类依赖字段分布的选择模式。
        selector = template.constant or ConstantSelectorSpec(mode="explicit")
        if selector.mode != "explicit":
            raise ValueError("Constant term templates currently require mode='explicit'")
        terms: list[GeneratedTerm] = []
        for value in selector.values:
            terms.append(GeneratedTerm(
                expr=Constant(value),
                display=str(value),
                field_names=(),
                has_field_reference=False,
                ordered_numeric=False,
                comparison_group=None,
                value_type=infer_constant_value_type(value),
                source={"kind": "constant", "value": value, "semantic_constants": []},
            ))
        return terms
    if template.kind == PredicateTermKind.SCALAR:
        # SCALAR：字段乘以常量。
        #
        # 典型用途是构造“缩放后的字段表达式”，例如：
        # - window_size_value * scale_factor
        # - packet_count * 65535
        #
        # 这种项必须同时配置字段选择器和常量选择器。
        if template.field is None or template.constant is None:
            raise ValueError("Scalar term templates require both `field` and `constant`")
        terms: list[GeneratedTerm] = []
        for field_name in select_fields(prepared, template.field):
            field = prepared.field_specs[field_name]
            # 只有有序数值字段才能参与乘法项。
            # 字符串、类别字段、枚举编码字段都不适合做数值缩放。
            if not is_ordered_numeric_field(field):
                continue
            comparison_group = numeric_comparison_group(field)
            for value in select_constants(prepared, field_name, field, template.constant):
                # 字符串常量不能作为乘法因子。
                if isinstance(value.value, str):
                    continue
                # int * real 结果应视为 real；int * int 仍为 int。
                value_type = combine_numeric_types(field.value_type, infer_constant_value_type(value.value))
                terms.append(GeneratedTerm(
                    expr=BinaryTerm("*", SymbolRef(field_name), Constant(value.value)),
                    display=f"{field_name} * {value.value}",
                    field_names=(field_name,),
                    has_field_reference=True,
                    ordered_numeric=True,
                    comparison_group=comparison_group,
                    value_type=value_type,
                    source={
                        "kind": "scalar",
                        "field": field_name,
                        "constant": value.value,
                        # 如果常量来自 profile，例如 p50，需要把语义标签保留下来。
                        "semantic_constants": build_semantic_entries("field", field_name, value),
                    },
                ))
        return terms
    if template.kind == PredicateTermKind.ADDITION:
        # ADDITION：字段 + 字段，或字段 + 常量。
        #
        # 加法项比普通字段比较更危险，因为只有某些语义组合才合理。
        # 例如 size + size 仍可视为 size；sequence + size 在本项目里可视为 sequence；
        # 但 time + size 一般没有明确含义，因此会被过滤。
        if template.field is None:
            raise ValueError("Addition term templates require `field`")
        terms: list[GeneratedTerm] = []
        left_fields = select_fields(prepared, template.field)
        if template.other_field is not None:
            # 字段 + 字段。
            right_fields = select_fields(prepared, template.other_field)
            for left_name in left_fields:
                left_field = prepared.field_specs[left_name]
                if not is_ordered_numeric_field(left_field):
                    continue
                left_group = numeric_comparison_group(left_field)
                for right_name in right_fields:
                    # 默认不允许 x + x 这种同字段组合，除非模板显式允许。
                    if left_name == right_name and not template.allow_same_field:
                        continue
                    right_field = prepared.field_specs[right_name]
                    if not is_ordered_numeric_field(right_field):
                        continue
                    # 判断两个字段相加后还能不能归到某个可比较语义组。
                    addition_group = addition_comparison_group(left_field, right_field)
                    if addition_group is None:
                        continue
                    terms.append(GeneratedTerm(
                        expr=BinaryTerm("+", SymbolRef(left_name), SymbolRef(right_name)),
                        display=f"{left_name} + {right_name}",
                        field_names=(left_name, right_name),
                        has_field_reference=True,
                        ordered_numeric=True,
                        comparison_group=addition_group,
                        value_type=combine_numeric_types(left_field.value_type, right_field.value_type),
                        source={
                            "kind": "addition",
                            "left_field": left_name,
                            "right_field": right_name,
                            "semantic_constants": [],
                        },
                    ))
        if template.constant is not None:
            # 字段 + 常量。
            # 常见用途是表达偏移量，例如 seq + tcp.len。
            for left_name in left_fields:
                left_field = prepared.field_specs[left_name]
                if not is_ordered_numeric_field(left_field):
                    continue
                comparison_group = numeric_comparison_group(left_field)
                for value in select_constants(prepared, left_name, left_field, template.constant):
                    if isinstance(value.value, str):
                        continue
                    terms.append(GeneratedTerm(
                        expr=BinaryTerm("+", SymbolRef(left_name), Constant(value.value)),
                        display=f"{left_name} + {value.value}",
                        field_names=(left_name,),
                        has_field_reference=True,
                        ordered_numeric=True,
                        comparison_group=comparison_group,
                        value_type=combine_numeric_types(left_field.value_type, infer_constant_value_type(value.value)),
                        source={
                            "kind": "addition",
                            "left_field": left_name,
                            "constant": value.value,
                            "semantic_constants": build_semantic_entries("field", left_name, value),
                        },
                    ))
        return terms
    raise ValueError(f"Unsupported term template kind: {template.kind}")


def select_fields(prepared: PreparedDataset, selector: VariableSelectorSpec) -> list[str]:
    """根据变量选择器从 `prepared.field_specs` 中筛字段。

    `VariableSelectorSpec` 可以理解为 grammar 里的“字段查询条件”。
    它不会直接读取 DataFrame 值，而是基于字段元数据做筛选，例如：
    - 按字段名白名单选择；
    - 按正则匹配字段名；
    - 按 ValueType 选择整数/实数/字符串/类别字段；
    - 按 FieldRole 选择 size/count/time/window 等语义角色；
    - 只选派生字段或排除派生字段；
    - 只选上下文窗口字段或排除窗口字段。

    返回顺序遵循输入字段顺序，便于生成稳定的谓词编号。
    """
    # 如果 selector.names 为空，默认从全部字段开始筛。
    names = selector.names or list(prepared.field_specs)
    if selector.regex is not None:
        # regex 是对字段名做 search，而不是 fullmatch。
        # 因此 `"tcp\\."` 可以匹配所有包含 tcp. 前缀的字段。
        pattern = re.compile(selector.regex)
        names = [name for name in names if pattern.search(name)]
    # 去掉数据集中不存在的字段，以及 selector.exclude 显式排除的字段。
    names = [name for name in names if name in prepared.field_specs and name not in selector.exclude]
    selected: list[str] = []
    for name in names:
        field = prepared.field_specs[name]
        # 按值类型筛选，例如只保留 INTEGER/REAL。
        if selector.types and field.value_type not in selector.types:
            continue
        # 按语义角色筛选。
        # 只要字段角色和 selector.roles 有交集即可通过。
        if selector.roles and not set(selector.roles).intersection(field.roles):
            continue
        # derived_only=True：只要派生字段；
        # derived_only=False：排除派生字段；
        # derived_only=None：不限制。
        if selector.derived_only is True and FieldRole.DERIVED not in field.roles:
            continue
        if selector.derived_only is False and FieldRole.DERIVED in field.roles:
            continue
        # 限定某个上下文字段族，例如只选 tcp.seq 这个 family 下的 ctx0/ctx1/ctx2。
        if selector.context_family is not None and field.context_family != selector.context_family:
            continue
        # window_only=True：只选上下文窗口字段；
        # window_only=False：排除上下文窗口字段；
        # window_only=None：不限制。
        if selector.window_only is True and field.context_family is None:
            continue
        if selector.window_only is False and field.context_family is not None:
            continue
        selected.append(name)
    return selected


def compatible_fields(lhs: FieldSpec, rhs: FieldSpec, ops: list[Comparator]) -> bool:
    """判断两个字段能否参与某一类比较。

    这一步是字段-字段谓词的语义防线。

    对大小比较：
    - 两边必须都是有序数值字段；
    - 两边必须属于同一个语义比较组，例如 size 和 size、time 和 time。

    对等值/不等值比较：
    - 同类型字段可以比较；
    - categorical 与 string 也允许互相比较，因为类别值常以字符串形式出现。
    """
    if any(op in {Comparator.GT, Comparator.GE, Comparator.LT, Comparator.LE} for op in ops):
        return are_numeric_fields_comparable(lhs, rhs)
    return lhs.value_type == rhs.value_type or {lhs.value_type, rhs.value_type} <= {ValueType.CATEGORICAL, ValueType.STRING}


def compatible_terms(lhs: GeneratedTerm, rhs: GeneratedTerm, ops: list[Comparator]) -> bool:
    """判断两个具体项能否比较。

    这里比字段比较更严格，因为项可能是算术表达式。

    例如：
    - `tcp.seq + tcp.len <= tcp.ack` 可能合理，因为 sequence + size 可以仍视为 sequence；
    - `frame.time_epoch + frame.len <= ip.ttl` 就不合理，因为 time/size/ttl 不在同一比较语义里；
    - `protocol > 3` 不合理，因为 protocol 是类别/字符串语义。
    """
    if any(op in {Comparator.GT, Comparator.GE, Comparator.LT, Comparator.LE} for op in ops):
        # 大小比较首先要求两边值类型都是数值。
        if lhs.value_type not in {ValueType.INTEGER, ValueType.REAL} or rhs.value_type not in {ValueType.INTEGER, ValueType.REAL}:
            return False
        if lhs.has_field_reference and rhs.has_field_reference:
            # scalar 项是字段乘常量。
            # 只要两边都仍然是有序数值项，就允许比较；这里不强制 comparison_group 相等，
            # 因为缩放常用于做单位换算或协议公式表达。
            if lhs.source.get("kind") == "scalar" or rhs.source.get("kind") == "scalar":
                return lhs.ordered_numeric and rhs.ordered_numeric
            # 两边都引用字段时，必须同属一个比较语义组。
            return (
                lhs.ordered_numeric
                and rhs.ordered_numeric
                and lhs.comparison_group is not None
                and lhs.comparison_group == rhs.comparison_group
            )
        # 一边是字段/表达式，一边是纯常量时，只要求字段侧是有序数值项。
        if lhs.has_field_reference:
            return lhs.ordered_numeric
        if rhs.has_field_reference:
            return rhs.ordered_numeric
        # 两边都是纯常量时，数值类型已经通过，可以比较。
        return True
    # 等值/不等值比较相对宽松。
    if lhs.value_type == rhs.value_type:
        if lhs.value_type in {ValueType.INTEGER, ValueType.REAL} and lhs.has_field_reference and rhs.has_field_reference:
            if lhs.ordered_numeric and rhs.ordered_numeric:
                if lhs.source.get("kind") == "scalar" or rhs.source.get("kind") == "scalar":
                    return True
                return lhs.comparison_group is not None and lhs.comparison_group == rhs.comparison_group
        return True
    # int 与 real 允许互相做等值/不等值比较。
    if lhs.value_type in {ValueType.INTEGER, ValueType.REAL} and rhs.value_type in {ValueType.INTEGER, ValueType.REAL}:
        return True
    # categorical 与 string 允许互相比较，因为类别值常常以字符串表示。
    return {lhs.value_type, rhs.value_type} <= {ValueType.CATEGORICAL, ValueType.STRING}


def compatible_constant(field: FieldSpec, constant: Any, ops: list[Comparator]) -> bool:
    """判断某字段与某常量在给定比较操作下是否兼容。

    字段-常量比较的规则比字段-字段简单：
    - 大小比较：字段必须是有序数值字段，常量不能是字符串；
    - 等值/不等值比较：默认允许，因为类别字段、字符串字段、布尔字段都常与常量做相等判断。
    """
    if any(op in {Comparator.GT, Comparator.GE, Comparator.LT, Comparator.LE} for op in ops):
        return is_ordered_numeric_field(field) and not isinstance(constant, str)
    return True


def select_constants(
    prepared: PreparedDataset,
    field_name: str,
    field: FieldSpec,
    selector: ConstantSelectorSpec,
) -> list[SelectedConstant]:
    """为某个字段选择可用于比较的常量。

    常量选择由 `ConstantSelectorSpec.mode` 决定：

    - explicit：
      直接使用配置里的 `values`。

    - field_constants：
      使用 `FieldSpec.constants` 里为该字段声明的常量。
      可通过 `selector.kinds` 限制常量类型，例如只取 assignment 常量或 semantic 常量。

    - domain：
      使用字段的显式 domain；如果没有 domain，则回退到 `prepared.value_catalog`。
      这通常用于类别/字符串/布尔字段枚举所有可见值。

    - profile：
      代码没有显式写 `elif selector.mode == "profile"`，而是通过前面几个 mode
      都不命中后的默认分支处理。数值字段取 quantiles；非数值字段取 top-k 高频值。
    """
    if selector.mode == "explicit":
        # 显式常量没有额外语义标签。
        return [SelectedConstant(value=value, label=None) for value in selector.values]
    if selector.mode == "field_constants":
        values: list[SelectedConstant] = []
        allowed_kinds = set(selector.kinds)
        for constant_spec in field.constants:
            # selector.kinds 为空表示不过滤常量类型。
            if allowed_kinds and constant_spec.kind not in allowed_kinds:
                continue
            for value in constant_spec.values:
                values.append(SelectedConstant(value=value, label=None))
        return dedupe_selected_constants(values)
    if selector.mode == "domain":
        # field.domain 优先，因为它是人工配置的值域；
        # 如果没有人工 domain，则使用 dataset 阶段从数据里建立的 value_catalog。
        return [SelectedConstant(value=value, label=None) for value in list(field.domain or prepared.value_catalog.get(field_name, []))]
    series = prepared.dataframe[field_name].dropna()
    if field.value_type in {ValueType.INTEGER, ValueType.REAL}:
        values: list[SelectedConstant] = []
        for quantile in selector.quantiles:
            # 数值 profile 常量来自分位数，例如 0.5 -> p50。
            raw_value = series.quantile(quantile)
            # 如果字段声明为 INTEGER，则把 pandas 算出的分位数四舍五入回整数。
            value = int(round(raw_value)) if field.value_type == ValueType.INTEGER else raw_value
            values.append(SelectedConstant(value=value, label=quantile_label(quantile)))
        return dedupe_selected_constants(values)
    # 非数值字段 profile 常量来自出现频率最高的 top_k 个值。
    return [
        SelectedConstant(value=value, label=f"top{index}")
        for index, value in enumerate(series.value_counts().head(selector.top_k).index.tolist(), start=1)
    ]


def select_quantifier_constants(
    prepared: PreparedDataset,
    field_names: list[str],
    selector: ConstantSelectorSpec,
) -> list[SelectedConstant]:
    """为量词字段族选择常量，统计范围覆盖整个上下文族。

    普通字段常量选择只看单列；量词模板面对的是一个上下文字段族。
    例如 family `tcp.seq` 可能包含：
    - `tcp.seq_ctx0`
    - `tcp.seq_ctx1`
    - `tcp.seq_ctx2`

    如果要生成 `forall k: tcp.seq[k] >= p50`，
    p50 应该基于整个 family 的所有窗口值计算，而不是只基于某一个 ctx 列。
    """
    if selector.mode == "explicit":
        return [SelectedConstant(value=value, label=None) for value in selector.values]
    # 把同一个上下文 family 下的所有列纵向拼接成一个 Series。
    # 这样 profile/domain 统计看到的是整个窗口族的值分布。
    series = pd.concat([prepared.dataframe[field] for field in field_names], axis=0).dropna()
    if selector.mode == "domain":
        # 对量词来说，domain 直接从 family 的所有实际值中去重得到。
        # 这里没有使用单个 FieldSpec.domain，因为一个 family 可能包含多个窗口列。
        return [SelectedConstant(value=value, label=None) for value in sorted(series.drop_duplicates().tolist())]
    if pd.api.types.is_numeric_dtype(series):
        values: list[SelectedConstant] = []
        for quantile in selector.quantiles:
            raw_value = series.quantile(quantile)
            value = int(round(raw_value)) if pd.api.types.is_integer_dtype(series) else raw_value
            values.append(SelectedConstant(value=value, label=quantile_label(quantile)))
        return dedupe_selected_constants(values)
    # 非数值上下文字段族使用全 family 的 top-k 高频值。
    return [
        SelectedConstant(value=value, label=f"top{index}")
        for index, value in enumerate(series.value_counts().head(selector.top_k).index.tolist(), start=1)
    ]


def infer_constant_value_type(value: Any) -> ValueType:
    """根据 Python 字面量推断常量类型。

    这主要服务于 term 兼容性判断。
    注意 bool 在 Python 中是 int 的子类，所以必须先判断 bool，再判断 int。
    """
    if isinstance(value, bool):
        return ValueType.BOOLEAN
    if isinstance(value, int):
        return ValueType.INTEGER
    if isinstance(value, float):
        return ValueType.REAL
    return ValueType.STRING


def combine_numeric_types(lhs: ValueType | None, rhs: ValueType | None) -> ValueType:
    """合并两个数值类型。

    规则很简单：
    - 只要任一侧是 REAL，结果就是 REAL；
    - 否则认为结果仍是 INTEGER。

    用于 `field * constant` 或 `field + constant/field` 这类算术项的类型推断。
    """
    if ValueType.REAL in {lhs, rhs}:
        return ValueType.REAL
    return ValueType.INTEGER


def dedupe_selected_constants(values: list[SelectedConstant]) -> list[SelectedConstant]:
    """保持原顺序去重常量。

    分位数或字段常量可能产生重复值。
    例如 p25、p50、p75 在小样本数据中可能都等于同一个数字。
    如果不去重，会生成重复谓词。

    使用 `repr(item.value)` 做 key，是为了区分某些字符串/数字显示相近但类型不同的值。
    """
    seen: set[str] = set()
    deduped: list[SelectedConstant] = []
    for item in values:
        key = repr(item.value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def build_semantic_entries(scope_kind: str, scope_name: str, constant: SelectedConstant) -> list[dict[str, Any]]:
    """把语义常量打包进 source 元数据，供后续解释阶段回溯。

    只有带 label 的常量才需要写入 semantic entries。
    例如：
    - p50 / p95 这类分位数常量；
    - top1 / top2 这类高频类别常量。

    普通 explicit 常量没有额外语义来源，返回空列表即可。
    """
    if not constant.label:
        return []
    return [{
        "scope_kind": scope_kind,
        "scope_name": scope_name,
        "label": constant.label,
        "value": constant.value,
    }]


def is_ordered_numeric_field(field: FieldSpec) -> bool:
    """判断字段是否适合参与有序数值比较。

    不是所有 INTEGER/REAL 都适合做 `>`、`<`：
    - 如果字段有 `enum_labels`，它可能只是类别编码，例如 1=TCP、2=UDP；
    - 如果字段 constants 中存在 ASSIGNMENT 常量，也暗示该数字可能是枚举赋值；
    - 这类字段可以做等值判断，但不应该做大小关系推断。
    """
    if field.value_type not in {ValueType.INTEGER, ValueType.REAL}:
        return False
    if field.enum_labels:
        return False
    return not any(constant.kind == ConstantKind.ASSIGNMENT for constant in field.constants)


def numeric_comparison_group(field: FieldSpec) -> str | None:
    """给数值字段归到某个可比较语义组，例如 size/time/count。

    同为数值字段也不能随便比较。
    例如：
    - `frame.len >= tcp.len` 合理，因为都属于 size；
    - `frame.time_epoch >= frame.len` 不合理，因为 time 和 size 语义不同。

    这里通过 FieldRole 给字段归组，只有归到同组的有序数值字段才允许大小比较。
    """
    if not is_ordered_numeric_field(field):
        return None
    for role in (FieldRole.SIZE, FieldRole.COUNT, FieldRole.TIME, FieldRole.SEQUENCE):
        if role in field.roles:
            return role.value
    return None


def are_numeric_fields_comparable(lhs: FieldSpec, rhs: FieldSpec) -> bool:
    """只有同语义组的有序数值字段才允许大小比较。

    这是字段-字段大小比较的最终判断函数。
    如果任何一侧不是有序数值字段，或者无法归入 size/count/time/sequence 等语义组，
    都会返回 False。
    """
    if not is_ordered_numeric_field(lhs) or not is_ordered_numeric_field(rhs):
        return False
    lhs_group = numeric_comparison_group(lhs)
    rhs_group = numeric_comparison_group(rhs)
    return lhs_group is not None and lhs_group == rhs_group


def addition_comparison_group(lhs: FieldSpec, rhs: FieldSpec) -> str | None:
    """判断两个字段相加后的结果可以被视为哪一类比较量。

    加法项必须能被解释成某个清晰语义组，才允许后续参与比较。

    当前规则：
    - size + size -> size；
    - count + count -> count；
    - time + time -> time，虽然业务上不一定常见，但语义组一致；
    - sequence + size -> sequence，用于表达“序列号加 payload 长度”这类网络协议关系；
    - 其他混合组合返回 None，表示不生成该加法项。
    """
    if not is_ordered_numeric_field(lhs) or not is_ordered_numeric_field(rhs):
        return None
    lhs_group = numeric_comparison_group(lhs)
    rhs_group = numeric_comparison_group(rhs)
    if lhs_group is None or rhs_group is None:
        return None
    if lhs_group == rhs_group:
        return lhs_group
    if {lhs_group, rhs_group} == {FieldRole.SEQUENCE.value, FieldRole.SIZE.value}:
        return FieldRole.SEQUENCE.value
    return None


def select_context_families(prepared: PreparedDataset, template: QuantifierTemplateSpec) -> dict[str, list[str]]:
    """选择符合量词模板要求的上下文字段族。

    `prepared.context_families` 的结构来自 dataset 阶段：
    - key 是 family 名称，例如 `tcp.seq`；
    - value 是按 context_index 排好序的窗口字段列表，例如
      `["tcp.seq_ctx0", "tcp.seq_ctx1", "tcp.seq_ctx2"]`。

    量词模板不是筛单个字段，而是筛一整个 family。
    这里用 family 第一个字段的 FieldSpec 作为代表样本，检查类型和角色是否符合模板要求。
    """
    families: dict[str, list[str]] = {}
    for family_name, field_names in prepared.context_families.items():
        # 同一个 family 内的字段应当拥有相同值类型和核心角色，
        # 因此取第一个字段作为元数据样本即可。
        sample = prepared.field_specs[field_names[0]]
        if template.selector.context_family is not None and family_name != template.selector.context_family:
            continue
        if template.selector.types and sample.value_type not in template.selector.types:
            continue
        if template.selector.roles and not set(template.selector.roles).intersection(sample.roles):
            continue
        families[family_name] = field_names
    return families


def project_quantified_family(
    family_name: str,
    family_fields: list[str],
    template: QuantifierTemplateSpec,
    op: Comparator,
    constant: SelectedConstant,
) -> tuple[Formula, str]:
    """把量词谓词投影成有限公式。

    例如：
    - forall X[k] >= c  -> min(X_*) >= c
    - exists X[k] >= c  -> max(X_*) >= c
    - 等号/不等号则退化为合取/析取

    为什么要投影：
    当前数据集里的上下文窗口长度是有限的，例如只有 ctx0/ctx1/ctx2。
    因此 `forall k in window: X[k] >= c` 可以变成普通有限公式，
    不需要保留一阶逻辑量词。

    投影规则：
    - forall + >= / >：所有元素都大于 c，等价于最小值大于 c；
    - exists + >= / >：存在元素大于 c，等价于最大值大于 c；
    - forall + <= / <：所有元素都小于 c，等价于最大值小于 c；
    - exists + <= / <：存在元素小于 c，等价于最小值小于 c；
    - forall + == / !=：展开成所有窗口列比较结果的 AND；
    - exists + == / !=：展开成所有窗口列比较结果的 OR。
    """
    # 把 family 中的每个窗口字段变成 AST 符号引用。
    terms = tuple(SymbolRef(name) for name in family_fields)
    constant_term = Constant(constant.value)
    # display 保留量词形式，方便用户理解原始意图；
    # formula 则是已经投影后的有限 AST。
    display = (
        f"{template.quantifier.upper()} k IN "
        f"{{{', '.join(str(i) for i in range(len(family_fields)))}}}: "
        f"{family_name}[k] {op.value} {constant.value}"
    )
    if op in {Comparator.GT, Comparator.GE}:
        # forall X >= c 需要看 min(X)；
        # exists X >= c 需要看 max(X)。
        agg = "min" if template.quantifier == "forall" else "max"
        return Compare(op.value, FuncCall(agg, terms), constant_term), display
    if op in {Comparator.LT, Comparator.LE}:
        # forall X <= c 需要看 max(X)；
        # exists X <= c 需要看 min(X)。
        agg = "max" if template.quantifier == "forall" else "min"
        return Compare(op.value, FuncCall(agg, terms), constant_term), display
    # 对 == / != 这类不能用 min/max 表达的比较，逐字段展开。
    grounded = tuple(Compare(op.value, SymbolRef(field), constant_term) for field in family_fields)
    if template.quantifier == "forall":
        # forall：所有窗口列都必须满足，因此是 AND。
        return BoolAnd(grounded), display
    # exists：任意一个窗口列满足即可，因此是 OR。
    return BoolOr(grounded), display
