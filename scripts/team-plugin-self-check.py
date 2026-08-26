#!/usr/bin/env python3
"""Verify a built Codex Team plugin bundle without source-repository access."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PROFILE = "codex-team-plugin-bundle"
PLUGIN_NAME = "codex-team"
RUNTIME_SCRIPTS = (
    "team.py",
    "team-plan.py",
    "team-run.py",
    "team-status.py",
    "team-integrate.py",
    "team-finish.py",
    "team-recover.py",
)


class BundleCheckError(ValueError):
    """A missing, extra, tampered, or unloadable plugin file."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BundleCheckError(f"{label}: cannot load JSON: {path}") from exc
    if not isinstance(value, dict):
        raise BundleCheckError(f"{label}: expected JSON object")
    return value


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BundleCheckError(f"unsafe bundle path: {value!r}")
    return path


def check() -> int:
    team_root = Path(__file__).resolve().parents[1]
    plugin_root = team_root.parents[1]
    bundle_path = team_root / "references" / "bundle-manifest.json"
    bundle = _load_json(bundle_path, "bundle manifest")
    if bundle.get("profile") != PROFILE or bundle.get("plugin_name") != PLUGIN_NAME:
        raise BundleCheckError("bundle manifest: unexpected profile or plugin name")
    files = bundle.get("files")
    if not isinstance(files, dict) or not files:
        raise BundleCheckError("bundle manifest: files must be a non-empty object")
    expected: set[str] = set()
    for relative, digest in sorted(files.items()):
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise BundleCheckError("bundle manifest: file entries must be string pairs")
        safe = _safe_relative(relative)
        expected.add(safe.as_posix())
        path = plugin_root.joinpath(*safe.parts)
        if path.is_symlink() or not path.is_file():
            raise BundleCheckError(f"missing or symlinked bundle file: {relative}")
        if _sha256(path) != digest:
            raise BundleCheckError(f"hash mismatch: {relative}")
    actual = {
        path.relative_to(plugin_root).as_posix()
        for path in plugin_root.rglob("*")
        if path.is_file()
        and path != bundle_path
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise BundleCheckError(f"bundle inventory mismatch: missing={missing}, extra={extra}")
    plugin = _load_json(plugin_root / ".codex-plugin" / "plugin.json", "plugin manifest")
    if plugin.get("name") != PLUGIN_NAME or plugin.get("skills") != "./skills/":
        raise BundleCheckError("plugin manifest: unexpected name or skills path")
    if bundle.get("plugin_version") != plugin.get("version"):
        raise BundleCheckError("bundle manifest: plugin version mismatch")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    runtime_root = team_root / "scripts"
    for filename in RUNTIME_SCRIPTS:
        result = subprocess.run(
            [sys.executable, "-B", str(runtime_root / filename), "--help"],
            cwd=plugin_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise BundleCheckError(f"runtime import failed for {filename}: {detail}")
    print(f"PASS: {len(expected)} bundle files and {len(RUNTIME_SCRIPTS)} runtime entrypoints")
    return 0


def main() -> int:
    try:
        return check()
    except (BundleCheckError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
