# NetNomos Project Structure / NetNomos 项目结构说明

## 1. Scope / 范围说明

This document describes the outer `NetNomos-main` directory as the authoritative project root.  
本文以外层 `NetNomos-main` 目录作为主项目根目录进行说明。

There is also a nested `NetNomos-main/NetNomos-main` directory, which appears to be a duplicated extraction and is not treated as the active working copy in this repository.  
目录中还存在 `NetNomos-main/NetNomos-main` 的重复嵌套副本，推测为重复解压结果，本仓库不将其作为当前主工作副本。

## 2. Top-Level Layout / 顶层目录结构

```text
NetNomos-main/
├─ cpp/
├─ data/
├─ examples/
├─ netnomos/
├─ rules/
├─ scripts/
├─ tests/
├─ .gitignore
├─ Change.md
├─ conversion.md
├─ LICENSE
├─ project.md
├─ pyproject.toml
├─ README.md
├─ README_ZH.md
├─ setup.py
└─ uv.lock
```

## 3. File and Directory Reference / 文件与目录作用对照

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `.gitignore` | 定义 Git 忽略规则，包含运行产物、缓存和重复嵌套目录。 | Git ignore rules for runtime outputs, caches, and the duplicated nested folder. |
| `Change.md` | 版本变更记录，记录本地 Git 版本和改动内容。 | Changelog tracking local Git versions and their modifications. |
| `conversion.md` | 本次会话的双语对话归档。 | Bilingual archive of this session's conversation. |
| `LICENSE` | 项目许可证文件。 | Project license file. |
| `project.md` | 本文件，双语说明项目结构与文件职责。 | This file, documenting the repository structure and file responsibilities. |
| `pyproject.toml` | Python 包元数据、依赖、脚本入口和构建配置。 | Python package metadata, dependencies, entry points, and build config. |
| `README.md` | 英文主说明文档。 | Main English README. |
| `README_ZH.md` | 中文主说明文档。 | Main Chinese README. |
| `setup.py` | pybind11 原生扩展的 setuptools 构建入口。 | setuptools entry for building the pybind11 native extension. |
| `uv.lock` | `uv` 依赖锁文件，用于复现实验环境。 | `uv` lockfile for reproducible environments. |
| `cpp/` | 原生 C++ 扩展代码目录。 | Native C++ extension source directory. |
| `data/` | 示例原始数据目录。 | Shipped sample raw data. |
| `examples/` | 数据集与语法 JSON 配置示例。 | Example dataset and grammar JSON specs. |
| `netnomos/` | Python 主包，包含 API、DSL、数据准备、理论求值、学习器等核心实现。 | Main Python package containing the core implementation. |
| `rules/` | 内置 golden 规则工件目录。 | Built-in golden rule artifacts. |
| `scripts/` | 辅助脚本目录。 | Helper scripts. |
| `tests/` | 自动化测试目录。 | Automated tests. |
| `NetNomos-main/` | 重复嵌套副本，不作为当前主工作目录使用。 | Nested duplicate copy, not treated as the active working tree. |

## 4. `netnomos/` Package / `netnomos/` 主包

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `netnomos/__init__.py` | 导出对外公开的高层 API。 | Exports the public high-level API. |
| `netnomos/__main__.py` | 支持 `python -m netnomos` 启动 CLI。 | Enables `python -m netnomos` CLI execution. |
| `netnomos/api.py` | 高层编程接口，封装 prepare、fit、validate、interpret、entails 和工件落盘。 | High-level API wrapping preparation, fitting, validation, interpretation, entailment, and artifact writing. |
| `netnomos/artifacts.py` | 管理运行目录和工件写出。 | Manages run directories and artifact writing. |
| `netnomos/ast.py` | 定义公式/项 AST 结构与序列化逻辑。 | Defines formula/term AST structures and serialization helpers. |
| `netnomos/cli.py` | 命令行参数解析和子命令分发。 | CLI parsing and command dispatch. |
| `netnomos/dataset.py` | 负责 CSV/PCAP 加载、预处理、窗口化、派生变量和字段目录构建。 | Handles CSV/PCAP loading, preprocessing, windowing, derived variables, and field catalogs. |
| `netnomos/dsl.py` | 公式 DSL 的词法分析和递归下降解析器。 | Tokenizer and recursive-descent parser for the formula DSL. |
| `netnomos/interpreter.py` | 将 AST 解释为更适合人阅读的规则文本。 | Interprets AST nodes into more human-readable rule text. |
| `netnomos/logging_utils.py` | 项目日志配置与 logger 获取工具。 | Logging configuration and logger helpers. |
| `netnomos/projection.py` | 根据语法模板生成候选谓词，并计算支持率。 | Generates candidate predicates from grammar templates and computes support. |
| `netnomos/semantic_values.py` | 维护 `p50`、`top1` 等语义常量标签与原始值映射。 | Maintains mappings between semantic labels like `p50`/`top1` and raw values. |
| `netnomos/specs.py` | 用 Pydantic 定义数据集配置和语法配置模型。 | Pydantic models for dataset and grammar specifications. |
| `netnomos/theory.py` | DataFrame 公式求值、Z3 降阶、一致性和蕴含检查。 | Formula evaluation on DataFrames, Z3 lowering, consistency checks, and entailment. |

## 5. `netnomos/learners/` / 学习器目录

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `netnomos/learners/__init__.py` | 汇总导出学习器接口。 | Re-exports learner interfaces. |
| `netnomos/learners/hittingset.py` | 基于极小 hitting set 的规则学习器，支持 Python/C++ 双后端。 | Minimal hitting-set learner with both Python and C++ backends. |
| `netnomos/learners/tree.py` | 基于决策树的 implication-style 规则学习器。 | Decision-tree-based learner for implication-style rules. |

## 6. `tests/` / 测试目录

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `tests/test_cli.py` | 测试 CLI 主命令和规则转换脚本集成行为。 | Tests the main CLI commands and rule-conversion script integration. |
| `tests/test_dsl.py` | 测试 DSL 解析和渲染行为。 | Tests DSL parsing and rendering behavior. |
| `tests/test_end_to_end.py` | 测试端到端挖掘流程、工件写出、缓存和验证。 | Tests end-to-end mining, artifact writing, caching, and validation. |
| `tests/test_hittingset.py` | 测试 hitting-set 搜索、超时和后端选择。 | Tests hitting-set search, timeout handling, and backend selection. |
| `tests/test_prepare.py` | 测试数据准备、预处理、窗口和派生变量逻辑。 | Tests data preparation, preprocessing, windows, and derived variables. |
| `tests/test_projection.py` | 测试谓词生成、语义筛选和语义标签逻辑。 | Tests predicate generation, semantic filtering, and semantic labels. |

## 7. `scripts/` / 脚本目录

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `scripts/convert_golden_rules.py` | 将旧版 anuta/SymPy 风格规则转换成当前 NetNomos 工件格式。 | Converts legacy anuta/SymPy-style rules into current NetNomos artifacts. |
| `scripts/setup_cloudlab.sh` | 在 CloudLab/Ubuntu 环境中安装系统依赖并同步项目依赖。 | Installs system dependencies and syncs project dependencies in CloudLab/Ubuntu. |

## 8. `cpp/` / 原生扩展目录

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `cpp/hittingset_native.cpp` | pybind11 C++ 扩展，实现高性能 hitting-set 枚举。 | pybind11 C++ extension implementing high-performance hitting-set enumeration. |

## 9. `examples/datasets/` / 数据集配置示例

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `examples/datasets/cidds.json` | CIDDS 流记录数据集配置。 | Dataset spec for CIDDS flow records. |
| `examples/datasets/cidds_simple.json` | 更简化的 CIDDS 配置示例。 | Simplified CIDDS dataset spec. |
| `examples/datasets/metadc.json` | MetaDC 聚合遥测数据配置。 | Dataset spec for MetaDC aggregated telemetry. |
| `examples/datasets/pcap_tcp.json` | PCAP/TCP 数据集配置。 | Dataset spec for PCAP/TCP packet data. |

## 10. `examples/grammars/` / 语法配置示例

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `examples/grammars/metadc_agg.json` | 面向 MetaDC 聚合字段的谓词语法配置。 | Grammar spec for MetaDC aggregated fields. |
| `examples/grammars/network_flow.json` | 面向网络流记录的谓词语法配置。 | Grammar spec for network-flow datasets. |
| `examples/grammars/pcap_window.json` | 面向窗口化 PCAP 字段的谓词/量词语法配置。 | Grammar spec for windowed PCAP fields. |
| `examples/grammars/simple.json` | 最小示例语法配置。 | Minimal example grammar spec. |

## 11. `data/` / 示例数据

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `data/cidds_wk2_normal_10k.csv` | CIDDS 示例流记录 CSV。 | Example CIDDS flow-record CSV. |
| `data/mawi_2025july19_tcp100k.pcap` | MAWI 示例 PCAP。 | Example MAWI PCAP trace. |
| `data/metadc_test_10racks_5ctx.csv` | MetaDC 示例聚合数据。 | Example MetaDC aggregated dataset. |
| `data/netflix.pcap` | Netflix 示例 PCAP。 | Example Netflix PCAP trace. |

## 12. `rules/` / 内置规则工件

### 12.1 `rules/golden_cidds/`

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `rules/golden_cidds/rules.json` | CIDDS 黄金规则原始结构化表示。 | Structured golden rules for CIDDS. |
| `rules/golden_cidds/interpreted_rules.clj` | CIDDS 黄金规则的可读文本。 | Human-readable golden rules for CIDDS. |
| `rules/golden_cidds/metadata.json` | CIDDS 黄金规则集元数据。 | Metadata for the CIDDS golden rule set. |

### 12.2 `rules/golden_mawi/`

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `rules/golden_mawi/rules.json` | MAWI 黄金规则原始结构化表示。 | Structured golden rules for MAWI. |
| `rules/golden_mawi/interpreted_rules.clj` | MAWI 黄金规则的可读文本。 | Human-readable golden rules for MAWI. |
| `rules/golden_mawi/metadata.json` | MAWI 黄金规则集元数据。 | Metadata for the MAWI golden rule set. |

### 12.3 `rules/golden_metadc/`

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `rules/golden_metadc/rules.json` | MetaDC 黄金规则原始结构化表示。 | Structured golden rules for MetaDC. |
| `rules/golden_metadc/interpreted_rules.clj` | MetaDC 黄金规则的可读文本。 | Human-readable golden rules for MetaDC. |
| `rules/golden_metadc/metadata.json` | MetaDC 黄金规则集元数据。 | Metadata for the MetaDC golden rule set. |

### 12.4 `rules/golden_netflix/`

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `rules/golden_netflix/rules.json` | Netflix 黄金规则原始结构化表示。 | Structured golden rules for Netflix. |
| `rules/golden_netflix/interpreted_rules.clj` | Netflix 黄金规则的可读文本。 | Human-readable golden rules for Netflix. |
| `rules/golden_netflix/metadata.json` | Netflix 黄金规则集元数据。 | Metadata for the Netflix golden rule set. |

### 12.5 `rules/golden_netflix_full/`

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `rules/golden_netflix_full/rules.json` | 完整版 Netflix 黄金规则原始结构化表示。 | Structured full golden rules for Netflix. |
| `rules/golden_netflix_full/interpreted_rules.clj` | 完整版 Netflix 黄金规则的可读文本。 | Human-readable full golden rules for Netflix. |
| `rules/golden_netflix_full/metadata.json` | 完整版 Netflix 黄金规则集元数据。 | Metadata for the full Netflix golden rule set. |

## 13. Build and Packaging Files / 构建与打包文件

| Path | 中文作用 | English purpose |
| --- | --- | --- |
| `pyproject.toml` | 声明依赖、CLI、构建后端和包发现规则。 | Declares dependencies, CLI entry points, build backend, and package discovery. |
| `setup.py` | 将 `cpp/hittingset_native.cpp` 注册为 pybind11 扩展模块。 | Registers `cpp/hittingset_native.cpp` as a pybind11 extension module. |
| `uv.lock` | 锁定依赖解析结果，提升环境可复现性。 | Locks dependency resolution for reproducible environments. |

## 14. Current Repository Notes / 当前仓库注意事项

- The active Git repository is initialized at the outer `NetNomos-main` root.  
  当前 Git 仓库初始化在外层 `NetNomos-main` 根目录。

- The nested `NetNomos-main/NetNomos-main` duplicate is ignored in Git to avoid tracking the same project twice.  
  内层 `NetNomos-main/NetNomos-main` 重复副本已在 Git 中忽略，避免重复跟踪同一项目。

- Runtime outputs under `runs/` are ignored by Git.  
  `runs/` 下的运行产物不会纳入 Git 跟踪。

