# Contributing

[English](CONTRIBUTING.md) · [简体中文](CONTRIBUTING.zh-CN.md)

Start with the [project definition](docs/project-definition.md), [architecture](docs/architecture.md), and [accepted decisions](docs/13-decisions.md). Changes should improve how Codex Team understands a delegation, organizes work, or delivers a result.

The runtime uses Python 3.12+ and its standard library. Install `pytest` and `jsonschema` for development. Keep native model validation in a separate workspace and state directory; select its model and budget explicitly.

Edit `team_runtime`, `scripts`, and `skills`. Build a fresh plugin directory with:

```sh
python -B scripts/build-team-plugin.py --out /existing/parent/codex-team
```

Copy the generated bundle into `plugins/codex-team`, then run:

```sh
python -B scripts/check-release.py
```

The release check exercises runtime and compatibility tests, builds a fresh bundle, verifies its inventory and imports, and compares it with the checked-in distribution. Regression tests should exercise the actual state transition or user outcome. Native test doubles must be labeled and supplemented by real Codex validation for changes to execution behavior.

Keep English and Chinese public documentation aligned. Update the definition and decision log when changing concepts or lifecycle rules. Working notes and private validation outputs belong outside the distributable tree.

Open a pull request explaining the concrete problem, resulting behavior, and validation. Preserve existing work and failures. Use one explicit owner for each mutable file during concurrent work, and integrate against the actual resulting artifacts.
