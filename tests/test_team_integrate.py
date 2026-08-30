from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEAM_INTEGRATE = ROOT / "scripts" / "team-integrate.py"
SCHEMA = ROOT / "schemas" / "team-integrate-artifacts.schema.json"
SKILL = ROOT / "skills" / "team-integrate" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "team-integrate" / "agents" / "openai.yaml"


def load_support(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load test support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN_SUPPORT = load_support("team_run_test_support_integrate", "tests/test_team_run.py")
STATUS_SUPPORT = load_support("team_status_test_support_integrate", "tests/test_team_status.py")


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def create_handoff_fixture(
    tmp_path: Path,
    lanes: tuple[str, ...] = ("core", "cli"),
    gate_commands: tuple[str, ...] | None = None,
    core_write_paths: list[str] | None = None,
    core_forbidden_paths: list[str] | None = None,
    changed_paths: dict[str, str] | None = None,
    team_run_path: Path | None = None,
    team_status_path: Path | None = None,
    lane_metadata: dict[str, dict[str, object]] | None = None,
) -> dict:
    fixture = RUN_SUPPORT.create_fixture(tmp_path)
    manifest = fixture["manifest"]
    if core_write_paths is not None:
        manifest["lanes"][0]["ownership"]["write_paths"] = core_write_paths
    if core_forbidden_paths is not None:
        manifest["lanes"][0]["ownership"]["forbidden_paths"] = core_forbidden_paths
    for lane_item in manifest["lanes"]:
        updates = (lane_metadata or {}).get(lane_item["lane_id"])
        if updates:
            lane_item.update(updates)
    commands = gate_commands or ("python -c \"print('gate-ok')\"",)
    manifest["global_gates"] = [
        {
            "gate_id": f"integration-{index}",
            "owner": "integrator",
            "command": command,
            "evidence_required": ["exact tree", "command log", "exit code"],
        }
        for index, command in enumerate(commands, start=1)
    ]
    write_json(Path(fixture["manifest_path"]), manifest)
    shutil.rmtree(Path(fixture["briefs"]))
    projection = run_command(
        [
            sys.executable,
            str(RUN_SUPPORT.TEAM_PLAN),
            "project",
            str(fixture["manifest_path"]),
            "--out",
            str(fixture["briefs"]),
        ],
        cwd=ROOT,
    )
    if projection.returncode != 0:
        raise AssertionError(f"team-plan reprojection failed:\n{projection.stderr}")
    run_root = Path(fixture["artifact_root"]) / "status-run"
    prepared = run_command(
        [
            sys.executable,
            str(team_run_path or RUN_SUPPORT.TEAM_RUN),
            "prepare",
            str(fixture["manifest_path"]),
            "--briefs",
            str(fixture["briefs"]),
            "--out",
            str(run_root),
        ],
        cwd=ROOT,
    )
    if prepared.returncode != 0:
        raise AssertionError(f"team-run preparation failed:\n{prepared.stderr}")
    facts_path = run_root / "status-facts.json"
    initialized = run_command(
        [
            sys.executable,
            str(team_status_path or STATUS_SUPPORT.TEAM_STATUS),
            "init-facts",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--out",
            str(facts_path),
        ],
        cwd=ROOT,
    )
    if initialized.returncode != 0:
        raise AssertionError(f"team-status facts initialization failed:\n{initialized.stderr}")
    fixture["run_root"] = run_root
    fixture["facts"] = facts_path
    facts = read_json(Path(fixture["facts"]))
    project_id = fixture["manifest"]["task_project"]["project_id"]
    for lane_id in lanes:
        receipt = run_root / "worker-receipts" / f"{lane_id}.json"
        preflight = run_command(
            [
                sys.executable,
                str(team_run_path or RUN_SUPPORT.TEAM_RUN),
                "worker-preflight",
                str(fixture["manifest_path"]),
                "--brief",
                str(Path(fixture["briefs"]) / f"{lane_id}.task-brief.json"),
                "--receipt",
                str(receipt),
            ],
            cwd=Path(fixture[lane_id]),
        )
        if preflight.returncode != 0:
            raise AssertionError(f"worker preflight fixture failed:\n{preflight.stderr}")
        workspace = Path(fixture[lane_id])
        owned_path = (changed_paths or {}).get(
            lane_id,
            "src/core.py" if lane_id == "core" else "src/cli.py",
        )
        target = workspace / owned_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{lane_id} = True\n", encoding="utf-8")
        RUN_SUPPORT.git(workspace, "add", owned_path)
        RUN_SUPPORT.git(workspace, "commit", "-m", f"feat: add {lane_id}")
        head = RUN_SUPPORT.git(workspace, "rev-parse", "HEAD")
        item = STATUS_SUPPORT.lane_facts(facts, lane_id)
        STATUS_SUPPORT.bind_task(item, lane_id, project_id, "completed")
        STATUS_SUPPORT.attach_completed_artifacts(fixture, facts, lane_id)
        item["workspace"]["head"] = head
        item["workspace"]["observed_at"] = "2026-08-24T14:00:00-04:00"
    facts_path = Path(fixture["run_root"]) / "facts-handoff-integrate.json"
    write_json(facts_path, facts)
    snapshot = Path(fixture["run_root"]) / "status-handoff-integrate.json"
    result = run_command(
        [
            sys.executable,
            str(team_status_path or STATUS_SUPPORT.TEAM_STATUS),
            "render",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--facts",
            str(facts_path),
            "--out",
            str(snapshot),
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise AssertionError(f"status fixture render failed:\n{result.stderr}")
    fixture["integration_facts"] = facts_path
    fixture["status_snapshot"] = snapshot
    fixture["candidates"] = Path(fixture["run_root"]) / "candidates"
    fixture["candidates"].mkdir()
    return fixture


def build_candidate(fixture: dict, lane_id: str, name: str | None = None) -> tuple[subprocess.CompletedProcess[str], Path]:
    facts = read_json(Path(fixture["integration_facts"]))
    item = STATUS_SUPPORT.lane_facts(facts, lane_id)
    output = Path(fixture["candidates"]) / (name or f"{lane_id}.json")
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "candidate",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--lane",
            lane_id,
            "--report",
            item["worker_report"]["path"],
            "--evidence",
            item["evidence"]["path"],
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def prepare_plan(fixture: dict, name: str = "integration-plan.json") -> tuple[subprocess.CompletedProcess[str], Path]:
    output = Path(fixture["run_root"]) / name
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "prepare",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--status",
            str(fixture["status_snapshot"]),
            "--candidates",
            str(fixture["candidates"]),
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def test_entrypoints_exist() -> None:
    assert TEAM_INTEGRATE.is_file()
    assert SCHEMA.is_file()
    assert SKILL.is_file()
    assert OPENAI_YAML.is_file()


def test_candidate_binds_git_report_and_evidence(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path, ("core",))
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 0, result.stderr
    candidate = read_json(output)
    assert candidate["kind"] == "integration-candidate"
    assert candidate["lane_id"] == "core"
    assert candidate["workspace"]["head"] == RUN_SUPPORT.git(Path(fixture["core"]), "rev-parse", "HEAD")
    assert candidate["changed_files"] == ["src/core.py"]
    assert candidate["workspace"]["ordinary_status"] == []


def test_candidate_accepts_explicit_recursive_directory_glob(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(
        tmp_path,
        ("core",),
        core_write_paths=["docs/**"],
        changed_paths={"core": "docs/nested/core.py"},
    )
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 0, result.stderr
    assert read_json(output)["changed_files"] == ["docs/nested/core.py"]


def test_candidate_accepts_descendant_of_bare_ownership_root(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(
        tmp_path,
        ("core",),
        core_write_paths=["docs"],
        changed_paths={"core": "docs/nested/core.py"},
    )
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 0, result.stderr
    assert read_json(output)["changed_files"] == ["docs/nested/core.py"]


def test_candidate_normalizes_windows_alias_and_case(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path, ("core",), core_write_paths=[r"SRC\CORE.PY"])
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 0, result.stderr
    assert read_json(output)["changed_files"] == ["src/core.py"]


def test_candidate_rejects_changed_file_outside_exact_ownership(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(
        tmp_path,
        ("core",),
        core_write_paths=["src/core.py"],
        changed_paths={"core": "src/other.py"},
    )
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 1
    assert "ownership" in result.stderr.lower()
    assert not output.exists()


def test_candidate_forbidden_paths_override_bare_write_root(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(
        tmp_path,
        ("core",),
        core_write_paths=["owned"],
        core_forbidden_paths=["owned/secrets"],
        changed_paths={"core": "owned/secrets/key.py"},
    )
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 1
    assert "ownership" in result.stderr.lower()
    assert not output.exists()


def test_candidate_rejects_out_of_ownership_change(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path, ("core",))
    workspace = Path(fixture["core"])
    (workspace / "outside.txt").write_text("outside\n", encoding="utf-8")
    RUN_SUPPORT.git(workspace, "add", "outside.txt")
    RUN_SUPPORT.git(workspace, "commit", "-m", "test: outside ownership")
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 1
    assert "ownership" in result.stderr.lower()
    assert not output.exists()


def test_candidate_rejects_dirty_workspace(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path, ("core",))
    (Path(fixture["core"]) / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    result, output = build_candidate(fixture, "core")
    assert result.returncode == 1
    assert "clean" in result.stderr.lower()
    assert not output.exists()


def test_prepare_orders_valid_candidates(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path)
    for lane_id in ("core", "cli"):
        result, _ = build_candidate(fixture, lane_id)
        assert result.returncode == 0, result.stderr
    result, output = prepare_plan(fixture)
    assert result.returncode == 0, result.stderr
    plan = read_json(output)
    assert plan["status"] == "ready-for-authorized-apply"
    assert [item["lane_id"] for item in plan["candidates"]] == ["core", "cli"]
    assert plan["authorization"] == {"command_execution": False, "git_mutation": False}


def test_prepare_rejects_lane_without_handoff_status(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path, ("core",))
    result, _ = build_candidate(fixture, "core")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(Path(fixture["status_snapshot"]))
    core = next(item for item in snapshot["lanes"] if item["lane_id"] == "core")
    core["status"] = "working"
    write_json(Path(fixture["status_snapshot"]), snapshot)
    result, output = prepare_plan(fixture)
    assert result.returncode == 1
    assert "handoff-ready" in result.stderr.lower()
    assert not output.exists()


def test_apply_requires_explicit_mutation_flag(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path)
    for lane_id in ("core", "cli"):
        assert build_candidate(fixture, lane_id)[0].returncode == 0
    assert prepare_plan(fixture)[0].returncode == 0
    receipt = Path(fixture["run_root"]) / "integration-apply.json"
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "apply",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(Path(fixture["run_root"]) / "integration-plan.json"),
            "--receipt",
            str(receipt),
        ],
        cwd=ROOT,
    )
    assert result.returncode == 1
    assert "allow-git-mutation" in result.stderr.lower()
    assert not receipt.exists()


def test_apply_rejects_tampered_plan_commit(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path)
    for lane_id in ("core", "cli"):
        assert build_candidate(fixture, lane_id)[0].returncode == 0
    result, plan_path = prepare_plan(fixture)
    assert result.returncode == 0, result.stderr
    plan = read_json(plan_path)
    plan["candidates"][0]["commit"] = fixture["manifest"]["base"]["commit"]
    write_json(plan_path, plan)
    receipt = Path(fixture["run_root"]) / "tampered-apply.json"
    before = RUN_SUPPORT.git(Path(fixture["integrator"]), "rev-parse", "HEAD")
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "apply",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(plan_path),
            "--receipt",
            str(receipt),
            "--allow-git-mutation",
        ],
        cwd=ROOT,
    )
    assert result.returncode == 1
    assert "candidate" in result.stderr.lower() and "plan" in result.stderr.lower()
    assert RUN_SUPPORT.git(Path(fixture["integrator"]), "rev-parse", "HEAD") == before
    assert not receipt.exists()


def test_apply_merges_candidates_in_integrator_workspace(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path)
    for lane_id in ("core", "cli"):
        assert build_candidate(fixture, lane_id)[0].returncode == 0
    assert prepare_plan(fixture)[0].returncode == 0
    receipt = Path(fixture["run_root"]) / "integration-apply.json"
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "apply",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(Path(fixture["run_root"]) / "integration-plan.json"),
            "--receipt",
            str(receipt),
            "--allow-git-mutation",
        ],
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    document = read_json(receipt)
    assert document["status"] == "applied"
    assert [item["lane_id"] for item in document["merges"]] == ["core", "cli"]
    integrator = Path(fixture["integrator"])
    assert (integrator / "src/core.py").is_file()
    assert (integrator / "src/cli.py").is_file()
    assert document["after"]["commit"] == RUN_SUPPORT.git(integrator, "rev-parse", "HEAD")


def test_run_gates_requires_explicit_command_flag(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path)
    for lane_id in ("core", "cli"):
        assert build_candidate(fixture, lane_id)[0].returncode == 0
    assert prepare_plan(fixture)[0].returncode == 0
    apply_receipt = Path(fixture["run_root"]) / "integration-apply.json"
    apply = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "apply",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(Path(fixture["run_root"]) / "integration-plan.json"),
            "--receipt",
            str(apply_receipt),
            "--allow-git-mutation",
        ],
        cwd=ROOT,
    )
    assert apply.returncode == 0, apply.stderr
    gate_receipt = Path(fixture["run_root"]) / "gate-receipt.json"
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "run-gates",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(Path(fixture["run_root"]) / "integration-plan.json"),
            "--apply-receipt",
            str(apply_receipt),
            "--receipt",
            str(gate_receipt),
        ],
        cwd=ROOT,
    )
    assert result.returncode == 1
    assert "allow-command-execution" in result.stderr.lower()
    assert not gate_receipt.exists()


def test_run_gates_records_exact_target_and_log(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(tmp_path)
    for lane_id in ("core", "cli"):
        assert build_candidate(fixture, lane_id)[0].returncode == 0
    assert prepare_plan(fixture)[0].returncode == 0
    plan = Path(fixture["run_root"]) / "integration-plan.json"
    apply_receipt = Path(fixture["run_root"]) / "integration-apply.json"
    assert run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "apply",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(plan),
            "--receipt",
            str(apply_receipt),
            "--allow-git-mutation",
        ],
        cwd=ROOT,
    ).returncode == 0
    gate_receipt = Path(fixture["run_root"]) / "gate-receipt.json"
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "run-gates",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(plan),
            "--apply-receipt",
            str(apply_receipt),
            "--receipt",
            str(gate_receipt),
            "--allow-command-execution",
        ],
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    document = read_json(gate_receipt)
    assert document["status"] == "passed"
    assert document["target"]["commit"] == read_json(apply_receipt)["after"]["commit"]
    assert document["gates"][0]["exit_code"] == 0
    log = Path(document["gates"][0]["log_ref"]["path"])
    assert log.is_file()


def test_run_gates_stops_on_first_nonzero(tmp_path: Path) -> None:
    fixture = create_handoff_fixture(
        tmp_path,
        gate_commands=(
            "python -c \"import sys; sys.exit(3)\"",
            "python -c \"print('must-not-run')\"",
        ),
    )
    for lane_id in ("core", "cli"):
        assert build_candidate(fixture, lane_id)[0].returncode == 0
    assert prepare_plan(fixture)[0].returncode == 0
    plan = Path(fixture["run_root"]) / "integration-plan.json"
    apply_receipt = Path(fixture["run_root"]) / "integration-apply.json"
    assert run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "apply",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(plan),
            "--receipt",
            str(apply_receipt),
            "--allow-git-mutation",
        ],
        cwd=ROOT,
    ).returncode == 0
    gate_receipt = Path(fixture["run_root"]) / "failed-gate-receipt.json"
    result = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "run-gates",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--plan",
            str(plan),
            "--apply-receipt",
            str(apply_receipt),
            "--receipt",
            str(gate_receipt),
            "--allow-command-execution",
        ],
        cwd=ROOT,
    )
    assert result.returncode == 1
    document = read_json(gate_receipt)
    assert document["status"] == "failed"
    assert len(document["gates"]) == 1
    assert document["gates"][0]["exit_code"] == 3
    assert not (Path(fixture["run_root"]) / "integration-gates" / "integration-2.log").exists()


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoints_exist]
    tests_with_tmp = [
        test_candidate_binds_git_report_and_evidence,
        test_candidate_accepts_explicit_recursive_directory_glob,
        test_candidate_accepts_descendant_of_bare_ownership_root,
        test_candidate_normalizes_windows_alias_and_case,
        test_candidate_rejects_changed_file_outside_exact_ownership,
        test_candidate_forbidden_paths_override_bare_write_root,
        test_candidate_rejects_out_of_ownership_change,
        test_candidate_rejects_dirty_workspace,
        test_prepare_orders_valid_candidates,
        test_prepare_rejects_lane_without_handoff_status,
        test_apply_requires_explicit_mutation_flag,
        test_apply_rejects_tampered_plan_commit,
        test_apply_merges_candidates_in_integrator_workspace,
        test_run_gates_requires_explicit_command_flag,
        test_run_gates_records_exact_target_and_log,
        test_run_gates_stops_on_first_nonzero,
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
