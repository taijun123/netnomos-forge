"""公式与项的抽象语法树定义。

AST 是 abstract syntax tree，抽象语法树。
NetNomos 不直接把规则保存成普通字符串，而是把规则拆成一棵结构化树：
- 叶子节点通常是常量 `Constant` 或字段引用 `SymbolRef`；
- 中间节点可以是算术项 `BinaryTerm`、函数调用 `FuncCall`；
- 公式节点可以是比较、逻辑与/或/非、蕴含、量词。

这样做的好处是：
1. projection 阶段可以程序化拼装谓词，而不是拼字符串；
2. theory 阶段可以递归求值或降阶到 Z3；
3. API 可以把规则可靠地序列化到 `rules.json`，之后再恢复成结构化对象；
4. interpreter 可以基于结构化节点做更友好的中文/语义解释。

该模块只负责三件事：
1. 定义节点类型；
2. 提供字典序列化/反序列化；
3. 提供统一的字符串渲染。

它不负责语义求值，求值逻辑位于 `theory.py`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Constant:
    """字面量常量，例如数字、字符串、布尔值。

    示例：
    - `Constant(10)` 表示规则里的数字 10；
    - `Constant("TCP")` 表示字符串常量 TCP；
    - `Constant(True)` 表示布尔常量 true。
    """

    # 原始 Python 值，序列化时会直接写入 JSON。
    value: Any


@dataclass(frozen=True, slots=True)
class SymbolRef:
    """对字段名的直接引用，例如 Bytes、tcp.seq_ctx0。

    它对应 DataFrame 中的一列。
    在求值阶段，`theory.py` 会用 `row[name]` 或 `frame[name]` 取出真实数据。
    """

    # 字段名必须能在 PreparedDataset.field_specs / dataframe.columns 中找到。
    name: str


@dataclass(frozen=True, slots=True)
class IndexedRef:
    """对上下文族的索引引用，例如 tcp.seq[k]。

    这是量词表达式里使用的节点。
    例如 `forall k in {0,1,2}: tcp.seq[k] >= 0` 中的 `tcp.seq[k]`
    会被表示成 `IndexedRef(base="tcp.seq", index="k")`。

    求值时需要结合：
    - `env`：把变量 k 绑定到具体数字；
    - `context_families`：把 family + index 解析成真实列名，如 tcp.seq_ctx1。
    """

    # 上下文字段族名称，例如 tcp.seq。
    base: str
    # 可以是具体整数，也可以是量词变量名。
    index: int | str


@dataclass(frozen=True, slots=True)
class BinaryTerm:
    """二元算术表达式，例如 A + B、Packets * 65535。

    这是“项”层面的表达式，不是完整公式。
    只有被放到 `Compare(left, right)` 中，它才变成谓词的一部分。
    """

    # 当前支持 +、-、*、/，具体求值逻辑在 theory.py。
    op: str
    # 左右两侧仍然是 Term，因此可以递归嵌套。
    left: Term
    right: Term


@dataclass(frozen=True, slots=True)
class FuncCall:
    """函数调用项，例如 MIN(...)、MAX(...)、MOD(..., ...)。

    projection 中的量词投影会经常生成 `min(...)` / `max(...)`。
    例如 `forall X[k] >= c` 会被投影成 `min(X_ctx0, X_ctx1, ...) >= c`。
    """

    # 函数名以字符串保存，求值时通常转成小写分派。
    name: str
    # 函数参数是 Term 元组，可包含字段、常量、算术表达式等。
    args: tuple[Term, ...]


Term = Constant | SymbolRef | IndexedRef | BinaryTerm | FuncCall
"""项节点联合类型。

Term 表示“能出现在比较符左右两边的表达式”。
"""


@dataclass(frozen=True, slots=True)
class Compare:
    """比较公式，是最基础的原子谓词。

    示例：
    - `frame.len >= 60`
    - `protocol = "TCP"`
    - `(tcp.seq + tcp.len) <= tcp.ack`
    """

    # 比较操作符，使用字符串保存，例如 =、!=、>、>=、<、<=。
    op: str
    # 比较符左右两侧是 Term。
    left: Term
    right: Term


@dataclass(frozen=True, slots=True)
class BoolConst:
    """布尔常量 TRUE / FALSE。

    通常用于测试、边界情况或构造恒真/恒假公式。
    """

    value: bool


@dataclass(frozen=True, slots=True)
class BoolNot:
    """逻辑非。

    表示 `NOT formula`。
    """

    value: Formula


@dataclass(frozen=True, slots=True)
class BoolAnd:
    """逻辑与。

    表示多个公式同时成立。`values` 为空在当前代码里没有特殊恒真语义，
    正常情况下应由上游生成至少一个子公式。
    """

    values: tuple[Formula, ...]


@dataclass(frozen=True, slots=True)
class BoolOr:
    """逻辑或。

    表示多个公式至少一个成立。
    """

    values: tuple[Formula, ...]


@dataclass(frozen=True, slots=True)
class Implies:
    """蕴含公式 left -> right。

    语义是：如果 left 成立，则 right 必须成立。
    在逐行求值中等价于 `(not left) or right`。
    """

    left: Formula
    right: Formula


@dataclass(frozen=True, slots=True)
class ForAll:
    """有限域上的全称量词。

    注意这里是有限域量词，不是无限一阶逻辑量词。
    例如 `forall k in {0,1,2}: tcp.seq[k] >= 0`。
    """

    variable: str
    domain: tuple[Any, ...]
    body: Formula


@dataclass(frozen=True, slots=True)
class Exists:
    """有限域上的存在量词。

    例如 `exists k in {0,1,2}: tcp.flags[k] = "SYN"`。
    """

    variable: str
    domain: tuple[Any, ...]
    body: Formula


Formula = Compare | BoolConst | BoolNot | BoolAnd | BoolOr | Implies | ForAll | Exists
"""公式节点联合类型。

Formula 表示“最终能被判断真假”的表达式。
"""


def constant(value: Any) -> Constant:
    """便捷构造器，减少外部代码显式写 Constant(...) 的样板。"""
    return Constant(value=value)


def render_keyword(value: str) -> str:
    """统一把逻辑关键字渲染为大写，便于人类阅读。"""
    return value.upper()


def formula_to_dict(node: Formula) -> dict[str, Any]:
    """把公式 AST 序列化成可写入 JSON 的字典。

    该函数用于 artifact 落盘，例如 `rules.json`。
    每个节点都会写出一个 `kind` 字段，反序列化时依靠它恢复具体节点类型。
    """
    if isinstance(node, Compare):
        return {
            "kind": "compare",
            "op": node.op,
            "left": term_to_dict(node.left),
            "right": term_to_dict(node.right),
        }
    if isinstance(node, BoolConst):
        return {"kind": "bool", "value": node.value}
    if isinstance(node, BoolNot):
        return {"kind": "not", "value": formula_to_dict(node.value)}
    if isinstance(node, BoolAnd):
        return {"kind": "and", "values": [formula_to_dict(v) for v in node.values]}
    if isinstance(node, BoolOr):
        return {"kind": "or", "values": [formula_to_dict(v) for v in node.values]}
    if isinstance(node, Implies):
        return {
            "kind": "implies",
            "left": formula_to_dict(node.left),
            "right": formula_to_dict(node.right),
        }
    if isinstance(node, ForAll):
        return {
            "kind": "forall",
            "variable": node.variable,
            "domain": list(node.domain),
            "body": formula_to_dict(node.body),
        }
    if isinstance(node, Exists):
        return {
            "kind": "exists",
            "variable": node.variable,
            "domain": list(node.domain),
            "body": formula_to_dict(node.body),
        }
    raise TypeError(f"Unsupported formula node: {type(node)!r}")


def term_to_dict(node: Term) -> dict[str, Any]:
    """把项 AST 序列化成可写入 JSON 的字典。

    它是 `formula_to_dict()` 的辅助函数，因为公式节点内部会嵌套 Term。
    """
    if isinstance(node, Constant):
        return {"kind": "constant", "value": node.value}
    if isinstance(node, SymbolRef):
        return {"kind": "symbol", "name": node.name}
    if isinstance(node, IndexedRef):
        return {"kind": "indexed", "base": node.base, "index": node.index}
    if isinstance(node, BinaryTerm):
        return {
            "kind": "binary",
            "op": node.op,
            "left": term_to_dict(node.left),
            "right": term_to_dict(node.right),
        }
    if isinstance(node, FuncCall):
        return {"kind": "call", "name": node.name, "args": [term_to_dict(v) for v in node.args]}
    raise TypeError(f"Unsupported term node: {type(node)!r}")


def formula_from_dict(data: dict[str, Any]) -> Formula:
    """从 JSON 字典恢复公式 AST。

    这是 `formula_to_dict()` 的逆操作。
    API 的 `load_rules()` 会用它把 `rules.json` 中的公式恢复成结构化对象。
    """
    kind = data["kind"]
    if kind == "compare":
        return Compare(data["op"], term_from_dict(data["left"]), term_from_dict(data["right"]))
    if kind == "bool":
        return BoolConst(bool(data["value"]))
    if kind == "not":
        return BoolNot(formula_from_dict(data["value"]))
    if kind == "and":
        return BoolAnd(tuple(formula_from_dict(v) for v in data["values"]))
    if kind == "or":
        return BoolOr(tuple(formula_from_dict(v) for v in data["values"]))
    if kind == "implies":
        return Implies(formula_from_dict(data["left"]), formula_from_dict(data["right"]))
    if kind == "forall":
        return ForAll(variable=data["variable"], domain=tuple(data["domain"]), body=formula_from_dict(data["body"]))
    if kind == "exists":
        return Exists(variable=data["variable"], domain=tuple(data["domain"]), body=formula_from_dict(data["body"]))
    raise ValueError(f"Unsupported formula kind: {kind}")


def term_from_dict(data: dict[str, Any]) -> Term:
    """从 JSON 字典恢复项 AST。

    这是 `term_to_dict()` 的逆操作。
    """
    kind = data["kind"]
    if kind == "constant":
        return Constant(data["value"])
    if kind == "symbol":
        return SymbolRef(data["name"])
    if kind == "indexed":
        return IndexedRef(data["base"], data["index"])
    if kind == "binary":
        return BinaryTerm(data["op"], term_from_dict(data["left"]), term_from_dict(data["right"]))
    if kind == "call":
        return FuncCall(data["name"], tuple(term_from_dict(v) for v in data["args"]))
    raise ValueError(f"Unsupported term kind: {kind}")


def term_to_string(node: Term) -> str:
    """把项渲染为人类可读字符串。

    这个字符串用于去重、展示和调试。
    注意它不是再解析时唯一可信的格式；结构化保存仍应使用 `term_to_dict()`。
    """
    if isinstance(node, Constant):
        return repr(node.value) if isinstance(node.value, str) else str(node.value)
    if isinstance(node, SymbolRef):
        return node.name
    if isinstance(node, IndexedRef):
        return f"{node.base}[{node.index}]"
    if isinstance(node, BinaryTerm):
        return f"({term_to_string(node.left)} {node.op} {term_to_string(node.right)})"
    if isinstance(node, FuncCall):
        return f"{render_keyword(node.name)}({', '.join(term_to_string(v) for v in node.args)})"
    raise TypeError(f"Unsupported term node: {type(node)!r}")


def formula_to_string(node: Formula) -> str:
    """把公式渲染为统一的可读文本表示。

    projection 阶段会用它作为候选谓词的去重 key。
    因此这里的输出应尽量稳定：同一棵 AST 在不同运行中应渲染为同一字符串。
    """
    if isinstance(node, Compare):
        return f"{term_to_string(node.left)} {node.op} {term_to_string(node.right)}"
    if isinstance(node, BoolConst):
        return render_keyword("true") if node.value else render_keyword("false")
    if isinstance(node, BoolNot):
        return f"{render_keyword('not')} ({formula_to_string(node.value)})"
    if isinstance(node, BoolAnd):
        return f" {render_keyword('and')} ".join(f"({formula_to_string(v)})" for v in node.values)
    if isinstance(node, BoolOr):
        return f" {render_keyword('or')} ".join(f"({formula_to_string(v)})" for v in node.values)
    if isinstance(node, Implies):
        return f"({formula_to_string(node.left)}) -> ({formula_to_string(node.right)})"
    if isinstance(node, ForAll):
        return (
            f"{render_keyword('forall')} {node.variable} {render_keyword('in')} "
            f"{{{', '.join(map(str, node.domain))}}}: {formula_to_string(node.body)}"
        )
    if isinstance(node, Exists):
        return (
            f"{render_keyword('exists')} {node.variable} {render_keyword('in')} "
            f"{{{', '.join(map(str, node.domain))}}}: {formula_to_string(node.body)}"
        )
    raise TypeError(f"Unsupported formula node: {type(node)!r}")
