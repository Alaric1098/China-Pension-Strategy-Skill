---
name: china-pension-strategy
description: Use when analyzing Chinese basic pension insurance, social-security contribution records, retirement contribution gaps, flexible-employment continuation, pension subsidy timing, regional pension rules, or comparing contribution and retirement strategies in China. 当用户需要计算养老缴费缺口与最低缴费年限、核对社保权益单、灵活就业缴费与补贴、北京等地区社保政策、比较停缴续缴方案、估算退休待遇、跨省领取地或办理补缴与个人养老金时，使用本技能。Runs deterministic calculations through the china-pension-strategy CLI and never computes policy values inline.
---

# China Pension Strategy

中国基本养老保险的确定性计算与续保策略技能。所有金额、月份、资格与推荐均由
`china-pension-strategy` CLI 内的规则求值器计算；本技能不内联任何政策数字。

## 何时使用

**应触发**——用用户语言匹配（→ 能力 → 输出）：

| 用户问 | 能力 | 说明 |
|---|---|---|
| 缴费还差多少个月 / 最低年限 / 缺口 | 缺口计算 | 输出剩余缺口与方案 |
| 权益单明细与累计对不上 | 对账 | 冲突列为待核验项 |
| 灵活就业每月交多少 / 补贴后净负担 | 缴费与补贴 | 按地区费率与补贴标准 |
| 停缴 / 续缴 / 补贴时机哪个划算 | 情景比较 | continue / stop / subsidized |
| 退休后每月能领多少 | 待遇测算（仅北京路由） | 当前路径使用全国待遇规则和显式计发基数输入 |
| 在哪个城市办退休 / 跨省转移 | 多地区比较 | 领取地判定 + 跨区缴费比较 |
| 缴费档次怎么选影响大吗 | 敏感性分析 | 指数档次待遇矩阵 |
| 年限不够能补吗 / 怎么办 | 补缴政策 | 最低年限表与延长/一次性选项 |
| 个人养老金能省多少税 | 个人养老金税优 | 缴费限额与领取计税 |
| 城乡居民养老怎么算 | 城乡居民养老 | 缴费档次、补贴、基础养老金与个人账户 |

**不应触发**：商业养老保险产品推荐、股票基金投资建议、其他国家养老金制度、
仅查询政策网页但不涉及个人养老计算的任务。

## 前置条件与自检

- 依赖仓库内已安装的 `china-pension-strategy` 包（`pip install -e .`；版本与依赖见 `pyproject.toml`）
- 规则包位于 `policy-data/packages/`；需要时用 `--packages-dir` 指向其他目录
- 分析前先运行契约自检：`python -m pytest tests/e2e/test_skill_contract.py -q`
- 维护数据时效用 `scripts/policy_expiry_report.py`（列出临近失效规则包）

## 隐私与数据边界

分析前先扫描全部输入。原始身份证号、社会保障号码、银行卡号、校验码与查询
流水号按 `BLOCK` 阻断；手机号、金额、地址、姓名等按 `REDACT` 脱敏后继续，
并在信封 warnings 中记录。决策模型为 `ALLOW` / `REDACT` / `BLOCK`。

- 输入必须携带 `consent_id`、分级（`S1-INTERNAL` 或 `S2-CONFIDENTIAL`）、目的常量、`expires_at` 与删除状态
- 分析模式必须为 `LOCAL_MVP`；`PRODUCTION` 未实现，不得假装支持
- 仅执行 `MVP_REVIEWED` 规则包；扫描在分析前进行，被阻断的输入不产生工件

## 工作流

接到任务后按以下顺序执行，所有数字一律来自 CLI 输出：

1. **读输入与预检**：确认携带 `consent_id`、`classification`、`purpose`、`expires_at`、`deletion_status` 与 `analysis_mode`；缺失时先用 `validate` 定位并向用户如实报告。
2. **先扫描后分析**：任何计算前先过隐私扫描；`BLOCK` 直接终止，`REDACT` 在 warnings 中如实转述。
3. **运行 analyze**：核对信封 `status`（success/partial/error）、`warnings`、`provenance`；非 success 要向用户明确说明。
4. **渲染与汇报**：报告用 `render --format markdown`；只转述信封与报告中的数值，不自行计算。
5. **说明边界**：附带 LOCAL_MVP 边界、政策版本与免责提示；未解决冲突与 `BLOCK`/`REDACT` 项列为待核验。

禁止内联计算政策数值、复制原始身份证号，或假装支持未实现能力（PRODUCTION、DOCX/PDF、远程服务、真实权益文件摄取）。

## CLI 命令

全部通过 `python -m china_pension_strategy.entrypoints.cli.main` 运行；退出码 0-8（成功/意外失败/用法/输入无效/政策无效/隐私阻断/渲染失败/运行未找到/清理失败）。

- `validate --input FILE [--schema FILE]`：仅校验输入，输出 `valid`
- `analyze --input FILE --runs-dir DIR [--packages-dir DIR] [--audit FILE] [--schema FILE] [--engine VER]`：扫描→映射地区→解析政策→确定性计算；信封到 stdout，原始输出与清单原子落盘
- `render --run-id RUN_ID --runs-dir DIR --format json|markdown [--output FILE]`：按 run_id 重载已验证输出渲染
- `cleanup --runs-dir DIR --expires-before ISO_DATETIME`：删除过期工件并写删除清单

输入 `region` 字段（北上广深、杭州、成都、武汉、南京、天津、重庆，缺省 `beijing`）决定用哪套规则包；`validate` 校验取值。

示例：

```text
python -m china_pension_strategy.entrypoints.cli.main analyze \
  --input evals/fixtures/golden-beijing-flex-2026.json --runs-dir runs

python -m china_pension_strategy.entrypoints.cli.main render \
  --run-id run-... --runs-dir runs --format markdown
```

## 输出处理

- 信封（`schema_version` 1.0.0，`status` success/partial/error，`data` 含 `run_id`/`artifact_ref`，provenance 为规则包摘要）输出到 stdout
- 已验证输出（`analysis-output`，`schema_version` 2.0.0）原子写入 `runs/<run_id>/analysis.json`，清单写入 `manifest.json`；Markdown 与 JSON 共享单一事实源
- 运行身份内容寻址：相同输入与版本产生相同 `run_id`

## LOCAL_MVP 边界

- 已实现：10 个地区（北上广深、杭州、成都、武汉、南京、天津、重庆）与全国规则；省份层缴费规则（浙江/四川/湖北/江苏）由省本级包承载
- 已实现：对账、缺口、缴费、补贴、情景和推荐；北京路由另接入待遇测算、城乡居民养老、多地区比较、敏感性、个人养老金税优与补缴
- 说明：十城养老与医疗费率已覆盖；失业费率仅北京已建模，其余城市按未覆盖处理（相应能力为部分能力）；待遇测算当前仅北京
- 未实现：`PRODUCTION` 模式、全国推广承诺、DOCX/PDF 渲染、远程服务与真实权益文件摄取（MVP 仅接受合成数据）

## 免责声明

本技能用于信息整理、确定性计算与决策支持，不替代社保经办机构的资格认定、
缴费年限核定、退休审批或法律意见。政策具有地区差异并会持续调整，任何
结论仅在所列政策版本、个人事实与模型假设下成立；办理停缴、补缴、转移、
退休或补贴申请前，应使用最新官方规则并向经办机构核验，取得必要的书面确认。
