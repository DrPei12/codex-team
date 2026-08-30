from __future__ import annotations

import hashlib
import json
import os
import shutil
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
        "execution_surface": "visible-task",
        "task_title": f"Team Run | {lane_id.title()}",
        "lifecycle": "one-shot",
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
        "user_locale": "en",
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


def file_ref(path: Path) -> dict[str, str]:
    return {
        "path": str(path.resolve()),
        "sha256": f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}",
    }


def advance_integrator(fixture: dict[str, Path | dict]) -> tuple[str, str]:
    source = Path(fixture["core"])
    owned_path = source / "src" / "core.py"
    owned_path.parent.mkdir(parents=True, exist_ok=True)
    owned_path.write_text("post_integration = True\n", encoding="utf-8")
    git(source, "add", "src/core.py")
    git(source, "commit", "-m", "test: create integration candidate")
    source_commit = git(source, "rev-parse", "HEAD")
    integrator = Path(fixture["integrator"])
    git(integrator, "merge", "--no-ff", "--no-edit", source_commit)
    return git(integrator, "rev-parse", "HEAD"), git(integrator, "rev-parse", "HEAD^{tree}")


def write_gate_receipt(
    fixture: dict[str, Path | dict],
    run_root: Path,
    target: tuple[str, str],
    *,
    status: str = "passed",
    manifest_ref: dict[str, str] | None = None,
    include_target: bool = True,
    allow_forged_single_parent: bool = False,
) -> Path:
    expected_gate = fixture["manifest"]["global_gates"][0]
    log_path = run_root / "gate.log"
    log_path.write_text("COMMAND: test\nEXIT: 0\n", encoding="utf-8")
    preregistration = run_root / "preregistration.json"
    manifest_ref_value = manifest_ref or read_json(preregistration)["manifest_ref"]
    base = fixture["manifest"]["base"]
    integrator_lane = next(
        lane for lane in fixture["manifest"]["lanes"] if lane["role"] == "integrator"
    )
    integrator = Path(fixture["integrator"])
    parent_line = git(integrator, "rev-list", "--parents", "-n", "1", target[0]).split()
    if allow_forged_single_parent:
        assert len(parent_line) == 2
        before_commit, source_commit = parent_line[1], target[0]
    else:
        assert len(parent_line) == 3
        before_commit, source_commit = parent_line[1], parent_line[2]
    source_tree = git(integrator, "rev-parse", f"{source_commit}^{{tree}}")
    candidates_dir = run_root / "candidates"
    candidates_dir.mkdir(exist_ok=True)
    candidate_path = candidates_dir / "core.json"
    core_lane = next(lane for lane in fixture["manifest"]["lanes"] if lane["lane_id"] == "core")
    candidate_document = {
        "profile": "codex-multitask-team-integrate",
        "schema_version": "0.1",
        "kind": "integration-candidate",
        "manifest_ref": manifest_ref_value,
        "created_at": "2026-08-29T11:57:00-04:00",
        "lane_id": "core",
        "workspace": {
            "path": str(Path(fixture["core"]).resolve()),
            "branch": core_lane["workspace"]["branch"],
            "base_revision": core_lane["workspace"]["base_revision"],
            "head": source_commit,
            "tree": source_tree,
            "ordinary_status": [],
        },
        "changed_files": ["src/core.py"],
        "report_ref": file_ref(preregistration),
        "evidence_ref": file_ref(preregistration),
        "worker_receipt_ref": file_ref(preregistration),
    }
    candidate_path.write_text(json.dumps(candidate_document, indent=2), encoding="utf-8")
    plan_path = run_root / "integration-plan.json"
    plan = {
        "profile": "codex-multitask-team-integrate",
        "schema_version": "0.1",
        "kind": "integration-plan",
        "manifest_ref": manifest_ref_value,
        "created_at": "2026-08-29T11:58:00-04:00",
        "status": "ready-for-authorized-apply",
        "status_snapshot_ref": file_ref(preregistration),
        "integration_lane": {
            "lane_id": integrator_lane["lane_id"],
            "workspace": integrator_lane["workspace"],
            "base_head": base["commit"],
            "base_tree": base["tree"],
        },
        "candidates": [
            {
                "lane_id": "core",
                "order": 1,
                "candidate_ref": file_ref(candidate_path),
                "commit": source_commit,
                "tree": source_tree,
                "changed_files": ["src/core.py"],
            }
        ],
        "gates": fixture["manifest"]["global_gates"],
        "authorization": {"git_mutation": False, "command_execution": False},
    }
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    apply_path = run_root / "integration-apply.json"
    apply_receipt = {
        "profile": "codex-multitask-team-integrate",
        "schema_version": "0.1",
        "kind": "integration-apply-receipt",
        "manifest_ref": manifest_ref_value,
        "recorded_at": "2026-08-29T11:59:00-04:00",
        "status": "applied",
        "plan_ref": file_ref(plan_path),
        "workspace": str(Path(fixture["integrator"]).resolve()),
        "before": {
            "commit": before_commit,
            "tree": git(integrator, "rev-parse", f"{before_commit}^{{tree}}"),
        },
        "after": {"commit": target[0], "tree": target[1]},
        "merges": [
            {
                "lane_id": "core",
                "source_commit": source_commit,
                "result_commit": target[0],
            }
        ],
        "ordinary_status_after": [],
        "errors": [],
    }
    apply_path.write_text(json.dumps(apply_receipt, indent=2), encoding="utf-8")
    document = {
        "profile": "codex-multitask-team-integrate",
        "schema_version": "0.1",
        "kind": "gate-receipt",
        "manifest_ref": manifest_ref_value,
        "recorded_at": "2026-08-29T12:00:00-04:00",
        "status": status,
        "plan_ref": file_ref(plan_path),
        "apply_receipt_ref": file_ref(apply_path),
        "gates": [
            {
                "gate_id": expected_gate["gate_id"],
                "owner": expected_gate["owner"],
                "command": expected_gate["command"],
                "exit_code": 0,
                "status": "passed",
                "log_ref": file_ref(log_path),
            }
        ],
    }
    if include_target:
        document["target"] = {"commit": target[0], "tree": target[1]}
    gate_path = run_root / "gate-receipt.json"
    gate_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return gate_path


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
    assert fixture["manifest"]["lanes"][0]["task_title"] in prompt_text
    assert dispatch["lanes"][0]["task_title"] == fixture["manifest"]["lanes"][0]["task_title"]
    assert dispatch["lanes"][0]["execution_surface"] == "visible-task"
    assert dispatch["lanes"][0]["lifecycle"] == "one-shot"
    assert dispatch["lanes"][0]["user_locale"] == "en"
    assert preregistration["manifest_ref"] == parent_receipt["manifest_ref"] == dispatch["manifest_ref"]
    reviewer_argv = dispatch["lanes"][-1]["worker_preflight_argv"]
    assert "--gate-receipt" in reviewer_argv
    gate_index = reviewer_argv.index("--gate-receipt")
    assert reviewer_argv[gate_index + 1] == str((run_root / "gate-receipt.json").resolve())


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


def test_global_clean_policy_overrides_lane_relaxation(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    manifest = fixture["manifest"]
    assert isinstance(manifest, dict)
    manifest["lanes"][0]["workspace"]["clean_start_required"] = False
    Path(fixture["manifest_path"]).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.rmtree(Path(fixture["briefs"]))
    projection = run_command(
        [
            sys.executable,
            str(TEAM_PLAN),
            "project",
            str(fixture["manifest_path"]),
            "--out",
            str(fixture["briefs"]),
        ],
        cwd=ROOT,
    )
    assert projection.returncode == 0, projection.stderr
    (Path(fixture["core"]) / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    run_root = Path(fixture["artifact_root"]) / "run-global-clean"
    result = run_prepare(fixture, run_root)
    assert result.returncode == 1
    receipt = read_json(run_root / "parent-preflight-receipt.json")
    core = next(item for item in receipt["lanes"] if item["lane_id"] == "core")
    assert core["expected"]["clean_start_required"] is True
    assert core["checks"]["clean_start"] is False


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
    gate_receipt: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(TEAM_RUN),
        "worker-preflight",
        str(fixture["manifest_path"]),
        "--brief",
        str(Path(fixture["briefs"]) / f"{lane_id}.task-brief.json"),
        "--receipt",
        str(receipt),
    ]
    if gate_receipt is not None:
        args.extend(["--gate-receipt", str(gate_receipt)])
    return run_command(args, cwd=cwd)


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


def test_reviewer_preflight_binds_post_integration_gate_target(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-target"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 0, result.stderr
    receipt = read_json(receipt_path)
    assert receipt["status"] == "passed"
    assert receipt["expected"]["head"] == target[0]
    assert receipt["target"] == {"commit": target[0], "tree": target[1]}
    assert receipt["gate_receipt_ref"] == file_ref(gate_path)
    assert receipt["observed"]["tree"] == target[1]
    assert receipt["checks"]["gate_target_tree_matches_workspace"] is True


def test_reviewer_preflight_rejects_missing_gate_receipt(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-missing-gate"
    assert run_prepare(fixture, run_root).returncode == 0
    advance_integrator(fixture)
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert any("gate-receipt" in error for error in receipt["errors"])


def test_reviewer_preflight_rejects_wrong_manifest_gate(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-wrong-manifest"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(
        fixture,
        run_root,
        target,
        manifest_ref={"run_id": "wrong-run", "sha256": read_json(run_root / "preregistration.json")["manifest_ref"]["sha256"]},
    )
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    assert read_json(receipt_path)["status"] == "failed"


def test_reviewer_preflight_rejects_failed_gate(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-failed-gate"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target, status="failed")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    assert read_json(receipt_path)["status"] == "failed"


def test_reviewer_preflight_rejects_noncanonical_gate_path(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-noncanonical-gate"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    canonical = write_gate_receipt(fixture, run_root, target)
    historical = run_root / "historical-gate-receipt.json"
    canonical.rename(historical)
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=historical,
    )
    assert result.returncode == 1
    assert read_json(receipt_path)["status"] == "failed"


def test_reviewer_preflight_rejects_gate_definition_different_from_manifest(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-wrong-gate-definition"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    document = read_json(gate_path)
    document["gates"][0]["command"] = "python -c \"print('different')\""
    gate_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    assert read_json(receipt_path)["status"] == "failed"
    assert any("differs from manifest" in error for error in read_json(receipt_path)["errors"])


def test_reviewer_preflight_rejects_self_consistent_fake_plan_apply_chain(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-fake-lineage"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    plan_path = run_root / "integration-plan.json"
    apply_path = run_root / "integration-apply.json"
    plan = read_json(plan_path)
    plan["kind"] = "preregistration"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    apply_receipt = read_json(apply_path)
    apply_receipt["plan_ref"] = file_ref(plan_path)
    apply_path.write_text(json.dumps(apply_receipt, indent=2), encoding="utf-8")
    gate = read_json(gate_path)
    gate["plan_ref"] = file_ref(plan_path)
    gate["apply_receipt_ref"] = file_ref(apply_path)
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert any("integration plan identity/status" in error for error in receipt["errors"])


def test_reviewer_preflight_rejects_single_parent_commit_claimed_as_merge(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-fake-merge-topology"
    assert run_prepare(fixture, run_root).returncode == 0
    integrator = Path(fixture["integrator"])
    owned_path = integrator / "src" / "core.py"
    owned_path.parent.mkdir(parents=True, exist_ok=True)
    owned_path.write_text("forged_direct_integration = True\n", encoding="utf-8")
    git(integrator, "add", "src/core.py")
    git(integrator, "commit", "-m", "test: forge direct integration commit")
    target = (git(integrator, "rev-parse", "HEAD"), git(integrator, "rev-parse", "HEAD^{tree}"))
    gate_path = write_gate_receipt(
        fixture,
        run_root,
        target,
        allow_forged_single_parent=True,
    )
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=integrator,
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert any("Git parents differ" in error for error in receipt["errors"])


def test_reviewer_preflight_rejects_unplanned_premerge_commit_as_plan_base(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-unplanned-base"
    assert run_prepare(fixture, run_root).returncode == 0
    integrator = Path(fixture["integrator"])
    (integrator / "unplanned.txt").write_text("not in manifest base\n", encoding="utf-8")
    git(integrator, "add", "unplanned.txt")
    git(integrator, "commit", "-m", "test: add unplanned pre-merge commit")
    unplanned = git(integrator, "rev-parse", "HEAD")
    unplanned_tree = git(integrator, "rev-parse", "HEAD^{tree}")
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    plan_path = run_root / "integration-plan.json"
    apply_path = run_root / "integration-apply.json"
    plan = read_json(plan_path)
    plan["integration_lane"]["base_head"] = unplanned
    plan["integration_lane"]["base_tree"] = unplanned_tree
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    apply_receipt = read_json(apply_path)
    apply_receipt["plan_ref"] = file_ref(plan_path)
    apply_path.write_text(json.dumps(apply_receipt, indent=2), encoding="utf-8")
    gate = read_json(gate_path)
    gate["plan_ref"] = file_ref(plan_path)
    gate["apply_receipt_ref"] = file_ref(apply_path)
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=integrator,
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert any("base differs from manifest" in error for error in receipt["errors"])


def test_reviewer_preflight_rejects_missing_candidate_order(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-missing-order"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    plan_path = run_root / "integration-plan.json"
    apply_path = run_root / "integration-apply.json"
    plan = read_json(plan_path)
    plan["candidates"][0].pop("order")
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    apply_receipt = read_json(apply_path)
    apply_receipt["plan_ref"] = file_ref(plan_path)
    apply_path.write_text(json.dumps(apply_receipt, indent=2), encoding="utf-8")
    gate = read_json(gate_path)
    gate["plan_ref"] = file_ref(plan_path)
    gate["apply_receipt_ref"] = file_ref(apply_path)
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    assert any("order is invalid" in error for error in read_json(receipt_path)["errors"])


def test_reviewer_preflight_rejects_boolean_candidate_order(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-boolean-order"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    plan_path = run_root / "integration-plan.json"
    apply_path = run_root / "integration-apply.json"
    plan = read_json(plan_path)
    plan["candidates"][0]["order"] = True
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    apply_receipt = read_json(apply_path)
    apply_receipt["plan_ref"] = file_ref(plan_path)
    apply_path.write_text(json.dumps(apply_receipt, indent=2), encoding="utf-8")
    gate = read_json(gate_path)
    gate["plan_ref"] = file_ref(plan_path)
    gate["apply_receipt_ref"] = file_ref(apply_path)
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    assert any("order is invalid" in error for error in read_json(receipt_path)["errors"])


def test_reviewer_preflight_rejects_wrong_gate_head_or_tree(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-wrong-target"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    base = fixture["manifest"]["base"]
    gate_path = write_gate_receipt(fixture, run_root, target)
    gate = read_json(gate_path)
    gate["target"]["commit"] = base["commit"]
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    assert read_json(receipt_path)["status"] == "failed"

    fixture = create_fixture(tmp_path / "tree")
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-wrong-tree"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    gate = read_json(gate_path)
    gate["target"]["tree"] = fixture["manifest"]["base"]["tree"]
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert receipt["checks"]["gate_target_tree_matches_workspace"] is False


def test_reviewer_preflight_rejects_dirty_shared_workspace(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-dirty"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    (Path(fixture["integrator"]) / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert receipt["checks"]["clean_start"] is False
    assert receipt["checks"]["gate_target_tree_matches_workspace"] is True


def test_reviewer_preflight_rejects_missing_target(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-reviewer-missing-target"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target, include_target=False)
    receipt_path = run_root / "worker-receipts" / "reviewer.json"
    result = run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    assert read_json(receipt_path)["status"] == "failed"


def test_non_reviewer_cannot_use_gate_receipt(tmp_path: Path) -> None:
    fixture = create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "run-non-reviewer-gate"
    assert run_prepare(fixture, run_root).returncode == 0
    target = advance_integrator(fixture)
    gate_path = write_gate_receipt(fixture, run_root, target)
    receipt_path = run_root / "worker-receipts" / "core-with-gate.json"
    result = run_worker_preflight(
        fixture,
        lane_id="core",
        cwd=Path(fixture["core"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 1
    receipt = read_json(receipt_path)
    assert receipt["status"] == "failed"
    assert any("only valid for reviewer" in error for error in receipt["errors"])


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoints_exist]
    tests_with_tmp = [
        test_prepare_creates_bound_artifacts,
        test_tampered_brief_is_rejected_before_output,
        test_brief_symlink_is_rejected_before_output,
        test_dirty_workspace_writes_failed_parent_receipt_only,
        test_global_clean_policy_overrides_lane_relaxation,
        test_ignored_inventory_is_recorded_without_failing,
        test_prepare_refuses_existing_output,
        test_worker_preflight_passes_in_assigned_workspace,
        test_worker_preflight_records_wrong_cwd_failure,
        test_worker_preflight_never_overwrites_receipt,
        test_reviewer_preflight_binds_post_integration_gate_target,
        test_reviewer_preflight_rejects_missing_gate_receipt,
        test_reviewer_preflight_rejects_wrong_manifest_gate,
        test_reviewer_preflight_rejects_failed_gate,
        test_reviewer_preflight_rejects_noncanonical_gate_path,
        test_reviewer_preflight_rejects_gate_definition_different_from_manifest,
        test_reviewer_preflight_rejects_self_consistent_fake_plan_apply_chain,
        test_reviewer_preflight_rejects_single_parent_commit_claimed_as_merge,
        test_reviewer_preflight_rejects_unplanned_premerge_commit_as_plan_base,
        test_reviewer_preflight_rejects_missing_candidate_order,
        test_reviewer_preflight_rejects_boolean_candidate_order,
        test_reviewer_preflight_rejects_wrong_gate_head_or_tree,
        test_reviewer_preflight_rejects_dirty_shared_workspace,
        test_reviewer_preflight_rejects_missing_target,
        test_non_reviewer_cannot_use_gate_receipt,
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
