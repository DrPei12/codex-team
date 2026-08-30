from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEAM_FINISH = ROOT / "scripts" / "team-finish.py"
SCHEMA = ROOT / "schemas" / "team-finish-artifacts.schema.json"
SKILL = ROOT / "skills" / "team-finish" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "team-finish" / "agents" / "openai.yaml"


def load_support(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load test support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INTEGRATE_SUPPORT = load_support("team_integrate_test_support_finish", "tests/test_team_integrate.py")
RUN_SUPPORT = load_support("team_run_test_support_finish", "tests/test_team_run.py")


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def create_integrated_fixture(
    tmp_path: Path,
    *,
    lane_metadata: dict[str, dict[str, object]] | None = None,
) -> dict:
    fixture = INTEGRATE_SUPPORT.create_handoff_fixture(
        tmp_path,
        lane_metadata=lane_metadata,
    )
    for lane_id in ("core", "cli"):
        result, _ = INTEGRATE_SUPPORT.build_candidate(fixture, lane_id)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
    result, plan = INTEGRATE_SUPPORT.prepare_plan(fixture)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    apply_receipt = Path(fixture["run_root"]) / "integration-apply.json"
    applied = run_command(
        [
            sys.executable,
            str(INTEGRATE_SUPPORT.TEAM_INTEGRATE),
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
    )
    if applied.returncode != 0:
        raise AssertionError(applied.stderr)
    gate_receipt = Path(fixture["run_root"]) / "gate-receipt.json"
    gated = run_command(
        [
            sys.executable,
            str(INTEGRATE_SUPPORT.TEAM_INTEGRATE),
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
    if gated.returncode != 0:
        raise AssertionError(gated.stderr)
    fixture["integration_plan"] = plan
    fixture["apply_receipt"] = apply_receipt
    fixture["gate_receipt"] = gate_receipt
    return fixture


def record_review(
    fixture: dict,
    *,
    decision: str = "approved",
    findings: list[dict] | None = None,
    name: str = "review-receipt.json",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    findings_path = Path(fixture["run_root"]) / f"{name}.findings.json"
    write_json(findings_path, {"findings": findings or []})
    output = Path(fixture["run_root"]) / name
    result = run_command(
        [
            sys.executable,
            str(TEAM_FINISH),
            "review",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--gate-receipt",
            str(fixture["gate_receipt"]),
            "--reviewer-lane",
            "reviewer",
            "--decision",
            decision,
            "--findings",
            str(findings_path),
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def audit(fixture: dict, review: Path, name: str = "finish-audit.json") -> tuple[subprocess.CompletedProcess[str], Path]:
    output = Path(fixture["run_root"]) / name
    result = run_command(
        [
            sys.executable,
            str(TEAM_FINISH),
            "audit",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--gate-receipt",
            str(fixture["gate_receipt"]),
            "--review-receipt",
            str(review),
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def finalize(
    fixture: dict,
    review: Path,
    audit_path: Path,
    name: str = "milestone-result.json",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = Path(fixture["run_root"]) / name
    result = run_command(
        [
            sys.executable,
            str(TEAM_FINISH),
            "finalize",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--gate-receipt",
            str(fixture["gate_receipt"]),
            "--review-receipt",
            str(review),
            "--audit",
            str(audit_path),
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def test_entrypoints_exist() -> None:
    assert TEAM_FINISH.is_file()
    assert SCHEMA.is_file()
    assert SKILL.is_file()
    assert OPENAI_YAML.is_file()


def test_review_receipt_binds_exact_gate_target(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, output = record_review(fixture)
    assert result.returncode == 0, result.stderr
    review = read_json(output)
    assert review["decision"] == "approved"
    assert review["target"] == read_json(Path(fixture["gate_receipt"]))["target"]
    assert review["finding_count"] == 0


def test_changes_requested_blocks_audit(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(
        fixture,
        decision="changes-requested",
        findings=[{"id": "R-001", "severity": "high", "summary": "fix required"}],
    )
    assert result.returncode == 0, result.stderr
    result, output = audit(fixture, review)
    assert result.returncode == 1
    document = read_json(output)
    assert document["status"] == "blocked"
    assert any("review" in error.lower() for error in document["errors"])


def test_audit_rejects_findings_changed_after_review(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    review_document = read_json(review)
    findings = Path(review_document["findings_ref"]["path"])
    findings.write_text('{"findings":[{"id":"late"}]}\n', encoding="utf-8")
    result, output = audit(fixture, review)
    assert result.returncode == 1
    assert "findings" in result.stderr.lower() and "hash" in result.stderr.lower()
    assert not output.exists()


def test_audit_records_ignored_residue_without_blocking(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    ignored = Path(fixture["integrator"]) / "cache.pyc"
    ignored.write_bytes(b"ignored")
    result, output = audit(fixture, review)
    assert result.returncode == 0, result.stderr
    document = read_json(output)
    assert document["status"] == "ready-to-finish"
    assert document["cleanliness"]["ordinary_status"] == []
    assert document["cleanliness"]["ignored_files"] == ["cache.pyc"]
    assert document["cleanliness"]["residue_free_checkout"] is False
    assert ignored.exists()


def test_audit_blocks_ordinary_dirty_workspace(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    (Path(fixture["integrator"]) / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    result, output = audit(fixture, review)
    assert result.returncode == 1
    document = read_json(output)
    assert document["status"] == "blocked"
    assert document["cleanliness"]["ordinary_status"]


def test_audit_blocks_git_operation_residue(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    integrator = Path(fixture["integrator"])
    git_dir_raw = RUN_SUPPORT.git(integrator, "rev-parse", "--git-dir")
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = integrator / git_dir
    (git_dir / "MERGE_HEAD").write_text(fixture["manifest"]["base"]["commit"] + "\n", encoding="ascii")
    result, output = audit(fixture, review)
    assert result.returncode == 1
    document = read_json(output)
    assert "MERGE_HEAD" in document["cleanliness"]["operation_residue"]


def test_finalize_requires_approved_review(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture, decision="changes-requested", findings=[{"id": "R-1"}])
    assert result.returncode == 0, result.stderr
    result, audit_path = audit(fixture, review)
    assert result.returncode == 1
    result, output = finalize(fixture, review, audit_path)
    assert result.returncode == 1
    assert "approved" in result.stderr.lower() or "ready-to-finish" in result.stderr.lower()
    assert not output.exists()


def test_finalize_reports_ignored_residue_and_no_cleanup(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    ignored = Path(fixture["integrator"]) / "cache.pyc"
    ignored.write_bytes(b"ignored")
    result, audit_path = audit(fixture, review)
    assert result.returncode == 0, result.stderr
    result, output = finalize(fixture, review, audit_path)
    assert result.returncode == 0, result.stderr
    milestone = read_json(output)
    assert milestone["status"] == "completed-with-ignored-residue"
    assert milestone["cleanup_performed"] is False
    assert all(item["authorized"] is False for item in milestone["workspace_actions"])
    assert milestone["archive_candidates"] == [
        lane["lane_id"] for lane in fixture["manifest"]["lanes"]
    ]
    assert all(
        item["recommended_action"] == "archive" and item["authorized"] is False
        for item in milestone["task_dispositions"]
    )
    assert [item["task_title"] for item in milestone["task_dispositions"]] == [
        lane["task_title"] for lane in fixture["manifest"]["lanes"]
    ]
    assert ignored.exists()


def test_finalize_rejects_workspace_change_after_audit(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    result, audit_path = audit(fixture, review)
    assert result.returncode == 0, result.stderr
    (Path(fixture["integrator"]) / "late.txt").write_text("late\n", encoding="utf-8")
    result, output = finalize(fixture, review, audit_path)
    assert result.returncode == 1
    assert "changed after audit" in result.stderr.lower()
    assert not output.exists()


def test_finalize_task_dispositions_respect_surface_and_lifecycle(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(
        tmp_path,
        lane_metadata={
            "core": {"lifecycle": "long-lived-owner"},
            "reviewer": {
                "execution_surface": "internal-subagent",
                "task_title": None,
                "lifecycle": "one-shot",
            },
        },
    )
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    result, audit_path = audit(fixture, review)
    assert result.returncode == 0, result.stderr
    result, output = finalize(fixture, review, audit_path)
    assert result.returncode == 0, result.stderr
    milestone = read_json(output)
    dispositions = {item["lane_id"]: item for item in milestone["task_dispositions"]}
    assert dispositions["core"]["recommended_action"] == "retain"
    assert dispositions["reviewer"]["recommended_action"] == "not-applicable"
    assert dispositions["cli"]["recommended_action"] == "archive"
    assert dispositions["integrator"]["recommended_action"] == "archive"
    assert milestone["archive_candidates"] == ["cli", "integrator"]
    assert all(item["authorized"] is False for item in milestone["task_dispositions"])


def test_finalize_never_overwrites_result(tmp_path: Path) -> None:
    fixture = create_integrated_fixture(tmp_path)
    result, review = record_review(fixture)
    assert result.returncode == 0, result.stderr
    result, audit_path = audit(fixture, review)
    assert result.returncode == 0, result.stderr
    result, output = finalize(fixture, review, audit_path)
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    second, _ = finalize(fixture, review, audit_path)
    assert second.returncode == 1
    assert output.read_bytes() == original


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoints_exist]
    tests_with_tmp = [
        test_review_receipt_binds_exact_gate_target,
        test_changes_requested_blocks_audit,
        test_audit_rejects_findings_changed_after_review,
        test_audit_records_ignored_residue_without_blocking,
        test_audit_blocks_ordinary_dirty_workspace,
        test_audit_blocks_git_operation_residue,
        test_finalize_requires_approved_review,
        test_finalize_reports_ignored_residue_and_no_cleanup,
        test_finalize_rejects_workspace_change_after_audit,
        test_finalize_task_dispositions_respect_surface_and_lifecycle,
        test_finalize_never_overwrites_result,
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
