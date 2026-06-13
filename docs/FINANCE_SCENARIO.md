# 财务场景（finance_v1）设计与验收说明

> 所有权：Finance-Dev。代码：`forge/scenarios/finance_v1/`、`forge/core/injector.py`；
> 测试：`tests/test_finance_{generator,faults,validator}.py`。
> 接口契约：`forge/contracts.py`（FIN_* 常量、Violation/ViolationReport、FIN_CORE_RULES_ZH、FIN_FAULTS）。

## 1. 数据设计

### 1.1 训练集（960 行）

`generate_training_data(seed=42)`：3 行业（consulting/retail/manufacturing）× 各 40 家公司
× 8 期 = 960 行，金额全部为**千元整数**，列序 = `contracts.FIN_FIELDS`（20 个字段）。

恒等式**正向推导**（生成端 100% 成立，校验器全绿互证）：

```
COGS              = round(Revenue × (1 - 毛利率))
GrossProfit       = Revenue - COGS                                  (R05)
Purchases         = COGS + (目标期末存货 - 期初存货)
Inventory_End     = Inventory_Begin + Purchases - COGS              (R01)
TotalAssets       = Cash_End + Inventory_End + AccountsReceivable + OtherAssets
TotalLiabilities  = TotalAssets - TotalEquity                       (R02)
下期 Inventory_Begin = 本期 Inventory_End                            (R03)
下期 Cash_Begin      = 本期 Cash_End                                 (R04)
```

随机性全部来自 `numpy.default_rng(seed)` + 固定遍历顺序 ⇒ 同 seed 逐位可复现。
增长率平滑演化（60% 惯性 + 40% 新抽样，[-2%, +8%]）。行业参数取验收区间的
"安全内圈"（base 区间 + 抖动幅度 + 取整余量），保证逐行严格落在：

| 行业 | 存货/总资产 | 毛利率 | 应收/营收 |
|---|---|---|---|
| consulting | < 2% | 35–55% | 15–35% |
| retail | 15–30% | 18–30% | 2–10% |
| manufacturing | 8–20% | 22–38% | 10–25% |

派生字段（把多元恒等式折叠成二元规则，供 NetNomos 语法搜索）：
`InventoryNetInflow = Purchases - COGS`；`InventoryToAssetsBp`、`ReceivableToRevenueBp`
为万分比四舍五入取整（三模块共用 `generator.bp`，口径唯一）。

### 1.2 华信咨询审阅资料包

`faults.build_clean_package()`：单公司（HX001 / consulting）8 期，主科目硬编码、
配平科目代码推导，FinanceValidator 校验零违规。规格指定的 F1 库存三元组
（期初 10,000 / 采购 4,000 / 期末 12,000，第 3 期）**内置于清洁基线**，
这样注入时只篡改 COGS，不破坏 R03 跨期滚动——是"单点违规、零级联误报"的关键。

## 2. 错误注入清单（truth_table 即自动验收依据）

`inject_faults(df_clean=None) -> (df_faulty, truth_table)`；
`forge.core.injector.inject("finance_v1")` 为通用入口薄封装。

| Fault | 期 | 行号(0基) | 篡改内容 | 命中规则 | 设计说明 |
|---|---|---|---|---|---|
| F1 | 3 | 2 | COGS 2,000→3,000；GrossProfit/InventoryNetInflow 连带算错 | R01 | 错误自洽传播 ⇒ R05 不误报，只有进销存勾稽能抓住 |
| F2a | 2 | 1 | Cash_Begin 8,000→8,500 | R04 | 上期 Cash_End=8,000，跨期现金断裂 500 |
| F2b | 5 | 4 | Cash_End 与 TotalAssets 同步虚增 500；第 6 期 Cash_Begin 同步抹平 | R02 | 现金虚增叙事；TA 比 TL+TE 多 500；抹平下期防 R04 级联 |
| F4 | 7 | 6 | AR 24,150→84,000（=第 3 期 4 倍，同比 +300%；营收同比 +15%）；虚增额从 OtherAssets 划出 | R07 | 资产合计仍配平，只有增速背离规则能识别 |
| F3 | 8 | 7 | Inventory_End → 35%×TotalAssets（299,600）；Purchases 同步做平；OtherAssets 划出 | R06 | 账面自洽的存货造假，勾稽全过，靠行业画像识别；选最后一期避免 R03 级联 |

truth_table 结构：`faults.{F*}.{rule_id, row_index, period_index, cells[], message_zh}`，
`cells` 列出全部被篡改单元格（行号/字段/错误值/正确值），与 `df_faulty - df_clean`
的差异**恰好一致**（tests 强校验）。落盘：`save_package(out_dir)` 输出
`huaxin_clean.csv` + `huaxin_audit_package.csv` + `truth_table.json`。

## 3. 校验器（FinanceValidator）

纯 pandas，无 z3；`validate(df 或 csv_path) -> contracts.ViolationReport`。

- R01–R05：恒等式与跨期滚动（R03/R04 仅在同公司、PeriodIndex 恰 +1 时检查）；
- R06：`Inventory_End/TotalAssets`（用原始字段重算 bp，不信任派生列）落行业区间；
- R07：同比（季度口径 t vs t-4）应收增速 ≥ +100% 且超出营收增速 ≥ 100pct 触发；
- R01 expected 给可读修正（审计惯例以 COGS 为修正对象）：
  `应为 2,000（=10,000+4,000-12,000）`；
- `satisfaction_rate = 1 - 违规行数(去重)/总行数`。

**有意不纳入校验器的检查**（避免与 F1 设计冲突，记录为设计决策）：
毛利率行业区间、应收/营收水平区间、资产构成恒等式（TA=Cash+Inv+AR+Other）。
它们由生成器测试在训练集上保证；华信资料包的 F1 行 COGS 极小（毛利率异常高），
若校验器检查毛利率区间会引入第 6 处违规，破坏"5 项违规、与真值表一一对应"的验收口径。

## 4. 验收方法

沙箱内（无 pip 外网，stdlib unittest）：

```bash
cd netnomos-forge
python3 -m unittest discover tests -v        # 当前 51 个用例全绿（含其他 Agent 用例）
```

财务场景验收点（22 个用例）：

1. 生成器：960 行、列序=FIN_FIELDS、全整数；FinanceValidator satisfaction_rate==1.0；
   跨期滚动全对；三行业 存货占比/毛利率/应收比 逐行落区间；同 seed 两次逐位相同；
2. 注入器：truth_table 含全部 5 个 fault；F1 数值与规格逐一吻合（10,000/4,000/12,000/3,000/2,000）；
   df_faulty 与 df_clean 的差异单元格与 truth_table 标注**集合相等**；
3. 校验器：df_clean（华信基线与 960 行训练集）零违规；df_faulty 恰好 5 项违规且
   (行号, 规则) 与真值表一一对应（零漏报零误报）；R01 expected 含 "2,000"。

## 5. 宿主机 netn 学习财务数据的步骤

> 沙箱无 z3/netnomos，以下在宿主机执行；FinanceValidator 与 NetNomos validate 互为印证。

```bash
# 0) 准备数据（沙箱/宿主机均可）
python -c "
from forge.scenarios.finance_v1.generator import generate_training_data, save_csv
save_csv(generate_training_data(42), 'data/finance_v1_train.csv')                      # 英文表头
save_csv(generate_training_data(42), 'data/finance_v1_train_zh.csv', use_source_names=True)  # 中文表头
from forge.scenarios.finance_v1.faults import save_package
save_package('data/huaxin')                                                            # 审阅资料包+真值表
"

# 1) 学习规则（dataset/grammar spec 见 forge/scenarios/finance_v1/）
netn learn --dataset forge/scenarios/finance_v1/dataset_spec.json \
           --grammar forge/scenarios/finance_v1/grammar_spec.json \
           --learner hitting-set --out runs/finance_v1
#    注意：dataset_spec.source.path 指向 finance_v1_train_zh.csv（中文表头）或
#    删除 source_name 字段后用英文表头版；见 finance_v1/README.md "待实测微调"。

# 2) 人工规则兜底：R01–R05 学不全时合并 manual_rules.json（golden rules.json 同构格式）
#    对应 contracts.RuleEngineAPI.add_manual_rules。

# 3) 验证华信资料包，与 truth_table.json / FinanceValidator 输出对照
netn validate --rules runs/finance_v1/rules.json --data data/huaxin/huaxin_audit_package.csv
python -c "
from forge.scenarios.finance_v1.validator import FinanceValidator
r = FinanceValidator().validate('data/huaxin/huaxin_audit_package.csv')
print(r.by_rule)   # 期望 {'R01':1,'R02':1,'R04':1,'R06':1,'R07':1}
"
```

预期：R01/R02/R05 与行业阈值类规则可由 grammar 的 addition/threshold 模板学出；
R03/R04 跨期规则依赖 context window（CompanyId 分区、PeriodIndex 排序），
若 netn 窗口配置未就绪则由 manual_rules.json 兜底。

## 6. 遗留风险

1. dataset/grammar spec 的 source_name 中文映射、`_ctx` 窗口语义、`profit-capacity`
   模板形态均未经宿主机 netn 实测（沙箱无 netnomos），已在 finance_v1/README.md 列出微调清单；
2. R07 同比口径假定 PeriodIndex 为季度（t vs t-4）；若改为年度口径需同步调整
   faults.F4 的基期与 validator 阈值；
3. 华信基线为叙事服务（COGS 极小、其他资产占比高），不参与训练集统计，
   若宿主机用它做 learn 输入会拉偏分位数常量——只应作为 validate 对象。
