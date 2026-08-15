# 政策与规则模型

政策层必须同时保存原始权威文本、可执行解释和批准轨迹。计算引擎不读取任意网页或自然语言段落，而是读取已验证、具有明确可执行状态且与运行日期匹配的规则包。

## 规则包

`PolicyRuleSet` 是领域内的机器可执行规则集合；发布时封装为可签名、不可变的 `RuleSetPackage`：

```json
{
  "ruleset_id": "cn-pension/example/2026.1",
  "scheme": "enterprise_employee_basic_pension",
  "jurisdiction": "example-region",
  "topic": "contribution_and_subsidy",
  "version": "2026.1.0",
  "effective_from": "2026-01-01",
  "effective_to": null,
  "transaction_from": "2026-01-08T09:30:00+08:00",
  "transaction_to": null,
  "source_ids": ["policy-doc-example-001"],
  "approvals": ["legal-review/example/42"],
  "engine_compatibility": ">=1.4,<2.0",
  "content_digest": "sha256:<digest>"
}
```

包内对象：

| 对象 | 作用 |
|---|---|
| `PolicyDocument` | 权威来源元数据、发布机关、发布日期、URL、文件摘要和抓取证据 |
| `PolicyFragment` | 原文中的稳定定位片段，含页码、条款、表格单元和原文摘要 |
| `PolicyRule` | 具有明确输入、条件、输出、优先级和适用范围的原子规则 |
| `DecisionTable` | 对多条件资格、费率和例外进行穷举且可测试的决策表 |
| `ParameterTable` | 基数上下限、费率、定额、日期和舍入参数 |
| `RuleOverride` | 上位规则和地区例外之间带依据的显式覆盖关系 |
| `RuleTestVector` | 来源于条文示例、边界值或已批准案例的输入与预期结果 |

每个 `PolicyRule` 和 `DecisionTable` 行必须能追溯到至少一个 `PolicyFragment`；没有来源定位或审批状态的规则不得发布。

原子 `PolicyRule` 至少声明 `rule_id`、`rule_type`、`scheme`、管辖角色、适用人群、输入字段、条件、结果、例外、有效时间、事务时间、法律层级、显式覆盖关系和来源片段。地区补贴公式属于规则包内容，不属于核心计算器或地区适配器代码。

条件值保持为与 `value_type` 一致的类型化字面量。规则结果不得保存任意表达式字符串；其值只能是严格对象：类型化字面量、`INPUT`/`PARAMETER`引用，或由 `ADD`、`SUBTRACT`、`MULTIPLY`、`DIVIDE`、`MIN`、`MAX` 构成的递归表达式树。每个节点和操作数均声明类型，所有对象拒绝未定义字段，减法和除法固定为两个操作数。

### 类型化执行

可执行规则的每个输入声明 `value_type` 和布尔 `required`。支持的类型为 `STRING`、`INTEGER`、`DECIMAL`、`BOOLEAN`、`DATE`、`YEAR_MONTH` 和 `NULL`，领域对象分别对应字符串、非布尔整数、`Decimal`、布尔、日期（不含时间）、月份值和 `None`；类型不匹配即拒绝。

- 条件必须引用已声明的输入，`value_type` 必须与所引用输入一致，条件值必须是该类型的字面量；排序运算符（`<`、`<=`、`>`、`>=`）只允许用于可排序类型（整数、小数、日期、月份、字符串），等值运算符（`=`、`!=`）可用于全部类型；
- 结果表达式声明的类型必须与结果字段类型一致：`LITERAL` 的字面量必须匹配类型；`REFERENCE` 必须引用存在的输入或参数，且引用类型必须与被引用目标的声明类型一致；`EXPRESSION` 的操作数数量受限（`ADD`/`MULTIPLY`/`MIN`/`MAX` 至少两个，`SUBTRACT`/`DIVIDE` 恰好两个），每个操作数类型必须与表达式类型一致，且运算符与类型组合受限（`ADD`/`SUBTRACT`/`MULTIPLY` 仅数值类型，`DIVIDE` 仅 `DECIMAL`，`MIN`/`MAX` 仅可排序类型）；
- 参数是类型化声明 `{"参数名": {"value_type": ..., "value": ...}}`，不允许未声明类型的标量参数；
- 例外必须声明 `EXCLUDE` 或 `OVERRIDE` 效果；测试向量的输入和预期值必须与输入、结果声明的类型一致。

### 限定规则身份与覆盖作用域

规则和包标识符不得包含 `:`。规则身份是包限定的 `package_id:rule_id`：不同包中出现相同裸 `rule_id` 是允许的，解析器的竞争规则输出和歧义报告必须使用限定身份，不得用裸 ID 跨包误删规则。

`explicit_override_refs` 支持两种形式：

- 裸 `rule_id`：作用域限定在声明它的规则所在包，只覆盖本包内同名规则，不影响其他包的同名规则；
- 限定 `package_id:rule_id`：显式跨包覆盖，在解析时对候选集求值；限定引用不得指向本包不存在的规则，也不得指向自身。

### 双时态因果

规则包的 `transaction_from` 不得早于该包全部证据与审核事件：任何来源的抓取时间 `retrieved_at`、工程审核时间 `reviewed_at`，以及生产批准（`PRODUCTION_APPROVED`）的发布时间 `published_at`。不满足因果顺序的包在构造时被拒绝；等于最新证据时间戳是允许的边界。

### 决策表资源上限

决策表在枚举前先计算输入域笛卡尔积大小，超过固定上限 `MAX_DECISION_TABLE_COMBINATIONS = 100_000` 时直接拒绝，避免行枚举消耗失控。`policy-package.schema.json` 同步声明基数限制：单规则输入最多 12 个，`input_domains` 最多 12 个键且每个域最多 256 个值，`decision_rows` 最多 100_000 行。`input_domains` 的值采用 JSON 字面量形式（`DECIMAL` 用 schema 的十进制定长字符串），由包加载器按输入声明的 `value_type` 转换为对应领域类型（如 `Decimal`），转换后在领域构造时校验类型一致性。

## 可执行状态

规则包只有以下两个可执行审核状态；二者是不同生命周期，不能互相替代：

| 状态 | 必须满足的门禁 | 允许的执行环境 |
|---|---|---|
| `PRODUCTION_APPROVED` | 权威来源和稳定定位、schema与引用校验、规则测试、领域审核、两名独立批准人、签名及正式发布生命周期全部完成 | `PRODUCTION`；也可用于受控历史重放 |
| `MVP_REVIEWED` | 权威官方来源和稳定定位、来源与包内容摘要、schema与引用校验、每条规则的测试向量及回归测试、工程审核全部完成，并明确标记 `local_only=true` | 仅 `analysis_mode=LOCAL_MVP` |

`MVP_REVIEWED` 的强制约束如下：

- 规则包的 `execution_modes` 必须且只能是 `["LOCAL_MVP"]`，`production_approval` 必须为 `null`；
- 每个来源必须使用 `https`，主机必须为 `gov.cn` 或其子域，并将机关层级声明为国家政府、国家部委、北京市政府或北京市人力资源社会保障部门之一；私人博客、转载站和其他主机不能作为该状态的可执行来源；
- 应用层在任何非 `LOCAL_MVP` 模式拒绝解析或执行该包，不能自动降级或改写模式；
- 使用该包的运行不得转换到 `PUBLISHED`，只能保留到 `VALIDATED` 或 `RENDERED`；
- 输入、结果、清单和渲染产物只能标记为 `S1-INTERNAL` 或 `S2-CONFIDENTIAL`；
- 每个结构化输出和渲染输出必须显著显示 `NOT_PRODUCTION_APPROVED`，并记录包状态和摘要；
- 结果只能作为本地信息筛查，`official_eligibility_claim` 必须为 `false`，不得表述为机关资格认定。

`MVP_REVIEWED` 不是对生产领域审核、双人批准、签名或发布门禁的豁免。候选规则、仅完成单次抽取的规则、缺少来源定位的规则，以及未完成上述任一状态门禁的规则均为非可执行规则；缺失的政策条件不得猜测，受影响能力返回 `UNKNOWN`、`BLOCKED` 或未支持。

## 双时态

政策记录采用双时态，由值对象 `PolicyValidTime` 和 `SystemRecordedTime` 表示：

- `PolicyValidTime`，即有效时间 `effective_from` / `effective_to`：政策在现实世界适用的期间；
- `SystemRecordedTime`，即事务时间 `transaction_from` / `transaction_to`：该版本何时进入或退出系统的已知事实集；
- `recorded_at`：单次证据采集或审核事件的时间戳，不替代事务区间。

一次运行必须同时指定 `as_of_effective_date` 和 `as_known_at`。重现历史结果时，规则解析器选择在两个时间轴上均有效的版本。因此，晚到的追溯性政策不会静默改变旧报告；它产生一个使用新事务时间的新运行，并显示与原运行的差异。

## 解析优先级

规则解析按以下顺序缩小候选集：

1. 制度 `scheme`；
2. 主题和管辖角色；
3. 有效时间与事务时间；
4. 法律层级和显式 `RuleOverride`；
5. 引擎兼容范围与发布状态。

不使用隐式“更具体”规则打破平局。若仍有多个产生不兼容输出的候选，解析器返回 `AMBIGUOUS_POLICY_RULE`，记录冲突维度和竞争规则ID，并阻塞受影响能力；不得以“最新网页”或模型置信度自动选择。机关针对个人案件作出的 `OfficialDetermination` 是案件证据，不重写一般政策优先级。

## 发布流程

```text
采集 PolicyDocument
→ 固定摘要和来源位置
→ LLM生成候选PolicyFragment/PolicyRule
→ schema与引用校验
→ 运行RuleTestVector与回归测试
→ 工程审核并标记MVP_REVIEWED（仅LOCAL_MVP），或继续生产流程
→ 领域审核和两名独立批准人批准
→ 签名并正式发布为PRODUCTION_APPROVED RuleSetPackage
→ 旧版本保留用于历史回放
```

撤销规则包只关闭其事务有效期，不删除历史内容。政策更正必须说明被替代版本、影响期间、影响运行和是否需要重新通知用户。
