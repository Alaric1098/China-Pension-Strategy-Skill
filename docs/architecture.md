# 系统架构

本文定义 `china-pension-strategy` 的可实施架构约束。README说明项目目标和产品边界；本文说明组件如何协作、哪些阶段允许使用LLM、哪些结果必须由确定性代码产生。

## 确定性内核

系统采用“受控智能外壳 + 确定性内核”。LLM属于非确定性组件，只能执行无法用固定算法可靠完成的语言任务。任何会改变月份、金额、资格结果或方案排序的数据都必须经过结构校验和批准后才能进入内核。

| 阶段 | 分类 | 允许的职责 | 禁止的职责 |
|---|---|---|---|
| 文档/OCR解释 | 非确定性或适配器相关 | 生成带来源位置和置信度的候选事实 | 直接修改已确认事实或计算金额 |
| 政策发现与条文解释 | 非确定性 | 生成候选规则、引用和待审核问题 | 直接生成可执行规则 |
| 脱敏与结构校验 | 确定性 | 检测敏感字段、验证schema和标准化格式 | 猜测缺失值 |
| 人工批准 | 控制边界 | 批准候选事实、规则和冲突处理 | 静默接受低证据等级内容 |
| 规则解析 | 确定性 | 选择适用的版本化规则或返回歧义 | 使用未批准的网页文本 |
| 对账与计算 | 确定性 | 月份、金额、补贴、现金流和敏感性计算 | 调用LLM补全参数 |
| 策略评价 | 确定性 | 按显式目标和假设比较方案 | 自行发明成功概率 |
| 叙述生成 | 非确定性 | 解释冻结的结构化结果 | 重算、覆盖或省略关键结果 |
| 图表与报告 | 确定性适配器 | 从冻结结果渲染JSON、Markdown、DOCX/PDF | 解析政策或改变结论 |

相同的规范化输入、政策快照、假设集、引擎版本和舍入配置必须产生完全相同的结构化计算结果。叙述措辞可以不同，但不属于权威计算记录。

## 决策流水线

```text
接入与脱敏
→ 事实对账
→ resolve_policy_rules + PolicyRepository
→ Eligibility Engine
→ Deterministic Calculator
→ Scenario Engine
→ Recommendation Engine
→ 结构化结果
```

- Eligibility Engine只返回 `ELIGIBLE`、`INELIGIBLE` 或 `UNKNOWN`，并列出满足、失败和未核验条件；
- Deterministic Calculator只执行已批准的 `PolicyRule`、`DecisionTable` 和 `ParameterTable`，不解释自然语言政策；
- Scenario Engine组合行动和显式假设，不发明概率；
- Recommendation Engine按可行性、目标、阈值和失效条件排序，只依赖 `AVAILABLE` 或明确披露限制的 `PARTIAL` 能力；
- `RegionPolicyProvider`只提供管辖枚举和映射，规则包加载由 `PolicyRepository` 完成，适用规则选择由 `resolve_policy_rules` 完成。

## 分层结构

```text
china-pension-strategy/
├── SKILL.md
├── src/
│   ├── domain/
│   ├── application/
│   ├── ports/
│   │   ├── inbound/
│   │   └── outbound/
│   ├── adapters/
│   │   ├── documents/
│   │   ├── policies/
│   │   ├── regions/
│   │   ├── persistence/
│   │   └── reporting/
│   └── entrypoints/
│       └── cli/
├── policy-data/
├── schemas/
├── tests/
└── evals/
```

## 依赖规则

依赖只能向内：

```text
entrypoints → application → domain
adapters ───────implements────→ ports
application ─────depends on───→ ports + domain
```

- `domain/` 不导入Pydantic、文件系统、HTTP、LLM SDK、Word、Pandoc或数据库代码。
- `application/` 编排用例并依赖抽象端口，不导入任何具体适配器。
- `ports/` 定义内核需要的协议，不包含外部框架类型。
- `adapters/` 负责把PDF、网页、地区政策、存储和报告格式转换为端口类型。
- `entrypoints/` 只解析请求、调用用例并映射响应，不承载政策或计算逻辑。
- 报告和图表只能读取冻结的结构化结果，不能反向调用政策解析或计算模块。
- 核心计算器和地区适配器均不得硬编码通用补贴公式；地区差异必须表现为已批准规则包中的可执行规则和参数。

CI应加入架构测试，阻止 `domain` 或 `application` 导入 `adapters`、`infrastructure` 和外部驱动。

## 决策原则

架构复杂度必须服务于可复核性。优先使用单进程、文件或本地数据库和明确端口；只有在性能、并发或恢复测试证明有必要时，才引入工作流引擎、远程服务或多Agent拓扑。
