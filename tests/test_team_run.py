from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEAM_PLAN = ROOT / "scripts" / "team-plan.py"
TEAM_RUN = ROOT / "scripts" / "team-run.py"
SCHEMA = ROOT / "schemas" / "team-run-artifacts.schema.json"
SKILL = ROOT / "skills" / "team-run" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "team-run" / "agents" / "openai.yaml"


def run_command(
    args: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def git(cwd: Path, *args: str) -> str:
    result = run_command(["git", *args], cwd=cwd)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip()


def lane(
    root: Path,
    base_commit: str,
    lane_id: str,
    role: str,
    depends_on: list[str],
    write_paths: list[str],
) -> dict:
    workspace = root / "worktrees" / lane_id
    return {
        "lane_id": lane_id,
        "role": role,
        "objective": f"Complete the {lane_id} responsibility.",
        "depends_on": depends_on,
        "workspace": {
            "mode": "read-only" if role == "reviewer" else "permanent-worktree",
            "path": str(workspace),
            "branch": None if role == "reviewer" else f"codex/{lane_id}",
            "base_revision": base_commit,
            "clean_start_required": True,
        },
        "ownership": {
            "write_paths": write_paths,
            "forbidden_paths": ["AGENTS.md"],
        },
        "inputs": [],
        "outputs": [f"artifact:{lane_id}:result"],
        "gates": [
            {
                "gate_id": f"{lane_id}-gate",
                "owner": role,
                "command": None if role == "reviewer" else "python -m unittest",
                "evidence_required": ["exact command", "exit code", "head revision"],
            }
        ],
        "stop_conditions": ["workspace identity mismatch", "ownership crossing"],
    }


def create_fixture(tmp_path: Path) -> dict[str, Path | dict]:
    experiment_root = tmp_path / "experiment"
    project = experiment_root / "control"
    worktree_root = experiment_root / "worktrees"
    artifact_root = experiment_root / "runs"
    project.mkdir(parents=True)
    worktree_root.mkdir()
    artifact_root.mkdir()

    git(project, "init", "-b", "main")
    git(project, "config", "user.name", "Codex Test")
    git(project, "config", "user.email", "codex-test@example.invalid")
    (project / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (project / "README.md").write_text("fixture\n", encoding="utf-8")
    git(project, "add", ".")
    git(project, "commit", "-m", "test: establish fixture")
    base_commit = git(project, "rev-parse", "HEAD")
    base_tree = git(project, "rev-parse", "HEAD^{tree}")

    for lane_id in ("core", "cli", "integrator"):
        git(
            project,
            "worktree",
            "add",
            "-b",
            f"codex/{lane_id}",
            str(worktree_root / lane_id),
            base_commit,
        )

    integrator = lane(
        experiment_root,
        base_commit,
        "integrator",
        "integrator",
        ["core", "cli"],
        ["src/**", "tests/**"],
    )
    reviewer = lane(
        experiment_root,
        base_commit,
        "reviewer",
        "reviewer",
        ["integrator"],
        [],
    )
    reviewer["workspace"]["path"] = integrator["workspace"]["path"]
    reviewer["workspace"]["base_revision"] = integrator["workspace"]["base_revision"]

    manifest = {
        "profile": "codex-multitask-team-plan",
        "schema_version": "0.1",
        "kind": "run-manifest",
        "run_id": "run:team-run:test-01",
        "created_at": "2026-08-24T12:00:00-04:00",
        "status": "planned",
        "objective": "Exercise the team-run preparation boundary.",
        "decision": {
            "mode": "multi-task",
            "reason": "Core and CLI have disjoint ownership.",
            "parallel_groups": [["core", "cli"], ["integrator"], ["reviewer"]],
        },
        "client_surface": "codex_desktop",
        "base": {
            "repository": "local/team-run-fixture",
            "branch": "main",
            "commit": base_commit,
            "tree": base_tree,
            "clean": True,
        },
        "task_project": {
            "project_id": "082eff70-1f80-4421-bb5b-d896d12961ff",
            "path": str(project),
            "environment": "local",
        },
        "runtime": {
            "requested_model": "default",
            "requested_thinking": "default",
            "effective_model": "unknown",
            "effective_thinking": "unknown",
        },
        "workspace_policy": {
            "experiment_root": str(experiment_root),
            "worktree_root": str(worktree_root),
            "artifact_root": str(artifact_root),
            "require_clean_start": True,
        },
        "contract": {
            "state": "frozen",
            "source": "README.md",
            "invariants": ["briefs are manifest projections"],
            "forbidden_changes": ["task graph", "ownership"],
        },
        "lanes": [
            lane(experiment_root, base_commit, "core", "implementer", [], ["src/core.py"]),
            lane(experiment_root, base_commit, "cli", "implementer", [], ["src/cli.py"]),
            integrator,
            reviewer,
        ],
        "integration_order": ["core", "cli", "integrator", "reviewer"],
        "global_gates": [
            {
                "gate_id": "public-suite",
                "owner": "integrator",
                "command": "python -m unittest",
                "evidence_required": ["exact tree", "test summary"],
            }
        ],
        "global_stop_conditions": ["contract change", "solution reference leakage"],
    }

    manifest_path = artifact_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    briefs = artifact_root / "briefs"
    result = run_command(
        [sys.executable, str(TEAM_PLAN), "project", str(manifest_path), "--out", str(briefs)],
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise AssertionError(f"team-plan fixture projection failed:\n{result.stderr}")

    return {
        "experiment_root": experiment_root,
        "project": project,
        "worktree_root": worktree_root,
        "artifact_root": artifact_root,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "briefs": briefs,
        "core": worktree_root / "core",
        "cli": worktree_root / "cli",
        "integrator": worktree_root / "integrator",
    }


def run_prepare(fixture: dict[str, Path | dict], out: Path | None = None) -> subprocess.CompletedProcess[str]:
    output = out or Path(fixture["artifact_root"]) / "run-01"
    return run_command(
        [
            sys.executable,
            str(TEAM_RUN),
            "prepare",
            str(fixture["manifest_path"]),
            "--briefs",
            str(fixture["briefs"]),
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_entrypoints_exist() -> None:
    assert TEAM_RUN.is_file()
    assert SCHEMA.is_file()
    assert SKILL.is_file()
    assert OPENAI_YAML.is_file()


def test_prepare_creates_bound_artifacts(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-01"
    result = run_prepare(fixture, run_root)
    assert result.returncode == 0, result.stderr

    preregistration = read_json(run_root / "preregistration.json")
    parent_receipt = read_json(run_root / "parent-preflight-receipt.json")
    dispatch = read_json(run_root / "dispatch-bundle.json")
    assert preregistration["kind"] == "preregistration"
    assert preregistration["authorization"] == {
        "create_tasks": False,
        "create_worktrees": False,
        "implement_code": False,
        "send_messages": False,
    }
    assert parent_receipt["status"] == "passed"
    assert dispatch["status"] == "ready_for_authorized_dispatch"
    assert [item["lane_id"] for item in dispatch["lanes"]] == [
        "core",
        "cli",
        "integrator",
        "reviewer",
    ]
    assert not any(key in json.dumps(dispatch).lower() for key in ("thread_id", "task_id"))
    for directory in (
        "runtime/cache",
        "runtime/dist",
        "runtime/logs",
        "runtime/pytest",
        "worker-receipts",
    ):
        target = run_root / directory
        assert target.is_dir()
        assert not any(target.iterdir())

    prompt = run_root / dispatch["lanes"][0]["prompt_ref"]["path"]
    prompt_bytes = prompt.read_bytes()
    assert dispatch["lanes"][0]["prompt_ref"]["sha256"] == (
        f"sha256:{hashlib.sha256(prompt_bytes).hexdigest()}"
    )
    prompt_text = prompt_bytes.decode("utf-8")
    assert "trusted assignment" in prompt_text.lower()
    assert "untrusted" in prompt_text.lower()
    assert preregistration["manifest_ref"] == parent_receipt["manifest_ref"] == dispatch["manifest_ref"]


def test_tampered_brief_is_rejected_before_output(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    brief_path = Path(fixture["briefs"]) / "core.task-brief.json"
    brief = read_json(brief_path)
    brief["objective"] = "tampered objective"
    brief_path.write_text(json.dumps(brief, indent=2), encoding="utf-8")
    run_root = Path(fixture["artifact_root"]) / "run-tampered"
    result = run_prepare(fixture, run_root)
    assert result.returncode == 1
    assert "brief" in result.stderr.lower()
    assert not run_root.exists()


def test_brief_symlink_is_rejected_before_output(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    brief_path = Path(fixture["briefs"]) / "core.task-brief.json"
    outside = tmp_path / "outside-brief.json"
    outside.write_bytes(brief_path.read_bytes())
    brief_path.unlink()
    try:
        os.symlink(outside, brief_path)
    except OSError as exc:
        raise AssertionError(f"symlink setup required for brief boundary test: {exc}") from exc
    run_root = Path(fixture["artifact_root"]) / "run-symlink"
    result = run_prepare(fixture, run_root)
    assert result.returncode == 1
    assert "brief" in result.stderr.lower() and "symlink" in result.stderr.lower()
    assert not run_root.exists()


def test_dirty_workspace_writes_failed_parent_receipt_only(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    (Path(fixture["core"]) / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    run_root = Path(fixture["artifact_root"]) / "run-dirty"
    result = run_prepare(fixture, run_root)
    assert result.returncode == 1
    receipt = read_json(run_root / "parent-preflight-receipt.json")
    assert receipt["status"] == "failed"
    assert any("clean" in error.lower() for error in receipt["errors"])
    assert not (run_root / "dispatch-bundle.json").exists()
    assert not (run_root / "prompts").exists()


def test_ignored_inventory_is_recorded_without_failing(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    (Path(fixture["core"]) / "cache.pyc").write_bytes(b"ignored")
    run_root = Path(fixture["artifact_root"]) / "run-ignored"
    result = run_prepare(fixture, run_root)
    assert result.returncode == 0, result.stderr
    receipt = read_json(run_root / "parent-preflight-receipt.json")
    core = next(item for item in receipt["lanes"] if item["lane_id"] == "core")
    assert core["observed"]["ordinary_status"] == []
    assert core["observed"]["ignored_files"] == ["cache.pyc"]


def test_prepare_refuses_existing_output(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-existing"
    run_root.mkdir()
    marker = run_root / "keep.txt"
    marker.write_text("keep\n", encoding="utf-8")
    result = run_prepare(fixture, run_root)
    assert result.returncode == 1
    assert marker.read_text(encoding="utf-8") == "keep\n"


def run_worker_preflight(
    fixture: dict[str, Path | dict],
    *,
    lane_id: str,
    cwd: Path,
    receipt: Path,
) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            sys.executable,
            str(TEAM_RUN),
            "worker-preflight",
            str(fixture["manifest_path"]),
            "--brief",
            str(Path(fixture["briefs"]) / f"{lane_id}.task-brief.json"),
            "--receipt",
            str(receipt),
        ],
        cwd=cwd,
    )


def test_worker_preflight_passes_in_assigned_workspace(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-worker-pass"
    assert run_prepare(fixture, run_root).returncode == 0
    receipt_path = run_root / "worker-receipts" / "core.json"
    result = run_worker_preflight(
        fixture,
        lane_id="core",
        cwd=Path(fixture["core"]),
        receipt=receipt_path,
    )
    assert result.returncode == 0, result.stderr
    receipt = read_json(receipt_path)
    assert receipt["status"] == "passed"
    assert receipt["lane_id"] == "core"
    assert all(receipt["checks"].values())


def test_worker_preflight_records_wrong_cwd_failure(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-worker-fail"
    assert run_prepare(fixture, run_root).returncode == 0
    receipt_path = run_root / "worker-receipts" / "core.json"
    result = run_worker_preflight(
        fixture,
        lane_id="core",
        cwd=Path(fixture["project"]),
        receipt=receipt_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert receipt["checks"]["cwd_matches_workspace"] is False


def test_worker_preflight_never_overwrites_receipt(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-worker-once"
    assert run_prepare(fixture, run_root).returncode == 0
    receipt_path = run_root / "worker-receipts" / "core.json"
    first = run_worker_preflight(
        fixture,
        lane_id="core",
        cwd=Path(fixture["core"]),
        receipt=receipt_path,
    )
    assert first.returncode == 0, first.stderr
    original = receipt_path.read_bytes()
    second = run_worker_preflight(
        fixture,
        lane_id="core",
        cwd=Path(fixture["core"]),
        receipt=receipt_path,
    )
    assert second.returncode == 1
    assert receipt_path.read_bytes() == original


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoints_exist]
    tests_with_tmp = [
        test_prepare_creates_bound_artifacts,
        test_tampered_brief_is_rejected_before_output,
        test_brief_symlink_is_rejected_before_output,
        test_dirty_workspace_writes_failed_parent_receipt_only,
        test_ignored_inventory_is_recorded_without_failing,
        test_prepare_refuses_existing_output,
        test_worker_preflight_passes_in_assigned_workspace,
        test_worker_preflight_records_wrong_cwd_failure,
        test_worker_preflight_never_overwrites_receipt,
    ]
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
            with tempfile.TemporaryDirectory() as directory:
                test(Path(directory))
            print(f"PASS {test.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    total = len(tests_without_tmp) + len(tests_with_tmp)
    print(f"SUMMARY: {total - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
