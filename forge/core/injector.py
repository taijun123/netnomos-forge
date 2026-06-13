# -*- coding: utf-8 -*-
"""forge.core.injector — 通用错误注入入口（薄封装）.

对外暴露统一接口 inject(scenario, ...)，内部按场景分发到具体实现：
- finance_v1 -> forge.scenarios.finance_v1.faults.inject_faults

新增场景时在 _DISPATCH 注册即可，调用方（server/web/tests）不感知场景内部实现。
第三方依赖懒加载：import 本模块不需要 pandas。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.contracts import Scenario


def _inject_finance_v1(df_clean=None, **kw):
    from forge.scenarios.finance_v1 import faults
    return faults.inject_faults(df_clean)


_DISPATCH = {
    Scenario.FINANCE_V1.value: _inject_finance_v1,
}


def supported_scenarios() -> list[str]:
    """当前支持错误注入的场景列表。"""
    return sorted(_DISPATCH)


def inject(scenario: str | Scenario, df_clean=None, **kw) -> tuple[Any, dict]:
    """通用注入接口：返回 (df_faulty, truth_table)。

    truth_table 为自动验收真值表（每个 fault：命中规则 id、行号、被篡改单元格的
    错误值/正确值、中文说明），结构见 forge.scenarios.finance_v1.faults。
    """
    key = scenario.value if isinstance(scenario, Scenario) else str(scenario)
    if key not in _DISPATCH:
        raise NotImplementedError(
            f"场景 {key!r} 暂不支持错误注入，可用：{supported_scenarios()}")
    return _DISPATCH[key](df_clean=df_clean, **kw)


def inject_to_dir(scenario: str | Scenario, out_dir: str | Path,
                  df_clean=None) -> dict[str, str]:
    """注入并落盘（CSV + truth_table.json），返回产物路径字典。"""
    key = scenario.value if isinstance(scenario, Scenario) else str(scenario)
    if key == Scenario.FINANCE_V1.value:
        from forge.scenarios.finance_v1 import faults
        return faults.save_package(out_dir, df_clean)
    raise NotImplementedError(f"场景 {key!r} 暂不支持落盘注入")
