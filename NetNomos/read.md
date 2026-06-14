# NetNomos 阅读笔记 / Reading Notes

## 1. 这份笔记的目的

这份文档用于记录“阅读源码时容易混淆、但又非常关键”的主线问题。

本轮先整理两个核心点：

1. `netnomos/specs.py` 的作用到底是什么
2. `examples/grammars/*.json` 这类 `grammar.json` 配置，最终是怎么变成一批候选谓词的

这不是 API 手册，而是源码阅读导图。

---

## 2. `specs.py` 的作用是什么

### 2.1 一句话概括

`netnomos/specs.py` 定义的不是“最终执行逻辑”，而是：

**NetNomos 的配置模型层，以及规则搜索空间的声明式语法。**

它解决的是：

- 外部 JSON 配置允许长成什么样
- 数据字段有哪些语义属性
- grammar 允许生成哪些结构的谓词
- 常量、字段、量词模板应该如何声明

换句话说，它主要定义“允许什么”，不负责真正“怎么跑”。

### 2.2 它涉及哪些功能

`specs.py` 主要覆盖两大类功能。

#### A. 数据语义建模

主要类：

- `SourceSpec`
- `FieldSpec`
- `DerivedVariableSpec`
- `DatasetSpec`

这些类负责定义：

- 数据源类型和路径
- 字段名、值类型、语义角色
- 派生变量如何声明
- 数据预处理、窗口化、字段元信息如何组织

这部分回答的是：

**系统有哪些原材料可以用来生成规则。**

#### B. 规则搜索空间建模

主要类：

- `VariableSelectorSpec`
- `ConstantSelectorSpec`
- `TermTemplateSpec`
- `PredicateTemplateSpec`
- `QuantifierTemplateSpec`
- `GrammarSpec`

这些类负责定义：

- 字段怎么筛
- 常量从哪里来
- 左右项允许长成什么形状
- 允许哪些比较符
- 是否允许量词模板

这部分回答的是：

**系统允许从这些原材料里拼出哪些候选谓词。**

### 2.3 更准确的边界

如果只用一句话总结 `specs.py`：

**它定义的是“配置语法”和“搜索空间模板”，不是“执行器”。**

真正执行这些模板定义的核心代码不在 `specs.py`，而在：

- [`netnomos/api.py`](./netnomos/api.py)
- [`netnomos/dataset.py`](./netnomos/dataset.py)
- [`netnomos/projection.py`](./netnomos/projection.py)
- [`netnomos/theory.py`](./netnomos/theory.py)

---

## 3. 你刚才那段理解，修正后的准确版本

你的原始理解大方向是对的：

- `QuantifierTemplateSpec`、`VariableSelectorSpec`、`ConstantSelectorSpec` 这些类，确实在定义一套“声明式语法”
- 这套语法控制字段如何被筛选、常量如何被选取、允许哪些比较形式

但更准确的说法是：

**`specs.py` 定义了 NetNomos 的规则生成模板语法，以及支撑这些模板的数据元信息。**

它不是直接执行“检索和操作”，而是先把这些“可检索方式、可选值来源、可用操作符、可用结构形状”描述出来。

后续执行模块再根据这些描述去真正展开。

---

## 4. `grammar.json` 是怎么变成候选谓词的

这一段是理解 NetNomos 运行脉络的关键。

### 4.1 第一步：读取 `grammar.json`

涉及代码：

- [`netnomos/specs.py`](./netnomos/specs.py)
  - `GrammarSpec`
  - `PredicateTemplateSpec`
  - `QuantifierTemplateSpec`
  - `VariableSelectorSpec`
  - `ConstantSelectorSpec`
  - `load_model()`
  - `load_grammar_spec()`

这里发生的事：

1. 从磁盘读取 JSON 文本
2. 交给 Pydantic 模型解析
3. 变成一个强类型 `GrammarSpec` 对象

结果是：

- 原本松散的 JSON
- 变成结构清晰、字段合法、类型受控的 grammar 配置对象

### 4.2 第二步：在 `fit()` 中进入候选谓词生成阶段

涉及代码：

- [`netnomos/api.py`](./netnomos/api.py)
  - `NetNomosMiner.fit()`

关键主线：

1. `fit()` 先准备数据
2. 再调用 `generate_predicates(prepared, self.grammar_spec)`
3. 把 grammar 配置真正展开成候选谓词列表

这一步是从“配置对象”进入“搜索空间实例化”的入口。

### 4.3 第三步：准备数据集元信息

涉及代码：

- [`netnomos/dataset.py`](./netnomos/dataset.py)
  - `prepare_dataset()`
  - `PreparedDataset`

这一步的意义是：

- 把原始数据读进来
- 建好 `field_specs`
- 建好 `context_families`
- 建好 `value_catalog`
- 准备后续字段筛选和常量选择所需的统计信息

因为 grammar 本身只定义“怎么选”，真正能不能选出来，取决于 `PreparedDataset` 里准备好的这些元信息。

### 4.4 第四步：`generate_predicates()` 开始展开模板

涉及代码：

- [`netnomos/projection.py`](./netnomos/projection.py)
  - `generate_predicates()`
  - `append_candidate()`

这是最核心的一步。

`generate_predicates(prepared, grammar)` 会遍历：

- `grammar.predicate_templates`
- `grammar.quantifier_templates`

然后把每个模板实例化成很多具体谓词。

最终输出类型是：

- `list[GroundedPredicate]`

也就是“已经具体化好的候选谓词列表”。

---

## 5. 普通谓词模板是怎么展开的

### 5.1 涉及哪些代码

主要看 [`netnomos/projection.py`](./netnomos/projection.py)：

- `generate_predicates()`
- `select_fields()`
- `select_constants()`
- `compatible_fields()`
- `compatible_constant()`
- `generate_terms()`
- `compatible_terms()`

### 5.2 基本思路

以 `PredicateTemplateSpec` 为例，它描述的是一类原子条件模板，比如：

- 字段 vs 字段
- 字段 vs 常量
- 项 vs 项

展开时大致分三类。

#### A. 字段 vs 字段

例如：

- `lhs` 用 `VariableSelectorSpec` 挑出一批左字段
- `rhs_field` 再挑出一批右字段
- `operators` 提供允许的比较符

然后系统做笛卡尔组合，再过滤不合理组合：

- 是否允许同字段比较
- 数值字段是否可比
- 类型是否兼容

最后得到像这样的候选：

- `Bytes > Packets`
- `Seq = Ack`

#### B. 字段 vs 常量

例如：

- `lhs` 先挑出字段
- `rhs_constant` 决定常量从哪里来

常量来源可能是：

- `explicit`
- `domain`
- `profile`
- `field_constants`

然后系统继续做兼容性过滤，得到像这样的候选：

- `Bytes > 512`
- `Proto = TCP`

#### C. 项 vs 项

当模板里用到 `lhs_term` / `rhs_term` 时，就不是简单字段比较了，而是先生成“项”。

涉及代码：

- `generate_terms()`

它会把模板展开成具体项，例如：

- `Bytes`
- `Packets * 65535`
- `Header + Payload`

然后再把左右项做组合，生成像这样的候选：

- `Bytes + Header > 1500`
- `Packets * 2 > Window`

---

## 6. `VariableSelectorSpec` 和 `ConstantSelectorSpec` 在这里分别干什么

### 6.1 `VariableSelectorSpec`

它的本质是：

**字段筛选器**

涉及代码：

- [`netnomos/specs.py`](./netnomos/specs.py)
  - `VariableSelectorSpec`
- [`netnomos/projection.py`](./netnomos/projection.py)
  - `select_fields()`

它定义“字段候选池如何被筛出来”，常见筛选维度有：

- `names`
- `regex`
- `types`
- `roles`
- `derived_only`
- `context_family`
- `window_only`
- `exclude`

也就是说，它不直接做比较，它只负责“先把可参与比较的字段集合挑出来”。

### 6.2 `ConstantSelectorSpec`

它的本质是：

**常量候选器**

涉及代码：

- [`netnomos/specs.py`](./netnomos/specs.py)
  - `ConstantSelectorSpec`
- [`netnomos/projection.py`](./netnomos/projection.py)
  - `select_constants()`
  - `select_quantifier_constants()`

它定义“常量候选值从哪里来”，常见模式有：

- `explicit`：直接使用 `values`
- `domain`：从字段离散值域取
- `profile`：从数据统计中取，例如 quantile 或 top-k
- `field_constants`：复用 `FieldSpec.constants`

所以你前面说的“直接使用 values 还是 top-k”，这个理解是对的。

---

## 7. 量词模板是怎么变成候选谓词的

### 7.1 涉及哪些代码

主要看 [`netnomos/projection.py`](./netnomos/projection.py)：

- `select_context_families()`
- `select_quantifier_constants()`
- `project_quantified_family()`

### 7.2 核心思路

`QuantifierTemplateSpec` 定义的是一类量词模板，例如：

- `forall`
- `exists`

但系统内部不会长期保留抽象量词形式，而是把它投影成有限公式。

例如文档注释里已经写得很清楚：

- `forall X[k] >= c  -> min(X_*) >= c`
- `exists X[k] >= c  -> max(X_*) >= c`

对等号 / 不等号这类情况，则可能展开成：

- `BoolAnd(...)`
- `BoolOr(...)`

也就是说，量词模板最后还是会落到一批普通的 AST 公式节点上。

---

## 8. 最终“候选谓词”长什么样

涉及代码：

- [`netnomos/projection.py`](./netnomos/projection.py)
  - `GroundedPredicate`
- [`netnomos/ast.py`](./netnomos/ast.py)
  - `Compare`
  - `SymbolRef`
  - `Constant`
  - `BinaryTerm`
  - `FuncCall`
  - `BoolAnd`
  - `BoolOr`

一个候选谓词并不只是字符串，它通常包含：

- `predicate_id`
- `formula`
- `display`
- `support`
- `source`

其中：

- `formula` 是结构化 AST
- `display` 是可读文本
- `support` 是这个谓词在数据上的满足率
- `source` 记录这个候选来自哪个模板、哪个字段组合、哪个常量来源

### 8.1 支持率是怎么得到的

涉及代码：

- [`netnomos/projection.py`](./netnomos/projection.py)
  - `generate_predicates()`
- [`netnomos/theory.py`](./netnomos/theory.py)
  - `evaluate_formula_df()`

生成候选之后，系统会逐个在 dataframe 上评估它们，然后求均值，得到支持率。

所以“候选谓词生成”不是只做结构展开，还顺带完成了第一轮数据打分。

---

## 9. 推荐的阅读顺序

如果你想顺着这条主线读源码，推荐顺序如下：

1. [`netnomos/specs.py`](./netnomos/specs.py)
先看 `FieldSpec`、`VariableSelectorSpec`、`ConstantSelectorSpec`、`PredicateTemplateSpec`、`QuantifierTemplateSpec`、`GrammarSpec`

2. [`netnomos/dataset.py`](./netnomos/dataset.py)
重点看 `PreparedDataset` 和 `prepare_dataset()`

3. [`netnomos/projection.py`](./netnomos/projection.py)
重点看 `generate_predicates()`，然后看 `select_fields()`、`select_constants()`、`project_quantified_family()`

4. [`netnomos/api.py`](./netnomos/api.py)
回到 `NetNomosMiner.fit()`，看它怎么把 prepare、projection、learner 串起来

---

## 10. 一句话总结

如果你只记一句话：

**`specs.py` 定义规则搜索空间的声明式模板，`projection.py` 负责把这些模板真正展开成一批可评估的候选谓词。**
