# 工具与输出契约

工具只交换版本化JSON。Markdown、图表和DOCX/PDF均由同一个已验证结构化结果渲染，不允许各自产生计算结论。

## 统一响应信封

每个工具调用返回同一顶层结构：

```json
{
  "schema_version": "1.0.0",
  "tool_name": "calculate_scenarios",
  "tool_version": "1.2.0",
  "run_id": "01JEXAMPLE0000000000000000",
  "request_id": "01JREQUEST000000000000000",
  "status": "success",
  "data": {},
  "warnings": [],
  "errors": [],
  "provenance": [],
  "metrics": {
    "duration_ms": 184,
    "cache_hit": false
  }
}
```

- `status` 只能为 `success`、`partial` 或 `error`；
- `partial` 必须包含至少一个结构化 `warnings` 条目；
- `error` 必须包含至少一个稳定错误码，`data` 不得伪装为完整结果；
- `provenance` 保存规则包摘要、事实快照摘要和来源引用ID，不嵌入敏感原文；
- 未识别的必填schema主版本必须拒绝，不能尽力猜测。

工具信封和分析结果的状态范围不同。全局阻塞或执行失败使用工具信封 `error`，此时 `data` 为空且不生成 `analysis-output`。已经完成权威计算的 `analysis-output` 只允许 `success` 或 `partial`。

工具描述必须明确：用途、适用时机、输入schema、输出schema、错误码、敏感数据等级、幂等语义和最小恢复示例。工具名使用动作加领域对象，例如 `reconcile_records`、`resolve_policy_rules`、`calculate_scenarios` 和 `render_report`。

## 单一事实源

`analysis-output.schema.json` 定义分析输出的单一事实源。结构化输出至少包含：

- 冻结的输入、规则和假设摘要；
- 当前资格、缴费和账户事实；
- 每项请求能力的 `AVAILABLE`、`PARTIAL` 或 `BLOCKED` 状态及其 `required_for` 事实；
- 每项资格的 `ELIGIBLE`、`INELIGIBLE` 或 `UNKNOWN` 状态和条件明细；
- 每个场景的行动、月度现金流、结果和可行性；
- 结构化事实冲突、政策歧义、warnings和能力阻塞项；
- 概率或情景假设的来源类型、建模模式、证据和失效日期；
- 推荐、目标、依赖能力、阈值、证据等级和失效条件；
- 用于复现的双时态、引擎、schema、规则包和舍入版本。

叙述生成器只读取这个结果并返回带字段引用的段落。渲染器校验每个展示金额、日期和场景ID都可反查到结构化字段。若叙述与结构化结果冲突，以结构化结果为准并阻止发布。

## 工具边界

| 工具 | 读取 | 写入 | 关键限制 |
|---|---|---|---|
| `ingest_evidence` | 临时文件句柄 | 候选事实 | 不创建正式认定 |
| `reconcile_records` | 候选事实和证据 | 事实版本和冲突集 | 不静默覆盖冲突 |
| `resolve_policy_rules` | 双时态、制度、管辖 | 规则包引用 | 不抓取任意网页 |
| `calculate_scenarios` | 冻结运行 | 结构化结果 | 不调用LLM |
| `generate_narrative` | 结构化结果 | 非权威叙述 | 不改变数值或推荐 |
| `render_report` | 结构化结果和叙述 | 展示产物 | 不重算业务规则 |

工具调用图由应用用例固定；LLM不能任意调用删除、发布或政策批准能力。

`resolve_policy_rules` 通过 `PolicyRepository` 加载和选择规则包；`RegionPolicyProvider` 只提供管辖枚举和映射。`calculate_scenarios` 内的确定性求值器执行规则包中的 `PolicyRule`、`DecisionTable` 和 `ParameterTable`，核心计算器和地区适配器均不内置通用补贴公式。
