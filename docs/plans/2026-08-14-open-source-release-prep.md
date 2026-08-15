# 开源发布准备 Implementation Plan（待审批）

> 依据"先计划→审核→批准→执行"治理规则提交。**批准前不做任何修改**。
> 目标：把当前工程整理为可公开发布的初版开源仓库。许可证已定（2026-08-14 讨论后修订）：**代码 MIT，数据 CC0 1.0**。
> 修订理由：本项目目标是最大化传播。Apache-2.0 的专利授权对"公开政策规则的确定性算术"近乎无价值，其 NOTICE 保留与修改声明义务反而增加下游负担，且与 GPLv2-only 项目不兼容；MIT 认知度最高、义务最轻、兼容面最广。数据侧由 CC BY 改为 CC0：`references/` 主体是政府公开文件原文摘录（著作权法第五条本不受保护），对其要求署名不合逻辑，CC0 让政策数据库这一最具传播价值的资产零门槛复用（CC0 同样保留免责声明）。
> 现状基线：642 个测试通过、`verify_design_docs.py` exit 0、`test_design_contracts.py` 11 项、`audit_architecture.py --gaps` 为 0、北京 golden run_id 稳定。**内容层面已达标，本计划只处理发布外壳。**

---

## Phase 0：发布前硬阻塞（P0，建议一次做完）

### Task 0.1 清理工作区残留

删除以下目录（全部为沙箱/工具残留，无项目内容）：

| 目录 | 内容 | 处置 |
|---|---|---|
| `.opencode/` | 3680 文件 / 52.54 MB，node_modules 工具残留 | **删除**（含大量第三方许可证，绝不能进首个提交） |
| `.bt-bisect`、`.bt-clean`、`.bt-conf`、`.bt-conf2`、`.bt-fresh2`、`.bt-nosub`、`.bt-ret-none`、`.mode-test`、`d-0700`、`eval-tmp2`、`eval-tmp3`、`.pytest-tmp-eval` | 12 个空目录（历史 0o700 ACL 实验残留） | **删除**；若 ACL 阻止删除，改为写入 `.gitignore` 并在 README 说明 |
| `.pytest-temproot/`（333 文件）、`.pytest_cache/`、`.hypothesis/`、`__pycache__/` | 运行期产物 | **删除 + 加入 `.gitignore`** |
| `architecture-autoresearch-results.tsv` | 一次性调研输出（已在 `.gitignore`） | 删除文件本体 |
| `fetch_gov.cjs` | 早期 Node 抓取试验，已被 `scripts/webget.py` 取代 | **删除**（功能重复且不再使用） |

**保留决策（✅ 已定 2026-08-14）**：`.specify/`（20 文件，0.09 MB）**整个目录保留**——`memory/constitution.md` 记录项目原则，模板对贡献者有参考价值。其自带的 `.specify/.gitignore` 一并保留，执行时确认它不会排除掉 constitution。

### Task 0.2 `.gitignore` 补全

现有 4 行 → 替换为完整版本：

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.venv/
venv/

# Test & tooling artifacts
.pytest_cache/
.pytest-temproot/
.hypothesis/
.coverage
htmlcov/

# Runtime output (analysis runs contain personal facts — never commit)
runs/
*.jsonl

# Tooling residue
.opencode/
.autoresearch-starred
architecture-autoresearch-results.tsv

# OS / editor
.DS_Store
Thumbs.db
.idea/
.vscode/
```

`runs/` 与 `*.jsonl`（审计日志）**必须**忽略——它们含个人事实，这是隐私边界的一部分，不只是整洁问题。

### Task 0.3 许可证与版权声明

| 文件 | 内容 |
|---|---|
| `LICENSE` | MIT License 全文（适用于代码：`src/`、`tests/`、`scripts/`、`schemas/`、`conftest.py` 与根目录三个脚本） |
| `LICENSE-DATA` | CC0 1.0 Universal 全文（适用于数据与证据档案：`policy-data/`、`references/`、`evals/fixtures/`） |
| `NOTICE` | 版权归属 + 政策原文声明（见下） |
| `README.md` 新增「许可证」章节 | 说明双许可的边界与理由 |

`NOTICE` 需明确三点：

1. **代码** MIT，**数据与证据档案** CC0 1.0（按目录逐一列举边界，不留解释空间）；`docs/`、`README.md`、`SKILL.md`、`CHANGELOG.md` 归入 CC0（属文档而非代码）。
2. **政策原文摘录不主张版权**：中国《著作权法》第五条将法律、法规、国家机关的决议、决定、命令及其官方正式译文排除在著作权保护之外；`references/` 中的原文摘录属此类官方文件，本项目不对其主张任何权利。
3. **镜像来源声明**：部分证据经转载/镜像页面取得（如天津补贴通知经法规库镜像、广东补贴清单经河源市转发件），仅作交叉核验用途，**以来源记录中的 gov.cn 权威 URL 为准**；若镜像站对其汇编主张权利，以其声明为准。

**版权头决策（✅ 已定 2026-08-14）**：`src/` 下**不逐文件加版权头**，只在 `LICENSE` + `NOTICE` + `pyproject.toml` 声明——MIT 本就不要求逐文件头，仅要求分发时保留版权声明与许可证文本。

**归属主体决策（✅ 已定 2026-08-14）**：`NOTICE`、`LICENSE` 版权行、`pyproject.toml` 的 `authors` 与 `[project.urls]` 一律使用占位符，发布前由你替换：

| 占位符 | 用途 | 出现位置 |
|---|---|---|
| `<COPYRIGHT_HOLDER>` | 版权归属主体（个人姓名或组织名） | `LICENSE` 的 `Copyright (c) 2026 <COPYRIGHT_HOLDER>` 行、`NOTICE`、`pyproject.toml` `authors.name`（CC0 是权利放弃声明，`LICENSE-DATA` 正文本身不需要填写主体） |
| `<CONTACT_EMAIL>` | 联系邮箱 | `pyproject.toml` `authors.email`（可选，留空亦可） |
| `<PROJECT_URL>` | 项目主页 / 仓库地址 | `pyproject.toml` `[project.urls]`、README 许可证章节 |

执行时会在 README 的「许可证」章节末尾加一行醒目提示：**发布前须替换全部 `<...>` 占位符**；并在 Phase 0 验收里加一步 `grep -r "<COPYRIGHT_HOLDER>\|<PROJECT_URL>\|<CONTACT_EMAIL>"` 列出全部待替换位置，作为交付清单交给你。

### Task 0.4 `git init` 与首个提交

1. `git init`，默认分支 `main`。
2. 新增 `.gitattributes`：`* text=auto eol=lf`（Windows 开发、跨平台一致；`canonical_source_digest` 已做行尾归一化，但仓库层面统一仍必要）。
3. **先落 `.gitignore` 与清理，再 `git add`**，避免 52 MB 残留进入历史（一旦进历史就只能重写历史才能移除）。
4. 提交前跑一次 `git status --porcelain` 人工核对文件清单，确认没有 `runs/`、临时目录、node_modules。
5. 首个提交信息：`Initial public release: deterministic China pension contribution & benefit analysis skill`。
6. **不推送**——远端仓库的创建与推送由你决定，本计划不含任何推送步骤。

### Task 0.5 README 补安装与快速开始

现有 README 是 17 章的设计说明，读者读完不知道怎么跑。在「目录」之后、「项目定位」之前插入三节：

- **免责声明（置顶）**：本工具输出为测算参考，不替代社保经办机构的资格认定与退休审批；政策数据有时效，办理前须以最新官方规则为准并向经办机构核验。（现有免责内容在 SKILL.md 与 README 末章，需在第一屏出现。）
- **安装**：`python -m venv .venv` → 激活 → `pip install -e ".[test]"`；Python ≥ 3.12。
- **快速开始**：三条可复制命令——`validate` 一个合成夹具、`analyze` 得到信封与 `runs/<run_id>/`、`render --format markdown`；并说明 `evals/fixtures/` 全为合成数据，不含真实个人信息。
- **数据时效**：说明政策包会过期，维护者应定期跑 `python scripts/policy_expiry_report.py`；当前广州医疗费率 2026-12-31 到期（4 个月）。

同时更新目录锚点（`verify_design_docs.py` 会校验 README 锚点与本地链接，改完必须复跑）。

---

## Phase 1：应补项（P1）

### Task 1.1 `pyproject.toml` 元数据

- `description` 现为 "Deterministic **Beijing** pension strategy analysis" → 已覆盖 10 个地区，需更新
- 补 `license = "MIT"`（PEP 639 的 SPDX 字符串形式）、`license-files = ["LICENSE", "LICENSE-DATA"]`、`readme = "README.md"`、`authors`、`keywords`、`classifiers`（含 `License :: OSI Approved :: MIT License`、`Programming Language :: Python :: 3.12/3.13/3.14`）、`[project.urls]`
- 执行时确认本机 setuptools 版本支持 PEP 639 的 `license` SPDX 写法；若不支持则回退为 `license = {text = "MIT"}` 并保留 classifier
- 考虑加 `[project.scripts]` 入口点（如 `china-pension = china_pension_strategy.entrypoints.cli.main:main`），让安装后可直接 `china-pension analyze …` 而非 `python -m …`

### Task 1.2 CI（GitHub Actions）

`.github/workflows/ci.yml`：push / PR 触发，矩阵 Python 3.12 与 3.13（本机 3.14 亦可加），步骤：

```
pip install -e ".[test]"
python -m pytest -q
python verify_design_docs.py
python test_design_contracts.py
python audit_architecture.py --gaps
python scripts/policy_expiry_report.py --horizon-months 6   # 数据时效门禁
```

**注意**：时效门禁在有临近到期包时退出 1。建议 CI 里用 `continue-on-error: true` 或降低 horizon，使其**提示而不阻断**——否则广州费率一到期 CI 就永久红，与历史包分区修复的初衷相悖。具体策略执行时定。

同时建议加 `ubuntu-latest` 跑一遍：目前全部验证都在 Windows 完成，`conftest.py` 的 ACL 补丁在 Linux 应为 no-op，**这条从未被验证过**，CI 是第一次真实检验。

### Task 1.3 `conftest.py` 说明

根 `conftest.py` 在 Windows 上剥离 `os.mkdir`/`os.makedirs` 的 mode 参数，属特定沙箱 ACL 问题的 workaround。外部贡献者看到会困惑（"为什么猴补丁标准库"）。需要：

- 文件头补完整 docstring：问题现象、根因、为何是测试期而非生产代码、非 Windows 为 no-op
- README 或 CONTRIBUTING 指向 `docs/sandbox-capabilities.md`
- 顺带核对：`docs/sandbox-capabilities.md` 中的内部沙箱代号与本机临时路径必须改写为通用表述

### Task 1.4 `CONTRIBUTING.md`（对本项目尤其重要）

本项目的价值建立在几条外部贡献者不会自然遵守的纪律上，不写下来第一个 PR 就会破坏：

1. **无 gov.cn 可核验来源的数值不得进规则包**——包括"看起来对"的费率；镜像来源须标注权威 URL 与交叉核验路径
2. **改证据档案必须重算摘要链**：references 章节正文 → `policy-data/sources/*.json` 的 `source_digest` → `source-digests.json` → 包 provenance → `content_digest`，任一环节不同步测试即红
3. **`transaction_from` 不得早于来源 `retrieved_at`**；新证据入包视为新包版本，须同步 `AS_KNOWN_AT` 与相关夹具
4. **run_id 不动性**：既有夹具的 run_id 是回归基线，改动不得使其变化（北京 `run-a7440a1a…` 为守门用例）
5. **SKILL.md 内不得内联政策数字**（百分比、补贴比例、金额字面量），由契约测试锁定
6. **历史包须标 `historical: true`**，否则污染时效门禁
7. **PR 前必跑的四条门禁命令**（同 CI）
8. 提交 PR 的政策数据须附来源 URL、文号、发布日期、原文摘录

### Task 1.5 免责与法律边界复核

- README 置顶免责（Task 0.5 已含）
- `NOTICE` 政策原文声明（Task 0.3 已含）
- 复核 `evals/fixtures/` 12 个夹具确无真实个人信息（现状为合成数据，需逐个确认后在 README 声明）
- 复核 `docs/` 28 个文件是否含本机路径、内部工具代号、会话细节（已知 `sandbox-capabilities.md` 需改写；执行日志与变更记录属项目历史，建议保留但扫一遍本机路径）

---

## Phase 2：可选（P2，不阻塞发布）

- `CODE_OF_CONDUCT.md`（Contributor Covenant）、`SECURITY.md`（漏洞报告渠道）
- **英文 README**：当前全中文。若目标受众含国际用户，`README.en.md` 值得做；政策内容本身是中国语境，优先级不高
- 根目录三个脚本（`audit_architecture.py`、`test_design_contracts.py`、`verify_design_docs.py`）归置到 `tools/`：**注意** `verify_design_docs.py` 从 `audit_architecture` 导入、且多处按 `ROOT = Path(__file__).parent` 定位，移动会牵动路径解析与 CI 命令，收益小风险中，建议**暂不动**
- Issue / PR 模板

---

## 验证（Phase 0 + 1 完成后）

1. **四条既有门禁全绿**：`pytest -q`（基线 642）、`verify_design_docs.py` exit 0、`test_design_contracts.py`、`audit_architecture.py --gaps` 为 0
2. **北京 golden run_id 仍为** `run-a7440a1a294cbdb2464f039f6a61e96d496cc1d5aa88c594c66b879602375d59`
3. **全新环境冒烟测试**（关键，此前从未做过）：在临时目录建全新 venv → `pip install -e ".[test]"` → 跑全量测试 → 按 README 快速开始逐条执行 `validate`/`analyze`/`render` → 确认无需任何本机特有配置
4. **`git status --porcelain` 人工核对**：无 `runs/`、无临时目录、无 node_modules；`git count-objects -vH` 确认仓库体积合理（预期 < 5 MB）
5. **README 锚点与本地链接**由 `verify_design_docs.py` 校验（改 README 必复跑）

## 风险

| 风险 | 处置 |
|---|---|
| 52 MB 残留进入首个提交后难以移除 | 严格顺序：清理 → `.gitignore` → `git add` → 提交前 `git status` 人工核对 |
| 删除目录时 ACL 拒绝（历史 0o700 目录） | 删不掉就 `.gitignore` 掉并在 README 记一句，不阻塞发布 |
| CI 在 Linux 首次运行暴露 Windows 特有假设 | 这正是要它跑的原因；若失败，修 `conftest.py` 的平台判定而非关掉 CI |
| 时效门禁使 CI 永久红 | CI 中设为提示不阻断（见 Task 1.2） |
| 公开后政策数据过期给出错误答案 | README 置顶免责 + 数据时效章节 + 时效报告；这是**声明**问题，不是技术问题，必须写清 |
| 双许可边界模糊（代码/数据分界） | `NOTICE` 中按目录明确列举，不留解释空间 |

**明确不做**：创建远端仓库、推送、发布到 PyPI、改动任何政策数据或引擎逻辑、为发布而放宽任何既有门禁。

---

## 审批请求

- **Phase 0（P0 六项）**：建议批准——这是"能不能发"的门槛。
- **Phase 1（P1 五项）**：建议批准——这是"发出去别人能不能用、会不会被改坏"的门槛。
- **Phase 2（P2）**：建议暂缓，发布后按需补。

**三项前置决定已定（2026-08-14）**：`.specify/` 保留 ✅ ｜ 不加逐文件版权头 ✅ ｜ 归属主体用占位符 ✅。计划无剩余待定项，可直接执行。

**执行前须知（不可逆动作清单）**：

| 动作 | 可逆性 |
|---|---|
| 删除 `.opencode/`（52.54 MB 工具残留） | 不可逆，但可由工具重新安装生成 |
| 删除 `fetch_gov.cjs` | 不可逆（功能已由 `scripts/webget.py` 覆盖，无引用） |
| 删除 `architecture-autoresearch-results.tsv` | 不可逆（一次性调研输出，已在 `.gitignore`） |
| 删除 12 个空残留目录、运行期缓存目录 | 无内容损失 |
| `git init` + 首个提交 | 可逆（删 `.git/` 即可） |

其余均为新增文件或文本编辑。**不含任何远端操作**（不建远端仓库、不推送、不发布 PyPI）。
