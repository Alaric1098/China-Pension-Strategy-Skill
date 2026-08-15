# 中国养老保险技能能力扩展 Implementation Plan（三阶段路线图）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. No Git repository, so commit steps are omitted.

**Goal:** 把 `china-pension-strategy` 从"缴费与补贴计算器"升级为"辅助规划指导"技能：补齐待遇测算（养老金计发）与延迟退休引擎（P0），再覆盖五险费率、多地区比较/转移接续、补缴、城乡居民养老保险（P1），最后增强政策时效看板、申报流程、记账利率与敏感性分析（P2）。全程保持确定性引擎、契约测试与既有一线/二线城市 run_id 不动性。

**Architecture:** 延续既有模式——政策事实进 `policy-data/sources`（gov.cn 原文+文号+摘要）、规则进 `policy-data/packages`（MVP_REVIEWED、双时态、向量测试）、能力进 schema `requested_capabilities` 枚举、地区适配器扩展 fact 映射。P0 的待遇测算复用既有 `docs/plans/2026-08-12-benefit-estimation.md`（12+ 任务、证据档案、FLOOR_DIVIDE/POWER 运算符）；延迟退休作为新的 national 规则包 + 退休年龄推导（出生年月→法定退休年龄/弹性窗口），是待遇测算与缺口/补贴判定的公共输入。P1/P2 按依赖排序。

**Tech Stack:** Python 3.14、Decimal、jsonschema、pytest、scripts/webget.py（沙箱内 gov.cn 抓取）、确定性 CLI。

---

## Phase 1（P0）：待遇测算 + 延迟退休引擎

### Task 1: 执行既有待遇测算计划（引用子计划）

执行 `docs/plans/2026-08-12-benefit-estimation.md` 全部任务（证据档案 12 来源 → FLOOR_DIVIDE/POWER 运算符 → 待遇规则包 → 计发月数表 → domain/application → 适配器/夹具 → SKILL 同步 → 门禁）。完成标志：`PENSION_ESTIMATION` 能力上线、golden 待遇案例通过、全量测试绿。

### Task 2: 延迟退休引擎（国家规则包 + 退休年龄推导）

**Files:**
- Create: `policy-data/sources/retire-delay-decision-2024.json`、`retire-elastic-method-2025.json`（2024-09 全国人大决定 + 2025 弹性退休办法，gov.cn 原文）
- Create: `policy-data/packages/national-delayed-retirement.json`（退休年龄节奏：男每 4 个月延 1 个月至 63；女原 55 每 4 个月延 1 个月至 58；女原 50 每 2 个月延 1 个月至 55；弹性提前 ≤3 年且不低于原法定、弹性延迟 ≤3 年）
- Modify: `src/china_pension_strategy/domain/values.py` 或新增 `domain/retirement.py`（出生年月 + 性别 + 原法定年龄 → 法定退休年月/弹性窗口推导，纯函数可测）
- Modify: `schemas/person-input.schema.json`（`requested_capabilities` 加 `RETIREMENT_AGE`；fact 加 `birth_year_month`、`gender`）
- Modify: 各地区适配器（退休年龄推导接入缺口/补贴"距退休"判定）
- Test: `tests/domain/test_retirement.py`、`tests/policy/test_official_packages.py`、契约/e2e

1. 调研并抓取：延迟退休决定（gov.cn 2024-09）、弹性退休办法（人社部发〔2025〕?号 或国办文件）、实施时间 2025-01-01。
2. 建来源记录 + references（national-rules.md 章节）。
3. 建 national 规则包（节奏表 DECISION_TABLE/PARAMETER_TABLE + 向量测试覆盖边界：1965 男、1970 女50、1975 女55、2000 后整 63/55/58 等）。
4. 实现退休年龄推导（纯函数）+ schema 扩展 + 适配器接线。
5. 门禁：official packages、契约、全量测试、北京/一线 run_id 不动。

---

## Phase 2（P1）：规划覆盖补全

### Task 3: 五险费率补齐（医保/失业/工伤，per region）

补齐广深/新城市的灵活就业医保与失业费率（粤医保规〔2022〕2号 等正文图片 OCR 或替代来源）；上海已有医疗 11%。完成标志：各城 `monthly_medical_contribution`/`monthly_unemployment_contribution` 不再为"未覆盖=0"。

### Task 4: 多地区比较与转移接续

新增 `CROSS_REGION_COMPARISON` 能力：跨省转移、临时账户、待遇领取地确定规则（缴满 10 年优先、户籍地兜底）national 规则包；比较引擎（同一个人事实在多个 region 的缴费/待遇输出对比表）。差异化能力。

### Task 5: 补缴政策

新增 `BACK_PAYMENT` 能力：灵活就业不得补缴（已实现口径）、单位补缴、2025 补缴新政、退休时不足年限的延缴路径；缺口场景方案集加入"补缴"。

### Task 6: 城乡居民养老保险及制度衔接

新增 `RESIDENTS_PENSION` 能力：城乡居民养老规则包 + 职工↔居民衔接折算（缴费年限/账户合并）。扩展适用人群。

---

## Phase 3（P2）：增强与体验

### Task 7: 政策时效看板
利用双时态/评估既有 `policy-version-miss` 机制，新增 `POLICY_EXPIRY_WATCH` 输出"哪些规则包将于何时失效/需更新"。

### Task 8: 申报办理流程指南
per-region 办事指南（参保登记、基数申报、补贴申请的材料/渠道/时限）进 references 并按需输出流程清单。

### Task 9: 个人账户记账利率与余额测算
记账利率（年度公布）→ 账户余额预测 → 与待遇测算联动（复用 benefit 计划的 POWER 运算符）。

### Task 10: 敏感性分析
基数档次（60%-300%）、退休时点、补贴申请时机对养老金/现金流的敏感性矩阵。

### Task 11: 个人养老金（第三支柱）税优测算
国家个人养老金账户税优（缴费/投资/领取三环节）测算；保持不推荐具体产品。

---

## 验证与门禁（每阶段）

- 契约测试 `tests/e2e/test_skill_contract.py` 通过；`tests/policy/test_official_packages.py` 通过
- 全量 `python -m pytest -q`（默认配置）通过；沙箱 tmp_path 已由 conftest 修复
- 北京 `run-a7440a1a...`、上海 `run-9e28e452...` 及全部已覆盖地区 run_id 不变
- 每 Task 记入 `docs/execution-log-2026-08-14-skill-polish.md`

## 明确不纳入

商业养老保险产品推荐、股票基金投资建议（保持技能不应触发边界）；真实权益文件 OCR 摄取列为长期可选。
