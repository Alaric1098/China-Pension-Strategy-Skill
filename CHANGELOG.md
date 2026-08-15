# Changelog

本文件记录 `china-pension-strategy` 技能设计和实现的重要变更。时间均为本机时间，格式为 `YYYY-MM-DD HH:mm:ss UTC offset`。

## 0.1.1 - 2026-08-15

- 请求的可选能力未产出时，信封返回 `partial`、写入具名 warning，并在冻结工件及推荐依赖中标记 `PARTIAL`；按 `run_id` 重新渲染时保留该状态。
- 隐私扫描覆盖数字类型的身份证号、银行卡号和手机号，同时保留普通月份、月数等短数字；数字身份证 eval 必须全局阻断且不产生工件。
- 运行清单的 `warnings_count` 与实际 warning 数一致，`duration_ms` 使用单调时钟记录真实耗时，不参与 `run_id` 内容寻址。
- CI 增加 Python 3.14，并新增每周政策到期工作流；发现当前规则临近到期时创建或更新 GitHub Issue，并让定时运行明确失败。
- 默认计算引擎、地区适配器和运行清单版本提升至 `0.1.1`；内容寻址运行 ID 按引擎版本生成新值，`0.1.0` 历史运行保持可重放。
- `0.1.1` 北京 golden 运行 ID：`run-95e2c71f61a9b8510cc4097e9c930d53afb36a4892be154802ac96c4687731e9`。
- 完整门禁：652 项自动化测试、设计文档、设计契约和架构审计通过。

## 2026-08-14

### 历史包与到期门禁区分

- **问题**：`policy_expiry_report.py` 把两个故意过期的历史包（广州/深圳 2024 医疗，各报
  包级+规则级 2 行）与"该更新却没更新"的现行包（广州医疗 4 个月、天津补贴 16 个月）混在
  同一 exit 1 门禁，门禁恒红会被无视。
- **方案 A（已批准）**：包记录新增显式 `historical: true` 标记——
  - `schemas/policy-package.schema.json` 新增可选 `historical`（boolean，缺省 false）；
  - `domain/policy.py` 的 `PolicyPackage` 与 `json_policy_repository.build_package`
    读取该字段（`historical: bool = False`）；
  - 广州/深圳 2024 历史包加 `"historical": true` + content_digest 重算；
  - `scripts/policy_expiry_report.py`：历史包单列 `[HISTORICAL]`（包级+规则级都列，
    便于审计），**不计入退出码**；退出码语义改为"仅非历史（现行）包/规则到期"；
  - 新增 `--packages-dir` 参数使测试可指向临时目录。
- **测试**：`tests/test_expiry_report.py`（4 用例：历史不计 exit / 现行到期仍 exit 1 /
  混合只计现行 / 无到期 exit 0）；`test_official_packages.py` 历史包例外断言改用
  `package.historical`。
- **验证**：报告（--as-of 2026-08-14）历史 4 行标 HISTORICAL、现行 2 行仍 EXPIRING_SOON
  → exit 1（广州医疗 4 个月到期是真实风险，仍正确告警）；官方包 206、契约 17、全量
  **642 passed**；北京 run_id 不变；verifier/design-contracts 门禁保持通过。

### 深圳 2024-2025 历史期医疗费率落地（任务 D 补齐）

- 来源已取得：深府办规〔2023〕5号（深圳市人民政府办公厅，2023-11-27 成文/2023-12-05 公开，
  **2024-01-01 施行**，有效期至 2026-12-31）第 8 条"灵活就业人员缴费费率下调为 7%"；
  `sz-medical-restore-2026` 确认降费政策实施期限至 2025-12-31、2026-01-01 起恢复 8%。
- 新增来源记录 `policy-data/sources/sz-medical-cut-2023.json` + `references/regions/shenzhen.md`
  来源章节 + `source-digests.json` 同步；`shenzhen.md` 的 sz-medical-restore-2026 章节更新
  （7% 期间由"未建模"改为"历史包建模"）并重算 digest。
- 新增历史包 `policy-data/packages/shenzhen-flex-medical-2024.json`（费率 0.07，effective
  2024-01-01~2025-12-31，6000×7%=420.00），与广州 2024-2025 历史包（6.5%）对齐；
  `test_official_packages.py` 历史包例外断言扩展至深圳包。
- 验证：规则评估 420.00 正确；官方包 206、全量 **638 passed**；北京 run_id 不变；
  深圳当前时点 run_id 因来源正文更新（7% 期间状态变更）而更新，属内容寻址的预期行为。
- 边界：完整历史时点（2024）CLI 分析仍受限于该时点其他规则缺失（如养老基数包
  effective_from 2025-07-01），属既有范围边界；历史包本身规则与 digest 均已验证。

### 校验器误判修复 + 四项遗留

- **任务 A（校验器）**：`verify_design_docs.py` 敏感扫描重构——正则提取为 `SENSITIVE_PATTERN` / `scan_sensitive()`；"标签+值"类要求值形后缀（4+ 字母/汉字）且禁止标签后跟标签（负向前瞻）；扫描前迭代剥离围栏与行内代码片段并清除孤立反引号；元提及字段名（`校验码：` 等）不再误判，真实身份证/流水号仍命中；新增 `tests/test_doc_verification.py`（12 用例）；校验器退出码恢复 0。
- **任务 E（到期监控扩到规则级）**：`scripts/policy_expiry_report.py` 扫描规则级 `effective_to`（包级保留）；`analyze.py` 时效提示扩到规则级（仅本次实际用到规则）；`guangzhou-flex-medical-contribution` 设 `effective_to: 2026-12-31`（穗医保规字〔2022〕1号 有效期）；同类排查结论：无其他规则需要标注（粤人社规〔2026〕14号/〔2025〕50号 无对应规则，50号有效期已在 references 记录）。
- **任务 C-1（基数越界告警）**：新增 `_base_limits_warnings()`——申报基数低于/高于养老或医疗上下限时产出非阻断警告（`CONTRIBUTION_BASE_BELOW_FLOOR` 等），数值与 run_id 不变（警告只进信封不进 analysis.json）；新增 `tests/application/test_base_limits_warning.py`（8 用例）+ `docs/computation-and-reliability.md` 告警语义章节。C-2（真正钳制）按计划**暂缓**。
- **任务 D（历史期费率）**：新增 `policy-data/packages/guangzhou-flex-medical-2024.json`（0.065，2024-03-01~2025-12-31，来源 gz-medical-cut-2024），历史包按 as-of 日期选择、不适用于当前时点；`test_official_packages.py` 增加历史包例外断言。深圳 7% 历史期缺原始降费文件，按计划不建。
- **任务 B（失业费率）**：定点复查 2026 年度失业保险基准费率——国家延续文件（人社部发〔2024〕40号 1%）止于 2025-12-31，2026 年度 gov.cn 原文未取得；按"无可核验当期数值不进规则包"纪律**不建规则**，验收条件与复查记录写入 `references/regions/guangdong.md`（含自愿参保 + `unemployment_enrolled` 事实 + 基数口径）。
- 门禁：`verify_design_docs.py` exit 0；`test_design_contracts.py` 11 passed；`audit_architecture.py --gaps` 通过；官方包 200、契约 17、全量 **632 passed**；北京 run_id 不变。

### 广深灵活就业医疗费率补齐（任务 1-B）

- 按已批准范围完成只读来源调研，并将可核验规则落包。
- **来源突破**：此前判定"不可核验"的广深医保费率，改由市级规范性文件与政府令取得可核验 gov.cn 文本，未使用图片附件路径——粤医保规〔2022〕2号 不再是必需来源。
- 广州：新增 `gz-medical-rate-2022`（穗医保规字〔2022〕1号，灵活就业按缴费基数 8%，2022-12-01 施行、有效期至 2026-12-31）与 `gz-medical-cut-2024`（2024-02-29 阶段性降为 6.5%，有效期至 2025-12-31）；据此 `guangzhou-flex-medical-contribution` 费率 0.08、effective_from 2026-01-01（阶段性降费到期后恢复）。
- 深圳：新增 `sz-medical-rate-358`（深圳市人民政府令第358号《深圳市医疗保障办法》第九条，灵活就业参加一档、按缴费基数 8% 全额缴纳）与 `sz-medical-restore-2026`（市医保局 2025-12-29 公告，2026-01-01 起 7% 恢复 8%，2026 年度医保基数下限 6727、上限 33633）；`shenzhen-flex-medical-contribution` 费率 0.08、effective_from 2026-01-01，二档费率 0.02 与医保基数上下限作为参数记录。
- 失业保险：新增证据 `gd-flex-unemployment-2025`（粤人社规〔2025〕50号《广东省灵活就业人员参加失业保险办法》，2026-01-01 施行、有效期 2 年、试点含广深、自愿参保、费率指向"国家和省规定的基准费率"）。1% 基准费率的现行依据文件有效期均止于 2025-12-31，**2026 年度基准费率无可核验原文** → 按纪律不建规则，广深 `monthly_unemployment_contribution` 维持未覆盖（按 0 计），仅入证据档案。
- 双时态修正：两包 `transaction_from` 随新来源检索时间提升至 2026-08-14T12:00:00Z（新证据进入包即为新包版本），`tests/policy/test_official_packages.py` 的 `AS_KNOWN_AT` 与两城夹具 `created_at` 同步；其余地区包与北京 run_id 不受影响。
- 输出校验：广州 6000 基数 → 养老 1200.00 + 医疗 480.00 = 1680.00；深圳 5000 基数 → 养老 1000.00 + 医疗 400.00 = 1400.00；北京 run_id `run-a7440a1a...` 不变；全量 606 passed。

### 六城灵活就业医疗费率补齐（任务 1-A）

- 按已批准范围补齐六城医疗费率；来源全部为可核验 gov.cn 文本。
- **来源调研结论**：天津官方确认"灵活就业参保个人不缴纳失业保险"（tj.gov.cn 留言选登），失业险在多数城市不适用（北京例外，上海已建模不含失业），故本阶段只补医疗费率。
- 新增 6 条来源记录（`policy-data/sources/{tj,cq,hz,cd,wh,nj}-medical-rate-*.json`）+ 对应 `references/regions/*.md` 章节 + `source-digests.json` 同步。
- 直辖市单层包增补医疗规则：`tianjin-flex-employment`（8.5%×基数，津医保局税务局 2026-03-09 通知）、`chongqing-flex-employment`（一档固定月额 256.25，渝医保发〔2024〕47号；二档 563.75 备选参数）。
- 省份层城市新增城市层医疗包：`hangzhou-flex-medical`（9.5%，杭医保〔2022〕41号）、`chengdu-flex-medical`（9.5% 含大病补充，成医保办〔2025〕17号+问答）、`wuhan-flex-medical`（6%，武汉市医保局问答）、`nanjing-flex-medical`（8%，南京市发布会，2023-04-01 起）；对应适配器 `policy_queries` 增加城市层 contribution 查询。
- 输出校验：杭州 5000→475.00、成都→475.00、武汉→300.00、南京→400.00、天津→442.00、重庆→256.25；北京 run_id 不变；官方包 194、契约 17、全量 606 通过。
- `tests/adapters/test_regions.py` 省份层查询结构断言更新为"省份层养老 + 城市层医疗"双层。

### 计发月数表核验修正（任务 2）

- 用福建省政府公报文本版（zfgb.fj.gov.cn，国发〔2005〕38号全文）核验 31 行计发月数表：仅 age=47 存在偏差（包内 207，官方 208），已修正 `national-pension-benefit.json` 两处（decision_row + 测试向量）。
- 新增来源 `guofa-2005-38-text-fj`（reference 章节 + source 记录 + digest）；gov.cn 原附件为图片，文本版作为可核验替代。

### 一线城市支持（上海、广州、深圳）

- 新增地区路由：`person-input.schema.json` 增加可选 `region` 属性（beijing/shanghai/guangzhou/shenzhen，缺省 beijing，向后兼容，既有夹具 run_id 不变）；`adapters/regions/__init__.py` 建立 `create_region_adapter` 工厂；CLI `analyze` 按输入 region 路由（`entrypoints/cli/main.py`）。
- 新增三城区域适配器：`adapters/regions/{shanghai,guangzhou,shenzhen}.py`（CN-31/CN-4401/CN-4403），镜像北京适配器的事实映射，不含业务计算。
- 新增证据档案：`references/regions/{shanghai,guangdong,guangzhou,shenzhen}.md` 与 12 条 `policy-data/sources/*.json`（沪人社规〔2023〕5号与 2024 补充通知、上海 2025 基数上下限 37302/7460、上海补贴 50% 且当前 1107.6 元/月、粤人社规〔2026〕14号 养老 20%、粤人社发〔2025〕32号 广东基数 27549/广州 5510/其他 4775、粤人社规〔2021〕12号 补贴 2/3、深圳促进就业困难人员再就业补贴办法 2/3 且不超 600 元/月）；`source-digests.json` 扩至 21 条，摘要由参考章节正文 SHA-256 推导并由测试重算验证。
- 新增 6 个政策规则包：`policy-data/packages/{shanghai,guangzhou,shenzhen}-{flex-employment,flex-subsidy}.json`，全部数值出自上述来源；上海覆盖养老 20%/医疗 11%（不含失业），广州/深圳覆盖养老 20% 与补贴（医疗/失业费率待官方数值核验后补入）。
- 引擎兼容异险种地区：`application/calculate_months.py` 的 `monthly_contributions` 将医疗/失业输出改为可选（缺失按 0.00），养老保持必填；`tests/domain/test_calculation.py` 对应用例更新。
- 新增三城评估夹具 `evals/fixtures/golden-{shanghai,guangzhou,shenzhen}-flex-2026.json` 与 `evals/evals.json` 三个 success 用例（共 11 例）；`tests/adapters/test_regions.py` 覆盖 schema/工厂/路由/未知地区。
- `tests/policy/test_official_packages.py` 的 `REFERENCE_FILES` 改为扫描全部 `references/regions/*.md`（56 项通过）。
- 三城 `analyze` 端到端成功（provenance 含 `cn-pension/<city>/...` 包）；北京 golden run_id 不变（`run-a7440a1a...759d59`）。

### 二线城市与省份覆盖（浙江/四川/湖北/江苏 + 杭州/成都/武汉/南京 + 天津/重庆）

- 新增 6 个地区适配器（省份层三查询模式：national + 省份缴费 + 城市补贴；直辖市两层合一）与 person-input schema region 枚举扩展（10 城）。
- 新增 11 条来源记录（浙人社发〔2025〕52号、川人社办发〔2025〕39号、湖北省 2025 通知、江苏 2025 基数通知、天津/重庆 2025 基数通知、国发〔2005〕38号 灵活就业 20% 国家费率、成都补贴 70%、南京补贴 2/3+1/2 等）与 6 个省/直辖市 reference 文件；source-digests.json 扩至 31 条。
- 新增 7 个规则包：6 省/直辖市缴费包（基数上下限 + 养老 20%）+ 成都补贴包（70%、60 个月期限）；南京补贴标准已核验但期限/资格未全，按纪律标记 pending（能力为部分能力）。
- 新增 6 城评估夹具与 evals.json 用例（共 17 例）；六城 analyze 端到端成功。
- 契约/包测试通过（official packages 98 passed）；北京与一线城市 run_id 不变。

### 待遇测算与延迟退休（PENSION_ESTIMATION / RETIREMENT_AGE）

- 新增引擎运算符 FLOOR_DIVIDE/POWER（复利与延迟退休表达式前置）。
- 新增证据档案 11 条（延迟退休决定/弹性办法、国办发〔2019〕13号、北京计发基数 2024/2025、计发月数表、记账利率 2.62% 等；registry 47 条）。
- 新增规则包：national/beijing pension-benefit（延迟退休 3 规则、计发月数表 31 行、基础/账户增长/个人账户/记账利率公式、北京 c-ping 表、过渡性养老金公式）。
- 新增 domain/retirement.py 退休年龄推导与 domain/benefit.py、application/estimate_pension.py（纯函数编排）。
- 集成：PENSION_ESTIMATION 能力、pension fact 映射、条件性 input_digest（既有 run_id 不变）、markdown「Pension Estimation」章节。
- 新增夹具 golden-beijing-benefit-2038 / partial-beijing-benefit（evals 19 例）；全量 558 passed。

### SKILL.md 技能打磨

- 触发描述双语化：frontmatter `description` 保留 8 个英文触发域关键词（pension/contribution/retirement/gap/flexible/subsidy/regional/strategy），新增中文触发词（养老/社保/缴费/缺口/灵活就业/补贴/北京/权益单）；新增契约用例 `test_trigger_description_covers_mandatory_chinese_domains` 锁定中文关键词防回归。
- 新增 `## 工作流` 章节：读输入与预检（consent/分级/目的/保留期/分析模式）→ 先扫描后分析 → 运行 analyze 并核对信封（status/warnings/provenance/artifact_ref）→ 渲染与汇报（只转述 CLI 数值）→ 说明边界与待核验清单；禁止内联计算、复制敏感标识符或假装支持未实现能力。
- 新增 `## 前置条件与自检` 章节：可编辑安装、规则包位置（`policy-data/packages/`）、运行契约自检后再分析；不写死 Python 小版本号以符合契约测试的无金额字面量约束。
- CLI 文档补齐 `analyze` 的 `--schema`/`--engine` 参数。
- 更新 `README.md`：状态行去掉易碎的具体测试数量；门禁统计按实测刷新（398 个测试、26 个端到端用例、8 处 Hypothesis 属性测试）。
- 契约测试（`tests/e2e/test_skill_contract.py`，16 用例升级为 17）通过；沙箱内 tmp_path 用例以手动黄金路径兜底，正常终端需全量复跑。

## 2026-08-11

### Task 12 Agent 技能与黄金评估

- 新增 `SKILL.md`：技能级契约——frontmatter（`name: china-pension-strategy` 与触发描述，覆盖养老分析、缴费记录、退休缺口、灵活就业、补贴时点、地区规则与策略比较）；隐私工作流（分析前先扫描，`BLOCK` 阻断身份证号/社保号/银行卡号/校验码/查询流水号，`REDACT` 脱敏手机号/金额/地址/姓名，`ALLOW/REDACT/BLOCK` 决策模型，无 `BLOCK` 值才允许分析）；CLI 命令（`validate`/`analyze`/`render`/`cleanup` 与稳定退出码 0–8）；输出处理（版本化工具信封 stdout、`runs/<run_id>/analysis.json` 与 `manifest.json` 原子落盘、Markdown 与 JSON 共享单一事实源、内容寻址可重放）；`LOCAL_MVP` 约束（仅 `MVP_REVIEWED` 包、`PRODUCTION` 未实现）；免责声明（不替代经办机构资格认定/退休审批，办理前用最新官方规则并向经办机构核验）。技能内不内联任何政策数字（无百分比、无补贴比例、无金额字面量）。
- 新增 `evals/fixtures/*.json`（8 个合成夹具）与 `evals/evals.json`（评估清单）：golden 完整北京灵活就业案例、部分能力（缺补贴事实仍完成分析）、隐私阻断（社保号 → 退出码 5 且零工件）、隐私脱敏（手机号 → 警告且不泄漏到存储结果）、记录冲突（聚合 181 对明细 → UNRESOLVED 冲突保留）、未知资格（缺困难认定事实仍保守完成）、政策版本缺失（输入早于全部包事务时间 → 安全失败退出码 1）、字节一致重放（与 golden 相同 `run_id`）。
- 新增 `tests/e2e/test_skill_contract.py`（16 个用例）：frontmatter 名称与描述、触发关键词覆盖、四个 CLI 命令、隐私工作流先于分析、无内联政策计算（禁 `%`/补贴比例/金额字面量）、输出处理（信封/`analysis-output`/`analysis.json`/`manifest.json`）、`LOCAL_MVP`/`MVP_REVIEWED`/`PRODUCTION` 约束、免责声明、无样例敏感标识符、eval 清单合法且夹具齐全、8 类必需模式覆盖、各夹具退出码与清单一致、阻断零工件、脱敏不泄漏、重放同一 `run_id`、golden 全链路（analyze → 信封 → `analysis.json`/`manifest.json` → Markdown 与 JSON 渲染 → cleanup 删除并写删除清单）。
- 黄金案例全链路执行：`evals/fixtures/golden-beijing-flex-2026.json` 通过 CLI 完成 analyze、落盘 JSON/清单与 Markdown 渲染，推荐场景 `continue`、`validation_status: passed`、确定性重放得到相同 `run_id`。
- 修复 Windows 平台瞬时文件锁：`FileRunRepository._write_atomic` 的 `os.replace` 在被反病毒/索引短暂占用新建的兄弟文件时偶发 `PermissionError`（E2E 复现），新增最多 10 次、间隔 50ms 的重试，压力探针 20/20 通过。
- 更新 `README.md`：状态改为北京 `LOCAL_MVP` 已实现；技能目录更新为实际仓库布局（`src/`、`policy-data/`、`schemas/`、`evals/`、`tests/`）；测试与评估记录实际门禁（390 个测试、6 个属性不变量、3 个双时态重放、25 个端到端用例）与完整验证命令；阶段一标记完成。
- 修复后全套件 390 个测试通过；`python test_design_contracts.py` 11 项契约、`python verify_design_docs.py` 文档验证、`python audit_architecture.py --gaps` 架构缺口 0 全部通过。

### Task 11 政策仓库、地区映射、报告与 CLI 适配器

- 新增 `adapters/policies/json_policy_repository.py`：按 `policy-package.schema.json` 校验包、独立重算 `content_digest`（摘要不一致即拒绝）、转换为领域包；`list_packages` 对目录缺失或无 `*.json` 文件抛出 `PackageDirectoryError`；仅提供 schema/摘要/双时态/工程审核均通过的 `MVP_REVIEWED` 包。
- 新增 `adapters/regions/beijing.py`：`BeijingRegionAdapter` 将人员输入映射为规范的 `PolicyQuery`（全国最低缴费年限基线、北京灵活就业缴费、北京就业困难人员补贴三组），事实按 `fact_id` 对齐输入、仅编码来源支持的映射，未知区域/方案抛出 `RegionMappingError`（稳定错误码），不包含任何业务计算。
- 新增 `adapters/reporting/json_renderer.py`：确定性工具信封（`build_envelope`，`data` 仅含 `run_id`/`status: VALIDATED`/`artifact_ref`，warnings 为 `{code,message,related_refs}` 消息对象，provenance 为 `package@version:digest` 列表），`EnvelopeValidator`/`OutputValidator` 分别按 `tool-envelope.schema.json` 与 `analysis-output.schema.json` 校验，失败抛出 `EnvelopeSchemaError`/`OutputValidationError`（安全失败，无裸异常）。
- 新增 `adapters/reporting/markdown_renderer.py`：从运行与已验证输出生成确定性 Markdown 报告（对账、情景对比表格、推荐与局限），纯渲染无重算。
- 新增 `entrypoints/cli/main.py`：组合根仅装配适配器与用例，无业务逻辑；命令 `validate`/`analyze`/`render`/`cleanup`，稳定退出码 0–8（成功/意外失败/用法/输入无效/政策无效/隐私阻断/渲染失败/运行未找到/清理失败），所有失败走 `CliError` 安全边界，不打印堆栈。
- `analyze` 将原始 schema 合法输出原子写入 `runs/<run_id>/analysis.json`，清单补充 `expires_at`（来自输入的保留期限）后原子重写，信封打印到 stdout；`render` 按 run_id 重新加载运行与已验证输出后渲染 JSON 信封或 Markdown；`cleanup` 依据清单 `expires_at`/`deletion_status` 判定过期并通过 `RetentionManager` 删除工件、在 `runs/manifests/` 原子写入删除清单。
- 修复 junction/importer 问题：测试侧 `ROOT` 由 `parents[3]` 修正为 `parents[2]`；`json_policy_repository.py`/`json_input.py` 路径基准改为 `os.path.realpath` 计算，保证 pytest 与直接运行解析到的包根一致。
- 重新创建此前未落盘的 Task 11 文件（`adapters/reporting/*`、`adapters/regions/beijing.py`、`entrypoints/cli/main.py` 及 `__init__.py`）；按真实 API 修正 `AuditLog.append`、`PersonInputLoader.load`、`PrivacyScanner.redact_record`、`RetentionManager.is_expired/delete_artifacts` 的调用；重新创建缺失的 `schemas/analysis-output.schema.json`（运行时输出形状，`schema_version` 常量 2.0.0）。
- 新增 `tests/adapters/test_policy_repository.py`（10 个用例）：schema 校验、摘要重算与失配拒绝、目录/文件错误、规则层篡改检测（翻转布尔值保持 schema 合法）；`tests/adapters/test_reporting.py`（9 个用例）：信封确定性、provenance、双 schema 校验、输出拒绝、Markdown 表格与推荐渲染。
- 新增 `tests/e2e/test_cli.py`（9 个端到端用例，真实子进程驱动 CLI）：happy path 信封与工件落盘、validate、政策无效退出码 4、输入无效退出码 3、隐私阻断退出码 5 且不产生工件、隐私脱敏警告且存储结果不泄漏手机号、按 run_id 渲染 Markdown/JSON、cleanup 删除过期工件并写入删除清单（保留未过期）、schema 合法但运行期除零的策略安全失败退出码 1。
- 修复后全套件 374 个测试通过。

### Task 10 输入、隐私、保留与审计适配器

- 新增 `adapters/input/json_input.py`：`PersonInputLoader` 按 person-input schema 加载并校验人员输入（schema 版本、`LOCAL_MVP`/`PRODUCTION` 分析模式、`S1-INTERNAL`/`S2-CONFIDENTIAL` 分级、目的常量、consent_id、`expires_at`、删除状态、`required_for` 能力、标量事实），错误统一为带稳定错误码的 `InputError`。
- 新增 `adapters/privacy/scanner.py`：确定性 `PrivacyScanner`，`ALLOW/REDACT/BLOCK` 三态扫描（身份证件带校验和验证、社保号、银行卡号、查询流水号、验证码、文件路径为 BLOCK；手机号、金额、地址、姓名、长自由文本为 REDACT），`scan_record` 返回带键路径的发现项，`redact_record` 返回 `(ScanDecision, 脱敏副本)`，原因字符串永不包含敏感值本身。
- 新增 `adapters/persistence/retention.py`：`RetentionManager` 检查 `expires_at`/删除状态过期、`flag_expired` 标记、`delete_artifacts` 原子删除并在 `manifests/` 写入删除清单（临时兄弟文件 + `os.replace`，失败路径清理临时文件，POSIX 上收紧权限 0o600）。
- 新增 `adapters/audit/jsonl_audit.py`：追加式 JSONL 审计日志，`AuditLog.append` 自动脱敏敏感字段（身份证/社保号/查询单号等模式）并附加 UTC 时间戳后逐行落盘。
- 新增 `tests/adapters/test_privacy.py`（19 个用例，含输入加载器）：schema 与 consent/分级元数据、禁止字段与值、安全错误与脱敏日志、确定性三态决策、字段名与文本模式全覆盖；`tests/adapters/test_retention.py`（10 个用例，含审计）：过期判定、删除清单、权限、成功与失败路径的临时文件清理。

### Task 9 不可变运行、端口与本地存储

- 新增 `domain/run.py`：冻结不可变 `AnalysisRun`（运行身份、组件/适配器版本、策略规则集引用、输入/假设/目标/输出/工件摘要、验证套件与状态、评审状态），合法状态迁移（`MVP_REVIEWED` 禁止 `PUBLISHED`），`from_manifest`/`to_manifest` 与 `warnings_count`、`unresolved_conflicts_count`。
- 新增 `ports/outbound/run_repository.py` 与 `ports/outbound/clock.py`：`RunRepository` Protocol（保存/加载/存在）与 `Clock` Protocol、`SystemClock` 实现。
- 新增 `application/manifest_validation.py` 与 `application/output_validation.py`：清单语义校验（`ManifestSemanticValidationError`）与输出文档语义校验（`OutputSemanticValidationError`），作为清单/输出落盘与读取的唯一事实源。
- 新增 `application/analyze.py`：编排用例 `analyze(request, policy_repository, run_repository, clock)`，幂等运行身份（内容寻址）、`AnalysisResult` 携带运行、输出、情景与推荐，输出版本常量 2.0.0。
- 新增 `adapters/persistence/file_run_repository.py`：每个运行一个目录的清单存储，临时兄弟文件 + `os.replace` 原子写，加载时重验语义、`run_id` 与内容摘要一致性，损坏/缺失分别抛 `ManifestInvalidError`/`RunNotFoundError` 等稳定端口错误。
- 新增 `tests/application/test_analysis_run.py`（21 个用例）、`test_manifest_validation.py`（11 个用例）、`test_output_validation.py`（20 个用例）、`test_analyze.py`（11 个用例）、`tests/adapters/test_file_run_repository.py`（9 个用例）：状态机、冻结身份、幂等 run_id、原子发布、清单完整性、摘要失配与中断写入。

### Task 8 情景与推荐引擎

- 新增 `domain/scenario.py`：停止/继续/补贴时机行动序列、包含式视界、各险种独立现金流（养老/医疗/失业/补贴/净流出/累计）、阈值/区间/情景假设、目标、局限、失效条件与阻断能力排除的领域模型。
- 新增 `application/analyze_scenarios.py` 与 `application/recommend.py`：确定性月度情景生成与排名，输出 `AnalysisOutput` 情景比较与推荐。
- 新增 `tests/domain/test_scenarios.py`（14 个用例）：行动序列、视界、现金流、假设、目标、局限、失效条件、阻断能力排除；属性测试覆盖累计现金流求和与确定性排名。

### Task 7 缺口、缴费与补贴引擎

- 新增 `domain/calculation.py` 与 `domain/eligibility.py`：最低月数计划、剩余缺口、缴费额、政策指定舍入、补贴金额/起止月、`ELIGIBLE/INELIGIBLE/UNKNOWN` 三值资格模型与条件证据、能力状态。
- 新增 `application/calculate_months.py`：确定性规则求值器（`evaluate_expression`、条件匹配、决策表行匹配、参数解析、`canonical_scalar` 类型化标量），对已解析的规则/参数/决策表求值，核心不分支北京字面量；除零等非法求值抛 `DomainValidationError`。
- 涵盖 59/60/61 个月补贴边界与年度参数过渡；`assess_subsidy` 对资格、期限（整数校验）、起算偏移、月度金额汇总与起止月推导。
- 新增 `tests/domain/test_calculation.py`（24 个用例）与 `tests/domain/test_eligibility.py`（32 个用例）；属性：新增一个已缴月不会增大缺口、更高补贴不会增加净流出、相同输入产生相同规范值。

### Task 6 缴费记录对账

- 新增 `domain/reconciliation.py`：重复月、竞争性的聚合与明细合计、分离方案、未解决冲突保留的领域模型，确认月数与缺口由月度集合推导。
- 新增 `application/reconcile_records.py`：纯对账与编排，保留未解决冲突供下游呈现。
- 新增 `tests/domain/test_reconciliation.py`（17 个用例）：179/180/181 个月边界、200 个月对 17 年零 1 个月案例、重复月与方案分离；属性：新增一个唯一有效缴费月不会减少确认月数。

### Task 5 官方政策研究与规则包

- 新增 `policy-data/sources/*.json`（9 条）与 `policy-data/source-digests.json`：来源记录（URL、发文机关、权威层级、文号、发布日期、抓取时间、定位符、来源摘要）与参考文件 `references/national-rules.md`、`references/regions/beijing.md` 的 `## 来源：` 小节一一对应，摘要在构造与测试两处独立重算核对。
- 新增三个 `MVP_REVIEWED`、`LOCAL_MVP`、本地专用规则包：`national-enterprise-pension.json`（全国企业职工基本养老保险，含最低缴费年限 180 个月与基础养老金基数规则）、`beijing-flex-employment.json`（北京灵活就业参保与 2025 年度缴费基数/费额，含 `beijing-subsidy-duration` 决策表依赖的基数参数）、`beijing-flex-subsidy.json`（就业困难人员灵活就业社保补贴：资格、期限、起算与养老/医疗/失业三项月度补贴金额，含决策表规则）。
- 仅编码来源支持的规则：补贴金额按「先缴后补、各险种最低缴费额的 2/3」并受 2025 基数下限约束；缴费基数/费额与补贴金额的当前值全部标记为「无授权来源支持的费率调整」依赖参数或 DECIMAL 字面量，未推断存储任何未来源支持的规则。
- 包级 `content_digest` 覆盖除自身外的全部字段，来源 `source_digest` 对参考文件对应小节重新规范化后一致；包与来源记录跨文件一致（同一来源在多个包中逐字段相同）。
- 新增 `tests/policy/test_official_packages.py`（20 个用例）：schema 校验、领域构造与双时态适用性、内容摘要重算、来源记录与包 provenance 一致、来源摘要与参考小节一致、规则来源解析与测试向量完整性。
- 修复后全套件 221 个测试通过。

### Task 4 质量评审复审修复（评审闭环）

- 补上 `:` 分隔符禁令的 schema 侧约束：`policy-package.schema.json` 新增 `plainId`（`^[^:]+$`），用于 `package_id` 与 `rule_id`，schema 与领域对象对带 `:` 的包/规则标识符同样拒绝。
- 语义规范化中 `Decimal` 先 `normalize()` 再进入签名，`Decimal("1")` 与 `Decimal("1.0")` 不再被拆成不同签名（消除误报歧义）。
- 补齐测试缺口：限定自覆盖拒绝（包级）、`rule_id`/`package_id` 禁含 `:`（领域与 schema 两层）、等值不同精度 `Decimal` 共享签名。
- 移除 `tests/contracts/test_schemas.py` 中重复的决策表行数断言块。
- 修复后全套件 201 个测试通过。

### Task 4 质量评审修复（限定规则身份与可执行类型安全）

- 新增可执行类型安全：输入声明 `value_type`/`required`，条件类型必须匹配输入并检查运算符与类型组合，表达式（`LITERAL`/`REFERENCE`/`EXPRESSION`）校验类型一致、引用解析、操作数元数与运算符类型限制，参数改为类型化声明，例外效果限定为 `EXCLUDE`/`OVERRIDE`，测试向量输入与预期按声明类型校验。
- 新增双时态因果：`PolicyPackage.transaction_from` 不得早于来源抓取时间、工程审核时间或生产批准发布时间，构造时拒绝违反因果顺序的包并修正测试夹具时间线。
- 新增决策表资源上限 `MAX_DECISION_TABLE_COMBINATIONS = 100_000`，枚举前校验笛卡尔积大小；`policy-package.schema.json` 增加输入数、域大小和行数基数限制。
- 新增限定规则身份 `package_id:rule_id`：解析器竞争报告使用限定身份，裸覆盖引用限定在声明包内，支持 `package_id:rule_id` 显式跨包覆盖，禁止 `:` 出现在规则与包标识符中。
- 语义规范化加入标量类型标签，消除 Python `True == 1` 造成的不同参数/条件签名折叠。
- 修复后全套件 197 个测试通过。

### Task 3 领域值与资格

- 新增 `domain/values.py`：封闭的 `YearMonth`（拒绝非法/非整数月份）、首尾月份均计入的包含式月数差、`Money`/`Decimal` 按 `CNY-half-up-v1` 政策指定舍入、金额幂的十次方约束与币种一致性（`CurrencyMismatchError`）、幂等内容摘要常量。
- 新增 `domain/facts.py`：不可变事实引用（集合禁止重复、全字段冻结、`fact_id` 全局唯一）与 `required_for` 能力声明。
- 新增 `domain/eligibility.py`：`ELIGIBLE`/`INELIGIBLE`/`UNKNOWN` 三值资格模型、条件状态 `SATISFIED`/`FAILED`/`UNVERIFIED`、能力状态 `AVAILABLE`/`PARTIAL`/`BLOCKED` 与条件证据推导；存在未核验条件且无失败条件时不得返回 `ELIGIBLE`。
- 新增 `domain/errors.py`：统一的 `DomainValidationError` 与稳定错误码。
- 新增 `tests/domain/test_values.py`（21 个用例）与 `tests/domain/test_eligibility.py`（32 个用例）：封闭月份、包含式计数、舍入与精度、冻结不可变、能力状态与资格三值推导；Hypothesis 属性覆盖月份计数单调性与资格状态推导。

### Task 2 治理与 JSON 契约

- 新增 `schemas/person-input.schema.json`：`LOCAL_MVP`/`PRODUCTION` 分析模式、`S1-INTERNAL`/`S2-CONFIDENTIAL` 分级、目的常量、`consent_id`、`expires_at` 与删除状态、七项能力枚举、`required_for` 标量事实（禁止对象值）。
- 新增 `schemas/policy-package.schema.json`：可执行规则包——类型化输入/条件/结果、`LITERAL`/`REFERENCE`/`EXPRESSION` 表达式、决策表行、测试向量、工程审核与生产批准、来源、双时态与 `content_digest`，全部 `additionalProperties: false`。
- 新增 `schemas/tool-envelope.schema.json`（1.0.0）：`success`/`partial`/`error` 状态与相互约束、`data` 仅允许 null 或引用字段（run_id/status/result_ref/manifest_ref/artifact_ref/deletion_manifest_ref）、结构化消息 `{code,message,related_refs}`、provenance 摘要与 metrics。
- 新增 `schemas/run-manifest.schema.json`（不可变运行清单 v2）：run_id、双时态、组件/适配器版本、摘要、验证套件、评审状态与发布状态。
- 扩展 `docs/schemas/analysis-output.schema.json`（设计契约单一事实源）：能力/资格评估、记录冲突、政策歧义、假设（六种建模模式：证据支持概率/用户假设/专家假设/纯情景/阈值/区间，含事件定义、分布、来源日期、人群、审批人与失效日期）、双时态快照与推荐依赖。
- 新增 `tests/contracts/test_schemas.py`（30 个用例）：`LOCAL_MVP`、`MVP_REVIEWED`、缴费缺口、政策证据、类型化月度现金流、情景结果、推荐限制与清单摘要的 schema 校验，合法/非法实例均用 jsonschema 验证。

### Task 1 包与测试框架

- 新增 `pyproject.toml`：`[tool.setuptools.packages.find] where=["src"]`，运行时依赖 `jsonschema`，测试依赖 `pytest`/`hypothesis`，pytest `testpaths=["tests"]`。
- 新增包骨架：`src/china_pension_strategy/` 及 `domain/`、`application/`、`ports/inbound/`、`ports/outbound/`、`adapters/`、`entrypoints/cli/` 全部 `__init__.py`。
- 新增 `tests/architecture/test_dependencies.py`（6 个用例）：扫描并解析每个源码模块，强制领域纯净——`domain` 不得导入 application/ports/adapters/entrypoints、Pydantic、文件系统、HTTP 或 CLI；静态扫描捕捉向外的 application/port 导入与数据库/进程/网络/SDK/`subprocess` 违规，禁止在源码中使用（Pydantic、boto3、openai、socket、sqlite3、subprocess 等）。

## 2026-08-11

### 设计契约闭环

- 将输入必需性改为按能力声明的 `required_for`，并定义 `AVAILABLE`、`PARTIAL` 和 `BLOCKED`。
- 增加 `ELIGIBLE`、`INELIGIBLE` 和 `UNKNOWN` 三值资格模型及条件证据。
- 扩充权威输出schema，纳入双时态、能力、资格、记录冲突、政策歧义、概率建模模式和推荐依赖。
- 移除核心引擎中的通用补贴公式，明确由规则解析器选择规则包、确定性求值器执行规则、地区提供器仅负责管辖映射。
- 将有效日期和已知时间加入幂等身份，增加隐私边界动作矩阵和无可信概率时的阈值/范围/情景回退。
- 将首版门禁提高为至少25个确定性案例、5个属性不变量、3个双时态重放案例和8个端到端eval。
- 新增设计契约单元测试，并把架构审计从纯关键词覆盖扩展为结构化契约检查。

## 2026-08-11 12:01:07 -06:00

### 技能架构Autoresearch

- 完成10轮技能架构迭代，机械覆盖指标由21/100提升至100/100，剩余缺口由19降至0。
- 明确确定性计算内核与非确定性LLM边界，并建立Clean/Hexagonal分层及依赖规则。
- 新增养老领域限界上下文、制度与管辖角色、值对象、不变量和冲突语义。
- 新增可执行政策规则包、双时态政策版本、不可变分析运行、入站/出站端口、状态机和稳定错误码。
- 新增统一工具信封、`analysis-output.schema.json`单一事实源、提示注入防护、隐私威胁模型和保留期限。
- 新增概率及独立性治理、幂等与内容寻址缓存、可观测性、运行清单、语义化版本、兼容性矩阵和发布门禁。
- 新增 `audit_architecture.py` 和 `verify_design_docs.py`，最终检查通过11个Markdown文件、15个README目录链接、9个本地链接及全部JSON示例。

## 2026-08-11 11:16:19 -06:00

### 技能设计README

- 新增项目级 `README.md`，文件生成时间为2026-08-11 11:16:05 -06:00。
- 将项目定位为中国基本养老保险的证据驱动计算与续保策略技能，并明确仍处于架构设计阶段。
- 记录全国规则核心、北京地区适配器、月度计算、缴费记录对账、政策证据等级、现金流比较和动态策略的总体架构。
- 定义建议的 `china-pension-strategy` 技能目录、触发范围、数据流、输入模型、政策模型、计算引擎和标准输出。
- 增加隐私脱敏要求、合成测试数据要求、无技能基线对照评估方案和五阶段实施路线。
- 已检查 `README.md`，未发现身份证号、校验码、查询流水号或社会保障号码。
