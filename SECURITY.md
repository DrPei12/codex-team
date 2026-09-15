# Security policy

[English](SECURITY.md) · [简体中文](SECURITY.zh-CN.md)

## Supported version

Security fixes target the latest release, **1.0.x**.

## Report a vulnerability

Use this repository's [private security reporting](https://github.com/DrPei12/codex-team/security/advisories/new). Include the affected version or commit, a minimal reproduction, the observed impact, and the permissions needed to reproduce it. Keep credentials, private project data, and exploit details in the private report.

## Areas to examine

- Work, execution, acceptance, and artifact identity.
- Workspace ownership, path containment, symlinks, and junctions.
- Private data in prompts, logs, artifacts, and release assets.
- Unintended external actions and ambiguous retry outcomes.
- Temporary coordination scope and native session recovery.
- Plugin bundle integrity.

Maintainers reproduce the reported behavior, assess its impact, and coordinate a fix and disclosure through the advisory.
