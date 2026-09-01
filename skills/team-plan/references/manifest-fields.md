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
| `workspace_policy` | Absolute experiment/worktree/artifact roots and clean-start policy. Roots must stay under `experiment_root`; mutable lane workspaces stay under `worktree_root`. |
| `contract` | Frozen source, invariants, and forbidden changes. |
| `requirements` | Machine-checkable coverage lattice. Each item binds a requirement id/statement, whether it is a frozen invariant, `change` or `verification-only` implementation kind, non-reviewer owner lanes, concrete owned paths, Gate ids, and one reviewer lane. Every frozen invariant must appear exactly once. A change requirement needs concrete paths with exactly one listed writable owner after forbidden deny rules; a verification-only requirement has no writable path but still needs an owner, Gate, and reviewer. |
| `checkpoints` | Stage boundaries with `after_lanes`, gated `before_lanes`, covered requirement ids, acceptance owner, required evidence, and mandatory accepted-state resume policy. Checkpoint evidence is later recorded in immutable status facts. |
| `user_locale` | The language/locale of user-facing task titles, such as `zh-CN`. It guides title authoring; the validator enforces only safe BCP-47-like syntax, not semantic language detection. |
| `lanes` | Each lane’s role, execution surface, user-facing title, lifecycle, objective, `requirement_ids`, explicit `does_not_cover`, configurable `progress_policy`, dependencies, workspace, ownership, inputs, outputs, gates, and stop conditions. `progress_policy` sets manifest-specific heartbeat and turn budgets with `checkpoint-stop`; Team does not provide universal time constants. `visible-task` lanes require a concise single-line `task_title` in the user’s language; the prompt remains a separate artifact. `internal-subagent` lanes use `task_title: null` and must be `one-shot`. Lifecycle is `one-shot`, `milestone`, or `long-lived-owner`. Reviewer lanes are read-only, directly review an integrator, and may share only that integrator’s exact workspace and base revision. Ownership paths are canonical repository-relative patterns: separators become `/`, Windows matching is case-insensitive, and a bare path owns that path plus every descendant. Explicit glob syntax is also supported; `*` and `?` stay within one path segment, while `**` can cross segments. `forbidden_paths` use the same matcher and always override `write_paths`. Plan, integrate, and recover share these rules. |
| `integration_order` | Each lane exactly once, after every dependency. |
| `global_gates`, `global_stop_conditions` | Run-wide evidence gates and stop conditions. |

Canonical bytes use UTF-8 JSON with `ensure_ascii=false`, sorted keys, and no
whitespace separators. The manifest reference is `sha256:<64 lowercase hex>`.
