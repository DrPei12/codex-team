# Releases

[English](CHANGELOG.md) · [简体中文](CHANGELOG.zh-CN.md)

## 2.1.0 · September 19, 2026

- Check for published updates when Team starts or resumes, with automatic installation enabled by default for the official Git marketplace.
- Describe successful updates with concise English/Chinese experience improvements and new capabilities.
- Preserve auto/notify/off preferences, local development and pinned versions; cache checks and continue through network failures.
- Defer installation for active or unknown execution; verify release hashes, use native Codex installation and retain a rollback bundle and recovery receipt.
- Continue existing schema 0.3 projects through the updated runtime path.

**Upgrade:** users on 2.0 and earlier install 2.1 once to enable use-time checks. See the [upgrade guide](docs/usage.md#upgrade).

## 2.0.0 · September 19, 2026

- Make **Team** the sole plugin entrypoint for goal discussion, execution, steering and delivery.
- Retire the six phase skills, legacy manifest router, Auto 0.2 controller and their dedicated scripts, schemas, examples and tests.
- Unify runtime commands under `scripts/team.py` and `python -m team_runtime`.
- Preserve adaptive state schema 0.3, native collaboration, working notes, searchable history, resource controls, acceptance and recovery.
- Extract shared policy validation and native-event redaction into focused modules.
- Update English/Chinese guidance and release checks around the current runtime and single-entrypoint package.

**Upgrade:** existing adaptive runs from 1.0.x continue from their saved state. Early Auto/manifest records remain with their historical release. See the [upgrade guide](docs/usage.md#upgrade).

## 1.0.1

- Adopt the new Codex Team icon throughout plugin metadata and the repository home page.
- Remove the local web interfaces and their `serve` commands from source and the installable bundle.
- Keep progress, control, collaboration and original history available through Codex and the CLI.
- Move the project board to the roadmap: live member activity, readable collaboration, assistance requests, results and project-level direction changes.

## 1.0.0 · September 15, 2026

Codex Team brings adaptive collaboration to delegated goals in Codex, with a complete installable plugin and English/Chinese documentation.

- Natural conversation develops the definition and execution arrangement.
- Native Codex members execute, share readable findings, and queue assistance.
- Temporary local coordinators can revise their work scope, accept other members' results, and return responsibility.
- Member identity survives role changes; stopped sessions can be replaced with a preserved handoff.
- Disjoint plan revisions rebase, queue aging addresses prolonged waiting, and independent local coordination can run alongside execution.
- Workspace occupancy spans state directories and remains held through unknown execution.
- External action records preserve a stable identity and require target observation after a lost response.
- Result acceptance binds content and criteria; invalidation isolates affected dependencies.
- The repository includes the complete plugin bundle, source-to-bundle checks and regression suites.

The 1.0 release included the adaptive runtime alongside entrypoints for earlier record formats.
