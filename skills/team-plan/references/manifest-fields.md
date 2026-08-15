# Manifest fields

Use one canonical `run-manifest` JSON document. The validator treats these
fields as the source of truth; briefs are projections and carry its SHA-256.

| Field | Meaning |
| --- | --- |
| `profile`, `schema_version`, `kind` | `codex-multitask-team-plan`, `0.1`, and `run-manifest`. |
| `run_id`, `created_at`, `status`, `objective` | Run identity, timezone-bearing ISO-8601 creation time, lifecycle, and goal. |
| `decision.parallel_groups` | A complete, non-overlapping partition of lane IDs; lanes in one group may neither depend on one another nor claim overlapping paths. |
| `base` | Repository, branch, 40-hex commit/tree, and clean-start identity. |
| `task_project` | UUID, local project path, and environment. |
| `workspace_policy` | Absolute experiment/worktree roots and clean-start policy. Every lane workspace must stay under `experiment_root`. |
| `contract` | Frozen source, invariants, and forbidden changes. |
| `lanes` | Each lane’s role, objective, dependencies, workspace, ownership, inputs, outputs, gates, and stop conditions. Reviewer lanes are read-only and have no write paths. |
| `integration_order` | Each lane exactly once, after every dependency. |
| `global_gates`, `global_stop_conditions` | Run-wide evidence gates and stop conditions. |

Canonical bytes use UTF-8 JSON with `ensure_ascii=false`, sorted keys, and no
whitespace separators. The manifest reference is `sha256:<64 lowercase hex>`.
