# 运行与端口契约

每次分析都是不可变、内容可寻址的 `AnalysisRun`。应用层只通过入站端口接收命令，并通过出站端口访问文件、政策、存储、时钟和报告渲染器。

## AnalysisRun

`AnalysisRun` 创建后只允许追加状态事件；已冻结的输入和结果不可原地修改：

```json
{
  "run_id": "01JEXAMPLE0000000000000000",
  "parent_run_id": null,
  "case_id": "case-pseudonym",
  "created_at": "2026-08-11T11:40:00-06:00",
  "as_of_effective_date": "2026-08-11",
  "as_known_at": "2026-08-11T11:40:00-06:00",
  "input_snapshot_digest": "sha256:<digest>",
  "policy_ruleset_digests": ["sha256:<digest>"],
  "assumption_set_digest": "sha256:<digest>",
  "engine_version": "1.0.0",
  "schema_version": "1.0.0",
  "rounding_profile": "CNY-half-up-v1",
  "random_seed": null,
  "status": "RECEIVED"
}
```

一个运行至少冻结：规范化事实快照、未解决冲突、制度和管辖关系、政策规则包摘要、假设集、目标权重、分析期间、引擎和schema版本、舍入配置以及随机种子。确定性流程的 `random_seed` 必须为 `null`。

输入事实按分析能力声明 `required_for`。缺项先形成 `CapabilityAssessment`：只有全部请求能力均为 `BLOCKED`，或安全/政策前置条件阻止任何权威计算时，运行才进入全局 `BLOCKED`。仍有能力可计算时进入 `READY`，最终结构化结果标记为 `partial` 并公开能力限制。

用户修改事实、审核员批准政策或引擎版本变化时创建新的 `AnalysisRun`，通过 `parent_run_id` 关联。旧运行及其产物继续可读，不进行就地迁移。

## 入站端口

| 入站端口 | 命令 | 输出 |
|---|---|---|
| `CreateCaseUseCase` | 授权、最小身份元数据 | `case_id` |
| `IngestEvidenceUseCase` | 文件句柄、文件类型、授权范围 | 候选事实与来源引用 |
| `ReconcileRecordsUseCase` | 候选事实、用户确认、机关证据 | 事实快照与冲突集 |
| `PublishRuleSetUseCase` | 候选规则包、审批 | 已签名规则包摘要 |
| `CreateAnalysisRunUseCase` | 案件版本、目标、假设、分析日期 | `run_id` |
| `ExecuteAnalysisUseCase` | `run_id` | 结构化分析结果 |
| `RenderReportUseCase` | `run_id`、报告格式 | 产物引用 |

入站端口接受领域命令和ID，不接受HTTP请求、CLI参数或框架模型。认证、请求大小和传输格式由入口适配器处理。

## 出站端口

| 出站端口 | 语义 | 适配器示例 |
|---|---|---|
| `EvidenceReader` | 读取原始证据并返回稳定位置 | PDF、OCR、DOCX |
| `PolicyRepository` | 按双时态和摘要加载规则包 | 版本化文件、数据库 |
| `CaseRepository` | 读取和追加案件版本 | 加密本地库 |
| `RunRepository` | 持久化运行、事件、结果和清单 | SQLite、对象存储 |
| `RegionPolicyProvider` | 提供地区枚举和映射 | 地区插件 |
| `NarrativeGenerator` | 从冻结结果生成非权威叙述 | LLM、模板 |
| `ArtifactRenderer` | 渲染Markdown、DOCX/PDF和图表 | Pandoc、绘图库 |
| `Clock` | 提供可测试的当前时间 | 系统时钟、固定时钟 |
| `AuditSink` | 追加脱敏审计事件 | JSONL、安全日志服务 |

所有出站端口必须声明超时、重试安全性、数据敏感等级和失败错误码。领域层不得知道适配器类型。

## 事务边界

- 冻结事实快照和创建运行属于同一事务；
- 计算结果先写临时对象，校验通过后原子发布；
- 报告渲染失败不回滚已验证的结构化结果；
- 外部调用在事务外执行，并使用请求摘要实现幂等；
- 审计事件只能追加，禁止包含原始身份证号、银行卡号或完整原文。

## 状态机

`AnalysisRun` 使用追加事件驱动的状态机，而不是散布在组件中的布尔标志：

```text
RECEIVED
  → INGESTED
  → RECONCILED
  → BLOCKED | READY
  → CALCULATED
  → VALIDATED
  → RENDERED
  → PUBLISHED
```

| 当前状态 | 允许事件 | 下一状态 | 门禁 |
|---|---|---|---|
| `RECEIVED` | `INGESTION_COMPLETED` | `INGESTED` | 文件摘要和授权有效 |
| `INGESTED` | `RECONCILIATION_COMPLETED` | `RECONCILED` | 每个候选事实有来源 |
| `RECONCILED` | `BLOCKERS_FOUND` | `BLOCKED` | 全部请求能力阻塞，或安全/政策前置条件失败 |
| `RECONCILED` | `INPUTS_FROZEN` | `READY` | 至少一项请求能力可计算，事实、规则和假设已冻结 |
| `BLOCKED` | `REMEDIATION_APPLIED` | `RECONCILED` | 创建新事实版本，不能覆盖旧值 |
| `READY` | `CALCULATION_COMPLETED` | `CALCULATED` | 结果通过schema和算术自检 |
| `CALCULATED` | `VALIDATION_PASSED` | `VALIDATED` | 独立交叉验证与不变量通过 |
| `VALIDATED` | `RENDER_COMPLETED` | `RENDERED` | 产物摘要和结果引用一致 |
| `RENDERED` | `PUBLICATION_APPROVED` | `PUBLISHED` | 发布门禁和授权通过 |

任意处理步骤失败都追加 `RunFailureRecorded`，但不删除最后一个有效状态。重试只能从该状态发出合法事件。已进入 `PUBLISHED` 的运行是终态；任何修订创建子运行。

全局 `BLOCKED` 不生成 `analysis-output`；工具响应使用 `status: error`、空 `data` 和至少一个稳定错误码。已进入计算的运行生成的分析结果只使用 `success` 或 `partial`：全部请求能力为 `AVAILABLE` 时是 `success`，存在 `PARTIAL` 或 `BLOCKED` 能力时是 `partial` 且至少包含一个warning。

## 错误码

所有端口返回稳定错误码、可安全展示的消息、恢复动作和可选内部原因；调用方不得解析自然语言来判断分支。

| 错误码 | 类别 | 是否可重试 | 恢复动作 |
|---|---|---:|---|
| `INVALID_INPUT_SCHEMA` | 输入 | 否 | 修正字段类型或格式 |
| `MISSING_REQUIRED_FACT` | 领域阻塞 | 否 | 请求指定事实或选择显式未知 |
| `UNRESOLVED_RECORD_CONFLICT` | 领域阻塞 | 否 | 获取机关证据或人工裁决 |
| `AMBIGUOUS_POLICY_RULE` | 政策阻塞 | 否 | 完成政策审核和显式覆盖关系 |
| `POLICY_VERSION_NOT_FOUND` | 政策阻塞 | 否 | 加载匹配双时态和地区的规则包 |
| `RULESET_INCOMPATIBLE` | 兼容性 | 否 | 使用兼容引擎或迁移规则包 |
| `EXTERNAL_SOURCE_TIMEOUT` | 外部依赖 | 是 | 按退避策略重试或改用已批准缓存 |
| `CONTENT_DIGEST_MISMATCH` | 完整性 | 否 | 隔离产物并重新采集来源 |
| `PRIVACY_POLICY_VIOLATION` | 安全 | 否 | 停止处理、清除临时产物并审计 |
| `CALCULATION_INVARIANT_FAILED` | 引擎 | 否 | 隔离运行并提交工程调查 |
| `ARTIFACT_RENDER_FAILED` | 展示 | 是 | 保留结构化结果并重试渲染 |

错误响应不包含堆栈、原始证件号码、完整政策文本或文件路径。内部诊断使用与 `run_id` 关联的受控审计事件。
