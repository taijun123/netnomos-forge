"""规则理论求值与 Z3 降阶。

本模块是 NetNomos 中“判断公式是否成立”的核心层。

它承担两类职责：
1. 数据级求值：
   在 Pandas DataFrame 上评估 AST 公式，得到每一行是否满足该公式。
   这服务于 predicate support 计算、规则 support 计算和 validate 流程。

2. 理论级求解：
   把 AST 公式转换为 Z3 表达式，交给 SMT solver 判断一致性和逻辑蕴含。
   这服务于 `entails` 查询和规则理论验证。

为什么需要两套逻辑：
- DataFrame 求值回答的是“这条规则在当前样本数据上成立比例是多少”；
- Z3 求解回答的是“这些公式在逻辑上是否推出另一个公式”，不依赖具体数据行。

因此 support 高不等于逻辑蕴含，逻辑蕴含也不等于在样本中频繁出现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import z3

from netnomos.ast import (
    BinaryTerm,
    BoolAnd,
    BoolConst,
    BoolNot,
    BoolOr,
    Compare,
    Constant,
    Exists,
    Formula,
    ForAll,
    FuncCall,
    Implies,
    IndexedRef,
    SymbolRef,
    Term,
    formula_to_string,
)
from netnomos.dataset import PreparedDataset
from netnomos.specs import FieldSpec, ValueType


@dataclass(slots=True)
class Theory:
    """由若干公式组成的理论。

    可以把 Theory 理解成一组已经学习到或人工提供的规则集合。
    它提供两个层面的能力：
    - `validate()`：回到真实数据上统计这些规则的满足率；
    - `entails()` / `is_consistent()`：交给 Z3 做逻辑级判断。
    """

    # 理论中的公式列表，通常来自 LearnedRule.formula。
    formulas: list[Formula]
    # 字段元数据，用于把 SymbolRef 降阶成正确的 Z3 类型。
    fields: dict[str, FieldSpec]
    # 上下文字段族索引，用于解析 IndexedRef，例如 tcp.seq[k]。
    context_families: dict[str, list[str]]

    def entails(self, query: Formula) -> bool:
        """检查当前理论是否逻辑蕴含 query。

        逻辑方法是反证：
        - 先把理论中的所有公式加入 solver；
        - 再加入 `not query`；
        - 如果 solver 判断不可满足（unsat），说明不存在“理论成立但 query 不成立”的情况；
        - 因此理论蕴含 query。
        """
        solver = z3.Solver()
        for formula in self.formulas:
            solver.add(lower_formula(formula, self.fields, self.context_families))
        solver.add(z3.Not(lower_formula(query, self.fields, self.context_families)))
        return solver.check() == z3.unsat

    def is_consistent(self) -> bool:
        """检查理论本身是否可满足。

        如果一组规则互相矛盾，例如同时要求 `x > 5` 和 `x <= 5`，
        Z3 会返回 unsat，表示理论不一致。
        """
        solver = z3.Solver()
        for formula in self.formulas:
            solver.add(lower_formula(formula, self.fields, self.context_families))
        return solver.check() == z3.sat

    def validate(self, prepared: PreparedDataset) -> dict[str, Any]:
        """在实际数据集上统计每条规则的满足率。

        这里不是逻辑证明，而是经验验证：
        - 对每条公式在 DataFrame 上求每行 True/False；
        - True 当作 1，False 当作 0；
        - mean() 就是该规则在当前数据上的满足率。
        """
        sats = [float(evaluate_formula_df(formula, prepared).mean()) for formula in self.formulas]
        return {
            "rule_count": len(self.formulas),
            "all_rows_satisfied": all(rate == 1.0 for rate in sats),
            "mean_satisfaction": float(np.mean(sats)) if sats else 1.0,
            "per_rule_satisfaction": sats,
        }


def evaluate_formula_df(formula: Formula, prepared: PreparedDataset) -> pd.Series:
    """在整个 DataFrame 上评估公式，返回每一行的布尔结果。

    优先尝试 Pandas 向量化：
    - 速度快；
    - 适合普通比较、逻辑与/或/非、蕴含等结构。

    如果公式包含复杂量词、复杂函数或 Pandas 类型不兼容，则回退到逐行递归求值。
    回退更慢，但语义覆盖更完整。
    """
    try:
        return _evaluate_formula_vectorized(formula, prepared)
    except Exception:
        # 量词、复杂函数或某些 Pandas 类型组合可能不适合向量化。
        return prepared.dataframe.apply(
            lambda row: bool(evaluate_formula_row(formula, row.to_dict(), prepared.context_families)),
            axis=1,
        )


def evaluate_formula_row(formula: Formula, row: dict[str, Any], context_families: dict[str, list[str]], env: dict[str, Any] | None = None) -> bool:
    """在单行数据环境中递归求值公式。

    `row` 是一行数据转成的字典。
    `env` 用于量词变量绑定，例如 forall k in {0,1,2} 时，k 的当前值会放在 env 中。

    这个函数是解释器式求值：
    - 遇到 BoolAnd 就递归求所有子公式；
    - 遇到 Compare 就先求左右 term，再执行比较；
    - 遇到 ForAll/Exists 就枚举有限 domain。
    """
    env = env or {}
    if isinstance(formula, BoolConst):
        return formula.value
    if isinstance(formula, Compare):
        # 比较公式先求左右项，再根据 op 做基础比较。
        left = evaluate_term_row(formula.left, row, context_families, env)
        right = evaluate_term_row(formula.right, row, context_families, env)
        return compare_values(formula.op, left, right)
    if isinstance(formula, BoolNot):
        return not evaluate_formula_row(formula.value, row, context_families, env)
    if isinstance(formula, BoolAnd):
        return all(evaluate_formula_row(v, row, context_families, env) for v in formula.values)
    if isinstance(formula, BoolOr):
        return any(evaluate_formula_row(v, row, context_families, env) for v in formula.values)
    if isinstance(formula, Implies):
        # A -> B 等价于 (not A) or B。
        return (not evaluate_formula_row(formula.left, row, context_families, env)) or evaluate_formula_row(formula.right, row, context_families, env)
    if isinstance(formula, ForAll):
        # 有限全称量词：domain 中每个值都让 body 成立。
        return all(evaluate_formula_row(formula.body, row, context_families, {**env, formula.variable: value}) for value in formula.domain)
    if isinstance(formula, Exists):
        # 有限存在量词：domain 中至少一个值让 body 成立。
        return any(evaluate_formula_row(formula.body, row, context_families, {**env, formula.variable: value}) for value in formula.domain)
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")


def evaluate_term_row(term: Term, row: dict[str, Any], context_families: dict[str, list[str]], env: dict[str, Any]) -> Any:
    """在单行数据环境中求值项表达式。

    Term 是公式比较符左右两侧的表达式。
    它可能是：
    - 常量；
    - 字段引用；
    - 上下文索引引用；
    - 算术表达式；
    - 函数调用。
    """
    if isinstance(term, Constant):
        return term.value
    if isinstance(term, SymbolRef):
        # SymbolRef 直接读取当前行中对应字段的值。
        return row[term.name]
    if isinstance(term, IndexedRef):
        # IndexedRef 需要先把 family/index 解析成真实列名。
        return row[resolve_indexed_name(term, env, context_families)]
    if isinstance(term, BinaryTerm):
        left = evaluate_term_row(term.left, row, context_families, env)
        right = evaluate_term_row(term.right, row, context_families, env)
        if term.op == "+":
            return left + right
        if term.op == "-":
            return left - right
        if term.op == "*":
            return left * right
        if term.op == "/":
            return left / right
        raise ValueError(f"Unsupported term op: {term.op}")
    if isinstance(term, FuncCall):
        # 函数参数先递归求值，再按函数名分派。
        args = [evaluate_term_row(arg, row, context_families, env) for arg in term.args]
        name = term.name.lower()
        if name == "min":
            return min(args)
        if name == "max":
            return max(args)
        if name == "sum":
            return sum(args)
        if name == "avg":
            return sum(args) / len(args)
        if name == "mod":
            if len(args) != 2:
                raise ValueError("MOD requires exactly two arguments")
            return args[0] % args[1]
        raise ValueError(f"Unsupported function: {term.name}")
    raise TypeError(f"Unsupported term node: {type(term)!r}")


def compare_values(op: str, left: Any, right: Any) -> bool:
    """执行基础比较操作。

    这里假设上游已经生成了语义合理、类型可比较的公式。
    如果实际值类型不兼容，Python 自身会抛出异常，并由上层决定是否回退或失败。
    """
    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    raise ValueError(f"Unsupported comparator: {op}")


def lower_formula(formula: Formula, fields: dict[str, FieldSpec], context_families: dict[str, list[str]], env: dict[str, Any] | None = None) -> z3.ExprRef:
    """把 AST 公式降到 Z3 表达式。

    “降阶 / lowering”指把项目内部 AST 转换成 Z3 能理解的表达式。

    与 DataFrame 求值不同：
    - DataFrame 求值需要真实行数据；
    - Z3 降阶只建立符号变量和约束，不需要具体数据。

    量词仍然按有限域展开：
    - ForAll -> And(body(value1), body(value2), ...)
    - Exists -> Or(body(value1), body(value2), ...)
    """
    env = env or {}
    if isinstance(formula, BoolConst):
        return z3.BoolVal(formula.value)
    if isinstance(formula, Compare):
        # 先把左右 term 降成 Z3 表达式，再应用比较操作。
        left = lower_term(formula.left, fields, context_families, env)
        right = lower_term(formula.right, fields, context_families, env)
        if formula.op == "=":
            return left == right
        if formula.op == "!=":
            return left != right
        if formula.op == ">":
            return left > right
        if formula.op == ">=":
            return left >= right
        if formula.op == "<":
            return left < right
        if formula.op == "<=":
            return left <= right
        raise ValueError(f"Unsupported comparator: {formula.op}")
    if isinstance(formula, BoolNot):
        return z3.Not(lower_formula(formula.value, fields, context_families, env))
    if isinstance(formula, BoolAnd):
        return z3.And(*[lower_formula(v, fields, context_families, env) for v in formula.values])
    if isinstance(formula, BoolOr):
        return z3.Or(*[lower_formula(v, fields, context_families, env) for v in formula.values])
    if isinstance(formula, Implies):
        return z3.Implies(lower_formula(formula.left, fields, context_families, env), lower_formula(formula.right, fields, context_families, env))
    if isinstance(formula, ForAll):
        return z3.And(*[lower_formula(formula.body, fields, context_families, {**env, formula.variable: value}) for value in formula.domain])
    if isinstance(formula, Exists):
        return z3.Or(*[lower_formula(formula.body, fields, context_families, {**env, formula.variable: value}) for value in formula.domain])
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")


def lower_term(term: Term, fields: dict[str, FieldSpec], context_families: dict[str, list[str]], env: dict[str, Any]) -> z3.ExprRef:
    """把项表达式降到 Z3。

    常量会变成 Z3 字面量；
    字段引用会变成 Z3 符号变量；
    算术和函数调用会被转换成对应的 Z3 表达式。
    """
    if isinstance(term, Constant):
        # Python bool 是 int 的子类，因此仍然要先判断 bool。
        if isinstance(term.value, bool):
            return z3.BoolVal(term.value)
        if isinstance(term.value, int):
            return z3.IntVal(term.value)
        if isinstance(term.value, float):
            return z3.RealVal(term.value)
        return z3.StringVal(str(term.value))
    if isinstance(term, SymbolRef):
        # 字段引用需要根据 FieldSpec.value_type 选择 Z3 Int/Real/Bool/String。
        return symbol_for_field(term.name, fields[term.name])
    if isinstance(term, IndexedRef):
        name = resolve_indexed_name(term, env, context_families)
        return symbol_for_field(name, fields[name])
    if isinstance(term, BinaryTerm):
        left = lower_term(term.left, fields, context_families, env)
        right = lower_term(term.right, fields, context_families, env)
        if term.op == "+":
            return left + right
        if term.op == "-":
            return left - right
        if term.op == "*":
            return left * right
        if term.op == "/":
            return left / right
        raise ValueError(f"Unsupported term op: {term.op}")
    if isinstance(term, FuncCall):
        args = [lower_term(arg, fields, context_families, env) for arg in term.args]
        name = term.name.lower()
        if name == "min":
            # Z3 没有直接的可变参数 min，这里用嵌套 If 表达。
            return fold_if_min(args)
        if name == "max":
            return fold_if_max(args)
        if name == "sum":
            result = args[0]
            for arg in args[1:]:
                result = result + arg
            return result
        if name == "avg":
            total = lower_term(FuncCall("sum", term.args), fields, context_families, env)
            return total / z3.RealVal(len(args))
        if name == "mod":
            if len(args) != 2:
                raise ValueError("MOD requires exactly two arguments")
            return args[0] % args[1]
        raise ValueError(f"Unsupported function: {term.name}")
    raise TypeError(f"Unsupported term node: {type(term)!r}")


def symbol_for_field(name: str, field: FieldSpec) -> z3.ExprRef:
    """根据字段类型选择合适的 Z3 符号类型。

    字段类型来自 `FieldSpec.value_type`。
    如果 value_type 不够明确，但 domain 全是同类值，也尝试从 domain 推断。
    最后兜底为 Z3 String。
    """
    if field.value_type == ValueType.INTEGER:
        return z3.Int(name)
    if field.value_type == ValueType.REAL:
        return z3.Real(name)
    if field.value_type == ValueType.BOOLEAN:
        return z3.Bool(name)
    if field.domain:
        if all(isinstance(value, bool) for value in field.domain):
            return z3.Bool(name)
        if all(isinstance(value, int) and not isinstance(value, bool) for value in field.domain):
            return z3.Int(name)
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in field.domain):
            return z3.Real(name)
    return z3.String(name)


def fold_if_min(args: list[z3.ExprRef]) -> z3.ExprRef:
    """用嵌套 If 构造最小值表达式，避免依赖额外 theory。

    例如 min(a, b, c) 会变成：
    If(If(a <= b, a, b) <= c, If(a <= b, a, b), c)
    """
    result = args[0]
    for arg in args[1:]:
        result = z3.If(result <= arg, result, arg)
    return result


def fold_if_max(args: list[z3.ExprRef]) -> z3.ExprRef:
    """用嵌套 If 构造最大值表达式。

    与 `fold_if_min()` 对称，用于量词投影后的 max(...) 表达式。
    """
    result = args[0]
    for arg in args[1:]:
        result = z3.If(result >= arg, result, arg)
    return result


def resolve_indexed_name(term: IndexedRef, env: dict[str, Any], context_families: dict[str, list[str]]) -> str:
    """把 X[k] 解析成具体列名，例如 tcp.seq_ctx1。

    `IndexedRef(base="tcp.seq", index="k")` 不能直接读取数据。
    需要先通过 env 找到 k 当前绑定的值，再从 context_families 中取对应列名。
    """
    index = env.get(term.index, term.index)
    if isinstance(index, str) and index.isdigit():
        index = int(index)
    if not isinstance(index, int):
        raise ValueError(f"Indexed reference {formula_to_string(Compare('=', term, Constant(0)))} requires an integer index")
    if term.base not in context_families:
        raise KeyError(f"Unknown context family: {term.base}")
    return context_families[term.base][index]


def _evaluate_formula_vectorized(formula: Formula, prepared: PreparedDataset) -> pd.Series:
    """在可能时使用 Pandas 向量化运算批量求值。

    这里是性能优先路径。
    对普通比较和布尔组合，Pandas 可以一次性对整列计算，远快于逐行 apply。
    """
    if isinstance(formula, BoolConst):
        return pd.Series([formula.value] * len(prepared.dataframe), index=prepared.dataframe.index)
    if isinstance(formula, Compare):
        left = _evaluate_term_vectorized(formula.left, prepared)
        right = _evaluate_term_vectorized(formula.right, prepared)
        if formula.op == "=":
            return left == right
        if formula.op == "!=":
            return left != right
        if formula.op == ">":
            return left > right
        if formula.op == ">=":
            return left >= right
        if formula.op == "<":
            return left < right
        if formula.op == "<=":
            return left <= right
    if isinstance(formula, BoolNot):
        return ~_evaluate_formula_vectorized(formula.value, prepared)
    if isinstance(formula, BoolAnd):
        # 从第一个子公式开始逐步按位与。
        result = _evaluate_formula_vectorized(formula.values[0], prepared)
        for child in formula.values[1:]:
            result = result & _evaluate_formula_vectorized(child, prepared)
        return result
    if isinstance(formula, BoolOr):
        result = _evaluate_formula_vectorized(formula.values[0], prepared)
        for child in formula.values[1:]:
            result = result | _evaluate_formula_vectorized(child, prepared)
        return result
    if isinstance(formula, Implies):
        # A -> B 等价于 (~A) | B。
        left = _evaluate_formula_vectorized(formula.left, prepared)
        right = _evaluate_formula_vectorized(formula.right, prepared)
        return (~left) | right
    raise ValueError("Quantified formulas require row-wise evaluation")


def _evaluate_term_vectorized(term: Term, prepared: PreparedDataset) -> pd.Series | Any:
    """向量化求值项表达式。

    返回值可能是：
    - pd.Series：当 term 引用 DataFrame 列时；
    - Python 标量：当 term 是纯常量或纯标量函数时。
    """
    frame = prepared.dataframe
    if isinstance(term, Constant):
        return term.value
    if isinstance(term, SymbolRef):
        return frame[term.name]
    if isinstance(term, IndexedRef):
        name = resolve_indexed_name(term, {}, prepared.context_families)
        return frame[name]
    if isinstance(term, BinaryTerm):
        left = _evaluate_term_vectorized(term.left, prepared)
        right = _evaluate_term_vectorized(term.right, prepared)
        if term.op == "+":
            return left + right
        if term.op == "-":
            return left - right
        if term.op == "*":
            return left * right
        if term.op == "/":
            return left / right
    if isinstance(term, FuncCall):
        # 函数调用的每个参数先向量化求值。
        columns = [_evaluate_term_vectorized(arg, prepared) for arg in term.args]
        name = term.name.lower()
        if all(isinstance(col, pd.Series) for col in columns):
            # 如果所有参数都是 Series，就按行聚合。
            tmp = pd.concat(columns, axis=1)
            if name == "min":
                return tmp.min(axis=1)
            if name == "max":
                return tmp.max(axis=1)
            if name == "sum":
                return tmp.sum(axis=1)
            if name == "avg":
                return tmp.mean(axis=1)
            if name == "mod":
                if len(columns) != 2:
                    raise ValueError("MOD requires exactly two arguments")
                return columns[0] % columns[1]
        # 如果存在标量和 Series 混合，当前实现只取 Series 的第一个值作为兜底。
        # 正常 projection 生成的函数项通常会走上面的全 Series 路径。
        values = [col if not isinstance(col, pd.Series) else col.iloc[0] for col in columns]
        if name == "min":
            return min(values)
        if name == "max":
            return max(values)
        if name == "sum":
            return sum(values)
        if name == "avg":
            return sum(values) / len(values)
        if name == "mod":
            if len(values) != 2:
                raise ValueError("MOD requires exactly two arguments")
            return values[0] % values[1]
    raise TypeError(f"Unsupported vectorized term: {type(term)!r}")
