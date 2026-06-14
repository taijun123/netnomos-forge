"""NetNomos 对外公开 API。

这个文件决定用户执行 `import netnomos` 后能直接看到哪些高层对象。
当前只导出两类最常用入口：
- `NetNomosMiner`：面向用户的规则挖掘主 API；
- `MiningResult`：一次挖掘运行的结构化结果。

底层模块如 dataset/projection/theory 仍可通过完整路径导入，
但不放进顶层命名空间，避免公开 API 过宽。
"""

from netnomos.api import NetNomosMiner, MiningResult

__all__ = ["NetNomosMiner", "MiningResult"]
