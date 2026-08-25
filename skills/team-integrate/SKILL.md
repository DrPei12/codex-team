---
name: team-integrate
description: Use after worker handoffs are manifest-bound and handoff-ready to validate candidates, prepare ordered integration, and—only with explicit authorization—apply Git merges and run integration Gates.
---

# Team Integrate

Validate proof-carrying worker handoffs and preserve the manifest integration
order. Preparing a plan is read-only; Git merges and Gate commands are separate
explicitly authorized actions.

## Workflow

1. Build one candidate from each handoff-ready implementer workspace:

   `python scripts/team-integrate.py candidate MANIFEST --run-dir RUN_DIR --lane LANE --report REPORT --evidence EVIDENCE --out CANDIDATE`

2. Prepare an ordered plan from a status snapshot and candidate directory:

   `python scripts/team-integrate.py prepare MANIFEST --run-dir RUN_DIR --status SNAPSHOT --candidates CANDIDATES --out PLAN`

3. Stop and request explicit user authorization before Git mutation. Only after
   authorization may an orchestrator run:

   `python scripts/team-integrate.py apply MANIFEST --run-dir RUN_DIR --plan PLAN --receipt RECEIPT --allow-git-mutation`

4. Stop again before executing project commands. Only after explicit
   authorization may the declared integration Gates run:

   `python scripts/team-integrate.py run-gates MANIFEST --run-dir RUN_DIR --plan PLAN --apply-receipt APPLY_RECEIPT --receipt GATE_RECEIPT --allow-command-execution`

Read [integration-contract.md](references/integration-contract.md) when
interpreting candidate identity, dependency ordering, apply receipts, or Gate
failure behavior.

## Boundaries

Do not create or message Codex tasks, modify worker worktrees, auto-resolve
conflicts, push, merge main, run sealed evaluators, or retry failed Gates. A
failed apply or Gate remains a stopped artifact and must be handled by a new
recovery decision.

## Verification

- `python -B tests/test_team_integrate.py`
- `python -B tests/test_team_status.py`
- `python -B tests/test_team_run.py`
