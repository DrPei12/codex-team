# How Codex Team works

[English](architecture.md) · [简体中文](architecture.zh-CN.md) · [Home](../README.md)

## One public entrypoint

The Team skill handles goal discussion, execution, steering and delivery. Its focused runtime reference describes operations the model selects as work develops. The script `scripts/team.py` and `python -m team_runtime` call the same CLI. Planning and completion tools are internal capabilities, with no separate phase skills or alternate controllers. State schema 0.3 is independent of release numbering and remains readable across this upgrade.

## Understanding comes before organization

The entrypoint runs in the user's Codex conversation. It develops the assignment into a coherent project definition, investigates missing facts, and recommends an execution arrangement. It carries clear revisions and adopted ideas into that definition. Working notes record the current position; the original history preserves the reasoning and evidence behind it.

The conversation determines the organization. Research, implementation, review, and integration become work items when they have a useful outcome or handoff. A simple assignment can reuse one native member for execution and overall coordination. More independent work can use additional members within the same resource policy.

## Four distinct identities

| Record | Purpose |
|---|---|
| Work | A goal, criteria, dependencies, responsibility and current state. |
| Member | A stable participant whose role can change across assignments. |
| Attempt | One actual native execution, with session/turn identity and its outcome. |
| Acceptance | A decision that a specific result satisfies its criteria, with rationale and content identity. |

A failed attempt stays in history. A replacement session continues the same work from current notes, definition and artifacts. A result becomes a dependency only after acceptance.

## Adaptive responsibility

Every run retains overall coordination responsibility for the goal and delivery. Members can communicate directly and propose changes to the division of work. The overall coordinator can delegate an explicit work scope to an existing member.

The local coordinator can inspect and accept other members' results, revise scoped work, and add follow-up work within the delegated directories and write permissions. It preserves acceptance criteria and cannot extend its own delegation. It cannot accept a result produced by its own member identity. Scope completion closes the delegation automatically; an explicit return records why responsibility ended earlier.

Roles are not permanent job titles. A member's native session can move from investigation into a read-only coordination turn, then back into its next authorized execution. Session replacement preserves a handoff record rather than erasing the member's history.

## Model judgment and program responsibility

Models determine the meaning of the assignment, the usefulness of collaboration, the appropriate methods, and the quality of outcomes. The runtime handles the durable records and deterministic transitions that make those judgments actionable.

`team_message` shares information. `team_request` creates queued assistance. `team_propose` records an organizational suggestion. `team_delegate` grants local responsibility. `team_change` versions the work plan, while `team_accept` binds a result and `team_finish` requests final delivery. Tool permissions are checked against the currently active responsibility.

## Dispatch and coordination

The scheduler checks dependencies, member availability, directory conflicts, stop intent and resource policy. Requests to busy members queue without steering their current turn. Queue aging raises the position of eligible work that has repeatedly waited. Local coordination in an independent directory can proceed alongside other execution; overall coordination requires stable read access to the project.

Plan revisions identify affected work. A stale revision can be rebased when its referenced work and definition have not changed. A revision touching changed or active work waits for review or a confirmed execution boundary. Accepted evidence remains attached to the version it supported; invalidation marks the affected dependency descendants for review.

## Durable state and recovery

SQLite transactions commit state, events, dispatch records and command receipts together. Repeated commands with the same identity return their recorded receipt; a reused identity with different content conflicts. Dispatch intent is saved before native work starts. Session binding is saved before turn start.

A controller lease identifies the process currently coordinating dispatch. Lease expiration alone does not clear native execution. Reconciliation queries the native session and background terminals, records the observation, and preserves the current files before continuing.

A per-user workspace registry coordinates occupancy across Team state directories. Overlapping projects cannot start independent controllers against the same physical workspace. Occupancy remains held through unknown execution and is released after confirmed settlement or reconciliation. The registry lives at `~/.codex-team/workspaces.sqlite3`.

## External actions

Before a native external write, a member records a stable action key, target and description through `team_effect`. The first reservation permits one attempt. Further reservations of that identity direct the member to inspect the target. A response lost after the action is handled by observing the existing operation, then recording `succeeded` or `not-applied` with evidence. Unknown outcomes block acceptance of the affected work and final delivery.

The ledger stores operation identity and observations; the actual service is accessed through the native tool available to the member under the user's authority. Target-specific receipts, idempotency keys and status queries supply the evidence.

## Context and visibility

The current definition, responsibilities, accepted results and recent messages form the execution brief. Members add working notes and retrieve original events with a literal query and cursor. Large artifacts remain addressable by content hash. The Codex conversation uses CLI snapshots and history queries to report progress and expose the underlying receipts.

## Use-time release updates

The Team skill invokes the bundled updater when a conversation starts or resumes. The updater checks the official GitHub stable release, caches availability and saves the user's auto/notify/off preference. Release highlights are descriptive data shown once per change. Only compatible releases within the same major version update an unpinned official Git installation automatically.

Downloads and file hashes are verified before the native Codex `plugin/install` call. A shared SQLite read lock protects controllers; installation acquires an exclusive lock and checks the cross-state workspace registry, including older controllers and unknown executions. The installer runs while that registry is locked. A preserved old bundle and independent installation journal support observed recovery and rollback. The registered marketplace and project state stay in place; Team switches to the returned installed skill and runtime paths.

## Source map

| Source | Responsibility |
|---|---|
| `adaptive.py` | Work, attempts, acceptance, plan revisions and control. |
| `coordination.py` | Proposals, scoped delegation, handoffs and action records. |
| `adaptive_runner.py` | Native Codex sessions, dynamic tools and scheduling. |
| `workspace_claims.py` | Occupancy shared across state directories. |
| `store.py` | SQLite transactions, events, receipts and revision checks. |
| `policy.py` | Resource settings and finite limit validation. |
| `redaction.py` | Credential redaction in native observations. |
| `cli.py` | Persistent runtime commands used from Codex. |
| `updates.py` | Published release checks, preferences, native installation and recovery. |
| `skills/team` | Natural-language entrypoint and runtime guidance. |

All runtime modules are under [`team_runtime`](../team_runtime). The installable plugin bundles these modules and the entrypoints under [`plugins/codex-team`](../plugins/codex-team).
