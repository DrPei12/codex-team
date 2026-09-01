#!/usr/bin/env python3
"""Validate, plan, apply, and gate an ordered Codex team integration."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


PROFILE = "codex-multitask-team-integrate"
SCHEMA_VERSION = "0.1"
ROOT = Path(__file__).resolve().parents[1]
TEAM_PLAN_PATH = ROOT / "scripts" / "team-plan.py"
TEAM_RUN_PATH = ROOT / "scripts" / "team-run.py"
TEAM_STATUS_PATH = ROOT / "scripts" / "team-status.py"


class TeamIntegrateError(ValueError):
    """An actionable candidate, integration, or Gate error."""


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise TeamIntegrateError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEAM_PLAN = _load_module("codex_team_plan_for_integrate", TEAM_PLAN_PATH)
TEAM_RUN = _load_module("codex_team_run_for_integrate", TEAM_RUN_PATH)
TEAM_STATUS = _load_module("codex_team_status_for_integrate", TEAM_STATUS_PATH)


def _manifest_ref(manifest: dict[str, Any]) -> dict[str, str]:
    return {"run_id": manifest["run_id"], "sha256": TEAM_PLAN.manifest_digest(manifest)}


def _now() -> str:
    return TEAM_STATUS._now()


def _load_json(path_value: str | Path, label: str) -> dict[str, Any]:
    try:
        return TEAM_STATUS._load_json(path_value, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamIntegrateError(str(exc)) from exc


def _write_json(path: Path, value: dict[str, Any]) -> None:
    try:
        TEAM_STATUS._write_json_exclusive(path, value)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamIntegrateError(str(exc)) from exc


def _sha256_file(path: Path) -> str:
    try:
        return TEAM_STATUS._sha256_file(path)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamIntegrateError(str(exc)) from exc


def _validate_manifest_ref(value: Any, expected: dict[str, str], label: str) -> None:
    try:
        TEAM_STATUS._validate_manifest_ref(value, expected, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamIntegrateError(str(exc)) from exc


def _validate_run_dir(manifest: dict[str, Any], run_value: str) -> Path:
    try:
        return TEAM_STATUS._validate_run_dir(manifest, run_value)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamIntegrateError(str(exc)) from exc


def _validate_output(manifest: dict[str, Any], run_dir: Path, value: str, label: str) -> Path:
    try:
        return TEAM_STATUS._validate_output(manifest, run_dir, value, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamIntegrateError(str(exc)) from exc


def _validate_run_artifacts(
    manifest: dict[str, Any], run_dir: Path, expected_ref: dict[str, str]
) -> dict[str, Any]:
    try:
        return TEAM_STATUS._load_run_artifacts(manifest, run_dir, expected_ref)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamIntegrateError(str(exc)) from exc


def _normal_path(value: str) -> str:
    return TEAM_PLAN._normal_path(value)


def _observe_git(path: str) -> dict[str, Any]:
    try:
        return TEAM_RUN._observe_git(path)
    except TEAM_RUN.TeamRunError as exc:
        raise TeamIntegrateError(str(exc)) from exc


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
        raise TeamIntegrateError(f"git {' '.join(args)} failed in {path}: {detail}")
    return result


def _nul_list(value: str) -> list[str]:
    return sorted(item.replace("\\", "/") for item in value.split("\0") if item)


def _path_owned(
    path: str,
    patterns: list[str],
    forbidden_patterns: list[str] | None = None,
) -> bool:
    return TEAM_PLAN._path_is_owned(path, patterns, forbidden_patterns)


def _file_ref(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": _sha256_file(path)}


def _validate_ref(path_value: str, expected_digest: str, run_dir: Path, label: str) -> Path:
    path_text = TEAM_PLAN._absolute_path(path_value, label, label=label)
    if not TEAM_PLAN._path_is_within(path_text, str(run_dir)):
        raise TeamIntegrateError(f"{label}: path is outside current run_dir")
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise TeamIntegrateError(f"{label}: missing or symlinked file")
    if _sha256_file(path) != expected_digest:
        raise TeamIntegrateError(f"{label}: hash mismatch")
    return path


def _lane(manifest: dict[str, Any], lane_id: str) -> dict[str, Any]:
    lane = next((item for item in manifest["lanes"] if item["lane_id"] == lane_id), None)
    if lane is None:
        raise TeamIntegrateError(f"unknown lane_id {lane_id!r}")
    return lane


def _passed_worker_receipt(
    run_dir: Path, lane_id: str, expected_ref: dict[str, str]
) -> tuple[Path, dict[str, Any]]:
    path = run_dir / "worker-receipts" / f"{lane_id}.json"
    receipt = _load_json(path, f"worker receipt {lane_id}")
    if receipt.get("profile") != TEAM_RUN.PROFILE or receipt.get("kind") != "worker-preflight-receipt":
        raise TeamIntegrateError(f"worker receipt {lane_id}: unexpected profile or kind")
    _validate_manifest_ref(receipt.get("manifest_ref"), expected_ref, f"worker receipt {lane_id}.manifest_ref")
    if receipt.get("lane_id") != lane_id or receipt.get("status") != "passed":
        raise TeamIntegrateError(f"worker receipt {lane_id}: must be a passed receipt for this lane")
    return path, receipt


def _candidate_changed_files(workspace: Path, base: str, head: str) -> list[str]:
    result = _git(workspace, "diff", "--name-only", "-z", f"{base}..{head}")
    return _nul_list(result.stdout)


def candidate(
    manifest_value: str,
    run_value: str,
    lane_id: str,
    report_value: str,
    evidence_value: str,
    output_value: str,
) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    _validate_run_artifacts(manifest, run_dir, expected_ref)
    lane = _lane(manifest, lane_id)
    if lane["role"] != "implementer":
        raise TeamIntegrateError(f"lane {lane_id}: only implementer lanes produce integration candidates")
    output = _validate_output(manifest, run_dir, output_value, "output")
    report_path = Path(report_value)
    evidence_path = Path(evidence_value)
    report_digest = _sha256_file(report_path)
    evidence_digest = _sha256_file(evidence_path)
    _validate_ref(str(report_path), report_digest, run_dir, "report")
    _validate_ref(str(evidence_path), evidence_digest, run_dir, "evidence")
    receipt_path, _ = _passed_worker_receipt(run_dir, lane_id, expected_ref)

    observed = _observe_git(lane["workspace"]["path"])
    expected_branch = lane["workspace"]["branch"]
    if not TEAM_PLAN._paths_same_existing(observed["path"], lane["workspace"]["path"]):
        raise TeamIntegrateError(f"lane {lane_id}: workspace path mismatch")
    if observed["branch"] != expected_branch:
        raise TeamIntegrateError(f"lane {lane_id}: branch mismatch")
    if observed["ordinary_status"]:
        raise TeamIntegrateError(f"lane {lane_id}: workspace must be ordinary clean")
    base = lane["workspace"]["base_revision"]
    head = observed["head"]
    if _git(Path(observed["path"]), "merge-base", "--is-ancestor", base, head, allow_failure=True).returncode != 0:
        raise TeamIntegrateError(f"lane {lane_id}: candidate HEAD is not descended from base_revision")
    changed_files = _candidate_changed_files(Path(observed["path"]), base, head)
    if not changed_files:
        raise TeamIntegrateError(f"lane {lane_id}: candidate has no changed files")
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
        raise TeamIntegrateError(f"lane {lane_id}: ownership violation: {violations}")

    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "integration-candidate",
        "manifest_ref": expected_ref,
        "created_at": _now(),
        "lane_id": lane_id,
        "workspace": {
            "path": observed["path"],
            "branch": observed["branch"],
            "base_revision": base,
            "head": head,
            "tree": observed["tree"],
            "ordinary_status": observed["ordinary_status"],
        },
        "changed_files": changed_files,
        "report_ref": _file_ref(report_path),
        "evidence_ref": _file_ref(evidence_path),
        "worker_receipt_ref": _file_ref(receipt_path),
    }
    _write_json(output, document)
    print(f"PASS: integration candidate {lane_id} at {output}")
    print("STOP: no integration workspace or Git ref was changed")
    return 0


def _validate_candidate_document(
    path: Path,
    document: dict[str, Any],
    manifest: dict[str, Any],
    run_dir: Path,
    expected_ref: dict[str, str],
    *,
    require_current_workspace: bool,
) -> dict[str, Any]:
    if document.get("profile") != PROFILE or document.get("kind") != "integration-candidate":
        raise TeamIntegrateError(f"candidate {path.name}: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, f"candidate {path.name}.manifest_ref")
    lane_id = document.get("lane_id")
    lane = _lane(manifest, lane_id)
    if lane["role"] != "implementer":
        raise TeamIntegrateError(f"candidate {path.name}: lane is not an implementer")
    workspace = document.get("workspace", {})
    if not TEAM_PLAN._paths_same_existing(
        workspace.get("path", ""), lane["workspace"]["path"]
    ):
        raise TeamIntegrateError(f"candidate {lane_id}: workspace differs from manifest")
    if workspace.get("branch") != lane["workspace"]["branch"]:
        raise TeamIntegrateError(f"candidate {lane_id}: branch differs from manifest")
    if workspace.get("base_revision") != lane["workspace"]["base_revision"]:
        raise TeamIntegrateError(f"candidate {lane_id}: base differs from manifest")
    for field in ("report_ref", "evidence_ref", "worker_receipt_ref"):
        reference = document.get(field, {})
        _validate_ref(reference.get("path"), reference.get("sha256"), run_dir, f"candidate {lane_id}.{field}")
    changed_files = document.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        raise TeamIntegrateError(f"candidate {lane_id}: changed_files must be non-empty")
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
        raise TeamIntegrateError(f"candidate {lane_id}: ownership violation: {violations}")
    head = workspace.get("head")
    tree = workspace.get("tree")
    actual_tree = _git(Path(workspace["path"]), "rev-parse", f"{head}^{{tree}}").stdout.strip()
    if actual_tree != tree:
        raise TeamIntegrateError(f"candidate {lane_id}: commit/tree mismatch")
    if require_current_workspace:
        observed = _observe_git(workspace["path"])
        if observed["head"] != head or observed["tree"] != tree:
            raise TeamIntegrateError(f"candidate {lane_id}: workspace moved after candidate creation")
        if observed["ordinary_status"]:
            raise TeamIntegrateError(f"candidate {lane_id}: workspace is no longer ordinary clean")
    return lane


def _load_status_snapshot(path_value: str, run_dir: Path, expected_ref: dict[str, str]) -> tuple[Path, dict[str, Any]]:
    path_text = TEAM_PLAN._absolute_path(path_value, "status", label="status")
    if not TEAM_PLAN._path_is_within(path_text, str(run_dir)):
        raise TeamIntegrateError("status: snapshot is outside run_dir")
    path = Path(path_text)
    snapshot = _load_json(path, "status snapshot")
    if snapshot.get("profile") != TEAM_STATUS.PROFILE or snapshot.get("kind") != "status-snapshot":
        raise TeamIntegrateError("status snapshot: unexpected profile or kind")
    _validate_manifest_ref(snapshot.get("manifest_ref"), expected_ref, "status snapshot.manifest_ref")
    return path, snapshot


def prepare(
    manifest_value: str,
    run_value: str,
    status_value: str,
    candidates_value: str,
    output_value: str,
) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    _validate_run_artifacts(manifest, run_dir, expected_ref)
    status_path, snapshot = _load_status_snapshot(status_value, run_dir, expected_ref)
    output = _validate_output(manifest, run_dir, output_value, "output")
    candidates_text = TEAM_PLAN._absolute_path(candidates_value, "candidates", label="candidates")
    if not TEAM_PLAN._path_is_within(candidates_text, str(run_dir)):
        raise TeamIntegrateError("candidates: directory is outside run_dir")
    candidates_dir = Path(candidates_text)
    if candidates_dir.is_symlink() or not candidates_dir.is_dir():
        raise TeamIntegrateError("candidates: missing or unsafe directory")
    paths = sorted(candidates_dir.iterdir())
    if not paths or any(path.suffix != ".json" or path.is_symlink() for path in paths):
        raise TeamIntegrateError("candidates: expected one or more plain JSON files")

    status_by_lane = {item["lane_id"]: item for item in snapshot.get("lanes", [])}
    candidates_by_lane: dict[str, tuple[Path, dict[str, Any]]] = {}
    changed_owner: dict[str, str] = {}
    for path in paths:
        document = _load_json(path, f"candidate {path.name}")
        lane = _validate_candidate_document(
            path,
            document,
            manifest,
            run_dir,
            expected_ref,
            require_current_workspace=True,
        )
        lane_id = lane["lane_id"]
        if lane_id in candidates_by_lane:
            raise TeamIntegrateError(f"candidates: duplicate lane {lane_id}")
        status = status_by_lane.get(lane_id, {}).get("status")
        if status not in {"handoff-ready", "accepted"}:
            raise TeamIntegrateError(f"candidate {lane_id}: status must be handoff-ready or accepted")
        for changed in document["changed_files"]:
            key = changed.replace("\\", "/").casefold()
            if key in changed_owner:
                raise TeamIntegrateError(
                    f"candidates: changed file {changed!r} overlaps lanes {changed_owner[key]!r} and {lane_id!r}"
                )
            changed_owner[key] = lane_id
        candidates_by_lane[lane_id] = (path, document)

    order_index = {lane_id: index for index, lane_id in enumerate(manifest["integration_order"])}
    ordered_ids = sorted(candidates_by_lane, key=order_index.__getitem__)
    for lane_id in ordered_ids:
        lane = _lane(manifest, lane_id)
        for dependency in lane["depends_on"]:
            if dependency in candidates_by_lane and order_index[dependency] < order_index[lane_id]:
                continue
            dependency_status = status_by_lane.get(dependency, {}).get("status")
            if dependency_status not in {"accepted", "integrating", "integrated", "review-pending", "reviewed"}:
                raise TeamIntegrateError(f"candidate {lane_id}: dependency {dependency} is not accepted or planned earlier")

    integrators = [lane for lane in manifest["lanes"] if lane["role"] == "integrator"]
    if len(integrators) != 1:
        raise TeamIntegrateError("manifest must contain exactly one integrator lane")
    integrator = integrators[0]
    target = _observe_git(integrator["workspace"]["path"])
    if target["branch"] != integrator["workspace"]["branch"]:
        raise TeamIntegrateError("integrator workspace branch mismatch")
    if target["head"] != integrator["workspace"]["base_revision"]:
        raise TeamIntegrateError("integrator workspace HEAD differs from planned base")
    if target["ordinary_status"]:
        raise TeamIntegrateError("integrator workspace must be ordinary clean")

    items: list[dict[str, Any]] = []
    for position, lane_id in enumerate(ordered_ids, start=1):
        path, document = candidates_by_lane[lane_id]
        items.append(
            {
                "lane_id": lane_id,
                "order": position,
                "candidate_ref": _file_ref(path),
                "commit": document["workspace"]["head"],
                "tree": document["workspace"]["tree"],
                "changed_files": copy.deepcopy(document["changed_files"]),
            }
        )
    plan = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "integration-plan",
        "manifest_ref": expected_ref,
        "created_at": _now(),
        "status": "ready-for-authorized-apply",
        "status_snapshot_ref": _file_ref(status_path),
        "integration_lane": {
            "lane_id": integrator["lane_id"],
            "workspace": copy.deepcopy(integrator["workspace"]),
            "base_head": target["head"],
            "base_tree": target["tree"],
        },
        "candidates": items,
        "gates": copy.deepcopy(manifest["global_gates"]),
        "authorization": {"git_mutation": False, "command_execution": False},
    }
    _write_json(output, plan)
    print(f"PASS: prepared integration plan with {len(items)} candidates at {output}")
    print("STOP: no Git merge or Gate command was executed")
    return 0


def _load_plan(
    plan_value: str,
    manifest: dict[str, Any],
    run_dir: Path,
    expected_ref: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    path_text = TEAM_PLAN._absolute_path(plan_value, "plan", label="plan")
    if not TEAM_PLAN._path_is_within(path_text, str(run_dir)):
        raise TeamIntegrateError("plan: outside run_dir")
    path = Path(path_text)
    document = _load_json(path, "integration plan")
    if document.get("profile") != PROFILE or document.get("kind") != "integration-plan":
        raise TeamIntegrateError("integration plan: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, "integration plan.manifest_ref")
    if document.get("status") != "ready-for-authorized-apply":
        raise TeamIntegrateError("integration plan: not ready for apply")
    return path, document


def apply(
    manifest_value: str,
    run_value: str,
    plan_value: str,
    receipt_value: str,
    allow_git_mutation: bool,
) -> int:
    if not allow_git_mutation:
        raise TeamIntegrateError("apply requires --allow-git-mutation after explicit user authorization")
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    plan_path, plan = _load_plan(plan_value, manifest, run_dir, expected_ref)
    receipt_path = _validate_output(manifest, run_dir, receipt_value, "receipt")
    integration_lane = _lane(manifest, plan["integration_lane"]["lane_id"])
    workspace = Path(integration_lane["workspace"]["path"])
    before = _observe_git(str(workspace))
    if before["branch"] != integration_lane["workspace"]["branch"]:
        raise TeamIntegrateError("apply: integration branch mismatch")
    if before["head"] != plan["integration_lane"]["base_head"] or before["tree"] != plan["integration_lane"]["base_tree"]:
        raise TeamIntegrateError("apply: integration workspace moved after plan")
    if before["ordinary_status"]:
        raise TeamIntegrateError("apply: integration workspace must be ordinary clean")

    merges: list[dict[str, str]] = []
    errors: list[str] = []
    for item in plan["candidates"]:
        candidate_path = _validate_ref(
            item["candidate_ref"]["path"],
            item["candidate_ref"]["sha256"],
            run_dir,
            f"candidate {item['lane_id']}",
        )
        candidate_document = _load_json(candidate_path, f"candidate {item['lane_id']}")
        _validate_candidate_document(
            candidate_path,
            candidate_document,
            manifest,
            run_dir,
            expected_ref,
            require_current_workspace=False,
        )
        if candidate_document["lane_id"] != item["lane_id"]:
            raise TeamIntegrateError(f"apply: plan lane {item['lane_id']} points to another candidate")
        if item["commit"] != candidate_document["workspace"]["head"]:
            raise TeamIntegrateError(f"apply: candidate {item['lane_id']} commit differs from plan")
        if item["tree"] != candidate_document["workspace"]["tree"]:
            raise TeamIntegrateError(f"apply: candidate {item['lane_id']} tree differs from plan")
        if item["changed_files"] != candidate_document["changed_files"]:
            raise TeamIntegrateError(f"apply: candidate {item['lane_id']} changed_files differ from plan")
        result = _git(workspace, "merge", "--no-ff", "--no-edit", item["commit"], allow_failure=True)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            errors.append(f"lane {item['lane_id']}: merge failed: {detail}")
            _git(workspace, "merge", "--abort", allow_failure=True)
            break
        merges.append(
            {
                "lane_id": item["lane_id"],
                "source_commit": item["commit"],
                "result_commit": _git(workspace, "rev-parse", "HEAD").stdout.strip(),
            }
        )
    after = _observe_git(str(workspace))
    if after["ordinary_status"]:
        errors.append("integration workspace is not ordinary clean after apply")
    receipt = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "integration-apply-receipt",
        "manifest_ref": expected_ref,
        "recorded_at": _now(),
        "status": "failed" if errors else "applied",
        "plan_ref": _file_ref(plan_path),
        "workspace": str(workspace.resolve()),
        "before": {"commit": before["head"], "tree": before["tree"]},
        "after": {"commit": after["head"], "tree": after["tree"]},
        "merges": merges,
        "ordinary_status_after": after["ordinary_status"],
        "errors": errors,
    }
    _write_json(receipt_path, receipt)
    if errors:
        print(f"ERROR: integration apply failed; receipt={receipt_path}", file=sys.stderr)
        return 1
    print(f"PASS: applied {len(merges)} candidates; receipt={receipt_path}")
    return 0


def _load_apply_receipt(
    value: str,
    run_dir: Path,
    expected_ref: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    path_text = TEAM_PLAN._absolute_path(value, "apply_receipt", label="apply_receipt")
    if not TEAM_PLAN._path_is_within(path_text, str(run_dir)):
        raise TeamIntegrateError("apply receipt: outside run_dir")
    path = Path(path_text)
    document = _load_json(path, "apply receipt")
    if document.get("profile") != PROFILE or document.get("kind") != "integration-apply-receipt":
        raise TeamIntegrateError("apply receipt: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, "apply receipt.manifest_ref")
    if document.get("status") != "applied":
        raise TeamIntegrateError("apply receipt: integration was not applied")
    return path, document


def run_gates(
    manifest_value: str,
    run_value: str,
    plan_value: str,
    apply_value: str,
    receipt_value: str,
    allow_command_execution: bool,
) -> int:
    if not allow_command_execution:
        raise TeamIntegrateError("run-gates requires --allow-command-execution after explicit user authorization")
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    plan_path, plan = _load_plan(plan_value, manifest, run_dir, expected_ref)
    apply_path, apply_receipt = _load_apply_receipt(apply_value, run_dir, expected_ref)
    if apply_receipt.get("plan_ref") != _file_ref(plan_path):
        raise TeamIntegrateError("run-gates: apply receipt does not bind the current plan bytes")
    receipt_path = _validate_output(manifest, run_dir, receipt_value, "receipt")
    workspace = Path(apply_receipt["workspace"])
    observed = _observe_git(str(workspace))
    if observed["head"] != apply_receipt["after"]["commit"] or observed["tree"] != apply_receipt["after"]["tree"]:
        raise TeamIntegrateError("run-gates: integration target moved after apply")
    if observed["ordinary_status"]:
        raise TeamIntegrateError("run-gates: integration workspace must be ordinary clean")
    logs = run_dir / "integration-gates"
    if logs.exists():
        raise TeamIntegrateError("run-gates: integration-gates directory already exists")
    logs.mkdir()

    gate_results: list[dict[str, Any]] = []
    failed = False
    for gate in plan["gates"]:
        command = gate.get("command")
        if not isinstance(command, str) or not command.strip():
            raise TeamIntegrateError(f"gate {gate.get('gate_id')}: command is required")
        result = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        log_path = logs / f"{gate['gate_id']}.log"
        log_path.write_text(
            f"COMMAND: {command}\nEXIT: {result.returncode}\n\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
            encoding="utf-8",
            newline="\n",
        )
        gate_results.append(
            {
                "gate_id": gate["gate_id"],
                "owner": gate["owner"],
                "command": command,
                "exit_code": result.returncode,
                "status": "passed" if result.returncode == 0 else "failed",
                "log_ref": _file_ref(log_path),
            }
        )
        if result.returncode != 0:
            failed = True
            break
    receipt = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "gate-receipt",
        "manifest_ref": expected_ref,
        "recorded_at": _now(),
        "status": "failed" if failed else "passed",
        "plan_ref": _file_ref(plan_path),
        "apply_receipt_ref": _file_ref(apply_path),
        "target": {"commit": observed["head"], "tree": observed["tree"]},
        "gates": gate_results,
    }
    _write_json(receipt_path, receipt)
    if failed:
        print(f"ERROR: integration Gate failed; receipt={receipt_path}", file=sys.stderr)
        return 1
    print(f"PASS: {len(gate_results)} integration Gates; receipt={receipt_path}")
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise TeamIntegrateError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    candidate_parser = commands.add_parser("candidate", help="build one integration candidate")
    candidate_parser.add_argument("manifest", metavar="MANIFEST")
    candidate_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    candidate_parser.add_argument("--lane", required=True, metavar="LANE")
    candidate_parser.add_argument("--report", required=True, metavar="REPORT")
    candidate_parser.add_argument("--evidence", required=True, metavar="EVIDENCE")
    candidate_parser.add_argument("--out", required=True, metavar="CANDIDATE")
    prepare_parser = commands.add_parser("prepare", help="prepare an ordered integration plan")
    prepare_parser.add_argument("manifest", metavar="MANIFEST")
    prepare_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    prepare_parser.add_argument("--status", required=True, metavar="SNAPSHOT")
    prepare_parser.add_argument("--candidates", required=True, metavar="DIR")
    prepare_parser.add_argument("--out", required=True, metavar="PLAN")
    apply_parser = commands.add_parser("apply", help="apply an authorized integration plan")
    apply_parser.add_argument("manifest", metavar="MANIFEST")
    apply_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    apply_parser.add_argument("--plan", required=True, metavar="PLAN")
    apply_parser.add_argument("--receipt", required=True, metavar="RECEIPT")
    apply_parser.add_argument("--allow-git-mutation", action="store_true")
    gate_parser = commands.add_parser("run-gates", help="run authorized integration Gates")
    gate_parser.add_argument("manifest", metavar="MANIFEST")
    gate_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    gate_parser.add_argument("--plan", required=True, metavar="PLAN")
    gate_parser.add_argument("--apply-receipt", required=True, metavar="RECEIPT")
    gate_parser.add_argument("--receipt", required=True, metavar="GATE_RECEIPT")
    gate_parser.add_argument("--allow-command-execution", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "candidate":
            return candidate(args.manifest, args.run_dir, args.lane, args.report, args.evidence, args.out)
        if args.command == "prepare":
            return prepare(args.manifest, args.run_dir, args.status, args.candidates, args.out)
        if args.command == "apply":
            return apply(args.manifest, args.run_dir, args.plan, args.receipt, args.allow_git_mutation)
        if args.command == "run-gates":
            return run_gates(
                args.manifest,
                args.run_dir,
                args.plan,
                args.apply_receipt,
                args.receipt,
                args.allow_command_execution,
            )
        raise TeamIntegrateError(f"unknown command {args.command!r}")
    except (
        TeamIntegrateError,
        TEAM_PLAN.ManifestError,
        TEAM_RUN.TeamRunError,
        TEAM_STATUS.TeamStatusError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
