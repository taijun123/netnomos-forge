# Financial Reporting and Audit Knowledge

> 用于规则卡 RAG 的财务报表勾稽、审计证据和内控知识库。资料来自 PCAOB AS 1105、COSO Internal Control - Integrated Framework、SEC MD&A 指引和 FASB 概念框架公开材料。

## 审计证据与可验证性

PCAOB AS 1105 要求审计证据足以支持审计结论，证据的可靠性取决于来源、性质和取得方式。对本项目的规则卡而言，勾稽规则命中的意义是把“语言模型的报告叙述”拉回到可验证数据：每个异常应能落到具体行、字段、实际值、期望值和规则来源。

Source: PCAOB AS 1105, Audit Evidence, https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105

## 财务报告内部控制

COSO Internal Control - Integrated Framework 把内部控制用于提升报告、运营和合规信息的可信度。财务 demo 中 R01-R07 的作用类似自动化控制点：先发现数据异常，再通过投影、槽位回填和终检限制报告正文，防止模型把未经校验的错误数字写进正式结论。

Source: COSO Internal Control - Integrated Framework, https://www.coso.org/guidance-on-ic

## 资产负债配平

资产总计应与负债加所有者权益保持配平，这体现了财务报表基本结构和复式记账逻辑。若 TotalAssets 不等于 TotalLiabilities + TotalEquity，即使单个科目看起来合理，整体报表也缺乏一致性。规则卡应把 R02 解释为硬性结构规则，违反时通常需要追溯现金、其他资产、负债或权益的同步调整。

Source: FASB Concepts Statements on financial statement elements, https://www.fasb.org

## 进销存勾稽与营业成本

期末存货 = 期初存货 + 本期采购 - 营业成本，是存货和成本数据之间的基本滚动关系。若营业成本被写高或写低，毛利润、毛利率、存货净流入等衍生指标可能随之错误；裸模型会照抄这些错误并继续生成看似合理的分析。规则卡解释 R01 时应强调这是可计算的硬规则，适合由 Projector 给出修正值。

Source: Financial statement articulation and inventory roll-forward practice, https://www.fasb.org

## 毛利恒等式

毛利润 = 营业收入 - 营业成本。该规则不依赖行业判断，属于报表内部算术一致性要求。规则卡解释 R05 时，应提示模型不能自行重算或猜测毛利，而必须引用经校验后的 Revenue 和 COGS 槽位；这也是 B 轨报告用程序回填衍生指标的原因。

Source: Financial statement presentation concepts, https://www.fasb.org

## 行业画像与软规则

存货占资产比例、应收增长与收入增长的背离，通常属于风险信号而不是直接数值修正依据。咨询类公司出现高存货占比，或应收远快于收入增长，应触发进一步审阅和证据获取；但这类规则需要结合行业、业务模式和管理层解释判断。规则卡应把 R06/R07 标为软规则，输出风险提示而不是直接改数。

Source: SEC MD&A disclosure themes and COSO reporting controls, https://www.sec.gov/corpfin/managements-discussion-and-analysis
