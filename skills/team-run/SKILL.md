---
name: team-run
description: Use after team-plan has produced a validated manifest and briefs to prepare preflight receipts, runtime roots, and prompt/dispatch bundles before separately authorized Codex task creation.
---

# Team Run

Prepare a non-live Codex multi-task run from one validated manifest and its
machine-projected briefs. This skill creates local run artifacts only; it does
not dispatch work.

## Workflow

1. Confirm the manifest and brief directory are the accepted `team-plan`
   outputs. Do not reconstruct either from prose.
2. Prepare a new, absent run directory under the manifest artifact root:

   `python scripts/team-run.py prepare MANIFEST --briefs BRIEF_DIR --out RUN_DIR`

3. If preparation fails, stop. Input failures create no run directory;
   workspace failures preserve preregistration and a failed parent receipt but
   do not create prompts or a dispatch bundle. Never overwrite or relabel the
   failed run directory.
4. If preparation passes, inspect `dispatch-bundle.json` and hand it to an
   orchestrator that already has explicit authority to create Codex tasks.
   This skill stops before that action. The orchestrator creates a sidebar task
   only for `execution_surface=visible-task` and passes the separate
   user-language `task_title`; `internal-subagent` lanes stay inside the owning
   task and never create sidebar clutter.
5. A future real worker must run the `worker_preflight_argv` recorded for its
   lane from the assigned workspace. Implementation may begin only when the
   exclusive receipt reports `passed`. A reviewer lane's recorded argv
   includes `--gate-receipt`; after integration it must bind the current run's
   passed Gate receipt and its exact target commit/tree before review begins.
6. After preflight and before implementation, the worker copies the recorded
   backbrief template to the canonical input path, fills the first bounded
   action, discloses assumptions/open questions, and runs the recorded
   `worker_backbrief_argv`. Only a `passed` receipt authorizes implementation.
   `needs-input` stops for a new accepted brief/successor; requirement ids,
   ownership, Gates, and `does_not_cover` cannot be paraphrased away.

Read [preparation-artifacts.md](references/preparation-artifacts.md) when
inspecting the artifact meanings, prompt trust boundary, or failure behavior.

## Boundaries

Do not create, fork, hand off, archive, or message Codex tasks. Do not create
lane worktrees, implement product code, change the frozen contract, infer
effective model settings, or clean a failed evidence directory. A prepared
dispatch bundle is not proof that Desktop dispatch works.

## Verification

- `python -B tests/test_team_run.py`
- `python -B tests/test_team_plan.py`
