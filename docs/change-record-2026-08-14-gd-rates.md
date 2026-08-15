# 修改记录（任务 1-B：广州/深圳 医疗与失业费率）

生成时间：2026-08-14
执行依据：`docs/plans/2026-08-14-task1b-gd-medical-unemployment.md`（审批选项 a：Step 0 只读调研 + Step 1 落包，图片路径用临时探针不动仓库）

## 一、Step 0 调研结论（来源梯子命中 L1/L2，未用到 L6 图片直读）

| 数值 | 结论 | 来源级别 | 出处 |
|---|---|---|---|
| 广州灵活就业医疗费率 8% | ✅ 已核验 | L1 市级规范性文件 | 穗医保规字〔2022〕1号（gz.gov.cn），二（二）；施行 2022-12-01，有效期至 2026-12-31 |
| 广州阶段性降费 6.5%（至 2025-12-31） | ✅ 已核验 | L1 市级通知 | 广州市医保局等 2024-02-29 通知（gz.gov.cn），一、二 |
| 深圳灵活就业医疗一档费率 8% | ✅ 已核验 | L1 市政府令 | 深圳市人民政府令第358号《深圳市医疗保障办法》第九条（sz.gov.cn） |
| 深圳 2026 恢复 8% + 医保基数 6727/33633 | ✅ 已核验 | L2 市医保局公告 | 深圳市医保局 2025-12-29 温馨提示（hsa.sz.gov.cn） |
| 广深灵活就业可参加失业保险 | ✅ 已核验 | L1 省级规范性文件 | 粤人社规〔2025〕50号（hrss.gd.gov.cn），2026-01-01 施行、有效期 2 年、试点含广深、自愿参保 |
| 广深失业保险当期基准费率 | ❌ 无当期来源 | — | 办法只写"国家和省规定的基准费率"；1% 的依据（粤人社函〔2023〕133号 转发件、国家延续文件）有效期止于 2025-12-31，未见 2026 年度原文 |

**关键结论**：原阻塞源 粤医保规〔2022〕2号（图片附件）**不再是必需来源**——广深医保费率各自有市级可核验文本，无需图片转录，L6 路径未启用。

## 二、Step 1 落包改动

### 新增来源记录（policy-data/sources/）

| 文件 | 文号 / 出处 |
|---|---|
| `gz-medical-rate-2022.json` | 穗医保规字〔2022〕1号 |
| `gz-medical-cut-2024.json` | 广州市医保局等 2024-02-29 阶段性降费通知（无文号） |
| `sz-medical-rate-358.json` | 深圳市人民政府令第358号 |
| `sz-medical-restore-2026.json` | 深圳市医保局温馨提示（2025-12-29，无文号） |

`gd-flex-unemployment-2025`（粤人社规〔2025〕50号）按 `tj-unemployment-not-applicable` 先例只建证据档案章节 + 摘要登记，不建来源文件、不进包 provenance（无规则引用）。

### 证据档案（references/regions/）

| 文件 | 变更 |
|---|---|
| `guangzhou.md` | 新增 `## 来源：gz-medical-rate-2022`、`## 来源：gz-medical-cut-2024`；`gz-flex-participation` 工程解释更新（医疗已核验、失业指向省办法） |
| `shenzhen.md` | 新增 `## 来源：sz-medical-rate-358`、`## 来源：sz-medical-restore-2026`；`sz-flex-participation` 与 `sz-subsidy-method` 工程解释更新（医疗已核验；补贴基数仍按养老口径，两种口径均触 600 元上限，结论不变） |
| `guangdong.md` | 新增 `## 来源：gd-flex-unemployment-2025`（失业办法与"费率待核验"判定） |

`policy-data/source-digests.json`：59 → 64 条（新增 5 条，另 4 条因章节正文修改重算）。

### 规则包（修改既有包，未新建包，未改适配器）

| 文件 | 变更 |
|---|---|
| `policy-data/packages/guangzhou-flex-employment.json` | 新增规则 `guangzhou-flex-medical-contribution`（0.08×基数，effective_from 2026-01-01，向量 5510→440.80、6000→480.00）；provenance +2；`transaction_from` → 2026-08-14T12:00:00Z；content_digest 重算 |
| `policy-data/packages/shenzhen-flex-employment.json` | 新增规则 `shenzhen-flex-medical-contribution`（0.08×基数，effective_from 2026-01-01，向量 5000→400.00、6727→538.16；参数含二档 0.02、医保基数 6727/33633）；provenance +2；`transaction_from` → 2026-08-14T12:00:00Z；content_digest 重算 |
| `guangzhou-flex-subsidy.json` / `shenzhen-flex-subsidy.json` | 仅因引用章节摘要变化同步 provenance 摘要与 content_digest，规则未变 |

### 测试与夹具

| 文件 | 变更 |
|---|---|
| `tests/policy/test_official_packages.py` | `AS_KNOWN_AT` 2026-08-11T12:00Z → 2026-08-14T12:00Z（新包版本的事务时间） |
| `evals/fixtures/golden-{guangzhou,shenzhen}-flex-2026.json` | `created_at` → 2026-08-14T12:00:00Z（否则新包版本在该时点不可见）；输入其余不变 |

适配器（`adapters/regions/{guangzhou,shenzhen}.py`）**无改动**——两城为城市层单包，既有 `flexible_employment_contribution` 查询已覆盖 CN-4401/CN-4403。

## 三、验证结果

- 官方包测试 + 区域适配器 + 契约：220 passed
- 全量 pytest：**606 passed**（与修改前基线一致，无新增用例、无回归）
- 北京 golden run_id 不变：`run-a7440a1a294cbdb2464f039f6a61e96d496cc1d5aa88c594c66b879602375d59`
- 端到端 analyze（退出码 0）：广州 6000 基数 → 养老 1200.00 + 医疗 480.00 = 净流出 1680.00；深圳 5000 基数 → 养老 1000.00 + 医疗 400.00 = 净流出 1400.00；失业两城均 0.00（未建模）
- `scripts/policy_expiry_report.py`：仅天津补贴包 EXPIRING_SOON（16 个月），与基线一致，无新增 EXPIRED

## 四、遗留事项

1. **广深失业保险费率**：可参保已核验，2026 年度基准费率无可核验原文 → 未建规则。取得 2026 年度基准费率（国家/省阶段性降费延续文件或省定基准）原文后可补规则；补规则时须一并建模失业保险基数口径（下限=所在市最低工资标准、上限=上年度在岗职工月平均工资 3 倍），与养老、医疗基数口径均不同。
2. **医保基数口径差异**：广深医保缴费基数上下限与养老不同源（深圳 2026 年度 6727/33633），引擎按用户申报的单一基数 × 费率输出，不做医保基数钳制——申报基数低于医保下限时实际缴费按下限计收，属已知偏差，已在 references 标注。
3. **历史期未建模**：广州 2024-03~2025-12 的 6.5%、深圳同期 7% 未建规则；对该期间的历史测算会按 8% 或无规则处理。
4. **穗医保规字〔2022〕1号 有效期至 2026-12-31**：到期须复核续期或替代文件（规则 effective_to 保持 null，与既有包惯例一致）。
