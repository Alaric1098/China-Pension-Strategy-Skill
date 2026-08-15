# 修改记录（任务 1-A 医疗费率补齐 + 任务 2 计发月数表核验）

生成时间：2026-08-14 本会话收尾

## 一、任务 2：计发月数表核验（age=47 修正）

| 文件 | 动作 | 说明 |
|---|---|---|
| `policy-data/packages/national-pension-benefit.json` | 修改 | age-47 行 207→208（decision_row + 测试向量两处）；provenance 增补 guofa-2005-38-text-fj；content_digest 重算 |
| `policy-data/sources/guofa-2005-38-text-fj.json` | 新增 | 福建省政府公报文本版来源记录（zfgb.fj.gov.cn，国发〔2005〕38号） |
| `references/national-rules.md` | 修改 | 新增 `## 来源：guofa-2005-38-text-fj` 章节 |
| `policy-data/source-digests.json` | 修改 | 新增 guofa-2005-38-text-fj 摘要条目 |

## 二、任务 1-A：六城灵活就业医疗费率补齐

### 直辖市包（修改，包内新增 medical 规则 + provenance + digest 重算）

| 文件 | 规则 | 费率/数值 | 来源 |
|---|---|---|---|
| `policy-data/packages/tianjin-flex-employment.json` | tianjin-flex-medical-contribution | 0.085×基数 | tj-medical-rate-2026（津医保局税务局 2026-03-09） |
| `policy-data/packages/chongqing-flex-employment.json` | chongqing-flex-medical-contribution | 一档固定 256.25/月（二档 563.75 备选参数） | cq-medical-rate-2025（渝医保发〔2024〕47号） |

### 省份层城市新增城市层医疗包（新增文件）

| 文件 | 规则 | 费率 | 来源 |
|---|---|---|---|
| `policy-data/packages/hangzhou-flex-medical.json` | hangzhou-flex-medical-contribution | 0.095 | hz-medical-rate-2022（杭医保〔2022〕41号） |
| `policy-data/packages/chengdu-flex-medical.json` | chengdu-flex-medical-contribution | 0.095 | cd-medical-rate-2025（成医保办〔2025〕17号+问答） |
| `policy-data/packages/wuhan-flex-medical.json` | wuhan-flex-medical-contribution | 0.06 | wh-medical-rate-2022（武汉市医保局问答） |
| `policy-data/packages/nanjing-flex-medical.json` | nanjing-flex-medical-contribution | 0.08 | nj-medical-rate-2023（南京市发布会） |

### 新增来源记录（policy-data/sources/）

| 文件 | 摘要 |
|---|---|
| `policy-data/sources/tj-medical-rate-2026.json` | `sha256:5767f495c95d54fd19166131ac1a5461a85cfce0361e422efc7608b3561a8986`（已与 reference 章节正文一致） |
| `policy-data/sources/cq-medical-rate-2025.json` | `sha256:c2feb2ff17fdae8e54a008bf88ab2cdad1902c670ead82575a5d87b91d5a8e8c`（已与 reference 章节正文一致） |
| `policy-data/sources/hz-medical-rate-2022.json` | `sha256:a0700533095a5243666583afa7ed71b0812ce9947d02beaee9d38e6294245e64`（已与 reference 章节正文一致） |
| `policy-data/sources/cd-medical-rate-2025.json` | `sha256:fc0615fb26937b8ce9e3ac0e92af7f958adb41e6a8dd6777a92c5bde2ee71d97`（已与 reference 章节正文一致） |
| `policy-data/sources/wh-medical-rate-2022.json` | `sha256:f5bb99406894f1cc7a5dfd2eb01bd9342d123d01d6f68def373927001ffbc313`（已与 reference 章节正文一致） |
| `policy-data/sources/nj-medical-rate-2023.json` | `sha256:74de64f247300f4f8e28fda53df13784e72b4cff094f8bcd8c20719caadb2d6d`（已与 reference 章节正文一致） |
| `policy-data/sources/tj-unemployment-not-applicable.json` | `sha256:ff1e52a4fbcaa989be344dce2bf11bcc146167acc34eb7c200fe9ffe339753a5`（已与 reference 章节正文一致） |

### 证据档案章节（references/regions/*.md，各新增一个 `## 来源：` 区块）

| 文件 | 新增来源区块 |
|---|---|
| `references/regions/tianjin.md` | tj-medical-rate-2026、tj-unemployment-not-applicable |
| `references/regions/chongqing.md` | cq-medical-rate-2025 |
| `references/regions/zhejiang.md` | hz-medical-rate-2022 |
| `references/regions/sichuan.md` | cd-medical-rate-2025 |
| `references/regions/hubei.md` | wh-medical-rate-2022 |
| `references/regions/jiangsu.md` | nj-medical-rate-2023 |

### 适配器（修改：policy_queries 增加城市层 contribution 查询，省份养老 + 城市医疗双层）

| 文件 | 新增查询 jurisdiction |
|---|---|
| `src/china_pension_strategy/adapters/regions/hangzhou.py` | CN-3301 |
| `src/china_pension_strategy/adapters/regions/chengdu.py` | CN-5101 |
| `src/china_pension_strategy/adapters/regions/wuhan.py` | CN-4201 |
| `src/china_pension_strategy/adapters/regions/nanjing.py` | CN-3201 |

### 测试更新

| 文件 | 变更 |
|---|---|
| `tests/adapters/test_regions.py` | 省份层查询结构断言改为双层（省份层养老 + 城市层医疗） |

## 三、验证结果

- 官方包测试（tests/policy/test_official_packages.py）：194 passed
- 契约测试（tests/e2e/test_skill_contract.py）：17 passed
- 区域适配器测试（tests/adapters/test_regions.py）：9 passed
- 全量 pytest：606 passed（此前 582，新增 24）
- 北京 run_id 不变：run-a7440a1a294cbdb2464f039f6a61e96d496cc1d5aa88c594c66b879602375d59
- 各城医疗月缴（5000 基数）：天津 442.00 / 重庆 256.25 / 杭州 475.00 / 成都 475.00 / 武汉 300.00 / 南京 400.00

## 四、遗留事项（任务 1-B）

- 广深医疗/失业费率（粤医保规〔2022〕2号）为反爬图片附件，沙箱无法核验；待用户提供文件内容或人工核验后补包。
