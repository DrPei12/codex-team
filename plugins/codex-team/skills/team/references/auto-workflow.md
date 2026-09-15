# Team Auto

Use this reference for a natural-language engineering request or an existing
Auto state directory. The separate legacy workflow remains in workflow-map.md.

## Locate the controller

Resolve the directory containing `team/SKILL.md` from the loaded skill location,
never from the user's current working directory. In a built plugin, `AUTO` below
means the absolute path to its `scripts/team-auto.py`. In the source repository,
it means the absolute path to the repository's `scripts/team-auto.py` (two levels
above the skill directory). Quote paths containing spaces. The wrapper locates
its own runtime; do not set PYTHONPATH or copy runtime code into the project.

Use Python 3.12 and an installed official Codex CLI with working existing login.
The App Server protocol is experimental and capability observations are local
evidence, not a portability guarantee. If launcher discovery fails, inspect the
installed CLI and set `CODEX_TEAM_CODEX` to its native executable. Do not install
another skill/plugin or provision an API key to make Auto work.

Choose an absolute `STATE` directory outside the target repository and retain it
for every command on the same run. It contains the transactional state, append-only
events, worktrees, and evidence. Use the established state path when continuing;
starting another directory loses continuity. `REPO` is the inspected target Git
repository. Never place control data in product source or edit SQLite directly.

`python -B AUTO --help` is a safe import and command-discovery check; it does not
call a model. Global `--state STATE` precedes the subcommand.

## Goal to a real run

1. Write the user's goal, constraints, acceptance criteria, and authorized stopping
   point to a UTF-8 brief file at an absolute path. Preserve scope; avoid substituting
   a sample project or forcing multiple sessions. If resource choices matter,
   prepare a policy JSON with supported finite settings using current CLI/runtime
   validation. Runtime defaults are local experiment choices, not universal advice.
2. Run `python -B AUTO --state STATE propose --repo REPO --brief-file BRIEF`.
   Optional `--answers-file ANSWERS` and `--policy-file POLICY` accept JSON files.
   This calls the real Codex planner and returns a persisted plan envelope.
   Present its objective, assumptions, allocation, ownership, Gates, resource
   limits, and checkpoint. Planning success is not execution success.
3. If `data.questions` is nonempty, obtain the missing consequential decisions,
   preserve the answers in JSON, and propose again with the same brief, repository,
   policy, and `--answers-file`. Use the new returned plan ID and digest. Do not
   treat elapsed time or unanswered questions as approval.
4. Compare the complete proposal with the user's existing authority. If it is
   covered, continue without asking the user to repeat permission. Otherwise
   present the concrete proposal and request only the missing authority. Freeze
   exactly the reviewed `data.digest`:
   `python -B AUTO --state STATE approve PLAN_ID --digest PLAN_DIGEST`.
   The returned run is authorized but has not started. Do not invent IDs/digests
   or approve a newer proposal using an older acceptance.
5. Execute `python -B AUTO --state STATE run RUN_ID`. Keep its process alive with
   the available terminal/session mechanism and observe output. It waits for a
   terminal state; tool timeout or detachment alone does not prove the controller
   or background worker remains alive. Track the actual process and persisted state.

## Observe, collaborate, and recover

Report progress and respond to user direction in the Codex conversation using the
saved runtime state, notes, original history and artifact receipts.

- `snapshot RUN_ID` returns recorded state and events; omitting the ID shows all
  plans/runs. `watch RUN_ID` observes without starting another dispatch.
- `request RUN_ID FROM_PACKAGE TO_PACKAGE QUESTION` records a collaboration
  request; `answer RUN_ID REQUEST_ID ANSWER` resolves it.
- `steer RUN_ID PACKAGE_ID MESSAGE` records corrective direction. Read current
  state and ownership before steering; messages are not an alternate source of truth.
- Use the saved work notes and searchable original history to recover context.
  Notes summarize navigation; verify important decisions and outcomes against the
  underlying events and artifact receipts. Package IDs, attempts, Codex thread
  identities, and plan/run IDs are distinct. App Server sessions are not promised
  to appear as Desktop sidebar tasks.
- `notes RUN_ID PACKAGE_ID` reads the current working note; `history RUN_ID QUERY`
  searches original events. Use `--package PACKAGE_ID` to narrow the query.
- `reconcile RUN_ID` verifies native idle state, remaining terminals, source identity,
  and the last durable observation after a controller interruption. Unknown outcomes
  remain blocked; do not mark them completed by hand.
- `supervise RUN_ID` independently checks direction at a stopped checkpoint.
  `replace-session RUN_ID PACKAGE_ID --reason REASON` transfers an unfinished package
  only after its interruption receipt, source snapshot, and working note validate.
- `limits RUN_ID --policy-file POLICY --digest DIGEST` records an explicit resource
  amendment for a stopped run. `requalify RUN_ID` checks an updated interpreter while
  preserving its predecessor evidence; neither action makes old tests pass on new bytes.
- `pause RUN_ID`, `resume RUN_ID`, and `cancel RUN_ID` use persisted controller
  transitions. Check acknowledgement and residual process status; a pause request
  is not proof every command has stopped. After a restart, inspect the same STATE
  and resume the known run rather than generating duplicate plans or dispatches.

On missing authentication, unsupported protocol, conflicting ownership/identity,
unverifiable evidence, or exceeded resource limits, report the actual error and
preserve state. Repair only within authorized scope and finite runtime budgets.
Never fabricate successful Gates, manually mark a run complete, or erase a failed
attempt to enable retry. Optional project tooling failures affect that project's
Gate; they do not justify changing Team's core dependency contract.

## Stop at the checkpoint

Read the target revision, Gate receipts, independent review, unresolved requests,
and final state. `awaiting-user` means evidence is ready for acceptance, not already
accepted. Apply the agreed acceptance policy; if user acceptance is required,
present the concrete result and wait for it. Then use the current snapshot's
`checkpoint_digest` with `python -B AUTO --state STATE accept RUN_ID --digest DIGEST`.
Acceptance verifies that evidence binding and stops; it does not authorize the
next milestone, publication, installation, cleanup, or deletion of user artifacts.
Report what ran, what passed, exact evidence locations, and remaining limitations.

## Reproducible invocation

For a user who has authorized implementing a CLI feature through its tests, write
that goal to an absolute brief file, choose an external state directory, and run
`propose`. Inspect the returned proposal and carry the authorized scope through
`approve` and `run`; use `snapshot` and original artifact receipts to inspect the result.
For a read-only packaging check, run `--help` and the bundled
`bundle-self-check.py` only; neither invokes Codex. This distinguishes a portable
runtime check from evidence of an actual engineering run.
