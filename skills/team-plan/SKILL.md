---
name: team-plan
description: Use when a Codex multi-task run needs a manifest-driven lane plan before dispatch.
---

# Team Plan

Use this skill to prepare and validate a frozen, manifest-driven lane plan. First
check whether parallel work is worth the coordination cost and whether boundaries,
owners, inputs, outputs, and integration points are explicit.

Workflow:

1. Freeze the contract and record its invariants and forbidden changes.
2. Generate one canonical JSON manifest with the base identity, lane graph,
   parallel groups, workspaces, ownership, gates, and stop conditions. Read
   [manifest-fields.md](references/manifest-fields.md) for the compact field map.
3. Run the validator before any dispatch:
   `python scripts/team-plan.py validate MANIFEST`
4. After a passing validation, project immutable lane briefs from that same
   manifest:
   `python scripts/team-plan.py project MANIFEST --out DIR`
5. Dispatch only the already-defined lanes through the surrounding orchestrator,
   preserving the manifest digest and ownership boundaries.

Do not create tasks, fork or message workers, implement code, change the frozen
contract, or invent lane data in this skill. Stop on validation failure or an
identity, ownership, dependency, workspace, or output-directory conflict.
