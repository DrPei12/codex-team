---
name: team
description: Use Team Auto for natural-language Codex engineering goals, proposals, authorized execution, live status, and checkpoints; preserve the legacy router for existing manifest-driven runs.
---

# Team

Use this skill when the user asks Team to carry an engineering goal through
planning and execution, or to continue, inspect, or finish a Team run. Ordinary
questions about teamwork or unrelated single-file edits do not require Team.

## Choose the existing run or Auto

- Natural-language goal without a legacy manifest, or an existing Auto plan/run:
  read [auto-workflow.md](references/auto-workflow.md) and use Team's own
  `team-auto.py` controller. Generate a real proposal, resolve necessary
  questions, then approve and run within the user's current authorization.
- Existing legacy manifest/run artifacts: use the route below. Do not reinterpret
  legacy artifacts as Auto state or silently migrate them.

Auto is a mode of this skill, not an additional skill. Its Python standard-library
runtime uses the official Codex App Server and existing Codex authentication;
it requires no third-party skill, plugin, or model API key. A missing optional
project tool must not become a dependency of Team itself.

Keep current explicit execution authority in effect. Legacy non-live preparation
boundaries do not cancel an authorized Auto run. Review the concrete proposal
against that authority before freezing its digest; ask only for missing decisions
or authority beyond the agreed scope. Neither mode bypasses environment approval.

## Legacy route

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

The legacy router never creates or messages Codex tasks, executes Gate commands, mutates
Git, archives tasks, cleans workspaces, or treats a recommendation as authority.
Do not skip a phase helper's own hash, identity, ownership, or precondition
checks merely because the router selected it.

## Verification

- `python -B tests/test_team_router.py`
- `python -B tests/test_team_v01.py`
- `python -B tests/test_auto_package.py`
