"""NetNomos 配置模型定义。

这个模块定义了项目几乎所有“配置驱动”的输入结构。
项目的大部分输入不是散落的函数参数，而是通过 JSON 文件统一描述，然后在这里
被 Pydantic 校验成强类型对象。

从职责上看，这个模块主要做三件事：
1. 定义数据集配置 `DatasetSpec` 及其相关子模型；
2. 定义语法空间配置 `GrammarSpec` 及其相关子模型；
3. 提供配置文件的加载、写回和统一 JSON 序列化工具。

为什么这一步很重要：
- 它决定了“输入配置能长成什么样”
- 它决定了哪些字段是必填的，哪些字段是可选的
- 它决定了非法配置是在加载时就报错，还是拖到运行中才暴露

阅读建议：
1. 先看所有 Enum，理解系统有哪些“受限取值”
2. 再看 DatasetSpec 这一支，理解数据怎么描述
3. 再看 GrammarSpec 这一支，理解搜索空间怎么描述
4. 最后看 load_* / dump_* 这些 I/O 工具函数
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """所有配置模型的共同基类。

    这里最关键的是：
    - `extra="forbid"`：禁止 JSON 中出现未定义字段
      这样能避免用户把字段名写错却被静默忽略
    - `populate_by_name=True`：当字段定义了 alias 时，仍允许代码按真实字段名传值
      它主要影响“模型构造 / 赋值阶段”的入参解析；导出时是否使用 alias，
      则通常由 `model_dump(by_alias=True)` 这类调用参数决定

    换句话说，这个基类的目标不是“灵活”，而是“严格且可预期”。
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SourceType(str, Enum):
    """输入源的物理类型。

    - `AUTO`：根据输入路径后缀自动推断
    - `CSV`：显式指定为 CSV
    - `PCAP`：显式指定为 PCAP
    """

    AUTO = "auto"
    CSV = "csv"
    PCAP = "pcap"


class ValueType(str, Enum):
    """字段值类型。

    这个类型会影响很多后续行为，例如：
    - 谓词能否做大小比较
    - 常量如何采样
    - Theory 中如何选择 Z3 符号类型
    """

    INTEGER = "integer"
    REAL = "real"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    STRING = "string"


class FieldRole(str, Enum):
    """字段的语义角色。

    角色不是“物理类型”，而是“这个字段在语义上扮演什么角色”。
    它主要用于：
    - 字段选择器按语义筛字段
    - 限制哪些字段彼此可比较
    - 允许或禁止某些算术组合

    例如：
    - `SIZE` 表示长度、字节数、MTU 之类的量
    - `TIME` 表示时间或持续时长
    - `SEQUENCE` 表示序列号
    """

    SRC = "src"
    DST = "dst"
    PROTO = "proto"
    TIME = "time"
    SEQUENCE = "sequence"
    MEASUREMENT = "measurement"
    IDENTIFIER = "identifier"
    WINDOW = "window"
    COUNT = "count"
    SIZE = "size"
    FLAG = "flag"
    DERIVED = "derived"


class Comparator(str, Enum):
    """支持的比较运算符。

    这些值会出现在：
    - 谓词模板配置里
    - AST 的 Compare 节点里
    - DSL 文本解析结果里
    """

    EQ = "="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="


class ConstantKind(str, Enum):
    """字段预定义常量的用途分类。

    一个字段可以在配置里自带一些有语义含义的常量，后续 grammar 可以复用它们。
    常见场景：
    - `ASSIGNMENT`：离散映射值，如类别编码
    - `SCALAR`：乘法比例因子，如 `Packets * 65535`
    - `LIMIT`：阈值常量
    - `ADDITION`：加法偏移量，如 `seq + 1`
    """

    ASSIGNMENT = "assignment"
    SCALAR = "scalar"
    LIMIT = "limit"
    ADDITION = "addition"


class Aggregator(str, Enum):
    """聚合器名称。

    主要用于两类场景：
    - 量词投影（如 min / max）
    - 派生变量计算（如 avg / count_nonzero）
    """

    MIN = "min"
    MAX = "max"
    SUM = "sum"
    AVG = "avg"
    COUNT_NONZERO = "count_nonzero"
    EXISTS = "exists"
    FORALL = "forall"


class PreprocessKind(str, Enum):
    """支持的数据预处理步骤类型。

    这些值会驱动 `dataset.py` 里的预处理分支逻辑。
    每个枚举值都代表一种对 DataFrame 的处理动作：
    - `RENAME`：按 mapping 批量改列名
    - `DROP`：删除指定列
    - `CAST`：把列转换成指定 pandas dtype
    - `PARSE_HEX`：把十六进制文本解析成整数
    - `FILLNA`：用固定值填补缺失值
    - `MAP_VALUES`：按简单字典映射替换列值
    - `MAP_RULES`：按规则列表做更复杂的条件映射
    - `FILTER_EQUALS`：只保留列值等于指定值的行
    - `FILTER_IN`：只保留列值属于指定集合的行
    - `FILTER_PRESENT`：只保留列值存在且非空的行
    - `SORT`：按指定列排序
    """

    RENAME = "rename"
    DROP = "drop"
    CAST = "cast"
    PARSE_HEX = "parse_hex"
    FILLNA = "fillna"
    MAP_VALUES = "map_values"
    MAP_RULES = "map_rules"
    FILTER_EQUALS = "filter_equals"
    FILTER_IN = "filter_in"
    FILTER_PRESENT = "filter_present"
    SORT = "sort"


class DerivedOperation(str, Enum):
    """支持的派生变量计算操作。"""

    COPY = "copy"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    AVG = "avg"
    STD = "std"
    DIFF = "diff"
    RATIO = "ratio"
    COUNT_NONZERO = "count_nonzero"
    EXISTS = "exists"
    FORALL = "forall"


class LearnerKind(str, Enum):
    """规则学习器类型。"""

    HITTING_SET = "hitting-set"
    TREE = "tree"


class HittingSetBackend(str, Enum):
    """hitting-set 学习器的具体实现后端。"""

    AUTO = "auto"
    NATIVE = "native"
    PYTHON = "python"


class SourceSpec(StrictModel):
    """输入源说明。

    字段含义：
    - `type`：输入源类型
    - `path`：默认输入路径
    - `csv_read_options`：额外传给 pandas.read_csv 的参数
    """

    type: SourceType
    path: str | None = None
    csv_read_options: dict[str, Any] = Field(default_factory=dict)


class BoundsSpec(StrictModel):
    """字段数值边界元数据。

    当前更多是“描述性信息”，还不是强制约束。
    但它为后续潜在的静态检查或更强规则约束留出了空间。
    """

    lower: float | int | None = None
    upper: float | int | None = None


class FieldConstantSpec(StrictModel):
    """字段附带的可复用常量集合。"""

    kind: ConstantKind
    values: list[Any] = Field(default_factory=list)
    description: str = ""


class FieldSpec(StrictModel):
    """字段定义。

    这是数据集语义建模里最核心的结构之一。
    之后的很多模块都会依赖它：
    - `dataset.py` 根据它补齐字段元数据
    - `projection.py` 根据它选择字段和常量
    - `interpreter.py` 根据它做 enum label 渲染
    - `theory.py` 根据它决定字段的逻辑类型

    关键字段说明：
    - `name`：字段在系统内的规范名称
    - `source_name`：原始数据中的字段名，若不同于规范名可在加载时重命名
    - `value_type`：值类型
    - `roles`：语义角色列表
    - `bounds`：数值边界元数据
    - `domain`：离散值域
    - `constants`：可复用常量列表
    - `enum_labels`：原始值到可读标签的映射
    - `context_family` / `context_index`：窗口化字段所属族与索引位置
    """

    name: str
    source_name: str | None = None
    value_type: ValueType | None = None
    roles: list[FieldRole] = Field(default_factory=list)
    bounds: BoundsSpec | None = None
    domain: list[Any] | None = None
    constants: list[FieldConstantSpec] = Field(default_factory=list)
    enum_labels: dict[str, str] = Field(default_factory=dict)
    context_family: str | None = None
    context_index: int | None = None


class ContextWindowSpec(StrictModel):
    """上下文窗口配置。

    用途：把多行 / 多包展开成单个窗口样本。

    字段说明：
    - `size`：窗口大小，例如 3 表示每个窗口含 3 条记录
    - `stride`：窗口滑动步长
    - `partition_by`：分区字段，保证窗口不跨实体
    - `order_by`：窗口内排序字段
    - `column_template`：展开后列名模板，如 `{name}_ctx{index}`
    """

    size: int
    stride: int = 1
    partition_by: list[str] = Field(default_factory=list)
    order_by: list[str] = Field(default_factory=list)
    column_template: str = "{name}_ctx{index}"


class MappingRuleMode(str, Enum):
    """规则映射步骤支持的匹配模式。

    这些模式只在 preprocessing 的 `map_rules` 步骤中使用，
    由 `dataset.py::apply_mapping_rules()` 逐条执行。

    每种模式的含义：
    - `EQUALS`：当前值等于 `value` 时命中
    - `IN`：当前值出现在 `values` 列表中时命中
    - `RANGE`：当前值转成数字后落在 lower/upper 区间内时命中
    - `PREFIX`：当前字符串以 `value` 作为前缀时命中
    - `REGEX`：当前值转成字符串后匹配正则 `value` 时命中
    - `DEFAULT`：设置兜底输出值；只有前面和后面都没有规则命中时才返回它
    """

    EQUALS = "equals"
    IN = "in"
    RANGE = "range"
    PREFIX = "prefix"
    REGEX = "regex"
    DEFAULT = "default"


class MappingRuleSpec(StrictModel):
    """单条映射规则。

    例如你可以用它把：
    - 某些端口映射成端口类别
    - 某些 IP 前缀映射成子网类别
    - 某些范围值映射成桶

    字段含义：
    - `mode`：选择哪一种匹配方式
    - `output`：命中后替换成什么值
    - `value`：单值匹配、前缀匹配、正则匹配时使用的主参数
    - `values`：集合匹配 `IN` 使用的候选值列表
    - `lower` / `upper`：范围匹配 `RANGE` 使用的上下界
    - `inclusive_lower` / `inclusive_upper`：范围边界是否闭区间

    规则执行顺序由配置列表顺序决定。
    除 `DEFAULT` 外，第一条命中的规则会立即返回 `output`。
    """

    mode: MappingRuleMode
    output: Any
    value: Any | None = None
    values: list[Any] = Field(default_factory=list)
    lower: float | int | None = None
    upper: float | int | None = None
    inclusive_lower: bool = True
    inclusive_upper: bool = True


class PreprocessStepSpec(StrictModel):
    """单步预处理配置。

    这是 dataset preprocessing 流水线中的一个步骤描述。
    不同的 `kind` 会解释不同字段，例如：
    - `map_values` 主要看 `mapping`
    - `map_rules` 主要看 `rules`
    - `cast` 主要看 `dtype`
    - `sort` 主要看 `by`

    这些步骤会按配置文件中的顺序依次执行。
    因此前一步可以为后一步创建新列，也可能先过滤掉一部分行。
    """

    kind: PreprocessKind
    columns: list[str] = Field(default_factory=list)
    target_column: str | None = None
    mapping: dict[str, Any] = Field(default_factory=dict)
    rules: list[MappingRuleSpec] = Field(default_factory=list)
    value: Any | None = None
    dtype: str | None = None
    by: list[str] = Field(default_factory=list)


class DerivedVariableSpec(StrictModel):
    """派生变量定义。

    它告诉系统如何从已有字段构造新字段。
    例如：
    - 计算多个时间间隔的均值 / 标准差
    - 构造差值、比值
    - 统计某几个位置上是否存在非零值
    """

    name: str
    operation: DerivedOperation
    inputs: list[str] = Field(default_factory=list)
    value_type: ValueType
    roles: list[FieldRole] = Field(default_factory=lambda: [FieldRole.DERIVED])
    literal: Any | None = None
    numerator: str | None = None
    denominator: str | None = None
    description: str | None = None


class DatasetSpec(StrictModel):
    """数据集配置的顶层模型。

    这是 `examples/datasets/*.json` 对应的核心结构。

    它整体描述了：
    - 数据来自哪里
    - 字段如何解释
    - 是否做预处理
    - 是否做窗口化
    - 是否生成派生变量
    - 哪些字段被纳入或排除
    """

    name: str
    description: str = ""
    source: SourceSpec
    fields: list[FieldSpec] = Field(default_factory=list)
    include_fields: list[str] = Field(default_factory=list)
    exclude_fields: list[str] = Field(default_factory=list)
    entity_keys: list[str] = Field(default_factory=list)
    grouping_keys: list[str] = Field(default_factory=list)
    ordering_keys: list[str] = Field(default_factory=list)
    preprocessing: list[PreprocessStepSpec] = Field(default_factory=list)
    context_window: ContextWindowSpec | None = None
    derived_variables: list[DerivedVariableSpec] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keys(cls, data: Any) -> Any:
        """兼容旧版配置中的 `excluded_fields` 命名。

        旧配置可能使用：
        - `excluded_fields`

        新配置统一使用：
        - `exclude_fields`

        这里在真正进入模型校验之前做一次字段名归一化。
        如果新旧命名同时出现，则直接报错，避免歧义。
        """

        if not isinstance(data, dict):
            return data
        if "excluded_fields" in data:
            if "exclude_fields" in data:
                raise ValueError("Use only one of `exclude_fields` or legacy `excluded_fields`.")
            data = dict(data)
            data["exclude_fields"] = data.pop("excluded_fields")
        return data


class ConstantSelectorSpec(StrictModel):
    """常量选择器。

    它决定 grammar 在生成谓词时，常量从哪里来。

    常见模式：
    - `explicit`：直接使用 `values`
    - `domain`：从字段 domain 取值
    - `profile`：从数据统计中自动采样，如分位数 / top-k
    - `field_constants`：复用字段配置里的 constants
    """

    mode: Literal["explicit", "domain", "profile", "field_constants"] = "profile"
    values: list[Any] = Field(default_factory=list)
    kinds: list[ConstantKind] = Field(default_factory=list)
    top_k: int = 10
    quantiles: list[float] = Field(default_factory=lambda: [0.25, 0.5, 0.75, 0.9])


class VariableSelectorSpec(StrictModel):
    """字段选择器。

    它是 Grammar 里非常关键的构件，用于声明式筛选字段。

    可以按以下维度过滤：
    - `names`：显式列出字段名
    - `regex`：按字段名正则筛
    - `types`：按 ValueType 筛
    - `roles`：按 FieldRole 筛
    - `derived_only`：只要派生字段 / 排除派生字段
    - `context_family`：只保留某个窗口族
    - `window_only`：只要窗口字段 / 排除窗口字段
    - `exclude`：最终显式剔除
    """

    names: list[str] = Field(default_factory=list)
    regex: str | None = None
    types: list[ValueType] = Field(default_factory=list)
    roles: list[FieldRole] = Field(default_factory=list)
    derived_only: bool | None = None
    context_family: str | None = None
    window_only: bool | None = None
    exclude: list[str] = Field(default_factory=list)


class PredicateTermKind(str, Enum):
    """项模板的形状。

    用于表达谓词左右两侧可以长成什么样：
    - `FIELD`：单个字段
    - `CONSTANT`：单个常量
    - `SCALAR`：字段乘常量
    - `ADDITION`：字段加字段 / 字段加常量
    """

    FIELD = "field"
    CONSTANT = "constant"
    SCALAR = "scalar"
    ADDITION = "addition"


class TermTemplateSpec(StrictModel):
    """项模板定义。

    这个模型主要出现在 predicate template 的 `lhs_term` 和 `rhs_term` 中，
    用于描述比较式两边的“项结构”。
    """

    kind: PredicateTermKind = PredicateTermKind.FIELD
    field: VariableSelectorSpec | None = None
    other_field: VariableSelectorSpec | None = None
    constant: ConstantSelectorSpec | None = None
    allow_same_field: bool = False
    description: str = ""


class PredicateTemplateSpec(StrictModel):
    """谓词模板定义。

    一个谓词模板描述“允许生成哪一类原子条件”。
    例如：
    - 字段 vs 字段
    - 字段 vs 常量
    - 算术项 vs 算术项

    这个结构是 grammar search space 的核心之一。
    """

    name: str
    lhs: VariableSelectorSpec | None = None
    operators: list[Comparator]
    rhs_field: VariableSelectorSpec | None = None
    rhs_constant: ConstantSelectorSpec | None = None
    lhs_term: TermTemplateSpec | None = None
    rhs_term: TermTemplateSpec | None = None
    allow_same_field: bool = False
    description: str = ""

    @model_validator(mode="after")
    def validate_shape(self) -> "PredicateTemplateSpec":
        """校验谓词模板的结构是否合法。

        这里强制三条规则：
        1. 左边必须有内容：`lhs` 或 `lhs_term` 至少一个
        2. 右边必须正好指定一种来源：字段 / 常量 / 项
        3. 不能同时指定多个右侧来源，否则语义会歧义
        """

        if self.lhs is None and self.lhs_term is None:
            raise ValueError("Predicate templates must define either `lhs` or `lhs_term`.")
        rhs_count = int(self.rhs_field is not None) + int(self.rhs_constant is not None) + int(self.rhs_term is not None)
        if rhs_count == 0:
            raise ValueError("Predicate templates must define one right-hand side selector or term.")
        if rhs_count > 1:
            raise ValueError("Predicate templates may define only one of `rhs_field`, `rhs_constant`, or `rhs_term`.")
        return self


class QuantifierTemplateSpec(StrictModel):
    """量词模板定义。

    用于在窗口字段族上声明：
    - `forall`
    - `exists`
    这类约束，并结合常量选择器生成量词相关谓词。
    """

    name: str
    quantifier: Literal["forall", "exists"]
    selector: VariableSelectorSpec
    operators: list[Comparator]
    constant: ConstantSelectorSpec
    aggregator_projection: Aggregator | None = None
    description: str = ""


class GrammarSpec(StrictModel):
    """语法配置的顶层模型。

    这是 `examples/grammars/*.json` 对应的核心结构。

    它整体描述了：
    - 搜索空间里允许哪些谓词模板
    - 是否允许量词模板
    - 规则最大复杂度
    - 最多保留多少规则
    """

    name: str
    description: str = ""
    max_clause_size: int = 4
    max_rules: int = 250
    predicate_templates: list[PredicateTemplateSpec] = Field(default_factory=list)
    quantifier_templates: list[QuantifierTemplateSpec] = Field(default_factory=list)


def load_model(model_type: type[BaseModel], path: str | Path) -> BaseModel:
    """从 JSON 文件读取并校验任意 Pydantic 模型。

    这里是最底层的通用加载工具。
    它会直接调用 Pydantic 的 `model_validate_json()`，因此：
    - 文件格式错误会报错
    - 字段类型不匹配会报错
    - 多余字段也会报错（因为继承了 StrictModel）
    """

    return model_type.model_validate_json(Path(path).read_text())


def dump_model(model: BaseModel, path: str | Path) -> None:
    """把 Pydantic 模型写回格式化 JSON 文件。"""

    Path(path).write_text(model.model_dump_json(indent=2))


def load_dataset_spec(path: str | Path) -> DatasetSpec:
    """加载 `DatasetSpec`。

    这是对 `load_model()` 的类型化封装，让调用者返回值更明确。
    """

    return load_model(DatasetSpec, path)


def load_grammar_spec(path: str | Path) -> GrammarSpec:
    """加载 `GrammarSpec`。"""

    return load_model(GrammarSpec, path)


def json_dumps(data: Any) -> str:
    """统一项目内 JSON 文本格式。

    主要保证：
    - 缩进一致
    - 键排序一致
    - 不可直接序列化的值转成字符串
    """

    return json.dumps(data, indent=2, sort_keys=True, default=str)
