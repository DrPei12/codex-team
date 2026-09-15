#!/usr/bin/env python3
"""Build a deterministic, relocatable Codex Team plugin with its own runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


PLUGIN_NAME = "codex-team"
PLUGIN_VERSION = "0.3.0"
ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = (
    "team",
    "team-plan",
    "team-run",
    "team-status",
    "team-integrate",
    "team-finish",
    "team-recover",
)
RUNTIME_SCRIPTS = (
    "team-next.py",
    "team-auto.py",
    "team.py",
    "team-plan.py",
    "team-run.py",
    "team-status.py",
    "team-integrate.py",
    "team-finish.py",
    "team-recover.py",
)
RUNTIME_SCHEMAS = (
    "team-plan-manifest.schema.json",
    "team-run-artifacts.schema.json",
    "team-status-artifacts.schema.json",
    "team-integrate-artifacts.schema.json",
    "team-finish-artifacts.schema.json",
    "team-recover-artifacts.schema.json",
    "team-router-artifacts.schema.json",
)


class PluginBuildError(ValueError):
    """An unsafe output path or incomplete source bundle."""


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _plain_source_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise PluginBuildError(f"{label}: missing or symlinked source file: {path}")
    return path


def _copy_plain_file(source: Path, target: Path, label: str) -> None:
    _plain_source_file(source, label)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def _packaged_skill_text(source: Path) -> str:
    text = _plain_source_file(source, f"skill {source.parent.name}").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise PluginBuildError(f"skill {source.parent.name}: invalid frontmatter")
    title_start = text.find("\n# ")
    if title_start < 0:
        raise PluginBuildError(f"skill {source.parent.name}: missing title")
    title_end = text.find("\n", title_start + 3)
    if title_end < 0:
        raise PluginBuildError(f"skill {source.parent.name}: incomplete title")
    runtime_note = (
        "\n\n## Bundled runtime\n\n"
        "In commands below, resolve `<TEAM_SKILL_DIR>` to the absolute directory\n"
        "containing the bundled `team/SKILL.md`. Never resolve it from the target\n"
        "repository working directory.\n"
    )
    text = text[:title_end] + runtime_note + text[title_end:]
    text = text.replace("python scripts/", "python <TEAM_SKILL_DIR>/scripts/")
    text = text.replace("`schemas/team-", "`<TEAM_SKILL_DIR>/references/schemas/team-")
    verification = (
        "## Bundle verification\n\n"
        "Run `python -B <TEAM_SKILL_DIR>/scripts/bundle-self-check.py` to verify\n"
        "the packaged file inventory, SHA-256 bindings, and runtime imports.\n"
    )
    marker = "\n## Verification\n"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n\n" + verification
    else:
        text = text.rstrip() + "\n\n" + verification
    return text


def _copy_skill(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise PluginBuildError(f"skill source is missing or symlinked: {source}")
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text(
        _packaged_skill_text(source / "SKILL.md"),
        encoding="utf-8",
        newline="\n",
    )
    for directory_name in ("agents", "references", "assets"):
        directory = source / directory_name
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise PluginBuildError(f"skill {source.name}: unsafe {directory_name} directory")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise PluginBuildError(f"skill {source.name}: symlinked resource: {path}")
            if path.is_file():
                _copy_plain_file(
                    path,
                    target / directory_name / path.relative_to(directory),
                    f"skill {source.name} resource",
                )


def _plugin_manifest() -> dict[str, Any]:
    return {
        "author": {"name": "Codex Multi-task Engineering Project"},
        "description": "Adaptive Codex collaboration for delegated goals, readable work queues, evidence and recovery.",
        "interface": {
            "capabilities": ["Read", "Write"],
            "category": "Productivity",
            "defaultPrompt": [
                "Use Team to understand this goal, recommend an execution plan and carry it to a verified result.",
                "Use Team Plan to split work only when ownership and dependencies support it.",
                "Use Team Recover to prepare a bounded successor for this blocked run.",
            ],
            "developerName": "Codex Multi-task Engineering Project",
            "displayName": "Codex Team",
            "longDescription": "Turn natural language goals into Codex proposals, authorized runs, live status, and evidence-bound checkpoints. Includes legacy manifest workflows and a bundled Python standard-library controller.",
            "shortDescription": "Evidence-bound Codex team workflows",
        },
        "name": PLUGIN_NAME,
        "skills": "./skills/",
        "version": PLUGIN_VERSION,
    }


def _bundle_manifest(plugin_root: Path) -> dict[str, Any]:
    bundle_path = plugin_root / "skills" / "team" / "references" / "bundle-manifest.json"
    files = {
        path.relative_to(plugin_root).as_posix(): _sha256(path)
        for path in sorted(plugin_root.rglob("*"))
        if path.is_file() and path != bundle_path
    }
    return {
        "files": files,
        "plugin_name": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "profile": "codex-team-plugin-bundle",
        "schema_version": "0.1",
    }


def _build_into(plugin_root: Path) -> None:
    _write_json(plugin_root / ".codex-plugin" / "plugin.json", _plugin_manifest())
    skills_root = plugin_root / "skills"
    for skill_name in SKILL_NAMES:
        _copy_skill(ROOT / "skills" / skill_name, skills_root / skill_name)
    runtime_root = skills_root / "team" / "scripts"
    for filename in RUNTIME_SCRIPTS:
        _copy_plain_file(
            ROOT / "scripts" / filename,
            runtime_root / filename,
            f"runtime script {filename}",
        )
    _copy_plain_file(
        ROOT / "scripts" / "team-plugin-self-check.py",
        runtime_root / "bundle-self-check.py",
        "bundle self-check",
    )
    package = ROOT / "team_runtime"
    if package.is_symlink() or not package.is_dir():
        raise PluginBuildError("Team Auto runtime package is missing or symlinked")
    for required in ("__init__.py", "__main__.py", "cli.py", "engine.py", "codex.py",
                     "adaptive.py", "adaptive_runner.py", "adaptive_cli.py", "adaptive_board.py",
                     "static/adaptive.html", "static/adaptive.js", "static/adaptive.css",
                     "store.py", "rules.py", "history.py", "board.py", "static/index.html",
                     "static/app.js", "static/styles.css"):
        _plain_source_file(package / required, "Team Auto runtime")
    for path in sorted(package.rglob("*")):
        relative = path.relative_to(package)
        if path.is_symlink():
            raise PluginBuildError(f"Team Auto runtime: symlinked resource: {path}")
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_file() and (path.suffix == ".py" or relative.parts[0] == "static"):
            _copy_plain_file(path, runtime_root / "team_runtime" / relative, "Team Auto runtime")
    schema_root = skills_root / "team" / "references" / "schemas"
    for filename in RUNTIME_SCHEMAS:
        _copy_plain_file(
            ROOT / "schemas" / filename,
            schema_root / filename,
            f"runtime schema {filename}",
        )
    _write_json(
        skills_root / "team" / "references" / "bundle-manifest.json",
        _bundle_manifest(plugin_root),
    )


def build(output_value: str) -> int:
    output = Path(output_value).expanduser().resolve(strict=False)
    if output.name != PLUGIN_NAME:
        raise PluginBuildError(f"output directory name must be {PLUGIN_NAME!r}")
    if output.exists() or output.is_symlink():
        raise PluginBuildError(f"refusing to overwrite existing output: {output}")
    parent = output.parent
    if parent.is_symlink() or not parent.is_dir():
        raise PluginBuildError(f"output parent must be an existing plain directory: {parent}")
    staging_parent = Path(tempfile.mkdtemp(prefix=".codex-team-build-", dir=parent))
    staging = staging_parent / PLUGIN_NAME
    try:
        staging.mkdir()
        _build_into(staging)
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging_parent, ignore_errors=True)
        raise
    shutil.rmtree(staging_parent, ignore_errors=True)
    print(f"PASS: built relocatable {PLUGIN_NAME} plugin at {output}")
    print("STOP: no marketplace, global skill directory, or Codex installation was changed")
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PluginBuildError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, metavar="PLUGIN_DIR")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        return build(args.out)
    except (PluginBuildError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
