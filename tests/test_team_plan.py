from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "team-plan.py"
SCHEMA = ROOT / "schemas" / "team-plan-manifest.schema.json"
EXPERIMENT_ROOT = Path(r"D:\Desktop\Codex多任务工程系统实验场")
BASE_COMMIT = "d235f59dcb7eb853043117402d3a1c8ef267b9af"
BASE_TREE = "063ebf5b6cb7dca61d9ceb08bbf7d9dff54061a7"


def lane(
    lane_id: str,
    role: str,
    depends_on: list[str],
    write_paths: list[str],
) -> dict:
    worktree = EXPERIMENT_ROOT / "worktrees" / f"demo-{lane_id}"
    return {
        "lane_id": lane_id,
        "role": role,
        "objective": f"Complete the {lane_id} responsibility.",
        "depends_on": depends_on,
        "workspace": {
            "mode": "read-only" if role == "reviewer" else "permanent-worktree",
            "path": str(worktree),
            "branch": None if role == "reviewer" else f"codex/demo-{lane_id}",
            "base_revision": BASE_COMMIT,
            "clean_start_required": True,
        },
        "ownership": {
            "write_paths": write_paths,
            "forbidden_paths": ["pyproject.toml", "uv.lock"],
        },
        "inputs": [],
        "outputs": [f"artifact:{lane_id}:result"],
        "gates": [
            {
                "gate_id": f"{lane_id}-gate",
                "owner": role,
                "command": None if role == "reviewer" else "python -m pytest -q",
                "evidence_required": ["exact command", "exit code", "head revision"],
            }
        ],
        "stop_conditions": ["workspace identity mismatch", "ownership crossing"],
    }


def valid_manifest() -> dict:
    project_path = EXPERIMENT_ROOT / "worktrees" / "outputguard-single"
    integrator = lane("integrator", "integrator", ["core", "cli"], ["outputguard/**", "tests/**"])
    reviewer = lane("reviewer", "reviewer", ["integrator"], [])
    reviewer["workspace"]["path"] = integrator["workspace"]["path"]
    reviewer["workspace"]["base_revision"] = integrator["workspace"]["base_revision"]
    return {
        "profile": "codex-multitask-team-plan",
        "schema_version": "0.1",
        "kind": "run-manifest",
        "run_id": "run:team-plan:demo-01",
        "created_at": "2026-08-15T12:00:00-04:00",
        "status": "planned",
        "objective": "Implement and verify streaming JSONL support.",
        "decision": {
            "mode": "multi-task",
            "reason": "The frozen contract separates Core and CLI ownership.",
            "parallel_groups": [["core", "cli"], ["integrator"], ["reviewer"]],
        },
        "client_surface": "codex_desktop",
        "base": {
            "repository": "ndcorder/outputguard",
            "branch": "codex/outputguard-single",
            "commit": BASE_COMMIT,
            "tree": BASE_TREE,
            "clean": True,
        },
        "task_project": {
            "project_id": "082eff70-1f80-4421-bb5b-d896d12961ff",
            "path": str(project_path),
            "environment": "local",
        },
        "runtime": {
            "requested_model": "gpt-5.6-luna",
            "requested_thinking": "max",
            "effective_model": "unknown",
            "effective_thinking": "unknown",
        },
        "workspace_policy": {
            "experiment_root": str(EXPERIMENT_ROOT),
            "worktree_root": str(EXPERIMENT_ROOT / "worktrees"),
            "artifact_root": str(EXPERIMENT_ROOT / "runs"),
            "require_clean_start": True,
        },
        "contract": {
            "state": "frozen",
            "source": "public/task-spec.md",
            "invariants": ["one physical line produces one result", "batch remains unchanged"],
            "forbidden_changes": ["sealed evaluator", "public contract"],
        },
        "lanes": [
            lane("core", "implementer", [], ["outputguard/jsonl.py", "tests/test_jsonl.py"]),
            lane("cli", "implementer", [], ["outputguard/cli.py", "tests/test_jsonl_cli.py"]),
            integrator,
            reviewer,
        ],
        "integration_order": ["core", "cli", "integrator", "reviewer"],
        "global_gates": [
            {
                "gate_id": "public-suite",
                "owner": "integrator",
                "command": "python -m pytest -q",
                "evidence_required": ["exact tree", "test summary"],
            }
        ],
        "global_stop_conditions": ["contract change", "solution reference leakage"],
    }


def run_cli(tmp_path: Path, manifest: dict, *args: str) -> subprocess.CompletedProcess[str]:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(CLI), *args, str(manifest_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_schema_and_skill_entrypoint_exist() -> None:
    assert SCHEMA.is_file()
    assert (ROOT / "skills" / "team-plan" / "SKILL.md").is_file()
    assert (ROOT / "skills" / "team-plan" / "agents" / "openai.yaml").is_file()


def test_valid_manifest_is_accepted(tmp_path: Path) -> None:
    result = run_cli(tmp_path, valid_manifest(), "validate")
    assert result.returncode == 0, result.stderr
    assert "PASS: run-manifest" in result.stdout


def test_unknown_dependency_is_rejected(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][2]["depends_on"].append("missing-lane")
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "unknown dependency" in result.stderr


def test_dependency_cycle_is_rejected(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][0]["depends_on"] = ["integrator"]
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "cycle" in result.stderr


def test_parallel_write_overlap_is_rejected(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][1]["ownership"]["write_paths"].append("outputguard/jsonl.py")
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "parallel ownership overlap" in result.stderr


def test_workspace_outside_experiment_root_is_rejected(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][0]["workspace"]["path"] = r"D:\Desktop\wrong-place\core"
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "outside experiment_root" in result.stderr


def test_mutable_workspace_must_be_under_worktree_root(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][0]["workspace"]["path"] = str(EXPERIMENT_ROOT / "runs" / "not-a-worktree")
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "outside worktree_root" in result.stderr


def test_mutable_workspace_must_not_be_task_project(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][0]["workspace"]["path"] = manifest["task_project"]["path"]
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "task_project" in result.stderr


def test_workspace_and_artifacts_must_not_overlap_control_or_lane_trees(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][0]["workspace"]["path"] = str(Path(manifest["task_project"]["path"]) / "nested")
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "task_project" in result.stderr

    manifest = valid_manifest()
    manifest["workspace_policy"]["artifact_root"] = str(Path(manifest["task_project"]["path"]) / "artifacts")
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "artifact_root" in result.stderr and "task_project" in result.stderr

    manifest = valid_manifest()
    manifest["workspace_policy"]["artifact_root"] = str(Path(manifest["lanes"][2]["workspace"]["path"]) / "artifacts")
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "artifact_root" in result.stderr and "workspace" in result.stderr


def test_worktree_root_real_path_must_stay_in_experiment_root(tmp_path: Path) -> None:
    declared_root = tmp_path / "declared"
    outside = tmp_path / "outside"
    declared_root.mkdir()
    outside.mkdir()
    worktree_link = declared_root / "worktrees"
    try:
        os.symlink(outside, worktree_link, target_is_directory=True)
    except OSError as exc:
        raise AssertionError(f"symlink setup required for boundary test: {exc}") from exc

    manifest = valid_manifest()
    manifest["workspace_policy"] = {
        "experiment_root": str(declared_root),
        "worktree_root": str(worktree_link),
        "artifact_root": str(declared_root / "runs"),
        "require_clean_start": True,
    }
    manifest["task_project"]["path"] = str(declared_root / "control")
    for lane_item in manifest["lanes"]:
        lane_item["workspace"]["path"] = str(worktree_link / lane_item["lane_id"])
    manifest["lanes"][3]["workspace"]["path"] = manifest["lanes"][2]["workspace"]["path"]
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "real path" in result.stderr and "experiment_root" in result.stderr


def test_lane_workspace_symlink_alias_is_rejected(tmp_path: Path) -> None:
    declared_root = tmp_path / "declared"
    worktree_root = declared_root / "worktrees"
    shared_workspace = worktree_root / "shared"
    shared_workspace.mkdir(parents=True)
    alias_workspace = worktree_root / "core-alias"
    try:
        os.symlink(shared_workspace, alias_workspace, target_is_directory=True)
    except OSError as exc:
        raise AssertionError(f"symlink setup required for lane alias test: {exc}") from exc

    manifest = valid_manifest()
    manifest["workspace_policy"] = {
        "experiment_root": str(declared_root),
        "worktree_root": str(worktree_root),
        "artifact_root": str(declared_root / "runs"),
        "require_clean_start": True,
    }
    manifest["task_project"]["path"] = str(declared_root / "control")
    manifest["lanes"][0]["workspace"]["path"] = str(alias_workspace)
    manifest["lanes"][1]["workspace"]["path"] = str(shared_workspace)
    manifest["lanes"][2]["workspace"]["path"] = str(worktree_root / "integrator")
    manifest["lanes"][3]["workspace"]["path"] = manifest["lanes"][2]["workspace"]["path"]
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "workspace conflicts" in result.stderr


def test_reviewer_must_depend_on_integrator_and_share_target_workspace(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][3]["depends_on"] = ["core"]
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "reviewer" in result.stderr and "integrator" in result.stderr

    manifest = valid_manifest()
    manifest["lanes"][3]["workspace"]["path"] = str(EXPERIMENT_ROOT / "worktrees" / "detached-review")
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "reviewer workspace" in result.stderr


def test_windows_ownership_aliases_are_rejected(tmp_path: Path) -> None:
    aliases = ["OUTPUTGUARD/JSONL.PY", "outputguard/./jsonl.py", "outputguard//jsonl.py"]
    for alias in aliases:
        manifest = valid_manifest()
        manifest["lanes"][1]["ownership"]["write_paths"].append(alias)
        result = run_cli(tmp_path, manifest, "validate")
        assert result.returncode == 1, alias
        assert "ownership" in result.stderr or "canonical" in result.stderr


def test_integration_order_must_respect_dependencies(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["integration_order"] = ["integrator", "core", "cli", "reviewer"]
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "integration_order" in result.stderr


def test_project_generates_briefs_from_one_canonical_manifest(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["workspace_policy"]["artifact_root"] = str(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    output_dir = tmp_path / "briefs"
    result = subprocess.run(
        [sys.executable, str(CLI), "project", str(manifest_path), "--out", str(output_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    briefs = sorted(output_dir.glob("*.task-brief.json"))
    assert [path.name for path in briefs] == [
        "cli.task-brief.json",
        "core.task-brief.json",
        "integrator.task-brief.json",
        "reviewer.task-brief.json",
    ]
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_digest = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    core = json.loads((output_dir / "core.task-brief.json").read_text(encoding="utf-8"))
    assert core["manifest_ref"] == {"run_id": manifest["run_id"], "sha256": expected_digest}
    assert core["base"] == manifest["base"]
    assert core["runtime"] == manifest["runtime"]
    assert core["workspace"] == manifest["lanes"][0]["workspace"]
    assert core["ownership"] == manifest["lanes"][0]["ownership"]


def test_projection_must_stay_under_artifact_root(tmp_path: Path) -> None:
    manifest = valid_manifest()
    artifact_root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    manifest["workspace_policy"]["artifact_root"] = str(artifact_root)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), "project", str(manifest_path), "--out", str(outside)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "artifact_root" in result.stderr
    assert not outside.exists()


def test_git_branch_and_timestamp_rules_are_fail_closed(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["lanes"][0]["workspace"]["branch"] = "codex/foo@{bar}"
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "branch identity" in result.stderr

    manifest = valid_manifest()
    manifest["lanes"][0]["workspace"]["branch"] = "codex/foo//bar"
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "branch identity" in result.stderr

    manifest = valid_manifest()
    manifest["created_at"] = "2026-08-15 12:00:00-04:00"
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 1
    assert "timestamp" in result.stderr


def test_skill_stops_after_planning_and_has_a_validation_feedback_loop() -> None:
    text = (ROOT / "skills" / "team-plan" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "stop after" in text or "then stop" in text
    assert "fix" in text and "run the validator again" in text


def test_validation_does_not_mutate_input(tmp_path: Path) -> None:
    manifest = valid_manifest()
    before = copy.deepcopy(manifest)
    result = run_cli(tmp_path, manifest, "validate")
    assert result.returncode == 0, result.stderr
    assert manifest == before


def main() -> int:
    failures = 0
    tests_without_tmp = [test_schema_and_skill_entrypoint_exist]
    tests_with_tmp = [
        test_valid_manifest_is_accepted,
        test_unknown_dependency_is_rejected,
        test_dependency_cycle_is_rejected,
        test_parallel_write_overlap_is_rejected,
        test_workspace_outside_experiment_root_is_rejected,
        test_mutable_workspace_must_be_under_worktree_root,
        test_mutable_workspace_must_not_be_task_project,
        test_workspace_and_artifacts_must_not_overlap_control_or_lane_trees,
        test_worktree_root_real_path_must_stay_in_experiment_root,
        test_lane_workspace_symlink_alias_is_rejected,
        test_reviewer_must_depend_on_integrator_and_share_target_workspace,
        test_windows_ownership_aliases_are_rejected,
        test_integration_order_must_respect_dependencies,
        test_project_generates_briefs_from_one_canonical_manifest,
        test_projection_must_stay_under_artifact_root,
        test_git_branch_and_timestamp_rules_are_fail_closed,
        test_validation_does_not_mutate_input,
    ]
    tests_without_tmp.append(test_skill_stops_after_planning_and_has_a_validation_feedback_loop)
    for test in tests_without_tmp:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    for test in tests_with_tmp:
        try:
            run_root = EXPERIMENT_ROOT / "runs"
            run_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=run_root) as directory:
                test(Path(directory))
            print(f"PASS {test.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    print(f"SUMMARY: {len(tests_without_tmp) + len(tests_with_tmp) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
