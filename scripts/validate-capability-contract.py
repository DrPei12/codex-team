#!/usr/bin/env python3
"""Validate the capability-contract profile without third-party dependencies."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROFILE = "codex-multitask-capability-contract"
SCHEMA_VERSION = "0.1-draft"
VALID_STATES = {
    "declared_unverified",
    "observed",
    "contradicted",
    "unsupported",
    "unknown",
}
VALID_EVIDENCE_KINDS = {
    "local_command",
    "tool_schema",
    "official_document",
    "behavior_run",
    "historical_experiment",
}
VALID_RELATIONS = {"supports", "contradicts", "qualifies", "mentions", "no_evidence"}


class ValidationFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def require_non_empty_string(value: Any, field: str) -> None:
    require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")


def require_string_list(value: Any, field: str) -> None:
    require(isinstance(value, list), f"{field} must be an array")
    for index, item in enumerate(value):
        require_non_empty_string(item, f"{field}[{index}]")


def require_keys(value: Any, keys: set[str], field: str) -> None:
    require(isinstance(value, dict), f"{field} must be an object")
    missing = sorted(keys - value.keys())
    require(not missing, f"{field} missing required keys: {', '.join(missing)}")


def unique_ids(items: list[dict[str, Any]], key: str, field: str) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        require_non_empty_string(item.get(key), f"{field}[{index}].{key}")
        identifier = item[key]
        require(identifier not in seen, f"duplicate {key}: {identifier}")
        seen.add(identifier)
    return seen


def validate(document: dict[str, Any]) -> None:
    top_level = {
        "profile",
        "schema_version",
        "snapshot_id",
        "captured_at",
        "scope",
        "environment",
        "evidence",
        "capabilities",
        "unknowns",
        "behavior_test_authorization",
    }
    require_keys(document, top_level, "document")
    require(document["profile"] == PROFILE, f"profile must be {PROFILE}")
    require(document["schema_version"] == SCHEMA_VERSION, f"schema_version must be {SCHEMA_VERSION}")
    require_non_empty_string(document["snapshot_id"], "snapshot_id")
    require_non_empty_string(document["captured_at"], "captured_at")

    scope = document["scope"]
    require_keys(scope, {"project", "platform", "claim_boundary"}, "scope")
    require(scope["platform"] == "Codex", "scope.platform must be Codex")
    require_non_empty_string(scope["claim_boundary"], "scope.claim_boundary")

    environment = document["environment"]
    require_keys(environment, {"os", "shell", "codex", "git", "repository"}, "environment")
    repository = environment["repository"]
    require_keys(
        repository,
        {"path", "branch", "head", "status", "dirty_paths", "preexisting_changes_preserved"},
        "environment.repository",
    )
    require(repository["status"] in {"clean", "dirty"}, "repository.status must be clean or dirty")
    require_string_list(repository["dirty_paths"], "environment.repository.dirty_paths")
    if repository["status"] == "clean":
        require(not repository["dirty_paths"], "clean repository must have no dirty_paths")
    else:
        require(bool(repository["dirty_paths"]), "dirty repository must list dirty_paths")

    evidence = document["evidence"]
    capabilities = document["capabilities"]
    unknowns = document["unknowns"]
    require(isinstance(evidence, list) and evidence, "evidence must be a non-empty array")
    require(isinstance(capabilities, list) and capabilities, "capabilities must be a non-empty array")
    require(isinstance(unknowns, list), "unknowns must be an array")

    evidence_ids = unique_ids(evidence, "evidence_id", "evidence")
    unique_ids(capabilities, "capability_id", "capabilities")
    unique_ids(unknowns, "unknown_id", "unknowns")

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(evidence):
        field = f"evidence[{index}]"
        require_keys(
            item,
            {"evidence_id", "kind", "relation", "captured_at", "locator", "result", "conditions", "limitations", "confidence"},
            field,
        )
        require(item["kind"] in VALID_EVIDENCE_KINDS, f"{field}.kind is invalid")
        require(item["relation"] in VALID_RELATIONS, f"{field}.relation is invalid")
        require(isinstance(item["result"], dict), f"{field}.result must be an object")
        require_string_list(item["conditions"], f"{field}.conditions")
        require_string_list(item["limitations"], f"{field}.limitations")
        evidence_by_id[item["evidence_id"]] = item

    for index, item in enumerate(capabilities):
        field = f"capabilities[{index}]"
        require_keys(
            item,
            {"capability_id", "surface", "claim", "state", "conditions", "evidence_refs", "required_tests", "limitations", "failure_policy"},
            field,
        )
        require(item["state"] in VALID_STATES, f"{field}.state is invalid")
        require_non_empty_string(item["claim"], f"{field}.claim")
        require_string_list(item["conditions"], f"{field}.conditions")
        require_string_list(item["evidence_refs"], f"{field}.evidence_refs")
        require_string_list(item["required_tests"], f"{field}.required_tests")
        require_string_list(item["limitations"], f"{field}.limitations")
        require_non_empty_string(item["failure_policy"], f"{field}.failure_policy")

        missing_refs = sorted(set(item["evidence_refs"]) - evidence_ids)
        require(not missing_refs, f"{field} has unresolved evidence refs: {', '.join(missing_refs)}")
        supporting = [
            evidence_by_id[ref]
            for ref in item["evidence_refs"]
            if evidence_by_id[ref]["relation"] == "supports"
        ]
        if item["state"] == "observed":
            require(
                any(entry["kind"] == "behavior_run" for entry in supporting),
                f"{field} is observed but lacks supporting behavior_run evidence",
            )
        if item["state"] in {"contradicted", "unsupported"}:
            require(bool(item["evidence_refs"]), f"{field} requires direct evidence")
        if item["state"] == "declared_unverified":
            require(
                any(entry["kind"] in {"tool_schema", "official_document", "local_command"} for entry in supporting),
                f"{field} is declared_unverified but lacks a current declaration",
            )

    authorization = document["behavior_test_authorization"]
    require_keys(authorization, {"required", "granted", "reason"}, "behavior_test_authorization")
    require(isinstance(authorization["required"], bool), "authorization.required must be boolean")
    require(isinstance(authorization["granted"], bool), "authorization.granted must be boolean")
    require_non_empty_string(authorization["reason"], "behavior_test_authorization.reason")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate-capability-contract.py <contract.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        require(isinstance(document, dict), "document root must be an object")
        validate(document)
    except (OSError, json.JSONDecodeError, ValidationFailure) as exc:
        print(f"FAIL {path}: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS {path}: {len(document['capabilities'])} capabilities, "
        f"{len(document['evidence'])} evidence records, {len(document['unknowns'])} unknowns"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
