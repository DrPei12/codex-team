---
name: team
description: Use Team for delegated goals that need organized execution, readable collaboration, persistent project context, evidence and recovery in Codex; also continue existing Team runs.
---

# Team

## Bundled runtime

In commands below, resolve `<TEAM_SKILL_DIR>` to the absolute directory
containing the bundled `team/SKILL.md`. Never resolve it from the target
repository working directory.


Use this skill when the user asks Team to carry a goal through understanding,
planning and execution, or to continue, inspect, or finish a Team run. Ordinary
questions about teamwork or unrelated single-file edits do not require Team.

Keep the conversation natural. Offer substantive judgments and useful information;
choose prose, examples, questions or informed options according to the content.
Maintain a coherent project definition as clear user revisions and adopted ideas
emerge. Discuss the execution organization after understanding the goal; it is not
an entry-mode questionnaire. Investigate uncertain external facts with native web
search and preserve sources. Working notes navigate current work; original records
and actual artifacts carry the evidence.

## Choose the existing record

- New delegated goal or adaptive run: read
  [adaptive-workflow.md](references/adaptive-workflow.md). Use the plugin's own
  `team-next.py` runtime to register the understood definition and initial work,
  then execute and verify within existing authorization.
- Existing Auto 0.2 plan/run: use [auto-workflow.md](references/auto-workflow.md)
  and `team-auto.py`; preserve its original contract and evidence.
- Existing legacy manifest/run artifacts: use the route below. Do not reinterpret
  legacy artifacts as Auto state or silently migrate them.

Team's Python standard-library runtime uses the official Codex App Server and existing Codex authentication;
it requires no third-party skill, plugin, or model API key. A missing optional
project tool must not become a dependency of Team itself.

Keep current explicit execution authority in effect. Legacy preparation boundaries
do not cancel an authorized current run. Ask only for consequential missing intent
or authority beyond scope. Methods remain autonomous within assigned responsibility.
The runtime preserves work identities, queues action requests, records attempts and
separates result submission from acceptance. Its controls do not bypass the host.
Suggest organizational changes when the current division stops serving the goal.
Members can offer temporary local coordination. The overall coordinator delegates
an explicit scope, which ends when its outcomes are accepted or the responsibility
is returned. Keep member identity separate from changing roles.

## Legacy route

Run:

`python <TEAM_SKILL_DIR>/scripts/team.py route MANIFEST --run-dir RUN_DIR`

The router reads only canonical run artifacts and returns `next_skill`,
`next_action`, its evidence references, and whether separate authority is still
required. To persist a non-overwriting route receipt inside an existing run:

`python <TEAM_SKILL_DIR>/scripts/team.py route MANIFEST --run-dir RUN_DIR --out ROUTE`

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

## Bundle verification

Run `python -B <TEAM_SKILL_DIR>/scripts/bundle-self-check.py` to verify
the packaged file inventory, SHA-256 bindings, and runtime imports.
