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
TEAM = ROOT / "scripts" / "team.py"
SCHEMA = ROOT / "schemas" / "team-router-artifacts.schema.json"
SKILL = ROOT / "skills" / "team" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "team" / "agents" / "openai.yaml"


def load_support(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load test support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN_SUPPORT = load_support("team_run_test_support_router", "tests/test_team_run.py")
INTEGRATE_SUPPORT = load_support("team_integrate_test_support_router", "tests/test_team_integrate.py")
FINISH_SUPPORT = load_support("team_finish_test_support_router", "tests/test_team_finish.py")
RECOVER_SUPPORT = load_support("team_recover_test_support_router", "tests/test_team_recover.py")


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def route(fixture: dict, run_root: Path | None = None) -> tuple[subprocess.CompletedProcess[str], dict | None]:
    target = run_root or Path(fixture["run_root"])
    result = run_command(
        [
            sys.executable,
            str(TEAM),
            "route",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(target),
        ],
        cwd=ROOT,
    )
    document = json.loads(result.stdout) if result.returncode == 0 else None
    return result, document


def test_entrypoints_exist() -> None:
    assert TEAM.is_file()
    assert SCHEMA.is_file()
    assert SKILL.is_file()
    assert OPENAI_YAML.is_file()


def test_route_missing_run_to_team_run(tmp_path: Path) -> None:
    fixture = RUN_SUPPORT.create_fixture(tmp_path)
    target = Path(fixture["artifact_root"]) / "planned-run"
    result, document = route(fixture, target)
    assert result.returncode == 0, result.stderr
    assert document is not None
    assert document["state"] == "planned"
    assert document["next_skill"] == "team-run"
    assert document["next_action"] == "prepare-run-artifacts"
    assert document["authorization"] == {
        "command_execution": False,
        "git_mutation": False,
        "task_creation": False,
        "workspace_cleanup": False,
    }


def test_route_prepared_run_to_status_initialization(tmp_path: Path) -> None:
    fixture = RUN_SUPPORT.create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "prepared-run"
    prepared = RUN_SUPPORT.run_prepare(fixture, run_root)
    assert prepared.returncode == 0, prepared.stderr
    fixture["run_root"] = run_root
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None
    assert document["next_skill"] == "team-status"
    assert document["next_action"] == "initialize-status-facts"


def test_route_handoffs_through_integration_stages(tmp_path: Path) -> None:
    fixture = INTEGRATE_SUPPORT.create_handoff_fixture(tmp_path)
    canonical_snapshot = Path(fixture["run_root"]) / "status-snapshot.json"
    shutil.copy2(Path(fixture["status_snapshot"]), canonical_snapshot)
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "freeze-integration-candidates"
    for lane_id in ("core", "cli"):
        candidate_result, _ = INTEGRATE_SUPPORT.build_candidate(fixture, lane_id)
        assert candidate_result.returncode == 0, candidate_result.stderr
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "prepare-integration-plan"
    plan_result, _ = INTEGRATE_SUPPORT.prepare_plan(fixture)
    assert plan_result.returncode == 0, plan_result.stderr
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "apply-integration-plan"
    assert document["requires_separate_authority"] is True


def test_route_passed_gate_through_finish_to_complete(tmp_path: Path) -> None:
    fixture = FINISH_SUPPORT.create_integrated_fixture(tmp_path)
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "record-independent-review"
    review_result, review = FINISH_SUPPORT.record_review(fixture)
    assert review_result.returncode == 0, review_result.stderr
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "audit-final-state"
    audit_result, audit_path = FINISH_SUPPORT.audit(fixture, review)
    assert audit_result.returncode == 0, audit_result.stderr
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "finalize-milestone"
    final_result, _ = FINISH_SUPPORT.finalize(fixture, review, audit_path)
    assert final_result.returncode == 0, final_result.stderr
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None
    assert document["state"] == "complete"
    assert document["next_skill"] is None


def test_route_failed_preflight_through_recovery_plan(tmp_path: Path) -> None:
    fixture = RECOVER_SUPPORT.create_blocked_fixture(tmp_path)
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "freeze-recovery-candidate"
    core = Path(fixture["core"])
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: recovery candidate")
    candidate_result, candidate = RECOVER_SUPPORT.create_candidate(fixture, mode="commit")
    assert candidate_result.returncode == 0, candidate_result.stderr
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "prepare-recovery-plan"
    plan_result, _ = RECOVER_SUPPORT.prepare_recovery(fixture, candidate)
    assert plan_result.returncode == 0, plan_result.stderr
    result, document = route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None and document["next_action"] == "project-recovery-brief"


def test_route_rejects_canonical_artifact_with_wrong_manifest(tmp_path: Path) -> None:
    fixture = RUN_SUPPORT.create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "tampered-run"
    prepared = RUN_SUPPORT.run_prepare(fixture, run_root)
    assert prepared.returncode == 0, prepared.stderr
    fixture["run_root"] = run_root
    dispatch = read_json(run_root / "dispatch-bundle.json")
    dispatch["manifest_ref"]["sha256"] = "sha256:" + "0" * 64
    write_json(run_root / "dispatch-bundle.json", dispatch)
    result, document = route(fixture)
    assert result.returncode == 1
    assert document is None
    assert "manifest" in result.stderr.lower()


def test_route_output_never_overwrites(tmp_path: Path) -> None:
    fixture = RUN_SUPPORT.create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "persisted-run"
    prepared = RUN_SUPPORT.run_prepare(fixture, run_root)
    assert prepared.returncode == 0, prepared.stderr
    output = run_root / "team-route.json"
    command = [
        sys.executable,
        str(TEAM),
        "route",
        str(fixture["manifest_path"]),
        "--run-dir",
        str(run_root),
        "--out",
        str(output),
    ]
    first = run_command(command, cwd=ROOT)
    assert first.returncode == 0, first.stderr
    original = output.read_bytes()
    second = run_command(command, cwd=ROOT)
    assert second.returncode == 1
    assert output.read_bytes() == original


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoints_exist]
    tests_with_tmp = [
        test_route_missing_run_to_team_run,
        test_route_prepared_run_to_status_initialization,
        test_route_handoffs_through_integration_stages,
        test_route_passed_gate_through_finish_to_complete,
        test_route_failed_preflight_through_recovery_plan,
        test_route_rejects_canonical_artifact_with_wrong_manifest,
        test_route_output_never_overwrites,
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
