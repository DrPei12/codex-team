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


def load_support(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load test support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = load_support("team_run_test_support_v01", "tests/test_team_run.py")
STATUS = load_support("team_status_test_support_v01", "tests/test_team_status.py")
INTEGRATE = load_support("team_integrate_test_support_v01", "tests/test_team_integrate.py")
FINISH = load_support("team_finish_test_support_v01", "tests/test_team_finish.py")
ROUTER = load_support("team_router_test_support_v01", "tests/test_team_router.py")

TEAM_STATUS = ROOT / "scripts" / "team-status.py"
TEAM_INTEGRATE = ROOT / "scripts" / "team-integrate.py"


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def assert_route(fixture: dict, action: str) -> dict:
    result, document = ROUTER.route(fixture)
    assert result.returncode == 0, result.stderr
    assert document is not None
    assert document["next_action"] == action, document
    assert not any(document["authorization"].values())
    return document


def validate_artifacts(artifacts: list[tuple[Path, Path]]) -> int:
    try:
        import jsonschema
    except ModuleNotFoundError:
        print("SKIP jsonschema artifact validation: dependency unavailable")
        return 0
    validated = 0
    validators: dict[Path, object] = {}
    for artifact, schema_path in artifacts:
        validator = validators.get(schema_path)
        if validator is None:
            schema = read_json(schema_path)
            jsonschema.Draft202012Validator.check_schema(schema)
            validator = jsonschema.Draft202012Validator(schema)
            validators[schema_path] = validator
        validator.validate(read_json(artifact))
        validated += 1
    return validated


def test_full_team_v01_mainline_offline(tmp_path: Path) -> None:
    fixture = RUN.create_fixture(tmp_path)
    manifest = read_json(Path(fixture["manifest_path"]))
    manifest["global_gates"] = [
        {
            "gate_id": "offline-smoke",
            "owner": "integrator",
            "command": "python -c \"print('gate-ok')\"",
            "evidence_required": ["exact tree", "command log", "exit code"],
        }
    ]
    write_json(Path(fixture["manifest_path"]), manifest)
    fixture["manifest"] = manifest
    shutil.rmtree(Path(fixture["briefs"]))
    projected = run_command(
        [
            sys.executable,
            str(RUN.TEAM_PLAN),
            "project",
            str(fixture["manifest_path"]),
            "--out",
            str(fixture["briefs"]),
        ],
        cwd=ROOT,
    )
    assert projected.returncode == 0, projected.stderr
    run_root = Path(fixture["artifact_root"]) / "team-v01-run"
    fixture["run_root"] = run_root
    assert_route(fixture, "prepare-run-artifacts")

    prepared = RUN.run_prepare(fixture, run_root)
    assert prepared.returncode == 0, prepared.stderr
    assert_route(fixture, "initialize-status-facts")

    facts_path = run_root / "status-facts.json"
    initialized = run_command(
        [
            sys.executable,
            str(TEAM_STATUS),
            "init-facts",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--out",
            str(facts_path),
        ],
        cwd=ROOT,
    )
    assert initialized.returncode == 0, initialized.stderr
    fixture["facts"] = facts_path
    assert_route(fixture, "render-status")

    facts = read_json(facts_path)
    project_id = fixture["manifest"]["task_project"]["project_id"]
    for lane_id, owned_path in (("core", "src/core.py"), ("cli", "src/cli.py")):
        STATUS.create_passed_worker_receipt(fixture, lane_id)
        workspace = Path(fixture[lane_id])
        target = workspace / owned_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{lane_id} = True\n", encoding="utf-8")
        RUN.git(workspace, "add", owned_path)
        RUN.git(workspace, "commit", "-m", f"feat: complete {lane_id}")
        item = STATUS.lane_facts(facts, lane_id)
        STATUS.bind_task(item, lane_id, project_id, "completed")
        STATUS.attach_completed_artifacts(fixture, facts, lane_id)
        item["workspace"]["head"] = RUN.git(workspace, "rev-parse", "HEAD")
        item["workspace"]["observed_at"] = "2026-08-25T12:00:00-04:00"
    write_json(facts_path, facts)

    snapshot_path = run_root / "status-snapshot.json"
    rendered = run_command(
        [
            sys.executable,
            str(TEAM_STATUS),
            "render",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--facts",
            str(facts_path),
            "--out",
            str(snapshot_path),
        ],
        cwd=ROOT,
    )
    assert rendered.returncode == 0, rendered.stderr
    fixture["integration_facts"] = facts_path
    fixture["status_snapshot"] = snapshot_path
    fixture["candidates"] = run_root / "candidates"
    fixture["candidates"].mkdir()
    assert_route(fixture, "freeze-integration-candidates")

    candidate_paths: list[Path] = []
    for lane_id in ("core", "cli"):
        candidate_result, candidate = INTEGRATE.build_candidate(fixture, lane_id)
        assert candidate_result.returncode == 0, candidate_result.stderr
        candidate_paths.append(candidate)
    assert_route(fixture, "prepare-integration-plan")

    plan_result, plan_path = INTEGRATE.prepare_plan(fixture)
    assert plan_result.returncode == 0, plan_result.stderr
    assert_route(fixture, "apply-integration-plan")

    apply_path = run_root / "integration-apply.json"
    applied = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "apply",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--plan",
            str(plan_path),
            "--receipt",
            str(apply_path),
            "--allow-git-mutation",
        ],
        cwd=ROOT,
    )
    assert applied.returncode == 0, applied.stderr
    fixture["integration_plan"] = plan_path
    fixture["apply_receipt"] = apply_path
    assert_route(fixture, "run-declared-gates")

    gate_path = run_root / "gate-receipt.json"
    gated = run_command(
        [
            sys.executable,
            str(TEAM_INTEGRATE),
            "run-gates",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--plan",
            str(plan_path),
            "--apply-receipt",
            str(apply_path),
            "--receipt",
            str(gate_path),
            "--allow-command-execution",
        ],
        cwd=ROOT,
    )
    assert gated.returncode == 0, gated.stderr
    fixture["gate_receipt"] = gate_path
    assert_route(fixture, "record-independent-review")

    review_result, review_path = FINISH.record_review(fixture)
    assert review_result.returncode == 0, review_result.stderr
    assert_route(fixture, "audit-final-state")
    audit_result, audit_path = FINISH.audit(fixture, review_path)
    assert audit_result.returncode == 0, audit_result.stderr
    assert read_json(audit_path)["status"] == "ready-to-finish"
    assert_route(fixture, "finalize-milestone")
    final_result, milestone_path = FINISH.finalize(fixture, review_path, audit_path)
    assert final_result.returncode == 0, final_result.stderr
    final_route = assert_route(fixture, "no-next-phase")
    assert final_route["state"] == "complete"

    schemas = ROOT / "schemas"
    artifacts: list[tuple[Path, Path]] = [
        (Path(fixture["manifest_path"]), schemas / "team-plan-manifest.schema.json"),
        (run_root / "preregistration.json", schemas / "team-run-artifacts.schema.json"),
        (run_root / "parent-preflight-receipt.json", schemas / "team-run-artifacts.schema.json"),
        (run_root / "dispatch-bundle.json", schemas / "team-run-artifacts.schema.json"),
        (facts_path, schemas / "team-status-artifacts.schema.json"),
        (snapshot_path, schemas / "team-status-artifacts.schema.json"),
        *[(path, schemas / "team-integrate-artifacts.schema.json") for path in candidate_paths],
        (plan_path, schemas / "team-integrate-artifacts.schema.json"),
        (apply_path, schemas / "team-integrate-artifacts.schema.json"),
        (gate_path, schemas / "team-integrate-artifacts.schema.json"),
        (review_path, schemas / "team-finish-artifacts.schema.json"),
        (audit_path, schemas / "team-finish-artifacts.schema.json"),
        (milestone_path, schemas / "team-finish-artifacts.schema.json"),
    ]
    worker_receipts = sorted((run_root / "worker-receipts").glob("*.json"))
    artifacts.extend((path, schemas / "team-run-artifacts.schema.json") for path in worker_receipts)
    validated = validate_artifacts(artifacts)
    if validated:
        assert validated == len(artifacts)
        print(f"PASS schema validation for {validated} end-to-end artifacts")


def main() -> int:
    failures = 0
    tests = [test_full_team_v01_mainline_offline]
    for test in tests:
        try:
            with tempfile.TemporaryDirectory() as directory:
                test(Path(directory))
            print(f"PASS {test.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    print(f"SUMMARY: {len(tests) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
