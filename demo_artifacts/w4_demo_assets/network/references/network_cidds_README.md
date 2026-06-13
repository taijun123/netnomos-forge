# network_cidds 场景资源

CIDDS NetFlow 网络场景（NetNomos 自带 10k 正常流量训练集）。

## 文件

| 文件 | 说明 |
|---|---|
| `dataset_spec.json` | NetNomos DatasetSpec，改编自 `NetNomos/examples/datasets/cidds.json`（含 SrcSubnet/DstSubnet/PortClass 预处理映射） |
| `grammar_spec.json` | NetNomos GrammarSpec，沿用 `NetNomos/examples/grammars/network_flow.json` |

## 数据路径相对约定（重要）

`dataset_spec.json` 的 `source.path` 写的是**相对于本目录（dataset_spec.json 所在目录）**的路径：

```
../../../../NetNomos/data/cidds_wk2_normal_10k.csv
```

即假设仓库布局为同级目录：

```
<workspace>/
├── NetNomos/            # NetNomos 仓库（数据在 NetNomos/data/）
└── netnomos-forge/
    └── forge/scenarios/network_cidds/   ← 本目录，向上 4 级到 <workspace>
```

注意：NetNomos 的 `prepare_dataset` 把相对路径按**当前工作目录**解析，而不是按 spec
文件所在目录。因此不要直接把本 spec 喂给 `netn` CLI 后在任意目录运行；
`forge.core.engine.ForgeRuleEngine` 会先把该相对路径解析为绝对路径，再通过
`input_path=` 显式传入，任何工作目录下都能正确加载。若手动使用 `netn` CLI，请用
`--input` 显式传绝对路径（参见 `scripts/host/run_network_learn.ps1`）。

## 宿主机最小用法

```powershell
# 一键学习并归档黄金规则集
powershell -File scripts/host/run_network_learn.ps1
```

```python
from forge.core.engine import ForgeRuleEngine

eng = ForgeRuleEngine.from_scenario("network_cidds")
ruleset = eng.learn(None)          # None = 使用 dataset_spec.json 内的默认数据路径
report = eng.validate(None, ruleset)
```
