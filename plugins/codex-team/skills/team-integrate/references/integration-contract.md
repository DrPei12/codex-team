# Team integration contract

## Candidate

An integration candidate binds one implementer lane to its exact clean branch,
base, HEAD/tree, owned changed files, passed worker-preflight receipt, worker
report, and evidence hash. Candidate creation is read-only. Out-of-ownership or
dirty workspaces fail before an artifact is written.

## Plan

The integration plan consumes a manifest-bound status snapshot. Candidate lanes
must be `handoff-ready` or already `accepted`; dependencies must be planned
earlier in the same plan or already accepted/integrated/reviewed. The plan also
freezes the Integrator workspace HEAD/tree, candidate order, changed-file set,
and global Gates. Its authorization flags remain false.

## Apply

`apply` requires `--allow-git-mutation` and revalidates the plan, candidates,
and Integrator workspace before merging. It uses the manifest order and writes
an exclusive receipt with before/after identity and each merge result. A merge
failure is aborted and recorded; the helper does not guess a resolution or
continue with later candidates.

## Gates

`run-gates` requires `--allow-command-execution`, binds commands to the exact
post-apply commit/tree, writes per-Gate logs and hashes, and stops on the first
nonzero exit. It does not retry, invoke sealed evaluation, push, or interpret a
failed Gate as a successful integration.
