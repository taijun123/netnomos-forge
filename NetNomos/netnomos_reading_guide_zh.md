# NetNomos 阅读讲解与算法指南

本文面向有神经网络基础、想快速理解 NetNomos 代码和论文思想的研究生读者。建议先把它当成一个“逻辑规则挖掘器”阅读，而不是当成一个端到端深度学习项目阅读。

当前仓库主要实现论文中的第一阶段：从网络数据中学习逻辑规则；同时实现了规则解释、规则验证、蕴含查询和 hitting-set 的 C++ 加速。论文中的 LLM 语义过滤和 GPT-2 token 级 SMT 强制生成，在这个仓库中不是主流程代码。

## 1. 一句话理解项目

NetNomos 的输入是：

1. 数据集配置 `DatasetSpec`：告诉系统如何读 CSV/PCAP、如何清洗、哪些字段是什么语义类型。
2. 语法配置 `GrammarSpec`：告诉系统允许生成哪些逻辑谓词。
3. 原始网络数据：NetFlow、PCAP、聚合遥测等。

输出是：

1. 候选谓词，例如 `Bytes > Mtu`、`Packets * 65535 >= Bytes`、`tcp.seq_ctx0 + 1 = tcp.ack_ctx0`。
2. 由谓词组合成的规则，例如 `p1 OR p7 OR p20`。
3. 可读规则文件、结构化 `rules.json`、语义常量映射和运行 manifest。

最核心的思想是：网络数据中的每一行或每个窗口都被看作满足某些隐藏网络规则的“可行解”。系统先枚举可能的谓词，再寻找一个尽量小的谓词集合，使得每条样本至少满足集合中的一个谓词。这个问题被代码实现为 minimal hitting set / set cover 风格的搜索。

## 2. 先看论文，再看代码时要抓住什么

论文《Making Logic a First-Class Citizen in Generative ML for Networking》把 NetNomos 分成三阶段：

1. Rule Learning：从数据中学习与数据一致且较强的规则。
2. Rule Filtering：用 LLM 或人工过滤掉语法正确但语义无意义的规则。
3. Rule Enforcement：在生成模型逐 token 推理时，用 SMT solver 排除会导致规则冲突的 token。

本仓库的对应关系：

| 论文概念 | 代码位置 | 本仓库实现情况 |
| --- | --- | --- |
| 数据可观测变量 `V` | `examples/datasets/*.json`, `netnomos/specs.py` | 已实现 |
| 有限一阶逻辑语法 `Gamma` | `examples/grammars/*.json`, `netnomos/specs.py` | 已实现为配置化模板 |
| 谓词投影 / grounding | `netnomos/projection.py` | 已实现 |
| evidence set 构造 | `netnomos/learners/hittingset.py` | 已实现 |
| minimal hitting set 搜索 | `netnomos/learners/hittingset.py`, `cpp/hittingset_native.cpp` | Python 和 C++ 两版 |
| 规则解释 | `netnomos/interpreter.py`, `netnomos/semantic_values.py` | 已实现 |
| 逻辑验证 / 蕴含查询 | `netnomos/theory.py` | 已用 Z3 实现 |
| LLM 过滤 | 论文第 5 节 | 当前仓库没有完整主流程 |
| GPT-2 + SMT 生成强制 | 论文第 6 节 | 当前仓库没有完整主流程 |

因此阅读时不要期待看到神经网络训练循环。这里的算法核心是符号逻辑、谓词枚举、DataFrame 求值、hitting set 搜索和 Z3 推理。

## 3. 推荐阅读顺序

第一遍只读主链路：

1. `README.md`：理解 CLI、输入输出、配置格式。
2. `netnomos/api.py`：从 `NetNomosMiner.fit()` 看完整流程。
3. `netnomos/dataset.py`：看原始数据如何变成 `PreparedDataset`。
4. `netnomos/projection.py`：看 grammar 如何生成具体谓词。
5. `netnomos/learners/hittingset.py`：看谓词如何组合成规则。
6. `netnomos/theory.py`：看规则如何在数据和 Z3 中被验证。
7. `tests/test_end_to_end.py`：用 toy case 串起完整行为。

第二遍再看配置和样例：

1. `examples/datasets/pcap_tcp.json`：看 PCAP 的窗口化字段。
2. `examples/grammars/pcap_window.json`：看 TCP 序列号、payload、interarrival 规则空间。
3. `examples/grammars/network_flow.json`：看 NetFlow 上的 assignment、scalar、addition 模板。
4. `rules/golden_*`：看已保存的规则长什么样。

第三遍再看扩展点：

1. `netnomos/learners/tree.py`：决策树 learner，是 hitting-set 以外的备选。
2. `cpp/hittingset_native.cpp`：hitting-set 的性能加速版。
3. `netnomos/dsl.py`：用户查询字符串如何解析成 AST。
4. `netnomos/ast.py`：公式和项的内部表示。

## 4. 核心数据流

完整流程可以写成：

```text
DatasetSpec + raw data
  -> prepare_dataset()
  -> PreparedDataset
  -> generate_predicates()
  -> list[GroundedPredicate]
  -> HittingSetLearner.fit() or EntropyTreeLearner.fit()
  -> list[LearnedRule]
  -> artifacts + interpretation + validation + entailment
```

对应入口在 `netnomos/api.py`：

1. `NetNomosMiner.fit()` 先调用 `prepare()`。
2. `prepare()` 调用 `prepare_dataset()`。
3. `fit()` 再调用 `generate_predicates()`。
4. 根据 `--learner` 选择 hitting-set 或 tree。
5. 生成 `semantic_values`。
6. 用 `interpret_formula()` 把 AST 渲染成人类可读文本。
7. 写入 `runs/<timestamp>_<dataset>_<grammar>/`。

你读代码时可以把 `NetNomosMiner.fit()` 当成总控函数。它不做具体算法，而是把数据准备、谓词生成、规则学习、解释和落盘串起来。

## 5. 数据准备：从原始网络数据到 PreparedDataset

入口：`netnomos/dataset.py::prepare_dataset()`。

它的核心输出是 `PreparedDataset`，包含：

1. `dataframe`：清洗、窗口化、派生变量之后的数据表。
2. `field_specs`：每个字段的类型、角色、常量、上下文窗口信息。
3. `value_catalog`：字段取值目录，用于 profile/domain 常量选择。
4. `context_families`：例如 `tcp.seq -> [tcp.seq_ctx0, tcp.seq_ctx1, tcp.seq_ctx2]`。
5. `derived_provenance`：派生变量来源记录。
6. `excluded_fields`：被自动排除的缺失列。

读 `prepare_dataset()` 时按下面顺序理解：

```text
resolve_source()
  -> 根据 input_path 或 spec.source.path 判断 CSV / PCAP

read_csv() or read_pcap()
  -> CSV 直接 pandas 读入
  -> PCAP 用 scapy 展开为固定字段 DataFrame

apply_source_renames()
  -> source_name 标准化为 name

apply_preprocessing()
  -> filter / cast / parse_hex / map_values / map_rules / sort

apply_field_selection()
  -> include_fields / exclude_fields

drop_incomplete_columns()
  -> 去掉 NaN 或空字符串列

initial_field_specs()
  -> 配置里有的字段用配置，没有的字段推断类型

apply_context_windows()
  -> 多行窗口展开成一行

apply_derived_variables()
  -> diff / ratio / std / min / max 等派生列

build_value_catalog()
attach_domains()
build_context_families()
  -> 给后续 grammar 选择字段和常量用
```

### 窗口化的含义

以 `examples/datasets/pcap_tcp.json` 为例，`context_window.size = 3`，所以连续三个包会被折叠成一行：

```text
tcp.seq      -> tcp.seq_ctx0, tcp.seq_ctx1, tcp.seq_ctx2
tcp.ack      -> tcp.ack_ctx0, tcp.ack_ctx1, tcp.ack_ctx2
frame.len    -> frame.len_ctx0, frame.len_ctx1, frame.len_ctx2
```

如果 partition 是五元组或四元组，窗口不会跨 flow 混合。这样 TCP 时序关系才能写成同一行里的逻辑谓词，例如：

```text
tcp.seq_ctx0 + 1 = tcp.ack_ctx0
tcp.seq_ctx0 + frame.len_ctx0 <= tcp.ack_ctx0
```

## 6. 谓词生成：GrammarSpec 如何变成 GroundedPredicate

入口：`netnomos/projection.py::generate_predicates()`。

`GrammarSpec` 不是直接写规则，而是写“模板”。模板定义：

1. 左边选哪些字段。
2. 右边选字段还是常量。
3. 用哪些比较符。
4. 是否允许算术项，如 `scalar` 或 `addition`。
5. 是否允许窗口上的 forall / exists。

`generate_predicates()` 做四件事：

1. 根据 selector 选字段：`select_fields()`。
2. 根据 constant selector 选常量：`select_constants()`。
3. 组合成 AST：`Compare`, `SymbolRef`, `Constant`, `BinaryTerm`, `FuncCall`。
4. 在数据上求 support：`evaluate_formula_df()`。

### 字段选择器

字段选择器 `VariableSelectorSpec` 支持：

```json
{
  "names": ["Bytes"],
  "types": ["integer", "real"],
  "roles": ["size"],
  "context_family": "tcp.seq",
  "window_only": true,
  "exclude": ["Duration"]
}
```

这让规则空间由数据语义约束，而不是盲目枚举所有列。

### 常量选择器

`ConstantSelectorSpec` 有四种来源：

1. `explicit`：配置里直接给常量。
2. `field_constants`：字段配置里声明的常量，如 MTU、端口分类、TCP seq + 1。
3. `domain`：离散字段的定义域或观测取值。
4. `profile`：从数据分布里取 quantile 或 top-k。

例如 `profile` 对数值字段会生成 `p25/p50/p75/p90`，对类别字段会生成 `top1/top2`。真实值保存在 `semantic_values.json`，解释规则时显示语义标签而不是裸数值。

### 算术谓词

代码支持三类常见项：

```text
field:    Bytes
scalar:   Packets * 65535
addition: Bytes + Header
```

这些在 `generate_terms()` 中展开。重要的是，代码会检查语义兼容性：

1. `Bytes <= Duration` 会被拒绝，因为 size 和 time 不能比较。
2. `Bytes + Header <= MTU` 可以生成，因为都是 size。
3. `tcp.seq + frame.len <= tcp.ack` 可以生成，因为 sequence + size 可被视为 sequence。

### 量词投影

`project_quantified_family()` 把有限窗口上的量词变成有限公式。例如：

```text
forall k: tcp.len[k] >= c
```

在窗口字段上投影为：

```text
min(tcp.len_ctx0, tcp.len_ctx1, tcp.len_ctx2) >= c
```

同理：

```text
exists k: tcp.len[k] >= c
```

投影为：

```text
max(tcp.len_ctx0, tcp.len_ctx1, tcp.len_ctx2) >= c
```

这就是论文里“有限域一阶逻辑 grounding / propositionalization”的代码化实现。

## 7. 核心算法：Minimal Hitting Set

入口：`netnomos/learners/hittingset.py::HittingSetLearner.fit()`。

设准备后的数据有 `n` 行：

```text
D = {d_1, d_2, ..., d_n}
```

谓词生成器产生 `m` 个候选谓词：

```text
P = {p_1, p_2, ..., p_m}
```

对每个谓词 `p_j`，定义 evidence set：

```text
E_j = { i | d_i |= p_j }
```

也就是说，`E_j` 是所有满足谓词 `p_j` 的样本行编号。

现在要找一个小集合：

```text
H subset {1, 2, ..., m}
```

使得：

```text
union_{j in H} E_j = {1, 2, ..., n}
```

这表示每条数据至少满足 `H` 中的一个谓词。于是可以构造规则：

```text
R_H = OR_{j in H} p_j
```

如果 `H = {3, 9, 12}`，规则就是：

```text
p_3 OR p_9 OR p_12
```

### 为什么最小 hitting set 对应更强规则

对于析取规则：

```text
p_1 OR p_2 OR p_3
```

如果删掉一个谓词，变成：

```text
p_1 OR p_2
```

满足它的样本集合通常会变小，因此规则更强。也就是说，在保证所有数据都满足的前提下，析取项越少，规则越严格、越有信息量。

所以代码寻找 minimal hitting set，本质是在找“尽量少的谓词组合”，使其仍然覆盖数据。

### 代码如何构建 evidence sets

`_load_or_build_evidence_sets()` 的逻辑是：

```text
初始化 evidence_sets[i] = 空集合

for each predicate p_j:
    sat = evaluate_formula_df(p_j, prepared)
    rows = 满足 p_j 的所有行
    for row in rows:
        evidence_sets[row].add(j)
```

注意这里的 `evidence_sets` 是按“样本行”存的：

```text
evidence_sets[i] = 第 i 行满足哪些谓词
```

随后搜索要从每个样本行的可选谓词中挑一个或多个，使所有样本行都被“命中”。这是 hitting set 的对偶表述。

一个实现细节很重要：如果某一行没有任何候选谓词为真，代码会把这行从 hitting-set 搜索中移除，因为它无法被任何规则覆盖。不过最后 `support` 仍在完整 prepared dataframe 上重新计算，所以你可以从规则 support 看出规则是否真的覆盖了所有原始行。

### Python 搜索过程

入口：`_enumerate_minimal_hitting_sets_python()`。

关键变量：

```text
idx_by_pred[p] = 谓词 p 能覆盖哪些 evidence 行
universe       = 所有 evidence 行
solutions      = 已找到的 minimal hitting sets
chosen         = 当前已选谓词集合
covered        = 当前已覆盖 evidence 行集合
```

递归 `branch(chosen, covered)` 的逻辑：

1. 如果 `covered == universe`，当前 `chosen` 是一个可行解。
2. 如果已有解是 `chosen` 的子集，则 `chosen` 不是极小解，丢弃。
3. 如果 `len(chosen) >= max_clause_size`，停止扩展。
4. 选择一个还没覆盖的 evidence 作为 pivot。
5. 优先尝试能覆盖更多未覆盖 evidence 的谓词。
6. 递归扩展。

这就是典型的回溯搜索加剪枝。

### C++ 加速版

`cpp/hittingset_native.cpp` 与 Python 版算法目标一致，但用 bitset 表示覆盖关系：

```text
predicate -> bitset of covered evidence rows
```

这样求并集、计算新增覆盖量、判断覆盖完成都更快。Python 侧通过 pybind11 调用它。

## 8. Tree learner 是什么

入口：`netnomos/learners/tree.py::EntropyTreeLearner.fit()`。

它不是论文主推的 hitting-set 路线，而是一个替代 learner：

1. 先把每个谓词在每行数据上的真假值组成布尔矩阵。
2. 每次选一个谓词当目标 `y`。
3. 用其他谓词作为特征 `X` 训练决策树。
4. 把高纯度正叶子的路径转成 implication：

```text
premise -> target
```

例如路径条件是：

```text
p1 = true AND p4 = false
```

目标是：

```text
p9 = true
```

生成规则：

```text
p1 AND NOT p4 -> p9
```

对于有神经网络背景的读者，可以把它理解成：先把逻辑谓词变成二值特征，再用信息熵决策树找局部可解释的 implication。

## 9. 公式求值与 Z3 推理

入口：`netnomos/theory.py`。

这个模块做两类事：

1. 在 DataFrame 上评价规则满足率。
2. 把 AST 降到 Z3 表达式，做一致性和蕴含检查。

### DataFrame 求值

`evaluate_formula_df()` 会优先尝试向量化：

```text
Bytes > Mtu
```

会变成：

```python
frame["Bytes"] > frame["Mtu"]
```

如果遇到量词或复杂函数无法向量化，就退回逐行递归求值。

规则 support 定义为：

```text
support(phi) = (1 / n) * sum_i 1[d_i |= phi]
```

代码里就是：

```python
float(evaluate_formula_df(formula, prepared).mean())
```

### Z3 蕴含

`Theory.entails(query)` 的逻辑是标准反证法：

```text
Th |= q    iff    Th AND NOT q is UNSAT
```

代码步骤：

1. 把所有规则公式加入 solver。
2. 加入 `Not(query)`。
3. 如果 solver 返回 `unsat`，说明规则集蕴含 query。

因此：

```text
entails("Bytes > Mtu") == true
```

表示在当前规则理论下，不可能存在一个满足所有规则但违反 `Bytes > Mtu` 的赋值。

这里做的是逻辑层面的蕴含，不是统计相关性。

## 10. AST 和 DSL 怎么读

内部公式不是字符串，而是 AST。核心节点在 `netnomos/ast.py`：

```text
SymbolRef("Bytes")          字段引用
Constant(65535)             常量
BinaryTerm("*", a, b)       算术项
Compare(">=", left, right)  比较谓词
BoolOr((p1, p2))            析取
BoolAnd((p1, p2))           合取
Implies(left, right)        蕴含
ForAll / Exists             有限域量词
FuncCall("min", args)       聚合函数
```

`netnomos/dsl.py` 把用户输入：

```text
Packets * 65535 >= Bytes
```

解析为 AST：

```text
Compare(">=", BinaryTerm("*", SymbolRef("Packets"), Constant(65535)), SymbolRef("Bytes"))
```

后续验证、解释、Z3 降低都围绕这个 AST 工作。

## 11. 一个最小例子帮助你建立直觉

假设数据是：

| Bytes | Packets | Mtu |
| --- | --- | --- |
| 10 | 1 | 5 |
| 11 | 2 | 6 |
| 20 | 3 | 7 |

候选谓词包括：

```text
p0: Bytes > Mtu
p1: Packets > 0
p2: Mtu > 0
p3: Bytes >= Packets
```

每个谓词的 evidence：

```text
E_0 = {1, 2, 3}
E_1 = {1, 2, 3}
E_2 = {1, 2, 3}
E_3 = {1, 2, 3}
```

任意一个都能覆盖所有样本。minimal hitting set 可以是 `{0}`，于是规则是：

```text
Bytes > Mtu
```

如果某些谓词只覆盖部分样本，例如：

```text
E_4 = {1, 2}
E_5 = {3}
```

那么 `{4, 5}` 也能形成规则：

```text
p4 OR p5
```

但如果 `{0}` 已经存在，`{4, 5}` 不一定是更强或更优的选择，具体取决于 minimal / subset pruning 和枚举顺序。

## 12. 配置文件该怎么看

### DatasetSpec

读 `examples/datasets/*.json` 时重点看：

1. `fields`：字段名、类型、角色、常量。
2. `preprocessing`：映射、过滤、类型转换。
3. `include_fields` / `exclude_fields`：最终进入规则学习的字段。
4. `context_window`：是否构造窗口。
5. `derived_variables`：是否加入统计量。

字段 `roles` 很关键。它决定哪些字段能被拿来比较。例如：

```json
{"name": "frame.len", "roles": ["size", "measurement"]}
{"name": "frame.time_epoch", "roles": ["time"]}
```

这会阻止 `frame.len <= frame.time_epoch` 这种语义错误谓词。

### GrammarSpec

读 `examples/grammars/*.json` 时重点看：

1. `max_clause_size`：一条 hitting-set 规则最多包含多少析取项。
2. `max_rules`：最多保存多少规则。
3. `predicate_templates`：普通谓词模板。
4. `quantifier_templates`：窗口量词模板。

例如 `network_flow.json` 中：

```json
"packet-capacity": Packets * 65535 <=/>= Bytes
```

对应论文中 NetFlow 规则：

```text
Bytes <= 65535 * Packets
```

这类规则表达的是一个流的字节数受包数和每包最大载荷限制。

## 13. 跟着代码走一遍 CLI

CLI 入口是 `netnomos/cli.py::main()`。

用户执行：

```bash
python -m netnomos learn \
  --dataset-spec examples/datasets/cidds.json \
  --grammar-spec examples/grammars/network_flow.json \
  --input data/cidds_wk2_normal_10k.csv
```

调用链是：

```text
cli.main()
  -> build_miner()
  -> NetNomosMiner.from_files()
  -> NetNomosMiner.fit()
  -> prepare_dataset()
  -> generate_predicates()
  -> HittingSetLearner.fit()
  -> _write_artifacts()
```

输出目录中最该看的文件：

1. `manifest.json`：本次运行摘要。
2. `predicates.jsonl`：所有候选谓词。
3. `interpreted_predicates.clj`：候选谓词可读文本。
4. `rules.json`：结构化规则。
5. `interpreted_rules.clj`：最终可读规则。
6. `semantic_values.json`：`p50/top1` 到原始值的映射。

## 14. 如何逐段阅读核心函数

### `NetNomosMiner.fit()`

逐段读：

1. `prepared = self.prepare(...)`：生成标准输入。
2. `predicates = generate_predicates(...)`：生成逻辑原子。
3. `learner_kind = LearnerKind(learner)`：选择 learner。
4. hitting-set 分支：构建 evidence cache，再 learner.fit。
5. tree 分支：构建决策树 learner。
6. `semantic_values = build_semantic_value_catalog(predicates)`。
7. `interpreted_predicates` / `interpreted_rules`。
8. `ArtifactStore.create(...)`。
9. `_write_artifacts(...)`。
10. `self.last_result = result`。

### `generate_predicates()`

逐段读：

1. 遍历 `predicate_templates`。
2. 如果是 term template，先 `generate_terms()`。
3. 如果是 field-field，双重循环组合字段。
4. 如果是 field-constant，字段和常量组合。
5. 调用兼容性检查，过滤无意义组合。
6. 用 `append_candidate()` 去重。
7. 遍历 `quantifier_templates`，投影为有限公式。
8. 对所有 candidate 求 support。
9. 返回 `GroundedPredicate` 列表。

### `HittingSetLearner.fit()`

逐段读：

1. `_load_or_build_evidence_sets()`：把数据转成覆盖关系。
2. `enumerate_minimal_hitting_sets()`：搜索 minimal covers。
3. 对每个 cover，把谓词 AST 组合成 `BoolOr`。
4. 重新计算规则 support。
5. `prune_tautologies()`：去掉明显永真析取式。
6. 记录 `last_fit_metadata`。

### `_enumerate_minimal_hitting_sets_python()`

逐段读：

1. 构建 `idx_by_pred` 倒排索引。
2. 定义 `universe`。
3. 定义 `has_subset()`，保证极小性。
4. 定义 `is_stalled()`，支持早停。
5. 递归 `branch()`。
6. pivot 选择：找一个未覆盖 evidence。
7. candidate 排序：优先覆盖更多未覆盖 evidence。
8. 递归扩展，直到覆盖全集或触发剪枝。

## 15. 当前环境复现注意事项

我在当前机器上尝试运行 PCAP prepare 时遇到两个环境问题：

1. 当前 Python 缺少 `scapy`，所以 `read_pcap()` 无法读取 PCAP。
2. 当前 Anaconda 环境中 NumPy 2.4.6 与一些已编译包存在 ABI 警告。

建议复现实验时使用项目锁定环境，而不是直接用 base Anaconda：

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
python -m pip install "numpy<2" scapy pandas pydantic rich scikit-learn tqdm z3-solver
```

如果使用 `uv`，按 README：

```bash
uv sync
uv run netn --help
```

注意：如果 PowerShell 中中文注释显示乱码，通常是终端编码问题。源码本身是 UTF-8，可以用 VS Code 或支持 UTF-8 的编辑器打开。

## 16. 建议你的学习路线

第一天：只跑通概念

1. 看 README 的 workflow。
2. 看 `NetNomosMiner.fit()`。
3. 手动画出数据流图。
4. 看一个简单 grammar，理解它能生成哪些谓词。

第二天：理解算法

1. 读论文第 4 节 rule learning。
2. 推导 `E_j = {i | d_i |= p_j}`。
3. 手算一个 3 行数据、4 个谓词的 hitting set。
4. 对照 `_enumerate_minimal_hitting_sets_python()`。

第三天：理解工程实现

1. 看 `prepare_dataset()` 的字段生命周期。
2. 看 `generate_predicates()` 的模板展开。
3. 看 `evaluate_formula_df()` 的向量化求值。
4. 看 `_write_artifacts()` 的输出结构。

第四天：理解验证与解释

1. 看 `interpreter.py` 和 `semantic_values.py`。
2. 看 `Theory.entails()`。
3. 用保存的 `rules.json` 跑 `interpret` 和 `entails`。

第五天：扩展实验

1. 改一个 grammar，只允许少量谓词。
2. 比较 predicate_count 和 rule_count。
3. 改 `max_clause_size`，观察规则复杂度。
4. 改 `profile.quantiles`，观察 `semantic_values.json`。

## 17. 读完后你应该能回答的问题

1. 一个字段为什么能或不能参与某类比较？
2. `p50`、`top1` 这类标签从哪里来？
3. PCAP 的三包窗口如何变成一行样本？
4. 一个谓词的 support 怎么计算？
5. hitting set 为什么能生成覆盖所有样本的规则？
6. 为什么析取项越少规则越强？
7. `entails` 为什么通过 `rules AND NOT query` 的不可满足性判断？
8. 当前仓库和论文完整系统之间差了哪些阶段？

如果能清楚回答这些问题，就已经掌握了这个项目的核心逻辑。
