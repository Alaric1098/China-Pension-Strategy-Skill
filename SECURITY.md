# Security Policy

## Scope

This project is a local, deterministic pension-calculation skill at
`LOCAL_MVP` status. It is not production software: it does not host user
data, does not receive requests over a network, and stores no credentials.
The attack surface is limited to files a user feeds to the CLI on their own
machine.

## Supported versions

Security fixes are released on the latest tagged release and on `main`.
Older releases receive fixes only when the same defect is reproducible on a
supported version; we do not promise patch releases for outdated versions.

## Reporting a vulnerability

Do not open a public issue and do not paste personal data into any public
discussion. Report privately through GitHub Security Advisories:

<https://github.com/Alaric1098/China-Pension-Strategy-Skill/security/advisories/new>

Include:

- the affected release, tag, or commit;
- a minimal synthetic reproduction (never real personal data);
- the exact local commands and inputs used;
- expected and observed behavior.

Public channels must never receive real or derived personal data: identity
numbers, social-security numbers, bank account numbers, phone numbers,
verification codes, query serial numbers, or benefit statement extracts.
Tests, fixtures, issues, and pull requests use only synthetic records
constructed from scratch.

## Handling

1. Acknowledge the report.
2. Triage and reproduce with synthetic data only.
3. Fix on `main` and ship with the next tagged release.
4. Disclose publicly only after a fix is available.
