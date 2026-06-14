"""数据集加载与准备。

这个模块负责把“原始输入文件”整理成系统内部统一使用的 `PreparedDataset`。

为什么需要这一层：
- 学习器、谓词投影器、理论验证器都不想各自重复做数据清洗
- CSV 和 PCAP 的输入形态差异很大，需要先规整成统一 DataFrame
- grammar 展开阶段依赖大量字段元信息，因此不能只保留裸表格

主流程可以概括为：
1. 解析输入源类型与路径；
2. 读取原始数据；
3. 执行字段改名与预处理；
4. 执行 include/exclude 字段选择；
5. 删除不完整列并校验关键列；
6. 生成基础字段元数据；
7. 如果需要，则把行序列展开成上下文窗口；
8. 计算派生变量；
9. 构建值域目录、上下文族索引和派生来源信息；
10. 打包成 `PreparedDataset` 返回给后续模块。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

from netnomos.logging_utils import get_logger
from netnomos.specs import (
    DatasetSpec,
    DerivedOperation,
    DerivedVariableSpec,
    FieldRole,
    FieldSpec,
    MappingRuleMode,
    PreprocessKind,
    SourceType,
    ValueType,
)


CTX_PATTERNS = [
    # 匹配 snake / dot 风格窗口列名，例如：
    # - tcp.seq_ctx0  -> base=tcp.seq, index=0
    # - frame.len_ctx2 -> base=frame.len, index=2
    #
    # `base` 表示这个窗口列来自哪个原始字段族；
    # `index` 表示它是窗口里的第几个位置。
    re.compile(r"^(?P<base>.+)_ctx(?P<index>\d+)$"),
    # 匹配 camel/Pascal 风格窗口列名，例如：
    # - tcpSeqCtx0 -> base=tcpSeq, index=0
    # - BytesCtx3  -> base=Bytes, index=3
    #
    # 保留这一种格式是为了兼容外部数据源可能已经展开好的窗口列。
    re.compile(r"^(?P<base>.+)Ctx(?P<index>\d+)$"),
]
log = get_logger("dataset")


@dataclass(slots=True)
class PreparedDataset:
    """准备完成后的数据集对象。

    这是学习器、谓词投影器、理论验证器共享的标准输入。

    可以把它理解成“原始数据 + 结构化元数据 + 运行期辅助索引”的组合：
    - `dataframe`：真正参与后续计算的二维表
    - `field_specs`：每个字段的语义说明，projection/theory 都会用到
    - `value_catalog`：每个字段可枚举值的目录，常量选择器会用到
    - `derived_provenance`：派生字段是怎么来的，便于工件落盘和解释
    - `context_families`：窗口字段按 family 分组后的索引，量词模板会用到
    - `excluded_fields`：哪些列被剔除了以及原因，便于回溯数据损失
    """

    spec: DatasetSpec
    source_type: SourceType
    dataframe: pd.DataFrame
    field_specs: dict[str, FieldSpec]
    value_catalog: dict[str, list[Any]]
    derived_provenance: dict[str, dict[str, Any]]
    context_families: dict[str, list[str]]
    # 用户在 DatasetSpec.exclude_fields 中显式要求排除、并且在当前 DataFrame 中真实存在的字段。
    # 它和 `excluded_fields` 不同：前者来自用户配置，后者来自系统自动剔除不完整列。
    # 后续 artifact 展示会把这类字段放在前面，保留“用户主动排除”的语义。
    configured_exclude_fields: list[str]
    excluded_fields: dict[str, str]

    @property
    def effective_excluded_fields(self) -> list[str]:
        """返回最终被排除的所有字段名，且保持配置排除字段优先。

        这里把两类排除来源合并：
        - 用户在 dataset spec 中显式 `exclude_fields`
        - 系统因为列不完整而自动剔除的字段

        合并时保留“用户显式排除优先”的顺序，便于日志和 artifact 展示。
        """
        seen = set(self.configured_exclude_fields)
        return [
            *self.configured_exclude_fields,
            *(name for name in self.excluded_fields if name not in seen),
        ]


def prepare_dataset(spec: DatasetSpec, input_path: str | Path | None = None, limit: int | None = None) -> PreparedDataset:
    """把数据集规范和原始输入转换为 `PreparedDataset`。

    这是本模块最重要的总入口。它把多个“彼此独立的小步骤”按固定顺序串起来。

    这里的顺序不能随意交换，原因例如：
    - 预处理通常依赖原始列名或重命名后的列名
    - 字段选择必须在预处理之后，否则可能选不到新列
    - 上下文窗口会改变表结构，因此要在基础字段元数据确定后再做
    - 值目录与上下文族索引必须基于最终 DataFrame 构建
    """
    source_type, path = resolve_source(spec, input_path)
    log.info("Loading dataset '%s' from %s as %s", spec.name, path, source_type.value)
    if source_type == SourceType.CSV:
        # CSV 读取参数完全由 spec.source.csv_read_options 驱动，
        # 这里额外允许用 `limit` 临时裁切前 N 行，便于调试或快速实验。
        read_options = dict(spec.source.csv_read_options)
        if limit is not None:
            read_options["nrows"] = limit
        frame = pd.read_csv(path, **read_options)
    else:
        # PCAP 读取不会走 pandas，而是进入下面的 `read_pcap()` 逐包解析。
        frame = read_pcap(path, limit=limit)

    # 字段级重命名先于一般预处理执行。
    # 这样配置里的 `FieldSpec.name` 能尽早成为系统内部统一字段名。
    frame = apply_source_renames(frame, spec)
    # 预处理阶段可以新增列、改写列、过滤行、排序等。
    frame = apply_preprocessing(frame, spec)
    # include/exclude 是“保留哪些列进入建模阶段”的第一道显式筛选。
    # `configured_exclude_fields` 只记录配置里明确 exclude 且实际存在的字段，
    # 用于和后续因 NaN/空字符串被自动剔除的字段区分开。
    frame, configured_exclude_fields = apply_field_selection(frame, spec)
    # 不完整列会在这里被自动剔除，因为后续比较/统计非常依赖列完整性。
    frame, excluded_fields = drop_incomplete_columns(frame)
    # 某些列即使整体策略是“可排除”，对上下文窗口来说仍然可能是硬依赖。
    validate_required_columns(frame, spec, excluded_fields)

    # 基础字段元数据以当前 DataFrame 为准建立。
    field_specs = initial_field_specs(spec, frame)
    if spec.context_window is not None:
        # 上下文窗口会把多行样本折叠成一行，因此字段定义也要同步复制成 *_ctxN。
        frame, field_specs = apply_context_windows(frame, field_specs, spec)

    # 派生变量会修改 DataFrame 和字段集合，因此放在窗口展开之后。
    frame, derived_provenance, field_specs = apply_derived_variables(frame, field_specs, spec.derived_variables)
    # 对于外部已经展开好的 *_ctxN 列，尝试从列名中自动补 family/index。
    field_specs = enrich_context_families(field_specs, frame.columns)
    # 为 grammar 常量选择器准备字段值目录。
    value_catalog = build_value_catalog(frame, field_specs)
    # 对离散字段回填 domain，便于后续 domain 模式常量枚举。
    field_specs = attach_domains(field_specs, value_catalog)
    # 量词模板依赖这个 family -> ordered field list 的映射。
    context_families = build_context_families(field_specs)
    return PreparedDataset(
        spec=spec,
        source_type=source_type,
        dataframe=frame,
        field_specs=field_specs,
        value_catalog=value_catalog,
        derived_provenance=derived_provenance,
        context_families=context_families,
        configured_exclude_fields=configured_exclude_fields,
        excluded_fields=excluded_fields,
    )


def resolve_source(spec: DatasetSpec, input_path: str | Path | None = None) -> tuple[SourceType, Path]:
    """确定本次运行的输入路径和实际源类型。

    这里有两层决策：
    - 路径优先使用调用方传入的 `input_path`
    - 否则回退到 dataset spec 里写死的默认路径

    源类型如果是 `auto`，就根据文件后缀推断真实类型。
    """
    path = Path(input_path or spec.source.path or "")
    if spec.source.type == SourceType.AUTO:
        source_type = infer_source_type(path)
        if source_type is None:
            raise ValueError(
                "Dataset source.type='auto' requires a path ending in .csv, .pcap, .pcapng, or .cap."
            )
        return source_type, path
    return spec.source.type, path


def infer_source_type(path: Path) -> SourceType | None:
    """根据文件后缀推断源类型。

    这里故意只支持少数明确后缀，避免把任意未知文件误判成可解析格式。
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return SourceType.CSV
    if suffix in {".pcap", ".pcapng", ".cap"}:
        return SourceType.PCAP
    return None


def apply_source_renames(frame: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    """先处理字段级 `source_name -> name` 的标准化改名。

    这一步服务于这样一种场景：
    - 原始 CSV/PCAP 里的列名不够规范
    - 但项目内部希望统一使用更稳定的字段名

    例如原始列叫 `tcp.seq_raw`，系统内部想统一成 `tcp.seq`。
    """
    rename_map = {
        field.source_name: field.name
        for field in spec.fields
        if field.source_name and field.source_name in frame.columns and field.source_name != field.name
    }
    if rename_map:
        frame = frame.rename(columns=rename_map)
    return frame


def apply_preprocessing(frame: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    """按配置顺序执行预处理步骤。

    顺序很重要，因为后续步骤可能依赖前一步创建的新列或过滤结果。

    每个 `step` 都来自 `DatasetSpec.preprocessing`，类型是 `PreprocessStepSpec`。
    `step.kind` 决定本次预处理动作属于哪一种 `PreprocessKind`。

    这段逻辑可以理解成一个小型 DataFrame 预处理流水线：
    - 改列名：让外部字段名适配内部规范
    - 改列值：做类型转换、十六进制解析、缺失值填充、值映射
    - 过滤行：只保留满足条件的样本
    - 排序行：为后续窗口化或时序处理提供稳定顺序
    """
    for step in spec.preprocessing:
        if step.kind == PreprocessKind.RENAME:
            # RENAME：按 `step.mapping` 批量重命名列。
            #
            # 典型配置含义：
            # {
            #   "kind": "rename",
            #   "mapping": {"old_col": "new_col"}
            # }
            #
            # 注意它和 `apply_source_renames()` 的区别：
            # - `apply_source_renames()` 来自 FieldSpec.source_name -> FieldSpec.name
            # - 这里的 RENAME 来自 preprocessing 中显式配置的任意列名映射
            frame = frame.rename(columns=step.mapping)
        elif step.kind == PreprocessKind.DROP:
            # DROP：删除 `step.columns` 中列名命中的列。
            #
            # 这常用于去掉明显不会参与学习的辅助列、备注列、临时列。
            # `errors="ignore"` 允许配置里的待删列在当前数据里不存在，
            # 这样不同数据版本可以复用同一份 preprocessing 配置。
            frame = frame.drop(columns=[c for c in step.columns if c in frame.columns], errors="ignore")
        elif step.kind == PreprocessKind.CAST:
            # CAST：把指定列转换成 `step.dtype` 指定的 pandas/numpy dtype。
            #
            # 例如把 "1"/"2" 这样的字符串列转成 int，
            # 或把原本 object 类型的列转成 float。
            # 如果某个值无法转换，pandas 会在 astype() 阶段抛错。
            for column in step.columns:
                if column in frame.columns:
                    frame[column] = frame[column].astype(step.dtype)
        elif step.kind == PreprocessKind.PARSE_HEX:
            # PARSE_HEX：把十六进制或十进制文本解析为整数。
            #
            # 典型场景是网络抓包导出的字段可能长成 "0x0012"，
            # 但后续比较和常量选择需要它是数值。
            for column in step.columns:
                if column in frame.columns:
                    frame[column] = frame[column].apply(parse_hex_value)
        elif step.kind == PreprocessKind.FILLNA:
            # FILLNA：把指定列中的缺失值填成 `step.value`。
            #
            # 注意后面 `drop_incomplete_columns()` 会剔除仍包含 NaN 的列；
            # 因此如果某些缺失值有合理默认值，需要在这里先填掉。
            for column in step.columns:
                if column in frame.columns:
                    frame[column] = frame[column].fillna(step.value)
        elif step.kind == PreprocessKind.MAP_VALUES:
            # MAP_VALUES：用一个简单字典做值替换。
            #
            # 例如把协议名映射成编码：
            # {"TCP": 6, "UDP": 17}
            #
            # 这个分支适合“精确值 -> 新值”的直接替换。
            for column in step.columns:
                if column in frame.columns:
                    # 未命中的值保持原样，避免 map 后大量 NaN。
                    mapped = frame[column].map(step.mapping).fillna(frame[column])
                    frame[resolve_preprocess_target(step, column)] = mapped
        elif step.kind == PreprocessKind.MAP_RULES:
            # MAP_RULES：按规则列表做条件映射，比 MAP_VALUES 更灵活。
            #
            # 每条规则可以表达 equals / in / prefix / regex / range / default。
            # 适合把复杂原始值归并成少量类别，例如把多个协议名归成同一类。
            for column in step.columns:
                if column in frame.columns:
                    mapped = frame[column].apply(lambda value: apply_mapping_rules(value, step.rules))
                    frame[resolve_preprocess_target(step, column)] = mapped
        elif step.kind == PreprocessKind.FILTER_EQUALS:
            # FILTER_EQUALS：只保留 `column == step.value` 的行。
            #
            # 这会改变样本数量，常用于只保留某个协议、某类事件或某个标签。
            for column in step.columns:
                if column in frame.columns:
                    frame = frame.loc[frame[column] == step.value].copy()
        elif step.kind == PreprocessKind.FILTER_IN:
            # FILTER_IN：只保留 `column` 的值属于 `step.value` 集合的行。
            #
            # 例如只保留 protocol in ["TCP", "UDP"]。
            # 这里要求 `step.value` 是 pandas `isin()` 可以接受的集合型对象。
            for column in step.columns:
                if column in frame.columns:
                    frame = frame.loc[frame[column].isin(step.value)].copy()
        elif step.kind == PreprocessKind.FILTER_PRESENT:
            # FILTER_PRESENT：只保留指定列“有值”的行。
            #
            # 对数值列来说，通常就是非 NaN；
            # 对字符串列来说，还要求去掉空白后不是空串。
            for column in step.columns:
                if column in frame.columns:
                    # “present” 不只是不为 NaN，还包括字符串不为空。
                    frame = frame.loc[is_present_value_series(frame[column])].copy()
        elif step.kind == PreprocessKind.SORT:
            # SORT：按 `step.by` 排序；若没写 by，则退回使用 `step.columns`。
            #
            # 排序本身不改字段值，但会影响后续窗口化。
            # 例如按时间戳排序后再做 context_window，窗口里的 ctx0/ctx1 才有时序意义。
            by = step.by or step.columns
            if by:
                frame = frame.sort_values(by=by)
        else:
            # 理论上 Pydantic/Enum 已经限制了合法 kind。
            # 这里保留防御性错误，避免未来新增枚举但忘记实现执行分支。
            raise ValueError(f"Unsupported preprocessing step: {step.kind}")
    return frame.reset_index(drop=True)


def apply_field_selection(frame: pd.DataFrame, spec: DatasetSpec) -> tuple[pd.DataFrame, list[str]]:
    """执行 include/exclude 变量选择。

    注意这里的选择发生在“列维度”，不是行维度：
    - `include_fields` 表示只保留这些列
    - `exclude_fields` 表示从当前候选列里删掉这些列

    返回值除了裁切后的 DataFrame，还会返回“配置中显式排除且实际命中的列”，
    便于后续 artifact/日志展示。

    这个返回列表就是 `configured_exclude_fields`。它只表达用户配置意图，
    不包含系统后续因为缺失值、空字符串等原因自动剔除的列。
    """
    selected = list(frame.columns)
    if spec.include_fields:
        missing = [name for name in spec.include_fields if name not in frame.columns]
        if missing:
            raise ValueError(f"Included fields not found after preprocessing: {missing}")
        selected = [name for name in spec.include_fields if name in frame.columns]
    configured_exclude_fields: list[str] = []
    if spec.exclude_fields:
        exclude_set = set(spec.exclude_fields)
        # 这里只记录“配置里要求排除、并且当前数据里确实存在”的字段。
        # 若配置中写了一个不存在的字段，它不会出现在记录里，因为没有实际从表中移除。
        configured_exclude_fields = [name for name in frame.columns if name in exclude_set]
        selected = [name for name in selected if name not in exclude_set]
    return frame[selected].copy(), configured_exclude_fields


def initial_field_specs(spec: DatasetSpec, frame: pd.DataFrame) -> dict[str, FieldSpec]:
    """构建初始字段元数据。

    配置中显式声明的字段优先；未声明但实际存在的列会自动推断类型补上。
    """
    # 先吃掉配置里已经明确定义过的字段。
    resolved = {field.name: field for field in spec.fields if field.name in frame.columns}
    for column in frame.columns:
        if column not in resolved:
            # 对“配置里没声明但数据里真实存在”的列，自动补一个最小 FieldSpec，
            # 这样后续 projection/theory 不会因为缺字段元信息而失效。
            resolved[column] = FieldSpec(name=column, value_type=infer_value_type(frame[column]))
    return resolved


def infer_value_type(series: pd.Series) -> ValueType:
    """根据 Pandas 列类型和基数启发式推断字段值类型。

    这里不是严格的数据模式推断器，而是“足够服务规则学习”的轻量启发式：
    - bool / int / float 直接映射
    - 其他对象列若唯一值较少，则视作 categorical
    - 否则按 string 处理
    """
    if pd.api.types.is_bool_dtype(series):
        return ValueType.BOOLEAN
    if pd.api.types.is_integer_dtype(series):
        return ValueType.INTEGER
    if pd.api.types.is_float_dtype(series):
        return ValueType.REAL
    nunique = series.nunique(dropna=True)
    if nunique <= 32:
        return ValueType.CATEGORICAL
    return ValueType.STRING


def apply_context_windows(
    frame: pd.DataFrame,
    field_specs: dict[str, FieldSpec],
    spec: DatasetSpec,
) -> tuple[pd.DataFrame, dict[str, FieldSpec]]:
    """把原始行序列转成滑动窗口样本。

    输入是一张“每行一个时刻/一个包/一个事件”的表；
    输出是一张“每行一个窗口”的表。

    例如窗口大小为 3 时，一行输出会展开成：
    - tcp.seq_ctx0
    - tcp.seq_ctx1
    - tcp.seq_ctx2

    同时字段元数据也要同步复制，并补上：
    - `context_family`
    - `context_index`
    - `FieldRole.WINDOW`
    """
    ctx = spec.context_window
    assert ctx is not None
    # 先按 partition/order 排序，保证同一个实体内窗口顺序稳定。
    ordered = frame.sort_values(by=ctx.partition_by + ctx.order_by if ctx.order_by else ctx.partition_by or frame.columns[:1].tolist())
    # 若没有 partition_by，则整张表视作一个整体序列；
    # 否则每个 partition 内独立滑窗，避免不同实体之间的行互相串窗。
    groups = [(None, ordered)] if not ctx.partition_by else list(ordered.groupby(ctx.partition_by, sort=False))
    rows: list[dict[str, Any]] = []
    for _, group in groups:
        group = group.reset_index(drop=True)
        for start in range(0, len(group) - ctx.size + 1, ctx.stride):
            window = group.iloc[start:start + ctx.size]
            row: dict[str, Any] = {}
            for offset in range(ctx.size):
                # 一个窗口中的每个偏移都会展开成单独列，例如 tcp.seq_ctx0/tcp.seq_ctx1。
                entry = window.iloc[offset]
                for column, value in entry.items():
                    row[ctx.column_template.format(name=column, index=offset)] = value
            rows.append(row)
    new_specs: dict[str, FieldSpec] = {}
    for name, base_field in field_specs.items():
        for offset in range(ctx.size):
            new_name = ctx.column_template.format(name=name, index=offset)
            new_specs[new_name] = base_field.model_copy(
                update={
                    "name": new_name,
                    "context_family": name,
                    "context_index": offset,
                    "roles": list(dict.fromkeys([*base_field.roles, FieldRole.WINDOW])),
                }
            )
    windowed = pd.DataFrame(rows, columns=list(new_specs))
    return windowed, new_specs


def apply_derived_variables(
    frame: pd.DataFrame,
    field_specs: dict[str, FieldSpec],
    derived_specs: list[DerivedVariableSpec],
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]], dict[str, FieldSpec]]:
    """按配置计算派生变量，并记录来源信息。

    派生变量可以理解成“由已有列计算出来的新列”。
    例如：
    - 用多个窗口字段计算平均值
    - 用两个字段计算差值或比值
    - 统计一组字段里有多少个非零值

    这些新列和原始列一样，后续也可能参与：
    - 字段选择
    - grammar 谓词生成
    - theory 公式求值
    - learner 规则学习

    这里会同时更新三份状态：
    - `frame`：新增实际计算出来的列
    - `field_specs`：为新列补元数据
    - `provenance`：记录这个派生列的声明式来源，便于追溯和落盘

    返回三份状态的原因是：
    - DataFrame 需要真实列值
    - field_specs 需要知道新列的类型和角色
    - provenance 需要保留“这个新列怎么来的”，供 artifacts/debug 使用
    """
    # provenance 的结构是：
    # {
    #   "derived_column_name": {原始 DerivedVariableSpec 的 JSON 形式}
    # }
    # 它不参与计算本身，主要用于输出工件和后续排查。
    provenance: dict[str, dict[str, Any]] = {}
    for derived in derived_specs:
        # 先做引用完整性检查，避免派生计算在中途才因为列不存在而崩掉。
        #
        # 派生变量可能通过三种字段引用已有列：
        # - derived.inputs：大多数操作使用的输入列列表
        # - derived.numerator：ratio 操作可显式指定的分子列
        # - derived.denominator：ratio 操作可显式指定的分母列
        #
        # 这里把三类引用统一摊平成一个列表，再检查它们是否都还在 frame 中。
        # 注意此时 frame 已经经过预处理、字段选择、缺失列剔除和可选窗口展开。
        missing = [
            name
            for name in [*derived.inputs, *( [derived.numerator] if derived.numerator else [] ), *( [derived.denominator] if derived.denominator else [] )]
            if name not in frame.columns
        ]
        if missing:
            # 如果依赖列不存在，继续计算会得到更难理解的 pandas 错误。
            # 因此这里直接抛出带派生变量名和缺失列名的业务错误。
            raise ValueError(
                f"Derived variable '{derived.name}' references unavailable columns: {sorted(set(missing))}"
            )
        # 真正执行派生列计算。
        # compute_derived_column() 会根据 derived.operation 分派到 copy/sum/min/max/avg/ratio 等 pandas 操作。
        # 返回值是一列 Series，直接挂到 frame[derived.name] 上，成为新的 DataFrame 列。
        frame[derived.name] = compute_derived_column(frame, derived)
        # 给新列补 FieldSpec。
        #
        # 后续 projection/theory 不直接靠 DataFrame dtype 猜语义，
        # 而是主要看 FieldSpec.value_type 和 FieldSpec.roles。
        # 因此派生列必须和原始字段一样登记到 field_specs 中。
        field_specs[derived.name] = FieldSpec(
            name=derived.name,
            value_type=derived.value_type,
            roles=derived.roles,
        )
        # 记录派生变量的声明式来源。
        #
        # mode="json" 会把 Enum 等对象转成适合 JSON 落盘的值，
        # 便于 _write_artifacts() 输出 derived_variables.json。
        provenance[derived.name] = derived.model_dump(mode="json")
    # 返回更新后的三份状态，让 prepare_dataset() 继续构建 value_catalog、domain 和 context_families。
    return frame, provenance, field_specs


def compute_derived_column(frame: pd.DataFrame, spec: DerivedVariableSpec) -> pd.Series:
    """执行单个派生变量的计算。

    这里实现的是 `DerivedOperation` 到 pandas 列运算的直接映射。
    设计目标是：
    - 简单透明
    - 每种 operation 都对应可预测的 DataFrame 操作
    - 尽量不引入额外魔法行为
    """
    if spec.operation == DerivedOperation.COPY:
        return frame[spec.inputs[0]]
    if spec.operation == DerivedOperation.SUM:
        return frame[spec.inputs].sum(axis=1)
    if spec.operation == DerivedOperation.MIN:
        return frame[spec.inputs].min(axis=1)
    if spec.operation == DerivedOperation.MAX:
        return frame[spec.inputs].max(axis=1)
    if spec.operation == DerivedOperation.AVG:
        return frame[spec.inputs].mean(axis=1)
    if spec.operation == DerivedOperation.STD:
        return frame[spec.inputs].std(axis=1, ddof=0)
    if spec.operation == DerivedOperation.DIFF:
        return frame[spec.inputs[0]] - frame[spec.inputs[1]]
    if spec.operation == DerivedOperation.RATIO:
        # 分母为 0 时统一转成 NaN，避免无穷值污染后续统计。
        denom = frame[spec.denominator or spec.inputs[1]].replace(0, np.nan)
        return frame[spec.numerator or spec.inputs[0]] / denom
    if spec.operation == DerivedOperation.COUNT_NONZERO:
        return (frame[spec.inputs] != 0).sum(axis=1)
    if spec.operation == DerivedOperation.EXISTS:
        return (frame[spec.inputs] != 0).any(axis=1).astype(int)
    if spec.operation == DerivedOperation.FORALL:
        return (frame[spec.inputs] != 0).all(axis=1).astype(int)
    raise ValueError(f"Unsupported derived operation: {spec.operation}")


def build_value_catalog(frame: pd.DataFrame, field_specs: dict[str, FieldSpec]) -> dict[str, list[Any]]:
    """为每个字段建立去重后的值目录，供 domain/profile 常量选择使用。

    这个目录不是为了完整统计分析，而是为了给 projection 阶段提供“可选常量池”。
    因此：
    - 对离散字段更关注 unique 值
    - 对数值字段保留去重后的取值集合
    - 如果字段已经在 spec 中声明了 domain，则优先尊重人工定义

    输出结构类似：
    {
        "ip.proto": [6, 17],
        "tcp.flags": [2, 16, 18],
        "service": ["dns", "http", "https"],
    }

    后续 `projection.py` 中的 `ConstantSelectorSpec(mode="domain")`
    或部分 profile 逻辑会基于这些候选值生成字段-常量谓词。
    """
    # catalog 的 key 是字段名，value 是这个字段可供后续枚举/采样的候选值列表。
    catalog: dict[str, list[Any]] = {}
    for name, field in field_specs.items():
        # field_specs 里可能有些字段元数据并不对应当前 DataFrame 的实际列。
        # 例如某些字段被预处理、字段选择或缺失列剔除阶段移除了。
        # 这些字段没有真实列值可统计，因此跳过。
        if name not in frame.columns:
            continue
        if field.domain is not None:
            # 如果配置里已经显式声明了 domain，就直接使用人工声明的值域。
            #
            # 这样做的原因是：人工 domain 可能比当前样本中出现过的值更完整。
            # 例如当前小样本只出现 TCP，但配置知道合法协议还包括 UDP/ICMP。
            catalog[name] = list(field.domain)
            continue

        # 没有人工 domain 时，就从当前 DataFrame 的实际列值中提取候选值。
        # NaN 不适合作为规则常量，因此先去掉。
        series = frame[name].dropna()
        if field.value_type in {ValueType.CATEGORICAL, ValueType.STRING, ValueType.BOOLEAN}:
            # 离散/字符串/布尔字段通常用于等值类谓词。
            # 这里只需要收集出现过的不同值，例如 protocol in {"TCP", "UDP"}。
            catalog[name] = sorted(series.unique().tolist())
        else:
            # 数值字段也保留去重后的候选值。
            # 后续 profile 模式通常还会基于原始 series 计算分位数等统计常量；
            # 这里的 catalog 仍可服务 domain 类枚举或调试输出。
            catalog[name] = sorted(series.drop_duplicates().tolist())
    return catalog


def attach_domains(field_specs: dict[str, FieldSpec], value_catalog: dict[str, list[Any]]) -> dict[str, FieldSpec]:
    """给离散型字段补齐 domain，便于后续枚举常量。

    只对离散/字符串/布尔字段做自动回填，
    避免给连续数值字段塞入过大的显式 domain。
    """
    for name, field in list(field_specs.items()):
        if field.domain is not None or name not in value_catalog:
            continue
        if field.value_type in {ValueType.CATEGORICAL, ValueType.STRING, ValueType.BOOLEAN}:
            field_specs[name] = field.model_copy(update={"domain": value_catalog[name]})
    return field_specs


def apply_mapping_rules(value: Any, rules: list[Any]) -> Any:
    """按顺序应用映射规则，遇到首个命中规则即返回。

    这里的行为类似一个小型 rule engine：
    - 规则按配置顺序生效
    - 一旦命中就停止
    - `DEFAULT` 只负责更新兜底返回值，不会立即短路

    这个函数通常由 preprocessing 的 `MAP_RULES` 分支调用。
    它的输入是单个单元格值，输出是映射后的新值。

    和 `MAP_VALUES` 的区别：
    - `MAP_VALUES` 是简单字典替换，只能做精确 key 匹配
    - `MAP_RULES` 可以做等值、集合、前缀、正则、数值区间和默认值映射
    """
    # 默认情况下，如果没有任何规则命中，就保持原值不变。
    # 如果规则列表里出现 DEFAULT，则把兜底值改成 DEFAULT.output。
    default_value = value
    for rule in rules:
        if rule.mode == MappingRuleMode.DEFAULT:
            # DEFAULT：设置兜底返回值，但不立即返回。
            #
            # 这样允许 DEFAULT 写在规则列表前面或中间：
            # - 后续如果有更具体的规则命中，会返回具体规则的 output
            # - 如果后续没有任何规则命中，最后才返回 default_value
            default_value = rule.output
            continue
        if rule.mode == MappingRuleMode.EQUALS and value == rule.value:
            # EQUALS：精确等值匹配。
            #
            # 例如 value == "TCP" 时返回 6，
            # 或 value == 443 时返回 "https"。
            return rule.output
        if rule.mode == MappingRuleMode.IN and value in set(rule.values):
            # IN：集合成员匹配。
            #
            # 例如 value in [80, 443, 8080] 时统一返回 "web"。
            # 这里转成 set 是为了让成员测试更快，语义仍然来自配置的 values 列表。
            return rule.output
        if rule.mode == MappingRuleMode.PREFIX and isinstance(value, str) and isinstance(rule.value, str):
            # PREFIX：字符串前缀匹配。
            #
            # 例如 IP 字符串以 "10." 开头时映射成 "private-10-network"。
            # 只有当前值和规则 value 都是字符串时才尝试 startswith。
            if value.startswith(rule.value):
                return rule.output
        if rule.mode == MappingRuleMode.REGEX and isinstance(rule.value, str):
            # REGEX：正则匹配。
            #
            # 当前值会先转成字符串，再用 rule.value 作为正则表达式搜索。
            # 适合处理更复杂的文本模式，例如端口标签、协议名、地址片段。
            if re.search(rule.value, str(value)):
                return rule.output
        if rule.mode == MappingRuleMode.RANGE and value is not None:
            # RANGE：数值区间匹配。
            #
            # 先尝试把当前值转成 float；转不成数字就跳过这条规则。
            # lower/upper 可以只写一边，分别表示无上界或无下界。
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            # 默认上下界都认为通过；只有配置了对应边界才真正检查。
            lower_ok = True
            upper_ok = True
            if rule.lower is not None:
                # inclusive_lower=True 表示 numeric >= lower；
                # 否则要求 numeric > lower。
                lower_ok = numeric >= rule.lower if rule.inclusive_lower else numeric > rule.lower
            if rule.upper is not None:
                # inclusive_upper=True 表示 numeric <= upper；
                # 否则要求 numeric < upper。
                upper_ok = numeric <= rule.upper if rule.inclusive_upper else numeric < rule.upper
            if lower_ok and upper_ok:
                return rule.output
    # 走到这里说明没有任何非 DEFAULT 规则命中。
    # 如果规则中出现过 DEFAULT，返回 DEFAULT.output；否则返回原始 value。
    return default_value


def parse_hex_value(value: Any) -> Any:
    """把十六进制或十进制文本安全地转换成整数。

    它兼容几类常见输入：
    - 已经是整数
    - 看起来像整数的浮点值
    - `0x...` 十六进制文本
    - 普通十进制字符串

    空值或无意义文本统一转成 `NaN`，便于 pandas 后续处理。
    """
    if value is None or pd.isna(value):
        return np.nan
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return int(value)
    text = str(value).strip()
    if not text:
        return np.nan
    if text.lower() in {"nan", "none"}:
        return np.nan
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


def is_present_value_series(series: pd.Series) -> pd.Series:
    """判断一列中的值是否“存在且非空字符串”。

    这是 `FILTER_PRESENT` 语义的具体实现：
    - 非字符串列：只要求非空
    - 字符串列：既要求非空，也要求去掉空白后不是空串
    """
    mask = series.notna()
    if pd.api.types.is_string_dtype(series) or series.dtype == object:
        stripped = series.astype("string").str.strip()
        mask = mask & stripped.ne("")
    return mask


def drop_incomplete_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """剔除包含 NaN 或空字符串的列，并返回原因。

    这里采用“按列剔除”的策略，而不是“按行剔除”：
    - NetNomos 更关注字段能否稳定参与规则生成
    - 某列只要存在缺失，就可能污染比较、常量选择和支持率统计

    返回的 `excluded_fields` 会记录每列为什么被删，便于后续报错和 artifact 说明。
    """
    excluded_fields: dict[str, str] = {}
    for column in frame.columns:
        reasons: list[str] = []
        series = frame[column]
        if series.isna().any():
            reasons.append("contains NaN values")
        if (pd.api.types.is_string_dtype(series) or series.dtype == object) and series.astype("string").str.strip().eq("").any():
            reasons.append("contains empty values")
        if reasons:
            excluded_fields[column] = " and ".join(reasons)
    if excluded_fields:
        details = ", ".join(f"{name} ({reason})" for name, reason in sorted(excluded_fields.items()))
        log.warning("Excluding incomplete columns during dataset loading: %s", details)
        frame = frame.drop(columns=list(excluded_fields))
    return frame, excluded_fields


def validate_required_columns(frame: pd.DataFrame, spec: DatasetSpec, excluded_fields: dict[str, str]) -> None:
    """校验上下文窗口依赖的关键列在预处理后仍然存在。

    目前主要保护 `partition_by` / `order_by` 这类窗口关键列。
    如果它们被预处理删掉或因为不完整而自动剔除，窗口逻辑就不再可靠，
    因此这里直接报错而不是继续运行。

    为什么只检查这些列：
    - 普通特征列缺失时，后续可以通过字段选择、自动剔除或配置调整处理
    - 但窗口化依赖列属于“组织样本顺序”的基础设施
    - `partition_by` 决定哪些行属于同一个实体/会话/连接
    - `order_by` 决定同一组内部按什么顺序滑动窗口

    如果这些列不存在，`apply_context_windows()` 就无法可靠判断：
    - 哪些行应该放在同一个窗口族里
    - 行之间的先后顺序是否正确

    `excluded_fields` 用于补充错误原因。
    例如某个必需列不是原本不存在，而是因为包含 NaN 被
    `drop_incomplete_columns()` 自动剔除，那么错误信息会把原因也带上。
    """
    # 先收集“必须存在”的列名。
    # 默认没有必需列；只有配置了 context_window 时，窗口依赖列才成为硬要求。
    required: set[str] = set()
    if spec.context_window is not None:
        # partition_by：窗口分组键。
        # 例如按连接 ID、源/目的地址或 flow key 分组，避免不同实体的行混在一个窗口里。
        required.update(spec.context_window.partition_by)
        # order_by：每个分组内部的排序键。
        # 例如按时间戳或包序号排序，保证 ctx0/ctx1/ctx2 的时序含义稳定。
        required.update(spec.context_window.order_by)

    # 检查这些硬依赖列在当前 DataFrame 中是否仍然存在。
    # 注意此时已经经过了 source rename、preprocessing、field selection 和 incomplete-column drop。
    missing = sorted(name for name in required if name not in frame.columns)
    if not missing:
        # 没有缺失就直接返回；这个函数只负责校验，不返回新的 DataFrame。
        return

    # 构造更可读的错误详情。
    # 如果缺失列出现在 excluded_fields 中，说明它是被系统自动剔除的，
    # 可以把剔除原因一起展示出来，例如 "timestamp (contains NaN values)"。
    details = ", ".join(
        f"{name} ({excluded_fields[name]})" if name in excluded_fields else name
        for name in missing
    )
    # 对窗口必需列，继续运行只会制造语义错误，因此这里选择快速失败。
    raise ValueError(f"Required dataset columns are unavailable after loading: {details}")


def resolve_preprocess_target(step: Any, column: str) -> str:
    """确定映射类步骤的输出列名。

    对 MAP_VALUES / MAP_RULES 这类步骤：
    - 不写 `target_column` 时，原地覆盖源列
    - 写了 `target_column` 时，表示把结果写到新列

    但写新列名时必须保证只有一个源列，否则无法明确输出列到底对应谁。
    """
    if step.target_column is None:
        return column
    if len(step.columns) != 1:
        raise ValueError("`target_column` requires exactly one source column in the preprocessing step.")
    return step.target_column


def build_context_families(field_specs: dict[str, FieldSpec]) -> dict[str, list[str]]:
    """根据字段的 `context_family/context_index` 反向构建族索引。

    输出结构是：
    - family 名称 -> 按 index 排好序的字段列表

    量词模板投影阶段会依赖这个结构，把一组窗口字段视作同一族。
    """
    families: dict[str, list[tuple[int, str]]] = {}
    for field in field_specs.values():
        if field.context_family is None or field.context_index is None:
            continue
        families.setdefault(field.context_family, []).append((field.context_index, field.name))
    return {family: [name for _, name in sorted(entries)] for family, entries in families.items()}


def enrich_context_families(field_specs: dict[str, FieldSpec], columns: Any) -> dict[str, FieldSpec]:
    """从列名模式自动推断上下文族信息，兼容外部已展开的窗口列。

    这一步的作用是兼容两种来源：
    - 本模块自己 `apply_context_windows()` 生成的窗口列
    - 外部数据源本来就已经带着 `xxx_ctx0/xxx_ctx1` 这类列

    一旦匹配到上下文模式，也会自动补上 `FieldRole.WINDOW`。
    """
    for column in columns:
        # 只处理已经有 FieldSpec 的列。
        # 如果某列不在 field_specs 中，即使名字像 *_ctx0，也没有足够元数据可更新。
        if column not in field_specs:
            continue
        field = field_specs[column]
        # 如果字段已经有 context_family，说明它可能来自 apply_context_windows()
        # 或者配置里已经明确写好了窗口元信息。这里不覆盖已有人工/上游标注。
        if field.context_family is not None:
            continue
        for pattern in CTX_PATTERNS:
            # 尝试用预定义的窗口列名模式匹配当前列名。
            #
            # 匹配成功后可以拿到两个命名捕获组：
            # - match.group("base")：窗口族名称，也就是原始字段名
            # - match.group("index")：窗口位置索引，字符串形式，需要转成 int
            match = pattern.match(column)
            if match is None:
                # 当前 pattern 不匹配就换下一个 pattern 试。
                continue
            # Pydantic 模型一般不直接原地改字段，而是复制一份并覆盖部分字段。
            # 这样可以保留原 FieldSpec 的 value_type、domain、constants 等其他元数据。
            field_specs[column] = field.model_copy(
                update={
                    # 例如 tcp.seq_ctx2 的 context_family 会被识别为 tcp.seq。
                    # 后续 build_context_families() 会把同 family 的 ctx0/ctx1/ctx2 聚成一组。
                    "context_family": match.group("base"),
                    # 例如 tcp.seq_ctx2 的 context_index 会被识别为 2。
                    # 后续会按 index 排序，保证窗口字段顺序稳定。
                    "context_index": int(match.group("index")),
                    # 给字段追加 WINDOW 语义角色。
                    # dict.fromkeys 用于去重并保持原有 roles 顺序，避免重复添加 FieldRole.WINDOW。
                    "roles": list(dict.fromkeys([*field.roles, FieldRole.WINDOW])),
                }
            )
            # 一个列名只需要命中一种模式；命中后跳出 pattern 循环处理下一个 column。
            break
    return field_specs


def read_pcap(path: Path, limit: int | None = None) -> pd.DataFrame:
    """把 PCAP 文件解析为扁平 DataFrame。

    这里提取的是 NetNomos 当前学习流程最常用的链路层、IP 层、TCP/UDP 层字段。
    未出现的协议字段会保留为 None，便于后续统一列结构。

    PCAP 的原始形态不是表格，而是“按时间顺序排列的一串网络包”。
    这个函数做的事情是：
    1. 用 Scapy 逐个读取 packet；
    2. 为每个 packet 构造一个固定结构的 row 字典；
    3. 按协议层判断这个 packet 有哪些字段；
    4. 把能抽取到的字段填入 row；
    5. 最后把所有 row 合成 DataFrame。

    因此输出表的语义是：
    - 一行代表一个网络包
    - 一列代表从协议层中抽取出的一个字段
    """
    # 延迟导入 Scapy，避免项目在只处理 CSV 时也强制加载抓包解析依赖。
    # PcapReader 负责以流式方式读取 PCAP，适合逐包处理。
    from scapy.all import PcapReader
    # IP/TCP/UDP/Ether 是 Scapy 的协议层类型。
    # 后面通过 `if IP in packet` 这种写法判断某个 packet 是否包含对应层。
    from scapy.layers.inet import IP, TCP, UDP
    from scapy.layers.l2 import Ether

    # rows 中每个元素都是一个 packet 被扁平化后的字段字典。
    # 最终 pd.DataFrame(rows) 会把这些字典合并成表格。
    rows: list[dict[str, Any]] = []
    with PcapReader(str(path)) as reader:
        # enumerate(..., start=1) 让 frame.number 从 1 开始，更接近 Wireshark 的包序号习惯。
        for index, packet in enumerate(reader, start=1):
            if limit is not None and index > limit:
                # limit 用于调试或快速预览，只读取前 N 个包。
                break
            # 先构造固定列集合，保证不同包类型最终能合并为统一 DataFrame。
            #
            # 为什么要先填 None：
            # - TCP 包没有 UDP 字段
            # - UDP 包没有 TCP seq/ack/window 字段
            # - 非 IP 包可能没有 IP/TCP/UDP 字段
            #
            # 统一列集合可以让输出 DataFrame 结构稳定。
            row: dict[str, Any] = {
                # frame.* 是包级元信息，不属于某个协议层。
                "frame.number": index,
                "frame.time_epoch": float(getattr(packet, "time", 0.0)),
                "frame.len": len(packet),
                # Ethernet 层字段：源/目的 MAC 地址。
                "eth.src": None,
                "eth.dst": None,
                # IP 层字段：版本、头长、总长度、分片、TTL、协议号和地址等。
                "ip.version": None,
                "ip.hdr_len": None,
                "ip.len": None,
                "ip.id": None,
                "ip.flags": None,
                "ip.frag_offset": None,
                "ip.ttl": None,
                "ip.proto": None,
                "ip.src": None,
                "ip.dst": None,
                # TCP 层字段：端口、头长、flags、payload 长度、序列号、确认号、窗口等。
                "tcp.srcport": None,
                "tcp.dstport": None,
                "tcp.hdr_len": None,
                "tcp.flags": None,
                "tcp.len": None,
                "tcp.seq": None,
                "tcp.ack": None,
                "tcp.urgent_pointer": None,
                "tcp.window_size_value": None,
                "tcp.window_size_scalefactor": 1,
                "tcp.window_size": None,
                "tcp.options.timestamp.tsval": None,
                "tcp.options.timestamp.tsecr": None,
                # UDP 层字段：端口和长度。
                "udp.srcport": None,
                "udp.dstport": None,
                "udp.length": None,
                # 模拟/兼容 Wireshark 常见协议列，用于快速区分当前包最高关注层。
                "_ws.col.protocol": None,
            }
            if Ether in packet:
                # 如果包里有 Ethernet 层，就抽取 MAC 地址。
                # 不是所有 PCAP 都一定以 Ether 开头，因此这里先判断再访问。
                row["eth.src"] = packet[Ether].src
                row["eth.dst"] = packet[Ether].dst
            if IP in packet:
                # IP 层字段是后续很多网络规则的基础特征。
                ip = packet[IP]
                # ip.ihl 是 IP header length，单位是 32-bit word；
                # 乘以 4 后才是字节数。
                row["ip.version"] = int(ip.version)
                row["ip.hdr_len"] = int(ip.ihl) * 4 if ip.ihl is not None else None
                row["ip.len"] = int(ip.len) if ip.len is not None else None
                row["ip.id"] = int(ip.id)
                row["ip.flags"] = int(ip.flags.value)
                row["ip.frag_offset"] = int(ip.frag)
                row["ip.ttl"] = int(ip.ttl)
                row["ip.proto"] = int(ip.proto)
                row["ip.src"] = ip.src
                row["ip.dst"] = ip.dst
                # 如果只有 IP 层，还没发现 TCP/UDP，先标记为 IP。
                # 后面如果发现 TCP/UDP，会覆盖成更具体的协议名。
                row["_ws.col.protocol"] = "IP"
            if TCP in packet:
                # TCP 层是当前 schema 里最丰富的一层，抽取了序号、窗口、时间戳等关键字段。
                tcp = packet[TCP]
                row["tcp.srcport"] = int(tcp.sport)
                row["tcp.dstport"] = int(tcp.dport)
                row["tcp.hdr_len"] = int(tcp.dataofs) * 4 if tcp.dataofs is not None else None
                row["tcp.flags"] = int(tcp.flags.value)
                # tcp.len 这里取的是 TCP payload 字节数，不是整个 TCP 段长度。
                row["tcp.len"] = len(bytes(tcp.payload))
                row["tcp.seq"] = int(tcp.seq)
                row["tcp.ack"] = int(tcp.ack)
                row["tcp.urgent_pointer"] = int(tcp.urgptr)
                row["tcp.window_size_value"] = int(tcp.window)
                row["tcp.window_size"] = int(tcp.window)
                row["_ws.col.protocol"] = "TCP"
                for option_name, option_value in tcp.options or []:
                    # 只抽取当前 schema 明确使用的 TCP 选项。
                    if option_name == "WScale":
                        # WScale 是 TCP window scale 选项。
                        # 当前实现保存 scale factor，但没有用它重算 tcp.window_size。
                        scale = int(option_value)
                        row["tcp.window_size_scalefactor"] = scale if scale > 0 else 1
                        continue
                    if option_name != "Timestamp":
                        # 除 WScale 和 Timestamp 外，其他 TCP option 当前不进入表格。
                        continue
                    if isinstance(option_value, tuple) and len(option_value) == 2:
                        # Timestamp option 通常是 (tsval, tsecr) 二元组。
                        # tsval 是发送方时间戳值，tsecr 是回显时间戳值。
                        row["tcp.options.timestamp.tsval"] = int(option_value[0])
                        row["tcp.options.timestamp.tsecr"] = int(option_value[1])
            if UDP in packet:
                # UDP 信息相对简单，主要保留端口和长度。
                udp = packet[UDP]
                row["udp.srcport"] = int(udp.sport)
                row["udp.dstport"] = int(udp.dport)
                row["udp.length"] = int(udp.len)
                row["_ws.col.protocol"] = "UDP"
            # 当前 packet 已经被扁平化成 row，加入行列表。
            rows.append(row)
    # 将所有 packet row 合成 DataFrame。
    # 如果 rows 为空，也会返回一个空 DataFrame，后续流程会按普通空数据处理或报错。
    return pd.DataFrame(rows)
