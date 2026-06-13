# -*- coding: utf-8 -*-
"""forge.scenarios.finance_v1 — 合成财务报表场景（960 行训练集 + 华信咨询错误资料包）.

模块组成：
- generator.py  确定性合成 3 行业 × 40 公司 × 8 期 = 960 行干净训练数据；
- faults.py     构造"华信咨询"8 期审阅资料包并注入 F1/F2a/F2b/F3/F4 五处错误；
- validator.py  纯 Python（pandas）实现 R01–R05 + 行业区间(R06) + 比率背离(R07) 校验。

第三方依赖（pandas/numpy）全部懒加载，import 本包不会触发。
"""
