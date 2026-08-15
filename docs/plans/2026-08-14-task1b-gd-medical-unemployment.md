# 任务 1-B 执行计划：广州/深圳 医疗与失业费率补齐（待审批）

> 依据"先计划→审核→批准→执行"治理规则提交。**批准前不做任何修改**（本文件本身为计划稿）。
> 前序：`docs/plans/2026-08-14-rates-payment-months.md` 任务 1 步骤 B；步骤 A（六城医疗）已完成，见 `docs/change-record-2026-08-14-rates-medical.md`。

---

## 一、目标与现状

**目标**：让广州（CN-4401）、深圳（CN-4403）灵活就业月缴不再把医疗（及深圳失业）计为"未覆盖=0"，与已覆盖的 8 个地区口径对齐。

**现状（已核验）**：

| 地区 | 养老 | 医疗 | 失业 |
|---|---|---|---|
| 广州 | ✅ 20%（粤人社规〔2026〕14号） | ❌ 未建模 | ❌ 未建模（灵活就业是否可参保待确认） |
| 深圳 | ✅ 20%（同上） | ❌ 未建模（一档医疗） | ❌ 未建模（无雇工个体工商户经营者可参保，见 `references/regions/shenzhen.md:49-57`） |

**阻塞原因**：广东医保费率权威源 **粤医保规〔2022〕2号** 正文为图片附件且站点反爬，此前两次尝试（沙箱抓取、用户浏览器）均未取得可核验文本。

**引擎影响面（已确认，降低本任务风险）**：

- `monthly_medical_contribution` / `monthly_unemployment_contribution` 为可选输出，缺失按 0 计（`application/calculate_months.py`），补入不改变引擎逻辑。
- 广深是**城市层单包**结构（同天津/重庆），适配器 `policy_queries` 已含 `flexible_employment_contribution` @ CN-4401 / CN-4403 → **本任务无需改适配器**（区别于六城那批需加城市层查询）。
- `evals/evals.json` 未对广深断言 run_id（只有北京 golden 重放断言），包内容变更不会造成重放回归。

---

## 二、Step 0：来源可行性调研（只读，不产生任何修改）

按"梯子"逐级尝试，**任一级取得可核验来源即进入 Step 1**；全部失败则进入 Step 2。

| 级 | 路径 | 手段 | 先例 |
|---|---|---|---|
| L1 | 政府公报文本版（广东省政府公报 / 广州市政府公报 / 深圳市政府公报）转载粤医保规〔2022〕2号全文 | `scripts/webget.py`（OpenSSL 通道）+ web_search 定位 | 国发〔2005〕38号 → 福建省政府公报文本版（本项目已用） |
| L2 | 市级医保局政策解读 / 办事指南 / 12333 问答（`ylbz.gz.gov.cn`、`hsa.sz.gov.cn`）中的费率数值 | 同上，取 HTML 文本 | 武汉 6%、成都 9.5% 均出自问答页 |
| L3 | 税务局缴费标准公告（广东省税务局 / 广州、深圳税务）灵活就业费率表 | 同上 | 天津 8.5% 出自医保局+税务局联合通知 |
| L4 | 区级政府转发文本（越秀/天河/南山/福田等 `*.gov.cn`） | 同上 | 杭州萧山区、武汉武昌区、重庆沙坪坝区先例 |
| L5 | 法规库镜像取全文 + gov.cn 权威 URL 交叉标注 | 同上；来源记录中明确标注"镜像交叉核验" | 天津 tj-subsidy-standard 先例（law.esnai.cn 镜像） |
| L6 | **图片附件直读**：下载 gov.cn 图片附件字节 → 用多模态读图逐字转录 | 见下方"L6 技术说明" | 本项目尚未尝试（此前判定为"不可核验"的是 OCR 路径） |

### L6 技术说明（此前未尝试的新路径）

- 阻塞点历史记录为"反爬 + 图片"，其中"图片不可读"这一半可解：本机 `Read` 工具可直接读取 jpg/png 并转录中文正文。
- 缺口在下载环节：`scripts/webget.py` 以 `decode("utf-8","replace")` 处理响应体，**二进制图片会被破坏**。
- 处理方式（二选一，请在审批时指定）：
  - **(i) 临时探针（默认推荐）**：在 scratchpad（工作区之外）写一次性下载脚本，带 `Referer`/`User-Agent` 头取图片字节 → 落到 scratchpad → `Read` 转录。**不改动仓库任何文件。**
  - **(ii) 固化能力**：给 `scripts/webget.py` 增加 `--binary` 参数（写字节不解码），作为沙箱能力的长期资产，并在 `docs/sandbox-capabilities.md` 补一节。属仓库修改，需一并批准。
- **纪律约束**：图片转录得到的数值，必须满足下列之一才允许进包——(a) 与另一独立来源（L1-L5 任一）数值一致；(b) 用户人工确认。否则按"存疑不进包"处理，只写入 references 的待核验清单。

### Step 0 产出

一份调研结论（会话内汇报，不落盘）：每个数值（广州医疗费率、广州失业适用性、深圳一档医疗费率、深圳失业费率）标注"已取得可核验来源 / 仅有存疑线索 / 无来源"，并附 URL、文号、原文摘录。**取得结论后暂停，等你确认是否进入 Step 1。**

---

## 三、Step 1：落包（仅对 Step 0 中取得可核验来源的数值执行）

严格套用六城医疗那批的既有流程与文件形状（`policy-data/packages/hangzhou-flex-medical.json` 为模板）。

### 1. 新增来源记录 `policy-data/sources/`

| 文件（按实际取得的来源命名） | 内容 |
|---|---|
| `gd-medical-rate-2022.json` 或 `gz-medical-rate-*.json` | 广州灵活就业职工医保费率来源 |
| `sz-medical-rate-*.json` | 深圳一档医疗费率来源 |
| `sz-unemployment-rate-*.json` | 深圳失业费率来源（若可参保且有费率） |
| `gz-unemployment-not-applicable.json` | 若官方明确广州灵活就业不缴失业保险（对应天津先例，属"事实：不适用"） |

每条含 URL / 发文机关 / 文号 / 发布日期 / authority_level / locator / `source_digest`（= references 章节正文规范化 SHA-256，由测试重算校验）。

### 2. 证据档案 `references/regions/`

- `guangdong.md`：新增 `## 来源：<source_id>` 区块（含原文摘录 + 工程解释）——若来源为省级文件。
- `guangzhou.md` / `shenzhen.md`：新增对应区块——若来源为市级文件。
- 更新 `shenzhen.md:56-57` 的"尚未取得可核验数值"表述为已核验结论（或缩小为剩余未核验项）。

### 3. `policy-data/source-digests.json`

新增对应摘要条目（与 references 章节正文一致，测试重算）。

### 4. 规则包（**修改既有包，不新建包**）

| 文件 | 新增规则 | 形状 |
|---|---|---|
| `policy-data/packages/guangzhou-flex-employment.json` | `guangzhou-flex-medical-contribution`（+ 视情况 `guangzhou-flex-unemployment-contribution`） | `POLICY_RULE`：input `contribution_base` → `MULTIPLY(base, rate)` → `monthly_medical_contribution`；`parameters.medical_rate`；`test_vectors` 覆盖基数下限与 5000 口径 |
| `policy-data/packages/shenzhen-flex-employment.json` | `shenzhen-flex-medical-contribution`、`shenzhen-flex-unemployment-contribution` | 同上；若深圳医疗为固定月额（一档按全市在岗平均工资固定比例），改用 `PARAMETER_TABLE` + 固定金额，形状比照 `chongqing-flex-employment.json` |

两包同时：`provenance` 增补新来源、`effective_from` 按文件施行日、**重算 `content_digest`**（用既有引擎算法，不手写）。

### 5. 适配器与 schema

**预期无改动**（广深单包 + 既有查询已覆盖）。若 Step 0 结论显示深圳医疗/失业需拆成独立包（例如施行日期不同导致双时态冲突），则改为新增 `shenzhen-flex-medical.json` 并在 `adapters/regions/shenzhen.py` 加一条查询——此分支会在 Step 1 开始前书面告知并重新确认。

### 6. 测试与夹具

- `tests/policy/test_official_packages.py`：自动覆盖新规则（schema / 摘要 / provenance / 向量），预期用例数增加。
- `evals/fixtures/golden-{guangzhou,shenzhen}-flex-2026.json`：输入不变，输出金额变化，人工核对月缴合计。
- 若 `tests/adapters/test_regions.py` 对广深查询结构有断言，同步核对（预期不变）。

---

## 四、Step 2：全部来源路径失败时（需要你提供材料）

若 Step 0 六级全部失败，我会停在这里，并向你提出**最小材料请求**：

1. 粤医保规〔2022〕2号 正文（PDF / Word / 截图 / 复制的文本任一），或
2. 广州市医保局、深圳市医保局关于灵活就业人员缴费费率的任一公开页面**文本内容**，或
3. 你人工核验后的数值 + 出处（文号 + URL + 施行日期），由我按 Step 1 落包并在来源记录中标注"用户提供、URL 权威、沙箱未直连"。

在此之前，广深维持现状（医疗/失业按未覆盖=0，属"部分能力"，SKILL.md 边界已声明），**不做任何猜测性建模**。

---

## 五、验证门禁（Step 1 完成后）

- `python -m pytest tests/policy/test_official_packages.py -q` 全绿（用例数增加）
- `python -m pytest tests/e2e/test_skill_contract.py -q` 17 passed
- `python -m pytest -q` 全量绿（当前基线 **606 passed**，本次预期 +4~+8）
- 广深 `analyze` 端到端 success，人工核对医疗/失业月缴数值与费率×基数一致
- **北京 golden run_id 仍为 `run-a7440a1a294cbdb2464f039f6a61e96d496cc1d5aa88c594c66b879602375d59`**
- `python scripts/policy_expiry_report.py` 无新增 EXPIRED

## 六、记录

- `CHANGELOG.md` 新增"广深医疗/失业费率补齐（任务 1-B）"章节
- `docs/execution-log-2026-08-14-skill-polish.md` 追加执行记录（含 Step 0 调研结论与每个数值的来源级别）
- 新建 `docs/change-record-2026-08-14-gd-rates.md`（比照上一份修改记录的表格形式）

---

## 七、风险与边界

| 风险 | 处置 |
|---|---|
| 图片转录出错（数字看错） | 强制交叉核验（另一来源或用户确认）才进包；否则只入 references 待核验清单 |
| 镜像站文本与原文不一致 | 沿用天津先例：来源记录写 gov.cn 权威 URL，locator 注明镜像交叉核验路径 |
| 深圳医疗分档（一档/二档/三档）口径混淆 | 只对"灵活就业可参加的一档"建模，其余档次作为 `parameters` 备选值记录，不进 results（比照重庆一档/二档处理） |
| 费率有年度调整（如 2026 新政） | 按双时态填 `effective_from`；若发现新文件覆盖 2022 号文，以新文为准并在 references 说明沿革 |
| 广州失业保险灵活就业不适用 | 按天津先例建"不适用"事实来源，不建费率规则 |

**明确不做**：无来源的费率估算、按"广东省平均水平"推断广深数值、把商保/大病补充混入基本医疗费率。

---

## 八、审批请求

请选择：

- **(a) 批准 Step 0 + Step 1**（推荐）：先只读调研，取得可核验来源后按既有纪律落包；L6 图片路径用 **临时探针(i)**，不动仓库。
- **(b) 批准 Step 0 + Step 1，且同意固化 `webget.py --binary`**（含 (ii) 的仓库修改与沙箱文档更新）。
- **(c) 仅批准 Step 0**：调研完汇报，落包另行审批。
- **(d) 暂不执行**：等你提供粤医保规〔2022〕2号 材料后再走 Step 1。
