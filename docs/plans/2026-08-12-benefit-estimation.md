# Pension Benefit Estimation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. No Git repository, so commit steps are omitted.

**Goal:** Add a deterministic pension benefit estimation capability (`PENSION_ESTIMATION`) to the Beijing LOCAL_MVP: statutory retirement derivation (progressive delayed retirement), personal-account payment-months lookup (non-integer age interpolation), base/personal-account/transition pension formulas, and account balance projection — all driven by source-backed `MVP_REVIEWED` rule packages.

**Architecture:** Follow the established hexagonal pattern. New rules live in two new packages (`national-pension-benefit`, `beijing-pension-benefit`) with sources in `policy-data/sources/`. The deterministic evaluator gains two generic arithmetic operators (`FLOOR_DIVIDE`, `POWER`) so the delay formula and compound projection are expressed in rule EXPRESSION ASTs, not hardcoded. Domain result dataclasses in `domain/benefit.py`; pure orchestration in `application/estimate_pension.py`; Beijing adapter maps new fact types; `analyze.py` embeds the estimation into the output; schemas extended additively (capability enum + optional output field) so existing fixtures keep identical run IDs.

**Tech Stack:** Python 3.12+, dataclasses, Decimal, jsonschema, pytest, Hypothesis. Policy facts researched on 2026-08-12 via gov.cn / municipal official sites (see Task 1).

---

### Task 1: Evidence Archive For Benefit Estimation

**Files:**
- Create: `policy-data/sources/*.json` (12 new source records)
- Modify: `policy-data/source-digests.json`, `references/national-rules.md`, `references/regions/beijing.md`
- Modify: `src/china_pension_strategy/domain/policy.py` (`_AUTHORITY_LEVELS`)
- Modify: `schemas/policy-package.schema.json` (`authority_level` enum)
- Modify: `docs/policy-model.md` (if it enumerates authorities)
- Test: `tests/policy/test_official_packages.py`, `tests/contracts/test_schemas.py`

1. **Extend authority levels.** Add `PROVINCIAL_HRSS`, `MUNICIPAL_GOVERNMENT`, `MUNICIPAL_HRSS` to `_AUTHORITY_LEVELS` in `src/china_pension_strategy/domain/policy.py` and to the `authority_level` enum in `schemas/policy-package.schema.json`. Update `docs/policy-model.md` if it lists authorities. Add tests: new authorities accepted by domain `PolicySource` and schema; `PRIVATE_BLOG` still rejected.

2. **Write 12 source records** in `policy-data/sources/*.json` (one file per source, matching existing layout):

   | source_id | URL | document_number | authority_level | locator | purpose |
   |---|---|---|---|---|---|
   | npc-delay-decision-2024 | https://www.gov.cn/yaowen/liebiao/202409/content_6974294.htm | null | NATIONAL_GOVERNMENT | 决定第一点；办法第一条、第二条 | 延迟退休节奏：男每4个月延迟1个月至63；女原55每4个月延迟1个月至58；女原50每2个月延迟1个月至55；2025-01-01施行；2030年起最低缴费年限每年提高6个月至20年 |
   | mohrss-elastic-2024-94 | https://www.gov.cn/zhengce/zhengceku/202501/content_6995747.htm | 人社部发〔2024〕94号 | NATIONAL_MINISTRY | 第一条、第三条、第七条 | 弹性提前≤3年且不低于原法定退休年龄；弹性延迟≤3年（MVP 不执行弹性，仅口径说明） |
   | guofa-2005-38 | https://www.gov.cn/zhengce/zhengceku/2008-03/28/content_7376.htm | 国发〔2005〕38号 | NATIONAL_GOVERNMENT | 第六部分；附件计发月数表 | 基础养老金=(上年度在岗职工月平均工资+本人指数化月平均缴费工资)/2×缴费每满1年×1%；个人账户养老金=储存额÷计发月数；灵活就业缴费20%其中8%入个人账户；计发月数表（40-70岁整岁） |
   | guoban-2019-13 | https://www.gov.cn/zhengce/content/2019-04/04/content_5379629.htm | 国办发〔2019〕13号 | NATIONAL_GOVERNMENT | 第三部分 | 灵活就业可在全口径社平工资60%-300%间选缴费基数（指数口径佐证） |
   | beijing-order-183-2006 | https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_56666.html | 北京市人民政府令第183号 | BEIJING_MUNICIPAL_GOVERNMENT | 第二十三、二十四条 | 基础养老金以本市上一年度职工月平均工资和本人指数化月平均缴费工资平均值为基数，缴费每满1年发给1%；个人账户养老金=储存额÷国家规定计发月数 |
   | beijing-2007-21 | https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/200804/t20080414_567066.html | 京劳社养发〔2007〕21号 | BEIJING_HRSS | 二、基本养老金计发办法 | 基础养老金公式与国家一致；过渡性养老金=按视同缴费年限计算的月过渡性养老金+按实际缴费年限计算的月过渡性养老金，均每满1年发给1% |
   | beijing-2007-31 | https://rsj.beijing.gov.cn/xxgk/2024zcwj/202406/t20240617_3717464.html | 京劳社养发〔2007〕31号 | BEIJING_HRSS | 二、第（二）项 | 视同缴费年限=1992-09-30前连续工龄；Z同指数=1；N实98=1992-10-01至1998-06-30实际缴费年限 |
   | beijing-2024-16-base | https://rsj.beijing.gov.cn/xxgk/2024zcwj/202412/t20241224_3972825.html | 京人社发〔2024〕16号 | BEIJING_HRSS | 一、养老金计发基数 | 2024年到龄退休核定待遇以11883元/月为计算基数 |
   | beijing-2025-13-base | https://www.beijing.gov.cn/zhengce/zhengcefagui/202511/t20251107_4265441.html | 京人社发〔2025〕13号 | BEIJING_HRSS | 一、养老金计发基数 | 2025年到龄退休核定待遇以12049元/月为计算基数 |
   | mohrss-2017-31-interest | https://www.mohrss.gov.cn/SYrlzyhshbzb/zhengcefabu/bumenjianzhang/zcjd/201704/t20170425_270902.html | 人社部发〔2017〕31号 | NATIONAL_MINISTRY | 二、四 | 个人账户记账利率每年由国家统一公布，不得低于银行定期存款利率 |
   | jinan-payment-months-2025 | https://www.jinan.gov.cn/col23076/art/2025/art_23076_5018027.html | null | MUNICIPAL_GOVERNMENT | 退休金与养老保险缴费年限、基数高低有关；计发月数答复 | 2025-01-01起非整岁退休按到月月数表计发（60岁1个月=138.4；50岁1个月=194.6）；地方经办佐证，不作为国家规范性文件 |
   | interest-rate-disclosure-2025 | https://www.yw.gov.cn/art/2025/6/3/art_1229134300_4228894.html | null | MUNICIPAL_GOVERNMENT | 企业职工基本养老保险（一） | 公告原文误标“2025年度…2.62%”；按全国年度序列作为2024年度利率存储并显式标记来源缺陷，只作可覆盖默认假设，不推断2025/2026+年度数值 |

   Each record: `source_id`, `url`, `issuing_authority`, `authority_level`, `document_number` (or null), `publication_date`, `retrieved_at` (2026-08-12T09:00:00Z), `locator`, `source_digest` (computed in step 4). **URLs must be `https://...gov.cn`**（`_GOV_URL` 与 schema 的 `pattern` 均要求 https + gov.cn）。实施时用 `curl -sI` 验证三个 https 端点可用（mof.gov.cn / jinan.gov.cn / yw.gov.cn）；若某端点 https 不可用，改用同文 gov.cn 镜像并在工程解释中注明。

   计发月数表整岁数值（国发〔2005〕38号附件）：40→233, 41→230, 42→226, 43→223, 44→220, 45→216, 46→212, 47→207, 48→204, 49→199, 50→195, 51→190, 52→185, 53→180, 54→175, 55→170, 56→164, 57→158, 58→152, 59→145, 60→139, 61→132, 62→125, 63→117, 64→109, 65→101, 66→93, 67→84, 68→75, 69→65, 70→56。附件为 gov.cn 图片；数值经许昌市政府网文本版 PDF（https://www.xuchang.gov.cn/upload/2016/05/04/20160504154258597.pdf）与岳阳市人社局网页（https://rsj.yueyang.gov.cn/7719/7742/59334/65117/65119/content_1930069.html）交叉验证；两者作为工程交叉核对 URL，不单独建立 source record。

3. **Write reference sections.** Add `## 来源：<source_id>` blocks to `references/national-rules.md` (national + municipal-scope sources: npc-delay-decision-2024, mohrss-elastic-2024-94, guofa-2005-38, guoban-2019-13, mohrss-2017-31-interest, jinan-payment-months-2025, interest-rate-disclosure-2025 — `reference_sections()` only scans national-rules.md and regions/beijing.md) and to `references/regions/beijing.md` (Beijing: beijing-order-183-2006, beijing-2007-21, beijing-2007-31, beijing-2024-16-base, beijing-2025-13-base), established format: URL、文号、发布、施行、权威级别、发文机关、定位、原文摘录（关键句）、工程解释（原文→规则推断边界；未获原文支持的内容不进规则包）。Digest rule: `source_digest` = SHA-256 of the section body from its first line to the next `## ` heading or file end — mirror the exact algorithm in `tests/policy/test_official_packages.py` (check whether trailing newline stripped).

4. **Compute and write digests.** Update `policy-data/source-digests.json` (keep existing 9 entries untouched; add 12 new). Generate with the same function the test uses.

5. **Run tests; expect pass.**
   ```
   python -m pytest tests/policy/test_official_packages.py tests/contracts/test_schemas.py tests/domain/test_policy.py -q
   ```

---

### Task 2: Engine Operators FLOOR_DIVIDE And POWER

**Files:**
- Modify: `src/china_pension_strategy/domain/policy.py`
- Modify: `src/china_pension_strategy/application/calculate_months.py`
- Modify: `schemas/policy-package.schema.json`
- Test: `tests/domain/test_policy.py`, `tests/domain/test_calculation.py`, `tests/contracts/test_schemas.py`

1. **Write failing tests first** (extend `tests/domain/test_calculation.py`, where engine evaluator tests live; do not create `tests/application/test_calculation.py`):
   - `FLOOR_DIVIDE(7,4)==1`, `(1,4)==0`, `(-1,4)==-1`, `(-5,2)==-3` (Python `//` semantics), DECIMAL variants, rejection of non-numeric operands.
   - `POWER("1.05", 2) == Decimal("1.1025")`; `POWER("1.0021833333", 12)` ≈ 1.026517…; rejection of invalid powers.
   - Validation failures in `tests/domain/test_policy.py`: `POWER` non-DECIMAL value_type rejected; `POWER` with ≠2 operands rejected; `FLOOR_DIVIDE` non-numeric operands rejected; `FLOOR_DIVIDE` non-INTEGER result type rejected.

2. **Implement.** `domain/policy.py`: extend `_EXPRESSION_OPERATORS` with `FLOOR_DIVIDE`, `POWER`; validation: FLOOR_DIVIDE numeric operands, exactly 2 operands, `INTEGER` value_type; POWER exactly 2 DECIMAL operands + `DECIMAL` value_type. `calculate_months.py`: `_floor_divide` (Decimal divide → `math.floor` → int; **mirror `_divide`'s zero-guard** so a zero divisor raises `DomainValidationError`, not raw `DivisionByZero`) and `_power` (Decimal `**` under `localcontext()` prec ≥ 40; raise `DomainValidationError` on invalid power). Wire into `evaluate_expression` dispatch. `schemas/policy-package.schema.json`: operator enum + exactly-two-operands constraint includes `POWER` **and `FLOOR_DIVIDE`**.

3. **Run tests; expect pass.**
   ```
   python -m pytest tests/domain/test_policy.py tests/domain/test_calculation.py tests/contracts/test_schemas.py -q
   ```

---

### Task 3: Benefit Rule Packages

**Files:**
- Create: `policy-data/packages/national-pension-benefit.json`
- Create: `policy-data/packages/beijing-pension-benefit.json`
- Test: `tests/policy/test_official_packages.py`

1. **National package** `cn-pension/national/pension-benefit-2026.1` (`scheme: enterprise_employee_basic_pension`, `topic: pension_benefit_estimation`, `jurisdiction: CN`, `review_status: MVP_REVIEWED`, `execution_modes: [LOCAL_MVP]`, `local_only: true`, `engine_compatibility: ">=0.1,<1.0"`, `effective_from: 2025-01-01`, `transaction_from` > max source `retrieved_at`). Rules:

   - `national-delayed-retirement-male` (POLICY_RULE): inputs `birth_year`/`birth_month` INTEGER. Parameters: `b0_year: 1965`, `b0_month: 1`, `step_months: 4`, `max_delay_months: 36`, `statutory_months: 720`. Result `delay_months` INTEGER:
     ```
     MIN(max_delay_months, MAX(0, ADD(1, FLOOR_DIVIDE(
        ADD(MULTIPLY(SUBTRACT(birth_year, b0_year), 12), SUBTRACT(birth_month, b0_month)),
        step_months))))
     ```
     Conditions: `birth_year >= 1900` guard (all POLICY_RULE and DECISION_TABLE types require ≥1 condition — `PolicyRule` rejects empty `conditions`, schema `minItems: 1`). Vectors: (1965,1)→1, (1965,4)→1, (1965,5)→2, (1976,2)→34, (1976,9)→36, (1976,12)→36, (1964,12)→0, (1990,1)→36.
   - `national-delayed-retirement-female-55`: same expression; params `b0_year: 1970`, `b0_month: 1`, `step_months: 4`, `max_delay_months: 36`, `statutory_months: 660`. **Condition `birth_year >= 1900`** (keeps pre-baseline vector (1969,12)→0 passing). Vectors: (1970,1)→1, (1970,5)→2, (1981,12)→36, (1969,12)→0, (1982,1)→36.
   - `national-delayed-retirement-female-50`: params `b0_year: 1975`, `b0_month: 1`, `step_months: 2`, `max_delay_months: 60`, `statutory_months: 600`. **Condition `birth_year >= 1900`** (keeps (1974,12)→0 passing). Vectors: (1975,1)→1, (1975,2)→1, (1975,3)→2, (1975,12)→6, (1984,12)→60, (1985,1)→60, (1974,12)→0.
   - `national-payment-months-table` (DECISION_TABLE): input `age_years` INTEGER, condition `age_years >= 40` (DECISION_TABLE rules also require ≥1 condition, cf. `beijing-subsidy-duration`), `input_domains` 40..70 (31 values), 31 rows (`age_years = N` → `payment_months` INTEGER per the table above). Vectors: 50→195, 55→170, 60→139, 63→117, 45→216, 70→56.
   - `national-basic-pension-formula` (POLICY_RULE): inputs `c_ping`/`avg_index`/`total_months` **DECIMAL** (adapter converts the integer `total_contribution_months` fact to Decimal; expression trees are type-homogeneous, so anything used under `DIVIDE` must be DECIMAL), condition `total_months >= 0` (PolicyRule requires ≥1 condition), → `basic_pension` DECIMAL:
     ```
     MULTIPLY(DIVIDE(ADD(c_ping, MULTIPLY(c_ping, avg_index)), 2.0),
              MULTIPLY(DIVIDE(total_months, 12.0), 0.01))
     ```
     DECIMAL literals must be string form with decimal point (`"2.0"`, `"12.0"`, `"0.01"` — schema `typedValueConsistency`). Vectors: (12049.00, 0.8, 360)→3253.23; (11883.00, 1.0, 300)→2970.75.
   - `national-account-growth-formula` (POLICY_RULE): inputs `balance`/`months`/`rate` **DECIMAL** (months sits under `POWER`), condition `months >= 0` → `stored_balance` DECIMAL:
     ```
     MULTIPLY(balance, POWER(ADD(1.0, DIVIDE(rate, 12.0)), months))
     ```
     Vector (input order balance, months, rate): (100000.00, 12, 0.0262) → **102651.69** (test computes expected with Decimal and same `localcontext`; 100000 × (1+0.0262/12)^12).
   - `national-personal-account-pension-formula` (POLICY_RULE): inputs `stored_balance`/`payment_months` DECIMAL, condition `payment_months > 0` → `monthly_personal_account` DECIMAL = `DIVIDE(stored_balance, payment_months)`. Vector: (138096.30, 118.3)→1167.34.
   - `national-record-interest-rate` (POLICY_RULE, not PARAMETER_TABLE — PolicyRule semantics are simpler here): inputs `months` INTEGER, condition `months >= 0`, result `record_interest_rate` DECIMAL = `{kind: REFERENCE, reference_type: PARAMETER, reference_id: "record_interest_rate"}`; parameter `record_interest_rate` DECIMAL = `0.0262` (义乌公告标注"2025年度"记账利率，见 `interest-rate-disclosure-2025` 的歧义说明；作为可覆盖的默认滚存假设，明确标注"2026年度及以后属用户假设"). Vector: (0)→0.0262. The application reads the parameter value directly via `_parameter_value` and never evaluates this rule; the rule exists solely as a provenance carrier. Sources: `interest-rate-disclosure-2025`, `mohrss-2017-31-interest`.

   Every rule (incl. both DECISION_TABLEs) must declare `test_vectors` with minItems 1 (`test_official_package_rules_are_source_supported_and_vector_tested` fails otherwise); scheme/topic match package, `source_refs` ⊆ provenance, `effective_from: 2025-01-01`, `legal_hierarchy` NATIONAL_LAW (决定/38号文) or MINISTRY_RULE (记账利率).

   **Package `provenance` must include ALL new national sources** (npc-delay-decision-2024, mohrss-elastic-2024-94, guofa-2005-38, guoban-2019-13, mohrss-2017-31-interest, interest-rate-disclosure-2025, jinan-payment-months-2025, xuchang-payment-months-pdf if created): `test_every_source_record_is_used_by_at_least_one_package` requires every digest entry to appear in some package's provenance.

2. **Beijing package** `cn-pension/beijing/pension-benefit-2026.1` (`jurisdiction: CN-11`, `jurisdiction_role: LOCAL_IMPLEMENTATION`, `population_scope: beijing participants`, same review gates). Rules:
   - `beijing-c-ping-table` (DECISION_TABLE): input `retirement_year` INTEGER, **condition `retirement_year >= 2024`** (≥1 condition required), domains [2024, 2025] → `c_ping` DECIMAL: 2024→11883.00, 2025→12049.00. Vectors for both rows.
   - `beijing-transition-pension-formula` (POLICY_RULE): inputs `c_ping`/`avg_index`/`deemed_years`/`transition_years_98` DECIMAL, condition `deemed_years >= 0` → `transition_pension` DECIMAL:
     ```
     ADD(MULTIPLY(MULTIPLY(c_ping, deemed_years), RATE),
         MULTIPLY(MULTIPLY(MULTIPLY(c_ping, avg_index), transition_years_98), RATE))
     ```
     (G同 = C平×N同×1%，G实 = C平×Z实指数×N实98×1%，视同指数 Z同 = 1。系数 1% 为参数 `transition_rate: 0.01`，表达式经 `{kind: REFERENCE, reference_type: PARAMETER, reference_id: "transition_rate"}` 引用。) Vectors: (12049.00, 0.8, 3.0, 0.0)→361.47; (12049.00, 0.8, 5.5, 2.0)→855.48.

   **Beijing package `provenance` must include ALL new Beijing sources** (beijing-order-183-2006, beijing-2007-21, beijing-2007-31, beijing-2025-13-base) — see the `test_every_source_record_is_used_by_at_least_one_package` requirement above.

3. **Package tests.** Extend `tests/policy/test_official_packages.py`: schema validation of both packages; dual-temporal applicability at 2026-08-12; content-digest recomputation; provenance cross-file consistency (shared sources byte-identical); rule vectors evaluated through the engine — **compare DECIMAL outputs quantized to 0.01 HALF_UP** (engine is exact; e.g. 138096.30/118.3 = 1167.3398… but the pinned expectations are the quantized 1167.34 / 855.48 / 102651.69); source-ref resolution; new sources present in `source-digests.json`.

4. **Run tests; expect pass.**
   ```
   python -m pytest tests/policy/test_official_packages.py -q
   ```

---

### Task 4: Domain And Application Layer

**Files:**
- Create: `src/china_pension_strategy/domain/benefit.py`
- Create: `src/china_pension_strategy/application/estimate_pension.py`
- Create: `tests/domain/test_benefit.py`, `tests/application/test_estimate_pension.py`

1. **Write failing domain tests** (`tests/domain/test_benefit.py`) for the frozen dataclasses in step 2: required strings non-empty; amounts non-negative finite Decimals; `payment_months` positive; valid `YearMonth`; `total_monthly == basic + personal_account + (transition or 0)`; `transition_pension` may be None; assumptions carry `source_type` (USER_OVERRIDE / PACKAGED_PARAMETER) and non-empty `note`.

2. **Implement `domain/benefit.py`** — frozen dataclasses:
   - `StatutoryRetirement`: `birth` YearMonth, `gender_category` str, `original_statutory_months` int, `delay_months` int, `retirement` YearMonth, `age_years` int, `age_months` int, `rule_refs` tuple[str,...]. Validates `retirement == birth.add_months(original + delay)` and `(age_years, age_months) == divmod(original + delay, 12)`.
   - `ProjectionAssumption`: `name` str, `value` object, `source_type` str, `source_refs` tuple[str,...], `note` str.
   - `PensionEstimate`: `statutory`, `payment_months` Decimal, `c_ping` Money, `c_ping_year` int, `record_interest_rate` Decimal, `account_balance` Money, `account_as_of_year_month` YearMonth, `stored_balance` Money, `total_contribution_months` int, `avg_index` Decimal, `deemed_years` Decimal, `transition_years_98` Decimal|None, `basic_pension` Money, `personal_account_pension` Money, `transition_pension` Money|None, `total_monthly` Money, `assumptions` tuple, `rule_refs` tuple[str,...], `limitations` tuple[str,...]. `total_monthly == basic + personal_account + (transition or 0)`.

3. **Write failing application tests** (`tests/application/test_estimate_pension.py`):
   - `derive_statutory_retirement(rules, birth, gender)`: male 1976-02 → retirement 2038-12, delay 34, age 62y10m; male 1965-01 → **2025-02** (birth + 720 + 1 months), delay 1, age 60y1m; female_50 1975-12 → 2026-06, delay 6, age 50y6m; female_55 1970-01 → 2025-02, delay 1, age 55y1m; unknown gender → `DomainValidationError`.
   - `payment_months_for_age(rules, 60, 0) == Decimal("139")`; (60,1)→138.4; (50,1)→194.6; (58,1)→151.4; **(62,10)→118.3** (125 − (125−117)×10/12 = 118.33…, HALF_UP 1 decimal; 119.7 is the 62y8m value); rounding HALF_UP to 1 decimal.
   - `project_stored_balance`: 100000.00, as_of 2026-08, retirement 2038-12, rate 0.0262 → months 148, stored ≈ **138096.30** (100000 × (1+0.0262/12)^148; test computes expected with Decimal and same `localcontext`); as_of after retirement → stored = balance.
   - Golden case `estimate_pension(...)`: male 1976-02, c_ping override 12049.00, avg_index 0.8, total 360, deemed 3.0, transition_years_98 None, balance 100000.00 as of 2026-08, rate default 0.0262 → basic 3253.23; stored ≈ 138096.30; payment_months **118.3**; MAP ≈ **1167.34** (138096.30/118.3); transition 361.47 with limitation "1998-06-30前实际缴费年限未提供"; total ≈ **4782.04** (3253.23 + 1167.34 + 361.47). Assumptions: c_ping USER_OVERRIDE, rate PACKAGED_PARAMETER with source refs.
   - Missing mandatory inputs: retirement year not in c_ping table AND no override → `DomainValidationError` naming the year. Missing `deemed_years` is **not** an error — `transition_pension` becomes None with limitation (PARTIAL outcome, matching Task 6) — both documented in docstring.

4. **Implement `application/estimate_pension.py`** — pure functions over `PolicyRule` tuples:
   - `_pick_delay_rule(rules, gender)`: select among `national-delayed-retirement-{male,female-55,female-50}`; raise if none.
   - `derive_statutory_retirement`: evaluate rule → `delay_months`; read `statutory_months` parameter; build `StatutoryRetirement` via `birth.add_months(statutory + delay)`.
   - `payment_months_for_age`: evaluate `national-payment-months-table` at `age_years` and `age_years+1`; linear interpolation by month fraction; quantize `Decimal("0.1")` HALF_UP; raise on lookup miss.
   - `c_ping_for_retirement(rules, retirement_year, override)`: override wins; else evaluate `beijing-c-ping-table`; miss → `DomainValidationError` naming the year.
   - `project_stored_balance`: months = `(retirement.year − as_of.year) × 12 + (retirement.month − as_of.month)` clamped ≥ 0; evaluate `national-account-growth-formula`; quantize 0.01.
   - `estimate_pension(...)`: orchestrate derive → c_ping → payment months → basic formula → growth → MAP formula → transition formula. **Skip only the G实 term when `transition_years_98` is None; G同 is still computed** (transition_pension = G同 with limitation "1998-06-30前实际缴费年限未提供"); if `deemed_years` is missing, transition_pension is None (PARTIAL). Assemble `PensionEstimate` with assumptions and limitations (missing 98-period years; future-year c_ping/rate assumptions need verification). All money quantized to 0.01 HALF_UP.

5. **Run tests; expect pass.**
   ```
   python -m pytest tests/domain/test_benefit.py tests/application/test_estimate_pension.py -q
   ```

---

### Task 5: Integration — Schema, Adapter, Use Case, Renderer

**Files:**
- Modify: `schemas/person-input.schema.json`, `schemas/analysis-output.schema.json`
- Modify: `src/china_pension_strategy/adapters/regions/beijing.py`
- Modify: `src/china_pension_strategy/application/analyze.py`
- Modify: `src/china_pension_strategy/adapters/reporting/markdown_renderer.py`
- Test: `tests/adapters/test_privacy.py`, `tests/application/test_analyze.py`, `tests/adapters/test_reporting.py`

1. **Extend person-input schema.** Add `PENSION_ESTIMATION` to the `capability` enum (additive; keep `const "1.0.0"`). Fact types are unconstrained strings; document accepted fact types in the schema `description` (optional).

2. **Extend analysis-output schema.** Add optional property `pension_estimation: { "type": ["object", "null"] }` (not required).

3. **Extend Beijing adapter** (`adapters/regions/beijing.py`):
   - New fact mappings in `to_analysis_request`:
     - `birth_year_month` (`YYYY-MM`) → `YearMonth`
     - `gender_category` → `MALE` | `FEMALE_55` | `FEMALE_50` (invalid → `RegionMappingError`)
     - `total_contribution_months` → int
     - `deemed_years`, `transition_years_98`, `average_contribution_index`, `account_balance`, `interest_rate_override`, `c_ping_override` → Decimal
     - `account_balance` uses the fact's `as_of_date` as as-of `YearMonth`
   - Collect into `AnalysisRequest.pension_inputs` + typed `account_as_of_year_month`.
   - `policy_queries(...)`: **add a `requested_capabilities: tuple[str, ...] = ()` parameter (backward compatible — existing callers unchanged); when `PENSION_ESTIMATION` requested**, append queries `(CN, pension_benefit_estimation, NATIONAL_BASELINE, enterprise participants)` and `(CN-11, pension_benefit_estimation, LOCAL_IMPLEMENTATION, beijing participants)`. Conditional so legacy fixtures keep identical scoping and run IDs.

4. **Extend `application/analyze.py`:**
   - Add `pension_inputs: Mapping[str, object] = field(default_factory=dict)` and `account_as_of_year_month: YearMonth | None = None` to `AnalysisRequest`.
   - If `PENSION_ESTIMATION in requested_capabilities and pension_inputs`: call `estimate_pension(...)` with benefit rules from `packages`; embed into `output["pension_estimation"]` (status AVAILABLE/PARTIAL, statutory, payment_months, c_ping, account, components, total, assumptions, limitations, rule_refs). On missing mandatory data emit `{"status": "BLOCKED", "reason": ...}` instead of failing the run.
   - Include pension inputs/as-of in `input_digest` content **only when pension inputs are present (conditional keys)** — unconditional keys would change the digest for legacy requests and break the Task 5 step 6 requirement that existing golden replay yields identical `run_id`.

5. **Extend markdown renderer**: add `## Pension Estimation` section (statutory retirement, payment months, c_ping + year, balance → stored, components, total, assumptions, limitations) rendered only when `pension_estimation` present.

6. **Update tests**: person-input loader accepts new capability; analyze emits `pension_estimation` for complete inputs; capability requested but facts missing → BLOCKED without run failure; existing golden replay still yields identical `run_id`.

7. **Run tests; expect pass.**
   ```
   python -m pytest tests/adapters/test_privacy.py tests/application/test_analyze.py tests/adapters/test_reporting.py -q
   ```

---

### Task 6: Eval Fixtures, Skill Surface, Docs, Gates

**Files:**
- Create: `evals/fixtures/golden-beijing-benefit-2038.json`
- Create: `evals/fixtures/partial-beijing-benefit.json`
- Modify: `evals/evals.json`, `SKILL.md`, `README.md`, `CHANGELOG.md`, `tests/e2e/test_skill_contract.py`

1. **Golden eval fixture** `golden-beijing-benefit-2038.json`: male, birth 1976-02, total_contribution_months 360, deemed_years 3.0, average_contribution_index 0.8, account_balance 100000.00 (as_of 2026-08-11), c_ping_override 12049.00, capabilities include `PENSION_ESTIMATION`; no interest override (packaged 0.0262 default). Expected estimation matches Task 4 golden numbers (118.3 / 138096.30 / 1167.34 / 4782.04). Add second fixture `partial-beijing-benefit.json`: missing `deemed_years` → **status PARTIAL** (basic + personal-account computed; transition_pension None with limitation "视同缴费年限未提供，无法计算过渡性养老金"), while unresolvable c_ping without override → **BLOCKED**. Pin both semantics here to avoid churn.

2. **Eval manifest** `evals/evals.json`: register both fixtures with their expected run semantics (success + estimation fields; partial status).

3. **Update `tests/e2e/test_skill_contract.py`**: new capabilities listed in trigger coverage; golden-benefit full-chain (analyze → stored JSON → markdown render); partial fixture produces PARTIAL/BLOCKED without failure; old golden replay unchanged (regression: identical run_id).

4. **Update `SKILL.md`** (trigger description + capabilities list add pension benefit estimation), `README.md` (capability table + status), `CHANGELOG.md` (Task 13 entry: 待遇测算能力 — sources, packages, engine operators, domain/application, integration, fixtures, gates).

5. **Run the complete verification suite; expect zero failures:**
   ```
   python -m pytest -q
   python -m pytest tests/architecture -q
   python -m pytest tests/e2e -q
   python test_design_contracts.py
   python verify_design_docs.py
   python audit_architecture.py --gaps
   ```

---

### Notes And Open Items

- 计发月数表附件为 gov.cn 图片，整岁数值经政府网站文本版交叉验证；上线前建议人工核对 gov.cn 图片。
- 记账利率数值无国家层面公开文件（国家文件不公布数值），经义乌市政府官网披露确认：公告原文标注"2025年度…2.62%"（按人社部每年6月公布上一年度利率的惯例亦可能为2024年度口径——原文无法裁决，工程解释注明歧义）；打包为可覆盖默认假设并在输出标注"2026年度及以后属用户假设"。
- 非整岁计发月数插值来源为济南市 12345 答复（地方经办口径，国家无公开逐月表）；北京无专门文件，输出需注明口径来源。
- 未来年度（>2025）计发基数与记账利率无来源：要求用户覆盖或标注假设；计发基数表仅收录 2024/2025 两个已公布年度。
- 北京过渡性养老金需 1992-10~1998-06 实际缴费年限（N实98）才计算 G实；未提供则只计 G同并标注局限。
