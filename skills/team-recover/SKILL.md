---
name: team-recover
description: Use after a team phase is blocked or failed to freeze the exact useful candidate and evidence, then prepare one bounded, non-live successor recovery brief without rewriting the predecessor.
---

# Team Recover

Preserve a failed run as evidence and prepare one small successor attempt. This
skill does not retry the predecessor in place and does not create a Codex task.

## Workflow

1. Freeze either a clean descendant commit or the current owned dirty files:

   `python scripts/team-recover.py candidate MANIFEST --run-dir RUN_DIR --lane LANE --mode commit|dirty --out CANDIDATE`

2. Bind the failed predecessor, exact candidate, reusable proof files, one new
   fact, allowed paths and command budget:

   `python scripts/team-recover.py prepare MANIFEST --run-dir RUN_DIR --predecessor RESULT --candidate CANDIDATE --proofs PROOFS_DIR --new-fact FACT --command COMMAND --allow-path PATH --max-commands N --out PLAN`

3. Project the validated plan into a non-live recovery brief:

   `python scripts/team-recover.py project PLAN --out BRIEF`

Read [recovery-contract.md](references/recovery-contract.md) before deciding
which candidate mode to use or what qualifies as a new fact.

## Boundaries

Do not mutate or relabel predecessor artifacts, create or message Codex tasks,
execute the recovery commands, modify workspaces, merge Git, or expand the
allowed paths after planning. A recovery brief authorizes none of those actions.

## Verification

- `python -B tests/test_team_recover.py`
- validate generated artifacts with `schemas/team-recover-artifacts.schema.json`
