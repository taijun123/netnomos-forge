# forge Core SDK（Core-Dev 交付）

实现 `forge/contracts.py` 的三个协议：`RuleEngineAPI` → `ForgeRuleEngine`、
`LLMClient` → `RoutedLLM`、`GeneratorAPI` → `ConstrainedGenerator`。
所有第三方重依赖（netnomos/z3、lejit/torch、ollama）全部**懒加载**：沙箱内可以 import、
可以跑纯 Python 功能；真正触发挖掘/训练时若缺依赖，会抛出带中文指引的 `RuntimeError`。

## 目录约定

```
<workspace>/
├── NetNomos/        # 规则挖掘引擎（uv sync 后可用，数据在 NetNomos/data/）
├── LeJIT/           # 受约束生成器（uv sync 后可用，需 torch）
└── netnomos-forge/  # 本仓库
    ├── forge/core/{engine,explainer,llm,generator}.py
    ├── forge/core/knowledge/            # 全局 RAG 知识库（Markdown / JSON）
    ├── forge/scenarios/network_cidds/   # dataset_spec.json + grammar_spec.json + knowledge/
    ├── forge/scenarios/finance_v1/      # 财务 demo + knowledge/
    ├── forge/rulesets/<scenario>/...    # learn 落盘产物 / golden / lejit_bundle
    └── scripts/host/*.ps1               # 宿主机一键脚本
```

`dataset_spec.json` 的相对 `source.path` **按 spec 文件所在目录解析**（引擎内统一转绝对
路径后经 `input_path=` 传给 NetNomos，规避 NetNomos 按 cwd 解析相对路径的行为）。

---

## 1. ForgeRuleEngine（forge/core/engine.py）

```python
from forge.core.engine import ForgeRuleEngine, save_ruleset, load_ruleset
from forge.core.llm import RoutedLLM

eng = ForgeRuleEngine.from_scenario("network_cidds")   # 读场景目录两个 spec

# 学习：NetNomosMiner.prepare+fit → contracts.RuleSet，
# 自动落盘 forge/rulesets/network_cidds/<时间戳>/{rules.json, ruleset.json, semantic_values.json}
ruleset = eng.learn(None, learner="hitting-set", limit=None)   # None=用 spec 默认数据

# 验证：逐行违规报告（ViolationReport）
report = eng.validate(None, ruleset)
print(report.satisfaction_rate, report.by_rule, report.violations[:3])

# Z3 蕴含检查（assertion 为 NetNomos DSL 公式字符串，如 "Bytes <= 1500"）
ok = eng.check(ruleset, "Bytes <= 1500")

# 规则卡基础模板：llm=None → 确定性中文模板（沙箱可用）
cards = eng.explain(ruleset, llm=None)                 # list[RuleCard]

# 人工规则合并（NetNomos 格式 rules.json，source="manual"，同 id 覆盖）
ruleset2 = eng.add_manual_rules(ruleset, "manual_rules.json")
ruleset2 = save_ruleset(ruleset2)                      # 重新落盘
old = load_ruleset("forge/rulesets/network_cidds/20260613-120000")  # 加载历史
```

要点：
- `Rule.formula` 保存 NetNomos 结构化公式 dict（`formula_to_dict` 产物），`Rule.text`
  为 `LearnedRule.display` 可读形式；`kind` 由 `classify_kind()` 从公式推断
  （implication/identity/exclusion/bound/composite/quantified）。
- **NetNomos `validate_rules` 真实返回结构**（已读源码确认，只有聚合指标）：
  `{"rule_count", "all_rows_satisfied", "mean_satisfaction", "per_rule_satisfaction"}`。
  逐行明细由引擎调 `netnomos.theory.evaluate_formula_df` 自行补算；每条规则最多展开
  50 条 `Violation`（`by_rule` 仍计全量）。
- `engine.explain(..., llm=None)` 只生成确定性基础卡；W4 管线随后调用
  `RuleExplainer.for_scenario(...).enhance(...)` 做 RAG citation、可选 LLM 润色和巧合过滤。

## 2. RuleExplainer（forge/core/explainer.py）

`RuleExplainer` 是规则卡 RAG 接入点，不修改 `contracts.py`。加载顺序：

- 默认 `forge/core/knowledge/`；
- 场景调用 `RuleExplainer.for_scenario("finance_v1" | "network_cidds")`
  时追加 `forge/scenarios/<scenario>/knowledge/`；
- 可用 `FORGE_RAG_KNOWLEDGE_DIRS` 追加本地目录（Windows 用 `;` 分隔）。

支持的知识库格式：

- Markdown：按 `##` 二级标题切成检索片段，一级标题作为 `doc_title`；
- JSON：根对象可含 `doc_title` / `source` / `tags` / `sections`，每个 section
  支持 `heading` / `body` / `tags` / `source`。

运行保护：

- `FORGE_RULECARD_LLM=1` 才会在 server pipeline 对规则卡调用 LLM；
- `FORGE_RULECARD_LLM_MAX_CARDS` 默认 `2`，限制每个 job 最多润色多少张卡；
- `FORGE_RAG_TOP_K` 默认 `3`；
- `FORGE_RAG_MAX_SECTION_CHARS` 默认 `1200`；
- `FORGE_RAG_MAX_CONTEXT_CHARS` 默认 `3600`。

## 3. RoutedLLM（forge/core/llm.py）

`contracts.DEFAULT_LLM_ROUTING` 仍保持冻结契约常量；运行时 `RoutedLLM()` 使用 overlay：
`induce` / `draft` 走本地 Ollama qwen2.5，`explain` 默认走本地 Ollama
`gemma3:27b`，再按 `ollama → codex → mock` 降级。规则卡 explain 走
Ollama `/api/chat`，prompt 采用“英文控制、最终中文输出”：英文约束任务和格式，
最终只返回简体中文规则解释。

```python
from forge.core.llm import RoutedLLM

llm = RoutedLLM()                      # 自动探测：ollama 不通 → codex → mock
llm = RoutedLLM(force_backend="mock")  # 强制确定性 mock（测试/沙箱）
text = llm.complete("解释这条规则", role="explain", system="用中文回答")
```

- `OllamaBackend`：POST `http://localhost:11434/api/generate`；可用
  `FORGE_OLLAMA_HOST` 或 `OLLAMA_HOST` 覆盖地址；
- `FORGE_OLLAMA_EXPLAIN_MODEL` 默认 `gemma3:27b`；
- `FORGE_OLLAMA_DRAFT_MODEL` 默认沿用 `qwen2.5:14b-instruct`；
- `FORGE_OLLAMA_TIMEOUT` 默认 `120` 秒，`FORGE_OLLAMA_PROBE_TIMEOUT` 默认 `2` 秒；
- `CodexBackend`：`codex exec <prompt>` 子进程，180s 超时保护；
- `MockBackend`：确定性模板；运行期真实后端报错也会兜底降级到 mock。

## 4. ConstrainedGenerator（forge/core/generator.py）

```python
from forge.core.generator import ConstrainedGenerator

# 训练（宿主机）：优先 lejit Python API（LeJITConfig + LeJITPipeline，与 lejit CLI 同入口），
# 不可导入时降级 `uv run lejit train` 子进程（cwd=LeJIT 仓库，1h 超时）
gen = ConstrainedGenerator.train("network_cidds", ruleset,
                                 epochs=3, device="cuda", n_samples=100)
# bundle 输出：forge/rulesets/network_cidds/lejit_bundle/

gen = ConstrainedGenerator.from_bundle("network_cidds")   # 加载已训练 bundle
rows = gen.generate(10)                                   # list[dict]，全部满足规则约束
done = gen.complete([{"Proto": "UDP", "DstPortClass": 53}])  # 前缀补全
```

`train(..., base_model="gpt2-medium")` 切换为预训练权重；缺省从零训练 6 层小 GPT-2
（与 LeJIT/configs/cidds/train.toml 一致）。

## 5. 宿主机运行步骤（Windows PowerShell）

```powershell
cd E:\yanchh\model_control\netnomos-forge

# ① 一键学习并归档黄金规则集（NetNomos uv sync → netn learn → 复制产物）
#    产物：forge\rulesets\network_cidds\golden\{rules.json, semantic_values.json, ...}
powershell -ExecutionPolicy Bypass -File scripts\host\run_network_learn.ps1
#    可选参数：-Learner tree  -Limit 1000  -Backend native

# ② 训练 LeJIT bundle（LeJIT uv sync → lejit train；-Gpu 0 即 CUDA_VISIBLE_DEVICES=0）
powershell -ExecutionPolicy Bypass -File scripts\host\train_network_lejit.ps1 -Gpu 0 -Epochs 3

# ③ 受约束生成 1000 行 NetFlow
powershell -ExecutionPolicy Bypass -File scripts\host\generate_network.ps1 -N 1000 -Gpu 0 -Device cuda

# ④ 跑全部测试（宿主机装好 netnomos/lejit 后跳过项会自动变为实测）
python -m unittest discover tests -v
```

## 6. 测试矩阵（tests/）

| 文件 | 沙箱实测 | 宿主机追加 |
|---|---|---|
| test_llm.py | mock 确定性、路由表 model/options、自动降级+日志、运行期兜底 | — |
| test_explainer.py | Markdown/JSON 知识库、多目录、场景检索、prompt 预算、LLM 卡片上限 | — |
| test_engine.py | kind 分类、字段提取、RuleSet 落盘/加载、缺依赖中文报错、人工规则合并、explain 模板/mock | 小样本 learn→validate→check 端到端 |
| test_generator.py | TOML 序列化、配置组装（绝对路径/预训练切换）、缺 lejit+uv 中文报错 | 极小训练+generate/complete 端到端 |

W4 RAG/LLM/pipeline 快速基线：
`PYTHONUTF8=1 python -m unittest tests.test_explainer tests.test_llm tests.test_pipeline -v`
→ **30 tests, OK**。
