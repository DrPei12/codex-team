# Team v0.1 workflow map

## Main path

`team-plan -> team-run -> team-status -> team-integrate -> team-finish`

`team-recover` is entered only from a blocked or failed fact. It freezes the
old run and prepares a new bounded successor; it never changes the old result.

## Canonical router inputs

The router recognizes these single-file names inside one run directory:

- `preregistration.json`, `parent-preflight-receipt.json`, `dispatch-bundle.json`
- `status-facts.json`, `status-snapshot.json`
- `integration-plan.json`, `integration-apply.json`, `gate-receipt.json`
- `review-receipt.json`, `finish-audit.json`, `milestone-result.json`
- `recovery-candidate.json`, `recovery-plan.json`, `recovery-brief.json`

Integration candidates are the plain JSON files in `candidates/`. A phase may
produce other filenames for experiments or historical evidence, but the router
does not guess which duplicate is authoritative. Promote an accepted artifact
to its canonical name before relying on automatic routing.

## Authority boundaries

A route to task creation, integration apply, Gate execution, successor task
creation, archive, or cleanup is only a recommendation. The route artifact sets
all authority flags to false. The current user must separately authorize any
state-changing action not already within the task's explicit scope.
