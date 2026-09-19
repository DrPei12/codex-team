# Install and use Codex Team

[English](usage.md) · [简体中文](usage.zh-CN.md) · [Home](../README.md)

## Install

Use Python 3.12+ and an authenticated Codex CLI. Confirm both commands are available:

```sh
python --version
codex --version
codex login status
```

If Codex is not installed, follow the [Codex CLI installation guide](https://developers.openai.com/codex/cli). Sign in with `codex login`.

Install the marketplace and plugin:

```sh
codex plugin marketplace add DrPei12/codex-team
codex plugin add codex-team@codex-team-local
```

For a local checkout:

```sh
git clone https://github.com/DrPei12/codex-team.git
cd codex-team
codex plugin marketplace add .
codex plugin add codex-team@codex-team-local
```

Run `codex plugin list` to inspect installation. Open a new Codex task so the installed Team entrypoint loads. Select **Team** from the skill picker; its qualified name is `codex-team:team`.

## Give Team an outcome

Start with the goal, relevant materials, and any limits that matter. You can begin with an idea or a detailed specification.

> $team Build a command-line importer for these CSV files. It should validate input, write to SQLite, and preserve existing data on failure. Use Luna/max with at most two simultaneous sessions. Create the implementation, tests, and a short usage guide.

Team investigates the available information and develops a coherent definition. It explains its recommended organization before execution, using your existing authorization. You can refine the audience, scope, priorities, or delivery conditions in the same conversation.

The model creates the internal records and runtime commands. You do not need to write a JSON plan to use the plugin.

## Follow and steer the work

Ask Team in Codex to report progress, explain current responsibilities and waiting work, inspect results, pause, continue, or revise the plan. Team reads the saved state and retrieves the original messages, decisions and artifact receipts relevant to your question.

Ask Team to pause to stop dispatch and request interruption of active native work. Ask it to continue to resume a stopped run. After a controller interruption, Team uses `reconcile` to check native sessions and background execution, preserve the current files, and prepare the same run to continue.

Keep the state directory with the project records. It contains `team.sqlite3` and content-addressed artifacts; place it outside the deliverable workspace. The controller runs while its terminal process is running.

## Runtime commands for developers

From a source checkout, use `scripts/team.py`. An installed plugin carries the same script under `skills/team/scripts`; Team resolves its absolute installed path.

```sh
python -B scripts/team.py --state /absolute/path/to/state list
python -B scripts/team.py --state /absolute/path/to/state snapshot RUN_ID
python -B scripts/team.py --state /absolute/path/to/state run RUN_ID
python -B scripts/team.py --state /absolute/path/to/state pause RUN_ID
python -B scripts/team.py --state /absolute/path/to/state reconcile RUN_ID
python -B scripts/team.py --state /absolute/path/to/state history RUN_ID "source decision"
```

On Windows, a state path can be `D:/TeamState/my-project`. Quote paths containing spaces.

For programmatic registration, `create` reads a definition, authority, initial work list, and resource policy from UTF-8 files. Run `--help` and `create --help` for the exact interface. A work item needs a title, goal, and acceptance criteria. Member identity, role, directory, write access, dependencies, and priority describe its execution context.

`delegate` assigns bounded local coordination. `return-coordination` closes it. `replace-session` preserves a stopped member's handoff record and creates fresh context on its next assignment. `revise` records scoped plan changes, and `message` records new user input. Team normally manages these commands from the conversation.

## Models and resources

The default model is `gpt-5.6-luna` with reasoning `max`. Set model, reasoning effort, concurrent session capacity, run duration, turn duration, repair attempts, observed token budget, and network access for the assignment. Coordination uses the same configured model and resource policy as execution. Team 2.0 schedules independent native sessions; `max_subagents_per_session` is `0`.

The runtime reserves part of the remaining token budget for each in-flight execution, tracks native usage notifications, and pauses when an allocation or elapsed-time limit is reached. Completed executions release their unused reservation; unknown executions retain it through reconciliation. Native token reports include cached input and arrive during execution. An account percentage budget is monitored through Codex account usage separately, because account usage includes other tasks. Set `CODEX_TEAM_CODEX` to the Codex executable when automatic launcher discovery needs an explicit path; `CODEX_TEAM_PYTHON` selects the Python executable used for native checks.

## Upgrade

Pause active Team runs and wait for their execution to stop. Refresh the marketplace and install the current plugin:

```sh
codex plugin marketplace upgrade codex-team-local
codex plugin add codex-team@codex-team-local
```

Open a new task after upgrading and continue from the original state directory. Codex replaces the cached plugin during installation, so the previous controller must have stopped first.

Version 2.0 exposes only **Team**. The six phase skills and the Auto 0.2 controller have been retired. Planning, status, recovery, integration and delivery remain available through the Team conversation.

Existing adaptive records from 1.0.x retain state schema 0.3, run IDs, artifacts and history. Team opens them with `scripts/team.py`; no data conversion is required. Developer integrations should replace the former adaptive launcher with this path or use `python -m team_runtime` from a source checkout.

Earlier Auto 0.2 and manifest records belong to their original release. Keep their state directories and use the corresponding [historical version](https://github.com/DrPei12/codex-team/releases/tag/v1.0.1) when inspecting those records. To carry an early project forward, bring its adopted definition, notes and verified artifacts into a new Team project. The upgrade preserves saved data and does not reinterpret old execution state.

## Troubleshooting

| Message or symptom | Action |
|---|---|
| Team is absent from the picker | Check `codex plugin list`, then open a new task. |
| Codex launcher is unavailable | Install/sign in to Codex and check `CODEX_TEAM_CODEX`. |
| Python cannot run in native execution | Point `CODEX_TEAM_PYTHON` to an accessible Python 3.12+ interpreter. |
| The project is waiting | Inspect queued work, proposals, results awaiting acceptance, and the latest controller error. |
| Workspace held by another run | Pause/reconcile the run named in the message, then continue the intended run. |
| External action outcome is unknown | Check the named remote target and record the original action's outcome. |
| A result changed after submission | Inspect the change and arrange verification of the current artifact. |
