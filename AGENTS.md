# Contributor and agent instructions

[English](AGENTS.md) · [简体中文](AGENTS.zh-CN.md)

This repository targets Codex. Task domains can vary; the execution platform stays specific. Add no other-platform adapter or required third-party skill/plugin dependency.

Authority order: the user's latest explicit instructions; accepted decisions in `docs/13-decisions.md`; the formal definition and design documents; templates and examples; temporary discussion conventions. Update decisions and the corresponding English/Chinese documentation when changing core concepts, protocols or lifecycle rules.

The primary task owns the overall plan, dependencies, assignments, integration and final conclusion. Work directly by default. Use subagents for necessary independent review or when the user explicitly requests them. Parallel work needs clear boundaries, file ownership, inputs, outputs and integration points. Each mutable file has one current owner. Prefer an isolated worktree for cross-module or high-risk changes.

Execution tasks receive the goal, scope, workspace, file responsibility, inputs, expected artifacts, acceptance criteria and reporting conditions. Versioned definitions, plans, state and artifacts hold shared facts. Messages carry discussion, notifications and references. Acceptance checks the actual revision, environment and evidence and reuses valid checks.

Preserve uncommitted work from the user and other tasks. Destructive resets and shared-history rewrites require explicit authorization. Handoffs retain the source revision, workspace status, changes, validation, remaining issues and continuation point. Worktrees isolate directories; semantic integration still needs verification.

Skills use progressive disclosure: clear metadata, a concise entrypoint and focused references/scripts. Each skill owns a clear capability. Maintain shared protocols centrally, along with triggering conditions, failure handling, reproducible examples and validation.

Completion requires the real artifact, relevant verification, locatable evidence and synchronized documentation. Distinguish established facts, observations, decisions and hypotheses. Report actual results. Runtime changes use native Codex validation of the affected product flow.
