<!-- Public pull requests must never contain real or derived personal data. -->

## What and why

Describe the user-visible behavior and the smallest supported scope.

## Version and replay impact

- Package version:
- Engine semantics version (`ENGINE_SEMANTICS_VERSION`):
- Schema changes:
- Ruleset changes:
- Golden values / `run_id` changes (expected digests and why):

## Evidence

For policy changes, attach the authoritative source URL (HTTPS on `gov.cn`),
issuing authority, document number, publication and retrieval dates, exact
quotation, jurisdiction, and the digest-chain entries updated.

## Privacy

- [ ] Uses only synthetic data; contains no real or derived personal data (identity numbers, social-security numbers, bank account numbers, phone numbers, verification codes, or benefit statement extracts).
- [ ] No `runs/`, JSONL logs, caches, or local paths are included.

## Local gates

- [ ] `python -m pytest -q`
- [ ] `python -m ruff format --check .`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy src/china_pension_strategy`
- [ ] `python verify_design_docs.py`
- [ ] `python test_design_contracts.py`
- [ ] `python audit_architecture.py --gaps`
