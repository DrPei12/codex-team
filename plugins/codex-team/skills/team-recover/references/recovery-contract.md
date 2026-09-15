# Team recovery contract

## Immutable predecessor

A failed, blocked, changes-requested, preparation-failed, or preflight-failed
artifact is a historical fact. Recovery references its exact bytes and status;
it never edits the file to make the old run appear successful.

## Exact candidate

Use `commit` only for an ordinary-clean descendant of the lane base revision.
The candidate binds the commit, tree, and changed paths. Use `dirty` when useful
owned files are not committed. The candidate then binds Git status, a binary
patch for tracked changes, and a deterministic ZIP snapshot for present files.
Both modes reject changed paths outside the lane's declared write ownership.

## One new fact and bounded attempt

The successor must state one non-empty fact that makes another attempt
meaningfully different. It also freezes reusable proof hashes, allowed commands,
allowed paths, and a maximum command count. Those fields describe a possible
future task; they do not grant authority to create it, run commands, or mutate a
workspace. A future executor must stop on the first nonzero command.

## Projection integrity

Before creating a recovery brief, projection rechecks the exact predecessor,
candidate, and proof bytes named by the plan. Replacement or tampering therefore
fails closed instead of silently changing the proposed successor.
