#!/usr/bin/env python3
"""Validate Codex multitask workflow artifacts without third-party packages.

The JSON Schema is the structural contract. This helper enforces the same
frozen v0.1 profile plus cross-artifact invariants needed by the first live
workflow: lane references, workspace/ownership equality, report proof fields,
and integration-queue consistency.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable


PROFILE = "codex-multitask-workflow"
SCHEMA_VERSION = "0.1"
KINDS = {
    "session-plan",
    "roster",
    "task-brief",
    "worker-report",
    "integration-queue",
}
GIT_HASH_RE = re.compile(r"^[0-9a-f]{40,64}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ValidationFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def require_exact_keys(value: Any, expected: set[str], field: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{field} must be an object")
    missing = sorted(expected - value.keys())
    extra = sorted(value.keys() - expected)
    require(not missing, f"{field} missing required keys: {', '.join(missing)}")
    require(not extra, f"{field} has unexpected keys: {', '.join(extra)}")
    return value


def require_non_empty_string(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value


def require_nullable_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return require_non_empty_string(value, field)


def require_string_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    require(isinstance(value, list), f"{field} must be an array")
    require(allow_empty or bool(value), f"{field} must not be empty")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(require_non_empty_string(item, f"{field}[{index}]"))
    return result


def require_bool(value: Any, field: str) -> bool:
    require(type(value) is bool, f"{field} must be boolean")
    return value


def require_int(value: Any, field: str, *, minimum: int | None = None) -> int:
    require(type(value) is int, f"{field} must be an integer")
    if minimum is not None:
        require(value >= minimum, f"{field} must be >= {minimum}")
    return value


def require_number(value: Any, field: str, *, minimum: float | None = None) -> float:
    require(type(value) in {int, float}, f"{field} must be a number")
    numeric = float(value)
    if minimum is not None:
        require(numeric >= minimum, f"{field} must be >= {minimum}")
    return numeric


def require_enum(value: Any, allowed: set[str], field: str) -> str:
    text = require_non_empty_string(value, field)
    require(text in allowed, f"{field} must be one of: {', '.join(sorted(allowed))}")
    return text


def require_git_hash(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    text = require_non_empty_string(value, field)
    require(bool(GIT_HASH_RE.fullmatch(text)), f"{field} must be a lowercase 40-64 character Git hash")
    return text


def require_sha256(value: Any, field: str) -> str:
    text = require_non_empty_string(value, field)
    require(bool(SHA256_RE.fullmatch(text)), f"{field} must be sha256:<64 lowercase hex>")
    return text


def require_timestamp(value: Any, field: str) -> str:
    text = require_non_empty_string(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationFailure(f"{field} must be an RFC3339-compatible timestamp") from exc
    return text


def require_absolute_path(value: Any, field: str) -> str:
    text = require_non_empty_string(value, field)
    require(
        Path(text).is_absolute() or PureWindowsPath(text).is_absolute(),
        f"{field} must be an absolute path",
    )
    return text


def normalized_repo_path(value: Any, field: str) -> str:
    text = require_non_empty_string(value, field).replace("\\", "/")
    require(not text.startswith("/"), f"{field} must be repository-relative")
    require(not PureWindowsPath(text).is_absolute(), f"{field} must be repository-relative")
    parts = [part for part in text.split("/") if part not in {"", "."}]
    require(parts and ".." not in parts, f"{field} must not escape the repository")
    return "/".join(parts)


def unique(values: Iterable[str], field: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        require(value not in seen, f"{field} contains duplicate value: {value}")
        seen.add(value)
    return seen


def validate_header(document: dict[str, Any], kind: str) -> None:
    require(document["profile"] == PROFILE, f"profile must be {PROFILE}")
    require(document["schema_version"] == SCHEMA_VERSION, f"schema_version must be {SCHEMA_VERSION}")
    require(document["kind"] == kind, f"kind must be {kind}")
    require_non_empty_string(document["artifact_id"], "artifact_id")
    require_non_empty_string(document["context_id"], "context_id")
    require_timestamp(document["created_at"], "created_at")


def validate_artifact_ref(value: Any, field: str) -> None:
    item = require_exact_keys(value, {"artifact_id", "path", "sha256"}, field)
    require_non_empty_string(item["artifact_id"], f"{field}.artifact_id")
    require_non_empty_string(item["path"], f"{field}.path")
    require_sha256(item["sha256"], f"{field}.sha256")


def validate_task_project(value: Any, field: str) -> None:
    item = require_exact_keys(value, {"project_id", "path", "environment"}, field)
    require_non_empty_string(item["project_id"], f"{field}.project_id")
    require_absolute_path(item["path"], f"{field}.path")
    require_enum(item["environment"], {"local", "worktree"}, f"{field}.environment")


def validate_workspace(value: Any, field: str) -> None:
    item = require_exact_keys(
        value,
        {"mode", "path", "branch", "base_revision", "clean_start_required"},
        field,
    )
    require_enum(
        item["mode"],
        {"desktop-local-checkout", "desktop-managed-worktree", "existing-permanent-worktree", "read-only"},
        f"{field}.mode",
    )
    require_absolute_path(item["path"], f"{field}.path")
    require_nullable_string(item["branch"], f"{field}.branch")
    require_git_hash(item["base_revision"], f"{field}.base_revision")
    require_bool(item["clean_start_required"], f"{field}.clean_start_required")


def validate_ownership(value: Any, field: str) -> None:
    item = require_exact_keys(value, {"write_paths", "forbidden_paths"}, field)
    write_paths = require_string_list(item["write_paths"], f"{field}.write_paths")
    forbidden_paths = require_string_list(item["forbidden_paths"], f"{field}.forbidden_paths")
    normalized_write = [normalized_repo_path(path, f"{field}.write_paths") for path in write_paths]
    normalized_forbidden = [normalized_repo_path(path, f"{field}.forbidden_paths") for path in forbidden_paths]
    unique(normalized_write, f"{field}.write_paths")
    unique(normalized_forbidden, f"{field}.forbidden_paths")


def validate_gate(value: Any, field: str) -> None:
    item = require_exact_keys(value, {"gate_id", "owner", "command", "evidence_required"}, field)
    require_non_empty_string(item["gate_id"], f"{field}.gate_id")
    require_enum(item["owner"], {"worker", "integrator", "reviewer", "orchestrator", "ci"}, f"{field}.owner")
    require_nullable_string(item["command"], f"{field}.command")
    require_string_list(item["evidence_required"], f"{field}.evidence_required")


def validate_lane(value: Any, field: str) -> None:
    item = require_exact_keys(
        value,
        {
            "lane_id",
            "role",
            "task_mode",
            "depends_on",
            "workspace",
            "ownership",
            "inputs",
            "gates",
            "stop_conditions",
        },
        field,
    )
    require_non_empty_string(item["lane_id"], f"{field}.lane_id")
    require_enum(item["role"], {"implementer", "integrator", "reviewer"}, f"{field}.role")
    require_enum(item["task_mode"], {"fresh-desktop-task", "continued-desktop-task"}, f"{field}.task_mode")
    require_string_list(item["depends_on"], f"{field}.depends_on")
    validate_workspace(item["workspace"], f"{field}.workspace")
    validate_ownership(item["ownership"], f"{field}.ownership")
    require(isinstance(item["inputs"], list), f"{field}.inputs must be an array")
    for index, artifact in enumerate(item["inputs"]):
        validate_artifact_ref(artifact, f"{field}.inputs[{index}]")
    require(isinstance(item["gates"], list), f"{field}.gates must be an array")
    for index, gate in enumerate(item["gates"]):
        validate_gate(gate, f"{field}.gates[{index}]")
    require_string_list(item["stop_conditions"], f"{field}.stop_conditions", allow_empty=False)


def validate_session_plan(document: dict[str, Any]) -> None:
    fields = {
        "profile",
        "schema_version",
        "kind",
        "artifact_id",
        "context_id",
        "created_at",
        "status",
        "objective",
        "client_surface",
        "base",
        "task_project",
        "lanes",
        "integration_order",
        "budgets",
        "global_stop_conditions",
    }
    require_exact_keys(document, fields, "session-plan")
    validate_header(document, "session-plan")
    require_enum(document["status"], {"draft", "frozen", "running", "completed", "blocked", "canceled"}, "status")
    require_non_empty_string(document["objective"], "objective")
    require(document["client_surface"] == "codex_desktop", "client_surface must be codex_desktop")
    base = require_exact_keys(document["base"], {"repository", "commit", "tree"}, "base")
    require_non_empty_string(base["repository"], "base.repository")
    require_git_hash(base["commit"], "base.commit")
    require_git_hash(base["tree"], "base.tree")
    validate_task_project(document["task_project"], "task_project")

    lanes = document["lanes"]
    require(isinstance(lanes, list) and lanes, "lanes must be a non-empty array")
    for index, lane in enumerate(lanes):
        validate_lane(lane, f"lanes[{index}]")
    lane_ids = unique((lane["lane_id"] for lane in lanes), "lanes.lane_id")
    for lane in lanes:
        dependencies = require_string_list(lane["depends_on"], f"lane {lane['lane_id']} depends_on")
        require(lane["lane_id"] not in dependencies, f"lane {lane['lane_id']} cannot depend on itself")
        missing = sorted(set(dependencies) - lane_ids)
        require(not missing, f"lane {lane['lane_id']} has unknown dependencies: {', '.join(missing)}")

    order = require_string_list(document["integration_order"], "integration_order", allow_empty=False)
    unique(order, "integration_order")
    missing_order = sorted(set(order) - lane_ids)
    require(not missing_order, f"integration_order has unknown lanes: {', '.join(missing_order)}")

    budgets = require_exact_keys(document["budgets"], {"desktop_tasks", "max_followups_per_task"}, "budgets")
    desktop_tasks = require_int(budgets["desktop_tasks"], "budgets.desktop_tasks", minimum=1)
    require(desktop_tasks == len(lanes), "budgets.desktop_tasks must equal the number of planned lanes")
    require_int(budgets["max_followups_per_task"], "budgets.max_followups_per_task", minimum=0)
    require_string_list(document["global_stop_conditions"], "global_stop_conditions", allow_empty=False)


def validate_roster(document: dict[str, Any]) -> None:
    fields = {"profile", "schema_version", "kind", "artifact_id", "context_id", "created_at", "plan_ref", "revision", "members"}
    require_exact_keys(document, fields, "roster")
    validate_header(document, "roster")
    require_non_empty_string(document["plan_ref"], "plan_ref")
    require_int(document["revision"], "revision", minimum=1)
    members = document["members"]
    require(isinstance(members, list) and members, "members must be a non-empty array")
    lane_ids: list[str] = []
    for index, member in enumerate(members):
        field = f"members[{index}]"
        item = require_exact_keys(
            member,
            {"lane_id", "thread_id", "status", "task_project_id", "workspace_path", "branch", "head", "last_update", "report_ref"},
            field,
        )
        lane_ids.append(require_non_empty_string(item["lane_id"], f"{field}.lane_id"))
        status = require_enum(
            item["status"],
            {"planned", "preflight", "working", "input-required", "handoff-ready", "accepted", "blocked", "failed", "canceled", "archived"},
            f"{field}.status",
        )
        thread_id = require_nullable_string(item["thread_id"], f"{field}.thread_id")
        if status != "planned":
            require(thread_id is not None, f"{field}.thread_id is required after planned state")
        require_non_empty_string(item["task_project_id"], f"{field}.task_project_id")
        require_absolute_path(item["workspace_path"], f"{field}.workspace_path")
        require_nullable_string(item["branch"], f"{field}.branch")
        require_git_hash(item["head"], f"{field}.head", nullable=True)
        require_timestamp(item["last_update"], f"{field}.last_update")
        require_nullable_string(item["report_ref"], f"{field}.report_ref")
    unique(lane_ids, "members.lane_id")


def validate_task_brief(document: dict[str, Any]) -> None:
    fields = {
        "profile",
        "schema_version",
        "kind",
        "artifact_id",
        "context_id",
        "created_at",
        "plan_ref",
        "lane_id",
        "objective",
        "scope_in",
        "scope_out",
        "task_project",
        "workspace",
        "ownership",
        "inputs",
        "contract",
        "required_outputs",
        "gates",
        "stop_conditions",
        "handoff_to",
    }
    require_exact_keys(document, fields, "task-brief")
    validate_header(document, "task-brief")
    require_non_empty_string(document["plan_ref"], "plan_ref")
    require_non_empty_string(document["lane_id"], "lane_id")
    require_non_empty_string(document["objective"], "objective")
    require_string_list(document["scope_in"], "scope_in", allow_empty=False)
    require_string_list(document["scope_out"], "scope_out")
    validate_task_project(document["task_project"], "task_project")
    validate_workspace(document["workspace"], "workspace")
    validate_ownership(document["ownership"], "ownership")
    require(isinstance(document["inputs"], list), "inputs must be an array")
    for index, artifact in enumerate(document["inputs"]):
        validate_artifact_ref(artifact, f"inputs[{index}]")
    contract = require_exact_keys(document["contract"], {"version", "sha256", "invariants", "forbidden_changes"}, "contract")
    require_non_empty_string(contract["version"], "contract.version")
    require_sha256(contract["sha256"], "contract.sha256")
    require_string_list(contract["invariants"], "contract.invariants", allow_empty=False)
    require_string_list(contract["forbidden_changes"], "contract.forbidden_changes", allow_empty=False)
    require_string_list(document["required_outputs"], "required_outputs", allow_empty=False)
    require(isinstance(document["gates"], list), "gates must be an array")
    for index, gate in enumerate(document["gates"]):
        validate_gate(gate, f"gates[{index}]")
    require_string_list(document["stop_conditions"], "stop_conditions", allow_empty=False)
    require_non_empty_string(document["handoff_to"], "handoff_to")


def validate_test_result(value: Any, field: str) -> None:
    item = require_exact_keys(value, {"command", "exit_code", "outcome", "duration_seconds", "evidence_path"}, field)
    require_non_empty_string(item["command"], f"{field}.command")
    exit_code = require_int(item["exit_code"], f"{field}.exit_code")
    outcome = require_enum(item["outcome"], {"passed", "failed", "blocked", "not-run"}, f"{field}.outcome")
    if item["duration_seconds"] is not None:
        require_number(item["duration_seconds"], f"{field}.duration_seconds", minimum=0)
    require_nullable_string(item["evidence_path"], f"{field}.evidence_path")
    if outcome == "passed":
        require(exit_code == 0, f"{field} passed but exit_code is not 0")
    if outcome == "failed":
        require(exit_code != 0, f"{field} failed but exit_code is 0")


def validate_worker_report(document: dict[str, Any]) -> None:
    fields = {
        "profile",
        "schema_version",
        "kind",
        "artifact_id",
        "context_id",
        "created_at",
        "plan_ref",
        "brief_ref",
        "lane_id",
        "status",
        "summary",
        "task",
        "workspace_state",
        "changed_files",
        "commits",
        "tests",
        "artifacts",
        "risks",
        "not_verified",
        "requested_action",
    }
    require_exact_keys(document, fields, "worker-report")
    validate_header(document, "worker-report")
    require_non_empty_string(document["plan_ref"], "plan_ref")
    require_non_empty_string(document["brief_ref"], "brief_ref")
    require_non_empty_string(document["lane_id"], "lane_id")
    status = require_enum(document["status"], {"completed", "partial", "blocked"}, "status")
    require_non_empty_string(document["summary"], "summary")
    task = require_exact_keys(document["task"], {"thread_id", "project_id"}, "task")
    require_non_empty_string(task["thread_id"], "task.thread_id")
    require_non_empty_string(task["project_id"], "task.project_id")
    state = require_exact_keys(
        document["workspace_state"],
        {"path", "branch", "base_revision", "head_revision", "tree", "clean"},
        "workspace_state",
    )
    require_absolute_path(state["path"], "workspace_state.path")
    require_non_empty_string(state["branch"], "workspace_state.branch")
    require_git_hash(state["base_revision"], "workspace_state.base_revision")
    head = require_git_hash(state["head_revision"], "workspace_state.head_revision", nullable=True)
    tree = require_git_hash(state["tree"], "workspace_state.tree", nullable=True)
    clean = require_bool(state["clean"], "workspace_state.clean")

    changed = [normalized_repo_path(path, "changed_files") for path in require_string_list(document["changed_files"], "changed_files")]
    unique(changed, "changed_files")
    commits = document["commits"]
    require(isinstance(commits, list), "commits must be an array")
    for index, commit in enumerate(commits):
        require_git_hash(commit, f"commits[{index}]")
    unique(commits, "commits")
    tests = document["tests"]
    require(isinstance(tests, list), "tests must be an array")
    for index, test in enumerate(tests):
        validate_test_result(test, f"tests[{index}]")
    artifacts = document["artifacts"]
    require(isinstance(artifacts, list), "artifacts must be an array")
    for index, artifact in enumerate(artifacts):
        validate_artifact_ref(artifact, f"artifacts[{index}]")
    require_string_list(document["risks"], "risks")
    require_string_list(document["not_verified"], "not_verified")
    action = require_enum(document["requested_action"], {"validate-and-integrate", "request-input", "record-blocked"}, "requested_action")

    if status == "completed":
        require(head is not None and tree is not None, "completed report requires head_revision and tree")
        require(clean, "completed report requires a clean workspace")
        require(bool(commits), "completed report requires at least one commit")
        require(bool(tests), "completed report requires test evidence")
        require(all(test["outcome"] == "passed" for test in tests), "completed report cannot contain non-passing tests")
        require(action == "validate-and-integrate", "completed report must request validate-and-integrate")
    if status == "blocked":
        require(action == "record-blocked", "blocked report must request record-blocked")


def validate_queue_item(value: Any, field: str) -> None:
    item = require_exact_keys(value, {"lane_id", "report_ref", "commit", "tree", "order", "status", "validation", "decision_reason"}, field)
    require_non_empty_string(item["lane_id"], f"{field}.lane_id")
    require_non_empty_string(item["report_ref"], f"{field}.report_ref")
    require_git_hash(item["commit"], f"{field}.commit", nullable=True)
    require_git_hash(item["tree"], f"{field}.tree", nullable=True)
    require_int(item["order"], f"{field}.order", minimum=1)
    status = require_enum(item["status"], {"pending", "validated", "integrated", "rejected", "blocked"}, f"{field}.status")
    validation = require_exact_keys(item["validation"], {"schema", "identity", "ownership", "evidence"}, f"{field}.validation")
    checks = [require_bool(validation[name], f"{field}.validation.{name}") for name in ("schema", "identity", "ownership", "evidence")]
    reason = require_nullable_string(item["decision_reason"], f"{field}.decision_reason")
    if status in {"validated", "integrated"}:
        require(all(checks), f"{field} cannot be {status} until every validation check passes")
        require(item["commit"] is not None and item["tree"] is not None, f"{field} {status} requires commit and tree")
    if status in {"rejected", "blocked"}:
        require(reason is not None, f"{field} {status} requires decision_reason")


def validate_integration_queue(document: dict[str, Any]) -> None:
    fields = {
        "profile",
        "schema_version",
        "kind",
        "artifact_id",
        "context_id",
        "created_at",
        "plan_ref",
        "integration_lane_id",
        "base_revision",
        "current_head",
        "status",
        "items",
        "next_action",
    }
    require_exact_keys(document, fields, "integration-queue")
    validate_header(document, "integration-queue")
    require_non_empty_string(document["plan_ref"], "plan_ref")
    require_non_empty_string(document["integration_lane_id"], "integration_lane_id")
    require_git_hash(document["base_revision"], "base_revision")
    require_git_hash(document["current_head"], "current_head")
    require_enum(document["status"], {"planned", "receiving", "integrating", "review", "completed", "blocked"}, "status")
    items = document["items"]
    require(isinstance(items, list), "items must be an array")
    for index, item in enumerate(items):
        validate_queue_item(item, f"items[{index}]")
    unique((item["lane_id"] for item in items), "items.lane_id")
    unique((str(item["order"]) for item in items), "items.order")
    require_non_empty_string(document["next_action"], "next_action")


VALIDATORS = {
    "session-plan": validate_session_plan,
    "roster": validate_roster,
    "task-brief": validate_task_brief,
    "worker-report": validate_worker_report,
    "integration-queue": validate_integration_queue,
}


def load_document(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(document, dict), f"{path} root must be an object")
    kind = document.get("kind")
    require(kind in KINDS, f"{path} kind must be one of: {', '.join(sorted(KINDS))}")
    VALIDATORS[kind](document)
    return document


def lane_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {lane["lane_id"]: lane for lane in plan["lanes"]}


def path_owned(path: str, patterns: list[str]) -> bool:
    normalized = normalized_repo_path(path, "changed file")
    for pattern in patterns:
        normalized_pattern = normalized_repo_path(pattern, "ownership pattern")
        if fnmatch.fnmatchcase(normalized, normalized_pattern):
            return True
    return False


def cross_validate(documents: list[dict[str, Any]], plan: dict[str, Any] | None) -> None:
    artifact_ids = unique((document["artifact_id"] for document in documents), "artifact_id")
    del artifact_ids
    contexts = {document["context_id"] for document in documents}
    require(len(contexts) == 1, "all artifacts in one validation bundle must share context_id")

    embedded_plans = [document for document in documents if document["kind"] == "session-plan"]
    require(len(embedded_plans) <= 1, "bundle contains more than one session-plan")
    if plan is None and embedded_plans:
        plan = embedded_plans[0]
    if plan is None:
        return

    validate_session_plan(plan)
    lanes = lane_by_id(plan)
    plan_ref = plan["artifact_id"]
    for document in documents:
        if document["kind"] == "session-plan":
            continue
        require(document["context_id"] == plan["context_id"], f"{document['artifact_id']} context_id differs from plan")
        require(document["plan_ref"] == plan_ref, f"{document['artifact_id']} plan_ref differs from plan artifact_id")

        if document["kind"] == "roster":
            roster_lanes = {member["lane_id"] for member in document["members"]}
            require(roster_lanes == set(lanes), "roster members must exactly match planned lanes")
            for member in document["members"]:
                lane = lanes[member["lane_id"]]
                require(member["task_project_id"] == plan["task_project"]["project_id"], f"roster lane {member['lane_id']} project differs from plan")
                require(member["workspace_path"] == lane["workspace"]["path"], f"roster lane {member['lane_id']} workspace differs from plan")
                require(member["branch"] == lane["workspace"]["branch"], f"roster lane {member['lane_id']} branch differs from plan")

        if document["kind"] == "task-brief":
            lane_id = document["lane_id"]
            require(lane_id in lanes, f"task brief references unknown lane: {lane_id}")
            lane = lanes[lane_id]
            require(document["task_project"] == plan["task_project"], f"task brief {lane_id} task_project differs from plan")
            require(document["workspace"] == lane["workspace"], f"task brief {lane_id} workspace differs from plan")
            require(document["ownership"] == lane["ownership"], f"task brief {lane_id} ownership differs from plan")

        if document["kind"] == "worker-report":
            lane_id = document["lane_id"]
            require(lane_id in lanes, f"worker report references unknown lane: {lane_id}")
            lane = lanes[lane_id]
            state = document["workspace_state"]
            require(state["path"] == lane["workspace"]["path"], f"worker report {lane_id} workspace path differs from plan")
            require(state["branch"] == lane["workspace"]["branch"], f"worker report {lane_id} branch differs from plan")
            require(state["base_revision"] == lane["workspace"]["base_revision"], f"worker report {lane_id} base differs from plan")
            require(document["task"]["project_id"] == plan["task_project"]["project_id"], f"worker report {lane_id} project differs from plan")
            owned = lane["ownership"]["write_paths"]
            violations = [path for path in document["changed_files"] if not path_owned(path, owned)]
            require(not violations, f"worker report {lane_id} contains out-of-ownership changes: {', '.join(violations)}")

        if document["kind"] == "integration-queue":
            require(document["integration_lane_id"] in lanes, "integration queue references unknown integration lane")
            require(lanes[document["integration_lane_id"]]["role"] == "integrator", "integration_lane_id is not an integrator lane")
            require(document["base_revision"] == plan["base"]["commit"], "integration queue base differs from plan")
            for item in document["items"]:
                require(item["lane_id"] in lanes, f"integration queue references unknown lane: {item['lane_id']}")


def verify_artifact_files(documents: list[tuple[Path, dict[str, Any]]]) -> None:
    for document_path, document in documents:
        references: list[dict[str, Any]] = []
        if document["kind"] == "session-plan":
            for lane in document["lanes"]:
                references.extend(lane["inputs"])
        elif document["kind"] == "task-brief":
            references.extend(document["inputs"])
        elif document["kind"] == "worker-report":
            references.extend(document["artifacts"])
        for reference in references:
            referenced_path = Path(reference["path"])
            if not referenced_path.is_absolute() and not PureWindowsPath(str(referenced_path)).is_absolute():
                referenced_path = document_path.parent / referenced_path
            require(referenced_path.is_file(), f"artifact path does not exist: {referenced_path}")
            digest = hashlib.sha256(referenced_path.read_bytes()).hexdigest()
            require(f"sha256:{digest}" == reference["sha256"], f"artifact hash mismatch: {referenced_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="workflow artifact JSON files")
    parser.add_argument("--plan", type=Path, help="session-plan JSON used for cross-artifact validation")
    parser.add_argument("--verify-artifacts", action="store_true", help="verify referenced artifact files and SHA-256 digests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        loaded = [(path, load_document(path)) for path in args.files]
        plan = load_document(args.plan) if args.plan else None
        if plan is not None:
            require(plan["kind"] == "session-plan", "--plan must point to a session-plan")
        cross_validate([document for _, document in loaded], plan)
        if args.verify_artifacts:
            verify_artifact_files(loaded)
    except ValidationFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    kinds: dict[str, int] = {}
    for _, document in loaded:
        kinds[document["kind"]] = kinds.get(document["kind"], 0) + 1
    summary = ", ".join(f"{kind}={count}" for kind, count in sorted(kinds.items()))
    print(f"PASS: {len(loaded)} workflow artifact(s); {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
