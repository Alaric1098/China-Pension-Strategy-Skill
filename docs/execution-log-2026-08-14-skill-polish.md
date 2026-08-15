# 执行记录：SKILL.md 技能打磨与一线城市支持

执行依据：`docs/plans/2026-08-14-skill-polish.md`（12 个任务）
开始时间：2026-08-14（本机）
执行方式：executing-plans（本会话内联执行；无 git 仓库，无提交步骤）

## 任务状态总览

| 任务 | 内容 | 状态 | 修改文件 | 验证 |
|---|---|---|---|---|
| 1 | 触发描述双语化 + 契约测试锁定 | ✅ 完成 | SKILL.md、tests/e2e/test_skill_contract.py | 契约 11 通过 + 手动黄金路径 |
| 2 | 「工作流」章节 | ✅ 完成 | SKILL.md | 契约通过 |
| 3 | 「前置条件与自检」章节 | ✅ 完成 | SKILL.md | 契约通过 |
| 4 | CLI 参数补齐 | ✅ 完成 | SKILL.md | 契约通过 |
| 5 | README/CHANGELOG 同步 | ✅ 完成 | README.md、CHANGELOG.md | 计数实测 398 |
| 6 | 全量验证（打磨部分） | ✅ 完成 | - | 契约约束全检通过 |
| 7 | 地区路由机制 | ✅ 完成 | schemas/person-input.schema.json、adapters/regions/__init__.py、cli/main.py、tests/adapters/test_regions.py | 6 passed + 手动路由 |
| 8 | 一线城市证据档案 | ✅ 完成 | references/regions/{shanghai,guangdong,guangzhou,shenzhen}.md、policy-data/sources/*（12 条）、source-digests.json（21 条）、tests/policy/test_official_packages.py | 官方包测试 56 passed |
| 9 | 各城市政策规则包 | ✅ 完成 | policy-data/packages/{shanghai,guangzhou,shenzhen}-{flex-employment,flex-subsidy}.json（6 个） | 56 passed + 端到端 |
| 10 | 各城市区域适配器 | ✅ 完成 | adapters/regions/{shanghai,guangzhou,shenzhen}.py、factory 注册、engine 兼容异险种（calculate_months.py） | 三城 analyze 成功 |
| 11 | 夹具、契约与 SKILL/文档同步 | ✅ 完成 | evals/fixtures/golden-{shanghai,guangzhou,shenzhen}-*.json、evals/evals.json（11 例）、SKILL.md、README.md、CHANGELOG.md | 契约通过 |
| 12 | 全量验证与北京不动性回归 | ✅ 完成 | - | 393 passed + 49 沙箱 tmp 错误；北京 run_id 不变 |

## 逐任务明细

（Task 1-7 明细见上文；以下为 Task 8-12 追加记录）

### Task 8: 一线城市证据档案（✅ 完成）

- **时间**：2026-08-14
- **调研方式**：web_search 定位来源 + Python urllib 经 Jina Reader 抓取官方页面原文（沙箱封锁 pwsh/curl 外网，但 Python 可用）
- **新建 references**：`references/regions/shanghai.md`（6 来源）、`guangdong.md`（3 来源，广州/深圳共用）、`guangzhou.md`（1 来源）、`shenzhen.md`（2 来源），每来源含 URL/文号/权威级别/原文摘录/工程解释
- **新建 12 条来源记录**：`policy-data/sources/{sh-*,gd-*,gz-*,sz-*}.json`；`source-digests.json` 扩至 21 条（摘要=参考章节正文规范化 SHA-256，测试重算验证）
- **关键核验数值**（均出自 gov.cn 原文）：
  - 上海：养老 24%→20%（沪人社规〔2023〕5号+2024-02 补充通知）、医疗 11%；2025 基数上下限 37302/7460（rsj.sh.gov.cn，2025-07-01 起）；补贴=基数下限应缴社保费 50%（当前 1107.6 元/月）、期限 3 年/距退休 5 年内延至退休
  - 广东：养老 20%（粤人社规〔2026〕14号，2026-05-01 施行）；2025 基数上限 27549、广州/省直下限 5510、其他地区 4775（粤人社发〔2025〕32号）；补贴=实际缴费额 2/3、最长 3 年（粤人社规〔2021〕12号，河源转发）
  - 深圳：补贴=实际缴费额 2/3 且每月不超 600 元、3 年（sz.gov.cn 公报《深圳市促进就业困难人员再就业补贴办法》）；个体工商户经营者以灵活就业身份参加养老/失业/一档医疗（sz.gov.cn 问答）
- **未核验项**（按纪律不入包）：广州/深圳医疗与失业缴费费率（粤医保规〔2022〕2号正文为图片附件无法提取）；深圳 2025 基数下限按广东"其他地区 4775"口径并在工程解释注明

### Task 9: 各城市政策规则包（✅ 完成）

- **新建 6 包**：`shanghai/guangzhou/shenzhen` × `flex-employment/flex-subsidy`；包 ID `cn-pension/<city>/...`，jurisdiction CN-31/CN-4401/CN-4403
- 上海：基数 7460-37302、养老 0.20、医疗 0.11（无失业——上海参保范围仅养老+医疗）；补贴 1107.60（50% 口径当期标准）
- 广州：基数 5510-27549、养老 0.20；补贴 734.67（2/3）
- 深圳：基数 4775-27549、养老 0.20；补贴 600.00（2/3 且封顶 600）
- 每包含 rules（PARAMETER_TABLE/POLICY_RULE/DECISION_TABLE）、parameters、test_vectors、engineering_review、provenance（来源记录一致）、content_digest
- **验证**：`tests/policy/test_official_packages.py` 56 passed（schema/领域构造/摘要/provenance/来源支持/向量测试）

### Task 10: 各城市区域适配器（✅ 完成）

- **新建** `adapters/regions/{shanghai,guangzhou,shenzhen}.py`（beijing.py 常量克隆）；工厂 `_REGISTRY` 注册四城，移除 PENDING_REGIONS
- **引擎兼容异险种**：`application/calculate_months.py` 的 `monthly_contributions` 将医疗/失业输出改为可选（缺失按 0.00），养老保持必填（上海无失业、广深医疗费率待补的场景得以运行）；`tests/domain/test_calculation.py` 对应更新
- **验证**：三城 `analyze` 端到端 success（provenance 含 `cn-pension/<city>/...` 包）；上海渲染数值正确（养老 1400=20%×7000、医疗 770=11%×7000、失业 0）

### Task 11: 夹具、契约与 SKILL/文档同步（✅ 完成）

- **新建夹具** `evals/fixtures/golden-{shanghai,guangzhou,shenzhen}-flex-2026.json`（region 字段 + 各城基数 8000/6000/5000）；`evals/evals.json` 新增 3 个 success 用例（共 11）
- **SKILL.md**：何时使用扩为一线城市；LOCAL_MVP 边界更新（北上广深包+region 路由+医疗/失业待核验说明）；CLI 节补 region 说明（无金额/比例字面量，符合契约）
- **README/CHANGELOG**：状态行改为一线城市；CHANGELOG 新增 `### 一线城市支持`
- **验证**：契约非 tmp 11 passed；三城夹具 analyze 全部 success

### Task 12: 全量验证与北京不动性回归（✅ 完成）

- **北京不动性**：golden-beijing run_id 仍为 `run-a7440a1a294cbdb2464f039f6a61e96d496cc1d5aa88c594c66b879602375d59` ✓
- **三城黄金路径**：analyze→render（含 `## Recommendation`）→cleanup 全部退出 0
- **全套件**：393 passed + 49 沙箱 tmp_path 环境错误（无真实失败；正常终端需全量复跑）
- **清理**：`.research-*`、`.city-test-*`、`runs-*` 已删除；沙箱遗留空目录 `eval-tmp2`/`eval-tmp3` 待人工清理

## 沙箱能力建设（追加任务，2026-08-14）

- **诊断**：pytest 的 tmpdir 插件以 `mode=0o700` 创建 basetemp 根与编号子目录；本机 Windows + Python 3.14 下显式 POSIX mode 创建的目录获得限制性 DACL，`os.scandir` 立即 `PermissionError (WinError 5)` → 任何使用 tmp_path 的测试都会污染 basetemp 根，且被污染目录无法读写删。
- **建设**：新建根 `conftest.py`——`pytest_configure` 在 Windows 上剥离 `os.mkdir`/`os.makedirs` 的 mode 参数；对陈旧被污染的 %TEMP% temproot 自动重定向到工作区 `.pytest-temproot`。
- **验证**：修复前全量 393 passed + 49 沙箱 tmp_path 错误 → 修复后默认配置 **442 passed，退出 0**（`tests/e2e/test_skill_contract.py` 17/17 通过）。
- **文档**：`docs/sandbox-capabilities.md`（根因、A/B 实验、能力矩阵、用法、遗留建议）。
- **遗留**：历史被污染目录（%TEMP% 会话目录、工作区 `.bt-*` 等 0o700 目录）ACL 无法会话内删除，建议用户手动清理；新会话 %TEMP% 全新，无影响。

## 继续核验：待补补贴项（2026-08-14 完成）

- **杭州**（✅ 核验）：萧山区政府页面——灵活就业社保补贴 = 实际缴纳养老+医疗的 50%（2023-02-01 起，单独参保亦 50%）。新建 hz-subsidy-standard 来源与 `hangzhou-flex-subsidy` 包（金额 498.60=4986×20%×50%，养老部分；期限按通用口径推断并标注）。
- **武汉**（✅ 核验）：武昌区政府问答——补贴 673.19 元/月（养老 448.80+医疗 224.39，2022-10 口径，随基数调整）；**期限核验**：初次核定男 55/女 45+ 最长 60 个月、其他 36 个月。新建 wh-subsidy-standard 来源与 `wuhan-flex-subsidy` 包（60/36 双档期限，全部有原文支撑）。
- **重庆**（✅ 核验）：沙坪坝区转发市通知——养老按基数下限缴费 2/3 + 医疗按最低档 2/3；期限最长 3 年、距退休不足 5 年可延。新建 cq-subsidy-standard 来源与 `chongqing-flex-subsidy` 包（金额 587.20=4404×20%×2/3，养老部分；医疗最低档未核验标注）。
- **南京**（✅ 核验+补包）：鼓楼区页面确认资格（经认定就业困难人员+就业登记+足额缴费）与标准（最低基数 2/3+超出 1/2）；期限按通用口径推断并标注。恢复 nj-subsidy-standard 来源与 `nanjing-flex-subsidy` 包（660.27=4952×20%×2/3）。
- **天津**（✅ 已核验，2026-08-14 追加）：hrss.tj.gov.cn 原文页对自动化抓取与用户浏览器均不可读（403/空白），经 esnai 法规库镜像（law.esnai.cn/mview/219790）取得《关于完善就业困难人员灵活就业社会保险补贴政策有关问题的通知》全文（2024-12-31 发文、2025-01-01 实施）：养老 600 元/月、医疗 200 元/月、同时参保 800 元/月；每人仅可申领一次，期限最长 3 年、距退休不足 5 年可延至退休，审核通过次月起计。新建 tj-subsidy-standard 来源（gov.cn 权威 URL + 镜像交叉核验注明）与 `tianjin-flex-subsidy` 包（600.00 养老口径，参数含 200/800）。至此 10 个地区补贴全部落地或核验。
- **验证**：official packages 122 passed；全量 509 passed（+24）；北京 `run-a7440a1a...`、上海 `run-9e28e452...` run_id 不变；六城 analyze 全部 success。
- **说明**：场景净额的补贴列为 0 为既有引擎行为（北京同款夹具同样为 0，补贴评估经规则/向量测试验证），非本次回归。

## 能力扩展 Phase 1：延迟退休引擎（2026-08-14 进行中）

- **计划**：`docs/plans/2026-08-14-pension-capability-expansion.md`（三阶段：P0 待遇测算+延迟退休 / P1 五险·多地区·补缴·城乡居保 / P2 看板·流程·利率·敏感性·个人养老金）。
- **已完成（Task 2 延迟退休引擎）**：
  - 来源 2 条：retire-delay-decision-2024（全国人大决定，legalinfo.moj.gov.cn，https 修正）、retire-elastic-method-2025（人社部等弹性办法答记者问，gov.cn）；注册表 38 条。
  - references/national-rules.md 新增两节（节奏表、弹性提前/延迟、2030 最低年限原文摘录+工程解释）。
  - 规则包 `national-delayed-retirement.json`：pace 拆为 3 条 POLICY_RULE（男60→4/63、女50→2/55、女55→4/58，避免决策表全组合覆盖限制）+ 弹性窗口规则；141 项包/域测试通过。
  - `src/china_pension_strategy/domain/retirement.py`：`statutory_retirement` 纯函数（出生年月+性别+原法定 → 法定退休年月/延迟月数/弹性窗口），pace 表镜像规则包；7 项单元测试通过（含 2025 首档零延迟、每 4/2 个月 +1、63/55/58 封顶、弹性窗口下限不破原法定）。
  - schema：`requested_capabilities` 增加 `RETIREMENT_AGE`。
- **验证**：全量 528 passed（+13）；北京 `run-a7440a1a...` 不变。
- **待续**：Task 2 的适配器/输出管线接线（birth_year_month/gender fact 映射 → RETIREMENT_AGE 输出）与 Task 1 待遇测算（执行既有 benefit-estimation 计划）。

## 能力扩展 Phase 3（P2）进度：Task 10 敏感性分析（SENSITIVITY_ANALYSIS，2026-08-14 完成）

- **实现**：schema SENSITIVITY_ANALYSIS；analyze 重构共享 `_run_estimate`（待遇测算与敏感性共用）；`_sensitivity_output` 对 sensitivity_index_tiers 逐档调用 estimate_pension → 输出各档平均指数/基础养老金/月待遇合计；adapter 解析 JSON 串 tiers；output schema 加 sensitivity_analysis。
- **夹具**：golden-sensitivity-analysis-2026（evals 24 例）；矩阵：指数 0.6→4049.70、1.0→4772.64、1.5→5676.32、2.0→6579.99、3.0→8387.34（多缴多得单调）。
- **验证**：全量 576 passed；北京 run_id 不变。
- **说明**：敏感性维度当前为平均缴费指数（对应缴费档次）；退休时点/补贴时机维度可后续扩展。


## 任务 1-A & 任务 2 执行（计划 2026-08-14-rates-payment-months.md，已批准）

### 任务 2：计发月数表核验（完成）
- 用福建公报文本版核验 31 行表：仅 age=47 偏差（包 207 vs 官方 208）→ 修正两处 + 新增 guofa-2005-38-text-fj 来源；官方包 194/契约 17/全量 582 通过（修正前），北京 run_id 不变。

### 任务 1-A：六城医疗费率补齐（完成）
- 调研：全部费率可核验 gov.cn 文本；天津官方确认灵活就业不缴失业保险 → 失业险不适用于多数城市（北京例外），本阶段仅补医疗。
- 直辖市：tianjin（8.5%）、chongqing（一档 256.25/月）包内加规则 + provenance。
- 省份层城市：新建 hangzhou/chengdu/wuhan/nanjing flex-medical 包（9.5%/9.5%/6%/8%）+ 适配器加城市层 contribution 查询。
- 验证：输出 杭州 475.00 / 成都 475.00 / 武汉 300.00 / 南京 400.00 / 天津 442.00 / 重庆 256.25；北京 run_id run-a7440a1a... 不变；全量 606 passed（+24）。
- 测试更新：test_regions 省份层查询结构断言改为双层（省份养老 + 城市医疗）。

### 遗留（任务 1-B，待用户提供材料）
- 广深医疗/失业费率（粤医保规〔2022〕2号 反爬图片）：沙箱无法核验，需用户提供文件内容或人工核验后补包。
- **后续更新（2026-08-14 同日）**：任务 1-B 已执行，医疗费率改由市级来源核验完成，见下节；失业费率仍待 2026 年度基准费率原文。

## 任务 1-B 执行（计划 2026-08-14-task1b-gd-medical-unemployment.md，审批选项 a）

### Step 0 来源调研（只读，L6 图片路径未启用）
- 命中 L1/L2：广州 8%（穗医保规字〔2022〕1号 二（二），gz.gov.cn）+ 阶段性 6.5% 至 2025-12-31（2024-02-29 通知）；深圳 8%（政府令第358号 第九条，sz.gov.cn）+ 2026-01-01 由 7% 恢复 8%、医保基数 6727/33633（市医保局 2025-12-29 温馨提示）。
- **原阻塞源作废**：粤医保规〔2022〕2号（图片附件）不再是必需来源——广深各有市级可核验文本，无需图片转录，scratchpad 二进制探针未使用，仓库未新增能力代码。
- 失业：粤人社规〔2025〕50号《广东省灵活就业人员参加失业保险办法》（2026-01-01 施行、有效期 2 年、试点含广深、自愿参保）已核验；但办法只指向"国家和省规定的基准费率"，1% 的依据文件（粤人社函〔2023〕133号 转发、国家延续文件）有效期止于 2025-12-31，**2026 年度基准费率无可核验原文** → 按纪律不建规则，只入证据档案。

### Step 1 落包
- 新增 4 条来源记录（gz-medical-rate-2022、gz-medical-cut-2024、sz-medical-rate-358、sz-medical-restore-2026）+ 3 个 references 文件章节更新；`gd-flex-unemployment-2025` 按 tj-unemployment-not-applicable 先例只建章节+摘要登记（无来源文件、不进 provenance）；source-digests.json 59→64。
- 两包各加一条医疗规则（0.08×基数，effective_from 2026-01-01）；深圳包参数记录二档 0.02 与医保基数 6727/33633。**适配器无改动**（城市层单包，既有查询已覆盖）。
- **双时态修正**：新来源 retrieved_at 为真实抓取时间 2026-08-14T09:00Z，触发领域校验"transaction_from 不得早于来源检索时间" → 两包 transaction_from 提升至 2026-08-14T12:00Z（新证据入包=新包版本），同步 `AS_KNOWN_AT` 常量与两城夹具 created_at。未回填假的 retrieved_at。
- **验证**：官方包+区域+契约 220 passed；全量 606 passed（无回归）；广州 6000→1200+480=1680、深圳 5000→1000+400=1400；失业两城 0.00；北京 run_id `run-a7440a1a...` 不变；policy_expiry_report 与基线一致（仅天津 EXPIRING_SOON）。
- **记录**：CHANGELOG、`docs/change-record-2026-08-14-gd-rates.md`。
- **遗留**：广深失业费率（待 2026 年度基准费率原文，补时须一并建模失业基数口径）；医保基数与养老基数口径差异未做钳制（已标注）；2024-2025 阶段性降费期间未建模。


## 校验器误判修复 + 四项遗留执行（计划 2026-08-14-verifier-and-leftovers.md，用户批准"执行修改"）

### 任务 A：校验器敏感扫描误判修复（完成）
- verify_design_docs.py 重构：SENSITIVE_PATTERN/scan_sensitive() 可测试化；标签+值要求值形后缀（4+ 字符）且负向前瞻禁止标签后跟标签；迭代剥离围栏+行内代码并清除孤立反引号。
- 计划文件第 19 行畸形嵌套反引号（双反引号包单反引号）修正为规范写法。
- tests/test_doc_verification.py 12 用例全绿；校验器 exit 0。

### 任务 E：到期监控扩到规则级（完成）
- policy_expiry_report.py 扫描规则级 effective_to；analyze.py 时效提示扩到规则级。
- guangzhou-flex-medical-contribution effective_to=2026-12-31（穗医保规字〔2022〕1号 有效期）；报告显示 4 个月后到期；广州 analyze limitations 出现规则级提示。
- 同类排查：无其他规则需要标注。

### 任务 C-1：基数越界告警（完成；C-2 按计划暂缓）
- _base_limits_warnings()：越界（养老/医疗上下限）产出非阻断警告，数值与 run_id 不变；深圳 5000<6727 触发 CONTRIBUTION_BASE_BELOW_MEDICAL_FLOOR。
- tests/application/test_base_limits_warning.py 8 用例；docs/computation-and-reliability.md 记录告警语义。

### 任务 D：广州历史期费率（完成）
- 引擎确认：同包同字段多版本会 duplicate 冲突 → 采用独立历史包 guangzhou-flex-medical-2024.json（0.065，2024-03-01~2025-12-31）。
- 历史包按 as_of 日期选择（2024-06-01 + known-now 组合），不适用于当前时点；test_official_packages 增加例外断言。
- 深圳历史期（7%）缺原始降费文件，不建（计划决策）。

### 任务 B：广深失业费率（只做复查+验收条件，完成）
- 定点复查 2026 年度基准费率：人社部发〔2024〕40号（1%）止于 2025-12-31；2026 年度 gov.cn 原文未取得 → 不建规则。
- 验收条件 + 复查记录写入 references/regions/guangdong.md；gd-flex-unemployment-2025 digest 重算同步。

### 最终验证
- verify_design_docs.py exit 0；test_design_contracts 11 passed；audit_architecture --gaps 通过。
- 官方包 200、契约 17、全量 **632 passed**（基线 606 + 26）。
- 北京 run_id run-a7440a1a...759d59 不变。


## 深圳 2024-2025 历史期医疗费率落地（用户："深圳的来源已有，请对齐并落地"）

- **来源确认**：深府办规〔2023〕5号（fgw.sz.gov.cn 政府信息公开规章库）第 8 条"灵活就业人员
  缴费费率下调为 7%"，2024-01-01 施行、有效期至 2026-12-31；sz-medical-restore-2026 确认
  降费至 2025-12-31、2026-01-01 恢复 8%。深圳历史期 = 2024-01-01~2025-12-31，费率 7%。
- **落地**：新增 sz-medical-cut-2023 来源记录 + shenzhen.md 来源章节 + digest 同步；
  shenzhen.md 的 restore 章节更新（7% 期间"未建模"→"历史包建模"）并重算 digest（此变化
  导致深圳当前包 content_digest 与 run_id 更新，内容寻址预期行为；北京不受影响）。
- **新增历史包** shenzhen-flex-medical-2024.json（0.07，2024-01-01~2025-12-31），与广州
  历史包对齐；test_official_packages.py 历史包例外断言扩展。
- **验证**：规则评估 6000×7%=420.00；官方包 206；全量 **638 passed**；北京 run_id 不变。
- **边界**：完整 2024 历史时点 CLI 分析受限于该时点其他规则缺失（养老基数包
  effective_from 2025-07-01），属既有范围边界；历史包规则与 digest 已验证。


## 历史包与到期门禁区分（计划 2026-08-14-historical-flag.md，用户批准）

- 问题：报告把故意过期的历史包（广州/深圳 2024 医疗）与应更新的现行包混在 exit 1 门禁，
  门禁恒红会被无视。
- 落地（方案 A：显式 historical 标记）：
  - schema 新增可选 historical（boolean 缺省 false）；domain PolicyPackage +
    build_package 读取；两历史包加 historical:true + digest 重算；
  - policy_expiry_report.py：历史包单列 [HISTORICAL] 不计退出码；退出码语义改为
    "仅现行包到期"；新增 --packages-dir 参数；
  - tests/test_expiry_report.py 4 用例；test_official_packages 例外断言改用 package.historical。
- 验证：报告历史 4 行 HISTORICAL、现行 2 行 EXPIRING_SOON → exit 1 正确（广州医疗 4 个月
  仍告警）；官方包 206；全量 642 passed（+4）；北京 run_id 不变；门禁保持通过。

## 治理规则（2026-08-14 起生效）

- **任何修改必须先写计划（docs/plans/）→ 用户审核批准 → 才可执行**；批准前不做任何修改（含回滚）。
- 例外处理：本会话中已先行应用的 SKILL.md 技能化重构，已补办计划 `docs/plans/2026-08-14-skill-centric-revision.md` 待审批（批准保留 / 不批准回滚）。

## SKILL.md 技能化重构（✅ 已批准 2026-08-14）

- 触发表化"何时使用"（用户语言 → 能力 → 输出，含补缴/个人养老金税优触发）；description 触发导向重写；移除引擎内部细节；修复冗余；契约 17/17 通过。
- 用户批准保留；计划归档于 `docs/plans/2026-08-14-skill-centric-revision.md`。

## 能力扩展收尾（2026-08-14）

- **Task 8 申报办理流程指南**：SKILL.md 新增「申报办理指引」章节（参保登记渠道、补贴申请"先缴后补"、发放时点；全部来自既有来源，非用户能力面）。
- **Task 9 记账利率与余额**：确认已由 PENSION_ESTIMATION 覆盖（project_stored_balance 用 record_interest_rate 0.0262 投影账户余额），无需独立能力。
- **五险费率补齐**：粤医保规〔2022〕2号 原文为图片附件（反爬），本会话无法核验；已记录来源线索与内容要点（灵活就业医保费率口径），待用户提供文件内容或人工浏览器核验后补入广深/新城市医疗/失业费率。
- **最终门禁**：契约 17 passed；全量 582 passed；北京 run_id `run-a7440a1a...` 不变；evals 23 例。
- **Phase 1/2/3 状态**：P0 延迟退休引擎+待遇测算 ✅；P1 补缴/城乡居民养老/多地区比较与转移接续 ✅（五险费率待外部文件）；P3 敏感性/个人养老金税优 ✅、时效看板经范围修正转为维护脚本+局限提示 ✅、申报流程指南 ✅。

## 范围修正：POLICY_EXPIRY_WATCH 移除（2026-08-14）

- **决策**（用户质疑"政策时效看板是否超出 skill 范围"，采纳）：规则包失效提醒是**数据治理/维护者关注点**，不属于用户可请求的养老金能力；以用户能力形式暴露会污染 capability 枚举与输出 schema、泄漏内部包元数据。
- **A：维护脚本** `scripts/policy_expiry_report.py`——扫描 policy-data/packages，列出已失效/临近失效（默认 18 个月）包，退出码 1 作维护门禁；实测输出 tianjin flex-subsidy EXPIRING_SOON（16 个月）。
- **B：结论局限提示**——analyze 的 recommendation 在所用关键规则包临近失效时追加一行"Policy version ... expires ...; conclusions rest on that rule version"，把时效意识以用户语言表达。
- **撤销**：schema capability 枚举、analysis-output schema、analyze `_policy_expiry_watch_output`、夹具 golden-policy-expiry-watch-2026 与 evals 用例（24→23）。
- **保留**：天津补贴包 effective_to 2027-12-31（真实政策元数据，供脚本与局限提示使用）。
- **验证**：全量 582 passed；北京 run_id 不变；SKILL.md 增加维护门禁说明。

## 能力扩展 Phase 3（P2）进度：Task 7 政策时效看板（POLICY_EXPIRY_WATCH，2026-08-14 完成）

- **实现**：schema POLICY_EXPIRY_WATCH；analyze `_policy_expiry_watch_output`（扫描仓库全部包：effective_to 已过→EXPIRED；18 个月内→EXPIRING_SOON+剩余月数）；output schema 加 policy_expiry_watch。
- **数据**：为天津补贴包设置 effective_to 2027-12-31（通知失效期，来源 tj-subsidy-standard）。
- **夹具**：golden-policy-expiry-watch-2026（evals 23 例）；输出 tianjin flex-subsidy EXPIRING_SOON、16 个月剩余。
- **验证**：全量 576 passed；北京 run_id 不变。
- **说明**：当前仅天津补贴包有明确失效期；其余包 effective_to 为 null（无已知失效）→ 看板如实不报。后续新年度基数/费率包上线时以 effective_to 标注即被看板捕获。

## 能力扩展 Phase 2（P1）进度：Task 4 多地区比较与转移接续（CROSS_REGION_COMPARISON，2026-08-14 完成）

- **证据**：国办发〔2009〕66号（北京政府网全文）第六条待遇领取地四层规则（关系在户籍地→户籍地；所在地满10年→该地；不满10年→上一个满10年参保地；各地均不满10年→户籍地）。registry 50 条。
- **规则包** `national-pension-place.json`（topic pension_place）：national-pension-place DECISION_TABLE（8 行全组合覆盖：HOME/CURRENT/PRIOR_OVER10/HOME_FALLBACK 四类判定）。
- **应用层** `application/cross_region.py`：determine_pension_place（按 66 号文评估判定规则，输出 place_rule/place/region_months）、compare_monthly_contributions（按 jurisdiction→rules 映射求值各区养老月缴费）。
- **能力接线**：schema CROSS_REGION_COMPARISON；北京适配器 fact 映射（home_region/current_region/comparison_regions 逗号串/region_contribution_months JSON 串，因 schema fact.value 仅标量）+ pension_place 查询；analyze 从仓库直接取外区缴费包（避免污染主查询集/场景引擎重复输出冲突）；output schema 加 cross_region_comparison。
- **夹具**：golden-cross-region-2026（evals 22 例）；输出 pension_place=beijing（CURRENT_REGION，满10年）、region_comparison beijing/chengdu/shanghai 均 1400（7000×20%）。
- **验证**：official packages 164 passed；全量 576 passed（+6）；北京 run_id 不变。
- **说明**：省份层城市（成都等）比较用省本级辖区（CN-51 等）；比较能力当前接在北京适配器。

## 能力扩展 Phase 2（P1）进度：Task 6 城乡居民养老保险（RESIDENTS_PENSION，2026-08-14 完成）

- **证据**：国发〔2014〕8号（gov.cn 原文：12 档 100-2000 元/年、政府补贴最低档 ≥30 元/500 元及以上 ≥60 元、个人账户÷139）；全国基础养老金最低标准 2024 提标至 123 元/月（凤县 gov，原 103 +20）。registry 49 条。
- **规则包** `national-residents-pension.json`（scheme/topic residents_pension，CN）：residents-gov-subsidy（DECISION_TABLE 补贴档）、residents-basic-pension（123.00）、residents-account-formula（÷139）。
- **能力接线**：schema RESIDENTS_PENSION；北京适配器条件性查询 + residents_account_balance fact；analyze 输出 residents_pension（basic/account/total）；output schema 加可选字段。
- **夹具**：golden-residents-pension-2026（evals 21 例）；输出 basic 123.00、account 359.71（50000÷139）、total 482.71。
- **验证**：official packages 158 passed；全量 570 passed（+6）；北京 run_id 不变。
- **说明**：居民养老为独立 scheme；其他地区适配器暂未接该查询（部分能力）。

## 能力扩展 Phase 2（P1）进度：Task 5 补缴政策（BACK_PAYMENT，2026-08-14 完成）

- **规则包** `national-back-payment.json`（jurisdiction CN，topic back_payment，来源 retire-delay-decision-2024）：
  - national-minimum-years-schedule：2030 起最低缴费年限 15→20 年每年 +6 个月（180→240 封顶），DECISION_TABLE 覆盖 2020-2040（2029 前 180 个月；输出字段 minimum_months_at_year 避免与最低年限需求规则冲突）。
  - national-insufficient-years-options：达龄年限不足可延长缴费或一次性缴费（决定第二条）。
- **能力接线**：schema capability 加 BACK_PAYMENT；北京适配器条件性追加 back_payment 查询（CN）；analyze 输出 back_payment 节（minimum_years_schedule + options）；analysis-output schema 加可选 back_payment。
- **夹具**：golden-beijing-back-payment-2026（evals 20 例）；输出 2026→180 个月、years 15.0、options extend/lump。
- **验证**：official packages 152 passed；全量 564 passed（+6）；北京 run_id 不变。
- **说明**：灵活就业不得补缴为地区口径（上海 2023 通知、广东办法第十条，已在 references），BACK_PAYMENT 国家包输出最低年限与不足选项；其他地区适配器暂未接该查询（部分能力）。

## 能力扩展 Phase 1 进度追加：Task 5 集成 + Task 6 夹具/文档/门禁（2026-08-14 完成）

- **Task 5 集成**：
  - person-input schema：capability 枚举加 PENSION_ESTIMATION；analysis-output schema 加可选 pension_estimation。
  - Beijing 适配器：pension fact 映射（birth_year_month/gender_category/total_contribution_months/deemed_years/transition_years_98/average_contribution_index/account_balance（as_of_date→account_as_of_year_month）/interest_rate_override/c_ping_override）；policy_queries 增加 requested_capabilities 参数，PENSION_ESTIMATION 时追加 national+北京 pension 查询（既有 run_id 不变）。
  - analyze：AnalysisRequest 加 pension_inputs/account_as_of_year_month；_pension_estimate_output 编排（benefit rules → estimate_pension → 序列化）；input_digest 条件性含 pension_inputs（仅存在时，避免破坏既有 run_id）。
  - markdown_renderer：「## Pension Estimation」章节（法定退休/计发月数/C_ping/利率/余额投影/三险/合计/假设）；修复渲染非 ASCII（C平→C_ping、→→->）。
  - **端到端**：golden-benefit 夹具 → retirement 2038-11、delay 33、计发月数 119.0、basic 3253.23/account 1157.94/transition 361.47/total 4772.64、stored 137795.45；渲染正常。
- **Task 6**：夹具 golden-beijing-benefit-2038/partial-beijing-benefit（evals 19 例）；SKILL.md（何时使用/边界）、README（状态）、CHANGELOG 更新。
- **验证**：契约+地区 26 passed；全量 558 passed；北京 run_id `run-a7440a1a...` 不变。
- **Phase 1 完成**：延迟退休引擎 + 待遇测算（PENSION_ESTIMATION）全部落地。

## 能力扩展 Phase 1 进度追加：Task 4 领域与应用层（2026-08-14 完成）

- **domain/benefit.py**：冻结数据类 StatutoryRetirement（birth/gender_category/original_statutory_months/delay_months/retirement + age_months）、ProjectionAssumption、PensionEstimate（payment_months/c_ping/stored/三险组成/假设）。
- **application/estimate_pension.py**（纯函数，无硬编码政策数字）：
  - derive_statutory_retirement（按 gender 选延迟规则 → 求值 delay_months → statutory_months 参数 + birth.add_months）
  - payment_months_for_age（计发月数表上下行线性插值，量化为 0.1）
  - c_ping_for_retirement（覆盖优先，否则查北京 c-ping 表；缺行抛错）
  - project_stored_balance（retirement−as_of 月数钳 ≥0 → 账户增长 POWER 公式）
  - estimate_pension（编排：法定退休 → 计发月数 → C平 → 记账利率（覆盖/发布）→ 余额投影 → 基础/个人账户/过渡性/合计）
- **测试**：tests/application/test_estimate_pension.py 9 项（首档零延迟、男 1976 delay 33→2038-11、女 50、整岁/插值计发月数 138.4/194.6/151.4/118.3、C平表与覆盖与缺行报错、余额投影、golden 估算 basic 3253.23/transition 361.47、缺 C平 报错）。
- **偏差记录**：计划公式的延迟 +1 偏移与官方对照表首档不一致，采用 floor 语义（1965-01 男 → 2025-01 零延迟；1976-02 → delay 33、2038-11），测试固定该语义。
- **验证**：全量 558 passed（+9）；北京 run_id 不变。
- **下一步**：Task 5 集成（analysis-output schema 加 pension_estimation、Beijing 适配器 fact 映射 birth_year_month/gender_category/total_contribution_months/deemed_years 等、analyze 编排、markdown 渲染）→ Task 6 夹具/SKILL/门禁。

## 能力扩展 Phase 1 进度追加：Task 1 证据档案 + Task 3 待遇规则包（2026-08-14 完成）

- **Task 1 证据档案**：9 条新来源全部核验并落地（registry 47 条）——guoban-2019-13（60%-300% 基数）、beijing-order-183-2006（个人账户 8%）、beijing-2007-21（计发办法公式）、beijing-2007-31（视同 N同=1992-09-30 前、N实98=1992-10~1998-06、Z实指数）、beijing-2024-16-base（11883）、beijing-2025-13-base（12049）、mohrss-2017-31-interest（记账利率规则，原文反爬未抓取，标注待核验）、jinan-payment-months-2025（60岁1月=138.4/50岁1月=194.6 插值口径）、interest-rate-disclosure-2025（2.62%）。references 相应章节（national-rules.md + regions/beijing.md）完成。
- **Task 3 待遇规则包**：
  - `national-pension-benefit.json`（8 规则）：延迟退休 3 规则（男/女55 步长 4、女50 步长 2，FLOOR_DIVIDE 表达式，首档零延迟语义——计划公式的 ADD(1,…) 判定为偏差，采用与官方对照表一致的 floor 语义并在包内向量固定）；计发月数表 DECISION_TABLE（40-70 岁 31 行）；基础养老金公式；账户增长公式（POWER 复利）；个人账户养老金公式；记账利率 0.0262。
  - `beijing-pension-benefit.json`（2 规则）：c-ping 表（2024=11883/2025=12049）；过渡性养老金公式（G同+G实，transition_rate 参数 0.01，向量 843.43）。
- **验证**：official packages 146 passed；全量 549 passed（+12）；北京 run_id 不变。
- **下一步**：Task 4（domain/benefit.py + application/estimate_pension.py + 测试）→ Task 5（集成：schema 输出/adapter/analyze/renderer）→ Task 6（夹具/SKILL/门禁）。

## 能力扩展 Phase 1 进度追加：Task 2 运算符（2026-08-14 完成）

- **FLOOR_DIVIDE/POWER 运算符**（待遇测算前置）：
  - `domain/policy.py`：`_EXPRESSION_OPERATORS` 增加 FLOOR_DIVIDE/POWER；校验——两者恰两操作数、FLOOR_DIVIDE 要求 INTEGER 结果、POWER 要求 DECIMAL 结果。
  - `application/calculate_months.py`：`_floor_divide`（零除数保护 + 高精度除法后 ROUND_FLOOR，Python // 语义含负数）、`_power`（localcontext prec=40、负指数拒绝、InvalidOperation 安全化）；dispatch 接线。
  - `schemas/policy-package.schema.json`：operator 枚举 + SUBTRACT/DIVIDE/FLOOR_DIVIDE/POWER 恰两操作数约束。
  - 测试：`tests/domain/test_operators.py`（9 项：正/负地板除法、DECIMAL 操作数、零除数、非数值、POWER 复利、负指数、非法操作数）；契约测试将原"POWER 无效示例"改为 MODULO。
- **验证**：127 项（运算符+域+契约）通过；全量 537 passed（+9）；无回归。
- **下一步**：Task 1 待遇测算证据档案（guoban-2019-13、北京计发基数 2024/2025、计发月数表、记账利率等 9 条新来源调研抓取）→ Task 3 规则包。

## 技能第二部分：二线城市与省份覆盖（2026-08-14 完成）

- **批次**：浙江/四川/湖北/江苏省本级缴费包 + 杭州/成都/武汉/南京城市适配器 + 天津/重庆直辖市（共 10 地区）。
- **架构**：省份层三查询模式（national + 省份缴费 CN-XX + 城市补贴 CN-XXXX），直辖市两层合一；person-input schema region 枚举扩至 10 城；适配器工厂注册 6 新类。
- **证据**：11 条新来源（浙人社发〔2025〕52号 25299/4986、川人社办发〔2025〕39号 22938/4588 + 灵活就业 20%、湖北 2025 武汉档 22488/4498、江苏 2025 24762/4952、天津 5124/25620、重庆 22017/4404、国发〔2005〕38号 国家 20% 费率、成都补贴养老+医疗 70% 且 60 个月期限、南京补贴 2/3+1/2）；source-digests.json 扩至 31 条；6 个省/直辖市 reference 文件。
- **规则包**：7 个（6 省/直辖市缴费包 + 成都补贴包）；official packages 98 passed。
- **待核验（部分能力）**：杭州/武汉/天津/重庆补贴标准、南京补贴期限与资格——本会话未能取得 gov.cn 原文（站点 403/超时/JS 渲染），按"无来源不进包"纪律标记 pending；南京补贴标准已记录于 references/regions/jiangsu.md 待后续补包。
- **夹具/文档**：6 城夹具 + evals.json（17 例）；SKILL.md 何时使用/边界/CLI region 说明、README 状态、CHANGELOG 更新。
- **验证**：全量 485 passed（+43）；北京 run_id `run-a7440a1a...` 与上海 `run-9e28e452...` 不变；六城 analyze 全部 success。

## 环境补齐（MCP/技能）

- Exa MCP（mcporter）：**健康**（2 工具）——web_search 的 MCP 通道可用。
- agent-reach CLI：npm 全局安装因沙箱限制（无法写工作区外的 npm 全局目录/缓存）失败；其 Exa 搜索后端已由 mcporter 覆盖，gov.cn 内容抓取由 scripts/webget.py（Python/OpenSSL）承担——调研工具链已闭环。
- node_repl/playwright MCP：沙箱 EPERM（daemon 锁文件），需在非受限环境使用。

## 沙箱能力建设·二：Schannel TLS 修复（2026-08-14 追加）

- **诊断**：Windows 受限环境用最小权限令牌运行命令 → Schannel `AcquireCredentialsHandle` 报 `SEC_E_NO_CREDENTIALS (0x8009030e)` → 所有 Schannel HTTPS 客户端（pwsh IWR/curl/.NET）握手失败；OpenSSL 客户端（Python/Node）正常；提升权限后的 IWR 返回 200（判定实验）。
- **建设**：
  - `scripts/webget.py`：OpenSSL HTTPS 抓取器（`--jina`/`--output`/`--status-only`，强制 UTF-8）
  - `scripts/net.ps1`：`Invoke-DshWebRequest` 包装器，Schannel 失败签名自动回退 webget.py
- **验证**：`Invoke-DshWebRequest 'https://www.gov.cn'` → 62374 字符成功；`-Jina` → 14867 字符成功。
- **文档**：`docs/sandbox-capabilities.md` 新增「Schannel TLS 失败：根因与解决方案」章节。

## 环境与已知限制

- 沙箱封锁子进程外网（pwsh/curl），Python urllib 可用 → 政策原文经 Jina Reader 抓取
- e2e/契约测试的 tmp_path 用例在沙箱内报 PermissionError（环境限制），以手动 CLI 黄金路径兜底
- 广州/深圳医疗与失业费率未核验，MVP 包按未覆盖处理（部分能力），后续补入
- 深圳 2025 基数下限采用广东"其他地区 4775"口径（工程解释注明），待深圳人社局原文确认
