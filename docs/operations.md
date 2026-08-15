# 可观测性与运行清单

可观测性的目标是证明系统执行了预期流程、定位失败阶段和重现结果，而不是收集用户材料。日志、指标和追踪默认只记录伪名ID、枚举、摘要、计数和耗时。

## 关联模型

- `request_id`：一次入口请求，可跨重试变化；
- `case_id`：不可逆伪名化的案件标识；
- `run_id`：不可变分析运行标识；
- `trace_id` / `span_id`：单次执行链路；
- `artifact_id`：内容寻址的产物标识。

所有运行级日志和指标包含 `run_id`。禁止记录姓名、证件号、手机号、银行卡号、完整地址、原始文本、金额明细或自由文本提示。

## 运行清单

每个 `VALIDATED` 运行生成机器可读 `run-manifest.json`，并与结果一起原子发布：

```json
{
  "schema_version": "2.0.0",
  "manifest_version": "2.0.0",
  "run_id": "01JEXAMPLE0000000000000000",
  "parent_run_id": null,
  "created_at": "2026-08-11T11:55:00-06:00",
  "analysis_mode": "LOCAL_MVP",
  "review_statuses": ["MVP_REVIEWED"],
  "component_versions": {
    "engine": "1.0.0",
    "input_schema": "1.0.0",
    "output_schema": "2.0.0",
    "manifest_schema": "2.0.0",
    "rounding_profile": "CNY-half-up-v1"
  },
  "input_snapshot_digest": "sha256:<digest>",
  "policy_rulesets": [
    {
      "package_id": "cn-pension/example/2026.1",
      "ruleset_id": "cn-pension/example/2026.1",
      "version": "2026.1.0",
      "digest": "sha256:<digest>"
    }
  ],
  "assumption_set_digest": "sha256:<digest>",
  "objective_digest": "sha256:<digest>",
  "engine_version": "1.0.0",
  "rounding_profile": "CNY-half-up-v1",
  "adapter_versions": {},
  "digests": {
    "input": "sha256:<digest>",
    "rules": ["sha256:<digest>"],
    "assumptions": "sha256:<digest>",
    "objective": "sha256:<digest>",
    "output": "sha256:<digest>",
    "artifacts": []
  },
  "validation": {
    "input_schema_valid": true,
    "policy_schema_valid": true,
    "output_schema_valid": true,
    "invariants_valid": true
  },
  "validation_suite": "architecture-and-domain-v1",
  "validation_status": "passed",
  "publication_status": "LOCAL_ONLY",
  "output_digest": "sha256:<digest>",
  "artifact_digests": [],
  "warnings_count": 0,
  "unresolved_conflicts_count": 0,
  "duration_ms": 512
}
```

`2.0.0` 是对上述既有运行清单的显式主版本迁移：保留 `parent_run_id`、`policy_rulesets`、顶层输入/假设/目标/输出/产物摘要、适配器版本、验证套件、计数和耗时；新增执行模式、政策审核状态、组件版本、分组摘要、逐类验证状态和发布状态。v1对象不能按v2静默读取，必须通过显式迁移创建新的v2对象和摘要，历史v1清单保持只读。

为保留上述兼容字段，v2有意同时保存顶层字段和分组字段，而不是删除旧字段。JSON Schema校验后、清单与结果原子发布前，应用层必须执行确定性语义校验：顶层引擎版本、清单schema版本和舍入配置必须与 `component_versions` 相等；顶层输入、假设、目标、输出、规则包和产物摘要必须按顺序与 `digests` 相等；`validation_status=passed` 时所有逐类验证字段必须为真。任一不一致均使清单验证失败，不得发布。

清单不包含原始事实值或政策全文。运维人员可以用摘要确认输入和产物完整性；有案件访问权的审核员再通过存储端口解析摘要对应对象。

## 结构化日志

允许的事件包括 `run_created`、`state_transitioned`、`port_call_completed`、`validation_failed`、`artifact_published`、`retention_deleted` 和 `security_violation_detected`。每个事件声明：

- 时间、严重级别、事件名和组件版本；
- `run_id`、`trace_id` 和可选错误码；
- 耗时、重试次数、对象计数和内容摘要；
- 数据分级和脱敏规则版本。

异常堆栈只进入受控工程日志，且在写入前经过路径、凭据和敏感值过滤。

## 指标与告警

| 指标 | 目的 | 告警示例 |
|---|---|---|
| 各状态运行数和停留时间 | 识别流程阻塞 | `READY`到`VALIDATED`的P95超过目标 |
| 各错误码计数 | 区分用户缺项、政策缺项与系统故障 | `CALCULATION_INVARIANT_FAILED`大于0 |
| 政策规则解析歧义率 | 发现规则覆盖不足 | 指定地区连续24小时超过基线 |
| 冲突集数量和解决时长 | 衡量对账质量 | 未解决冲突持续增长 |
| 缓存命中率和摘要不匹配数 | 验证缓存健康 | 摘要不匹配大于0 |
| 验证、渲染和发布成功率 | 定位产物流水线问题 | 成功率低于服务目标 |
| 保留删除逾期数 | 验证隐私生命周期 | 任一S3对象超过到期时间 |

指标标签不得包含用户ID、文件名、自由文本、具体金额或高基数规则ID。地区标签仅在样本量达到隐私阈值时启用。

## 诊断路径

1. 根据 `run_id` 查询当前状态和错误码；
2. 校验运行清单和产物摘要；
3. 定位失败span及端口适配器版本；
4. 用清单引用在隔离环境重放；
5. 比较结构化结果摘要和不变量；
6. 修复后创建子运行，不修改历史清单。
