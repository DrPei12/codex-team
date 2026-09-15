# Adaptive Team execution

Use this for Codex Team 1.0 and adaptive state schema 0.3. Existing 0.2 Auto
records retain their controller and interpretation in auto-workflow.md.

## Locate the runtime and preserve context

Resolve `NEXT` to `scripts/team-next.py` beside the loaded `team/SKILL.md`. Use an
absolute, quoted path. The bundle includes the standard-library runtime; do not
copy it into the product or require another skill/plugin. Python 3.12+ and an
installed, authenticated official Codex CLI are required. `python -B NEXT --help`
loads no model. Set `CODEX_TEAM_CODEX` only if native launcher discovery fails.

Choose a persistent absolute `STATE` outside the product `WORKSPACE`. Record it in
the project's working notes. Use it for every continuation. The workspace can be
a normal document directory; Git is optional. Never edit Team's SQLite by hand.

Understand the user's intent in the current conversation. Maintain the full
definition, current working notes and links to original decisions; do not funnel
the conversation through a scripted questionnaire or invoke a second planner just
to restate a goal already understood. Propose the organization with meaningful
reasons and tradeoffs. Ordinary authorized decisions need no repeated approval.

## Register a reviewed initial plan

Prepare UTF-8 files: `DEFINITION` with the coherent adopted goal, `AUTHORITY` with
the actual user's delegation and limits, and `PLAN` containing a JSON list of
initial work. Distant work may be added after investigation. Each work needs
`title`, `goal`, and `acceptance`; optional fields are `id`, `role`, `directory`
(relative to WORKSPACE, default `.`), `member` (stable identity, defaults to role), `writable` (default false), `depends_on`
(work IDs), `kind` (execution/assistance/review/repair), and `priority` (-100..100).
IDs and metadata can be generated; do not demand that the user fill this form.

A work's writable directory is its native sandbox boundary. Two overlapping
writable directories are scheduled sequentially. Give independent authors separate
directories when the result permits, and make integration an explicit responsibility.
Read-only investigations need neither commits nor executable test gates. Examples
are illustrations of the record shape, not a mandatory decomposition.

Prepare `POLICY` using `--help` and existing settings. Supported fields are model,
reasoning, max_sessions, max_subagents_per_session, max_turn_seconds,
max_run_seconds, max_repair_attempts, token_budget and network_access. Choose finite
values from the actual delegation, explain material assumptions, and include
coordination and verification in resource accounting. Choose the model and
capacity for the actual delegation. Team schedules native Codex sessions; set
max_subagents_per_session to 0. The default model is Luna/max.

Run `python -B NEXT --state STATE create --workspace WORKSPACE --definition-file
DEFINITION --plan-file PLAN --authority-file AUTHORITY --policy-file POLICY
--operation-id REQUEST_ID --title TITLE`. Reuse the request ID only for identical
retries. Record the returned run_id; creation has not started execution.

## Run, observe and respond to changes

Run `python -B NEXT --state STATE run RUN_ID` in a persistent terminal. It performs
real Codex work and returns completion or the actual waiting/stopped/unknown state.
Keep observing while it runs; an exec timeout does not prove the process stopped.
`snapshot RUN_ID` reads current facts; `list` finds existing adaptive runs.

Report progress in the Codex conversation using the snapshot and original history.
Explain current responsibilities, waiting reasons and verified results; provide
artifact references when the user asks to inspect an outcome.

Workers request assistance with the supplied Team tool. Requests queue; waiting
workers save notes and end the turn. The controller resumes eligible work after
the requested result has been accepted. A coordinator checks actual artifacts and
evidence, adjusts scoped work when necessary, and requests final completion.
The host checks that this final result actually meets the user's overall intent.

Members share information with team_message and request action with team_request.
Use team_propose to recommend a different division of work or offer temporary
coordination. The overall coordinator can adopt a proposal with team_delegate,
assigning an existing member a bounded list of work IDs. Local coordinators can
accept other members' results and revise work within that scope. They preserve
acceptance criteria and existing permissions. Their original native session can
continue in the temporary role, then return to execution. Coordination ends when
the scoped outcomes are accepted or team_return_coordination records the handback.

The runtime keeps unrelated work moving, rebases disjoint plan revisions, queues
requests to busy members, and ages queued work to prevent priority starvation.
Read/write conflicts wait for a stable workspace boundary. Workspace claims are
shared across Team state directories and remain held while execution is unknown.

Before an external write, use team_effect with a stable key and exact target and
description. Perform the action only when execute=true. Inspect the target and
record succeeded or not-applied with its receipt or observation. A lost response
requires observation of the original action. Unresolved actions block acceptance.

Use `message RUN_ID --file MESSAGE --operation-id ID` to record new user context.
When adopted intent changes the definition, preserve the original discussion and
use `revise RUN_ID --changes-file CHANGES --operation-id ID`; CHANGES contains
base_revision, reason, and optional add/update/definition. Read the current plan
revision first. Active affected work must reach a confirmed boundary; a full
definition change currently requires all active work to stop. Do not weaken the
goal to make a run finish or reopen accepted work; create justified successors.

## Recover and verify

`pause RUN_ID` and `cancel RUN_ID` record intent before stopping native work.
`reconcile RUN_ID` checks lost execution, background terminals and current files;
it never infers business completion from idle. Preserve unknown outcomes and
uncommitted work. After confirmed reconciliation, `run RUN_ID` continues the same
nonterminal run and creates new attempts without erasing failures.

`history RUN_ID QUERY --after CURSOR --limit N` retrieves original records with
pagination. Use targeted original evidence, not successive summaries alone. Native
web search can operate separately from shell network permissions; the actual
configuration and observations determine what was available.

Use `replace-session RUN_ID --member MEMBER --reason REASON` after confirming the
member stopped. The successor receives the current definition, notes, work,
result references and original history. The retired native session remains in
the handoff record. Use `delegate RUN_ID --member MEMBER --work WORK_ID --reason
REASON --operation-id ID` for an already-authorized host delegation; repeat --work
for each scope item. `return-coordination RUN_ID DELEGATION_ID --reason REASON`
returns that responsibility.

For stopped runs, `limits RUN_ID --policy-file POLICY --reason REASON
--operation-id ID` records a resource amendment under the user's existing scope.
Do not increase a user budget simply to bypass a stop. Account percentage and
observed native tokens have different meanings; preserve missing telemetry.

Result acceptance checks the registered content identity; quality and goal coverage
still require actual review. `accept RUN_ID WORK_ID --result-hash HASH --reason
REASON --actor operator` records a delegated operator's acceptance. Use actor user
only for the user's real acceptance. This does not imply the user personally saw
a UI. A stopped or partially verified run is not a completed deliverable.

Missing account access, unsupported native behavior, unknown in-flight actions or
unmet authority must be reported with the exact evidence and continue position.
Don't replace unknown actions with fabricated success, erase failed attempts,
silently resubmit external side effects, or promise unattended work without a
running controller. Preserve earlier valid results and avoid redundant tests.
