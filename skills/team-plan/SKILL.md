---
name: team-plan
description: Use when a Codex multi-task run needs a manifest-driven lane plan before dispatch.
---

# Team Plan

Use this skill to prepare and validate a frozen, manifest-driven lane plan. First
check whether parallel work is worth the coordination cost and whether boundaries,
owners, inputs, outputs, and integration points are explicit.

For every lane, decide whether it needs a user-visible durable task or a short
internal subagent. Visible tasks require a concise title in the user's current
language; never use the task prompt or a machine lane id as the sidebar title.
Record whether the lane is one-shot, milestone-scoped, or a long-lived owner so
finish can recommend the correct lifecycle action.

Workflow:

1. Freeze the contract and record its invariants and forbidden changes.
2. Build a requirement coverage lattice before lane dispatch. Every frozen
   invariant and delivery requirement must bind exactly one writable owner for
   each concrete path, one or more Gates, and a reviewer. Reject ownership
   orphans and objectives that require a lane's forbidden path.
3. Generate one canonical JSON manifest with the base identity, lane graph,
   parallel groups, workspaces, ownership, requirement coverage, stage
   checkpoints, per-lane progress policy, gates, and stop conditions. Read
   [manifest-fields.md](references/manifest-fields.md) for the compact field map.
4. Run the validator before any dispatch:
   `python scripts/team-plan.py validate MANIFEST`
   If validation fails, fix only the manifest from the concrete error and run the validator again. Stop when identity or a required fact is missing, or when the same error repeats.
5. After a passing validation, project immutable lane briefs from that same
   manifest:
   `python scripts/team-plan.py project MANIFEST --out DIR`
6. Stop after project succeeds, then hand the manifest, digest, and brief
   directory to the already-authorized orchestrator, preserving ownership
   boundaries.

Do not create or dispatch tasks, fork or message workers, implement code, change
the frozen contract, or invent lane data in this skill. The authorized
orchestrator owns dispatch and implementation after this skill stops.
