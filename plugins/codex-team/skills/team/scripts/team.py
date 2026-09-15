#!/usr/bin/env python3
"""Route one Codex team run to its next bounded workflow phase."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


PROFILE = "codex-multitask-team"
SCHEMA_VERSION = "0.1"
ROOT = Path(__file__).resolve().parents[1]


class TeamRouterError(ValueError):
    """A manifest, run-state, or canonical-artifact routing error."""


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise TeamRouterError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEAM_PLAN = _load_module("codex_team_plan_for_router", ROOT / "scripts" / "team-plan.py")
TEAM_STATUS = _load_module("codex_team_status_for_router", ROOT / "scripts" / "team-status.py")

PROFILES = {
    "preregistration": "codex-multitask-team-run",
    "parent-preflight-receipt": "codex-multitask-team-run",
    "dispatch-bundle": "codex-multitask-team-run",
    "status-facts": "codex-multitask-team-status",
    "status-snapshot": "codex-multitask-team-status",
    "integration-candidate": "codex-multitask-team-integrate",
    "integration-plan": "codex-multitask-team-integrate",
    "integration-apply-receipt": "codex-multitask-team-integrate",
    "gate-receipt": "codex-multitask-team-integrate",
    "review-receipt": "codex-multitask-team-finish",
    "finish-audit": "codex-multitask-team-finish",
    "milestone-result": "codex-multitask-team-finish",
    "recovery-candidate": "codex-multitask-team-recover",
    "recovery-plan": "codex-multitask-team-recover",
    "recovery-brief": "codex-multitask-team-recover",
}

CANONICAL_FILES = {
    "preregistration": "preregistration.json",
    "parent-preflight-receipt": "parent-preflight-receipt.json",
    "dispatch-bundle": "dispatch-bundle.json",
    "status-facts": "status-facts.json",
    "status-snapshot": "status-snapshot.json",
    "integration-plan": "integration-plan.json",
    "integration-apply-receipt": "integration-apply.json",
    "gate-receipt": "gate-receipt.json",
    "review-receipt": "review-receipt.json",
    "finish-audit": "finish-audit.json",
    "milestone-result": "milestone-result.json",
    "recovery-candidate": "recovery-candidate.json",
    "recovery-plan": "recovery-plan.json",
    "recovery-brief": "recovery-brief.json",
}


def _manifest_ref(manifest: dict[str, Any]) -> dict[str, str]:
    return {"run_id": manifest["run_id"], "sha256": TEAM_PLAN.manifest_digest(manifest)}


def _sha256_file(path: Path) -> str:
    try:
        return TEAM_STATUS._sha256_file(path)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRouterError(str(exc)) from exc


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return TEAM_STATUS._load_json(path, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRouterError(str(exc)) from exc


def _validate_manifest_ref(value: Any, expected: dict[str, str], label: str) -> None:
    try:
        TEAM_STATUS._validate_manifest_ref(value, expected, label)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRouterError(str(exc)) from exc


def _file_ref(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": _sha256_file(path)}


def _planned_run_path(manifest: dict[str, Any], run_value: str) -> Path:
    path_text = TEAM_PLAN._absolute_path(run_value, "run_dir", label="run_dir")
    artifact_root = manifest["workspace_policy"]["artifact_root"]
    if not TEAM_PLAN._real_path_is_within(path_text, artifact_root):
        raise TeamRouterError("run_dir: outside artifact_root")
    path = Path(path_text)
    if path.exists():
        try:
            return TEAM_STATUS._validate_run_dir(manifest, run_value)
        except TEAM_STATUS.TeamStatusError as exc:
            raise TeamRouterError(str(exc)) from exc
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise TeamRouterError("run_dir: missing run requires an existing plain parent")
    if not TEAM_PLAN._real_path_is_within(str(parent), artifact_root):
        raise TeamRouterError("run_dir: parent real path is outside artifact_root")
    return path


def _artifact(path: Path, kind: str, expected_ref: dict[str, str]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise TeamRouterError(f"{kind}: canonical artifact is not a plain file")
    document = _load_json(path, kind)
    if document.get("profile") != PROFILES[kind] or document.get("kind") != kind:
        raise TeamRouterError(f"{kind}: unexpected profile or kind")
    _validate_manifest_ref(document.get("manifest_ref"), expected_ref, f"{kind}.manifest_ref")
    return document


def _load_artifacts(run_dir: Path, expected_ref: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    artifacts: dict[str, Any] = {}
    observations: list[dict[str, str]] = []
    for kind, relative in CANONICAL_FILES.items():
        path = run_dir / relative
        document = _artifact(path, kind, expected_ref)
        if document is not None:
            artifacts[kind] = document
            observations.append({"kind": kind, **_file_ref(path)})
    candidate_dir = run_dir / "candidates"
    candidates: list[dict[str, Any]] = []
    if candidate_dir.exists():
        if candidate_dir.is_symlink() or not candidate_dir.is_dir():
            raise TeamRouterError("candidates: not a plain directory")
        if not TEAM_PLAN._real_path_is_within(str(candidate_dir), str(run_dir)):
            raise TeamRouterError("candidates: real path is outside run_dir")
        for path in sorted(candidate_dir.glob("*.json"), key=lambda item: item.name.casefold()):
            if not TEAM_PLAN._real_path_is_within(str(path), str(run_dir)):
                raise TeamRouterError(f"integration-candidate: real path is outside run_dir: {path}")
            document = _artifact(path, "integration-candidate", expected_ref)
            assert document is not None
            candidates.append(document)
            observations.append({"kind": "integration-candidate", **_file_ref(path)})
    artifacts["integration-candidates"] = candidates
    return artifacts, observations


def _decision(
    manifest: dict[str, Any],
    run_exists: bool,
    artifacts: dict[str, Any],
) -> tuple[str, str | None, str, str, bool]:
    if not run_exists:
        return (
            "planned",
            "team-run",
            "prepare-run-artifacts",
            "the manifest exists but the run directory has not been prepared",
            False,
        )
    milestone = artifacts.get("milestone-result")
    if milestone is not None:
        if milestone.get("status") not in {"completed", "completed-with-ignored-residue"}:
            raise TeamRouterError("milestone-result: unsupported status")
        return "complete", None, "no-next-phase", "the milestone result is complete", False
    if artifacts.get("recovery-brief") is not None:
        return (
            "recovery-prepared",
            "team-recover",
            "await-successor-task-authority",
            "a bounded recovery brief is ready but authorizes no task creation",
            True,
        )
    if artifacts.get("recovery-plan") is not None:
        return (
            "recovering",
            "team-recover",
            "project-recovery-brief",
            "a recovery plan is prepared and its bound evidence must be rechecked",
            False,
        )
    if artifacts.get("recovery-candidate") is not None:
        return (
            "recovering",
            "team-recover",
            "prepare-recovery-plan",
            "an exact recovery candidate has been frozen",
            False,
        )
    audit = artifacts.get("finish-audit")
    if audit is not None:
        if audit.get("status") == "ready-to-finish":
            return "finishing", "team-finish", "finalize-milestone", "the final audit is ready", False
        if audit.get("status") == "blocked":
            return "blocked", "team-recover", "freeze-recovery-candidate", "the final audit is blocked", False
        raise TeamRouterError("finish-audit: unsupported status")
    review = artifacts.get("review-receipt")
    if review is not None:
        if review.get("decision") == "approved":
            return "finishing", "team-finish", "audit-final-state", "independent review approved the Gate target", False
        if review.get("decision") in {"changes-requested", "rejected"}:
            return "blocked", "team-recover", "freeze-recovery-candidate", "review did not approve the target", False
        raise TeamRouterError("review-receipt: unsupported decision")
    gate = artifacts.get("gate-receipt")
    if gate is not None:
        if gate.get("status") == "passed":
            return "reviewing", "team-finish", "record-independent-review", "all declared Gates passed", False
        if gate.get("status") == "failed":
            return "blocked", "team-recover", "freeze-recovery-candidate", "a declared Gate failed", False
        raise TeamRouterError("gate-receipt: unsupported status")
    apply_receipt = artifacts.get("integration-apply-receipt")
    if apply_receipt is not None:
        if apply_receipt.get("status") == "applied":
            return "integrating", "team-integrate", "run-declared-gates", "the exact integration plan was applied", True
        if apply_receipt.get("status") == "failed":
            return "blocked", "team-recover", "freeze-recovery-candidate", "integration apply failed", False
        raise TeamRouterError("integration-apply-receipt: unsupported status")
    if artifacts.get("integration-plan") is not None:
        return (
            "integration-prepared",
            "team-integrate",
            "apply-integration-plan",
            "the ordered integration plan is ready but Git mutation is not authorized by it",
            True,
        )
    parent = artifacts.get("parent-preflight-receipt")
    if parent is not None and parent.get("status") == "failed":
        return "blocked", "team-recover", "freeze-recovery-candidate", "parent preflight failed", False
    snapshot = artifacts.get("status-snapshot")
    candidates = artifacts.get("integration-candidates", [])
    if snapshot is not None:
        run_status = snapshot.get("run_status")
        if run_status in {"blocked", "preparation-failed"}:
            return "blocked", "team-recover", "freeze-recovery-candidate", "the status snapshot is blocked", False
        eligible = [
            lane.get("lane_id")
            for lane in snapshot.get("lanes", [])
            if lane.get("status") in {"handoff-ready", "accepted"}
        ]
        candidate_ids = {item.get("lane_id") for item in candidates}
        missing = [lane_id for lane_id in eligible if lane_id not in candidate_ids]
        if missing:
            return (
                "receiving",
                "team-integrate",
                "freeze-integration-candidates",
                f"handoff-ready lanes still need candidates: {', '.join(missing)}",
                False,
            )
        if eligible and candidate_ids:
            return (
                "receiving",
                "team-integrate",
                "prepare-integration-plan",
                "every handoff-ready lane has an exact integration candidate",
                False,
            )
        if run_status == "ready-for-dispatch":
            return (
                "dispatch-ready",
                "team-run",
                "await-task-creation-authority",
                "run preparation is complete but task creation needs separate authority",
                True,
            )
        return "observing", "team-status", "refresh-status", f"run status is {run_status}", False
    if candidates:
        raise TeamRouterError("integration candidates exist without canonical status-snapshot.json")
    if artifacts.get("status-facts") is not None:
        return "observing", "team-status", "render-status", "status facts exist without a canonical snapshot", False
    if artifacts.get("dispatch-bundle") is not None:
        return "prepared", "team-status", "initialize-status-facts", "the non-live dispatch bundle is ready", False
    if parent is not None:
        if parent.get("status") != "passed":
            raise TeamRouterError("parent-preflight-receipt: unsupported status")
        raise TeamRouterError("parent preflight passed but canonical dispatch-bundle.json is absent")
    if artifacts.get("preregistration") is not None:
        raise TeamRouterError("preregistration exists without parent-preflight-receipt.json")
    return "planned", "team-run", "prepare-run-artifacts", "the run directory is empty", False


def route(manifest_value: str, run_value: str, output_value: str | None) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _planned_run_path(manifest, run_value)
    run_exists = run_dir.exists()
    artifacts: dict[str, Any] = {}
    observations: list[dict[str, str]] = []
    if run_exists:
        artifacts, observations = _load_artifacts(run_dir, expected_ref)
    state, next_skill, next_action, reason, separate_authority = _decision(manifest, run_exists, artifacts)
    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "team-route",
        "manifest_ref": expected_ref,
        "generated_at": TEAM_STATUS._now(),
        "run_dir": str(run_dir.resolve(strict=False)),
        "run_exists": run_exists,
        "state": state,
        "next_skill": next_skill,
        "next_action": next_action,
        "reason": reason,
        "requires_separate_authority": separate_authority,
        "observations": observations,
        "authorization": {
            "task_creation": False,
            "git_mutation": False,
            "command_execution": False,
            "workspace_cleanup": False,
        },
    }
    content = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if output_value is None:
        print(content, end="")
        return 0
    if not run_exists:
        raise TeamRouterError("output: cannot persist a route before the run directory exists")
    try:
        output = TEAM_STATUS._validate_output(manifest, run_dir, output_value, "output")
        TEAM_STATUS._write_json_exclusive(output, document)
    except TEAM_STATUS.TeamStatusError as exc:
        raise TeamRouterError(str(exc)) from exc
    print(f"PASS: wrote team route at {output}")
    print("STOP: routing authorized no task, Git mutation, command, or cleanup")
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise TeamRouterError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    route_parser = commands.add_parser("route", help="select the next bounded team phase")
    route_parser.add_argument("manifest", metavar="MANIFEST")
    route_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    route_parser.add_argument("--out", metavar="ROUTE")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "route":
            return route(args.manifest, args.run_dir, args.out)
        raise TeamRouterError(f"unknown command {args.command!r}")
    except (TeamRouterError, TEAM_PLAN.ManifestError, TEAM_STATUS.TeamStatusError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
