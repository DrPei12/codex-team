---
name: team-finish
description: Use after integration Gates and independent review to audit exact final Git/artifact state and produce a non-destructive milestone result with archive and cleanup recommendations.
---

# Team Finish

## Bundled runtime

In commands below, resolve `<TEAM_SKILL_DIR>` to the absolute directory
containing the bundled `team/SKILL.md`. Never resolve it from the target
repository working directory.


Close a milestone with exact Gate, review, Git, and residue evidence. This skill
records recommendations only; it never archives tasks or deletes workspaces.

## Workflow

1. Record the independent Reviewer decision against the passed Gate target:

   `python <TEAM_SKILL_DIR>/scripts/team-finish.py review MANIFEST --run-dir RUN_DIR --gate-receipt GATE_RECEIPT --reviewer-lane REVIEWER --decision DECISION --findings FINDINGS --out REVIEW_RECEIPT`

2. Audit the exact integration target and run directory:

   `python <TEAM_SKILL_DIR>/scripts/team-finish.py audit MANIFEST --run-dir RUN_DIR --gate-receipt GATE_RECEIPT --review-receipt REVIEW_RECEIPT --out AUDIT`

3. Finalize only when the Gate passed, review approved, and audit is
   `ready-to-finish`:

   `python <TEAM_SKILL_DIR>/scripts/team-finish.py finalize MANIFEST --run-dir RUN_DIR --gate-receipt GATE_RECEIPT --review-receipt REVIEW_RECEIPT --audit AUDIT --out RESULT`

4. Inspect `task_dispositions`. Visible one-shot/milestone tasks become archive
   candidates, long-lived owners are retained, and internal subagents are not
   sidebar actions. A separately authorized orchestrator may execute the exact
   archive plan only after a before snapshot and rollback mapping; worktree
   cleanup remains a different action.

Read [finish-contract.md](references/finish-contract.md) when interpreting
cleanliness dimensions, ignored residue, archive candidates, or blocked finish.

## Boundaries

Do not rerun Gates, invoke sealed evaluation, merge or push Git, archive Codex
tasks, remove worktrees, delete ignored files, or rewrite a blocked audit.
Task dispositions and cleanup remain explicit future actions even after a
completed result. Archiving a task never authorizes removing its worktree or
evidence.

## Bundle verification

Run `python -B <TEAM_SKILL_DIR>/scripts/bundle-self-check.py` to verify
the packaged file inventory, SHA-256 bindings, and runtime imports.
