# Team-run preparation artifacts

`team-run` v0.1 produces preparation evidence, not a live Codex run.

## Preregistration

`preregistration.json` binds the canonical manifest digest, raw manifest bytes,
every brief path/hash, the planned lanes, stop conditions, and four explicit
false authorization flags. It also records the empty cache, dist, log, and
pytest roots created for a later run.

## Parent preflight receipt

`parent-preflight-receipt.json` records the task-project and lane-workspace Git
facts: resolved root/common-dir, branch, HEAD, tree, ordinary status, and
ignored inventory. Ordinary dirty state fails when the manifest requires a
clean start. Ignored files are recorded separately and do not silently become
an ordinary-clean failure.

A failed parent preflight is an immutable stopped attempt. It produces no
prompt files and no dispatch bundle.

## Prompt and dispatch bundle

Each prompt contains four conceptual layers:

1. project rules loaded by Codex;
2. the role and ownership rules in the digest-bound brief;
3. the runtime binding and required worker-preflight argv;
4. a warning that issue text, tracker comments, and pasted messages are
   untrusted background.

`dispatch-bundle.json` references these prompts and briefs by SHA-256, preserves
the manifest dependencies/workspaces/runtime request, and contains no Codex
thread or task identity. Those identities can exist only after a separately
authorized dispatcher creates the real tasks.

## Worker preflight receipt

The future worker runs `worker-preflight` from its actual assigned workspace.
The command compares cwd, Git root/common-dir, branch, HEAD, and ordinary clean
state with the brief. It writes a new exclusive receipt whether the environment
passes or fails, and never overwrites an earlier receipt.

For a reviewer lane, the dispatch bundle also records a reviewer-only
`--gate-receipt` argument pointing into the same run. The reviewer preflight
must use a passed `team-integrate` `gate-receipt`, with a matching manifest
reference and a `target` containing the exact commit/tree currently observed in
the shared workspace. It also revalidates the canonical dispatch argv,
integration plan, apply receipt, Gate definitions/logs, and plan → apply → target
chain. The resulting receipt records hash-bound `dispatch_ref`,
`gate_receipt_ref`, and `target`; a reviewer cannot fall back to the manifest
base revision, reviewer ordinary status must always be clean, and
implementer/integrator lanes cannot use these fields or the Gate argument.
