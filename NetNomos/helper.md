# NetNomos Helper

`helper.md` 的职责是记录 **NetNomos 项目相关的类、枚举、配置结构、命令行参数和工具使用方法**，帮助中文开发者在阅读源码时快速理解：

- 这个对象是干什么的
- 这个类或工具该怎么用
- 它在项目里通常出现在哪里
- 它和运行流程中的哪一环有关

本文档不是通用 Python 教程，而是“结合项目上下文的开发辅助说明”。  
后续如果项目里新增了值得单独解释的类、工具或配置项，应继续同步补充到这里。

---

## 1. `Enum` 是什么？

`Enum` 是 Python 标准库里的“枚举类型”。
它的核心作用是：

- 把一组“合法取值”集中定义出来
- 用有名字的成员代替散乱的魔法字符串或魔法数字
- 让代码更可读、更安全、更容易校验

最常见的理解方式是：

`Enum = 一组有限、明确、带名字的常量`

例如，不要到处手写：

```python
"csv"
"pcap"
"auto"
```

而是统一定义成：

```python
from enum import Enum


class SourceType(str, Enum):
    AUTO = "auto"
    CSV = "csv"
    PCAP = "pcap"
```

这样代码里就能写成：

```python
if source_type == SourceType.CSV:
    ...
```

而不是：

```python
if source_type == "csv":
    ...
```

## 2. 为什么要用 `Enum`

### 2.1 提高可读性

看到：

```python
if learner == LearnerKind.HITTING_SET:
    ...
```

你一眼就知道这是在比较“学习器类型”。

如果写成：

```python
if learner == "hitting-set":
    ...
```

虽然也能看懂，但语义弱一些，而且字符串更容易拼错。

### 2.2 限制取值范围

`Enum` 的成员是固定的，不允许随便传入新值。

例如：

```python
LearnerKind("tree")
```

是合法的；

```python
LearnerKind("random-forest")
```

就会报错。

这对配置校验很有用，因为系统能很早发现非法值。

### 2.3 避免魔法字符串扩散

如果项目里到处散落：

```python
"exists"
"forall"
"sum"
"avg"
```

后面改名字、排查 typo、统一搜索都会比较麻烦。
用 `Enum` 后，所有合法值集中在一个地方管理。

### 2.4 更适合和 Pydantic / JSON 配置结合

这个项目大量使用 JSON 配置和 Pydantic 模型。
`Enum` 很适合这种场景，因为：

- JSON 里写字符串，容易编辑
- 代码里拿到的是强类型枚举成员，便于判断和校验

例如配置文件里写：

```json
{
  "type": "csv"
}
```

Pydantic 读进来后会变成：

```python
SourceType.CSV
```

## 3. 常见写法

### 3.1 基础写法

```python
from enum import Enum


class Color(Enum):
    RED = 1
    BLUE = 2
```

这里：

- `Color.RED` 是枚举成员
- `1` 是它对应的值

### 3.2 字符串枚举

项目里更常见的是：

```python
class SourceType(str, Enum):
    AUTO = "auto"
    CSV = "csv"
    PCAP = "pcap"
```

这里让枚举同时继承 `str` 和 `Enum`，有两个好处：

- 更适合 JSON 序列化
- 和字符串配置交互更自然

这也是 `netnomos/specs.py` 里最常见的风格。

## 4. 常用用法

### 4.1 比较

```python
if source_type == SourceType.CSV:
    ...
```

这是最推荐的写法。

### 4.2 从字符串构造

```python
source_type = SourceType("csv")
```

结果是：

```python
SourceType.CSV
```

如果值不合法，会直接抛异常。

这个项目里经常这么用，比如：

```python
learner_kind = LearnerKind(learner)
```

意思是把字符串 `"hitting-set"` 或 `"tree"` 转成强类型枚举。

### 4.3 取原始值

```python
SourceType.CSV.value
```

结果是：

```python
"csv"
```

这个写法常见于：

- 写回 JSON
- 记录日志
- 输出到 `manifest.json`

例如：

```python
learner_kind.value
```

会得到：

```python
"hitting-set"
```

### 4.4 遍历所有成员

```python
for item in LearnerKind:
    print(item, item.value)
```

在 CLI 里经常用这个生成可选项，例如：

```python
choices=[item.value for item in LearnerKind]
```

这就会自动得到：

```python
["hitting-set", "tree"]
```

## 5. 这个项目里 `Enum` 的典型作用

在 [`netnomos/specs.py`](./netnomos/specs.py) 里，`Enum` 主要用于定义“配置中的合法取值集合”。

### 5.1 `SourceType`

```python
class SourceType(str, Enum):
    AUTO = "auto"
    CSV = "csv"
    PCAP = "pcap"
```

作用：

- 限定输入源类型只能是这三种之一
- 避免配置里出现乱写的 `"pcapp"`、`"CSVV"` 之类错误

### 5.2 `ValueType`

这类枚举通常用于描述字段或派生变量的“值语义”。
常见用途包括：

- 告诉系统某个值是离散类别、连续数值还是其他特定类型
- 帮助后续规则学习、谓词构造和统计摘要阶段采用正确处理方式
- 让配置文件在进入程序后立刻完成合法性校验

### 5.3 `LearnerKind`

这类枚举用于控制“学习器走哪一套实现路径”。
例如：

```python
LearnerKind.HITTING_SET
LearnerKind.TREE
```

它的意义是：

- 统一限制 `learn` 阶段允许选择的算法类型
- 避免 CLI、API、配置层各自散落不同字符串
- 让 [`netnomos/api.py`](./netnomos/api.py) 和 [`netnomos/cli.py`](./netnomos/cli.py) 中的分支判断更清晰

## 6. 后续维护约定

后续维护 `helper.md` 时，优先补充以下内容：

- 项目里的核心枚举、数据类、配置类分别表示什么
- 某个类或工具通常从哪里进入、被谁调用、输出什么
- 某个 CLI 参数、JSON 字段、配置项在实际运行流程中的作用
- 容易混淆的概念差异，例如“字符串值”和“枚举成员”、“显示文本”和“结构化对象”

如果某段解释只适用于 NetNomos 的具体实现，应该直接写出对应文件路径，例如：

- `netnomos/specs.py`
- `netnomos/api.py`
- `netnomos/cli.py`

这样文档才能持续作为“项目辅助说明”，而不是脱离仓库上下文的泛化笔记。

---

## 7. `pydantic` 包的作用

### 7.1 在这个项目里它是干什么的

在 NetNomos 里，`pydantic` 主要负责把“外部 JSON 配置”转换成“程序内部可校验、可补全、可推断的强类型对象”。

它解决的不是算法计算本身，而是算法运行前的“输入结构治理”问题：

- 配置文件允许有哪些字段
- 哪些字段必填，哪些可选
- 每个字段应该是什么类型
- 非法配置是在加载时立刻报错，还是拖到运行中才出错

对应到项目里，最典型的文件就是 [`netnomos/specs.py`](./netnomos/specs.py)。

### 7.2 为什么这个项目需要 `pydantic`

这个项目是明显的“配置驱动”结构。
很多关键输入不是直接写死在函数参数里，而是来自：

- 数据集描述 JSON
- 语法空间描述 JSON
- 字段定义、预处理、派生变量等配置结构

如果不用 `pydantic`，这些 JSON 读进来后通常只是普通 `dict`，会有几个问题：

- 字段名写错时不容易第一时间发现
- 代码里到处都要自己写 `if "xxx" in data`
- 类型错误可能要到运行很深处才暴露
- 很难形成统一、清晰、可维护的数据结构

用了 `pydantic` 之后，JSON 一加载就会被校验并转换成模型对象，问题会更早暴露。

### 7.3 在 `specs.py` 里的典型角色

这里最核心的基类是：

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
```

它说明了这个项目对配置模型的态度是“严格校验”，不是“宽松接收”。

其中：

- `BaseModel`：Pydantic 的基础模型类，所有配置对象通常都从它派生
- `ConfigDict(extra="forbid")`：禁止未声明字段混入配置
- `populate_by_name=True`：允许按字段名进行赋值和序列化

这意味着：

- JSON 里多写了一个未知字段，不会被静默吞掉
- 配置拼写错误通常能在加载阶段直接暴露

### 7.4 它在运行流程中的位置

可以把 `pydantic` 理解成“进入算法主流程前的第一道结构化关卡”。

大致顺序是：

1. 从磁盘读取 JSON 配置
2. 交给 `pydantic` 模型解析
3. 得到 `DatasetSpec`、`GrammarSpec` 等强类型对象
4. 后续 `api.py`、`dataset.py`、`grammar.py` 等模块基于这些对象继续工作

也就是说，`pydantic` 本身不负责学习规则，但它负责保证“送进学习器的配置至少是结构正确的”。

### 7.5 常见收益

在这个项目里，`pydantic` 的实际收益主要有：

- 让配置对象从 `dict` 升级成带字段约束的模型对象
- 让 `Enum`、`Literal`、嵌套模型等约束真正生效
- 让默认值、可选字段、别名字段等行为更明确
- 让错误尽量在配置加载阶段暴露，而不是在算法中途报错

### 7.6 一个直观例子

例如某段配置里要求：

- `type` 必须是 `SourceType`
- `path` 可以为空
- `csv_read_options` 默认是字典

那么写成 Pydantic 模型后：

```python
class SourceSpec(StrictModel):
    type: SourceType
    path: str | None = None
    csv_read_options: dict[str, Any] = Field(default_factory=dict)
```

它表达的意思是：

- `type` 不能乱写
- `path` 可以缺省
- `csv_read_options` 就算用户不写，也会有稳定默认值

这比直接维护一个松散的 `dict` 更适合长期演化。

### 7.7 你阅读源码时该怎么理解它

阅读 `specs.py` 时，看到 `pydantic` 模型，不要只把它当成“数据容器”，而要把它理解成：

- 配置格式声明
- 输入合法性校验器
- 运行前的数据结构整理器
- 项目各模块共享的统一接口对象

所以在这个项目里，`pydantic` 的核心作用可以浓缩成一句话：

`把外部 JSON 配置，转成内部严格、可靠、可推断的配置对象。`

### 7.8 `populate_by_name=True` 是什么意思

它的准确含义是：

- 如果某个 Pydantic 字段定义了 `alias`
- 那么在创建模型对象时，除了可以用 `alias` 传值
- 也仍然允许按“真实字段名”传值

例如：

```python
from pydantic import BaseModel, ConfigDict, Field


class Demo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    full_name: str = Field(alias="fullName")
```

这时下面两种写法都可以：

```python
Demo(full_name="Alice")
Demo(fullName="Alice")
```

如果不开 `populate_by_name=True`，通常就更依赖 alias 输入。

在 NetNomos 当前这份 `specs.py` 里，这个配置更多体现的是一种“模型兼容策略”：

- 未来如果某些字段引入 alias，内部 Python 代码仍然可以继续按字段真实名传值
- 外部配置和内部代码不必被同一种命名形式完全绑死

要注意的是，它主要影响“输入/构造阶段”。
导出时是否按 alias 输出，通常要看：

```python
model_dump(by_alias=True)
```

所以不要把它简单理解成“自动按字段名序列化”。

### 7.9 `BaseModel`、`ConfigDict`、`Field`、`model_validator` 分别是做什么的

这四个名字可以看成 Pydantic 在项目里最常见的一组基础部件：

- `BaseModel`：定义“结构化配置对象”的基类
- `ConfigDict`：定义“这个模型怎么校验、怎么处理输入”的规则
- `Field`：定义“某个字段自身的默认值、别名、约束、说明”
- `model_validator`：定义“跨字段联动检查”逻辑

它们不是四个互相独立的小工具，而是一起构成“配置模型系统”。

#### `BaseModel` 的作用

`BaseModel` 是 Pydantic 所有模型类的基础父类。

在 NetNomos 里，你可以把它理解成：

- 让普通 Python 类变成“可解析 JSON 的配置模型”
- 让字段类型注解真正参与校验
- 让模型具备统一的导入、导出、报错能力

例如：

```python
class SourceSpec(StrictModel):
    type: SourceType
    path: str | None = None
```

这里 `SourceSpec` 本质上就是一个建立在 `BaseModel` 体系上的“配置对象类”。

如果没有 `BaseModel`，这些类型注解更多只是提示；  
有了 `BaseModel`，它们才会在运行时参与解析和校验。

#### `ConfigDict` 的作用

`ConfigDict` 用来配置“这个模型整体按什么规则工作”。

它不是某个字段的规则，而是模型级别的规则。

在这个项目里最典型的是：

```python
model_config = ConfigDict(extra="forbid", populate_by_name=True)
```

这表示：

- `extra="forbid"`：不允许未声明字段混入
- `populate_by_name=True`：如果字段有 alias，仍允许按真实字段名传值

所以 `ConfigDict` 解决的是：

- 模型整体宽松还是严格
- 输入里多余字段怎么处理
- alias 和字段名怎么兼容

你可以把它理解成“这个模型类的总开关配置”。

#### `Field` 的作用

`Field` 是“字段级配置器”。

当你只写：

```python
name: str
```

这只是声明“这个字段类型是字符串”。

如果你还想表达更具体的行为，就会用 `Field(...)`，例如：

```python
csv_read_options: dict[str, Any] = Field(default_factory=dict)
```

这里 `Field` 的作用是：

- 给字段提供默认值或默认工厂
- 可以声明 alias
- 可以附加描述、约束和元信息

在 NetNomos 里你最常见到的用途是：

- `default_factory=dict`
- `default_factory=list`

原因是可变对象不能安全地直接写成默认值：

```python
bad: dict[str, Any] = {}
```

这种写法容易带来共享默认对象的问题。  
`Field(default_factory=dict)` 的意思是“每次创建模型对象时，重新生成一个新的空字典”。

#### `model_validator` 的作用

`model_validator` 用来写“跨字段联合校验”。

有些规则不是单个字段自己能判断的，而是必须把多个字段放在一起检查。例如：

- A 字段有值时，B 字段必须也有值
- 当 `type="csv"` 时，某些字段必须满足某种约束
- 某两个配置项不能同时出现

这类逻辑就适合放在 `model_validator` 里。

你可以把它理解成：

- `Field` 负责单字段层面的约束
- `model_validator` 负责整模型层面的联动约束

在 `specs.py` 里，这类校验常用于：

- 纠正或兼容旧格式
- 检查配置结构是否自洽
- 在模型创建前后做统一规范化

#### 这四者在项目里的配合关系

可以用一句话串起来：

1. `BaseModel` 提供模型能力
2. `ConfigDict` 规定模型整体行为
3. `Field` 精细控制每个字段
4. `model_validator` 处理跨字段逻辑

所以你读 `specs.py` 时，看到它们可以这样理解：

- `BaseModel`：这是个“可校验配置对象”
- `ConfigDict`：这个对象整体按什么规则收输入
- `Field`：某个字段有没有默认值、alias、特殊元信息
- `model_validator`：多个字段之间有没有联动约束

这就是 Pydantic 在 NetNomos 里的最小工作闭环。

## 8. `FieldSpec.constants`：字段级可复用常量列表

### 8.1 它是什么

`FieldSpec.constants` 是写在某个字段元数据里的“人工声明常量池”。

它的类型是：

```python
constants: list[FieldConstantSpec] = Field(default_factory=list)
```

其中每个 `FieldConstantSpec` 大致包含：

```python
class FieldConstantSpec(StrictModel):
    kind: ConstantKind
    values: list[Any] = Field(default_factory=list)
    description: str = ""
```

可以把它理解成：

- 这些常量不是从当前数据统计出来的
- 也不是字段所有可能取值的完整枚举
- 而是“这个字段经常需要拿来比较的一组有业务含义的固定值”

### 8.2 举例

假设字段是 `ip.proto`，它是 IP 协议号。

数据里可能出现很多协议号，但我们知道下面几个值最常用：

```json
{
  "name": "ip.proto",
  "value_type": "integer",
  "constants": [
    {
      "kind": "assignment",
      "values": [6, 17, 1],
      "description": "Common IP protocol numbers: TCP=6, UDP=17, ICMP=1"
    }
  ],
  "enum_labels": {
    "6": "TCP",
    "17": "UDP",
    "1": "ICMP"
  }
}
```

这表示：后续如果 grammar 明确要求复用字段常量，就可以生成类似：

```text
ip.proto = 6
ip.proto = 17
ip.proto = 1
```

解释阶段再结合 `enum_labels`，可以显示成更可读的：

```text
ip.proto = TCP
ip.proto = UDP
ip.proto = ICMP
```

### 8.3 它什么时候会被使用

`FieldSpec.constants` 不会自动在所有场景里都参与规则生成。

它只有在 grammar 的常量选择器使用下面模式时才会被读取：

```json
{
  "mode": "field_constants"
}
```

对应代码在 `projection.py` 的 `select_constants()`：

```python
if selector.mode == "field_constants":
    values = []
    allowed_kinds = set(selector.kinds)
    for constant_spec in field.constants:
        if allowed_kinds and constant_spec.kind not in allowed_kinds:
            continue
        for value in constant_spec.values:
            values.append(SelectedConstant(value=value, label=None))
    return dedupe_selected_constants(values)
```

也就是说：

1. 先看当前字段 `field.constants`
2. 如果 grammar 写了 `kinds`，就只取指定类型的常量
3. 把命中的 `values` 展开成候选常量
4. 去重后返回给谓词生成逻辑

### 8.4 它和 `domain`、`profile`、`explicit` 的区别

这几个常量来源容易混淆：

- `explicit`：常量直接写在 grammar 里，适合模板级固定常量。
- `domain`：字段的离散取值范围，通常表示“这个字段可能有哪些值”。
- `profile`：从当前数据统计出来的常量，例如 p50、p90、top1。
- `field_constants`：字段自己携带的可复用业务常量，例如协议号、标志位、特殊阈值。

举例：

```text
domain      = 这个字段可能出现哪些值
profile     = 当前数据里哪些值有代表性
explicit    = 这个 grammar 模板指定用哪些值
constants   = 这个字段长期有意义、可复用的业务常量
```

### 8.5 为什么叫“可复用”

因为这些常量跟字段绑定，而不是跟某一个 grammar 模板绑定。

同一个字段的 `constants` 可以被多个 grammar 模板复用：

- 一个模板可以生成 `ip.proto = 6`
- 另一个模板可以生成 `ip.proto != 17`
- 还有一个模板可以在算术项或字段-常量比较中复用这些值

这样就不用在每个 grammar 模板里重复写 `[6, 17, 1]`。

### 8.6 需要注意的点

`constants` 不是数据校验规则。

如果你写了：

```json
"constants": [{"kind": "assignment", "values": [6, 17]}]
```

并不表示 `ip.proto` 只能等于 6 或 17。

它只是告诉 projection：

```text
当 grammar 要求 field_constants 时，可以把 6 和 17 拿出来当候选比较常量。
```

真正限制字段允许取值的是 `domain`，而真正从数据分布自动选值的是 `profile`。

## 9. `SelectedConstant`：候选常量的运行时包装对象

### 9.1 它是什么

`SelectedConstant` 定义在 `netnomos/projection.py` 中：

```python
@dataclass(slots=True)
class SelectedConstant:
    value: Any
    label: str | None
```

它不是配置模型，也不是字段定义。

它是 projection 阶段运行时临时创建的“候选常量包装对象”。

可以把它理解成：

```text
一个真正要参与公式比较的常量值 + 这个常量的可选语义标签
```

例如：

```python
SelectedConstant(value=64, label="p50")
SelectedConstant(value="TCP", label="top1")
SelectedConstant(value=6, label=None)
```

### 9.2 为什么 class 里看不到赋值逻辑

因为 `SelectedConstant` 是 dataclass。

dataclass 的字段赋值发生在构造对象时：

```python
SelectedConstant(value=value, label=None)
```

也就是说，class 定义里只声明它有哪些字段：

```python
value: Any
label: str | None
```

真正决定 `value` 和 `label` 是什么的逻辑，不在 class 内部，而在构造它的函数里。

### 9.3 普通字段常量：`select_constants()`

普通字段的常量由 `projection.py` 中的 `select_constants()` 生成。

它会根据 `ConstantSelectorSpec.mode` 走不同分支。

#### `explicit`

配置里直接写死值：

```json
{
  "mode": "explicit",
  "values": [0, 1]
}
```

代码会生成：

```python
SelectedConstant(value=0, label=None)
SelectedConstant(value=1, label=None)
```

这里没有语义标签，因为这些值就是用户显式写的。

#### `field_constants`

从 `FieldSpec.constants` 读取字段级可复用常量：

```python
for constant_spec in field.constants:
    for value in constant_spec.values:
        values.append(SelectedConstant(value=value, label=None))
```

例如 `ip.proto.constants = [6, 17, 1]`，就会生成：

```python
SelectedConstant(value=6, label=None)
SelectedConstant(value=17, label=None)
SelectedConstant(value=1, label=None)
```

#### `domain`

从字段的 domain 或 `prepared.value_catalog` 读取值：

```python
SelectedConstant(value=value, label=None)
```

例如 `protocol.domain = ["TCP", "UDP"]`，就会生成：

```python
SelectedConstant(value="TCP", label=None)
SelectedConstant(value="UDP", label=None)
```

对应源码是：

```python
return [
    SelectedConstant(value=value, label=None)
    for value in list(field.domain or prepared.value_catalog.get(field_name, []))
]
```

这行代码可以拆成三层理解。

第一层：先决定值从哪里来。

```python
field.domain or prepared.value_catalog.get(field_name, [])
```

它的意思是：

- 如果 `field.domain` 有值，就用 `field.domain`
- 如果 `field.domain` 是 `None` 或空列表，就用 `prepared.value_catalog[field_name]`
- 如果 `value_catalog` 里也没有这个字段，就用空列表 `[]`

第二层：为什么 `field.domain` 优先。

`field.domain` 是人工配置的字段值域，通常代表“业务上我认可这个字段可以枚举这些值”。

例如：

```json
{
  "name": "protocol",
  "value_type": "categorical",
  "domain": ["TCP", "UDP", "ICMP"]
}
```

即使当前数据样本里只出现了 `TCP` 和 `UDP`，系统仍然优先使用人工 domain：

```python
["TCP", "UDP", "ICMP"]
```

因为人工配置通常比当前样本更完整、更稳定。

第三层：`value_catalog` 是兜底。

如果字段没有写 domain，dataset 阶段会从当前 DataFrame 中构建 `value_catalog`。

例如当前数据是：

```text
protocol
TCP
UDP
TCP
ICMP
```

`build_value_catalog()` 可能得到：

```python
prepared.value_catalog["protocol"] = ["ICMP", "TCP", "UDP"]
```

这时 `domain` 模式会退而使用这个 catalog：

```python
SelectedConstant(value="ICMP", label=None)
SelectedConstant(value="TCP", label=None)
SelectedConstant(value="UDP", label=None)
```

注意这里 `label=None`。

原因是：domain 常量不是从 profile 统计策略里来的，不是 p50/top1 这种“语义标签常量”。

所以：

- `value` 会进入实际公式比较
- `label` 保持 `None`

生成的谓词类似：

```text
protocol = TCP
protocol = UDP
protocol = ICMP
```

而不会显示成：

```text
protocol = top1
```

### 9.3.1 `field.domain or value_catalog` 的一个完整例子

假设 grammar 里配置：

```json
{
  "rhs_constant": {
    "mode": "domain"
  }
}
```

字段配置情况一：有人工 domain。

```python
field.domain = ["TCP", "UDP", "ICMP"]
prepared.value_catalog["protocol"] = ["TCP", "UDP"]
```

最终使用：

```python
["TCP", "UDP", "ICMP"]
```

因为 `field.domain` 优先。

字段配置情况二：没有人工 domain。

```python
field.domain = None
prepared.value_catalog["protocol"] = ["TCP", "UDP"]
```

最终使用：

```python
["TCP", "UDP"]
```

因为回退到了 `value_catalog`。

字段配置情况三：两边都没有。

```python
field.domain = None
prepared.value_catalog.get("protocol", []) == []
```

最终使用空列表：

```python
[]
```

这意味着这个字段不会从 domain 模式生成任何常量谓词。

#### `profile`：数值字段

数值字段会按分位数计算：

```python
raw_value = series.quantile(quantile)
value = int(round(raw_value)) if field.value_type == ValueType.INTEGER else raw_value
SelectedConstant(value=value, label=quantile_label(quantile))
```

例如 `quantile=0.5`，`raw_value=64`：

```python
SelectedConstant(value=64, label="p50")
```

这里 `label="p50"` 很重要。

后续解释阶段可以把：

```text
ip.ttl >= 64
```

显示成：

```text
ip.ttl >= p50
```

#### `profile`：非数值字段

非数值字段会按出现频率取 top-k：

```python
SelectedConstant(value=value, label=f"top{index}")
```

例如 `protocol` 中 `"TCP"` 出现最多：

```python
SelectedConstant(value="TCP", label="top1")
```

### 9.4 量词字段族常量：`select_quantifier_constants()`

量词模板不是对单个字段选常量，而是对一整个上下文字段族选常量。

例如 family `tcp.seq` 可能包含：

```text
tcp.seq_ctx0
tcp.seq_ctx1
tcp.seq_ctx2
```

`select_quantifier_constants()` 会先把这些列合并：

```python
series = pd.concat([prepared.dataframe[field] for field in field_names], axis=0).dropna()
```

然后再从整个 family 的值分布中生成：

- explicit 常量
- domain 去重值
- 数值 quantile 常量
- 非数值 top-k 常量

所以量词里的 `SelectedConstant(value=..., label="p50")`，代表的是整个上下文字段族的 p50，而不是某一列单独的 p50。

### 9.5 它后续怎么被使用

`SelectedConstant` 生成后，会进入 `generate_predicates()`。

字段-常量谓词中：

```python
formula = Compare(op.value, SymbolRef(lhs), Constant(constant.value))
```

也就是说：

- `constant.value` 进入真正的 AST 公式
- `constant.label` 不参与计算，只进入 source 元数据

语义标签写入 source 的位置是：

```python
"semantic_constants": build_semantic_entries("field", lhs, constant)
```

如果 `label` 是 `None`，就不会写入语义标签。

如果 `label` 是 `"p50"` 或 `"top1"`，后续 `interpreter.py` 可以用它把原始常量解释成更友好的标签。

### 9.6 一句话总结

`SelectedConstant` 的赋值不是在 class 里完成的，而是在常量选择函数中完成的：

```text
ConstantSelectorSpec + FieldSpec + PreparedDataset
        ↓
select_constants() / select_quantifier_constants()
        ↓
SelectedConstant(value=实际常量值, label=可选语义标签)
        ↓
generate_predicates() 生成 AST 谓词
```

其中：

- `value` 参与实际比较和规则计算
- `label` 只用于解释和展示

## 10. 新版 term 结构 vs 旧版 term 结构

### 10.1 先说结论

旧版 predicate template 把谓词固定理解成：

```text
左侧字段 lhs  比较符 op  右侧字段 rhs_field / 右侧常量 rhs_constant
```

新版 term 结构把比较符左右两侧统一抽象成“项 / term”：

```text
左侧项 lhs_term  比较符 op  右侧项 rhs_term
```

这个变化的核心价值是：比较式两边不再只能是裸字段或裸常量，也可以是带计算结构的表达式，例如 `tcp.seq + tcp.len <= tcp.ack`。

### 10.2 旧版结构是什么

旧版结构主要使用 `PredicateTemplateSpec` 里的这几个字段：

```python
lhs: VariableSelectorSpec | None = None
rhs_field: VariableSelectorSpec | None = None
rhs_constant: ConstantSelectorSpec | None = None
```

它能表达两类谓词：

- 字段 vs 字段，例如 `tcp.seq <= tcp.ack`
- 字段 vs 常量，例如 `ip.ttl >= 64`

旧版 JSON 配置通常长这样：

```json
{
  "name": "field_vs_constant",
  "lhs": {
    "names": ["ip.ttl"]
  },
  "operators": [">="],
  "rhs_constant": {
    "mode": "profile",
    "quantiles": [0.5]
  }
}
```

它的生成路径在 `netnomos/projection.py::generate_predicates()` 里是旧版分支：

```text
select_fields(prepared, template.lhs)
        ↓
rhs_field 分支：select_fields(...)
rhs_constant 分支：select_constants(...)
        ↓
Compare(op, SymbolRef(lhs), SymbolRef(rhs) 或 Constant(value))
```

所以旧版结构比较直接，但表达能力有限：左侧一定是字段，右侧只能是字段或常量。

### 10.3 新版 term 结构是什么

新版结构主要使用：

```python
lhs_term: TermTemplateSpec | None = None
rhs_term: TermTemplateSpec | None = None
```

`TermTemplateSpec` 再通过 `kind` 描述这个 term 长什么样：

```python
class PredicateTermKind(str, Enum):
    FIELD = "field"
    CONSTANT = "constant"
    SCALAR = "scalar"
    ADDITION = "addition"
```

含义分别是：

- `field`：单个字段，例如 `Bytes`
- `constant`：单个常量，例如 `100`
- `scalar`：字段乘常量，例如 `Packets * 65535`
- `addition`：字段加字段或字段加常量，例如 `tcp.seq + tcp.len`

新版 JSON 配置可以写成：

```json
{
  "name": "tcp_seq_end_before_ack",
  "lhs_term": {
    "kind": "addition",
    "field": {
      "names": ["tcp.seq"]
    },
    "other_field": {
      "names": ["tcp.len"]
    }
  },
  "operators": ["<="],
  "rhs_term": {
    "kind": "field",
    "field": {
      "names": ["tcp.ack"]
    }
  }
}
```

这类模板可以生成：

```text
tcp.seq + tcp.len <= tcp.ack
```

旧版 `lhs/rhs_field/rhs_constant` 很难直接表达这个公式，因为旧版没有“左侧是一个加法表达式”的结构。

### 10.4 两者在代码生成路径上的区别

新版 term 分支在 `generate_predicates()` 中由这个条件触发：

```python
if template.lhs_term is not None or template.rhs_term is not None:
```

触发后，流程变成：

```text
lhs_term / rhs_term
        ↓
generate_terms()
        ↓
GeneratedTerm(expr, display, field_names, value_type, comparison_group, ...)
        ↓
compatible_terms()
        ↓
Compare(op, lhs_term.expr, rhs_term.expr)
```

新版不是直接拿字段名生成 `SymbolRef`，而是先把 term 展开成 `GeneratedTerm`。
`GeneratedTerm` 会额外携带语义信息，例如：

- 这个 term 引用了哪些字段
- 这个 term 是否是有序数值
- 这个 term 属于哪个比较语义组，例如 size/count/time/sequence
- 这个 term 的 AST 表达式是什么

这些信息用于过滤不合理组合，例如避免把 `Bytes` 和 `frame.time_epoch` 直接做大小比较。

### 10.5 兼容旧版配置的桥接逻辑

新版结构没有直接废掉旧版写法。`projection.py` 里有兼容函数：

```python
def build_legacy_rhs_term(template: Any) -> TermTemplateSpec:
    if template.rhs_field is not None:
        return TermTemplateSpec(kind=PredicateTermKind.FIELD, field=template.rhs_field)
    if template.rhs_constant is not None:
        return TermTemplateSpec(kind=PredicateTermKind.CONSTANT, constant=template.rhs_constant)
```

它的作用是把旧版右侧结构转换成新版 `rhs_term`：

```text
rhs_field     -> kind="field" 的 rhs_term
rhs_constant  -> kind="constant" 的 rhs_term
```

左侧也有类似兼容：

```python
template.lhs_term or TermTemplateSpec(kind=PredicateTermKind.FIELD, field=template.lhs)
```

意思是：如果没有写 `lhs_term`，但写了旧版 `lhs`，就把旧版 `lhs` 包装成一个 `field` term。

所以项目现在支持混合写法：

- 纯旧版：`lhs + rhs_field`
- 纯旧版：`lhs + rhs_constant`
- 新版：`lhs_term + rhs_term`
- 兼容混合：`lhs + rhs_term`
- 兼容混合：`lhs_term + rhs_field/rhs_constant`

### 10.6 对比表

| 对比项 | 旧版结构 | 新版 term 结构 |
| --- | --- | --- |
| 左侧 | 只能用 `lhs` 选择字段 | 可用 `lhs_term` 表达字段、常量、乘法项、加法项 |
| 右侧 | `rhs_field` 或 `rhs_constant` 二选一 | 统一用 `rhs_term` 表达任意支持的 term |
| 典型公式 | `Bytes >= 100`、`tcp.seq <= tcp.ack` | `tcp.seq + tcp.len <= tcp.ack`、`Packets * 65535 >= Bytes` |
| 生成函数 | `select_fields()`、`select_constants()` | `generate_terms()` |
| 兼容性检查 | `compatible_fields()`、`compatible_constant()` | `compatible_terms()` |
| 表达能力 | 简单字段比较 | 支持更复杂的算术项比较 |
| 元数据 | 主要记录 lhs/rhs/constant | 记录 term 来源、字段引用、值类型、比较语义组等 |

### 10.7 阅读源码时怎么判断当前模板走哪条路

看 grammar 里的 predicate template：

- 如果出现 `lhs_term` 或 `rhs_term`，走新版 term 分支。
- 如果只出现 `lhs` 和 `rhs_field`，走旧版字段-字段分支。
- 如果只出现 `lhs` 和 `rhs_constant`，走旧版字段-常量分支。
- 如果出现 `lhs_term`，但右侧还是 `rhs_field` 或 `rhs_constant`，会通过 `build_legacy_rhs_term()` 自动转成新版右侧 term。

一句话总结：

```text
旧版结构 = 字段比较模板
新版 term 结构 = 可组合表达式比较模板
```
