"""NetNomos 公式 DSL 解析器。

DSL 是 domain-specific language，即“面向本项目规则表达的小语言”。
用户或测试可以写出类似下面的公式字符串：
- `frame.len >= 60`
- `(tcp.seq + tcp.len) <= tcp.ack`
- `protocol = 'TCP' and frame.len > 100`
- `forall k in {0, 1, 2}: tcp.seq[k] >= 0`

本模块负责把这些字符串解析成 `ast.py` 中定义的结构化 AST。
它不负责判断公式真假，求值在 `theory.py`；也不负责生成候选公式，生成在 `projection.py`。

解析流程分两步：
1. `tokenize()`：词法分析，把字符串切成 Token 序列；
2. `FormulaParser`：递归下降解析，把 Token 序列变成 AST。

递归下降的优先级从低到高为：
蕴含 -> 或 -> 与 -> 一元逻辑 -> 比较 -> 加减 -> 乘除 -> 原子项。

也就是说：
- `a -> b or c` 会先解析为 `a -> (b or c)`；
- `a + b * c` 会先解析乘法，再解析加法。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from netnomos.ast import (
    BinaryTerm,
    BoolAnd,
    BoolConst,
    BoolNot,
    BoolOr,
    Compare,
    Constant,
    Exists,
    ForAll,
    FuncCall,
    Formula,
    Implies,
    IndexedRef,
    SymbolRef,
    Term,
)


TOKEN_RE = re.compile(
    r"""
    (?P<SPACE>\s+)
    |(?P<ARROW>->)
    |(?P<GE>>=)
    |(?P<LE><=)
    |(?P<NE>!=)
    |(?P<GT>>)
    |(?P<LT><)
    |(?P<EQ>=)
    |(?P<LPAREN>\()
    |(?P<RPAREN>\))
    |(?P<LBRACE>\{)
    |(?P<RBRACE>\})
    |(?P<LBRACK>\[)
    |(?P<RBRACK>\])
    |(?P<COMMA>,)
    |(?P<COLON>:)
    |(?P<PLUS>\+)
    |(?P<MINUS>-)
    |(?P<STAR>\*)
    |(?P<SLASH>/)
    |(?P<NUMBER>\d+(?:\.\d+)?)
    |(?P<STRING>'[^']*'|"[^"]*")
    |(?P<IDENT>[A-Za-z_][A-Za-z0-9_.]*)
    """,
    re.VERBOSE,
)
"""DSL 词法规则。

每个命名分组都会变成一个 Token.kind。
顺序很重要：例如 `>=` 必须在 `>` 之前匹配，否则会被错误拆成 `>` 和 `=`。

当前 DSL 支持：
- 逻辑符号：`->`、and、or、not；
- 比较符：=、!=、>、>=、<、<=；
- 括号、花括号、方括号、逗号、冒号；
- 算术符：+、-、*、/；
- 数字、单/双引号字符串、标识符。
"""


KEYWORDS = {"and", "or", "not", "forall", "exists", "in", "true", "false"}
"""保留关键字集合。

词法分析时，普通 IDENT 如果命中这些关键字，会被改成对应的小写 kind。
这样解析器可以直接 `match("and")`，不用再判断 IDENT 的具体值。
"""


@dataclass(frozen=True, slots=True)
class Token:
    """词法分析后的单个记号。

    示例：
    - 输入 `frame.len >= 60`
    - 输出 Token 序列大致为：
      `IDENT(frame.len)`, `GE(>=)`, `NUMBER(60)`
    """

    # Token 类型，来自 TOKEN_RE 的命名分组或关键字本身。
    kind: str
    # 原始文本值。
    value: str


def tokenize(text: str) -> list[Token]:
    """把输入字符串切分成记号序列，忽略空白。

    这是解析器的第一阶段。
    它只负责“认出文本片段是什么类型”，不负责理解公式结构。

    如果遇到无法匹配的字符，会立即抛出包含位置的错误，方便用户定位 DSL 拼写问题。
    """
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        # 从当前位置开始匹配一个 token。
        # 必须从 pos 精确匹配，不能跳过未知字符。
        match = TOKEN_RE.match(text, pos)
        if match is None:
            raise ValueError(f"Unexpected token at position {pos}: {text[pos:pos + 20]!r}")
        pos = match.end()
        kind = match.lastgroup
        value = match.group()
        if kind == "SPACE":
            # 空白只用于分隔，不进入语法树。
            continue
        if kind == "IDENT" and value.lower() in KEYWORDS:
            # 关键字统一变成小写 kind，避免 AND/and 混用导致解析差异。
            tokens.append(Token(value.lower(), value.lower()))
        else:
            tokens.append(Token(kind, value))
    return tokens


class FormulaParser:
    """递归下降公式解析器。

    递归下降的核心思想是：
    - 每个优先级层级对应一个 parse_xxx() 方法；
    - 低优先级方法调用高优先级方法；
    - 当前方法只处理自己这一层的操作符。

    例如 `parse_or()` 会先调用 `parse_and()` 解析左侧，
    然后循环消费所有 `or`，从而保证 `and` 比 `or` 优先级更高。
    """

    def __init__(self, text: str):
        # 先做词法分析，后续解析只在 token 列表上移动 index。
        self.tokens = tokenize(text)
        # 当前读取到的 token 位置。
        self.index = 0

    def parse(self) -> Formula:
        """解析完整公式，并确保输入被完全消费。

        如果解析出一个公式后还有剩余 token，说明输入里有多余内容，
        例如 `a = 1 b = 2`，这应该视为语法错误。
        """
        formula = self.parse_implication()
        if self.index != len(self.tokens):
            raise ValueError(f"Unexpected trailing token: {self.tokens[self.index]!r}")
        return formula

    def parse_implication(self) -> Formula:
        """解析蕴含表达式。

        蕴含 `->` 是最低优先级，并且这里写成右结合：
        `a -> b -> c` 会解析为 `a -> (b -> c)`。
        """
        left = self.parse_or()
        if self.match("ARROW"):
            right = self.parse_implication()
            return Implies(left, right)
        return left

    def parse_or(self) -> Formula:
        """解析析取 OR。

        如果只解析出一个子公式，就直接返回该子公式，避免生成多余的 BoolOr 包装。
        """
        values = [self.parse_and()]
        while self.match("or"):
            values.append(self.parse_and())
        if len(values) == 1:
            return values[0]
        return BoolOr(tuple(values))

    def parse_and(self) -> Formula:
        """解析合取 AND。

        AND 的优先级高于 OR，因此这里调用 `parse_unary_formula()` 作为子层级。
        """
        values = [self.parse_unary_formula()]
        while self.match("and"):
            values.append(self.parse_unary_formula())
        if len(values) == 1:
            return values[0]
        return BoolAnd(tuple(values))

    def parse_unary_formula(self) -> Formula:
        """解析 NOT、量词、括号、布尔常量或比较公式。

        这一层处理“公式级”的一元结构：
        - `not formula`
        - `forall/exists ...`
        - `(formula)`
        - `true/false`
        - 最后兜底为普通比较公式。
        """
        if self.match("not"):
            return BoolNot(self.parse_unary_formula())
        if self.peek("forall") or self.peek("exists"):
            return self.parse_quantified()
        if self.match("LPAREN"):
            inner = self.parse_implication()
            self.expect("RPAREN")
            return inner
        if self.peek("true"):
            self.expect("true")
            return BoolConst(True)
        if self.peek("false"):
            self.expect("false")
            return BoolConst(False)
        return self.parse_comparison()

    def parse_quantified(self) -> Formula:
        """解析 forall / exists 量词结构。

        支持的形态是：
        - `forall k in {0, 1, 2}: body`
        - `exists k in {0, 1, 2}: body`

        注意 domain 必须是有限集合，因为后续求值和 Z3 降阶都会把量词展开成有限合取/析取。
        """
        quantifier = self.expect("forall", "exists")
        variable = self.expect("IDENT").value
        self.expect("in")
        domain = self.parse_domain()
        self.expect("COLON")
        body = self.parse_implication()
        if quantifier.kind == "forall":
            return ForAll(variable=variable, domain=domain, body=body)
        return Exists(variable=variable, domain=domain, body=body)

    def parse_domain(self) -> tuple[Any, ...]:
        """解析量词的有限域，例如 {0, 1, 2}。

        domain 中支持数字、字符串和标识符。
        标识符会作为普通字符串保存，例如 `{SYN, ACK}` 会变成 `("SYN", "ACK")`。
        """
        self.expect("LBRACE")
        values: list[Any] = []
        while True:
            if self.peek("NUMBER"):
                token = self.expect("NUMBER")
                values.append(float(token.value) if "." in token.value else int(token.value))
            elif self.peek("STRING"):
                token = self.expect("STRING")
                values.append(token.value[1:-1])
            else:
                values.append(self.expect("IDENT").value)
            if not self.match("COMMA"):
                break
        self.expect("RBRACE")
        return tuple(values)

    def parse_comparison(self) -> Formula:
        """解析形如 lhs >= rhs 的原子比较。

        比较是最基础的谓词形态。
        左右两侧都先按 term 解析，因此可以支持算术项和函数调用。
        """
        left = self.parse_term()
        token = self.expect("EQ", "NE", "GT", "GE", "LT", "LE")
        right = self.parse_term()
        op_map = {
            "EQ": "=",
            "NE": "!=",
            "GT": ">",
            "GE": ">=",
            "LT": "<",
            "LE": "<=",
        }
        return Compare(op_map[token.kind], left, right)

    def parse_term(self) -> Term:
        """解析加减表达式。

        这一层处理 `+` 和 `-`，优先级低于乘除。
        例如 `a + b * c` 中，右侧 `b * c` 会先在 `parse_factor()` 里解析完成。
        """
        node = self.parse_factor()
        while self.peek("PLUS") or self.peek("MINUS"):
            op = self.expect("PLUS", "MINUS").value
            node = BinaryTerm(op, node, self.parse_factor())
        return node

    def parse_factor(self) -> Term:
        """解析乘除表达式。

        这一层处理 `*` 和 `/`，优先级高于加减。
        """
        node = self.parse_atom()
        while self.peek("STAR") or self.peek("SLASH"):
            op = self.expect("STAR", "SLASH").value
            node = BinaryTerm(op, node, self.parse_atom())
        return node

    def parse_atom(self) -> Term:
        """解析最小语法单元：常量、标识符、索引、函数调用、括号。

        atom 是 term 解析的最底层，支持：
        - `(term)`：括号项；
        - `-x`：一元负号，转换成 `-1 * x`；
        - 数字、字符串；
        - `name`：字段引用；
        - `family[index]`：上下文索引引用；
        - `func(arg1, arg2)`：函数调用。
        """
        if self.match("LPAREN"):
            inner = self.parse_term()
            self.expect("RPAREN")
            return inner
        if self.match("MINUS"):
            # 为了不单独引入 UnaryMinus 节点，把 -x 统一表示为 -1 * x。
            return BinaryTerm("*", Constant(-1), self.parse_atom())
        if self.peek("NUMBER"):
            token = self.expect("NUMBER")
            return Constant(float(token.value) if "." in token.value else int(token.value))
        if self.peek("STRING"):
            return Constant(self.expect("STRING").value[1:-1])
        ident = self.expect("IDENT").value
        if self.match("LBRACK"):
            # 方括号表示上下文族索引，例如 tcp.seq[k]。
            if self.peek("NUMBER"):
                token = self.expect("NUMBER")
                index: int | str = int(token.value)
            else:
                index = self.expect("IDENT").value
            self.expect("RBRACK")
            return IndexedRef(ident, index)
        if self.match("LPAREN"):
            # 标识符后跟括号表示函数调用，例如 min(a, b)。
            args: list[Term] = []
            if not self.peek("RPAREN"):
                args.append(self.parse_term())
                while self.match("COMMA"):
                    args.append(self.parse_term())
            self.expect("RPAREN")
            return FuncCall(ident, tuple(args))
        return SymbolRef(ident)

    def match(self, *kinds: str) -> Token | None:
        """若当前位置记号属于候选集合则消费并返回，否则返回 None。

        这是递归下降解析器最常用的“小步前进”方法。
        """
        if self.index >= len(self.tokens):
            return None
        token = self.tokens[self.index]
        if token.kind in kinds:
            self.index += 1
            return token
        return None

    def peek(self, kind: str) -> bool:
        """只看当前记号是否匹配，不前进游标。

        用于分支判断，例如先看是不是 `forall`，再决定是否进入量词解析。
        """
        return self.index < len(self.tokens) and self.tokens[self.index].kind == kind

    def expect(self, *kinds: str) -> Token:
        """强制要求当前位置出现某类记号，否则抛出可读错误。

        与 `match()` 的区别是：`match()` 失败返回 None，`expect()` 失败直接报错。
        这适合语法中“必须出现”的位置，例如量词里的 `in`、冒号、右括号。
        """
        token = self.match(*kinds)
        if token is None:
            expected = " or ".join(kinds)
            actual = self.tokens[self.index].kind if self.index < len(self.tokens) else "EOF"
            raise ValueError(f"Expected {expected}, got {actual}")
        return token


def parse_formula(text: str) -> Formula:
    """对外暴露的单入口解析函数。

    外部模块通常不直接实例化 `FormulaParser`，而是调用这个函数。
    """
    return FormulaParser(text).parse()
