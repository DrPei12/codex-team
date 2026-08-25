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

The milestone result references exact Gate, review, and audit bytes. It lists
archive candidates and unique workspace actions, but every workspace action is
`retain` with `authorized=false`. Cleanup and archive are never implied by
milestone completion and must be separately authorized.
