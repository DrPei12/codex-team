# Accepted design decisions

[English](13-decisions.md) · [简体中文](13-decisions.zh-CN.md)

The current definition and these accepted decisions guide implementation. Historical decisions retain their original context in Git history.

| Decision | Rationale and effect |
|---|---|
| D-070: Codex-only, across task domains | The platform stays specific; methods and validation follow the assignment. The plugin core has no third-party skill or plugin dependency. |
| D-071: Natural communication and evolving definition | Models choose useful ways to communicate. Adopted ideas enter the coherent definition proactively; working notes and original history preserve continuity. |
| D-072: Autonomous execution and progressive planning | Overall responsibility remains clear. Work, attempts, acceptance and sessions stay separate; plans evolve as evidence arrives. |
| D-073: Durable adaptive runtime | SQLite commands, native execution, readable queues, scoped revisions and evidence-bound acceptance form the runtime foundation. |
| D-074: Temporary local coordination | An existing member can receive a bounded work scope, revise its organization, accept other members' results, and return responsibility. It cannot enlarge its own authority or approve its own produced result. |
| D-075: Stable identity and independent progress | Member identity survives role changes. A session can switch between execution and coordination; replacement preserves a handoff. Disjoint changes rebase, while affected active work waits for a stable boundary. |
| D-076: Workspace occupancy and external operation identity | Cross-state workspace claims remain held through unknown execution. External writes use a stable action record and target observation before any retry. |
| D-077: English-first bilingual distribution | The GitHub tree contains the product source, installable bundle, tests and current English/Chinese documentation. Historical playground material leaves the current tree and remains in Git history. |
| D-078: Budget reservations and exact recovery | Dispatch reserves budget transactionally. Unknown execution retains its reservation. Recovery verifies native session, turn, project, workspace and execution policy before releasing occupancy. Explicit revocation interrupts the temporary coordination turn while other members continue. |
| D-079: Organizational changes preserve delivery intent | Member transfers close orphaned coordination grants. Local consolidation retains the original goal and criteria in a proposal for overall coordination; newly added work carries its scope criteria. Abandoned workspace claims are reclaimed only after checking the owning run's execution and controller state. |
| D-080: Conversation-first release and deferred project workspace | Remove both local web interfaces and their commands from the product and bundle. Codex conversation and CLI remain the current interaction surface. A future project workspace will show live member activity, readable collaboration, assistance requests and results, and support project-level discussion and direction changes across sessions. |
| D-081: One Team entrypoint and one runtime | Retire the six phase skills, manifest router and Auto 0.2 controller from current source and distribution. Planning, execution, review, integration, recovery and delivery remain internal capabilities selected by the model. Preserve adaptive schema 0.3 records, shared reliability mechanisms and historical releases. |

Completing a delegated scope cancels its queued coordination turn. Failed local coordination remains retryable within the repair policy, then returns responsibility to overall coordination with the original results intact.

D-074 through D-079 were adopted on September 15, 2026 under the user's formal-release delegation. Release version and project-definition version are maintained separately. Native sessions are the execution unit in the current release; local coordination uses the same configured model and resource policy as other work.

D-081 was adopted on September 19, 2026.
