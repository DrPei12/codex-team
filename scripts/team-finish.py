#!/usr/bin/env python3
"""Record review, audit final state, and project a non-destructive milestone result."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


PROFILE = "codex-multitask-team-finish"
SCHEMA_VERSION = "0.1"
ROOT = Path(__file__).resolve().parents[1]
TEAM_PLAN_PATH = ROOT / "scripts" / "team-plan.py"
TEAM_RUN_PATH = ROOT / "scripts" / "team-run.py"
TEAM_STATUS_PATH = ROOT / "scripts" / "team-status.py"
TEAM_INTEGRATE_PATH = ROOT / "scripts" / "team-integrate.py"
OPERATION_MARKERS = (
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "REBASE_HEAD",
    "rebase-merge",
    "rebase-apply",
    "BISECT_LOG",
)


class TeamFinishError(ValueError):
    """An actionable review, audit, or milestone finalization error."""


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise TeamFinishError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEAM_PLAN = _load_module("codex_team_plan_for_finish", TEAM_PLAN_PATH)
TEAM_RUN = _load_module("codex_team_run_for_finish", TEAM_RUN_PATH)
TEAM_STATUS = _load_module("codex_team_status_for_finish", TEAM_STATUS_PATH)
TEAM_INTEGRATE = _load_module("codex_team_integrate_for_finish", TEAM_INTEGRATE_PATH)


def _manifest_ref(manifest: dict[str, Any]) -> dict[str, str]:
    return {"run_id": manifest["run_id"], "sha256": TEAM_PLAN.manifest_digest(manifest)}


def _now() -> str:
    return TEAM_STATUS._now()


def _load_json(path_value: str | Path, label: str) -> dict[str, Any]:
    try:
        return TEAM_STATUS._load_json(path_value, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamFinishError(str(exc)) from exc


def _write_json(path: Path, value: dict[str, Any]) -> None:
    try:
        TEAM_STATUS._write_json_exclusive(path, value)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamFinishError(str(exc)) from exc


def _sha256_file(path: Path) -> str:
    try:
        return TEAM_STATUS._sha256_file(path)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamFinishError(str(exc)) from exc


def _file_ref(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": _sha256_file(path)}


def _validate_manifest_ref(value: Any, expected: dict[str, str], label: str) -> None:
    try:
        TEAM_STATUS._validate_manifest_ref(value, expected, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamFinishError(str(exc)) from exc


def _validate_run_dir(manifest: dict[str, Any], run_value: str) -> Path:
    try:
        return TEAM_STATUS._validate_run_dir(manifest, run_value)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamFinishError(str(exc)) from exc


def _validate_output(manifest: dict[str, Any], run_dir: Path, value: str, label: str) -> Path:
    try:
        return TEAM_STATUS._validate_output(manifest, run_dir, value, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamFinishError(str(exc)) from exc


def _normal_path(value: str) -> str:
    return TEAM_PLAN._normal_path(value)


def _observe_git(path: str) -> dict[str, Any]:
    try:
        return TEAM_RUN._observe_git(path)
    except TEAM_RUN.TeamRunError as exc:
        raise TeamFinishError(str(exc)) from exc


def _run_git(path: Path, *args: str) -> str:
    result = TEAM_INTEGRATE._git(path, *args)
    return result.stdout.strip()


def _validate_run_file(run_dir: Path, value: str, label: str) -> Path:
    path_text = TEAM_PLAN._absolute_path(value, label, label=label)
    if not TEAM_PLAN._path_is_within(path_text, str(run_dir)):
        raise TeamFinishError(f"{label}: path is outside run_dir")
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise TeamFinishError(f"{label}: missing or symlinked file")
    if not TEAM_PLAN._real_path_is_within(str(path), str(run_dir)):
        raise TeamFinishError(f"{label}: real path is outside run_dir")
    return path


def _load_gate_receipt(
    value: str,
    run_dir: Path,
    expected_ref: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    path = _validate_run_file(run_dir, value, "gate_receipt")
    document = _load_json(path, "gate receipt")
    if document.get("profile") != TEAM_INTEGRATE.PROFILE or document.get("kind") != "gate-receipt":
        raise TeamFinishError("gate receipt: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, "gate receipt.manifest_ref")
    for index, gate in enumerate(document.get("gates", [])):
        reference = gate.get("log_ref", {})
        log_path = _validate_run_file(run_dir, reference.get("path"), f"gate_receipt.gates[{index}].log")
        if _sha256_file(log_path) != reference.get("sha256"):
            raise TeamFinishError(f"gate_receipt.gates[{index}].log: hash mismatch")
    return path, document


def review(
    manifest_value: str,
    run_value: str,
    gate_value: str,
    reviewer_lane_id: str,
    decision: str,
    findings_value: str,
    output_value: str,
) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    gate_path, gate = _load_gate_receipt(gate_value, run_dir, expected_ref)
    if gate.get("status") != "passed":
        raise TeamFinishError("review: gate receipt must be passed")
    reviewer = next((lane for lane in manifest["lanes"] if lane["lane_id"] == reviewer_lane_id), None)
    if reviewer is None or reviewer["role"] != "reviewer":
        raise TeamFinishError("review: reviewer-lane must identify a reviewer")
    if decision not in {"approved", "changes-requested", "rejected"}:
        raise TeamFinishError("review: decision must be approved, changes-requested, or rejected")
    findings_path = _validate_run_file(run_dir, findings_value, "findings")
    findings = _load_json(findings_path, "review findings")
    if set(findings) != {"findings"} or not isinstance(findings["findings"], list):
        raise TeamFinishError("review findings: root must contain only a findings array")
    if not all(isinstance(item, dict) for item in findings["findings"]):
        raise TeamFinishError("review findings: every finding must be an object")
    output = _validate_output(manifest, run_dir, output_value, "output")
    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "review-receipt",
        "manifest_ref": expected_ref,
        "recorded_at": _now(),
        "reviewer_lane_id": reviewer_lane_id,
        "decision": decision,
        "target": gate["target"],
        "gate_receipt_ref": _file_ref(gate_path),
        "findings_ref": _file_ref(findings_path),
        "finding_count": len(findings["findings"]),
    }
    _write_json(output, document)
    print(f"PASS: recorded reviewer decision {decision}; receipt={output}")
    print("STOP: no task, Git, archive, or cleanup state was changed")
    return 0


def _load_review_receipt(
    value: str,
    run_dir: Path,
    expected_ref: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    path = _validate_run_file(run_dir, value, "review_receipt")
    document = _load_json(path, "review receipt")
    if document.get("profile") != PROFILE or document.get("kind") != "review-receipt":
        raise TeamFinishError("review receipt: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, "review receipt.manifest_ref")
    findings_ref = document.get("findings_ref", {})
    findings_path = _validate_run_file(run_dir, findings_ref.get("path"), "review receipt findings")
    if _sha256_file(findings_path) != findings_ref.get("sha256"):
        raise TeamFinishError("review receipt findings: hash mismatch")
    return path, document


def _integration_lane(manifest: dict[str, Any]) -> dict[str, Any]:
    integrators = [lane for lane in manifest["lanes"] if lane["role"] == "integrator"]
    if len(integrators) != 1:
        raise TeamFinishError("manifest must contain exactly one integrator lane")
    return integrators[0]


def _git_operation_residue(workspace: Path) -> list[str]:
    git_dir_raw = _run_git(workspace, "rev-parse", "--git-dir")
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = workspace / git_dir
    git_dir = git_dir.resolve()
    return [marker for marker in OPERATION_MARKERS if (git_dir / marker).exists()]


def _run_inventory(run_dir: Path, excluded: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    excluded_resolved = excluded.resolve()
    for path in sorted(run_dir.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.resolve() == excluded_resolved:
            continue
        relative = path.relative_to(run_dir).as_posix()
        if path.is_symlink():
            inventory.append({"path": relative, "kind": "symlink", "size": None, "sha256": None})
        elif path.is_file():
            inventory.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
        elif path.is_dir():
            inventory.append({"path": relative, "kind": "directory", "size": None, "sha256": None})
    return inventory


def audit(
    manifest_value: str,
    run_value: str,
    gate_value: str,
    review_value: str,
    output_value: str,
) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    gate_path, gate = _load_gate_receipt(gate_value, run_dir, expected_ref)
    review_path, review_document = _load_review_receipt(review_value, run_dir, expected_ref)
    output = _validate_output(manifest, run_dir, output_value, "output")
    errors: list[str] = []
    if gate.get("status") != "passed":
        errors.append("integration Gate is not passed")
    if review_document.get("decision") != "approved":
        errors.append("review decision is not approved")
    if review_document.get("gate_receipt_ref") != _file_ref(gate_path):
        errors.append("review receipt does not bind current gate receipt bytes")
    if review_document.get("target") != gate.get("target"):
        errors.append("review target differs from gate target")

    integrator = _integration_lane(manifest)
    workspace = Path(integrator["workspace"]["path"])
    observed = _observe_git(str(workspace))
    if observed["head"] != gate.get("target", {}).get("commit"):
        errors.append("integration HEAD differs from gate target")
    if observed["tree"] != gate.get("target", {}).get("tree"):
        errors.append("integration tree differs from gate target")
    operation_residue = _git_operation_residue(workspace)
    if observed["ordinary_status"]:
        errors.append("integration workspace has ordinary tracked/untracked changes")
    if operation_residue:
        errors.append("integration workspace has Git operation residue")
    cleanliness = {
        "ordinary_status": observed["ordinary_status"],
        "ignored_files": observed["ignored_files"],
        "operation_residue": operation_residue,
        "residue_free_checkout": not (
            observed["ordinary_status"] or observed["ignored_files"] or operation_residue
        ),
    }
    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "finish-audit",
        "manifest_ref": expected_ref,
        "recorded_at": _now(),
        "status": "blocked" if errors else "ready-to-finish",
        "target": {"commit": observed["head"], "tree": observed["tree"]},
        "gate_receipt_ref": _file_ref(gate_path),
        "review_receipt_ref": _file_ref(review_path),
        "cleanliness": cleanliness,
        "run_inventory": _run_inventory(run_dir, output),
        "cleanup_performed": False,
        "errors": errors,
    }
    _write_json(output, document)
    if errors:
        print(f"ERROR: finish audit blocked; receipt={output}", file=sys.stderr)
        return 1
    print(f"PASS: finish audit ready; receipt={output}")
    print("STOP: ignored residue was recorded; no cleanup or archive action was performed")
    return 0


def _load_audit(
    value: str,
    run_dir: Path,
    expected_ref: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    path = _validate_run_file(run_dir, value, "audit")
    document = _load_json(path, "finish audit")
    if document.get("profile") != PROFILE or document.get("kind") != "finish-audit":
        raise TeamFinishError("finish audit: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, "finish audit.manifest_ref")
    return path, document


def finalize(
    manifest_value: str,
    run_value: str,
    gate_value: str,
    review_value: str,
    audit_value: str,
    output_value: str,
) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    gate_path, gate = _load_gate_receipt(gate_value, run_dir, expected_ref)
    review_path, review_document = _load_review_receipt(review_value, run_dir, expected_ref)
    audit_path, audit_document = _load_audit(audit_value, run_dir, expected_ref)
    if gate.get("status") != "passed":
        raise TeamFinishError("finalize requires a passed gate receipt")
    if review_document.get("decision") != "approved":
        raise TeamFinishError("finalize requires an approved review receipt")
    if audit_document.get("status") != "ready-to-finish":
        raise TeamFinishError("finalize requires a ready-to-finish audit")
    if audit_document.get("gate_receipt_ref") != _file_ref(gate_path):
        raise TeamFinishError("finalize: audit does not bind current gate receipt")
    if audit_document.get("review_receipt_ref") != _file_ref(review_path):
        raise TeamFinishError("finalize: audit does not bind current review receipt")
    if audit_document.get("target") != gate.get("target"):
        raise TeamFinishError("finalize: audit target differs from gate target")
    integrator = _integration_lane(manifest)
    workspace = Path(integrator["workspace"]["path"])
    observed = _observe_git(str(workspace))
    current_operation_residue = _git_operation_residue(workspace)
    current_cleanliness = {
        "ordinary_status": observed["ordinary_status"],
        "ignored_files": observed["ignored_files"],
        "operation_residue": current_operation_residue,
        "residue_free_checkout": not (
            observed["ordinary_status"] or observed["ignored_files"] or current_operation_residue
        ),
    }
    if observed["head"] != gate["target"]["commit"] or observed["tree"] != gate["target"]["tree"]:
        raise TeamFinishError("finalize: integration target changed after audit")
    if current_cleanliness != audit_document.get("cleanliness"):
        raise TeamFinishError("finalize: workspace cleanliness changed after audit")
    output = _validate_output(manifest, run_dir, output_value, "output")
    ignored = audit_document["cleanliness"]["ignored_files"]
    status = "completed-with-ignored-residue" if ignored else "completed"
    unique_workspaces: dict[str, dict[str, Any]] = {}
    for lane in manifest["lanes"]:
        key = _normal_path(lane["workspace"]["path"])
        unique_workspaces.setdefault(
            key,
            {
                "path": lane["workspace"]["path"],
                "lanes": [],
                "recommended_action": "retain",
                "authorized": False,
            },
        )["lanes"].append(lane["lane_id"])
    task_dispositions: list[dict[str, Any]] = []
    archive_candidates: list[str] = []
    for lane in manifest["lanes"]:
        if lane["execution_surface"] == "internal-subagent":
            action = "not-applicable"
            reason = "internal subagent has no user-visible task to archive"
        elif lane["lifecycle"] == "long-lived-owner":
            action = "retain"
            reason = "long-lived owner remains available after this milestone"
        else:
            action = "archive"
            reason = "visible one-shot or milestone task is complete; preserve history by archiving"
            archive_candidates.append(lane["lane_id"])
        task_dispositions.append(
            {
                "lane_id": lane["lane_id"],
                "execution_surface": lane["execution_surface"],
                "task_title": lane["task_title"],
                "lifecycle": lane["lifecycle"],
                "recommended_action": action,
                "reason": reason,
                "authorized": False,
            }
        )
    result = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "milestone-result",
        "manifest_ref": expected_ref,
        "recorded_at": _now(),
        "status": status,
        "target": gate["target"],
        "gate_receipt_ref": _file_ref(gate_path),
        "review_receipt_ref": _file_ref(review_path),
        "audit_ref": _file_ref(audit_path),
        "archive_candidates": archive_candidates,
        "task_dispositions": task_dispositions,
        "workspace_actions": list(unique_workspaces.values()),
        "ignored_residue": ignored,
        "cleanup_performed": False,
        "residual_risks": (
            ["ignored checkout residue remains and requires separate cleanup authorization"] if ignored else []
        ),
    }
    _write_json(output, result)
    print(f"PASS: milestone result {status}; artifact={output}")
    print("STOP: task dispositions and workspace cleanup remain unexecuted recommendations")
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise TeamFinishError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    review_parser = commands.add_parser("review", help="record an independent review decision")
    review_parser.add_argument("manifest", metavar="MANIFEST")
    review_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    review_parser.add_argument("--gate-receipt", required=True, metavar="GATE_RECEIPT")
    review_parser.add_argument("--reviewer-lane", required=True, metavar="LANE")
    review_parser.add_argument("--decision", required=True)
    review_parser.add_argument("--findings", required=True, metavar="FINDINGS")
    review_parser.add_argument("--out", required=True, metavar="REVIEW_RECEIPT")
    audit_parser = commands.add_parser("audit", help="audit final Git and artifact state")
    audit_parser.add_argument("manifest", metavar="MANIFEST")
    audit_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    audit_parser.add_argument("--gate-receipt", required=True, metavar="GATE_RECEIPT")
    audit_parser.add_argument("--review-receipt", required=True, metavar="REVIEW_RECEIPT")
    audit_parser.add_argument("--out", required=True, metavar="AUDIT")
    finalize_parser = commands.add_parser("finalize", help="project a non-destructive milestone result")
    finalize_parser.add_argument("manifest", metavar="MANIFEST")
    finalize_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    finalize_parser.add_argument("--gate-receipt", required=True, metavar="GATE_RECEIPT")
    finalize_parser.add_argument("--review-receipt", required=True, metavar="REVIEW_RECEIPT")
    finalize_parser.add_argument("--audit", required=True, metavar="AUDIT")
    finalize_parser.add_argument("--out", required=True, metavar="RESULT")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "review":
            return review(
                args.manifest,
                args.run_dir,
                args.gate_receipt,
                args.reviewer_lane,
                args.decision,
                args.findings,
                args.out,
            )
        if args.command == "audit":
            return audit(args.manifest, args.run_dir, args.gate_receipt, args.review_receipt, args.out)
        if args.command == "finalize":
            return finalize(
                args.manifest,
                args.run_dir,
                args.gate_receipt,
                args.review_receipt,
                args.audit,
                args.out,
            )
        raise TeamFinishError(f"unknown command {args.command!r}")
    except (
        TeamFinishError,
        TEAM_PLAN.ManifestError,
        TEAM_RUN.TeamRunError,
        TEAM_STATUS.TeamStatusError,
        TEAM_INTEGRATE.TeamIntegrateError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
