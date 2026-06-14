# Change Log / 变更记录

## 说明 / Note

This file records version-level changes for the locally initialized Git history of this repository.  
本文档记录当前仓库在本地初始化 Git 之后的版本级变更内容。

Because the original project directory did not contain Git metadata when this task started, the pristine upstream state was not committed as a separate baseline revision.  
由于本次任务开始时原项目目录并不包含 Git 元数据，因此最初的上游原始状态没有作为单独的基线提交保存。

## Versions / 版本记录

### v0.2.28

- Commit subject / 提交主题
  `v0.2.28 对比新旧 term 结构 / Compare legacy and new term structures`
- Scope / 范围
  补充新版 `lhs_term/rhs_term` 与旧版 `lhs/rhs_field/rhs_constant` 的差异说明，并同步维护项目帮助文档和对话归档。
- Key changes / 关键改动
  - 在 `helper.md` 中新增“新版 term 结构 vs 旧版 term 结构”专节。
  - 说明旧版结构主要支持字段-字段、字段-常量比较。
  - 说明新版 term 结构可表达字段、常量、字段乘常量、字段加字段/常量等更通用的比较项。
  - 说明 `build_legacy_rhs_term()` 和 `lhs` 包装逻辑如何保留旧版配置兼容性。
  - 在 `conversion.md` 中追加第 52 条快照索引和详细双语问答记录。

### v0.2.27

- Commit subject / 提交主题
  `v0.2.27 说明 domain 常量选择逻辑 / Explain domain constant selection logic`
- Scope / 范围
  补充 `select_constants()` 中 domain 模式的常量来源选择说明，并同步维护对话归档。
- Key changes / 关键改动
  - 在 `helper.md` 中详细拆解 `field.domain or prepared.value_catalog.get(field_name, [])`。
  - 说明人工 `field.domain` 优先于当前数据样本构建的 `value_catalog`。
  - 说明 `SelectedConstant(value=value, label=None)` 中 `label=None` 的原因。
  - 在 `conversion.md` 中追加第 51 条快照索引和详细双语问答记录。

### v0.2.26

- Commit subject / 提交主题
  `v0.2.26 说明 SelectedConstant 赋值链路 / Explain SelectedConstant assignment flow`
- Scope / 范围
  补充 `SelectedConstant` 的赋值来源说明，并同步维护项目帮助文档和对话归档。
- Key changes / 关键改动
  - 在 `projection.py` 的 `SelectedConstant` 注释中说明它只是 dataclass 容器，真正赋值发生在常量选择函数中。
  - 在 `helper.md` 中新增 `SelectedConstant` 专节，解释 `select_constants()` 和 `select_quantifier_constants()` 如何构造 `value` 与 `label`。
  - 说明 `value` 参与 AST 比较，`label` 只用于 p50/top1 等解释展示。
  - 在 `conversion.md` 中追加第 50 条快照索引和详细双语问答记录。

### v0.2.25

- Commit subject / 提交主题
  `v0.2.25 说明字段可复用常量 / Explain field reusable constants`
- Scope / 范围
  补充 `FieldSpec.constants` 的项目化说明，并同步维护对话归档。
- Key changes / 关键改动
  - 在 `helper.md` 中新增 `FieldSpec.constants` 说明，解释它是字段级人工声明常量池。
  - 对比 `explicit`、`domain`、`profile`、`field_constants` 四种常量来源。
  - 说明 `projection.select_constants()` 只有在 grammar 使用 `mode="field_constants"` 时才读取字段常量。
  - 在 `conversion.md` 中追加第 49 条快照索引和详细双语问答记录。

### v0.2.24

- Commit subject / 提交主题
  `v0.2.24 补齐主包中文注释 / Expand Chinese comments across main package`
- Scope / 范围
  在不改变代码逻辑的前提下，按 `dataset.py` / `projection.py` 的解释粒度补齐 `netnomos` 主包中注释仍偏简略的文件；已足够详细的模块不重复扩写。
- Key changes / 关键改动
  - 为 `ast.py` 补充 AST 节点、序列化/反序列化和字符串渲染的详细中文说明。
  - 为 `dsl.py` 补充 Token、词法规则、递归下降解析和优先级的详细中文说明。
  - 为 `theory.py` 补充 DataFrame 求值、逐行回退、Z3 降阶、符号类型和向量化路径的详细中文说明。
  - 为 `learners/hittingset.py` 与 `learners/tree.py` 补充 evidence set、搜索剪枝、后端选择、决策树路径转规则等说明。
  - 为 `interpreter.py`、`semantic_values.py`、`artifacts.py`、`logging_utils.py` 和入口导出文件补充职责说明。
  - 在 `conversion.md` 中追加第 48 条快照索引和详细双语问答记录。

### v0.2.23

- Commit subject / 提交主题
  `v0.2.23 细化 projection 中文注释 / Expand Chinese comments in projection`
- Scope / 范围
  在不改变 `netnomos/projection.py` 代码逻辑的前提下，按 `dataset.py` 的注释风格补充详细中文说明，并同步维护 `conversion.md`。
- Key changes / 关键改动
  - 扩展 `projection.py` 模块级说明，明确其在 `GrammarSpec + PreparedDataset -> GroundedPredicate` 链路中的职责。
  - 为 `GroundedPredicate`、`GeneratedTerm`、`SelectedConstant` 补充字段级中文说明。
  - 细化 `generate_predicates()`、`generate_terms()`、`select_fields()`、`select_constants()`、兼容性过滤和量词投影相关函数的中文注释。
  - 在 `conversion.md` 中追加第 47 条快照索引和详细双语问答记录。

### v0.2.22

- Commit subject / 提交主题
  `v0.2.22 补齐对话归档并建立同步约定 / Backfill conversation archive and sync rule`
- Scope / 范围
  重写并补齐 `conversion.md`，将此前只记录初始阶段的快照扩展为覆盖当前协作历史的双语摘要归档。
- Key changes / 关键改动
  - 按时间线补充从项目初始化、文档创建、CLI/API/specs/dataset 注释，到 PCAP 文档和 dataset 阅读问答的主要记录。
  - 将 `conversion.md` 定位为持续维护的双语对话归档，而不是一次性快照。
  - 将前半部分调整为“快照索引”，并在后半部分新增“详细对话内容”，用相同编号关联摘要表格和详细问答。
  - 增加后续维护约定：每次新的项目问答、文档更新、注释更新或版本提交都同步追加到 `conversion.md`。

### v0.2.21

- Commit subject / 提交主题  
  `v0.2.21 细化 PCAP 解析中文注释 / Expand PCAP parsing comments`
- Scope / 范围  
  在 `netnomos/dataset.py` 中补充 `read_pcap()` 的详细中文注释，说明 PCAP 如何逐包解析并扁平化为 DataFrame。
- Key changes / 关键改动
  - 说明 PCAP 原始形态是网络包序列，输出 DataFrame 中一行代表一个包。
  - 说明 Scapy 的 `PcapReader`、`Ether`、`IP`、`TCP`、`UDP` 在解析中的作用。
  - 说明固定 row 模板为什么需要先填充 None。
  - 说明 frame、Ethernet、IP、TCP、TCP options、UDP 各字段的抽取逻辑。

### v0.2.20

- Commit subject / 提交主题  
  `v0.2.20 细化值目录构建中文注释 / Expand value catalog comments`
- Scope / 范围  
  在 `netnomos/dataset.py` 中补充 `build_value_catalog()` 的详细中文注释，说明字段值目录如何为后续常量选择提供候选值。
- Key changes / 关键改动
  - 说明 value catalog 的输出结构是字段名到候选值列表的映射。
  - 说明显式 `domain` 优先于当前样本统计值的原因。
  - 说明为什么跳过不存在于 DataFrame 的字段以及为什么先 `dropna()`。
  - 说明离散字段与数值字段在候选值收集上的处理方式。

### v0.2.19

- Commit subject / 提交主题  
  `v0.2.19 细化上下文字段推断中文注释 / Expand context field inference comments`
- Scope / 范围  
  在 `netnomos/dataset.py` 中补充 `CTX_PATTERNS` 和 `enrich_context_families()` 的详细中文注释，说明外部已展开窗口列如何被识别为上下文字段。
- Key changes / 关键改动
  - 说明 `*_ctxN` 和 `*CtxN` 两类窗口列名模式分别如何匹配。
  - 说明 `base` 会成为 `context_family`，`index` 会成为 `context_index`。
  - 说明为什么跳过没有 `FieldSpec` 的列和已经标注过 `context_family` 的字段。
  - 说明 `model_copy(update=...)` 如何保留原字段元数据并补充窗口角色。

### v0.2.18

- Commit subject / 提交主题  
  `v0.2.18 细化派生变量中文注释 / Expand derived variable comments`
- Scope / 范围  
  在 `netnomos/dataset.py` 中补充 `apply_derived_variables()` 的详细中文注释，说明派生变量如何更新 DataFrame、字段元数据和来源记录。
- Key changes / 关键改动
  - 说明派生变量是由已有列计算出来的新列，后续可参与谓词生成和规则学习。
  - 说明 `frame`、`field_specs`、`provenance` 三份返回状态分别服务的后续环节。
  - 说明 `inputs`、`numerator`、`denominator` 的引用完整性检查逻辑。
  - 说明 `compute_derived_column()`、`FieldSpec` 补登记和 `model_dump(mode="json")` 的作用。

### v0.2.17

- Commit subject / 提交主题  
  `v0.2.17 细化必需列校验中文注释 / Expand required-column validation comments`
- Scope / 范围  
  在 `netnomos/dataset.py` 中补充 `validate_required_columns()` 的详细中文注释，说明上下文窗口依赖列的校验逻辑。
- Key changes / 关键改动
  - 说明 `partition_by` 和 `order_by` 为什么属于窗口化硬依赖列。
  - 说明 `required`、`missing` 和 `excluded_fields` 在错误检查中的作用。
  - 说明如果必需列被预处理或缺失列剔除阶段移除，为什么需要快速失败。

### v0.2.16

- Commit subject / 提交主题  
  `v0.2.16 细化映射规则中文注释 / Expand mapping rule comments`
- Scope / 范围  
  在 `netnomos/dataset.py` 和 `netnomos/specs.py` 中补充 `MappingRuleMode` 与 `apply_mapping_rules()` 的详细中文说明。
- Key changes / 关键改动
  - 说明 `EQUALS`、`IN`、`PREFIX`、`REGEX`、`RANGE`、`DEFAULT` 每种映射规则的匹配语义。
  - 说明 `DEFAULT` 只设置兜底值，不会立即短路返回。
  - 说明 `MAP_RULES` 与简单字典映射 `MAP_VALUES` 的区别。
  - 在 `apply_mapping_rules()` 每个分支中补充命中条件、替换行为和典型使用场景。

### v0.2.15

- Commit subject / 提交主题  
  `v0.2.15 细化预处理步骤中文注释 / Expand preprocessing step comments`
- Scope / 范围  
  在 `netnomos/dataset.py` 和 `netnomos/specs.py` 中补充 `PreprocessKind` 各类预处理动作的详细中文说明。
- Key changes / 关键改动
  - 在 `PreprocessKind` 枚举注释中说明 `RENAME`、`DROP`、`CAST`、`PARSE_HEX`、`FILLNA`、`MAP_VALUES`、`MAP_RULES`、`FILTER_EQUALS`、`FILTER_IN`、`FILTER_PRESENT`、`SORT` 的含义。
  - 在 `apply_preprocessing()` 的每个分支前补充中文注释，说明对应步骤读取哪些配置字段、如何修改 DataFrame。
  - 补充说明预处理步骤按顺序执行，前一步可能影响后一步的输入列、行集合和排序结果。

### v0.2.14

- Commit subject / 提交主题  
  `v0.2.14 新增 PCAP 数据格式 Word 文档 / Add PCAP data format Word document`
- Scope / 范围  
  新增面向中文开发者的 PCAP 数据格式说明文档，采用博客分享文体解释 PCAP 原始形态、文件结构、packet record、与 CSV 的区别，以及 `read_pcap()` 如何将其转换为 DataFrame。
- Key changes / 关键改动
  - 新增 `docs/pcap_data_format_blog.docx` Word 文档。
  - 新增 `docs/pcap_data_format_blog.md` 作为可维护的正文源文档。
  - 新增 `docs/assets/pcap_concept.png` 概念图，用于说明 PCAP 到 DataFrame 的转换过程。
  - 使用 LibreOffice 和 `pdftoppm` 将 DOCX 渲染为页面 PNG 并完成视觉检查。

### v0.2.13

- Commit subject / 提交主题  
  `v0.2.13 说明 configured_exclude_fields 含义 / Document configured_exclude_fields semantics`
- Scope / 范围  
  在 `netnomos/dataset.py` 中补充 `configured_exclude_fields` 的详细中文注释，说明它和自动剔除字段的区别。
- Key changes / 关键改动
  - 说明 `configured_exclude_fields` 只记录用户在 `DatasetSpec.exclude_fields` 中显式排除且实际存在的字段。
  - 说明它不同于 `excluded_fields`，后者记录系统因 NaN 或空字符串自动剔除的字段。
  - 在 `PreparedDataset` 字段定义、`prepare_dataset()` 主流程和 `apply_field_selection()` 中补充对应说明。

### v0.2.12

- Commit subject / 提交主题  
  `v0.2.12 细化 dataset 中文注释 / Expand Chinese comments in dataset`
- Scope / 范围  
  在不改变 `netnomos/dataset.py` 逻辑的前提下，补充详细中文注释，帮助阅读数据加载、预处理、窗口展开和派生变量流程。
- Key changes / 关键改动
  - 重写 `dataset.py` 的模块级说明，明确其在数据准备链路中的职责。
  - 为 `PreparedDataset`、`prepare_dataset()`、`resolve_source()`、`apply_preprocessing()`、`apply_field_selection()` 等核心入口补充详细中文说明。
  - 为上下文窗口展开、派生变量计算、值目录构建、上下文族索引、缺失列剔除等关键步骤补充流程性注释。
  - 为 `read_pcap()` 中的链路层、IP、TCP、UDP 字段提取逻辑补充说明。

### v0.2.11

- Commit subject / 提交主题  
  `v0.2.11 新增 grammar 到候选谓词阅读笔记 / Add reading note for grammar-to-predicate flow`
- Scope / 范围  
  新增 `read.md`，单独梳理 `specs.py` 的职责边界，以及 `grammar.json` 如何一路变成候选谓词。
- Key changes / 关键改动
  - 说明 `specs.py` 定义的是配置模型层和规则搜索空间模板，而不是执行器本身。
  - 说明 `FieldSpec`、`VariableSelectorSpec`、`ConstantSelectorSpec`、`PredicateTemplateSpec`、`QuantifierTemplateSpec` 各自负责什么。
  - 说明 `NetNomosMiner.fit()`、`prepare_dataset()`、`generate_predicates()`、`select_fields()`、`select_constants()`、`project_quantified_family()` 等函数在主链路中的作用。
  - 说明 `grammar.json` 从 Pydantic 模型到 `GroundedPredicate` 列表的完整路径。
  - 给出这一条源码主线的推荐阅读顺序。

### v0.2.10

- Commit subject / 提交主题  
  `v0.2.10 补充 Pydantic 核心组件说明 / Add Pydantic core component helper`
- Scope / 范围  
  在 `helper.md` 中补充 `BaseModel`、`ConfigDict`、`Field`、`model_validator` 的项目化说明，帮助理解 `netnomos/specs.py` 的配置模型写法。
- Key changes / 关键改动
  - 说明 `BaseModel` 在项目中承担“结构化配置对象基类”的角色。
  - 说明 `ConfigDict` 控制模型级校验策略，如 `extra="forbid"` 和 `populate_by_name=True`。
  - 说明 `Field` 负责字段默认值、默认工厂、alias 和元信息。
  - 说明 `model_validator` 负责跨字段联动校验与规范化。
  - 总结四者在 NetNomos 配置系统中的协作关系。

### v0.2.9

- Commit subject / 提交主题  
  `v0.2.9 修正 populate_by_name 注释说明 / Clarify populate_by_name comments`
- Scope / 范围  
  修正 `netnomos/specs.py` 中对 `populate_by_name=True` 的中文注释，并在 `helper.md` 中补充更准确的项目化解释。
- Key changes / 关键改动
  - 将 `populate_by_name=True` 的说明从“按字段名赋值与序列化”修正为“当存在 alias 时仍允许按真实字段名传值”。
  - 补充说明它主要影响模型构造阶段，而不是直接决定导出时是否使用 alias。
  - 在 `helper.md` 中加入独立小节，给出 alias / 字段名的直观示例。

### v0.2.8

- Commit subject / 提交主题  
  `v0.2.8 补充 Pydantic 项目说明 / Add project-focused Pydantic helper`
- Scope / 范围  
  在 `helper.md` 中新增 `pydantic` 的项目化说明，聚焦它在 `netnomos/specs.py` 和配置驱动流程中的作用。
- Key changes / 关键改动
  - 说明 `pydantic` 在 NetNomos 中的职责是把外部 JSON 配置转成内部强类型对象。
  - 说明 `BaseModel`、`ConfigDict(extra="forbid")`、`Field(default_factory=...)` 在本项目中的实际意义。
  - 说明 `pydantic` 在配置加载、早期报错、结构校验和模块协作中的位置。
  - 结合 `SourceSpec`、`DatasetSpec`、`GrammarSpec` 的使用场景给出阅读指引。

### v0.2.7

- Commit subject / 提交主题  
  `v0.2.7 新增 Enum 使用说明文档 / Add Enum usage helper document`
- Scope / 范围  
  新增并定位 `helper.md` 为“项目相关类与工具使用手册”，首篇内容介绍 Python `Enum` 的作用、常见用法以及它在 `netnomos/specs.py` 中的实际用途。
- Key changes / 关键改动
  - 为 `helper.md` 增加文档职责说明，明确它用于沉淀 NetNomos 项目相关类、枚举、配置结构与工具的使用方法。
  - 说明 `Enum` 的基本概念与价值。
  - 说明 `class X(str, Enum)` 的常见写法。
  - 说明 `.value`、从字符串构造、遍历、比较等常用用法。
  - 结合 `SourceType`、`ValueType`、`LearnerKind` 等示例解释项目内的实际应用场景。
  - 增加后续维护约定，要求新类和新工具的说明继续同步到 `helper.md`。

### v0.2.6

- Commit subject / 提交主题  
  `v0.2.6 细化 specs 中文注释 / Expand Chinese comments in specs`
- Scope / 范围  
  在不改变 `netnomos/specs.py` 逻辑的前提下，重写并补充详细中文注释，帮助后续阅读配置模型与 JSON 结构。
- Key changes / 关键改动
  - 重写 `specs.py` 的模块级说明，明确其在配置驱动体系中的作用。
  - 为所有核心 Enum、DatasetSpec、GrammarSpec 及相关子模型补充详细中文注释。
  - 为 `PredicateTemplateSpec.validate_shape()`、`DatasetSpec.normalize_legacy_keys()` 等关键校验逻辑补充解释。
  - 清理 `specs.py` 中原有乱码注释，统一为 UTF-8 可读文本。

### v0.2.5

- Commit subject / 提交主题  
  `v0.2.5 补充 artifacts 写入含义注释 / Document artifact outputs in API`
- Scope / 范围  
  在 `netnomos/api.py` 的 `_write_artifacts()` 中补充所有输出文件与关键摘要字段的含义说明，不改变代码逻辑。
- Key changes / 关键改动
  - 为 `dataset_spec.json`、`grammar_spec.json`、`fields.json`、`derived_variables.json` 等文件增加用途注释。
  - 为 `manifest.json` 中各字段的意义增加逐项说明。
  - 为 `predicates.jsonl`、`rules.json`、`interpreted_predicates.clj`、`interpreted_rules.clj` 增加内容说明。

### v0.2.4

- Commit subject / 提交主题  
  `v0.2.4 细化 API 中文注释 / Expand Chinese comments in API`
- Scope / 范围  
  在不改变 `netnomos/api.py` 逻辑的前提下，重写并补充详细中文注释，帮助中文开发者理解高层流程编排。
- Key changes / 关键改动
  - 重写 `api.py` 的模块级说明，明确其在系统中的编排角色。
  - 为 `MiningResult` 和 `NetNomosMiner` 的关键方法补充详细中文 docstring。
  - 为 `fit()` 的主流程、规则验证、解释、蕴含、缓存和工件落盘逻辑补充中文注释。
  - 清理 `api.py` 中原有乱码注释，统一为 UTF-8 可读文本。

### v0.2.3

- Commit subject / 提交主题  
  `v0.2.3 细化 CLI main 中文流程注释 / Expand Chinese flow comments in CLI main`
- Scope / 范围  
  进一步补充 `netnomos/cli.py` 中 `main()` 函数内部的中文流程注释，帮助中文开发者沿命令分支理解执行脉络。
- Key changes / 关键改动
  - 为 `main()` 中的参数解析、日志初始化、轻量命令、miner 构造等阶段补充详细中文注释。
  - 为 `show-dataset`、`show-grammar`、`prepare`、`learn`、`validate`、`interpret`、`entails` 分支补充执行意图说明。
  - 明确说明“已有规则模式”和“先学习再操作模式”的差异。

### v0.2.2

- Commit subject / 提交主题  
  `v0.2.2 将 CLI 用户文案改为双语 / Make CLI user-facing text bilingual`
- Scope / 范围  
  将 `netnomos/cli.py` 中所有面向终端用户的描述、示例、帮助文本改为中英双语。
- Key changes / 关键改动
  - 将顶层 `CLI_DESCRIPTION` 改为中英双语。
  - 将 `CLI_EPILOG` 中的示例改为中英双语说明。
  - 将全局参数、子命令参数、子命令帮助文本和描述全部改为中英双语。
  - 清理 `cli.py` 中原有乱码注释，统一为 UTF-8 可读文本。

### v0.2.1

- Commit subject / 提交主题  
  `v0.2.1 细化 CLI 中文注释 / Refine Chinese comments in CLI`
- Scope / 范围  
  重新整理 `netnomos/cli.py` 的中文注释层，提升中文开发者阅读命令行入口时的理解效率。
- Key changes / 关键改动
  - 重写 `cli.py` 的模块级说明。
  - 为各类 `add_*_arg()` 参数装配函数补充详细中文注释。
  - 为 `build_parser()`、`build_fit_kwargs()`、`build_miner()`、`main()` 增加流程性说明。
  - 补充子命令分支的执行意图说明，包括 `prepare`、`learn`、`validate`、`interpret`、`entails`。

### v0.2.0

- Commit subject / 提交主题  
  `v0.2.0 新增中文与双语项目文档 / Add Chinese and bilingual project documentation`
- Scope / 范围  
  补齐中文说明文档、项目结构文档、对话归档和变更记录。
- Key changes / 关键改动
  - 新增 `README_ZH.md` 中文主说明文档。
  - 新增 `project.md` 双语项目结构说明。
  - 新增 `conversion.md` 双语会话归档。
  - 新增 `Change.md` 版本变更记录。
  - 说明外层主仓库与内层重复目录的关系。

### v0.1.0

- Commit subject / 提交主题  
  `v0.1.0 初始化仓库并补充中文代码注释 / Initialize repo and add Chinese code comments`
- Scope / 范围  
  初始化外层 `NetNomos-main` 为 Git 仓库，并补充核心代码、测试、脚本、C++ 扩展和构建文件的中文注释。
- Key changes / 关键改动
  - 为 `netnomos/` 主包中的模块、类、函数补充中文说明。
  - 为 `tests/` 中的测试补充中文目的说明。
  - 为 `scripts/`、`setup.py`、`pyproject.toml`、`cpp/hittingset_native.cpp` 补充中文注释。
  - 在 `.gitignore` 中显式忽略重复嵌套的 `NetNomos-main/NetNomos-main` 目录。

## Verification / 验证

- Test command / 测试命令  
  `python -m pytest tests`
- Result / 结果  
  `26 passed, 1 skipped`
