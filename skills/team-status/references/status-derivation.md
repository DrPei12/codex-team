# Team-status fact and derivation rules

`status-facts` stores observations. `status-snapshot` is a disposable projection
that can always be regenerated. Never copy a display status back into facts.

## Durable facts

Each lane records task identity/state, workspace observation, worker-report and
evidence references, acceptance, integration, review, blocker, and archive
facts. Referenced report/evidence files are hash-verified under the current run
directory so another run cannot satisfy this run's handoff. A task that is not
created cannot carry thread/project identity;
accepted and integrated facts require the earlier proof states.

Run validation also reconstructs every recorded worker-preflight argv from the
manifest, preregistration, brief, run directory, and lane role. A passed reviewer
receipt must carry the canonical dispatch and Gate refs plus the exact target;
the renderer revalidates the plan → apply → Gate → target chain before treating
that preflight as durable. Non-reviewer receipts cannot carry reviewer binding
fields.

## Display precedence

The renderer applies higher-risk facts first:

1. archived;
2. failed parent/worker preflight;
3. blocker, failed/canceled task, invalid evidence, rejected handoff, blocked
   integration, or changes requested;
4. reviewed, review pending, integrated, integrating, accepted;
5. handoff-ready or needs-evidence;
6. needs-input, no-signal, working, or preflight;
7. waiting-dependency, ready-for-dispatch, or planned.

This prevents an optimistic activity signal from hiding a failed Gate or review
decision.

## Dependencies

A not-created lane becomes `ready-for-dispatch` only after every dependency has
the durable fact `acceptance_state=accepted`. Display states such as `archived`
do not satisfy a dependency by themselves. An accepted dependency stays
satisfied if its task is later archived. The renderer therefore exposes only
genuinely accepted prerequisites instead of creating every planned task at once.

## Live adapter boundary

A future Codex-native adapter may read task/list/wait and Git state, then write a
new immutable `status-facts` artifact. The adapter owns observation; this skill
owns validation and derivation. Messaging, task creation, handoff, archive, and
recovery remain separate authorized workflows.
