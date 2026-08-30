---
name: team-finish
description: Use after integration Gates and independent review to audit exact final Git/artifact state and produce a non-destructive milestone result with archive and cleanup recommendations.
---

# Team Finish

Close a milestone with exact Gate, review, Git, and residue evidence. This skill
records recommendations only; it never archives tasks or deletes workspaces.

## Workflow

1. Record the independent Reviewer decision against the passed Gate target:

   `python scripts/team-finish.py review MANIFEST --run-dir RUN_DIR --gate-receipt GATE_RECEIPT --reviewer-lane REVIEWER --decision DECISION --findings FINDINGS --out REVIEW_RECEIPT`

2. Audit the exact integration target and run directory:

   `python scripts/team-finish.py audit MANIFEST --run-dir RUN_DIR --gate-receipt GATE_RECEIPT --review-receipt REVIEW_RECEIPT --out AUDIT`

3. Finalize only when the Gate passed, review approved, and audit is
   `ready-to-finish`:

   `python scripts/team-finish.py finalize MANIFEST --run-dir RUN_DIR --gate-receipt GATE_RECEIPT --review-receipt REVIEW_RECEIPT --audit AUDIT --out RESULT`

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

## Verification

- `python -B tests/test_team_finish.py`
- `python -B tests/test_team_integrate.py`
