# 领域模型

领域模型使用明确的养老制度、时间、管辖角色和证据状态，避免把所有“缴费月数”“地区”和“退休时间”压缩成含义不明的标量。

## 限界上下文

| 限界上下文 | 英文标识 | 责任 |
|---|---|---|
| 案件接入 | Case Intake | 用户授权、原始文件、脱敏和候选事实 |
| 参保与缴费账本 | Coverage Ledger | 制度参保期间、月度入账、缴费基数和账户快照 |
| 记录对账 | Record Reconciliation | 竞争性断言、差异原因和正式认定 |
| 政策注册表 | Policy Registry | 政策文件、规则版本、证据和适用范围 |
| 管辖与转移接续 | Jurisdiction Coordination | 参保地、待遇领取地、补贴受理地和跨区转移 |
| 退休资格 | Retirement Eligibility | 退休日期、最低年限和待遇资格测算 |
| 缴费定价 | Contribution Pricing | 基数、费率、舍入和应缴金额 |
| 补贴管理 | Subsidy Administration | 资格、申请、核定、暂停、发放和追缴 |
| 外部状态 | External Status | 就业、失业登记、失业待遇和身份事件时间线 |
| 场景规划 | Scenario Planning | 行动序列、假设、月度现金流和投影 |
| 决策支持 | Decision Support | 可行性、目标权重、门槛和条件式推荐 |
| 报告与审计 | Reporting and Audit | 不可变运行记录、结构化结果和展示产物 |

上下文通过ID和端口交换数据，不共享可变领域对象。医疗和失业保险可以复用通用账本接口，但必须使用独立的制度标识、规则和不变量。

## 核心类型

| 类型 | 定义 |
|---|---|
| `PensionScheme` | 法律上独立的养老制度，例如企业职工基本养老保险或城乡居民基本养老保险 |
| `SchemeEnrollment` | 某人在一个制度和经办机构下的生效参保期间 |
| `YearMonth` | 不含时区歧义的闭合日历月，格式为 `YYYY-MM` |
| `Money` | 带币种、最小单位、精度和舍入模式的不可变金额 |
| `ContributionPosting` | 权益文件或经办系统报告的一笔月度缴费入账 |
| `PaidCoverageMonth` | 已被接受付款的制度月份 |
| `RecognizedServiceMonth` | 被指定机关用于指定资格测试的认可月份 |
| `DeemedServiceMonth` | 没有普通缴费入账但依法认可的月份 |
| `ReportedAggregate` | 来源直接显示的汇总值，不与明细推导值互相覆盖 |
| `AccountSnapshot` | 明确账户类型和截止日期的余额快照 |
| `JurisdictionAssignment` | 某地区以特定角色作用于案件的生效关系 |
| `OfficialDetermination` | 经办机构针对具体案件作出的正式认定 |
| `Assessment` | 系统依据事实和规则计算的分析结果，不等同于正式认定 |
| `ConflictSet` | 对相同主体、字段、制度和期间存在的多个不兼容断言 |
| `Scenario` | 固定分析期间内不可变的行动序列 |
| `Recommendation` | 绑定运行、目标、假设、门槛和失效条件的决策产物 |
| `EligibilityAssessment` | 绑定能力、主体范围、适用规则和条件明细的三值资格判断 |
| `CapabilityAssessment` | 某项分析能力为可用、部分可用或阻塞的结构化说明 |

## 资格与能力状态

`EligibilityAssessment.status` 只能为：

- `ELIGIBLE`：没有失败或未核验条件；
- `INELIGIBLE`：至少一个条件已失败；
- `UNKNOWN`：没有已失败条件，但至少一个条件未核验。

每个条件使用 `SATISFIED`、`FAILED` 或 `UNVERIFIED`，并引用事实和规则。不得把缺失事实折算为否定条件，也不得把系统 `Assessment` 表述为机关 `OfficialDetermination`。

每项输入事实通过 `required_for` 关联分析能力。`CapabilityAssessment.status` 只能为：

- `AVAILABLE`：该能力所需事实齐备；
- `PARTIAL`：可输出有界结果，但缺少影响精度的事实；
- `BLOCKED`：无法产生该能力的权威结果。

## 管辖角色

单一“参保地区”字段不足以处理跨地区案件。`JurisdictionAssignment` 至少支持：

- `contribution_jurisdiction`：缴费记录所属地区；
- `current_enrollment_jurisdiction`：当前参保关系所在地；
- `household_registration_jurisdiction`：户籍地；
- `subsidy_service_jurisdiction`：补贴申领服务地；
- `benefit_determination_jurisdiction`：养老金待遇核定地；
- `medical_administration_jurisdiction`：医保经办地。

每个角色都带 `valid_from`、`valid_to`、来源和状态。不同制度或地区的月份不得直接合并，除非存在适用的转移、折算或协调规则。

## 不变量

1. 每个缴费、认可期间、账户快照和规则必须属于一个明确的制度。
2. 对同一制度和资格测试，一个日历月最多计入一次；多笔入账不自动产生多个月份。
3. `ContributionPosting` 不自动等于 `RecognizedServiceMonth`，后者也不自动证明发生普通缴费。
4. `ReportedAggregate` 和明细推导合计保持为两个独立观察值；差异进入 `ConflictSet`。
5. 只有机关证据可以产生 `OfficialDetermination`；系统只能产生 `Assessment`。
6. 冲突断言不可删除。解决后仍保留原值、解决依据、责任机关和时间。
7. 不同 `PensionScheme` 或地区的月份，未经明确规则不得合并。
8. `Money` 运算必须币种一致，并记录每险种、每月和汇总的舍入阶段。
9. 场景与计算结果一旦发布即不可变；输入、规则或假设变化时创建新版本。
10. 推荐在依赖的事实、规则、假设或触发条件变化后立即失效。
11. 推荐不得依赖 `BLOCKED` 能力；依赖 `PARTIAL` 能力时必须显示限制和失效条件。
12. `ELIGIBLE`、`INELIGIBLE` 和 `UNKNOWN` 必须由条件状态机械推导，不能由叙述生成器覆盖。

## 模糊术语替换

| 避免使用 | 改用 |
|---|---|
| 缴费月数 | 实际入账月、已付款覆盖月或法定认可月 |
| 累计年限 | 指定制度、用途和认定机关的累计认可月数 |
| 退休时间 | 预计法定退休日、申报退休日、批准退休日或待遇起始日 |
| 地区 | 带角色和生效期间的 `JurisdictionAssignment` |
| 已确认 | 用户确认、来源报告、系统校验或机关正式认定 |
| 补贴 | 计划、申请、核定、应计、发放或追回状态 |
