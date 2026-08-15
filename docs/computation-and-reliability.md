# 计算与可靠性

计算引擎把政策规则、用户事实和场景假设转换为可复现的月度结果。确定事实与不确定事件使用不同的数据类型和展示方式。

## 概率治理

成功概率、补贴获批概率、就业持续概率和政策变化概率不是事实。每个概率参数必须声明：

- `event_id` 和事件的可判定定义；
- 数值、范围或分布；
- 来源类型：`official_statistic`、`user_provided`、`expert_assumption` 或 `scenario_only`；
- 来源日期、样本范围和适用人群；
- 相关事件及联合建模方法；
- 谁批准该参数以及何时失效。

LLM不得生成缺乏来源的成功概率。用户提供的概率必须标记为 `user_provided`，不能在报告中改写为客观统计。当没有可信概率时，输出门槛分析、范围分析或“未知”，而不是任意点估计。

只有当前有效、经过批准、事件定义和适用人群与案件匹配的 `official_statistic` 才能使用 `EVIDENCE_BACKED_PROBABILITY`。其他来源分别使用 `USER_ASSUMPTION`、`EXPERT_ASSUMPTION` 或 `SCENARIO_ONLY`；无合格统计时使用 `THRESHOLD` 或 `RANGE`。结构化结果必须保存 `modeling_mode`、来源、批准、失效时间和依赖处理，不能只展示一个百分比。

### 独立性

多个事件默认不独立。只有存在证据和审核结论时，才能把 `independence_assumption` 设为 `approved`。例如，灵活就业持续月份、补贴获批和失业待遇状态可能共享就业状态原因，不能简单相乘。

依赖关系采用以下一种方式表达：

- 联合情景表：列出允许的状态组合及权重；
- 条件概率：显式记录 `P(A | B)`；
- 相关范围：在已批准上下界内做敏感性分析；
- 不赋概率：比较最坏、基准和最好情景。

任何期望值必须同时展示关键概率、来源、独立性假设和门槛值。推荐仅在合理参数区间内稳定时才能称为稳健。

## 幂等

创建分析运行的幂等键为以下规范JSON的SHA-256摘要：

```text
idempotency_key = SHA256(
  case_version_id
  + input_snapshot_digest
  + ordered_policy_ruleset_digests
  + assumption_set_digest
  + objective_digest
  + analysis_horizon
  + as_of_effective_date
  + as_known_at
  + engine_semantics_version
  + schema_version
  + rounding_profile
)
```

相同幂等键的并发请求只能创建一个 `AnalysisRun`；其余请求返回相同 `run_id`。失败重试使用相同键，除非输入或计算语义版本发生实质变化。请求ID、Python 包发行版本、工具版本和适配器发行版本仅用于追踪，不参与计算身份。

## 内容寻址与缓存

事实快照、规则包、假设集、结构化结果和报告产物均使用内容寻址。缓存键必须覆盖所有影响结果的输入：

| 缓存 | 缓存键 | 可复用条件 |
|---|---|---|
| 文档解析 | 文件摘要 + 解析器版本 + OCR配置 | 文件和配置完全一致 |
| 政策解析 | 来源摘要 + 提取schema + 模型/模板版本 | 候选输出仍需审批 |
| 规则选择 | 制度 + 管辖 + 双时态 + 规则注册表摘要 | 注册表摘要一致 |
| 计算结果 | `idempotency_key` | 所有输入与版本一致 |
| 报告产物 | 结果摘要 + 模板摘要 + 渲染器版本 + 格式 | 仅展示层一致 |

缓存项存储内容摘要、创建时间、敏感等级、过期时间和生产组件版本。摘要校验失败时隔离缓存项并返回 `CONTENT_DIGEST_MISMATCH`。

以下变化自动产生新缓存键，不需要全局清空：事实版本、政策事务时间、假设、目标、分析期间、舍入方式、引擎语义、schema、模板或渲染器。纯包发行、文档、CI 和分发元数据变化不改变计算结果缓存键。涉及撤回授权或安全事件时，按内容索引删除所有关联缓存和派生产物。

## 月度数值规则

- 金额使用 `Decimal`，禁止二进制浮点参与权威结果；
- 按月计算后按政策指定阶段舍入，汇总不得反向改变单月值；
- 日期区间使用闭合 `YearMonth`，每一步明确是否包含起止月；
- 金额差异交叉验证容差默认为人民币0.01元，月份计数容差为0；
- 性能优化必须保持相同规范化结果摘要，否则视为行为变更。

## 结果发布不变量

`analysis-output.schema.json` 校验通过后、计算结果原子发布前，应用层必须执行确定性的跨引用语义校验。JSON Schema负责单个对象的形状和枚举，应用层校验负责数组之间无法由schema可靠表达的关系：

- 推荐中的每个能力依赖ID必须解析到顶层唯一的 `CapabilityAssessment`；
- 推荐声明的依赖状态必须与对应顶层能力状态完全一致；
- 推荐不得依赖顶层状态或依赖声明为 `BLOCKED` 的能力，只允许一致的 `AVAILABLE` 或 `PARTIAL`；
- 每项能力的 `required_fact_ids` 必须恰好等于互不相交的 `satisfied_fact_ids` 与 `missing_fact_ids` 之并集，三个列表均不得重复；`AVAILABLE` 必须满足全部必需事实且没有缺失事实；
- 养老金、医疗、失业缴费、补贴、净支出和累计支出均不得为负；应用层使用 `Decimal` 校验每月 `net_outflow = pension + medical + unemployment - subsidy`，累计支出按月连续递增，场景结果中的各项总额必须等于月度明细之和；
- 任一未解析引用、状态矛盾或阻塞依赖均使结果验证失败，不得写入已验证结果或交给渲染器。

该校验位于应用内层，不访问文件、适配器或外部服务；相同结构化输入必须产生相同通过结果或稳定错误。

## 缴费基数越界告警（非阻断）

申报的缴费基数若落在规则包公布的养老或医疗基数上下限之外，引擎**不钳制、不拒绝**：

- 数值仍按申报基数计算（结果与 run_id 保持不变）；
- 信封 `warnings` 中产出非阻断警告，例如 `CONTRIBUTION_BASE_BELOW_FLOOR`、
  `CONTRIBUTION_BASE_BELOW_MEDICAL_FLOOR`、`CONTRIBUTION_BASE_ABOVE_CEILING`、
  `CONTRIBUTION_BASE_ABOVE_MEDICAL_CEILING`，并注明"结果使用申报基数"。

警告只出现在信封（envelope）与审计记录，不进入 `analysis.json` 数值输出，因此不影响
内容寻址 run_id。缺省基数为 `None` 时不产生该类警告；规则无对应参数时不产生。
