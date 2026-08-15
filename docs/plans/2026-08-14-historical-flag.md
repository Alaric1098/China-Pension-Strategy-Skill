# 历史包与到期门禁区分 Implementation Plan（待审批）

> 依据"先计划→审核→批准→执行"规则提交。**批准前不做任何修改**。

---

## 问题

`scripts/policy_expiry_report.py` 把两个**故意过期**的历史包（广州/深圳 2024 医疗，各报
包级+规则级 2 行）与**该更新却没更新**的现行包（广州医疗 4 个月到期、天津补贴 16 个月）
混在同一 exit 1 门禁里。长期看维护者会无视门禁。

当前输出（--as-of 2026-08-14）：
```
[EXPIRED] cn-pension/guangzhou/flex-medical-2024.1 / (package) ...
[EXPIRED] cn-pension/guangzhou/flex-medical-2024.1 / guangzhou-flex-medical-contribution-2024 ...
[EXPIRED] cn-pension/shenzhen/flex-medical-2024.1 / (package) ...
[EXPIRED] cn-pension/shenzhen/flex-medical-2024.1 / shenzhen-flex-medical-contribution-2024 ...
[EXPIRING_SOON] cn-pension/guangzhou/flex-employment-2026.1 / guangzhou-flex-medical-contribution ...
[EXPIRING_SOON] cn-pension/tianjin/flex-subsidy-2026.1 / (package) ...
```

## 推荐方案：显式 `historical: true` 包标记（方案 A）

包是数据声明；"此包是历史归档、非现行政策"应作为包自身元数据显式声明，
而不是靠包 ID 后缀猜测（后缀只是约定，未来其他历史包命名可能变化）。

### 改动清单

| 文件 | 动作 |
|---|---|
| `schemas/policy-package.schema.json` | 新增可选 `historical`（boolean，缺省 false，additionalProperties:false 需显式声明） |
| `src/china_pension_strategy/domain/policy.py` | `PolicyPackage` 新增 `historical: bool = False`（末尾默认字段，不影响现有构造） |
| `src/china_pension_strategy/adapters/policies/json_policy_repository.py` | `build_package` 读取 `record.get("historical", False)` |
| `policy-data/packages/guangzhou-flex-medical-2024.json` | 加 `"historical": true` + content_digest 重算 |
| `policy-data/packages/shenzhen-flex-medical-2024.json` | 加 `"historical": true` + content_digest 重算 |
| `scripts/policy_expiry_report.py` | 输出分类：`HISTORICAL` 单列（包级+规则级都列出，便于审计），**不计入退出码**；`EXPIRED`/`EXPIRING_SOON` 仅限非历史包；退出码语义改为"仅现行包到期" |
| `tests/policy/test_official_packages.py` | 历史包例外断言改用 `package.historical`（替代包 ID 后缀判断） |
| 新增 `tests/test_expiry_report.py` | 报告单测：历史包标 HISTORICAL 且不计 exit；现行包到期仍 exit 1；混合场景 |

### 退出码语义（新）

- `0`：无现行包到期/将到期（历史包忽略）
- `1`：至少一个**现行**包或规则已到期/18 个月内将到期
- 历史包无论何时到期都只出现在 HISTORICAL 行，不影响退出码

### 验证

- `python scripts/policy_expiry_report.py --as-of 2026-08-14`：历史包 4 行标 HISTORICAL；
  广州医疗/天津补贴 2 行仍 EXPIRING_SOON；退出码 1（因广州医疗 4 个月到期——仍正确）
- 删除广州医疗 effective_to 后（模拟无现行到期）退出码应为 0（测试中用临时目录模拟）
- 官方包测试 / 契约 / 全量 pytest 绿；北京 run_id 不变（历史包标记不改现行包）

## 备选方案 B（不推荐）：包 ID 后缀识别

报告脚本按 `-20XX.1` 正则识别历史包，零数据改动。缺点：后缀是命名约定而非声明，
未来历史包命名变化即失效；且 domain/schema 无法表达"此包是历史"这一语义。

## 审批请求

- 方案 A（historical 标记）：建议批准。
