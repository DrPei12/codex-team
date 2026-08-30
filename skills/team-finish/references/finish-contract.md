# Team finish contract

## Review

The review receipt binds one reviewer lane, decision, findings artifact, passed
Gate receipt bytes, and exact target commit/tree. `changes-requested` and
`rejected` decisions are valid review facts but cannot finalize a milestone.

## Audit

The finish audit rechecks the integration workspace against the Gate target and
reports four distinct boundaries:

- ordinary tracked/untracked status;
- ignored-file inventory;
- merge/rebase/cherry-pick/bisect operation residue;
- run-directory artifact inventory and hashes.

Ordinary or Git-operation residue blocks finish. Ignored residue is retained and
reported separately: it can produce `completed-with-ignored-residue` after all
functional Gates and review pass, but never `residue_free_checkout=true`.

## Final result

The milestone result references exact Gate, review, and audit bytes. It lists a
task disposition for every lane: visible one-shot/milestone tasks recommend
`archive`, visible long-lived owners recommend `retain`, and internal subagents
are `not-applicable`. All dispositions remain `authorized=false`; execution
requires a native task-lifecycle adapter with a before snapshot and rollback
mapping. Unique workspace actions remain `retain` and separately unauthorized.
Task archive never implies worktree or evidence cleanup.
