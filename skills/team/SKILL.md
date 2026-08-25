---
name: team
description: Use as the unified Codex-only entry point for a manifest-driven multi-task run; route verified repository artifacts to team-run, team-status, team-integrate, team-finish, or team-recover without performing the phase itself.
---

# Team

Use this skill first when the user asks to start, continue, inspect, integrate,
finish, or recover a Codex multi-task run. It selects one phase; the selected
phase skill remains responsible for validation and execution.

## Route

Run:

`python scripts/team.py route MANIFEST --run-dir RUN_DIR`

The router reads only canonical run artifacts and returns `next_skill`,
`next_action`, its evidence references, and whether separate authority is still
required. To persist a non-overwriting route receipt inside an existing run:

`python scripts/team.py route MANIFEST --run-dir RUN_DIR --out ROUTE`

Read [workflow-map.md](references/workflow-map.md) for the phase boundaries and
canonical artifact names.

## Delegate to one phase

- `$team-plan`: create and validate the manifest and lane briefs.
- `$team-run`: prepare preregistration, preflight receipts, prompts, and the
  non-live dispatch bundle.
- `$team-status`: record supplied facts and render derived status.
- `$team-integrate`: freeze candidates, prepare/apply the ordered integration,
  and run declared Gates with explicit authority.
- `$team-finish`: bind independent review, audit final state, and record the
  milestone without cleanup.
- `$team-recover`: freeze a failed candidate and prepare one bounded successor.

## Boundaries

Routing never creates or messages Codex tasks, executes Gate commands, mutates
Git, archives tasks, cleans workspaces, or treats a recommendation as authority.
Do not skip a phase helper's own hash, identity, ownership, or precondition
checks merely because the router selected it.

## Verification

- `python -B tests/test_team_router.py`
- `python -B tests/test_team_v01.py`
