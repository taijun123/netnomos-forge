# 华信咨询年度财务分析与审阅报告

> 报告对象：{{company_name}}（行业：{{industry_zh}}）　报告期间：第 {{period_first}}–{{period_last}} 期（共 {{period_count}} 期）
> 金额单位：千元　数据来源：{{data_source}}　规则集：{{ruleset_name}}（{{rule_count}} 条，启用 {{rule_enabled_count}} 条）

---

## 一、公司与行业概况

{{company_name}} 属 {{industry_zh}} 行业。报告期内最新一期营业收入 {{revenue_latest}}，
期间累计营业收入 {{revenue_total}}，营收复合期增速 {{revenue_cagr_pct}}。
行业画像基准：存货占总资产常态区间 {{industry_inv_band}}，应收/营收常态区间 {{industry_ar_band}}，
毛利率常态区间 {{industry_margin_band}}。本公司最新一期存货占比 {{inv_to_assets_pct_latest}}、
应收/营收 {{ar_to_revenue_pct_latest}}、毛利率 {{gross_margin_pct_latest}}。

## 二、财务规则画像

本次审阅依据 {{rule_count}} 条结构化财务规则（学习 {{learned_rule_count}} 条 + 人工兜底 {{manual_rule_count}} 条），核心恒等式：

| 规则 | 含义 | 校验结果 |
|---|---|---|
| R01 | 期末存货 = 期初存货 + 本期采购 - 营业成本 | {{r01_status}} |
| R02 | 资产总计 = 负债总计 + 所有者权益 | {{r02_status}} |
| R03 | 下期期初存货 = 本期期末存货 | {{r03_status}} |
| R04 | 下期期初现金 = 本期期末现金 | {{r04_status}} |
| R05 | 毛利润 = 营业收入 - 营业成本 | {{r05_status}} |
| R06 | 存货占总资产落在行业常态区间 | {{r06_status}} |
| R07 | 应收增速与营收增速不背离 | {{r07_status}} |

## 三、勾稽核查结论

全量 {{total_rows}} 行报表数据校验：违规 {{violation_count}} 处，规则满足率 {{satisfaction_rate_pct}}。

1. **进销存勾稽（R01）**：第 {{f1_period}} 期账面营业成本 {{cogs_reported}}，按
   期初存货 {{f1_inventory_begin}} + 本期采购 {{f1_purchases}} - 期末存货 {{f1_inventory_end}}
   勾稽，应为 {{cogs_corrected}}，差异 {{f1_diff}}；毛利润相应应修正为 {{gross_profit_corrected}}。
2. **现金跨期衔接（R04）**：第 {{f2a_period}} 期期初现金 {{f2a_cash_begin_reported}} 与上期期末现金
   {{f2a_cash_end_prev}} 断裂，差额 {{f2a_diff}}。
3. **资产负债配平（R02）**：第 {{f2b_period}} 期资产总计 {{f2b_total_assets}} 比 负债+权益
   {{f2b_liab_plus_equity}} 多 {{f2b_diff}}，与期末现金同步虚增的记账痕迹一致。
4. **行业画像偏离（R06）**：第 {{f3_period}} 期期末存货 {{f3_inventory_end}} 占资产总计
   {{f3_inv_ratio_pct}}，显著偏离 {{industry_zh}} 行业 {{industry_inv_band}} 的常态区间。
5. **应收/营收背离（R07）**：第 {{f4_period}} 期应收账款 {{f4_ar_reported}} 同比 {{f4_ar_growth_pct}}，
   而营业收入同比仅 {{f4_revenue_growth_pct}}，存在虚增应收/收入质量风险。

## 四、经营分析

以勾稽修正后口径分析：报告期毛利率均值 {{gross_margin_pct_avg}}，净利率均值 {{net_margin_pct_avg}}；
期末现金 {{cash_end_latest}}，资产负债率 {{debt_ratio_pct_latest}}；存货周转与采购节奏
{{inventory_turnover_comment}}。剔除第 {{f4_period}} 期异常应收后，应收/营收稳定在
{{ar_to_revenue_pct_normal}} 水平，经营性增长 {{growth_comment}}。

## 五、风险提示

- {{risk_item_1}}
- {{risk_item_2}}
- {{risk_item_3}}

## 六、校验附录

- 数据文件：{{data_path}}（{{total_rows}} 行 × {{total_fields}} 字段）
- 校验引擎：{{validator_engine}}（NetNomos validate / FinanceValidator 互为印证）
- 违规明细：{{violations_table}}
- 真值表比对：{{truth_table_match_summary}}
- 报告生成时间：{{generated_at}}　追踪号：{{trace_id}}
