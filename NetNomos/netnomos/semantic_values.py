"""语义常量目录。

projection 阶段可能会从数据分布中自动生成常量。
例如：
- 数值字段的 0.5 quantile 生成常量 128；
- 类别字段的 top1 生成常量 "TCP"。

这些原始值虽然可计算，但对人不够友好。
如果直接展示 `Bytes <= 128`，用户不知道 128 是配置写死的，还是从数据统计来的。

本模块维护“语义标签 <-> 原始值”之间的映射，例如：
- `Bytes <= 128` 可以在解释阶段显示成 `Bytes <= p50`；
- `protocol = "TCP"` 可以显示成 `protocol = top1`。

它主要服务 `interpreter.py` 和 artifact 输出。
"""

from __future__ import annotations

import json
from typing import Any

from netnomos.ast import BinaryTerm, FuncCall, IndexedRef, SymbolRef, Term
from netnomos.specs import FieldSpec


def make_value_key(value: Any) -> str:
    """将任意值编码为稳定字符串，用于字典键比较。

    不能直接用原始值做统一 key 的原因：
    - 值可能是字符串、数字、布尔值等不同类型；
    - JSON 序列化后的字符串形式更适合跨文件、跨运行比较；
    - `default=str` 可以处理少数 JSON 默认不支持的对象。
    """
    return json.dumps(value, sort_keys=True, default=str)


def quantile_label(quantile: float) -> str:
    """把分位数 0.5 / 0.9 转成 p50 / p90 之类的标签。

    规则：
    - 0.5 -> p50；
    - 0.95 -> p95；
    - 如果不是整数百分位，例如 0.333，则转成 p33_3 这类可做标识的文本。
    """
    percent = quantile * 100
    rounded = round(percent)
    if abs(percent - rounded) < 1e-9:
        return f"p{int(rounded)}"
    sanitized = str(round(percent, 3)).replace(".", "_")
    return f"p{sanitized}"


def build_semantic_value_catalog(predicates: list[Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """从谓词来源元数据中收集所有语义常量标签。

    projection 在生成谓词时，会把 profile 常量来源写进 predicate.source：
    - scope_kind: field / family
    - scope_name: 字段名或上下文 family 名
    - label: p50/top1
    - value: 实际常量值

    这里把所有谓词里的这些元数据汇总成目录，供解释阶段查找。
    """
    catalog: dict[str, dict[str, dict[str, Any]]] = {
        # 单字段范围，例如 fields["Bytes"]["p50"] = 128。
        "fields": {},
        # 上下文字段族范围，例如 families["tcp.seq"]["p50"] = 12345。
        "families": {},
    }
    for predicate in predicates:
        # source 可能是嵌套结构，例如 term-comparison 中 lhs_term/rhs_term 各自带 source。
        # 因此不能只看顶层，需要递归提取 semantic_constants。
        for entry in iter_semantic_entries(getattr(predicate, "source", {})):
            label = entry.get("label")
            if not label:
                continue
            scope_kind = entry.get("scope_kind")
            scope_name = entry.get("scope_name")
            value = entry.get("value")
            catalog_key = f"{scope_kind}s"
            if catalog_key not in catalog or not scope_name:
                continue
            # setdefault 保留第一次遇到的 label -> value，避免重复覆盖。
            catalog[catalog_key].setdefault(scope_name, {})
            catalog[catalog_key][scope_name].setdefault(label, value)
    return catalog


def iter_semantic_entries(payload: Any) -> list[dict[str, Any]]:
    """递归遍历嵌套 source 元数据，提取 semantic_constants 列表。

    source 元数据可能长这样：
    {
      "lhs_term": {"semantic_constants": [...]},
      "rhs_term": {"semantic_constants": [...]}
    }

    所以这里对 dict/list 都做递归遍历，找到所有 semantic_constants。
    """
    entries: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        raw_entries = payload.get("semantic_constants", [])
        if isinstance(raw_entries, list):
            entries.extend(entry for entry in raw_entries if isinstance(entry, dict))
        for value in payload.values():
            entries.extend(iter_semantic_entries(value))
    elif isinstance(payload, list):
        for item in payload:
            entries.extend(iter_semantic_entries(item))
    return entries


def lookup_semantic_label(
    term: Term,
    value: Any,
    fields: dict[str, FieldSpec],
    catalog: dict[str, dict[str, dict[str, Any]]] | None,
) -> str | None:
    """根据项引用范围查找某个常量值对应的语义标签。

    查找顺序：
    1. 如果 term 只引用了单个字段，就先在 fields 目录下查；
    2. 如果 term 引用的一组字段属于同一个上下文 family，再在 families 目录下查；
    3. 都找不到则返回 None，让解释器回退到原始值。
    """
    if not catalog:
        return None
    value_key = make_value_key(value)
    field_name = resolve_field_reference(term)
    if field_name is not None:
        label = lookup_scope_label(catalog.get("fields", {}), field_name, value_key)
        if label is not None:
            return label
    family_name = resolve_family_reference(term, fields)
    if family_name is not None:
        return lookup_scope_label(catalog.get("families", {}), family_name, value_key)
    return None


def lookup_scope_label(scope_catalog: dict[str, dict[str, Any]], scope_name: str, value_key: str) -> str | None:
    """在字段或上下文族的标签表里查找值对应的标签名。

    `scope_catalog` 形如：
    {
      "Bytes": {"p50": 128, "p90": 512}
    }

    这里是“根据值反查标签”，所以需要遍历 label -> raw_value。
    """
    labels = scope_catalog.get(scope_name, {})
    for label, raw_value in labels.items():
        if make_value_key(raw_value) == value_key:
            return label
    return None


def resolve_field_reference(term: Term) -> str | None:
    """若一个项只引用了单个字段，则返回该字段名。

    例如：
    - `Bytes` -> Bytes
    - `Bytes + 10` -> Bytes
    - `Bytes + Header` -> None，因为引用了两个字段
    """
    symbols = collect_symbol_refs(term)
    if len(symbols) == 1:
        return symbols[0]
    return None


def resolve_family_reference(term: Term, fields: dict[str, FieldSpec]) -> str | None:
    """若一个项引用的字段都来自同一上下文族，则返回该族名。

    这服务于量词投影后的公式。
    例如 `MIN(tcp.seq_ctx0, tcp.seq_ctx1, tcp.seq_ctx2) >= 100`
    里面引用的字段都属于 family `tcp.seq`，因此可以用 family 级 p50/top1 标签。
    """
    symbols = collect_symbol_refs(term)
    families = {
        fields[name].context_family
        for name in symbols
        if name in fields and fields[name].context_family is not None
    }
    if len(families) == 1:
        return next(iter(families))
    return None


def collect_symbol_refs(term: Term) -> list[str]:
    """递归收集项中出现的所有 SymbolRef 名称。

    注意 `IndexedRef` 不返回字段名，因为它还需要结合 env/context_families 才能解析成具体列。
    当前语义标签查找主要面对 projection 后的 SymbolRef/FuncCall 结构。
    """
    if isinstance(term, SymbolRef):
        return [term.name]
    if isinstance(term, IndexedRef):
        return []
    if isinstance(term, BinaryTerm):
        return [*collect_symbol_refs(term.left), *collect_symbol_refs(term.right)]
    if isinstance(term, FuncCall):
        refs: list[str] = []
        for arg in term.args:
            refs.extend(collect_symbol_refs(arg))
        return refs
    return []
