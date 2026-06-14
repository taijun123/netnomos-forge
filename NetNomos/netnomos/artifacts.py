"""工件目录管理。

NetNomos 每次运行可能会产出很多中间结果和最终结果，例如：
- 数据集配置快照；
- grammar 配置快照；
- 候选谓词列表；
- 学到的规则；
- 解释后的规则文本；
- manifest 元数据。

该模块负责为一次规则挖掘运行创建输出目录，并统一提供 JSON、JSONL、
纯文本三类工件的写入能力。

这样上层 API 只需要说“写一个 rules.json”，不用反复处理：
- 输出目录是否存在；
- 父目录是否需要创建；
- JSON 如何格式化；
- JSONL 如何逐行写入。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class ArtifactStore:
    """表示一次运行对应的工件根目录。

    `ArtifactStore` 是一个很薄的封装：
    - `root` 指向本次运行的输出目录；
    - `write_json()` / `write_jsonl()` / `write_text()` 负责具体写文件。
    """

    # 本次运行的 artifact 根目录。
    root: Path

    @classmethod
    def create(cls, base: Path, dataset_name: str, grammar_name: str) -> "ArtifactStore":
        """创建带时间戳的运行目录，避免不同实验结果互相覆盖。

        目录名中包含：
        - 当前时间戳；
        - dataset 名称；
        - grammar 名称。

        `exist_ok=False` 是有意的：如果极小概率出现同名目录，直接报错比覆盖旧结果安全。
        """
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        root = base / f"{stamp}_{dataset_name}_{grammar_name}"
        root.mkdir(parents=True, exist_ok=False)
        return cls(root=root)

    def write_json(self, relative: str, data: Any) -> Path:
        """将对象序列化为格式化 JSON 并写入运行目录。

        适合配置快照、manifest、规则列表这类结构化但规模不太大的内容。
        `default=str` 用于兜底处理 Path、Enum 等 JSON 默认不认识的对象。
        """
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str))
        return path

    def write_jsonl(self, relative: str, rows: Iterable[dict[str, Any]]) -> Path:
        """按 JSON Lines 格式逐行写入记录，适合谓词等大列表工件。

        JSONL 的特点是一行一个 JSON 对象：
        - 便于流式写入；
        - 便于命令行逐行处理；
        - 比一个巨大 JSON 数组更适合候选谓词这类大列表。
        """
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            for row in rows:
                handle.write(json.dumps(row, default=str) + "\n")
        return path

    def write_text(self, relative: str, text: str) -> Path:
        """写入普通文本工件。

        适合解释后的规则、Clojure 风格表达式或其他人类可读文本。
        """
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path
