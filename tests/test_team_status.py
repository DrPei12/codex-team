from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEAM_STATUS = ROOT / "scripts" / "team-status.py"
SCHEMA = ROOT / "schemas" / "team-status-artifacts.schema.json"
SKILL = ROOT / "skills" / "team-status" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "team-status" / "agents" / "openai.yaml"


def load_team_run_tests():
    path = ROOT / "tests" / "test_team_run.py"
    spec = importlib.util.spec_from_file_location("team_run_test_support", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load team-run test support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEAM_RUN_TESTS = load_team_run_tests()


def load_team_status_runtime():
    spec = importlib.util.spec_from_file_location("team_status_runtime", TEAM_STATUS)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load team-status runtime: {TEAM_STATUS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEAM_STATUS_RUNTIME = load_team_status_runtime()


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def create_status_fixture(tmp_path: Path) -> dict:
    fixture = TEAM_RUN_TESTS.create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "status-run"
    prepared = TEAM_RUN_TESTS.run_prepare(fixture, run_root)
    if prepared.returncode != 0:
        raise AssertionError(f"team-run preparation failed:\n{prepared.stderr}")
    facts = run_root / "status-facts.json"
    initialized = run_command(
        [
            sys.executable,
            str(TEAM_STATUS),
            "init-facts",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--out",
            str(facts),
        ],
        cwd=ROOT,
    )
    if initialized.returncode != 0:
        raise AssertionError(f"team-status facts initialization failed:\n{initialized.stderr}")
    fixture["run_root"] = run_root
    fixture["facts"] = facts
    return fixture


def render(fixture: dict, facts: Path, name: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = Path(fixture["run_root"]) / name
    result = run_command(
        [
            sys.executable,
            str(TEAM_STATUS),
            "render",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--facts",
            str(facts),
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def lane_facts(document: dict, lane_id: str) -> dict:
    return next(item for item in document["lanes"] if item["lane_id"] == lane_id)


def bind_task(item: dict, lane_id: str, project_id: str, state: str) -> None:
    item["task"] = {
        "thread_id": f"thread-{lane_id}",
        "project_id": project_id,
        "state": state,
        "last_event_at": "2026-08-24T13:00:00-04:00",
    }


def copy_facts(fixture: dict, name: str) -> tuple[dict, Path]:
    document = read_json(Path(fixture["facts"]))
    path = Path(fixture["run_root"]) / name
    write_json(path, document)
    return document, path


def create_passed_worker_receipt(fixture: dict, lane_id: str) -> Path:
    receipt = Path(fixture["run_root"]) / "worker-receipts" / f"{lane_id}.json"
    result = TEAM_RUN_TESTS.run_worker_preflight(
        fixture,
        lane_id=lane_id,
        cwd=Path(fixture[lane_id]),
        receipt=receipt,
    )
    if result.returncode != 0:
        raise AssertionError(f"worker preflight fixture failed:\n{result.stderr}")
    return receipt


def create_passed_backbrief(fixture: dict, lane_id: str) -> Path:
    result, receipt = TEAM_RUN_TESTS.run_worker_backbrief(
        fixture,
        run_root=Path(fixture["run_root"]),
        lane_id=lane_id,
        cwd=Path(fixture[lane_id]),
    )
    if result.returncode != 0:
        raise AssertionError(f"worker backbrief fixture failed:\n{result.stderr}")
    return receipt


def set_current_progress(document: dict, lane_id: str) -> None:
    timestamp = document["observed_at"]
    lane_facts(document, lane_id)["progress"] = {
        "phase": "implementation",
        "phase_started_at": timestamp,
        "last_material_progress_at": timestamp,
        "material_delta": "commit:test-material-delta",
        "next_bounded_action": "Run the lane Gate once.",
        "stalled_reason": None,
    }


def accept_checkpoint(fixture: dict, document: dict, checkpoint_id: str) -> None:
    artifact_dir = Path(fixture["run_root"]) / "status-inputs"
    artifact_dir.mkdir(exist_ok=True)
    evidence = artifact_dir / f"{checkpoint_id}.json"
    evidence.write_text(
        json.dumps({"checkpoint_id": checkpoint_id, "result": "accepted"}) + "\n",
        encoding="utf-8",
    )
    checkpoint = next(
        item for item in document["checkpoints"] if item["checkpoint_id"] == checkpoint_id
    )
    checkpoint["state"] = "accepted"
    checkpoint["observed_at"] = document["observed_at"]
    checkpoint["evidence"] = {"state": "valid", "path": str(evidence), "sha256": sha256(evidence)}
    checkpoint["reason"] = "Representative behavior and exact candidate refs were accepted."


def attach_completed_artifacts(fixture: dict, document: dict, lane_id: str, *, accepted: bool = False) -> None:
    run_root = Path(fixture["run_root"])
    artifact_dir = run_root / "status-inputs"
    artifact_dir.mkdir(exist_ok=True)
    report = artifact_dir / f"{lane_id}.worker-report.json"
    evidence = artifact_dir / f"{lane_id}.evidence.json"
    report.write_text(json.dumps({"lane_id": lane_id, "status": "completed"}) + "\n", encoding="utf-8")
    evidence.write_text(json.dumps({"lane_id": lane_id, "result": "passed"}) + "\n", encoding="utf-8")
    item = lane_facts(document, lane_id)
    item["worker_report"] = {
        "status": "completed",
        "path": str(report),
        "sha256": sha256(report),
    }
    item["evidence"] = {
        "state": "valid",
        "path": str(evidence),
        "sha256": sha256(evidence),
    }
    if accepted:
        item["acceptance_state"] = "accepted"


def statuses(snapshot: dict) -> dict[str, str]:
    return {item["lane_id"]: item["status"] for item in snapshot["lanes"]}


def test_entrypoints_exist() -> None:
    assert TEAM_STATUS.is_file()
    assert SCHEMA.is_file()
    assert SKILL.is_file()
    assert OPENAI_YAML.is_file()


def test_ref_file_accepts_real_path_alias_within_allowed_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real-artifact-root"
    real_root.mkdir()
    alias_root = tmp_path / "artifact-root-alias"
    try:
        os.symlink(real_root, alias_root, target_is_directory=True)
    except OSError as exc:
        raise AssertionError(f"directory symlink setup required for alias test: {exc}") from exc
    artifact = real_root / "brief.json"
    artifact.write_text('{"kind":"brief"}\n', encoding="utf-8")
    TEAM_STATUS_RUNTIME._validate_ref_file(
        {"path": str(artifact), "sha256": sha256(artifact)},
        "alias fixture",
        str(alias_root),
        required=True,
    )


def test_initial_status_respects_dependencies(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    result, output = render(fixture, Path(fixture["facts"]), "initial-status.json")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(output)
    assert snapshot["run_status"] == "ready-for-dispatch"
    assert statuses(snapshot) == {
        "core": "ready-for-dispatch",
        "cli": "ready-for-dispatch",
        "integrator": "waiting-dependency",
        "reviewer": "waiting-dependency",
    }


def test_failed_parent_run_renders_preparation_failed(tmp_path: Path) -> None:
    fixture = TEAM_RUN_TESTS.create_fixture(tmp_path)
    (Path(fixture["core"]) / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    run_root = Path(fixture["artifact_root"]) / "failed-status-run"
    prepared = TEAM_RUN_TESTS.run_prepare(fixture, run_root)
    assert prepared.returncode == 1
    facts = run_root / "status-facts.json"
    initialized = run_command(
        [
            sys.executable,
            str(TEAM_STATUS),
            "init-facts",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--out",
            str(facts),
        ],
        cwd=ROOT,
    )
    assert initialized.returncode == 0, initialized.stderr
    fixture["run_root"] = run_root
    result, output = render(fixture, facts, "failed-parent-status.json")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(output)
    assert snapshot["run_status"] == "preparation-failed"
    assert set(statuses(snapshot).values()) == {"preparation-failed"}


def test_bound_task_without_receipt_is_preflight(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    document, facts = copy_facts(fixture, "facts-bound.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "active",
    )
    write_json(facts, document)
    result, output = render(fixture, facts, "bound-status.json")
    assert result.returncode == 0, result.stderr
    assert statuses(read_json(output))["core"] == "preflight"


def test_passed_preflight_without_backbrief_requires_acknowledgement(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    document, facts = copy_facts(fixture, "facts-working.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "active",
    )
    write_json(facts, document)
    result, output = render(fixture, facts, "working-status.json")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(output)
    assert snapshot["run_status"] == "needs-input"
    assert statuses(snapshot)["core"] == "backbrief-required"


def test_passed_backbrief_and_current_progress_is_working(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    create_passed_backbrief(fixture, "core")
    document, facts = copy_facts(fixture, "facts-working-current.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "active",
    )
    set_current_progress(document, "core")
    write_json(facts, document)
    result, output = render(fixture, facts, "working-current-status.json")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(output)
    assert snapshot["run_status"] == "working"
    assert statuses(snapshot)["core"] == "working"


def test_stale_material_progress_requires_checkpoint_stop(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    create_passed_backbrief(fixture, "core")
    document, facts = copy_facts(fixture, "facts-stale-progress.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "active",
    )
    set_current_progress(document, "core")
    progress = lane_facts(document, "core")["progress"]
    progress["phase_started_at"] = "2026-08-24T10:00:00-04:00"
    progress["last_material_progress_at"] = "2026-08-24T10:00:00-04:00"
    document["observed_at"] = "2026-08-24T13:00:00-04:00"
    write_json(facts, document)
    result, output = render(fixture, facts, "stale-progress-status.json")
    assert result.returncode == 0, result.stderr
    assert statuses(read_json(output))["core"] == "checkpoint-required"


def test_failed_worker_receipt_blocks_lane(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    receipt = Path(fixture["run_root"]) / "worker-receipts" / "core.json"
    failed = TEAM_RUN_TESTS.run_worker_preflight(
        fixture,
        lane_id="core",
        cwd=Path(fixture["project"]),
        receipt=receipt,
    )
    assert failed.returncode == 1
    document, facts = copy_facts(fixture, "facts-failed-preflight.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "active",
    )
    write_json(facts, document)
    result, output = render(fixture, facts, "failed-preflight-status.json")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(output)
    assert snapshot["run_status"] == "blocked"
    assert statuses(snapshot)["core"] == "preflight-failed"


def test_failed_backbrief_receipt_blocks_lane_without_becoming_invalid_input(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    result, receipt = TEAM_RUN_TESTS.run_worker_backbrief(
        fixture,
        run_root=Path(fixture["run_root"]),
        lane_id="core",
        cwd=Path(fixture["core"]),
        tamper_requirement_ids=True,
    )
    assert result.returncode == 1
    assert read_json(receipt)["status"] == "failed"
    document, facts = copy_facts(fixture, "facts-failed-backbrief.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "active",
    )
    write_json(facts, document)
    rendered, output = render(fixture, facts, "failed-backbrief-status.json")
    assert rendered.returncode == 0, rendered.stderr
    snapshot = read_json(output)
    assert snapshot["run_status"] == "blocked"
    assert statuses(snapshot)["core"] == "backbrief-failed"


def test_completed_task_without_valid_evidence_needs_evidence(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    document, facts = copy_facts(fixture, "facts-needs-evidence.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "completed",
    )
    write_json(facts, document)
    result, output = render(fixture, facts, "needs-evidence-status.json")
    assert result.returncode == 0, result.stderr
    assert statuses(read_json(output))["core"] == "needs-evidence"


def test_valid_completed_report_is_handoff_ready(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    document, facts = copy_facts(fixture, "facts-handoff.json")
    bind_task(
        lane_facts(document, "core"),
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "completed",
    )
    attach_completed_artifacts(fixture, document, "core")
    write_json(facts, document)
    result, output = render(fixture, facts, "handoff-status.json")
    assert result.returncode == 0, result.stderr
    assert statuses(read_json(output))["core"] == "handoff-ready"


def test_completed_dirty_workspace_blocks_handoff(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    document, facts = copy_facts(fixture, "facts-dirty-handoff.json")
    item = lane_facts(document, "core")
    bind_task(
        item,
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "completed",
    )
    attach_completed_artifacts(fixture, document, "core")
    item["workspace"]["ordinary_status"] = ["?? uncommitted.txt"]
    item["workspace"]["observed_at"] = "2026-08-24T13:05:00-04:00"
    write_json(facts, document)
    result, output = render(fixture, facts, "dirty-handoff-status.json")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(output)
    core = next(lane for lane in snapshot["lanes"] if lane["lane_id"] == "core")
    assert core["status"] == "blocked"
    assert core["workspace"]["ordinary_status"] == ["?? uncommitted.txt"]


def test_report_from_another_run_is_rejected(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    create_passed_worker_receipt(fixture, "core")
    document, facts = copy_facts(fixture, "facts-cross-run-report.json")
    item = lane_facts(document, "core")
    bind_task(
        item,
        "core",
        fixture["manifest"]["task_project"]["project_id"],
        "completed",
    )
    other_run = Path(fixture["artifact_root"]) / "other-run"
    other_run.mkdir()
    report = other_run / "core.worker-report.json"
    evidence = other_run / "core.evidence.json"
    report.write_text('{"status":"completed"}\n', encoding="utf-8")
    evidence.write_text('{"result":"passed"}\n', encoding="utf-8")
    item["worker_report"] = {"status": "completed", "path": str(report), "sha256": sha256(report)}
    item["evidence"] = {"state": "valid", "path": str(evidence), "sha256": sha256(evidence)}
    write_json(facts, document)
    result, output = render(fixture, facts, "cross-run-report-status.json")
    assert result.returncode == 1
    assert "outside allowed root" in result.stderr.lower()
    assert not output.exists()


def test_accepted_dependencies_unlock_integrator_only(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    document, facts = copy_facts(fixture, "facts-accepted.json")
    project_id = fixture["manifest"]["task_project"]["project_id"]
    for lane_id in ("core", "cli"):
        create_passed_worker_receipt(fixture, lane_id)
        bind_task(lane_facts(document, lane_id), lane_id, project_id, "completed")
        attach_completed_artifacts(fixture, document, lane_id, accepted=True)
    lane_facts(document, "core")["archived"] = True
    write_json(facts, document)
    result, output = render(fixture, facts, "accepted-status.json")
    assert result.returncode == 0, result.stderr
    current = statuses(read_json(output))
    assert current["integrator"] == "waiting-checkpoint"
    assert current["reviewer"] == "waiting-dependency"

    document, accepted_facts = copy_facts(fixture, "facts-checkpoint-accepted.json")
    for lane_id in ("core", "cli"):
        bind_task(lane_facts(document, lane_id), lane_id, project_id, "completed")
        attach_completed_artifacts(fixture, document, lane_id, accepted=True)
    accept_checkpoint(fixture, document, "vertical-slice-accepted")
    write_json(accepted_facts, document)
    result, accepted_output = render(
        fixture, accepted_facts, "checkpoint-accepted-status.json"
    )
    assert result.returncode == 0, result.stderr
    assert statuses(read_json(accepted_output))["integrator"] == "ready-for-dispatch"


def test_unaccepted_archived_dependency_does_not_unlock(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    document, facts = copy_facts(fixture, "facts-unaccepted-archive.json")
    lane_facts(document, "core")["archived"] = True
    write_json(facts, document)
    result, output = render(fixture, facts, "unaccepted-archive-status.json")
    assert result.returncode == 0, result.stderr
    snapshot = read_json(output)
    integrator = next(lane for lane in snapshot["lanes"] if lane["lane_id"] == "integrator")
    assert integrator["status"] == "waiting-dependency"
    assert set(integrator["blocking_dependencies"]) == {"core", "cli"}


def test_review_changes_and_archive_have_higher_precedence(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    document, facts = copy_facts(fixture, "facts-review.json")
    create_passed_worker_receipt(fixture, "integrator")
    item = lane_facts(document, "integrator")
    bind_task(
        item,
        "integrator",
        fixture["manifest"]["task_project"]["project_id"],
        "completed",
    )
    attach_completed_artifacts(fixture, document, "integrator", accepted=True)
    item["integration_state"] = "integrated"
    item["review_state"] = "changes-requested"
    write_json(facts, document)
    result, output = render(fixture, facts, "review-status.json")
    assert result.returncode == 0, result.stderr
    assert statuses(read_json(output))["integrator"] == "changes-requested"

    archived = read_json(facts)
    lane_facts(archived, "integrator")["archived"] = True
    archived_path = Path(fixture["run_root"]) / "facts-archived.json"
    write_json(archived_path, archived)
    result, output = render(fixture, archived_path, "archived-status.json")
    assert result.returncode == 0, result.stderr
    assert statuses(read_json(output))["integrator"] == "archived"


def test_manifest_ref_mismatch_is_rejected(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    document, facts = copy_facts(fixture, "facts-mismatch.json")
    document["manifest_ref"]["sha256"] = "sha256:" + "0" * 64
    write_json(facts, document)
    result, output = render(fixture, facts, "mismatch-status.json")
    assert result.returncode == 1
    assert "manifest" in result.stderr.lower()
    assert not output.exists()


def test_inconsistent_integration_fact_is_rejected(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    document, facts = copy_facts(fixture, "facts-inconsistent-integration.json")
    lane_facts(document, "core")["integration_state"] = "pending"
    write_json(facts, document)
    result, output = render(fixture, facts, "inconsistent-integration-status.json")
    assert result.returncode == 1
    assert "integration" in result.stderr.lower() and "accepted" in result.stderr.lower()
    assert not output.exists()


def test_tampered_dispatch_binding_is_rejected(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    dispatch_path = Path(fixture["run_root"]) / "dispatch-bundle.json"
    dispatch = read_json(dispatch_path)
    dispatch["lanes"][0]["workspace"]["path"] = str(tmp_path / "wrong-workspace")
    write_json(dispatch_path, dispatch)
    result, output = render(fixture, Path(fixture["facts"]), "tampered-dispatch-status.json")
    assert result.returncode == 1
    assert "dispatch" in result.stderr.lower() and "manifest" in result.stderr.lower()
    assert not output.exists()


def test_tampered_reviewer_dispatch_argv_is_rejected(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    dispatch_path = Path(fixture["run_root"]) / "dispatch-bundle.json"
    dispatch = read_json(dispatch_path)
    reviewer = next(item for item in dispatch["lanes"] if item["role"] == "reviewer")
    reviewer["worker_preflight_argv"][-1] = str(
        (Path(fixture["run_root"]) / "historical-gate.json").resolve()
    )
    write_json(dispatch_path, dispatch)
    result, output = render(fixture, Path(fixture["facts"]), "tampered-reviewer-argv.json")
    assert result.returncode == 1
    assert "worker preflight argv changed" in result.stderr
    assert not output.exists()


def test_reviewer_receipt_gate_binding_is_revalidated(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    target = TEAM_RUN_TESTS.advance_integrator(fixture)
    gate_path = TEAM_RUN_TESTS.write_gate_receipt(
        fixture,
        Path(fixture["run_root"]),
        target,
    )
    receipt_path = Path(fixture["run_root"]) / "worker-receipts" / "reviewer.json"
    result = TEAM_RUN_TESTS.run_worker_preflight(
        fixture,
        lane_id="reviewer",
        cwd=Path(fixture["integrator"]),
        receipt=receipt_path,
        gate_receipt=gate_path,
    )
    assert result.returncode == 0, result.stderr
    rendered, output = render(fixture, Path(fixture["facts"]), "reviewer-bound.json")
    assert rendered.returncode == 0, rendered.stderr
    assert output.is_file()

    receipt = read_json(receipt_path)
    receipt["target"] = {
        "commit": fixture["manifest"]["base"]["commit"],
        "tree": fixture["manifest"]["base"]["tree"],
    }
    write_json(receipt_path, receipt)
    rendered, output = render(fixture, Path(fixture["facts"]), "reviewer-tampered.json")
    assert rendered.returncode == 1
    assert "reviewer Gate binding changed" in rendered.stderr
    assert not output.exists()


def test_facts_outside_run_directory_are_rejected(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    outside = tmp_path / "outside-facts.json"
    outside.write_bytes(Path(fixture["facts"]).read_bytes())
    result, output = render(fixture, outside, "outside-facts-status.json")
    assert result.returncode == 1
    assert "facts" in result.stderr.lower() and "run_dir" in result.stderr.lower()
    assert not output.exists()


def test_render_never_overwrites_snapshot(tmp_path: Path) -> None:
    fixture = create_status_fixture(tmp_path)
    result, output = render(fixture, Path(fixture["facts"]), "once-status.json")
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    second, _ = render(fixture, Path(fixture["facts"]), "once-status.json")
    assert second.returncode == 1
    assert output.read_bytes() == original


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoints_exist]
    tests_with_tmp = [
        test_ref_file_accepts_real_path_alias_within_allowed_root,
        test_initial_status_respects_dependencies,
        test_failed_parent_run_renders_preparation_failed,
        test_bound_task_without_receipt_is_preflight,
        test_passed_preflight_without_backbrief_requires_acknowledgement,
        test_passed_backbrief_and_current_progress_is_working,
        test_stale_material_progress_requires_checkpoint_stop,
        test_failed_worker_receipt_blocks_lane,
        test_failed_backbrief_receipt_blocks_lane_without_becoming_invalid_input,
        test_completed_task_without_valid_evidence_needs_evidence,
        test_valid_completed_report_is_handoff_ready,
        test_completed_dirty_workspace_blocks_handoff,
        test_report_from_another_run_is_rejected,
        test_accepted_dependencies_unlock_integrator_only,
        test_unaccepted_archived_dependency_does_not_unlock,
        test_review_changes_and_archive_have_higher_precedence,
        test_manifest_ref_mismatch_is_rejected,
        test_inconsistent_integration_fact_is_rejected,
        test_tampered_dispatch_binding_is_rejected,
        test_tampered_reviewer_dispatch_argv_is_rejected,
        test_reviewer_receipt_gate_binding_is_revalidated,
        test_facts_outside_run_directory_are_rejected,
        test_render_never_overwrites_snapshot,
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
