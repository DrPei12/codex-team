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
TEAM_RUN_PATH = ROOT / "scripts" / "team-run.py"
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
CHECKPOINT_STATES = {"pending", "accepted", "changes-requested", "blocked"}


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
TEAM_RUN = _load_module("codex_team_run_for_status", TEAM_RUN_PATH)


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
                    "user_locale",
                    "execution_surface",
                    "task_title",
                    "lifecycle",
                    "depends_on",
                    "task_project",
                    "workspace",
                    "runtime",
                    "brief_ref",
                    "prompt_ref",
                    "worker_preflight_argv",
                    "backbrief_template_ref",
                    "worker_backbrief_argv",
                    "external_context_policy",
                },
                f"dispatch bundle.lanes[{index}]",
            )
            lane_id = item["lane_id"]
            lane = lane_by_id[lane_id]
            if item["role"] != lane["role"] or item["depends_on"] != lane["depends_on"]:
                raise TeamStatusError(f"dispatch lane {lane_id}: role/dependencies differ from manifest")
            if (
                item["user_locale"] != manifest["user_locale"]
                or item["execution_surface"] != lane["execution_surface"]
                or item["task_title"] != lane["task_title"]
                or item["lifecycle"] != lane["lifecycle"]
            ):
                raise TeamStatusError(
                    f"dispatch lane {lane_id}: title/surface/lifecycle differs from manifest"
                )
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
            _validate_ref_file(
                item["backbrief_template_ref"],
                f"dispatch lane {lane_id}.backbrief_template_ref",
                artifact_root,
                required=True,
            )
            if not isinstance(item["worker_preflight_argv"], list) or not item["worker_preflight_argv"]:
                raise TeamStatusError(f"dispatch lane {lane_id}: worker preflight argv is missing")
            if not all(isinstance(arg, str) and arg for arg in item["worker_preflight_argv"]):
                raise TeamStatusError(f"dispatch lane {lane_id}: worker preflight argv is invalid")
            expected_argv_tail = [
                "worker-preflight",
                preregistration["inputs"]["manifest"]["path"],
                "--brief",
                item["brief_ref"]["path"],
                "--receipt",
                str((run_dir / "worker-receipts" / f"{lane_id}.json").resolve()),
            ]
            if lane["role"] == "reviewer":
                expected_argv_tail.extend(
                    ["--gate-receipt", str((run_dir / "gate-receipt.json").resolve())]
                )
            argv = item["worker_preflight_argv"]
            if (
                len(argv) != len(expected_argv_tail) + 2
                or not Path(argv[1]).is_absolute()
                or Path(argv[1]).name.casefold() != "team-run.py"
                or argv[2:] != expected_argv_tail
            ):
                raise TeamStatusError(f"dispatch lane {lane_id}: worker preflight argv changed")
            expected_backbrief_tail = [
                "worker-backbrief",
                preregistration["inputs"]["manifest"]["path"],
                "--brief",
                item["brief_ref"]["path"],
                "--preflight-receipt",
                str((run_dir / "worker-receipts" / f"{lane_id}.json").resolve()),
                "--input",
                str((run_dir / "backbrief-inputs" / f"{lane_id}.json").resolve()),
                "--receipt",
                str((run_dir / "backbrief-receipts" / f"{lane_id}.json").resolve()),
            ]
            backbrief_argv = item["worker_backbrief_argv"]
            if (
                not isinstance(backbrief_argv, list)
                or len(backbrief_argv) != len(expected_backbrief_tail) + 2
                or not all(isinstance(arg, str) and arg for arg in backbrief_argv)
                or not Path(backbrief_argv[1]).is_absolute()
                or Path(backbrief_argv[1]).name.casefold() != "team-run.py"
                or backbrief_argv[2:] != expected_backbrief_tail
            ):
                raise TeamStatusError(f"dispatch lane {lane_id}: worker backbrief argv changed")
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
        "progress": {
            "phase": None,
            "phase_started_at": None,
            "last_material_progress_at": None,
            "material_delta": None,
            "next_bounded_action": None,
            "stalled_reason": None,
        },
        "acceptance_state": "pending",
        "integration_state": "not-started",
        "review_state": "not-requested",
        "blocked_reason": None,
        "archived": False,
    }


def _initial_checkpoint_fact(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint["checkpoint_id"],
        "state": "pending",
        "observed_at": None,
        "evidence": {"state": "not-checked", "path": None, "sha256": None},
        "reason": None,
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
        "checkpoints": [
            _initial_checkpoint_fact(checkpoint) for checkpoint in manifest["checkpoints"]
        ],
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
    if not (
        TEAM_PLAN._path_is_within(path_text, allowed_root)
        or TEAM_PLAN._real_path_is_within(path_text, allowed_root)
    ):
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
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    _require_keys(
        document,
        {"profile", "schema_version", "kind", "manifest_ref", "observed_at", "source", "lanes", "checkpoints"},
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
                "progress",
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
        progress = _require_keys(
            item["progress"],
            {
                "phase",
                "phase_started_at",
                "last_material_progress_at",
                "material_delta",
                "next_bounded_action",
                "stalled_reason",
            },
            f"{label}.progress",
        )
        _string(progress["phase"], f"{label}.progress.phase", nullable=True)
        _timestamp(
            progress["phase_started_at"],
            f"{label}.progress.phase_started_at",
            nullable=True,
        )
        _timestamp(
            progress["last_material_progress_at"],
            f"{label}.progress.last_material_progress_at",
            nullable=True,
        )
        _string(progress["material_delta"], f"{label}.progress.material_delta", nullable=True)
        _string(
            progress["next_bounded_action"],
            f"{label}.progress.next_bounded_action",
            nullable=True,
        )
        _string(progress["stalled_reason"], f"{label}.progress.stalled_reason", nullable=True)
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
    checkpoint_values = document["checkpoints"]
    if not isinstance(checkpoint_values, list):
        raise TeamStatusError("status facts.checkpoints: must be an array")
    expected_checkpoints = {
        checkpoint["checkpoint_id"]: checkpoint for checkpoint in manifest["checkpoints"]
    }
    checkpoints: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(checkpoint_values):
        label = f"status facts.checkpoints[{index}]"
        item = _require_keys(
            value,
            {"checkpoint_id", "state", "observed_at", "evidence", "reason"},
            label,
        )
        checkpoint_id = _string(item["checkpoint_id"], f"{label}.checkpoint_id")
        assert isinstance(checkpoint_id, str)
        if checkpoint_id not in expected_checkpoints or checkpoint_id in checkpoints:
            raise TeamStatusError(f"{label}: unknown or duplicate checkpoint_id {checkpoint_id!r}")
        state = _enum(item["state"], CHECKPOINT_STATES, f"{label}.state")
        _timestamp(item["observed_at"], f"{label}.observed_at", nullable=True)
        checkpoint_evidence = _require_keys(
            item["evidence"], {"state", "path", "sha256"}, f"{label}.evidence"
        )
        checkpoint_evidence_state = _enum(
            checkpoint_evidence["state"], EVIDENCE_STATES, f"{label}.evidence.state"
        )
        _validate_ref_file(
            checkpoint_evidence,
            f"{label}.evidence",
            str(run_dir),
            required=checkpoint_evidence_state == "valid",
        )
        _string(item["reason"], f"{label}.reason", nullable=True)
        if state == "accepted" and checkpoint_evidence_state != "valid":
            raise TeamStatusError(f"{label}: accepted checkpoint requires valid evidence")
        checkpoints[checkpoint_id] = item
    if set(checkpoints) != set(expected_checkpoints):
        missing = sorted(set(expected_checkpoints) - set(checkpoints))
        raise TeamStatusError(f"status facts: missing checkpoints: {missing}")
    return facts, checkpoints


def _worker_receipts(
    run_dir: Path,
    manifest: dict[str, Any],
    expected_ref: dict[str, str],
    run_artifacts: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    directory = run_dir / "worker-receipts"
    if directory.is_symlink() or not directory.is_dir():
        raise TeamStatusError("worker-receipts: missing or unsafe directory")
    lanes = {lane["lane_id"]: lane for lane in manifest["lanes"]}
    dispatch_lanes = {
        item["lane_id"]: item for item in (run_artifacts.get("dispatch") or {}).get("lanes", [])
    }
    manifest_path = run_artifacts["preregistration"]["inputs"]["manifest"]["path"]
    receipts: dict[str, dict[str, Any]] = {}
    for path in directory.iterdir():
        if path.suffix != ".json" or path.stem not in lanes:
            raise TeamStatusError(f"worker-receipts: unexpected entry {path.name!r}")
        receipt = _load_json(path, f"worker receipt {path.stem}")
        if receipt.get("profile") != TEAM_RUN_PROFILE or receipt.get("kind") != "worker-preflight-receipt":
            raise TeamStatusError(f"worker receipt {path.stem}: unexpected profile or kind")
        if receipt.get("lane_id") != path.stem:
            raise TeamStatusError(f"worker receipt {path.stem}: lane identity mismatch")
        lane = lanes[path.stem]
        if receipt.get("role") != lane["role"]:
            raise TeamStatusError(f"worker receipt {path.stem}: role differs from manifest")
        _validate_manifest_ref(receipt.get("manifest_ref"), expected_ref, f"worker receipt {path.stem}.manifest_ref")
        receipt_status = _enum(
            receipt.get("status"), {"passed", "failed"}, f"worker receipt {path.stem}.status"
        )
        binding_fields = ("dispatch_ref", "gate_receipt_ref", "target")
        if lane["role"] != "reviewer":
            if any(field in receipt for field in binding_fields):
                raise TeamStatusError(
                    f"worker receipt {path.stem}: non-reviewer contains reviewer Gate binding"
                )
        elif receipt_status == "passed" or any(field in receipt for field in binding_fields):
            if not all(field in receipt for field in binding_fields):
                raise TeamStatusError(
                    f"worker receipt {path.stem}: reviewer Gate binding is incomplete"
                )
            dispatch_lane = dispatch_lanes.get(path.stem)
            if dispatch_lane is None:
                raise TeamStatusError(f"worker receipt {path.stem}: reviewer dispatch lane is missing")
            try:
                _, gate_ref, target, dispatch_ref = TEAM_RUN._load_reviewer_gate_receipt(
                    manifest,
                    expected_ref,
                    lane,
                    manifest_path,
                    dispatch_lane["brief_ref"],
                    receipt["gate_receipt_ref"]["path"],
                    path,
                    require_current_invocation=False,
                )
            except (TEAM_RUN.TeamRunError, TEAM_PLAN.ManifestError) as exc:
                raise TeamStatusError(
                    f"worker receipt {path.stem}: invalid reviewer Gate binding: {exc}"
                ) from exc
            if (
                receipt["gate_receipt_ref"] != gate_ref
                or receipt["target"] != target
                or receipt["dispatch_ref"] != dispatch_ref
            ):
                raise TeamStatusError(
                    f"worker receipt {path.stem}: reviewer Gate binding changed"
                )
        receipts[path.stem] = receipt
    return receipts


def _backbrief_receipts(
    run_dir: Path,
    manifest: dict[str, Any],
    expected_ref: dict[str, str],
    worker_receipts: dict[str, dict[str, Any]],
    run_artifacts: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    directory = run_dir / "backbrief-receipts"
    if directory.is_symlink() or not directory.is_dir():
        raise TeamStatusError("backbrief-receipts: missing or unsafe directory")
    lanes = {lane["lane_id"]: lane for lane in manifest["lanes"]}
    dispatch_lanes = {
        item["lane_id"]: item for item in (run_artifacts.get("dispatch") or {}).get("lanes", [])
    }
    receipts: dict[str, dict[str, Any]] = {}
    for path in directory.iterdir():
        if path.suffix != ".json" or path.stem not in lanes:
            raise TeamStatusError(f"backbrief-receipts: unexpected entry {path.name!r}")
        receipt = _load_json(path, f"backbrief receipt {path.stem}")
        lane = lanes[path.stem]
        dispatch_lane = dispatch_lanes.get(path.stem)
        if dispatch_lane is None:
            raise TeamStatusError(f"backbrief receipt {path.stem}: dispatch lane is missing")
        if (
            receipt.get("profile") != TEAM_RUN_PROFILE
            or receipt.get("kind") != "worker-backbrief-receipt"
            or receipt.get("lane_id") != path.stem
            or receipt.get("role") != lane["role"]
            or receipt.get("brief_ref") != dispatch_lane["brief_ref"]
        ):
            raise TeamStatusError(f"backbrief receipt {path.stem}: identity differs from manifest/dispatch")
        _validate_manifest_ref(
            receipt.get("manifest_ref"), expected_ref, f"backbrief receipt {path.stem}.manifest_ref"
        )
        status = _enum(
            receipt.get("status"),
            {"passed", "needs-input", "failed"},
            f"backbrief receipt {path.stem}.status",
        )
        preflight = worker_receipts.get(path.stem)
        preflight_path = run_dir / "worker-receipts" / f"{path.stem}.json"
        expected_preflight_ref = None if preflight is None else {
            "path": str(preflight_path.resolve()),
            "sha256": _sha256_file(preflight_path),
        }
        if preflight is None or preflight.get("status") != "passed":
            raise TeamStatusError(f"backbrief receipt {path.stem}: passed worker preflight is missing")
        if receipt.get("preflight_ref") != expected_preflight_ref:
            raise TeamStatusError(f"backbrief receipt {path.stem}: preflight reference changed")
        input_ref = receipt.get("input_ref")
        if not isinstance(input_ref, dict) or set(input_ref) != {"path", "sha256"}:
            raise TeamStatusError(f"backbrief receipt {path.stem}: input_ref is invalid")
        _validate_ref_file(
            input_ref,
            f"backbrief receipt {path.stem}.input_ref",
            str(run_dir),
            required=True,
        )
        acknowledgement = receipt.get("acknowledgement")
        if not isinstance(acknowledgement, dict):
            raise TeamStatusError(f"backbrief receipt {path.stem}: acknowledgement is invalid")
        input_document = _load_json(input_ref["path"], f"backbrief input {path.stem}")
        if input_document != acknowledgement:
            raise TeamStatusError(
                f"backbrief receipt {path.stem}: acknowledgement differs from input bytes"
            )
        expected_ack = {
            "requirement_ids": lane["requirement_ids"],
            "ownership": lane["ownership"],
            "gate_ids": [gate["gate_id"] for gate in lane["gates"]],
            "does_not_cover": lane["does_not_cover"],
        }
        if status != "failed":
            for field, expected in expected_ack.items():
                if acknowledgement.get(field) != expected:
                    raise TeamStatusError(
                        f"backbrief receipt {path.stem}: acknowledgement {field} differs from manifest"
                    )
        assumptions = acknowledgement.get("assumptions")
        questions = acknowledgement.get("open_questions")
        if status == "passed" and (assumptions or questions):
            raise TeamStatusError(
                f"backbrief receipt {path.stem}: passed receipt cannot contain assumptions/questions"
            )
        if status == "passed" and (
            receipt.get("errors")
            or not isinstance(receipt.get("checks"), dict)
            or not receipt["checks"]
            or not all(value is True for value in receipt["checks"].values())
        ):
            raise TeamStatusError(
                f"backbrief receipt {path.stem}: passed receipt has errors or failed checks"
            )
        if status == "needs-input" and not (assumptions or questions):
            raise TeamStatusError(
                f"backbrief receipt {path.stem}: needs-input receipt has no disclosed assumption/question"
            )
        if status == "failed" and (
            not receipt.get("errors")
            or not isinstance(receipt.get("checks"), dict)
            or all(value is True for value in receipt["checks"].values())
        ):
            raise TeamStatusError(
                f"backbrief receipt {path.stem}: failed receipt lacks errors or a failed check"
            )
        receipts[path.stem] = receipt
    return receipts


def _elapsed_minutes(now_value: str, earlier_value: str) -> float:
    def parse(value: str) -> _datetime.datetime:
        return _datetime.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)

    return max(0.0, (parse(now_value) - parse(earlier_value)).total_seconds() / 60.0)


def _status_reason_and_action(
    lane: dict[str, Any],
    fact: dict[str, Any],
    receipt: dict[str, Any] | None,
    backbrief_receipt: dict[str, Any] | None,
    parent_passed: bool,
    dispatch_ready: bool,
    blocking_dependencies: list[str],
    blocking_checkpoints: list[str],
    observed_at: str,
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
    if backbrief_receipt is not None and backbrief_receipt["status"] == "failed":
        return "backbrief-failed", "worker backbrief receipt failed", "inspect the backbrief receipt and stop this task"
    if backbrief_receipt is not None and backbrief_receipt["status"] == "needs-input":
        return "needs-input", "worker backbrief disclosed assumptions or open questions", "resolve them through an accepted brief or successor"
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
        if backbrief_receipt is None:
            return "backbrief-required", "task passed preflight but has no backbrief receipt", "complete the recorded worker backbrief before implementation"
        progress = fact["progress"]
        if (
            progress["phase"] is None
            or progress["phase_started_at"] is None
            or progress["last_material_progress_at"] is None
            or progress["material_delta"] is None
            or progress["next_bounded_action"] is None
        ):
            return "checkpoint-required", "active task has no complete material-progress checkpoint", "write a new immutable progress fact and stop until it is visible"
        policy = lane["progress_policy"]
        if _elapsed_minutes(observed_at, progress["last_material_progress_at"]) > policy["heartbeat_minutes"]:
            return "checkpoint-required", "material-progress heartbeat exceeded the manifest interval", "checkpoint and stop before continuing"
        if _elapsed_minutes(observed_at, progress["phase_started_at"]) > policy["max_turn_minutes"]:
            return "checkpoint-required", "turn phase exceeded the manifest wall-clock budget", "checkpoint and stop before continuing"
        return "working", "task has passed preflight/backbrief and a current material-progress fact", "wait for the next bounded transition or blocker"
    if blocking_dependencies:
        return (
            "waiting-dependency",
            f"waiting for dependencies: {', '.join(blocking_dependencies)}",
            "wait until every dependency is accepted or integrated",
        )
    if blocking_checkpoints:
        return (
            "waiting-checkpoint",
            f"waiting for accepted checkpoints: {', '.join(blocking_checkpoints)}",
            "accept or reject the exact checkpoint evidence before dispatch",
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
    if any(status in {"blocked", "preflight-failed", "backbrief-failed", "changes-requested"} for status in statuses):
        return "blocked"
    if any(
        status in {"needs-input", "needs-evidence", "no-signal", "backbrief-required", "checkpoint-required"}
        for status in statuses
    ):
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
    if any(status == "waiting-checkpoint" for status in statuses):
        return "waiting-checkpoint"
    return "planned"


def render(manifest_value: str, run_value: str, facts_value: str, output_value: str) -> int:
    manifest = TEAM_PLAN.load_manifest(manifest_value)
    TEAM_PLAN.validate_manifest(manifest)
    expected_ref = _manifest_ref(manifest)
    run_dir = _validate_run_dir(manifest, run_value)
    run_artifacts = _load_run_artifacts(manifest, run_dir, expected_ref)
    facts_path = _validate_facts_path(run_dir, facts_value)
    facts_document = _load_json(facts_path, "status facts")
    facts, checkpoint_facts = _validate_facts(
        facts_document, manifest, expected_ref, run_dir
    )
    receipts = _worker_receipts(run_dir, manifest, expected_ref, run_artifacts)
    backbrief_receipts = _backbrief_receipts(
        run_dir, manifest, expected_ref, receipts, run_artifacts
    )
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
        blocking_checkpoints = [
            checkpoint["checkpoint_id"]
            for checkpoint in manifest["checkpoints"]
            if lane_id in checkpoint["before_lanes"]
            and checkpoint_facts[checkpoint["checkpoint_id"]]["state"] != "accepted"
        ]
        status, reason, next_action = _status_reason_and_action(
            lane,
            facts[lane_id],
            receipts.get(lane_id),
            backbrief_receipts.get(lane_id),
            parent_passed,
            dispatch_ready,
            blocking,
            blocking_checkpoints,
            facts_document["observed_at"],
        )
        receipt_ref = None
        receipt_path = run_dir / "worker-receipts" / f"{lane_id}.json"
        if lane_id in receipts:
            receipt_ref = {"path": str(receipt_path.resolve()), "sha256": _sha256_file(receipt_path)}
        backbrief_ref = None
        backbrief_path = run_dir / "backbrief-receipts" / f"{lane_id}.json"
        if lane_id in backbrief_receipts:
            backbrief_ref = {
                "path": str(backbrief_path.resolve()),
                "sha256": _sha256_file(backbrief_path),
            }
        derived.append(
            {
                "lane_id": lane_id,
                "role": lane["role"],
                "status": status,
                "reason": reason,
                "depends_on": copy.deepcopy(lane["depends_on"]),
                "blocking_dependencies": blocking,
                "blocking_checkpoints": blocking_checkpoints,
                "task": copy.deepcopy(facts[lane_id]["task"]),
                "workspace": copy.deepcopy(facts[lane_id]["workspace"]),
                "progress": copy.deepcopy(facts[lane_id]["progress"]),
                "worker_receipt_ref": receipt_ref,
                "backbrief_receipt_ref": backbrief_ref,
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
        "checkpoints": [
            copy.deepcopy(checkpoint_facts[checkpoint["checkpoint_id"]])
            for checkpoint in manifest["checkpoints"]
        ],
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
