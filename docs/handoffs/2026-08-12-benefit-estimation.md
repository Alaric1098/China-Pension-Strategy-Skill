# China Pension Strategy Handoff

## Resume Point

Implementation is paused during Task 1 of the approved plan. Resume from:

- Project: `C:\Projects\Workspace\China-Pension-Strategy`
- Plan: `docs/plans/2026-08-12-benefit-estimation.md`
- Current task: Task 1, evidence archive
- Todo state: Task 1 `in_progress`; Tasks 2-6 `pending`

The plan has already undergone multiple reviewer passes. Do not redesign it before reading the current file and the evidence corrections below.

## Suggested Skills

- `executing-plans`: continue Tasks 1-6 from the approved plan.
- `agent-reach`: only if additional official-source research is needed.
- `verification-before-completion`: before claiming any task or feature complete.
- `finishing-a-development-branch`: required by the execution workflow at final completion, although this directory is not a git repository.

## Changes Already Applied

- `src/china_pension_strategy/domain/policy.py`
  - `_AUTHORITY_LEVELS` now includes `PROVINCIAL_HRSS`, `MUNICIPAL_GOVERNMENT`, and `MUNICIPAL_HRSS`.
- `schemas/policy-package.schema.json`
  - `authority_level` enum now includes the same three values.
- `tests/domain/test_policy.py`
  - Added a parametrized acceptance test for the three new authority levels.
  - Added explicit rejection coverage for `PRIVATE_BLOG`.
- `tests/contracts/test_schemas.py`
  - Added parametrized schema acceptance coverage for the three new authority levels.
- `docs/plans/2026-08-12-benefit-estimation.md`
  - Source set corrected to 12 records.
  - Added separate `beijing-2024-16-base` source for 2024 base `11883`.
  - `beijing-2025-13-base` now supports only 2025 base `12049`.
  - Replaced MOF URL with verified MOHRSS URL for 人社部发〔2017〕31号.
  - Replaced dead Jinan URL with the live 2025-06-12 Jinan hotline article.
  - Yiwu source now explicitly records its incorrect `2025年度` label and treats 2.62% as the 2024 annual rate with a source-defect warning.
  - Xuchang/Yueyang table links remain engineering cross-check URLs, not separate source records.

No source JSON, reference evidence sections, or digests have been created yet.

## Critical Evidence Corrections

Use these corrected sources rather than earlier notes:

- Monthly divisor practice:
  - `https://www.jinan.gov.cn/col23076/art/2025/art_23076_5018027.html`
  - Published `2025-06-12`, source `热线办` / 济南市12345市民服务热线办公室.
  - Explicitly states non-integer retirement ages use the month-level table after 2025-01-01; examples: 60y1m=`138.4`, 50y1m=`194.6`.
  - This is local handling corroboration, not national normative authority.
- Interest method:
  - `https://www.mohrss.gov.cn/SYrlzyhshbzb/zhengcefabu/bumenjianzhang/zcjd/201704/t20170425_270902.html`
  - 人社部发〔2017〕31号, made `2017-04-13`, published `2017-04-25`.
- Numeric interest disclosure:
  - `https://www.yw.gov.cn/art/2025/6/3/art_1229134300_4228894.html`
  - Page literally says `2025年度...2.62%`, but the national annual sequence identifies 2.62% as the 2024 rate.
  - Store executable `rate_year=2024`, `rate=0.0262`; retain and flag the source defect. Do not infer a verified 2025 rate.
- Beijing bases:
  - 2024 `11883`: `https://rsj.beijing.gov.cn/xxgk/2024zcwj/202412/t20241224_3972825.html`, 京人社发〔2024〕16号.
  - 2025 `12049`: `https://www.beijing.gov.cn/zhengce/zhengcefagui/202511/t20251107_4265441.html`, 京人社发〔2025〕13号.
  - Do not attribute 11883 to the 2025 source.
- Beijing Order 183 portal date conflict:
  - Operative text and publication date indicate `2006-12-14`; portal metadata also shows conflicting `2006-12-24`. Record the text-supported date and flag the metadata conflict.

## Next Exact Actions

1. Read the current Task 1 source table in `docs/plans/2026-08-12-benefit-estimation.md` and verify no stale source names remain.
2. Write evidence sections using established `## 来源：<source_id>` format:
   - `references/national-rules.md`: 7 new sections.
   - `references/regions/beijing.md`: 5 new sections.
3. Compute each section digest exactly as `canonical_source_digest()` in `tests/policy/test_official_packages.py`:
   - strip trailing whitespace per line;
   - strip final whitespace;
   - append exactly one newline;
   - SHA-256 UTF-8; prefix `sha256:`.
4. Create 12 matching `policy-data/sources/*.json` records and append all 12 values to `policy-data/source-digests.json` without altering existing entries.
5. Run authority/schema tests first:
   - `python -m pytest tests/domain/test_policy.py tests/contracts/test_schemas.py -q`
6. Run official-package evidence tests excluding the expected source-usage failure until Task 3 creates the new packages. The full `test_every_source_record_is_used_by_at_least_one_package` cannot pass immediately after Task 1 because the new source records are not yet referenced by packages.

## Source IDs For Task 1

- `npc-delay-decision-2024`
- `mohrss-elastic-2024-94`
- `guofa-2005-38`
- `guoban-2019-13`
- `mohrss-2017-31-interest`
- `jinan-payment-months-2025`
- `interest-rate-disclosure-2025`
- `beijing-order-183-2006`
- `beijing-2007-21`
- `beijing-2007-31`
- `beijing-2024-16-base`
- `beijing-2025-13-base`

## Verification Constraint

The workspace is not a git repository. Do not run worktree or commit steps. Preserve unrelated concurrent changes. Use `apply_patch` for manual edits.

## Interrupted Operation

A `docs-manager` task intended to append the 12 evidence sections was launched in parallel with a plan edit, but the task call was aborted. The plan edit succeeded; assume the documentation agent made no changes and verify before proceeding.
