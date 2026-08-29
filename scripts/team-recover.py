#!/usr/bin/env python3
"""Freeze exact recovery candidates and project a non-live successor plan."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any


PROFILE = "codex-multitask-team-recover"
SCHEMA_VERSION = "0.1"
ROOT = Path(__file__).resolve().parents[1]
TEAM_PLAN_PATH = ROOT / "scripts" / "team-plan.py"
TEAM_RUN_PATH = ROOT / "scripts" / "team-run.py"
TEAM_STATUS_PATH = ROOT / "scripts" / "team-status.py"
BLOCKED_STATUSES = {
    "failed",
    "blocked",
    "changes-requested",
    "preparation-failed",
    "preflight-failed",
}


class TeamRecoverError(ValueError):
    """An actionable candidate, predecessor, proof, or projection error."""


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise TeamRecoverError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEAM_PLAN = _load_module("codex_team_plan_for_recover", TEAM_PLAN_PATH)
TEAM_RUN = _load_module("codex_team_run_for_recover", TEAM_RUN_PATH)
TEAM_STATUS = _load_module("codex_team_status_for_recover", TEAM_STATUS_PATH)


def _manifest_ref(manifest: dict[str, Any]) -> dict[str, str]:
    return {"run_id": manifest["run_id"], "sha256": TEAM_PLAN.manifest_digest(manifest)}


def _now() -> str:
    return TEAM_STATUS._now()


def _load_json(path_value: str | Path, label: str) -> dict[str, Any]:
    try:
        return TEAM_STATUS._load_json(path_value, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRecoverError(str(exc)) from exc


def _write_json(path: Path, value: dict[str, Any]) -> None:
    try:
        TEAM_STATUS._write_json_exclusive(path, value)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRecoverError(str(exc)) from exc


def _sha256_file(path: Path) -> str:
    try:
        return TEAM_STATUS._sha256_file(path)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRecoverError(str(exc)) from exc


def _file_ref(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": _sha256_file(path)}


def _validate_manifest_ref(value: Any, expected: dict[str, str], label: str) -> None:
    try:
        TEAM_STATUS._validate_manifest_ref(value, expected, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRecoverError(str(exc)) from exc


def _validate_run_dir(manifest: dict[str, Any], run_value: str) -> Path:
    try:
        return TEAM_STATUS._validate_run_dir(manifest, run_value)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRecoverError(str(exc)) from exc


def _validate_output(manifest: dict[str, Any], run_dir: Path, value: str, label: str) -> Path:
    try:
        return TEAM_STATUS._validate_output(manifest, run_dir, value, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRecoverError(str(exc)) from exc


def _validate_run_file(run_dir: Path, value: str, label: str) -> Path:
    path_text = TEAM_PLAN._absolute_path(value, label, label=label)
    if not TEAM_PLAN._path_is_within(path_text, str(run_dir)):
        raise TeamRecoverError(f"{label}: path is outside run_dir")
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise TeamRecoverError(f"{label}: missing or symlinked file")
    if not TEAM_PLAN._real_path_is_within(str(path), str(run_dir)):
        raise TeamRecoverError(f"{label}: real path is outside run_dir")
    return path


def _lane(manifest: dict[str, Any], lane_id: str) -> dict[str, Any]:
    lane = next((item for item in manifest["lanes"] if item["lane_id"] == lane_id), None)
    if lane is None:
        raise TeamRecoverError(f"unknown lane_id {lane_id!r}")
    return lane


def _observe_git(path: str) -> dict[str, Any]:
    try:
        return TEAM_RUN._observe_git(path)
    except TEAM_RUN.TeamRunError as exc:
        raise TeamRecoverError(str(exc)) from exc


def _git(path: Path, *args: str, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0 and not allow_failure:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise TeamRecoverError(f"git {' '.join(args)} failed in {path}: {detail}")
    return result


def _changed_paths(status_entries: list[str]) -> list[str]:
    paths: list[str] = []
    for entry in status_entries:
        if len(entry) < 4:
            raise TeamRecoverError(f"cannot parse Git status entry: {entry!r}")
        path = entry[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.replace("\\", "/"))
    return sorted(set(paths), key=str.casefold)


def _path_owned(
    path: str,
    patterns: list[str],
    forbidden_patterns: list[str] | None = None,
) -> bool:
    return TEAM_PLAN._path_is_owned(path, patterns, forbidden_patterns)


def _write_text_exclusive(path: Path, value: str) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
    except FileExistsError as exc:
        raise TeamRecoverError(f"refusing to overwrite existing file: {path}") from exc
    except OSError as exc:
        raise TeamRecoverError(f"cannot write {path}: {exc}") from exc


def _write_snapshot_zip(workspace: Path, paths: list[str], output: Path) -> None:
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative in paths:
                source = workspace / relative
                if not source.is_file() or source.is_symlink():
                    continue
                info = zipfile.ZipInfo(relative.replace("\\", "/"))
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes())
    except (OSError, zipfile.BadZipFile) as exc:
        raise TeamRecoverError(f"cannot write candidate snapshot {output}: {exc}") from exc


def candidate(
    manifest_value: str,
    run_value: str,
    lane_id: str,
    mode: str,
    output_value: str,
) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    output = _validate_output(manifest, run_dir, output_value, "output")
    lane = _lane(manifest, lane_id)
    observed = _observe_git(lane["workspace"]["path"])
    if TEAM_PLAN._normal_path(observed["path"]) != TEAM_PLAN._normal_path(lane["workspace"]["path"]):
        raise TeamRecoverError("candidate: workspace path mismatch")
    if lane["workspace"]["branch"] is not None and observed["branch"] != lane["workspace"]["branch"]:
        raise TeamRecoverError("candidate: workspace branch mismatch")
    changed_files: list[str]
    patch_ref: dict[str, str] | None = None
    snapshot_ref: dict[str, str] | None = None
    commit_value: str | None = None
    tree_value: str | None = None
    base_commit = lane["workspace"]["base_revision"]
    base_tree = _git(Path(observed["path"]), "rev-parse", f"{base_commit}^{{tree}}").stdout.strip()

    if mode == "commit":
        if observed["ordinary_status"]:
            raise TeamRecoverError("candidate commit mode requires an ordinary clean workspace")
        if _git(
            Path(observed["path"]),
            "merge-base",
            "--is-ancestor",
            base_commit,
            observed["head"],
            allow_failure=True,
        ).returncode != 0:
            raise TeamRecoverError("candidate commit is not descended from lane base_revision")
        changed_files = _commit_changed_files(Path(observed["path"]), base_commit, observed["head"])
        if not changed_files:
            raise TeamRecoverError("candidate commit has no changed files")
        commit_value = observed["head"]
        tree_value = observed["tree"]
        candidate_mode = "git-commit"
    elif mode == "dirty":
        if not observed["ordinary_status"]:
            raise TeamRecoverError("candidate dirty mode requires ordinary changes")
        changed_files = _changed_paths(observed["ordinary_status"])
        violations = [
            path
            for path in changed_files
            if not _path_owned(
                path,
                lane["ownership"]["write_paths"],
                lane["ownership"]["forbidden_paths"],
            )
        ]
        if violations:
            raise TeamRecoverError(f"candidate ownership violation: {violations}")
        patch_path = output.with_suffix(".patch")
        snapshot_path = output.with_suffix(".zip")
        patch = _git(Path(observed["path"]), "diff", "--binary", "HEAD").stdout
        _write_text_exclusive(patch_path, patch)
        _write_snapshot_zip(Path(observed["path"]), changed_files, snapshot_path)
        patch_ref = _file_ref(patch_path)
        snapshot_ref = _file_ref(snapshot_path)
        candidate_mode = "dirty-files"
    else:
        raise TeamRecoverError("candidate mode must be commit or dirty")

    if mode == "commit":
        violations = [
            path
            for path in changed_files
            if not _path_owned(
                path,
                lane["ownership"]["write_paths"],
                lane["ownership"]["forbidden_paths"],
            )
        ]
        if violations:
            raise TeamRecoverError(f"candidate ownership violation: {violations}")
    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "recovery-candidate",
        "manifest_ref": expected_ref,
        "created_at": _now(),
        "lane_id": lane_id,
        "mode": candidate_mode,
        "workspace": {
            "path": observed["path"],
            "branch": observed["branch"],
            "base_commit": base_commit,
            "base_tree": base_tree,
        },
        "commit": commit_value,
        "tree": tree_value,
        "git_status": observed["ordinary_status"],
        "changed_files": changed_files,
        "patch_ref": patch_ref,
        "snapshot_ref": snapshot_ref,
    }
    _write_json(output, document)
    print(f"PASS: froze {candidate_mode} recovery candidate at {output}")
    print("STOP: no task was created and no workspace content was changed")
    return 0


def _commit_changed_files(workspace: Path, base: str, head: str) -> list[str]:
    result = _git(workspace, "diff", "--name-only", "-z", f"{base}..{head}")
    return sorted(item.replace("\\", "/") for item in result.stdout.split("\0") if item)


def _validate_candidate(
    path: Path,
    manifest: dict[str, Any],
    run_dir: Path,
    expected_ref: dict[str, str],
) -> dict[str, Any]:
    document = _load_json(path, "recovery candidate")
    if document.get("profile") != PROFILE or document.get("kind") != "recovery-candidate":
        raise TeamRecoverError("recovery candidate: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, "recovery candidate.manifest_ref")
    lane = _lane(manifest, document.get("lane_id"))
    workspace = document.get("workspace", {})
    if TEAM_PLAN._normal_path(workspace.get("path", "")) != TEAM_PLAN._normal_path(lane["workspace"]["path"]):
        raise TeamRecoverError("recovery candidate: workspace differs from manifest")
    if workspace.get("base_commit") != lane["workspace"]["base_revision"]:
        raise TeamRecoverError("recovery candidate: base differs from manifest")
    mode = document.get("mode")
    if mode == "git-commit":
        if document.get("patch_ref") is not None or document.get("snapshot_ref") is not None:
            raise TeamRecoverError("recovery candidate: commit mode must not contain dirty artifacts")
        commit_value = document.get("commit")
        tree_value = document.get("tree")
        actual_tree = _git(Path(workspace["path"]), "rev-parse", f"{commit_value}^{{tree}}").stdout.strip()
        if actual_tree != tree_value:
            raise TeamRecoverError("recovery candidate: commit/tree mismatch")
    elif mode == "dirty-files":
        if document.get("commit") is not None or document.get("tree") is not None:
            raise TeamRecoverError("recovery candidate: dirty mode must not claim commit/tree")
        for field in ("patch_ref", "snapshot_ref"):
            reference = document.get(field, {})
            artifact = _validate_run_file(run_dir, reference.get("path"), f"candidate {field}")
            if _sha256_file(artifact) != reference.get("sha256"):
                raise TeamRecoverError(f"candidate {field}: hash mismatch")
    else:
        raise TeamRecoverError("recovery candidate: unsupported mode")
    changed_files = document.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        raise TeamRecoverError("recovery candidate: changed_files must be non-empty")
    violations = [
        path
        for path in changed_files
        if not _path_owned(
            path,
            lane["ownership"]["write_paths"],
            lane["ownership"]["forbidden_paths"],
        )
    ]
    if violations:
        raise TeamRecoverError(f"recovery candidate ownership violation: {violations}")
    return document


def _validate_bound_file_ref(run_dir: Path, value: Any, label: str) -> Path:
    if not isinstance(value, dict):
        raise TeamRecoverError(f"{label}: expected file reference")
    path = _validate_run_file(run_dir, value.get("path"), label)
    if _sha256_file(path) != value.get("sha256"):
        raise TeamRecoverError(f"{label}: hash mismatch")
    return path


def _status_of_predecessor(document: dict[str, Any]) -> str:
    value = document.get("status", document.get("run_status"))
    if not isinstance(value, str):
        raise TeamRecoverError("predecessor: missing status/run_status")
    return value


def prepare(
    manifest_value: str,
    run_value: str,
    predecessor_value: str,
    candidate_value: str,
    proofs_value: str,
    new_fact: str,
    commands: list[str],
    allowed_paths: list[str],
    max_commands: int,
    output_value: str,
) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    output = _validate_output(manifest, run_dir, output_value, "output")
    predecessor_path = _validate_run_file(run_dir, predecessor_value, "predecessor")
    predecessor = _load_json(predecessor_path, "predecessor")
    _validate_manifest_ref(predecessor.get("manifest_ref"), expected_ref, "predecessor.manifest_ref")
    predecessor_status = _status_of_predecessor(predecessor)
    if predecessor_status not in BLOCKED_STATUSES:
        raise TeamRecoverError("predecessor must have a blocked or failed status")
    candidate_path = _validate_run_file(run_dir, candidate_value, "candidate")
    candidate_document = _validate_candidate(candidate_path, manifest, run_dir, expected_ref)

    proofs_text = TEAM_PLAN._absolute_path(proofs_value, "proofs", label="proofs")
    if not TEAM_PLAN._path_is_within(proofs_text, str(run_dir)):
        raise TeamRecoverError("proofs: directory is outside run_dir")
    proofs_dir = Path(proofs_text)
    if proofs_dir.is_symlink() or not proofs_dir.is_dir():
        raise TeamRecoverError("proofs: missing or unsafe directory")
    proof_paths = sorted(proofs_dir.iterdir())
    if not proof_paths or any(path.suffix != ".json" or path.is_symlink() for path in proof_paths):
        raise TeamRecoverError("proofs: expected one or more plain JSON files")
    proofs: list[dict[str, str]] = []
    for path in proof_paths:
        proof = _load_json(path, f"proof {path.name}")
        try:
            _validate_manifest_ref(proof.get("manifest_ref"), expected_ref, f"proof {path.name}.manifest_ref")
        except TeamRecoverError as exc:
            raise TeamRecoverError(f"proof {path.name}: manifest mismatch") from exc
        proofs.append(_file_ref(path))
    if not isinstance(new_fact, str) or not new_fact.strip():
        raise TeamRecoverError("new-fact must be one non-empty statement")
    if not commands or any(not command.strip() for command in commands):
        raise TeamRecoverError("at least one allowed command is required")
    if not allowed_paths or any(not path.strip() for path in allowed_paths):
        raise TeamRecoverError("at least one allowed path is required")
    if max_commands < 1:
        raise TeamRecoverError("max-commands must be >= 1")
    candidate_digest = _sha256_file(candidate_path)
    successor_run_id = f"{manifest['run_id']}:recovery:{candidate_digest[7:15]}"
    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "recovery-plan",
        "manifest_ref": expected_ref,
        "created_at": _now(),
        "status": "prepared-not-dispatched",
        "successor_run_id": successor_run_id,
        "predecessor": {
            "kind": predecessor.get("kind", "unknown"),
            "status": predecessor_status,
            "result_ref": _file_ref(predecessor_path),
            "immutable": True,
        },
        "candidate_ref": _file_ref(candidate_path),
        "candidate_mode": candidate_document["mode"],
        "candidate_lane_id": candidate_document["lane_id"],
        "reused_proofs": proofs,
        "new_fact": new_fact.strip(),
        "allowed_commands": commands,
        "allowed_paths": allowed_paths,
        "budget": {"max_commands": max_commands, "commands_used": 0},
        "stop_conditions": [
            "stop at the first nonzero command",
            "do not rewrite predecessor status or artifacts",
            *manifest["global_stop_conditions"],
        ],
        "authorization": {
            "task_creation": False,
            "workspace_mutation": False,
            "command_execution": False,
        },
    }
    _write_json(output, document)
    print(f"PASS: prepared recovery successor {successor_run_id} at {output}")
    print("STOP: no recovery task was created and no command was executed")
    return 0


def project(plan_value: str, output_value: str) -> int:
    plan_path = Path(plan_value)
    if plan_path.is_symlink() or not plan_path.is_file():
        raise TeamRecoverError("recovery plan: missing or symlinked file")
    plan = _load_json(plan_path, "recovery plan")
    if plan.get("profile") != PROFILE or plan.get("kind") != "recovery-plan":
        raise TeamRecoverError("recovery plan: unexpected profile or kind")
    if plan.get("status") != "prepared-not-dispatched":
        raise TeamRecoverError("recovery plan: not prepared")
    run_dir = plan_path.resolve().parent
    _validate_bound_file_ref(run_dir, plan.get("predecessor", {}).get("result_ref"), "predecessor")
    _validate_bound_file_ref(run_dir, plan.get("candidate_ref"), "candidate")
    reused_proofs = plan.get("reused_proofs")
    if not isinstance(reused_proofs, list) or not reused_proofs:
        raise TeamRecoverError("recovery plan: reused_proofs must be non-empty")
    for index, proof_ref in enumerate(reused_proofs):
        _validate_bound_file_ref(run_dir, proof_ref, f"reused proof {index}")
    output_text = TEAM_PLAN._absolute_path(output_value, "output", label="output")
    if not TEAM_PLAN._path_is_within(output_text, str(run_dir)):
        raise TeamRecoverError("output: recovery brief must be inside plan run directory")
    output = Path(output_text)
    if output.exists():
        raise TeamRecoverError(f"output: already exists; refusing to overwrite: {output}")
    if not output.parent.is_dir():
        raise TeamRecoverError("output: parent directory does not exist")
    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "recovery-brief",
        "manifest_ref": plan["manifest_ref"],
        "created_at": _now(),
        "plan_ref": _file_ref(plan_path),
        "successor_run_id": plan["successor_run_id"],
        "predecessor": plan["predecessor"],
        "candidate_ref": plan["candidate_ref"],
        "candidate_mode": plan["candidate_mode"],
        "candidate_lane_id": plan["candidate_lane_id"],
        "reused_proofs": plan["reused_proofs"],
        "new_fact": plan["new_fact"],
        "allowed_commands": plan["allowed_commands"],
        "allowed_paths": plan["allowed_paths"],
        "budget": plan["budget"],
        "stop_conditions": plan["stop_conditions"],
        "task_creation_authorized": False,
    }
    _write_json(output, document)
    print(f"PASS: projected recovery brief at {output}")
    print("STOP: the brief contains no task identity and authorizes no dispatch")
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise TeamRecoverError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="phase", required=True)
    candidate_parser = commands.add_parser("candidate", help="freeze an exact recovery candidate")
    candidate_parser.add_argument("manifest", metavar="MANIFEST")
    candidate_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    candidate_parser.add_argument("--lane", required=True, metavar="LANE")
    candidate_parser.add_argument("--mode", required=True, choices=("commit", "dirty"))
    candidate_parser.add_argument("--out", required=True, metavar="CANDIDATE")
    prepare_parser = commands.add_parser("prepare", help="prepare one successor recovery plan")
    prepare_parser.add_argument("manifest", metavar="MANIFEST")
    prepare_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    prepare_parser.add_argument("--predecessor", required=True, metavar="RESULT")
    prepare_parser.add_argument("--candidate", required=True, metavar="CANDIDATE")
    prepare_parser.add_argument("--proofs", required=True, metavar="DIR")
    prepare_parser.add_argument("--new-fact", required=True)
    prepare_parser.add_argument("--command", dest="allowed_commands", action="append", required=True)
    prepare_parser.add_argument("--allow-path", action="append", required=True)
    prepare_parser.add_argument("--max-commands", required=True, type=int)
    prepare_parser.add_argument("--out", required=True, metavar="PLAN")
    project_parser = commands.add_parser("project", help="project a recovery plan into a brief")
    project_parser.add_argument("plan", metavar="PLAN")
    project_parser.add_argument("--out", required=True, metavar="BRIEF")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.phase == "candidate":
            return candidate(args.manifest, args.run_dir, args.lane, args.mode, args.out)
        if args.phase == "prepare":
            return prepare(
                args.manifest,
                args.run_dir,
                args.predecessor,
                args.candidate,
                args.proofs,
                args.new_fact,
                args.allowed_commands,
                args.allow_path,
                args.max_commands,
                args.out,
            )
        if args.phase == "project":
            return project(args.plan, args.out)
        raise TeamRecoverError(f"unknown command {args.phase!r}")
    except (
        TeamRecoverError,
        TEAM_PLAN.ManifestError,
        TEAM_RUN.TeamRunError,
        TEAM_STATUS.TeamStatusError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
