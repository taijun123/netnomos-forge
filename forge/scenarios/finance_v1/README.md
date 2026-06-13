# finance_v1 — 合成财务报表场景

财务场景三件套：**数据生成（generator）→ 错误注入（faults）→ 校验（validator）**，
配套 NetNomos 格式的 dataset/grammar/manual_rules 与双轨报告模板。

## 文件清单

| 文件 | 说明 |
|---|---|
| `generator.py` | 确定性合成 960 行训练数据（3 行业 × 40 公司 × 8 期，seed=42），恒等式正向推导 |
| `faults.py` | 构造"华信咨询"8 期清洁基线并注入 F1/F2a/F2b/F3/F4，输出资料包 CSV + truth_table.json |
| `validator.py` | FinanceValidator：纯 pandas 实现 R01–R05 + R06（行业存货区间）+ R07（应收/营收背离） |
| `dataset_spec.json` | NetNomos DatasetSpec（字段类型、中文 source_name、CompanyId 分区 / PeriodIndex 排序） |
| `grammar_spec.json` | NetNomos GrammarSpec（比较 / addition 线性恒等式 / 蕴含式谓词空间，常量来自分位数与区间端点） |
| `manual_rules.json` | R01–R05 人工规则（golden rules.json 同构格式，学不出来时兜底注入） |
| `report_template.md` | 《华信咨询年度财务分析与审阅报告》模板，正文数值一律 `{{slot}}` 槽位 |

## 快速使用

```python
from forge.scenarios.finance_v1.generator import generate_training_data, save_csv
from forge.scenarios.finance_v1.faults import inject_faults, save_package
from forge.scenarios.finance_v1.validator import FinanceValidator

df = generate_training_data(seed=42)            # 960 行干净数据
save_csv(df, "data/finance_v1_train.csv")       # 英文表头
save_csv(df, "data/finance_v1_train_zh.csv", use_source_names=True)  # 中文表头

df_faulty, truth = inject_faults()              # 华信咨询资料包 + 真值表
report = FinanceValidator().validate(df_faulty) # 恰好 5 项违规，与真值表一一对应
```

## ⚠ 待宿主机 netn 实测微调

`dataset_spec.json` / `grammar_spec.json` / `manual_rules.json` 按
`NetNomos/examples/{datasets,grammars}` 与 `NetNomos/rules/golden_cidds/rules.json`
的真实格式起草，但以下点需在宿主机 `netn` 实测后微调：

1. **中文 source_name**：spec 中 source_name 为中文表头（对应
   `save_csv(use_source_names=True)` 导出）；若 netn 摄入英文表头 CSV，需确认其
   是否在缺少 source_name 列时回退到 name，否则删掉 source_name 字段即可。
2. **跨期规则（R03/R04）的窗口语义**：manual_rules.json 用 `_ctx0/_ctx1` 后缀
   表示 本期/下期（参考 golden_mawi 的 context window 命名），实际滑窗配置
   （按 CompanyId 分区、PeriodIndex 排序、窗口=2）需对照 netn 的 dataset
   预处理/窗口参数确认；必要时在 `derived_variables` 预物化 `Prev_*` 滞后字段。
3. **grammar 的 lhs_term/rhs_term 形态**：`profit-capacity` 模板中
   `{"kind": "field"}` 的 lhs_term 写法未在官方示例出现，若 netn 校验不过，
   改用 addition/scalar 形态或删除该模板。
4. **行业蕴含式**：`Industry=consulting -> InventoryToAssetsBp <= 200` 这类规则
   预期由 learner 在 industry-assignments × ratio-band-thresholds 谓词空间内
   自行组合；若学不出来，走 manual 通道兜底（格式同 manual_rules.json）。

## 设计要点

- **金额千元整数**；派生字段把多元恒等式折叠为二元规则便于语法搜索：
  `InventoryNetInflow = Purchases - COGS`、`InventoryToAssetsBp`、
  `ReceivableToRevenueBp`（万分比四舍五入取整，三模块共用 `generator.bp`）。
- **行业差异化**（生成端取验收区间的"安全内圈"，叠加抖动/取整后仍严格达标）：

  | 行业 | 存货/总资产 | 毛利率 | 应收/营收 |
  |---|---|---|---|
  | consulting | < 2% | 35–55% | 15–35% |
  | retail | 15–30% | 18–30% | 2–10% |
  | manufacturing | 8–20% | 22–38% | 10–25% |

- **错误注入"单点违规、零级联"**：每个 fault 恰好命中一条规则；自洽传播的
  连带篡改（如 F1 的 GrossProfit、F2b 的下期 Cash_Begin、F3 的 Purchases）
  全部登记进 truth_table，详见 `faults.py` 模块注释与
  `docs/FINANCE_SCENARIO.md`。
