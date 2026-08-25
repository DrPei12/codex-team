#!/usr/bin/env python3
"""Derive a read-only Codex team status snapshot from durable artifact facts."""

from __future__ import annotations

import argparse
import copy
import datetime as _datetime
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


PROFILE = "codex-multitask-team-status"
SCHEMA_VERSION = "0.1"
ROOT = Path(__file__).resolve().parents[1]
TEAM_PLAN_PATH = ROOT / "scripts" / "team-plan.py"
TEAM_RUN_PROFILE = "codex-multitask-team-run"

TASK_STATES = {
    "not-created",
    "active",
    "idle",
    "waiting-input",
    "completed",
    "failed",
    "canceled",
    "archived",
    "unknown",
}
REPORT_STATES = {"absent", "partial", "completed", "blocked"}
EVIDENCE_STATES = {"not-checked", "missing", "valid", "invalid"}
ACCEPTANCE_STATES = {"pending", "accepted", "rejected"}
INTEGRATION_STATES = {"not-started", "pending", "integrated", "blocked"}
REVIEW_STATES = {"not-requested", "pending", "approved", "changes-requested"}


class TeamStatusError(ValueError):
    """An actionable status input or projection error."""


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise TeamStatusError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEAM_PLAN = _load_module("codex_team_plan_for_status", TEAM_PLAN_PATH)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path_value: str | Path, label: str) -> dict[str, Any]:
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise TeamStatusError(f"{label}: symlink or missing file is not allowed: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise TeamStatusError(f"{label}: invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TeamStatusError(f"{label}: root must be an object")
    return value


def _write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.write("\n")
    except FileExistsError as exc:
        raise TeamStatusError(f"refusing to overwrite existing file: {path}") from exc
    except OSError as exc:
        raise TeamStatusError(f"cannot write {path}: {exc}") from exc


def _sha256_file(path: Path) -> str:
    try:
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    except OSError as exc:
        raise TeamStatusError(f"cannot hash {path}: {exc}") from exc


def _now() -> str:
    return _datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _manifest_ref(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        "run_id": manifest["run_id"],
        "sha256": TEAM_PLAN.manifest_digest(manifest),
    }


def _normal_path(value: str) -> str:
    return TEAM_PLAN._normal_path(value)


def _real_path(value: str) -> str:
    return TEAM_PLAN._real_path(value)


def _require_keys(value: Any, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TeamStatusError(f"{label}: must be an object")
    missing = sorted(required - value.keys())
    extra = sorted(value.keys() - required)
    if missing:
        raise TeamStatusError(f"{label}: missing fields: {missing}")
    if extra:
        raise TeamStatusError(f"{label}: unexpected fields: {extra}")
    return value


def _string(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TeamStatusError(f"{label}: must be a non-empty string")
    return value


def _enum(value: Any, allowed: set[str], label: str) -> str:
    text = _string(value, label)
    assert isinstance(text, str)
    if text not in allowed:
        raise TeamStatusError(f"{label}: must be one of {sorted(allowed)}")
    return text


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise TeamStatusError(f"{label}: must be boolean")
    return value


def _timestamp(value: Any, label: str, *, nullable: bool = False) -> str | None:
    text = _string(value, label, nullable=nullable)
    if text is None:
        return None
    try:
        _datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TeamStatusError(f"{label}: must be an RFC3339-compatible timestamp") from exc
    return text


def _sha256(value: Any, label: str, *, nullable: bool = False) -> str | None:
    text = _string(value, label, nullable=nullable)
    if text is None:
        return None
    if len(text) != 71 or not text.startswith("sha256:"):
        raise TeamStatusError(f"{label}: must be sha256:<64 lowercase hex>")
    try:
        int(text[7:], 16)
    except ValueError as exc:
        raise TeamStatusError(f"{label}: must be sha256:<64 lowercase hex>") from exc
    if text != text.lower():
        raise TeamStatusError(f"{label}: must use lowercase hex")
    return text


def _validate_manifest_ref(value: Any, expected: dict[str, str], label: str) -> None:
    reference = _require_keys(value, {"run_id", "sha256"}, label)
    _string(reference["run_id"], f"{label}.run_id")
    _sha256(reference["sha256"], f"{label}.sha256")
    if reference != expected:
        raise TeamStatusError(f"{label}: manifest identity mismatch")


def _validate_run_dir(manifest: dict[str, Any], run_value: str) -> Path:
    run_text = TEAM_PLAN._absolute_path(run_value, "run_dir", label="run_dir")
    artifact_root = manifest["workspace_policy"]["artifact_root"]
    if not TEAM_PLAN._path_is_within(run_text, artifact_root):
        raise TeamStatusError(f"run_dir: {run_text} is outside artifact_root")
    run_dir = Path(run_text)
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise TeamStatusError(f"run_dir: not a plain directory: {run_dir}")
    if not TEAM_PLAN._real_path_is_within(str(run_dir), artifact_root):
        raise TeamStatusError("run_dir: real path is outside artifact_root")
    return run_dir


def _validate_output(manifest: dict[str, Any], run_dir: Path, output_value: str, label: str) -> Path:
    output_text = TEAM_PLAN._absolute_path(output_value, label, label=label)
    if not TEAM_PLAN._path_is_within(output_text, str(run_dir)):
        raise TeamStatusError(f"{label}: must be inside run_dir")
    TEAM_PLAN._check_output_parent_real_path(
        output_text,
        manifest["workspace_policy"]["artifact_root"],
        manifest["workspace_policy"]["experiment_root"],
    )
    output = Path(output_text)
    if output.exists():
        raise TeamStatusError(f"{label}: already exists; refusing to overwrite: {output}")
    if not output.parent.is_dir():
        raise TeamStatusError(f"{label}: parent directory does not exist: {output.parent}")
    return output


def _validate_facts_path(run_dir: Path, facts_value: str) -> Path:
    facts_text = TEAM_PLAN._absolute_path(facts_value, "facts", label="facts")
    if not TEAM_PLAN._path_is_within(facts_text, str(run_dir)):
        raise TeamStatusError("facts: must be inside run_dir")
    facts = Path(facts_text)
    if facts.is_symlink() or not facts.is_file():
        raise TeamStatusError(f"facts: symlink or missing file is not allowed: {facts}")
    if not TEAM_PLAN._real_path_is_within(str(facts), str(run_dir)):
        raise TeamStatusError("facts: real path is outside run_dir")
    return facts


def _load_run_artifacts(
    manifest: dict[str, Any],
    run_dir: Path,
    expected_ref: dict[str, str],
) -> dict[str, Any]:
    preregistration = _load_json(run_dir / "preregistration.json", "preregistration")
    parent = _load_json(run_dir / "parent-preflight-receipt.json", "parent receipt")
    for label, document, kind in (
        ("preregistration", preregistration, "preregistration"),
        ("parent receipt", parent, "parent-preflight-receipt"),
    ):
        if document.get("profile") != TEAM_RUN_PROFILE or document.get("kind") != kind:
            raise TeamStatusError(f"{label}: unexpected profile or kind")
        _validate_manifest_ref(document.get("manifest_ref"), expected_ref, f"{label}.manifest_ref")

    parent_status = _enum(parent.get("status"), {"passed", "failed"}, "parent receipt.status")
    dispatch_path = run_dir / "dispatch-bundle.json"
    dispatch: dict[str, Any] | None = None
    if dispatch_path.exists():
        dispatch = _load_json(dispatch_path, "dispatch bundle")
        if dispatch.get("profile") != TEAM_RUN_PROFILE or dispatch.get("kind") != "dispatch-bundle":
            raise TeamStatusError("dispatch bundle: unexpected profile or kind")
        _validate_manifest_ref(dispatch.get("manifest_ref"), expected_ref, "dispatch bundle.manifest_ref")
        lane_ids = [item.get("lane_id") for item in dispatch.get("lanes", [])]
        expected_ids = [lane["lane_id"] for lane in manifest["lanes"]]
        if lane_ids != expected_ids:
            raise TeamStatusError("dispatch bundle: lane order or identity differs from manifest")
        prereg_briefs = {
            item.get("lane_id"): item
            for item in preregistration.get("inputs", {}).get("briefs", [])
            if isinstance(item, dict)
        }
        if set(prereg_briefs) != set(expected_ids):
            raise TeamStatusError("preregistration: brief identities differ from manifest")
        lane_by_id = {lane["lane_id"]: lane for lane in manifest["lanes"]}
        artifact_root = manifest["workspace_policy"]["artifact_root"]
        for index, item_value in enumerate(dispatch["lanes"]):
            item = _require_keys(
                item_value,
                {
                    "lane_id",
                    "role",
                    "depends_on",
                    "task_project",
                    "workspace",
                    "runtime",
                    "brief_ref",
                    "prompt_ref",
                    "worker_preflight_argv",
                    "external_context_policy",
                },
                f"dispatch bundle.lanes[{index}]",
            )
            lane_id = item["lane_id"]
            lane = lane_by_id[lane_id]
            if item["role"] != lane["role"] or item["depends_on"] != lane["depends_on"]:
                raise TeamStatusError(f"dispatch lane {lane_id}: role/dependencies differ from manifest")
            if item["task_project"] != manifest["task_project"]:
                raise TeamStatusError(f"dispatch lane {lane_id}: task project differs from manifest")
            if item["workspace"] != lane["workspace"]:
                raise TeamStatusError(f"dispatch lane {lane_id}: workspace differs from manifest")
            if item["runtime"] != manifest["runtime"]:
                raise TeamStatusError(f"dispatch lane {lane_id}: runtime differs from manifest")
            if item["brief_ref"] != prereg_briefs[lane_id]:
                raise TeamStatusError(f"dispatch lane {lane_id}: brief reference differs from preregistration")
            _validate_ref_file(
                item["brief_ref"],
                f"dispatch lane {lane_id}.brief_ref",
                artifact_root,
                required=True,
            )
            prompt_ref = _require_keys(
                item["prompt_ref"],
                {"path", "sha256"},
                f"dispatch lane {lane_id}.prompt_ref",
            )
            prompt_relative = _string(prompt_ref["path"], f"dispatch lane {lane_id}.prompt_ref.path")
            prompt_digest = _sha256(prompt_ref["sha256"], f"dispatch lane {lane_id}.prompt_ref.sha256")
            assert isinstance(prompt_relative, str) and isinstance(prompt_digest, str)
            prompt_path = run_dir / prompt_relative
            if prompt_path.is_symlink() or not prompt_path.is_file():
                raise TeamStatusError(f"dispatch lane {lane_id}: prompt file is missing or unsafe")
            if not TEAM_PLAN._real_path_is_within(str(prompt_path), str(run_dir)):
                raise TeamStatusError(f"dispatch lane {lane_id}: prompt real path is outside run_dir")
            if _sha256_file(prompt_path) != prompt_digest:
                raise TeamStatusError(f"dispatch lane {lane_id}: prompt hash mismatch")
            if not isinstance(item["worker_preflight_argv"], list) or not item["worker_preflight_argv"]:
                raise TeamStatusError(f"dispatch lane {lane_id}: worker preflight argv is missing")
            if not all(isinstance(arg, str) and arg for arg in item["worker_preflight_argv"]):
                raise TeamStatusError(f"dispatch lane {lane_id}: worker preflight argv is invalid")
            if item["external_context_policy"] != "untrusted-background-only":
                raise TeamStatusError(f"dispatch lane {lane_id}: external context policy changed")
    if parent_status == "passed" and dispatch is None:
        raise TeamStatusError("run artifacts: passed parent receipt requires dispatch bundle")
    if parent_status == "failed" and dispatch is not None:
        raise TeamStatusError("run artifacts: failed parent receipt must not have dispatch bundle")
    return {
        "preregistration": preregistration,
        "parent": parent,
        "dispatch": dispatch,
    }


def _initial_lane_fact(manifest: dict[str, Any], lane: dict[str, Any]) -> dict[str, Any]:
    return {
        "lane_id": lane["lane_id"],
        "task": {
            "thread_id": None,
            "project_id": None,
            "state": "not-created",
            "last_event_at": None,
        },
        "workspace": {
            "path": lane["workspace"]["path"],
            "head": None,
            "ordinary_status": [],
            "observed_at": None,
        },
        "worker_report": {"status": "absent", "path": None, "sha256": None},
        "evidence": {"state": "not-checked", "path": None, "sha256": None},
        "acceptance_state": "pending",
        "integration_state": "not-started",
        "review_state": "not-requested",
        "blocked_reason": None,
        "archived": False,
    }


def init_facts(manifest_value: str, run_value: str, output_value: str) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    _load_run_artifacts(manifest, run_dir, expected_ref)
    output = _validate_output(manifest, run_dir, output_value, "output")
    document = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "status-facts",
        "manifest_ref": expected_ref,
        "observed_at": _now(),
        "source": "prepared-run",
        "lanes": [_initial_lane_fact(manifest, lane) for lane in manifest["lanes"]],
    }
    _write_json_exclusive(output, document)
    print(f"PASS: initialized status facts for {len(document['lanes'])} lanes at {output}")
    print("STOP: no Codex task, Git workspace, or message state was changed")
    return 0


def _validate_ref_file(
    value: dict[str, Any],
    label: str,
    allowed_root: str,
    *,
    required: bool,
) -> None:
    path_value = _string(value["path"], f"{label}.path", nullable=not required)
    digest = _sha256(value["sha256"], f"{label}.sha256", nullable=not required)
    if not required:
        if (path_value is None) != (digest is None):
            raise TeamStatusError(f"{label}: path and sha256 must both be null or both be present")
        if path_value is None:
            return
    assert path_value is not None and digest is not None
    path_text = TEAM_PLAN._absolute_path(path_value, f"{label}.path", label=f"{label}.path")
    if not TEAM_PLAN._path_is_within(path_text, allowed_root):
        raise TeamStatusError(f"{label}: path is outside allowed root")
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise TeamStatusError(f"{label}: symlink or missing file is not allowed")
    if _sha256_file(path) != digest:
        raise TeamStatusError(f"{label}: file hash mismatch")


def _validate_facts(
    document: dict[str, Any],
    manifest: dict[str, Any],
    expected_ref: dict[str, str],
    run_dir: Path,
) -> dict[str, dict[str, Any]]:
    _require_keys(
        document,
        {"profile", "schema_version", "kind", "manifest_ref", "observed_at", "source", "lanes"},
        "status facts",
    )
    if document["profile"] != PROFILE or document["schema_version"] != SCHEMA_VERSION:
        raise TeamStatusError("status facts: unsupported profile or schema_version")
    if document["kind"] != "status-facts":
        raise TeamStatusError("status facts: kind must be status-facts")
    _validate_manifest_ref(document["manifest_ref"], expected_ref, "status facts.manifest_ref")
    _timestamp(document["observed_at"], "status facts.observed_at")
    _string(document["source"], "status facts.source")
    lanes_value = document["lanes"]
    if not isinstance(lanes_value, list):
        raise TeamStatusError("status facts.lanes: must be an array")

    expected_lanes = {lane["lane_id"]: lane for lane in manifest["lanes"]}
    facts: dict[str, dict[str, Any]] = {}
    project_id = manifest["task_project"]["project_id"]
    for index, value in enumerate(lanes_value):
        label = f"status facts.lanes[{index}]"
        item = _require_keys(
            value,
            {
                "lane_id",
                "task",
                "workspace",
                "worker_report",
                "evidence",
                "acceptance_state",
                "integration_state",
                "review_state",
                "blocked_reason",
                "archived",
            },
            label,
        )
        lane_id = _string(item["lane_id"], f"{label}.lane_id")
        assert isinstance(lane_id, str)
        if lane_id not in expected_lanes or lane_id in facts:
            raise TeamStatusError(f"{label}: unknown or duplicate lane_id {lane_id!r}")
        lane = expected_lanes[lane_id]

        task = _require_keys(
            item["task"],
            {"thread_id", "project_id", "state", "last_event_at"},
            f"{label}.task",
        )
        thread_id = _string(task["thread_id"], f"{label}.task.thread_id", nullable=True)
        task_project_id = _string(task["project_id"], f"{label}.task.project_id", nullable=True)
        task_state = _enum(task["state"], TASK_STATES, f"{label}.task.state")
        _timestamp(task["last_event_at"], f"{label}.task.last_event_at", nullable=True)
        if task_state == "not-created":
            if thread_id is not None or task_project_id is not None:
                raise TeamStatusError(f"{label}.task: not-created task cannot have identities")
        elif thread_id is None or task_project_id != project_id:
            raise TeamStatusError(f"{label}.task: created task requires matching thread/project identity")

        workspace = _require_keys(
            item["workspace"],
            {"path", "head", "ordinary_status", "observed_at"},
            f"{label}.workspace",
        )
        workspace_path = _string(workspace["path"], f"{label}.workspace.path")
        assert isinstance(workspace_path, str)
        if _normal_path(workspace_path) != _normal_path(lane["workspace"]["path"]):
            raise TeamStatusError(f"{label}.workspace.path: differs from manifest")
        head = _string(workspace["head"], f"{label}.workspace.head", nullable=True)
        if head is not None and (len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head)):
            raise TeamStatusError(f"{label}.workspace.head: must be a lowercase 40-character Git hash")
        if not isinstance(workspace["ordinary_status"], list) or not all(
            isinstance(entry, str) for entry in workspace["ordinary_status"]
        ):
            raise TeamStatusError(f"{label}.workspace.ordinary_status: must be a string array")
        _timestamp(workspace["observed_at"], f"{label}.workspace.observed_at", nullable=True)

        report = _require_keys(item["worker_report"], {"status", "path", "sha256"}, f"{label}.worker_report")
        report_state = _enum(report["status"], REPORT_STATES, f"{label}.worker_report.status")
        _validate_ref_file(
            report,
            f"{label}.worker_report",
            str(run_dir),
            required=report_state != "absent",
        )
        if report_state == "absent" and (report["path"] is not None or report["sha256"] is not None):
            raise TeamStatusError(f"{label}.worker_report: absent report must not have a reference")

        evidence = _require_keys(item["evidence"], {"state", "path", "sha256"}, f"{label}.evidence")
        evidence_state = _enum(evidence["state"], EVIDENCE_STATES, f"{label}.evidence.state")
        _validate_ref_file(
            evidence,
            f"{label}.evidence",
            str(run_dir),
            required=evidence_state == "valid",
        )
        acceptance = _enum(item["acceptance_state"], ACCEPTANCE_STATES, f"{label}.acceptance_state")
        integration = _enum(item["integration_state"], INTEGRATION_STATES, f"{label}.integration_state")
        review = _enum(item["review_state"], REVIEW_STATES, f"{label}.review_state")
        _string(item["blocked_reason"], f"{label}.blocked_reason", nullable=True)
        _boolean(item["archived"], f"{label}.archived")

        if report_state == "completed" and task_state != "completed":
            raise TeamStatusError(f"{label}: completed report requires completed task state")
        if acceptance == "accepted" and not (report_state == "completed" and evidence_state == "valid"):
            raise TeamStatusError(f"{label}: accepted state requires completed report and valid evidence")
        if integration != "not-started" and acceptance != "accepted":
            raise TeamStatusError(f"{label}: integration state requires accepted state")
        if review in {"approved", "changes-requested", "pending"} and integration != "integrated":
            raise TeamStatusError(f"{label}: review state requires integrated state")
        facts[lane_id] = item

    if set(facts) != set(expected_lanes):
        missing = sorted(set(expected_lanes) - set(facts))
        raise TeamStatusError(f"status facts: missing lanes: {missing}")
    return facts


def _worker_receipts(
    run_dir: Path,
    manifest: dict[str, Any],
    expected_ref: dict[str, str],
) -> dict[str, dict[str, Any]]:
    directory = run_dir / "worker-receipts"
    if directory.is_symlink() or not directory.is_dir():
        raise TeamStatusError("worker-receipts: missing or unsafe directory")
    lanes = {lane["lane_id"] for lane in manifest["lanes"]}
    receipts: dict[str, dict[str, Any]] = {}
    for path in directory.iterdir():
        if path.suffix != ".json" or path.stem not in lanes:
            raise TeamStatusError(f"worker-receipts: unexpected entry {path.name!r}")
        receipt = _load_json(path, f"worker receipt {path.stem}")
        if receipt.get("profile") != TEAM_RUN_PROFILE or receipt.get("kind") != "worker-preflight-receipt":
            raise TeamStatusError(f"worker receipt {path.stem}: unexpected profile or kind")
        if receipt.get("lane_id") != path.stem:
            raise TeamStatusError(f"worker receipt {path.stem}: lane identity mismatch")
        _validate_manifest_ref(receipt.get("manifest_ref"), expected_ref, f"worker receipt {path.stem}.manifest_ref")
        _enum(receipt.get("status"), {"passed", "failed"}, f"worker receipt {path.stem}.status")
        receipts[path.stem] = receipt
    return receipts


def _status_reason_and_action(
    lane: dict[str, Any],
    fact: dict[str, Any],
    receipt: dict[str, Any] | None,
    parent_passed: bool,
    dispatch_ready: bool,
    blocking_dependencies: list[str],
) -> tuple[str, str, str | None]:
    lane_id = lane["lane_id"]
    task_state = fact["task"]["state"]
    report_state = fact["worker_report"]["status"]
    evidence_state = fact["evidence"]["state"]
    acceptance = fact["acceptance_state"]
    integration = fact["integration_state"]
    review = fact["review_state"]

    if fact["archived"] or task_state == "archived":
        return "archived", "task is archived", None
    if not parent_passed:
        return "preparation-failed", "parent preflight failed", "inspect the parent preflight receipt"
    if fact["blocked_reason"]:
        return "blocked", fact["blocked_reason"], "resolve the recorded blocker through a successor action"
    if receipt is not None and receipt["status"] == "failed":
        return "preflight-failed", "worker preflight receipt failed", "inspect the worker receipt and stop this task"
    if review == "changes-requested":
        return "changes-requested", "review requested changes", "route the review facts to the owning worker"
    at_handoff_boundary = (
        task_state == "completed"
        or report_state == "completed"
        or acceptance != "pending"
        or integration != "not-started"
        or review != "not-requested"
    )
    if at_handoff_boundary and fact["workspace"]["ordinary_status"]:
        return "blocked", "workspace is not ordinary clean at the handoff boundary", "resolve or explain the workspace changes"
    if integration == "blocked":
        return "blocked", "integration is blocked", "inspect the integration evidence"
    if evidence_state == "invalid":
        return "blocked", "evidence is invalid", "request corrected evidence without accepting the handoff"
    if acceptance == "rejected":
        return "blocked", "handoff was rejected", "record the rejection reason and decide recovery"
    if task_state in {"failed", "canceled"} or report_state == "blocked":
        return "blocked", f"task/report state is {task_state}/{report_state}", "record the blocker and decide recovery"
    if review == "approved":
        return "reviewed", "integrated result is approved", None
    if review == "pending":
        return "review-pending", "integrated result awaits review", "complete independent review"
    if integration == "integrated":
        return "integrated", "accepted result is integrated", "request independent review"
    if integration == "pending":
        return "integrating", "accepted result is in the integration queue", "continue ordered integration"
    if acceptance == "accepted":
        return "accepted", "handoff identity and evidence were accepted", "enqueue the lane for ordered integration"
    if report_state == "completed":
        if evidence_state == "valid":
            return "handoff-ready", "completed report has valid evidence", "validate and accept or reject the handoff"
        return "needs-evidence", "completed report lacks valid evidence", "request missing or corrected evidence"
    if task_state == "waiting-input":
        return "needs-input", "task is waiting for authorized input", "provide or escalate the required input"
    if task_state == "completed":
        return "needs-evidence", "task completed without a completed report", "request the worker report and evidence"
    if task_state == "unknown":
        return "no-signal", "task exists but current state is unknown", "refresh the task observation"
    if task_state in {"active", "idle"}:
        if receipt is None:
            return "preflight", "task exists but has no worker preflight receipt", "run the recorded worker preflight argv"
        return "working", "task is active with a passed worker preflight", "wait for a state transition or blocker"
    if blocking_dependencies:
        return (
            "waiting-dependency",
            f"waiting for dependencies: {', '.join(blocking_dependencies)}",
            "wait until every dependency is accepted or integrated",
        )
    if dispatch_ready:
        return (
            "ready-for-dispatch",
            "prepared lane has no task binding and its dependencies are satisfied",
            f"create Codex task for lane {lane_id} only after explicit authorization",
        )
    return "planned", "lane is planned but no dispatch bundle is available", "complete run preparation"


def _run_status(lanes: list[dict[str, Any]]) -> str:
    statuses = [lane["status"] for lane in lanes]
    if any(status == "preparation-failed" for status in statuses):
        return "preparation-failed"
    if any(status in {"blocked", "preflight-failed", "changes-requested"} for status in statuses):
        return "blocked"
    if any(status in {"needs-input", "needs-evidence", "no-signal"} for status in statuses):
        return "needs-input"
    if any(status in {"working", "preflight", "integrating", "review-pending"} for status in statuses):
        return "working"
    if statuses and all(status in {"reviewed", "archived"} for status in statuses):
        return "reviewed"
    if any(status in {"handoff-ready", "accepted", "integrated"} for status in statuses):
        return "receiving"
    if any(status == "ready-for-dispatch" for status in statuses):
        return "ready-for-dispatch"
    if any(status == "waiting-dependency" for status in statuses):
        return "waiting-dependency"
    return "planned"


def render(manifest_value: str, run_value: str, facts_value: str, output_value: str) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    run_artifacts = _load_run_artifacts(manifest, run_dir, expected_ref)
    facts_path = _validate_facts_path(run_dir, facts_value)
    facts_document = _load_json(facts_path, "status facts")
    facts = _validate_facts(facts_document, manifest, expected_ref, run_dir)
    receipts = _worker_receipts(run_dir, manifest, expected_ref)
    output = _validate_output(manifest, run_dir, output_value, "output")

    parent_passed = run_artifacts["parent"]["status"] == "passed"
    dispatch_ready = run_artifacts["dispatch"] is not None
    lane_by_id = {lane["lane_id"]: lane for lane in manifest["lanes"]}
    derived: list[dict[str, Any]] = []
    for lane_id in manifest["integration_order"]:
        lane = lane_by_id[lane_id]
        blocking = [
            dependency
            for dependency in lane["depends_on"]
            if facts[dependency]["acceptance_state"] != "accepted"
        ]
        status, reason, next_action = _status_reason_and_action(
            lane,
            facts[lane_id],
            receipts.get(lane_id),
            parent_passed,
            dispatch_ready,
            blocking,
        )
        receipt_ref = None
        receipt_path = run_dir / "worker-receipts" / f"{lane_id}.json"
        if lane_id in receipts:
            receipt_ref = {"path": str(receipt_path.resolve()), "sha256": _sha256_file(receipt_path)}
        derived.append(
            {
                "lane_id": lane_id,
                "role": lane["role"],
                "status": status,
                "reason": reason,
                "depends_on": copy.deepcopy(lane["depends_on"]),
                "blocking_dependencies": blocking,
                "task": copy.deepcopy(facts[lane_id]["task"]),
                "workspace": copy.deepcopy(facts[lane_id]["workspace"]),
                "worker_receipt_ref": receipt_ref,
                "next_action": next_action,
            }
        )

    counts: dict[str, int] = {}
    next_actions: list[dict[str, str]] = []
    for lane in derived:
        counts[lane["status"]] = counts.get(lane["status"], 0) + 1
        if lane["next_action"] is not None:
            next_actions.append({"lane_id": lane["lane_id"], "action": lane["next_action"]})
    snapshot = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "kind": "status-snapshot",
        "manifest_ref": expected_ref,
        "generated_at": _now(),
        "facts_ref": {"path": str(facts_path.resolve()), "sha256": _sha256_file(facts_path)},
        "run_status": _run_status(derived),
        "counts": counts,
        "lanes": derived,
        "next_actions": next_actions,
    }
    _write_json_exclusive(output, snapshot)
    print(f"PASS: rendered status for {len(derived)} lanes at {output}")
    print("STOP: no Codex task, message, wait cursor, or Git workspace was changed")
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise TeamStatusError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("init-facts", help="initialize a no-task status fact snapshot")
    init_parser.add_argument("manifest", metavar="MANIFEST")
    init_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    init_parser.add_argument("--out", required=True, metavar="FACTS")
    render_parser = commands.add_parser("render", help="derive display status from durable facts")
    render_parser.add_argument("manifest", metavar="MANIFEST")
    render_parser.add_argument("--run-dir", required=True, metavar="RUN_DIR")
    render_parser.add_argument("--facts", required=True, metavar="FACTS")
    render_parser.add_argument("--out", required=True, metavar="SNAPSHOT")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "init-facts":
            return init_facts(args.manifest, args.run_dir, args.out)
        if args.command == "render":
            return render(args.manifest, args.run_dir, args.facts, args.out)
        raise TeamStatusError(f"unknown command {args.command!r}")
    except (TeamStatusError, TEAM_PLAN.ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
