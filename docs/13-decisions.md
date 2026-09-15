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

D-074 through D-078 were adopted on September 15, 2026 under the user's formal-release delegation. Release version and project-definition version are maintained separately. Native sessions are the execution unit in 1.0; local coordination uses the same configured model and resource policy as other work.
