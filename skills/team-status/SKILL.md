---
name: team-status
description: Use to derive a reviewable Codex multi-task status snapshot and next actions from manifest-bound run artifacts and durable task facts without mutating tasks or workspaces.
---

# Team Status

Render project status from durable facts. Do not accept a worker's prose status
as the project truth, and do not store the derived display status back into the
facts artifact.

## Workflow

1. For a newly prepared `team-run` directory, initialize an immutable no-task
   fact snapshot:

   `python scripts/team-status.py init-facts MANIFEST --run-dir RUN_DIR --out FACTS`

2. A future authorized observation adapter may create a newer facts file with
   actual thread/project IDs, task state, report/evidence references,
   acceptance, integration, review, blocker, and archive facts. It must not edit
   an older facts file in place.
3. Render a new status projection:

   `python scripts/team-status.py render MANIFEST --run-dir RUN_DIR --facts FACTS --out SNAPSHOT`

4. Inspect lane reasons and next actions. A ready lane still requires explicit
   authority before task creation; a blocked or failed-preflight lane must stop.

Read [status-derivation.md](references/status-derivation.md) when adding a fact
collector, interpreting precedence, or changing dependency behavior.

## Boundaries

Do not create, message, wait on, hand off, archive, or rename Codex tasks. Do
not inspect live threads, run Git mutations, merge code, rewrite facts, or clean
workspaces. This v0.1 renderer proves artifact-to-status behavior only; live
Codex observations remain a separate future adapter and capability test.

## Verification

- `python -B tests/test_team_status.py`
- `python -B tests/test_team_run.py`
- `python -B tests/test_team_plan.py`
