# NetNomos 中文说明

## 1. 项目简介

NetNomos 是一个面向网络数据的声明式逻辑规则挖掘框架。它能够从以下类型的数据中学习逻辑规则：

- NetFlow / 流记录
- PCAP 抓包文件
- 预聚合遥测数据

项目的核心思想是把“数据如何解释”“允许搜索哪些谓词”“采用哪种规则学习器”三件事完全配置化：

- `DatasetSpec` 定义数据源、字段、预处理、上下文窗口和派生变量
- `GrammarSpec` 定义谓词模板、量词模板和规则复杂度约束
- `Learner` 负责把候选谓词组合成最终规则

Python 包名为 `netnomos`，CLI 入口既可以用 `netnomos`，也可以用更短的 `netn`。

## 2. 适用场景

NetNomos 适合以下任务：

- 从网络流量数据中自动发现可解释规则
- 对规则学习空间做精细控制，而不是完全交给黑盒模型
- 研究“字段语义角色”对规则搜索空间的约束作用
- 将学习结果导出为可验证、可解释、可复现实验工件

## 3. 核心架构

一次典型运行的流水线如下：

1. 读取 `examples/datasets/*.json` 中的数据集配置
2. 读取 `examples/grammars/*.json` 中的语法配置
3. 执行 `prepare_dataset()` 完成数据清洗、窗口化、派生变量计算
4. 执行 `generate_predicates()` 生成所有候选谓词并计算支持率
5. 使用学习器生成规则
6. 将规则、解释文本、语义常量目录、运行清单等工件写入 `runs/`

项目目前提供两种学习器：

- `hitting-set`
  说明：枚举极小 hitting set，生成析取规则。
  特点：支持 Python 后端和 pybind11/C++ 原生后端。
- `tree`
  说明：对每个目标谓词训练决策树，并把高纯度正叶子路径还原成蕴含规则。
  特点：更偏向 `premise -> conclusion` 风格的规则。

## 4. 环境要求

- Python `>= 3.10`
- 推荐安装工具：`uv`
- 若希望启用原生 hitting-set 后端，需要本地 C++ 编译环境

如果本机没有 `uv`，也可以直接使用 `pip` 安装依赖：

```bash
python -m pip install numpy pandas pydantic rich scapy scikit-learn tqdm z3-solver
```

## 5. 安装方式

### 方式 A：使用 `uv`

```bash
git clone <your-repo-url>
cd NetNomos-main
uv sync
```

### 方式 B：使用当前 Python 环境

```bash
python -m pip install -e .
```

## 6. 快速开始

### 查看数据集配置

```bash
python -m netnomos show-dataset --dataset-spec examples/datasets/cidds.json
```

### 查看语法配置

```bash
python -m netnomos show-grammar --grammar-spec examples/grammars/network_flow.json
```

### 准备数据

```bash
python -m netnomos prepare \
  --dataset-spec examples/datasets/pcap_tcp.json \
  --input data/netflix.pcap \
  --limit 10
```

### 学习规则

```bash
python -m netnomos learn \
  --dataset-spec examples/datasets/cidds.json \
  --grammar-spec examples/grammars/network_flow.json \
  --input data/cidds_wk2_normal_10k.csv
```

### 校验已有规则

```bash
python -m netnomos validate \
  --dataset-spec examples/datasets/cidds.json \
  --grammar-spec examples/grammars/network_flow.json \
  --input data/cidds_wk2_normal_10k.csv \
  --rules runs/<run>/rules.json
```

### 解释已有规则

```bash
python -m netnomos interpret \
  --dataset-spec examples/datasets/cidds.json \
  --grammar-spec examples/grammars/network_flow.json \
  --input data/cidds_wk2_normal_10k.csv \
  --rules runs/<run>/rules.json
```

### 查询蕴含关系

```bash
python -m netnomos entails \
  --dataset-spec examples/datasets/cidds.json \
  --grammar-spec examples/grammars/network_flow.json \
  --input data/cidds_wk2_normal_10k.csv \
  --rules runs/<run>/rules.json \
  --query "Packets * 65535 >= Bytes"
```

## 7. 关键概念

### DatasetSpec

`DatasetSpec` 决定数据如何被 NetNomos 理解，主要包括：

- `source`：输入文件类型与默认路径
- `fields`：字段名、值类型、语义角色、常量、枚举标签
- `preprocessing`：按顺序执行的预处理步骤
- `context_window`：滑动窗口配置
- `derived_variables`：窗口之后再计算的新字段
- `include_fields` / `exclude_fields`：字段选择

### GrammarSpec

`GrammarSpec` 决定 NetNomos 能够生成哪些谓词，主要包括：

- `predicate_templates`：字段-字段、字段-常量、算术项-算术项等模板
- `quantifier_templates`：上下文窗口上的 `forall` / `exists` 模板
- `max_clause_size`：规则最大析取项数
- `max_rules`：最多保留多少条规则

### 语义常量

当常量来自 `profile`、`quantiles`、`top_k` 时，NetNomos 会生成语义标签，例如：

- `p50`
- `p90`
- `top1`

这些映射会写入 `semantic_values.json`，解释规则时会优先显示标签，而不是原始数值。

## 8. 输出工件

每次 `learn` 运行会在 `runs/` 下生成一个目录，通常包含：

- `dataset_spec.json`：本次运行使用的数据集配置
- `grammar_spec.json`：本次运行使用的语法配置
- `fields.json`：窗口化和派生变量完成后的字段定义
- `derived_variables.json`：派生变量来源信息
- `configured_exclude_fields.json`：由配置显式排除的字段
- `excluded_fields.json`：因缺失值或空值而被自动排除的字段
- `manifest.json`：本次运行摘要
- `predicates.jsonl`：生成的所有谓词
- `interpreted_predicates.clj`：可读化谓词文本
- `rules.json`：学习得到的规则
- `interpreted_rules.clj`：可读化规则文本
- `semantic_values.json`：语义标签到原始值的映射

## 9. 测试

项目测试位于 `tests/`。本次仓库整理后，已在当前环境中验证：

```bash
python -m pytest tests
```

结果：

- `26 passed`
- `1 skipped`

其中跳过项通常与原生 hitting-set 扩展是否已编译有关。

## 10. 目录说明补充

当前工作目录下存在一层重复解压目录：

```text
NetNomos-main/NetNomos-main
```

这份内容与外层项目基本重复。本次整理以外层 `NetNomos-main` 作为主仓库根目录，内层重复目录已在 Git 中忽略，以避免重复跟踪和重复提交。

## 11. 本次补充文档

本次整理新增了以下文档：

- `README_ZH.md`
  说明：中文项目说明。
- `project.md`
  说明：双语项目结构和文件职责说明。
- `conversion.md`
  说明：本次会话对话归档（双语）。
- `Change.md`
  说明：版本变更记录。

