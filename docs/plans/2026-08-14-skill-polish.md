# SKILL.md 技能打磨与一线城市支持 Implementation Plan（触发双语化、工作流、前置条件、文档同步、北上广深地区支持）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. No Git repository, so commit steps are omitted.

**Goal:** 落实 2026-08-14 技能评估的改进——(1) 触发描述加入中文关键词并由契约测试锁定；(2) 新增 agent 工作流编排章节；(3) 新增前置条件与自检章节；(4) 补齐 CLI 参数文档并同步 README/CHANGELOG；(5) 一线城市支持：引入地区路由机制，新增上海、广州、深圳三个地区的证据档案、政策规则包、区域适配器与评估夹具（北京已实现），保持既有北京案例的 run_id 与退出码完全不变。全程保持 `tests/e2e/test_skill_contract.py` 全部通过，且不引入任何内联政策数字。

**Architecture:** 技能本体是仓库根 `SKILL.md`（88 行），其内容受 `tests/e2e/test_skill_contract.py`（16 个用例）契约测试约束。技能打磨部分：frontmatter `description` 重写、正文新增两节（`## 工作流`、`## 前置条件与自检`）、CLI 命令一节一行补齐、README/CHANGELOG 同步，无 Python 源码改动。一线城市部分：当前 CLI 硬编码 `BeijingRegionAdapter`（`entrypoints/cli/main.py:154`），输入 schema 无地区字段；方案是给 `person-input.schema.json` 新增**可选** `region` 属性（enum: beijing/shanghai/guangzhou/shenzhen，缺省 beijing，向后兼容、既有夹具 run_id 不变），在 `adapters/regions/__init__.py` 建立适配器工厂路由，main.py 按 region 选择适配器；每城按既有模式（证据档案 → 规则包 → 适配器 → 夹具 → 契约/SKILL 同步）落地。权限层级 `_AUTHORITY_LEVELS` 已含 `PROVINCIAL_HRSS`/`MUNICIPAL_GOVERNMENT`/`MUNICIPAL_HRSS`，无需扩展。

**Tech Stack:** Markdown（SKILL.md）、Python pytest（契约测试）、README.md / CHANGELOG.md 同步。无 git 仓库，故无提交步骤。

---

## 约束（改动前必读，来自 tests/e2e/test_skill_contract.py）

SKILL.md 全文（含 frontmatter）必须满足，否则契约测试失败：

1. **禁止出现** `%`、字符串 `2/3`、`\b\d+\.\d{2}\b`（金额样式——注意 `3.12` 这类版本号也会命中，前置条件一节不得写具体 Python 小版本号）、17 位身份证、`\d{3}-\d{2}-\d{4}`、`1[3-9]\d{9}`、字符串 `校验码：` 与 `查询流水号：`。
2. **description 必须保留** 8 个英文关键词：`pension` `contribution` `retirement` `gap` `flexible` `subsidy` `regional` `strategy`（`test_trigger_description_covers_mandatory_domains`）。
3. **description 必须是单行**（`parse_frontmatter` 按行切分 `key: value`）。
4. 必须保留既有关键词与表述：`validate`/`analyze`/`render`/`cleanup`、`REDACT`/`BLOCK`、`身份证`/`社保`/`银行卡`、"分析前扫描"（`先.*扫描|扫描.*(后|前).*分析|分析前`）、`envelope`/`analysis-output`/`analysis.json`/`manifest.json`、`LOCAL_MVP`/`MVP_REVIEWED`/`PRODUCTION`、`免责`/`经办机构`/`核验`。
5. 环境提示：本沙箱对 `%TEMP%` 与跨进程目录枚举有限制，e2e 的 `tmp_path` 可能报 `PermissionError`（与代码无关）。请在正常终端运行 pytest；若必须在本沙箱验证，用 `--basetemp` 指向工作区目录并接受其 teardown 限制，另以 Task 6 的手动黄金路径兜底。
6. **一线城市向后兼容**：`person-input.schema.json` 新增的 `region` 属性必须为可选（缺省 `beijing`），不得使既有夹具输入失效；改动后 golden-beijing 的 run_id 必须与改动前一致（内容寻址确定性，由 `test_replay_fixture_yields_identical_run_id` 与人工前后对比共同把关）。

---

### Task 1: 触发描述双语化 + 契约测试锁定

**Files:**
- Modify: `SKILL.md`（第 3 行 frontmatter `description`）
- Modify: `tests/e2e/test_skill_contract.py`（新增 1 个测试函数）
- Test: `tests/e2e/test_skill_contract.py`

**Step 1: 替换 description 为单行双语版本**

将第 3 行整体替换为（保持单行、无换行）：

```text
description: Use when analyzing Chinese basic pension insurance, social-security contribution records, retirement contribution gaps, flexible-employment continuation, pension subsidy timing, regional pension rules, or comparing contribution and retirement strategies in China. 当用户需要计算养老缴费缺口与最低缴费年限、核对社保权益单（明细月数与累计年限不一致）、灵活就业养老/医疗/失业保险缴费、北京就业困难人员社保补贴的资格与申请时机、比较停缴/续缴/补贴方案现金流，或解析国家与北京地区养老金政策时，使用本技能。Runs deterministic, reproducible calculations through the china-pension-strategy CLI and never computes policy values inline.
```

自检：含全部 8 个英文关键词；含中文触发词 养老/社保/缴费/缺口/灵活就业/补贴/北京/权益单；无 `%`、无 `2/3`、无 `\d+\.\d{2}`、无敏感标识符。

**Step 2: 新增中文关键词契约测试**

在 `test_trigger_description_covers_mandatory_domains`（第 52-65 行）之后插入：

```python
def test_trigger_description_covers_mandatory_chinese_domains() -> None:
    frontmatter = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    description = frontmatter["description"]
    for keyword in (
        "养老",
        "社保",
        "缴费",
        "缺口",
        "灵活就业",
        "补贴",
        "北京",
        "权益单",
    ):
        assert keyword in description, f"trigger description misses {keyword!r}"
```

**Step 3: 运行契约测试，期望全部通过（含新增用例）**

```text
python -m pytest tests/e2e/test_skill_contract.py -q
```

Expected: 17 passed（原 16 + 新增 1），无失败。

---

### Task 2: 新增「工作流」章节

**Files:**
- Modify: `SKILL.md`（在隐私与数据边界一节的条目列表之后、`## CLI 命令` 之前插入，即第 36 行与第 38 行之间）
- Test: `tests/e2e/test_skill_contract.py`（回归）

**Step 1: 插入完整章节**

```markdown
## 工作流

接到任务后按以下顺序执行，所有数字一律来自 CLI 输出：

1. **读输入与预检**：确认输入 JSON 携带 `consent_id`、`classification`、`purpose`、`expires_at`、`deletion_status` 与 `analysis_mode`（必须为 `LOCAL_MVP`）。字段缺失或不合规时，先用 `validate` 定位错误，向用户如实报告，不跳过预检。
2. **先扫描后分析**：任何计算前先经隐私扫描。被 `BLOCK` 的输入直接终止并说明原因，不产生任何运行工件；`REDACT` 字段在 warnings 中记录，汇报时如实转述。
3. **运行 analyze**：信封输出到 stdout。核对 `status`（success/partial/error）、`warnings`、`provenance`（规则包版本摘要）与 `data.artifact_ref`；任何非 success 状态都要向用户明确说明。
4. **渲染与汇报**：需要人读的报告用 `render --format markdown`（或 json）生成。汇报只转述信封与报告中的数值，不自行计算、不改写任何数字。
5. **说明边界**：结论附带 LOCAL_MVP 边界、政策版本与免责声明提示；把未解决冲突、`BLOCK`/`REDACT` 项列为待核验清单。

禁止在对话中内联计算政策数值、复制原始身份证号或社会保障号码，或假装支持未实现能力（PRODUCTION 模式、DOCX/PDF 渲染、远程服务、真实权益文件摄取）。
```

自检：无 `%`、无 `2/3`、无 `\d+\.\d{2}`、无敏感标识符；保留 `REDACT`/`BLOCK`、`LOCAL_MVP`/`PRODUCTION` 关键词。

**Step 2: 契约测试回归**

```text
python -m pytest tests/e2e/test_skill_contract.py -q
```

Expected: 17 passed。

---

### Task 3: 新增「前置条件与自检」章节

**Files:**
- Modify: `SKILL.md`（在 `## 何时使用` 的"不应触发"列表之后、`## 隐私与数据边界` 之前插入，即第 23 行与第 25 行之间）
- Test: `tests/e2e/test_skill_contract.py`（回归）

**Step 1: 插入完整章节**

```markdown
## 前置条件与自检

- 本技能依赖仓库内已安装的 `china-pension-strategy` 包（`pip install -e .` 可编辑安装；Python 版本与依赖以 `pyproject.toml` 的 `requires-python` 和 `dependencies` 为准）
- 政策规则包位于 `policy-data/packages/`，随仓库提供；需要时可用 `--packages-dir` 指向其他目录
- 开始分析前先运行契约自检：`python -m pytest tests/e2e/test_skill_contract.py -q`；未通过则先修复环境，不跳过自检直接分析
```

注意：不得写具体 Python 小版本号（如 `3.12` 会命中金额字面量正则）。

**Step 2: 契约测试回归**

```text
python -m pytest tests/e2e/test_skill_contract.py -q
```

Expected: 17 passed。

---

### Task 4: CLI 参数文档补齐（--schema / --engine）

**Files:**
- Modify: `SKILL.md`（`## CLI 命令` 一节中 analyze 行的参数清单）
- Test: `tests/e2e/test_skill_contract.py`（回归）

**Step 1: 替换 analyze 命令行**

原文（第 45 行）：

```text
- `analyze --input FILE --runs-dir DIR [--packages-dir DIR] [--audit FILE]`：扫描、映射地区、解析政策并执行确定性计算；信封打印到 stdout，原始输出与清单原子落盘
```

替换为：

```text
- `analyze --input FILE --runs-dir DIR [--packages-dir DIR] [--audit FILE] [--schema FILE] [--engine VER]`：扫描、映射地区、解析政策并执行确定性计算；信封打印到 stdout，原始输出与清单原子落盘（`--engine` 指定引擎版本，缺省为当前默认版本）
```

**Step 2: 契约测试回归**

```text
python -m pytest tests/e2e/test_skill_contract.py -q
```

Expected: 17 passed。

---

### Task 5: README 与 CHANGELOG 同步

**Files:**
- Modify: `README.md`（第 5 行、第 289 行）
- Modify: `CHANGELOG.md`（新增 `## 2026-08-14` 条目）
- Test: 无（纯文档）

**Step 1: README 第 5 行去掉易碎的数量**

原文：`> 当前状态：北京 `LOCAL_MVP` 已实现——规则包、CLI、隐私/保留/审计适配器、测试与评估全部通过（390 个自动化测试）。`

改为：`> 当前状态：北京 `LOCAL_MVP` 已实现——规则包、CLI、隐私/保留/审计适配器、测试与评估全部通过。`

**Step 2: 实测并刷新 README 第 289 行门禁数量**

在正常终端运行：`python -m pytest -q`，记录实际 `N passed`；对照 `tests/` 下统计确定性案例、Hypothesis 属性不变量、双时态重放与端到端用例的实际数量，将第 289 行中 `390 个自动化测试` 及子计数（25+ 确定性案例、6 个属性不变量、3 个双时态重放、25 个端到端用例）更新为实测值；若子计数与现状不符一并修正。

**Step 3: CHANGELOG 新增条目（仿照既有格式）**

在文件顶部（第 3 行说明之后）新增：

```markdown
## 2026-08-14

### SKILL.md 技能打磨

- 触发描述双语化：frontmatter `description` 保留 8 个英文触发域关键词（pension/contribution/retirement/gap/flexible/subsidy/regional/strategy），新增中文触发词（养老/社保/缴费/缺口/灵活就业/补贴/北京/权益单/停缴/续缴/方案现金流/政策解析）；新增契约用例 `test_trigger_description_covers_mandatory_chinese_domains` 锁定中文关键词防回归。
- 新增 `## 工作流` 章节：读输入与预检（consent/分级/目的/保留期/分析模式）→ 先扫描后分析 → 运行 analyze 并核对信封（status/warnings/provenance/artifact_ref）→ 渲染与汇报（只转述 CLI 数值）→ 说明边界与待核验清单；禁止内联计算、复制敏感标识符或假装支持未实现能力。
- 新增 `## 前置条件与自检` 章节：可编辑安装、规则包位置（`policy-data/packages/`）、运行契约自检后再分析；不写死 Python 小版本号以符合契约测试的无金额字面量约束。
- CLI 文档补齐 `analyze` 的 `--schema`/`--engine` 参数。
- 更新 `README.md`：状态行去掉易碎的具体测试数量；门禁统计按实测刷新。
- 契约测试（`tests/e2e/test_skill_contract.py`，16 用例升级为 17）与全套件全部通过。
```

---

### Task 6: 全量验证

**Files:** 无新增（验证 + 清理）

**Step 1: 契约测试**

```text
python -m pytest tests/e2e/test_skill_contract.py -q
```
Expected: 17 passed。

**Step 2: 全套件（正常终端）**

```text
python -m pytest -q
```
Expected: 全部通过（当前实测 350 个单元/集成 + e2e；沙箱内 e2e 的 tmp_path 受环境限制，以正常终端结果为准）。

**Step 3: 手动黄金路径兜底（覆盖 e2e 核心路径）**

```text
python -m china_pension_strategy.entrypoints.cli.main analyze --input evals/fixtures/golden-beijing-flex-2026.json --runs-dir runs
```
Expected: 退出 0，信封 `schema_version 1.0.0`、`status: success`、provenance 含 3 个规则包摘要。

```text
python -m china_pension_strategy.entrypoints.cli.main render --run-id <上一步 run_id> --runs-dir runs --format markdown
```
Expected: 退出 0，输出含 `## Recommendation` 与 `## Scenario Comparison`。

```text
python -m china_pension_strategy.entrypoints.cli.main cleanup --runs-dir runs --expires-before 2027-01-01T00:00:00Z
```
Expected: 退出 0，写入 `runs/manifests/deletion-*.json`。

```text
python -m china_pension_strategy.entrypoints.cli.main analyze --input evals/fixtures/privacy-block-ssn.json --runs-dir runs-blocked
```
Expected: 退出 5，stderr 含 `privacy scan blocked`。

**Step 4: 清理**

删除本任务产生的 `runs/`、`runs-blocked/` 与任何 `--basetemp` 临时目录；另清理评估遗留的 `.pytest-tmp-eval`、`eval-tmp2`、`eval-tmp3`（若沙箱仍拒绝删除，记录并交由人工清理）。确认 `git` 不可用（非 git 仓库），以文件清单人工核对改动面：`SKILL.md`、`tests/e2e/test_skill_contract.py`、`README.md`、`CHANGELOG.md`。

---

### Task 7: 一线城市支持 — 地区路由机制（region 字段 + 适配器工厂）

**Files:**
- Modify: `schemas/person-input.schema.json`（新增可选 `region` 属性：enum `beijing`/`shanghai`/`guangzhou`/`shenzhen`，缺省 `beijing`；不得设为 required）
- Create: `src/china_pension_strategy/adapters/regions/__init__.py`（`create_region_adapter(region, engine_version, ...)` 工厂；未知地区抛 `RegionMappingError`）
- Modify: `src/china_pension_strategy/entrypoints/cli/main.py`（第 154 行由硬编码 `BeijingRegionAdapter` 改为按输入 `region` 路由；`--engine` 传递不变）
- Test: `tests/adapters/test_regions.py`（新建）、`tests/contracts/test_schemas.py`、`tests/e2e/test_cli.py`

1. **写失败测试**（本任务只测路由机制，不依赖后续任务的规则包/夹具）：schema 接受 `region: "shanghai"`、拒绝未知地区值（如 `"xian"`）；工厂对四城返回对应适配器（断言类型为 `ShanghaiRegionAdapter` 等）、对未知地区抛 `RegionMappingError`；CLI 对带 `region: "shanghai"` 的临时输入走到上海适配器（断言退出码与路由结果；provenance 含 `cn-pension/shanghai/...` 的端到端断言推迟到 Task 11/12，届时上海规则包与夹具已就绪）。
2. **实现**：schema 属性 → 工厂 → main.py 路由。`region` 缺省 `beijing` 时行为与现状完全一致。
3. **北京回归**：运行 `evals/fixtures/golden-beijing-flex-2026.json`，记录 run_id 与改动前 `run-a7440a1a...759d59` 对比，必须一致。
4. **跑测试**：
   ```text
   python -m pytest tests/adapters/test_regions.py tests/contracts/test_schemas.py tests/e2e/test_cli.py -q
   ```
   Expected: 全部通过（新用例 + 既有用例）。

---

### Task 8: 一线城市证据档案（上海、广州、深圳）

**Files:**
- Create: `policy-data/sources/shanghai-*.json`、`guangzhou-*.json`、`shenzhen-*.json`（每城 3-5 条来源记录）
- Modify: `policy-data/source-digests.json`（保留既有 9 条不动，新增条目）
- Create: `references/regions/shanghai.md`、`guangzhou.md`、`shenzhen.md`（沿用 `beijing.md` 的格式：URL、文号、发布、施行、权威级别、发文机关、定位、原文摘录关键句、工程解释）
- Modify: `references/national-rules.md`（如各城需补充国家/省共用的口径佐证）
- Modify: `docs/policy-model.md`（地区清单，如枚举地区）
- Test: `tests/policy/test_official_packages.py`、`tests/contracts/test_schemas.py`

1. **逐城调研**（web_search 起点线索见下方，均为未验证线索；实施时逐条确认 `https://...gov.cn` 可达、文号与原文可核）。调研领域：

   | 城市 | 调研领域 | 初步线索（须验证） |
   |---|---|---|
   | 上海 | 灵活就业养老/医疗/失业缴费比例与基数上下限；就业困难人员灵活就业社保补贴（资格/期限/标准/申请时点） | 市人社局+市税务局《关于灵活就业人员参加本市职工基本养老保险有关问题的补充通知》（https://www.shanghai.gov.cn/nw12344/20240228/1fa3b59ef795429f9bc3cfd7b6599ceb.html）；就业困难人员补贴标准问答（https://rsj.sh.gov.cn/tcjjyyhzc_17545/20220705/t0035_1408073.html）；区级政策解读（https://www.shcn.gov.cn/col7454/20250429/1287750.html）；2025 年度缴费基数上下限须找市人社局原文（tyjr.sh.gov.cn 为转发，不作权威来源） |
   | 广州 | 广东省 2025 职工基本养老保险缴费基数上下限与计发基数（全省适用广州）；广州市灵活就业缴费比例；就业困难人员灵活就业社保补贴（市或省口径） | 广东省人社厅《关于公布2025年职工基本养老保险缴费基数上下限和基本养老金计发基数有关问题的通知》（https://hrss.gd.gov.cn/gkmlpt/content/4/4789/post_4789618.html）；越秀区补贴申领与热点问答（http://www.yuexiu.gov.cn/zwgk/zwgksxbzml/26/jyly/content/post_10556620.html、http://www.yuexiu.gov.cn/ggfw/ztfw/jy2/jyxx/content/mpost_9645582.html，区级佐证）；广州市本级灵活就业比例通知待查（本地宝/商业站不作来源） |
   | 深圳 | 灵活就业参保与缴费口径；2025 缴费基数上下限；促进就业困难人员再就业补贴办法（资格/期限/标准）；医保一档/二档结构对灵活就业的影响 | 深圳市政府公报《深圳市促进就业困难人员再就业补贴办法》（http://www.sz.gov.cn/zfgb/2024/gb1317/content/post_11106068.html）及政策解读（https://www.sz.gov.cn/zfgb/zcjd/content/post_11106144.html）；灵活就业参保问答（https://www.sz.gov.cn/ztfw/shbz/wyw_184041/ywzsk_184570/content/mpost_12250522.html）；2025 基数上下限与医保档位文件待查 |

   **来源纪律**：与既有来源一致——`source_digest` 为 SHA-256（镜像 `tests/policy/test_official_packages.py` 的算法）；URL 必须 `https://...gov.cn`；`authority_level` 取值须在 `_AUTHORITY_LEVELS` 内（已含 `PROVINCIAL_HRSS`/`MUNICIPAL_GOVERNMENT`/`MUNICIPAL_HRSS`）；无官方原文支持的内容一律不进来源记录与规则包。

2. **建立来源记录**：每城 3-5 条 `policy-data/sources/<city>-*.json`（字段对齐既有 beijing 记录：source_id、url、issuing_authority、authority_level、document_number（无则 null）、publication_date、retrieved_at、locator、source_digest）。
3. **写 reference sections**：`references/regions/{shanghai,guangzhou,shenzhen}.md`，每来源一个 `## 来源：<source_id>` 块（原文摘录关键句 + 工程解释：原文→规则推断边界）。
4. **计算并写入 digests**：更新 `policy-data/source-digests.json`（既有条目不动）。
5. **验证**：
   ```text
   python -m pytest tests/policy/test_official_packages.py tests/contracts/test_schemas.py -q
   ```
   Expected: 全部通过。

---

### Task 9: 各城市政策规则包

**Files:**
- Create: `policy-data/packages/shanghai-flex-employment.json`、`shanghai-flex-subsidy.json`、`guangzhou-flex-employment.json`、`guangzhou-flex-subsidy.json`、`shenzhen-flex-employment.json`、`shenzhen-flex-subsidy.json`（命名镜像既有 `beijing-*`）
- Modify: `policy-data/source-digests.json`（新包引用新来源）
- Test: `tests/policy/test_official_packages.py`、`tests/adapters/test_policy_repository.py`、`tests/domain/test_policy.py`

1. **写失败测试**：新包通过 schema 校验、`content_digest` 重算一致、`review_status = MVP_REVIEWED`、`local_only`、仅 `LOCAL_MVP` 模式可用；`list_packages` 收录 6 个新包。
2. **实现规则包**：包 ID 形如 `cn-pension/shanghai/flex-employment-2026.1`；规则覆盖缴费基数上下限、灵活就业缴费比例、补贴资格/期限/起算月/申请时点、方案现金流所需参数；**所有数值必须出自 Task 8 来源记录**，无来源支持不进包；national 最低年限包（`national-enterprise-pension.json`）全城复用，不重复造。
3. **跑测试**：
   ```text
   python -m pytest tests/policy/test_official_packages.py tests/adapters/test_policy_repository.py tests/domain/test_policy.py -q
   ```
   Expected: 全部通过。

---

### Task 10: 各城市区域适配器

**Files:**
- Create: `src/china_pension_strategy/adapters/regions/shanghai.py`、`guangzhou.py`、`shenzhen.py`（镜像 `beijing.py`：各自 `JURISDICTION` 为 `CN-31`/`CN-4401`/`CN-4403`、`POPULATION_*` 文案、事实映射与 `RegionMappingError` 错误码行为）
- Modify: `src/china_pension_strategy/adapters/regions/__init__.py`（注册三城）
- Test: `tests/adapters/test_regions.py`

1. **写失败测试**：每城 `policy_queries` 返回正确 `jurisdiction`/`topic`/`jurisdiction_role`/`population_scope`（national baseline 仍指向 `CN`）；`to_analysis_request` 事实映射（基数、月数、补贴事实）与北京一致的安全错误行为（缺事实/非法值 → `RegionMappingError` 带稳定错误码）。
2. **实现**：三个适配器只做查询构建与事实映射，**不含任何业务计算**（数值经 `PolicyQuery` 由规则包求值）。
3. **跑测试**：
   ```text
   python -m pytest tests/adapters/test_regions.py -q
   ```
   Expected: 全部通过。

---

### Task 11: 评估夹具、契约与 SKILL.md/文档同步

**Files:**
- Create: `evals/fixtures/golden-shanghai-flex-2026.json`、`golden-guangzhou-flex-2026.json`、`golden-shenzhen-flex-2026.json`（结构镜像 golden-beijing，`region` 字段 + 各城事实；数值与各城规则包一致）
- Modify: `evals/evals.json`（新增 3-6 个 cases：每城至少 1 个 success；可加区域特异场景，如深圳医保档位或上海补贴期限边界）
- Modify: `SKILL.md`（`## 何时使用` 的"北京就业困难人员社保补贴"扩为一线城市表述；`## LOCAL_MVP 边界` 的"已实现：北京地区适配器"改为北上广深列表；CLI 一节补 `region` 说明；`description` 若提及"北上广深"须保持单行与 8 个英文关键词）
- Modify: `README.md`、`CHANGELOG.md`（Task 5 条目之外新增城市支持条目）
- Test: `tests/e2e/test_skill_contract.py`（eval 清单 >=8 cases 已满足，新增后更多；fixture 存在性）、`tests/e2e/test_cli.py`

1. **新增三城 golden 夹具**：复用 golden-beijing 结构（schema_version/consent/分级/目的/保留期/能力/facts），`region` 设各城值；facts 用各城规则包支持的字段。
2. **更新 evals.json**：新增 cases（`id` 如 `golden-shanghai`，`kind: success`，`expected_exit_code: 0`）；跑 `tests/e2e/test_skill_contract.py::test_eval_fixtures_produce_expected_exit_codes` 确认。
3. **更新 SKILL.md**：注意契约约束——不写死金额/比例/版本号，`一线城市` 表述不带数字；`region` 说明加入 CLI 与输入字段描述。
4. **README/CHANGELOG**：README 状态与能力清单更新；CHANGELOG 新增 `### 一线城市支持` 条目（来源数、规则包数、适配器、夹具、门禁通过情况）。
5. **跑契约测试**：
   ```text
   python -m pytest tests/e2e/test_skill_contract.py -q
   ```
   Expected: 通过（用例数随 eval 清单增长）。

---

### Task 12: 全量验证与北京不动性回归

**Files:** 无新增（验证 + 清理）

1. **契约测试**：`python -m pytest tests/e2e/test_skill_contract.py -q`，Expected: 通过。
2. **全套件**（正常终端）：`python -m pytest -q`，Expected: 全部通过。
3. **北京不动性**：重跑 `evals/fixtures/golden-beijing-flex-2026.json`，run_id 必须仍为 `run-a7440a1a...759d59`（与改动前一致）；privacy-block 仍退出 5 且零工件。
4. **每城手动黄金路径**：对 `golden-shanghai-flex-2026.json`、`golden-guangzhou-flex-2026.json`、`golden-shenzhen-flex-2026.json` 依次执行 analyze → render --format markdown → cleanup（`--expires-before 2027-01-01T00:00:00Z`），断言退出 0、信封 `status: success`、provenance 含对应 `cn-pension/<city>/...` 包。
5. **清理**：删除任务产生的 `runs/`、`runs-blocked/` 与临时目录。

---

## 后续可选（不在本次范围）

- **下一批地区**：一线城市落地并验证后，按同一模式扩展二线城市（成都、杭州、武汉等），每城复用 Task 8-10 的证据档案→规则包→适配器流程，national 包与地区路由机制不动。
- **LLM 级触发评测**（skill-creator 的 run_loop 需 `claude` CLI，本环境不可用）：后续若接入，可在 `evals/trigger-cases.json` 建立 should/should-not 触发查询集（如"帮我算下上海社保缴费还差多少个月"→应触发；"推荐个商业养老年金产品"→不应触发），再以独立评测循环验证触发准确率。
---

# 第二部分：二线城市与省份覆盖（追加批次）

**批次（用户已确认推荐方案）**：省本级规则包——浙江（CN-33）、四川（CN-51）、湖北（CN-42）、江苏（CN-32）；城市适配器——杭州（CN-3301）、成都（CN-5101）、武汉（CN-4201）、南京（CN-3201）；直辖市（省本级=城市）——天津（CN-12）、重庆（CN-50）。

**架构决策**：省份层承载缴费基数上下限与灵活就业养老费率（省办法），城市层承载补贴与特例。适配器发出三类查询——national 最低年限（CN）、省份缴费（CN-XX，LOCAL_IMPLEMENTATION）、城市补贴（CN-XXXX）；直辖市两层合一。既有一线城市（北上广深）保持城市自有包不动（run_id 不变性）；广州/深圳重构为省份层列为后续可选。

### Task 13: 架构——region 枚举扩展与省份层适配器设计

**Files:**
- Modify: `schemas/person-input.schema.json`（region 枚举加 hangzhou/chengdu/wuhan/nanjing/tianjin/chongqing）
- Modify: `src/china_pension_strategy/adapters/regions/__init__.py`（注册 6 个新适配器）
- Create: `src/china_pension_strategy/adapters/regions/{hangzhou,chengdu,wuhan,nanjing,tianjin,chongqing}.py`（省份层三查询模式；直辖市两层）
- Test: `tests/adapters/test_regions.py`（新增 6 城工厂/查询断言）

1. schema 枚举扩展（向后兼容，既有夹具不受影响）。
2. 工厂注册 6 城。
3. 适配器：城市适配器发出 national(CN) + 省份缴费(CN-XX) + 城市补贴(CN-XXXX) 三查询；直辖市发出 national + 本级缴费 + 本级补贴。
4. 测试：工厂返回对应类；`policy_queries` 返回正确 jurisdiction 集合；北京/一线 run_id 不变。

### Task 14: 证据档案（6 省 + 6 城调研与来源）

**Files:**
- Create: `policy-data/sources/{zj,sc,hb,js,tj,cq}-*.json`、`references/regions/{zhejiang,sichuan,hubei,jiangsu,tianjin,chongqing,hangzhou,chengdu,wuhan,nanjing}.md`
- Modify: `policy-data/source-digests.json`、`tests/policy/test_official_packages.py`（REFERENCE_FILES 已 glob，无需改）

1. 每省：2025/2026 缴费基数上下限通知（省人社厅）、灵活就业养老费率（省办法，通常 20%）→ 2-3 来源。
2. 每城：就业困难人员灵活就业社保补贴（城市或省标准、期限）→ 1-2 来源；直辖市补贴单独调研。
3. 来源纪律：gov.cn、文号、原文摘录、SHA-256 摘要（复用既有管线）。

### Task 15: 规则包（6 省本级 + 4 城补贴 + 2 直辖市）

**Files:**
- Create: `policy-data/packages/{zhejiang,sichuan,hubei,jiangsu}-flex-employment.json`、`{hangzhou,chengdu,wuhan,nanjing}-flex-subsidy.json`、`{tianjin,chongqing}-flex-employment.json`、`{tianjin,chongqing}-flex-subsidy.json`

1. 省包：基数上下限（PARAMETER_TABLE）+ 养老 20%（POLICY_RULE）；省份 population_scope。
2. 城市补贴包：资格/期限/金额（参照既有模式）；直辖市单层双包。
3. 全部数值出自 Task 14 来源；test_vectors 齐全；`tests/policy/test_official_packages.py` 通过。

### Task 16: 城市适配器落地

**Files:**
- Modify: `adapters/regions/__init__.py`（已完成注册，核查）
- Test: `tests/adapters/test_regions.py`（扩展查询断言）

### Task 17: 夹具、契约与 SKILL/文档同步

**Files:**
- Create: `evals/fixtures/golden-{hangzhou,chengdu,wuhan,nanjing,tianjin,chongqing}-flex-2026.json`
- Modify: `evals/evals.json`、`SKILL.md`（何时使用/边界/region 列表）、`README.md`、`CHANGELOG.md`

### Task 18: 全量验证与不动性回归

1. 北京 `run-a7440a1a...` 与一线城市 run_id 全部不变。
2. 六城 analyze→render→cleanup 全链路。
3. 全量 `python -m pytest -q`（默认配置）通过。
4. 清理临时文件；执行日志与 `docs/sandbox-capabilities.md` 同步。

