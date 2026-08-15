#!/usr/bin/env python3
"""Validate a team-plan run manifest and project canonical lane briefs."""

from __future__ import annotations

import argparse
import copy
import datetime as _datetime
import fnmatch
import hashlib
import json
import ntpath
import os
import re
import sys
from pathlib import Path
from typing import Any


PROFILE = "codex-multitask-team-plan"
SCHEMA_VERSION = "0.1"
KIND = "run-manifest"
STATUSES = {"planned", "active", "completed", "blocked", "cancelled"}
ROLES = {"implementer", "integrator", "reviewer"}
WORKSPACE_MODES = {"read-only", "permanent-worktree"}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
GENERIC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


class ManifestError(ValueError):
    """An actionable manifest or projection error."""


def _fail(path: str, message: str) -> None:
    raise ManifestError(f"{path}: {message}")


def _object(value: Any, path: str, required: set[str], allowed: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "expected an object")
    missing = sorted(required.difference(value))
    if missing:
        _fail(path, f"missing required field(s): {', '.join(missing)}")
    if allowed is not None:
        unknown = sorted(set(value).difference(allowed))
        if unknown:
            _fail(path, f"unknown field(s): {', '.join(unknown)}")
    return value


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        _fail(path, "expected a string")
    if nonempty and not value.strip():
        _fail(path, "must not be empty")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "expected a boolean")
    return value


def _list(value: Any, path: str, *, min_items: int = 0) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "expected an array")
    if len(value) < min_items:
        _fail(path, f"must contain at least {min_items} item(s)")
    return value


def _string_list(value: Any, path: str, *, min_items: int = 0, unique: bool = True) -> list[str]:
    values = _list(value, path, min_items=min_items)
    result: list[str] = []
    for index, item in enumerate(values):
        result.append(_string(item, f"{path}[{index}]"))
    if unique and len(set(result)) != len(result):
        _fail(path, "items must be unique")
    return result


def _exact(value: Any, expected: str, path: str) -> None:
    if value != expected:
        _fail(path, f"must be {expected!r}")


def _identity(value: Any, path: str, pattern: re.Pattern[str]) -> str:
    text = _string(value, path)
    if not pattern.fullmatch(text):
        _fail(path, "has an invalid identity")
    return text


def _timestamp(value: Any, path: str) -> str:
    text = _string(value, path)
    if not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T", text):
        _fail(path, "timestamp must use 'T' between date and time")
    if not re.search(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$", text):
        _fail(path, "must include a timezone offset")
    try:
        iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = _datetime.datetime.fromisoformat(iso_text)
    except ValueError:
        _fail(path, "must be an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(path, "must include a timezone offset")
    return text


def _commit(value: Any, path: str) -> str:
    text = _string(value, path)
    if not HEX40_RE.fullmatch(text):
        _fail(path, "must be a 40-character hexadecimal revision")
    return text


def _branch(value: Any, path: str) -> str:
    text = _string(value, path)
    invalid = {" ", "~", "^", ":", "?", "*", "[", "]", "\\"}
    components = text.split("/")
    if (
        text.startswith("/")
        or text.endswith(("/", "."))
        or ".." in text
        or text.endswith(".lock")
        or text == "@"
        or "@{" in text
        or "//" in text
        or any(component.startswith(".") or component.endswith(".lock") for component in components)
        or any(ord(char) < 32 or ord(char) == 127 for char in text)
        or any(char.isspace() or char in invalid for char in text)
    ):
        _fail(path, "has an invalid branch identity")
    return text


def _uuid(value: Any, path: str) -> str:
    text = _string(value, path)
    if not UUID_RE.fullmatch(text):
        _fail(path, "must be a canonical UUID identity")
    return text


def _path_is_absolute(value: str) -> bool:
    return ntpath.isabs(value) or os.path.isabs(value)


def _normal_path(value: str) -> str:
    if ntpath.isabs(value):
        return ntpath.normcase(ntpath.normpath(value))
    return os.path.normcase(os.path.abspath(value))


def _path_is_within(child: str, root: str) -> bool:
    child_normal = _normal_path(child)
    root_normal = _normal_path(root).rstrip("\\/")
    return child_normal == root_normal or child_normal.startswith(root_normal + "\\") or child_normal.startswith(root_normal + "/")


def _absolute_path(value: Any, path: str, *, root: str | None = None, label: str = "path") -> str:
    text = _string(value, path)
    if not _path_is_absolute(text):
        _fail(path, f"{label} must be absolute")
    if root is not None and not _path_is_within(text, root):
        _fail(path, f"{label} is outside experiment_root")
    return text


def _owned_path(value: Any, path: str) -> str:
    text = _string(value, path)
    normalized = text.replace("\\", "/")
    if ntpath.isabs(text) or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        _fail(path, "write paths must be relative")
    if any(part == ".." for part in normalized.split("/")):
        _fail(path, "write paths must not escape the repository")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts:
        _fail(path, "write path must not be empty")
    return ntpath.normcase("/".join(parts)).replace("\\", "/")


def _path_patterns_overlap(left: str, right: str) -> bool:
    """Conservatively detect overlap for exact paths and common glob paths."""

    left = left.replace("\\", "/").casefold()
    right = right.replace("\\", "/").casefold()
    if left == right:
        return True
    if left.startswith(right + "/") or right.startswith(left + "/"):
        return True
    if fnmatch.fnmatchcase(left, right) or fnmatch.fnmatchcase(right, left):
        return True
    for pattern, candidate in ((left, right), (right, left)):
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if candidate == prefix or candidate.startswith(prefix + "/"):
                return True
    return False


def _nearest_existing_path(value: str) -> str:
    candidate = value
    while not os.path.lexists(candidate):
        parent = os.path.dirname(candidate)
        if not parent or parent == candidate:
            return candidate
        candidate = parent
    return candidate


def _real_path(value: str) -> str:
    return _normal_path(os.path.realpath(value))


def _path_is_ancestor_or_descendant(left: str, right: str) -> bool:
    return _path_is_within(left, right) or _path_is_within(right, left)


def _paths_overlap(left: str, right: str) -> bool:
    """Detect lexical and resolved-parent ancestor/descendant overlap."""

    if _path_is_ancestor_or_descendant(left, right):
        return True
    left_real = _real_path(left)
    right_real = _real_path(right)
    if _path_is_ancestor_or_descendant(left_real, right_real):
        return True
    left_parent_real = _real_path(_nearest_existing_path(left))
    right_parent_real = _real_path(_nearest_existing_path(right))
    return _path_is_within(left_parent_real, right_real) or _path_is_within(right_parent_real, left_real)


def _real_path_is_within(child: str, root: str) -> bool:
    """Resolve existing path components without requiring a future leaf."""

    return _path_is_within(_real_path(child), _real_path(root))


def _check_output_parent_real_path(output: str, artifact_root: str, experiment_root: str) -> None:
    """Reject symlink/junction escapes before creating any output directory."""

    experiment_real = _real_path(experiment_root)
    artifact_anchor = _nearest_existing_path(artifact_root)
    artifact_anchor_real = _real_path(artifact_anchor)
    if not _path_is_within(artifact_anchor_real, experiment_real):
        _fail("output", "artifact_root real path escapes experiment_root")

    output_parent = _nearest_existing_path(output)
    output_parent_real = _real_path(output_parent)
    if not _path_is_within(output_parent_real, artifact_anchor_real):
        _fail("output", "existing parent real path escapes artifact_root")


def _check_reviewer_workspaces(
    lane_by_id: dict[str, dict[str, Any]],
    lane_roles: dict[str, str],
    graph: dict[str, list[str]],
) -> None:
    for lane_id, role in lane_roles.items():
        if role != "reviewer":
            continue
        integrator_dependencies = [
            dependency for dependency in graph[lane_id] if lane_roles[dependency] == "integrator"
        ]
        if not integrator_dependencies:
            _fail(
                f"lanes[{lane_id}].depends_on",
                "reviewer must directly depend on at least one integrator",
            )
        reviewer = lane_by_id[lane_id]
        reviewer_workspace = reviewer["workspace"]
        reviewer_path = _real_path(reviewer_workspace["path"])
        matching_integrators = [
            dependency
            for dependency in integrator_dependencies
            if _real_path(lane_by_id[dependency]["workspace"]["path"]) == reviewer_path
        ]
        if not matching_integrators:
            _fail(
                f"lanes[{lane_id}].workspace.path",
                "reviewer workspace must match a directly depended-on integrator",
            )
        if not any(
            reviewer_workspace["base_revision"] == lane_by_id[dependency]["workspace"]["base_revision"]
            for dependency in matching_integrators
        ):
            _fail(
                f"lanes[{lane_id}].workspace.base_revision",
                "reviewer workspace base_revision must match the shared integrator",
            )


def _check_workspace_conflicts(
    workspace_keys: dict[str, list[str]],
    lane_by_id: dict[str, dict[str, Any]],
    lane_roles: dict[str, str],
    graph: dict[str, list[str]],
) -> None:
    for workspace_key, lane_ids in workspace_keys.items():
        if len(lane_ids) == 1:
            continue
        if len(lane_ids) == 2:
            reviewer = next((lane_id for lane_id in lane_ids if lane_roles[lane_id] == "reviewer"), None)
            integrator = next((lane_id for lane_id in lane_ids if lane_roles[lane_id] == "integrator"), None)
            if reviewer and integrator and integrator in graph[reviewer]:
                reviewer_base = lane_by_id[reviewer]["workspace"]["base_revision"]
                integrator_base = lane_by_id[integrator]["workspace"]["base_revision"]
                if reviewer_base == integrator_base:
                    continue
        _fail(
            "lanes.workspace.path",
            f"workspace conflicts between lanes: {', '.join(lane_ids)}",
        )


def _gate(value: Any, path: str, *, command_required: bool) -> dict[str, Any]:
    allowed = {"gate_id", "owner", "command", "evidence_required"}
    gate = _object(value, path, allowed, allowed)
    _identity(gate["gate_id"], f"{path}.gate_id", GENERIC_ID_RE)
    _string(gate["owner"], f"{path}.owner")
    command = gate["command"]
    if command is not None and not isinstance(command, str):
        _fail(f"{path}.command", "expected a string or null")
    if isinstance(command, str) and not command.strip():
        _fail(f"{path}.command", "must be a non-empty string when present")
    if command_required and command is None:
        _fail(f"{path}.command", "must be a non-empty string for a mutable gate")
    _string_list(gate["evidence_required"], f"{path}.evidence_required", min_items=1)
    return gate


def _dependency_reachable(graph: dict[str, list[str]], start: str, target: str) -> bool:
    pending = list(graph[start])
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph[current])
    return False


def _check_cycles(graph: dict[str, list[str]]) -> None:
    state: dict[str, int] = {node: 0 for node in graph}
    stack: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for dependency in graph[node]:
            if state[dependency] == 1:
                start = stack.index(dependency)
                cycle = stack[start:] + [dependency]
                _fail("lanes.depends_on", f"dependency cycle: {' -> '.join(cycle)}")
            if state[dependency] == 0:
                visit(dependency)
        stack.pop()
        state[node] = 2

    for node in graph:
        if state[node] == 0:
            visit(node)


def _check_parallel_groups(
    groups: list[Any],
    lane_ids: set[str],
    graph: dict[str, list[str]],
    write_paths: dict[str, list[str]],
) -> None:
    seen: set[str] = set()
    for group_index, raw_group in enumerate(groups):
        group = _string_list(raw_group, f"decision.parallel_groups[{group_index}]", min_items=1)
        for lane_id in group:
            if lane_id not in lane_ids:
                _fail(
                    f"decision.parallel_groups[{group_index}]",
                    f"unknown lane {lane_id!r}",
                )
            if lane_id in seen:
                _fail("decision.parallel_groups", f"lane {lane_id!r} appears more than once")
            seen.add(lane_id)

        for left_index, left in enumerate(group):
            for right in group[left_index + 1 :]:
                if _dependency_reachable(graph, left, right) or _dependency_reachable(graph, right, left):
                    _fail(
                        "decision.parallel_groups",
                        f"parallel dependency conflict between {left!r} and {right!r}",
                    )
                for left_path in write_paths[left]:
                    for right_path in write_paths[right]:
                        if _path_patterns_overlap(left_path, right_path):
                            _fail(
                                "decision.parallel_groups",
                                "parallel ownership overlap: "
                                f"{left!r} claims {left_path!r} and {right!r} claims {right_path!r}",
                            )

    missing = sorted(lane_ids.difference(seen))
    if missing:
        _fail(
            "decision.parallel_groups",
            f"incomplete parallel_groups; missing lane(s): {', '.join(missing)}",
        )


def validate_manifest(manifest: Any) -> None:
    top_allowed = {
        "profile",
        "schema_version",
        "kind",
        "run_id",
        "created_at",
        "status",
        "objective",
        "decision",
        "client_surface",
        "base",
        "task_project",
        "runtime",
        "workspace_policy",
        "contract",
        "lanes",
        "integration_order",
        "global_gates",
        "global_stop_conditions",
    }
    manifest_object = _object(manifest, "manifest", top_allowed, top_allowed)
    _exact(manifest_object["profile"], PROFILE, "profile")
    _exact(manifest_object["schema_version"], SCHEMA_VERSION, "schema_version")
    _exact(manifest_object["kind"], KIND, "kind")
    _identity(manifest_object["run_id"], "run_id", GENERIC_ID_RE)
    _timestamp(manifest_object["created_at"], "created_at")
    status = _string(manifest_object["status"], "status")
    if status not in STATUSES:
        _fail("status", f"must be one of: {', '.join(sorted(STATUSES))}")
    _string(manifest_object["objective"], "objective")
    _exact(manifest_object["client_surface"], "codex_desktop", "client_surface")

    decision_allowed = {"mode", "reason", "parallel_groups"}
    decision = _object(manifest_object["decision"], "decision", decision_allowed, decision_allowed)
    _exact(decision["mode"], "multi-task", "decision.mode")
    _string(decision["reason"], "decision.reason")
    parallel_groups = _list(decision["parallel_groups"], "decision.parallel_groups", min_items=1)

    base_allowed = {"repository", "branch", "commit", "tree", "clean"}
    base = _object(manifest_object["base"], "base", base_allowed, base_allowed)
    _string(base["repository"], "base.repository")
    base_branch = _branch(base["branch"], "base.branch")
    _commit(base["commit"], "base.commit")
    _commit(base["tree"], "base.tree")
    _boolean(base["clean"], "base.clean")

    project_allowed = {"project_id", "path", "environment"}
    task_project = _object(manifest_object["task_project"], "task_project", project_allowed, project_allowed)
    _uuid(task_project["project_id"], "task_project.project_id")
    _string(task_project["path"], "task_project.path")
    _exact(task_project["environment"], "local", "task_project.environment")

    runtime_allowed = {"requested_model", "requested_thinking", "effective_model", "effective_thinking"}
    runtime = _object(manifest_object["runtime"], "runtime", runtime_allowed, runtime_allowed)
    for field in sorted(runtime_allowed):
        _string(runtime[field], f"runtime.{field}")

    policy_allowed = {"experiment_root", "worktree_root", "artifact_root", "require_clean_start"}
    workspace_policy = _object(
        manifest_object["workspace_policy"],
        "workspace_policy",
        policy_allowed,
        policy_allowed,
    )
    experiment_root = _absolute_path(
        workspace_policy["experiment_root"],
        "workspace_policy.experiment_root",
        label="experiment_root",
    )
    worktree_root = _absolute_path(
        workspace_policy["worktree_root"],
        "workspace_policy.worktree_root",
        root=experiment_root,
        label="worktree_root",
    )
    artifact_root = _absolute_path(
        workspace_policy["artifact_root"],
        "workspace_policy.artifact_root",
        root=experiment_root,
        label="artifact_root",
    )
    _boolean(workspace_policy["require_clean_start"], "workspace_policy.require_clean_start")
    task_project_path = _absolute_path(
        task_project["path"],
        "task_project.path",
        root=experiment_root,
        label="task project path",
    )
    if not _path_is_within(worktree_root, experiment_root):
        _fail("workspace_policy.worktree_root", "worktree_root is outside experiment_root")
    if not _path_is_within(artifact_root, experiment_root):
        _fail("workspace_policy.artifact_root", "artifact_root is outside experiment_root")
    if not _real_path_is_within(worktree_root, experiment_root):
        _fail(
            "workspace_policy.worktree_root",
            "worktree_root real path is outside experiment_root",
        )
    if _paths_overlap(task_project_path, artifact_root):
        _fail(
            "workspace_policy.artifact_root",
            "artifact_root overlaps task_project.path",
        )

    contract_allowed = {"state", "source", "invariants", "forbidden_changes"}
    contract = _object(manifest_object["contract"], "contract", contract_allowed, contract_allowed)
    _exact(contract["state"], "frozen", "contract.state")
    _string(contract["source"], "contract.source")
    _string_list(contract["invariants"], "contract.invariants", min_items=1)
    _string_list(contract["forbidden_changes"], "contract.forbidden_changes", min_items=1)

    lane_allowed = {
        "lane_id",
        "role",
        "objective",
        "depends_on",
        "workspace",
        "ownership",
        "inputs",
        "outputs",
        "gates",
        "stop_conditions",
    }
    workspace_allowed = {"mode", "path", "branch", "base_revision", "clean_start_required"}
    ownership_allowed = {"write_paths", "forbidden_paths"}
    lanes = _list(manifest_object["lanes"], "lanes", min_items=1)
    lane_by_id: dict[str, dict[str, Any]] = {}
    lane_roles: dict[str, str] = {}
    graph: dict[str, list[str]] = {}
    write_paths: dict[str, list[str]] = {}
    workspace_keys: dict[str, list[str]] = {}
    branch_keys: dict[str, str] = {}
    gate_ids: set[str] = set()

    for index, raw_lane in enumerate(lanes):
        lane_path = f"lanes[{index}]"
        lane = _object(raw_lane, lane_path, lane_allowed, lane_allowed)
        lane_id = _identity(lane["lane_id"], f"{lane_path}.lane_id", ID_RE)
        if lane_id in lane_by_id:
            _fail(f"{lane_path}.lane_id", f"duplicate lane_id {lane_id!r}")
        role = _string(lane["role"], f"{lane_path}.role")
        if role not in ROLES:
            _fail(f"{lane_path}.role", f"must be one of: {', '.join(sorted(ROLES))}")
        _string(lane["objective"], f"{lane_path}.objective")
        dependencies = _string_list(lane["depends_on"], f"{lane_path}.depends_on")

        workspace = _object(
            lane["workspace"],
            f"{lane_path}.workspace",
            workspace_allowed,
            workspace_allowed,
        )
        mode = _string(workspace["mode"], f"{lane_path}.workspace.mode")
        if mode not in WORKSPACE_MODES:
            _fail(
                f"{lane_path}.workspace.mode",
                f"must be one of: {', '.join(sorted(WORKSPACE_MODES))}",
            )
        workspace_path = _absolute_path(
            workspace["path"],
            f"{lane_path}.workspace.path",
            root=experiment_root,
            label="workspace",
        )
        workspace_key = _real_path(workspace_path)
        workspace_keys.setdefault(workspace_key, []).append(lane_id)
        if role != "reviewer":
            if _paths_overlap(workspace_path, task_project_path):
                _fail(
                    f"{lane_path}.workspace.path",
                    "mutable workspace overlaps task_project.path",
                )
            if not _path_is_within(workspace_path, worktree_root):
                _fail(
                    f"{lane_path}.workspace.path",
                    "mutable workspace is outside worktree_root",
                )
            if not _real_path_is_within(workspace_path, worktree_root):
                _fail(
                    f"{lane_path}.workspace.path",
                    "mutable workspace real path is outside worktree_root",
                )
        if _paths_overlap(artifact_root, workspace_path):
            _fail(
                f"{lane_path}.workspace.path",
                "lane workspace overlaps artifact_root",
            )
        _commit(workspace["base_revision"], f"{lane_path}.workspace.base_revision")
        _boolean(workspace["clean_start_required"], f"{lane_path}.workspace.clean_start_required")

        ownership = _object(
            lane["ownership"],
            f"{lane_path}.ownership",
            ownership_allowed,
            ownership_allowed,
        )
        raw_write_paths = _string_list(
            ownership["write_paths"],
            f"{lane_path}.ownership.write_paths",
        )
        normalized_write_paths = [
            _owned_path(path, f"{lane_path}.ownership.write_paths[{path_index}]")
            for path_index, path in enumerate(raw_write_paths)
        ]
        if len(set(normalized_write_paths)) != len(normalized_write_paths):
            _fail(f"{lane_path}.ownership.write_paths", "normalized paths must be unique")
        _string_list(ownership["forbidden_paths"], f"{lane_path}.ownership.forbidden_paths")

        if role == "reviewer":
            if mode != "read-only":
                _fail(
                    lane_path,
                    "read-only reviewer must use workspace.mode 'read-only'",
                )
            if workspace["branch"] is not None:
                _fail(f"{lane_path}.workspace.branch", "read-only reviewer must not have a branch")
            if normalized_write_paths:
                _fail(
                    f"{lane_path}.ownership.write_paths",
                    "read-only reviewer must not have writable paths",
                )
        else:
            if mode == "read-only":
                _fail(lane_path, "only a reviewer may use a read-only workspace")
            branch = _branch(workspace["branch"], f"{lane_path}.workspace.branch")
            branch_key = branch.casefold()
            if branch_key in branch_keys:
                _fail(
                    f"{lane_path}.workspace.branch",
                    f"mutable branch conflicts with lane {branch_keys[branch_key]!r}",
                )
            if branch_key == base_branch.casefold():
                _fail(
                    f"{lane_path}.workspace.branch",
                    "mutable branch conflicts with base.branch",
                )
            branch_keys[branch_key] = lane_id

        _string_list(lane["inputs"], f"{lane_path}.inputs")
        _string_list(lane["outputs"], f"{lane_path}.outputs", min_items=1)
        _string_list(
            lane["stop_conditions"],
            f"{lane_path}.stop_conditions",
            min_items=1,
        )
        gates = _list(lane["gates"], f"{lane_path}.gates", min_items=1)
        lane_gate_ids: set[str] = set()
        for gate_index, raw_gate in enumerate(gates):
            gate_path = f"{lane_path}.gates[{gate_index}]"
            gate = _gate(raw_gate, gate_path, command_required=role != "reviewer")
            gate_id = gate["gate_id"]
            if gate_id in lane_gate_ids or gate_id in gate_ids:
                _fail(f"{gate_path}.gate_id", f"duplicate gate_id {gate_id!r}")
            lane_gate_ids.add(gate_id)
            gate_ids.add(gate_id)
            owner = gate["owner"]
            if owner != role and owner != lane_id:
                _fail(
                    f"{gate_path}.owner",
                    f"lane gate owner must be the lane role {role!r} or lane_id {lane_id!r}",
                )

        lane_by_id[lane_id] = lane
        lane_roles[lane_id] = role
        graph[lane_id] = dependencies
        write_paths[lane_id] = normalized_write_paths

    lane_ids = set(lane_by_id)
    for lane_id, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in lane_ids:
                _fail(
                    f"lanes[{lane_id}].depends_on",
                    f"unknown dependency {dependency!r}",
                )
    _check_cycles(graph)
    _check_reviewer_workspaces(lane_by_id, lane_roles, graph)
    _check_workspace_conflicts(workspace_keys, lane_by_id, lane_roles, graph)
    _check_parallel_groups(parallel_groups, lane_ids, graph, write_paths)

    order = _string_list(manifest_object["integration_order"], "integration_order", min_items=1)
    if set(order) != lane_ids or len(order) != len(lane_ids):
        _fail(
            "integration_order",
            "must contain each lane_id exactly once",
        )
    positions = {lane_id: index for index, lane_id in enumerate(order)}
    for lane_id, dependencies in graph.items():
        for dependency in dependencies:
            if positions[dependency] > positions[lane_id]:
                _fail(
                    "integration_order",
                    f"lane {lane_id!r} appears before dependency {dependency!r}",
                )

    global_gates = _list(manifest_object["global_gates"], "global_gates", min_items=1)
    valid_owners = lane_ids.union(lane_roles.values())
    for index, raw_gate in enumerate(global_gates):
        gate_path = f"global_gates[{index}]"
        gate = _gate(raw_gate, gate_path, command_required=True)
        gate_id = gate["gate_id"]
        if gate_id in gate_ids:
            _fail(f"{gate_path}.gate_id", f"duplicate gate_id {gate_id!r}")
        gate_ids.add(gate_id)
        if gate["owner"] not in valid_owners:
            _fail(f"{gate_path}.owner", f"unknown lane or role {gate['owner']!r}")
    _string_list(
        manifest_object["global_stop_conditions"],
        "global_stop_conditions",
        min_items=1,
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_manifest(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise ManifestError(f"manifest: file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ManifestError(f"manifest: invalid JSON in {path}: {exc}") from exc
    return manifest


def canonical_json_bytes(manifest: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"manifest: cannot canonicalize JSON: {exc}") from exc


def manifest_digest(manifest: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()}"


def _brief(manifest: dict[str, Any], lane: dict[str, Any], digest: str) -> dict[str, Any]:
    """Project only manifest-owned fields; do not add runtime-generated task data."""

    return {
        "manifest_ref": {"run_id": manifest["run_id"], "sha256": digest},
        "lane_id": lane["lane_id"],
        "role": lane["role"],
        "objective": lane["objective"],
        "depends_on": copy.deepcopy(lane["depends_on"]),
        "base": copy.deepcopy(manifest["base"]),
        "runtime": copy.deepcopy(manifest["runtime"]),
        "contract": copy.deepcopy(manifest["contract"]),
        "workspace": copy.deepcopy(lane["workspace"]),
        "ownership": copy.deepcopy(lane["ownership"]),
        "inputs": copy.deepcopy(lane["inputs"]),
        "outputs": copy.deepcopy(lane["outputs"]),
        "gates": copy.deepcopy(lane["gates"]),
        "stop_conditions": copy.deepcopy(lane["stop_conditions"]),
    }


def project_manifest(manifest: dict[str, Any], output_value: str) -> int:
    """Validate, then create lane briefs without overwriting any existing content."""

    validate_manifest(manifest)
    digest = manifest_digest(manifest)
    lanes = manifest["lanes"]
    artifact_root = manifest["workspace_policy"]["artifact_root"]
    output_text = _absolute_path(output_value, "output", label="output")
    if not _path_is_within(output_text, artifact_root):
        raise ManifestError(f"output: {output_text} is outside artifact_root")
    if _normal_path(output_text) == _normal_path(manifest["task_project"]["path"]):
        raise ManifestError("output: must not equal task_project.path")
    for lane in lanes:
        if _normal_path(output_text) == _normal_path(lane["workspace"]["path"]):
            raise ManifestError(f"output: must not equal lane workspace {lane['lane_id']!r}")
    _check_output_parent_real_path(output_text, artifact_root, manifest["workspace_policy"]["experiment_root"])

    output = Path(output_text)
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            raise ManifestError(f"output: {output} is not a directory")
        try:
            existing = next(output.iterdir())
        except StopIteration:
            existing = None
        if existing is not None:
            raise ManifestError(f"output: directory is not empty; refusing to overwrite: {output}")
    else:
        try:
            output.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise ManifestError(f"output: cannot create directory {output}: {exc}") from exc

    for lane in lanes:
        target = output / f"{lane['lane_id']}.task-brief.json"
        content = json.dumps(
            _brief(manifest, lane, digest),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.write("\n")
        except FileExistsError as exc:
            raise ManifestError(f"output: refusing to overwrite existing file {target}") from exc
        except OSError as exc:
            raise ManifestError(f"output: cannot write {target}: {exc}") from exc
    print(f"PASS: projected {len(lanes)} task briefs to {output}")
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ManifestError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        description="Validate a team-plan manifest or project canonical lane briefs."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate MANIFEST")
    validate.add_argument("manifest", metavar="MANIFEST")
    project = commands.add_parser("project", help="project MANIFEST into task briefs")
    project.add_argument("manifest", metavar="MANIFEST")
    project.add_argument("--out", required=True, metavar="DIR")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        manifest = load_manifest(args.manifest)
        if args.command == "validate":
            validate_manifest(manifest)
            print(f"PASS: {KIND} {manifest['run_id']}")
            return 0
        if args.command == "project":
            return project_manifest(manifest, args.out)
        raise ManifestError(f"unknown command {args.command!r}")
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
