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
TEAM_RECOVER = ROOT / "scripts" / "team-recover.py"
SCHEMA = ROOT / "schemas" / "team-recover-artifacts.schema.json"
SKILL = ROOT / "skills" / "team-recover" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "team-recover" / "agents" / "openai.yaml"


def load_support(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load test support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN_SUPPORT = load_support("team_run_test_support_recover", "tests/test_team_run.py")


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def create_blocked_fixture(tmp_path: Path) -> dict:
    fixture = RUN_SUPPORT.create_fixture(tmp_path)
    (Path(fixture["core"]) / "src").mkdir()
    (Path(fixture["core"]) / "src/core.py").write_text("candidate = True\n", encoding="utf-8")
    run_root = Path(fixture["artifact_root"]) / "blocked-run"
    prepared = RUN_SUPPORT.run_prepare(fixture, run_root)
    assert prepared.returncode == 1
    fixture["run_root"] = run_root
    fixture["predecessor"] = run_root / "parent-preflight-receipt.json"
    proofs = run_root / "proofs"
    proofs.mkdir()
    shutil.copy2(run_root / "preregistration.json", proofs / "preregistration.json")
    fixture["proofs"] = proofs
    return fixture


def create_candidate(
    fixture: dict,
    *,
    mode: str,
    name: str = "recovery-candidate.json",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = Path(fixture["run_root"]) / name
    result = run_command(
        [
            sys.executable,
            str(TEAM_RECOVER),
            "candidate",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--lane",
            "core",
            "--mode",
            mode,
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def prepare_recovery(
    fixture: dict,
    candidate: Path,
    *,
    predecessor: Path | None = None,
    name: str = "recovery-plan.json",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = Path(fixture["run_root"]) / name
    result = run_command(
        [
            sys.executable,
            str(TEAM_RECOVER),
            "prepare",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--predecessor",
            str(predecessor or fixture["predecessor"]),
            "--candidate",
            str(candidate),
            "--proofs",
            str(fixture["proofs"]),
            "--new-fact",
            "Verify the frozen candidate against the corrected root precondition.",
            "--command",
            "python -m unittest",
            "--allow-path",
            "src/core.py",
            "--max-commands",
            "2",
            "--out",
            str(output),
        ],
        cwd=ROOT,
    )
    return result, output


def test_entrypoints_exist() -> None:
    assert TEAM_RECOVER.is_file()
    assert SCHEMA.is_file()
    assert SKILL.is_file()
    assert OPENAI_YAML.is_file()


def test_dirty_candidate_freezes_patch_and_snapshot(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    result, output = create_candidate(fixture, mode="dirty")
    assert result.returncode == 0, result.stderr
    candidate = read_json(output)
    assert candidate["mode"] == "dirty-files"
    assert candidate["changed_files"] == ["src/core.py"]
    assert Path(candidate["patch_ref"]["path"]).is_file()
    assert Path(candidate["snapshot_ref"]["path"]).is_file()


def test_commit_candidate_requires_clean_descendant(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    core = Path(fixture["core"])
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: freeze recovery candidate")
    result, output = create_candidate(fixture, mode="commit")
    assert result.returncode == 0, result.stderr
    candidate = read_json(output)
    assert candidate["mode"] == "git-commit"
    assert candidate["commit"] == RUN_SUPPORT.git(core, "rev-parse", "HEAD")
    assert candidate["tree"] == RUN_SUPPORT.git(core, "rev-parse", "HEAD^{tree}")


def test_dirty_candidate_rejects_unowned_paths_without_partial_artifacts(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    manifest = read_json(Path(fixture["manifest_path"]))
    core_lane = next(lane for lane in manifest["lanes"] if lane["lane_id"] == "core")
    core_lane["ownership"]["write_paths"] = ["owned/**"]
    write_json(Path(fixture["manifest_path"]), manifest)
    result, output = create_candidate(fixture, mode="dirty", name="unowned-candidate.json")
    assert result.returncode == 1
    assert "ownership" in result.stderr.lower()
    assert not output.exists()
    assert not output.with_suffix(".patch").exists()
    assert not output.with_suffix(".zip").exists()


def test_prepare_binds_predecessor_candidate_proofs_and_budget(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    core = Path(fixture["core"])
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: freeze recovery candidate")
    result, candidate = create_candidate(fixture, mode="commit")
    assert result.returncode == 0, result.stderr
    result, output = prepare_recovery(fixture, candidate)
    assert result.returncode == 0, result.stderr
    plan = read_json(output)
    assert plan["status"] == "prepared-not-dispatched"
    assert plan["predecessor"]["status"] == "failed"
    assert plan["candidate_ref"]["path"] == str(candidate.resolve())
    assert len(plan["reused_proofs"]) == 1
    assert plan["new_fact"].startswith("Verify the frozen candidate")
    assert plan["budget"] == {"max_commands": 2, "commands_used": 0}
    assert plan["authorization"] == {"command_execution": False, "task_creation": False, "workspace_mutation": False}


def test_prepare_rejects_nonblocked_predecessor(tmp_path: Path) -> None:
    fixture = RUN_SUPPORT.create_fixture(tmp_path)
    run_root = Path(fixture["artifact_root"]) / "passed-run"
    assert RUN_SUPPORT.run_prepare(fixture, run_root).returncode == 0
    fixture["run_root"] = run_root
    fixture["predecessor"] = run_root / "parent-preflight-receipt.json"
    fixture["proofs"] = run_root / "proofs"
    fixture["proofs"].mkdir()
    shutil.copy2(run_root / "preregistration.json", fixture["proofs"] / "preregistration.json")
    core = Path(fixture["core"])
    (core / "src").mkdir()
    (core / "src/core.py").write_text("candidate = True\n", encoding="utf-8")
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: candidate")
    result, candidate = create_candidate(fixture, mode="commit")
    assert result.returncode == 0, result.stderr
    result, output = prepare_recovery(fixture, candidate)
    assert result.returncode == 1
    assert "blocked" in result.stderr.lower() or "failed" in result.stderr.lower()
    assert not output.exists()


def test_prepare_rejects_proof_with_wrong_manifest(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    core = Path(fixture["core"])
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: candidate")
    result, candidate = create_candidate(fixture, mode="commit")
    assert result.returncode == 0, result.stderr
    proof = read_json(Path(fixture["proofs"]) / "preregistration.json")
    proof["manifest_ref"]["sha256"] = "sha256:" + "0" * 64
    write_json(Path(fixture["proofs"]) / "preregistration.json", proof)
    result, output = prepare_recovery(fixture, candidate)
    assert result.returncode == 1
    assert "proof" in result.stderr.lower() and "manifest" in result.stderr.lower()
    assert not output.exists()


def test_project_creates_bound_recovery_brief_without_dispatch(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    core = Path(fixture["core"])
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: candidate")
    result, candidate = create_candidate(fixture, mode="commit")
    assert result.returncode == 0, result.stderr
    result, plan = prepare_recovery(fixture, candidate)
    assert result.returncode == 0, result.stderr
    brief = Path(fixture["run_root"]) / "recovery-brief.json"
    result = run_command(
        [
            sys.executable,
            str(TEAM_RECOVER),
            "project",
            str(plan),
            "--out",
            str(brief),
        ],
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    document = read_json(brief)
    assert document["kind"] == "recovery-brief"
    assert document["plan_ref"]["path"] == str(plan.resolve())
    assert document["task_creation_authorized"] is False
    assert "thread_id" not in json.dumps(document).lower()


def test_project_never_overwrites_brief(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    core = Path(fixture["core"])
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: candidate")
    candidate = create_candidate(fixture, mode="commit")[1]
    plan = prepare_recovery(fixture, candidate)[1]
    brief = Path(fixture["run_root"]) / "recovery-brief.json"
    command = [sys.executable, str(TEAM_RECOVER), "project", str(plan), "--out", str(brief)]
    first = run_command(command, cwd=ROOT)
    assert first.returncode == 0, first.stderr
    original = brief.read_bytes()
    second = run_command(command, cwd=ROOT)
    assert second.returncode == 1
    assert brief.read_bytes() == original


def test_project_rejects_candidate_replaced_after_plan(tmp_path: Path) -> None:
    fixture = create_blocked_fixture(tmp_path)
    core = Path(fixture["core"])
    RUN_SUPPORT.git(core, "add", "src/core.py")
    RUN_SUPPORT.git(core, "commit", "-m", "fix: candidate")
    result, candidate = create_candidate(fixture, mode="commit")
    assert result.returncode == 0, result.stderr
    result, plan = prepare_recovery(fixture, candidate)
    assert result.returncode == 0, result.stderr
    document = read_json(candidate)
    document["created_at"] = "2026-08-25T00:00:00Z"
    write_json(candidate, document)
    brief = Path(fixture["run_root"]) / "tampered-brief.json"
    result = run_command(
        [sys.executable, str(TEAM_RECOVER), "project", str(plan), "--out", str(brief)],
        cwd=ROOT,
    )
    assert result.returncode == 1
    assert "candidate" in result.stderr.lower() and "hash" in result.stderr.lower()
    assert not brief.exists()


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoints_exist]
    tests_with_tmp = [
        test_dirty_candidate_freezes_patch_and_snapshot,
        test_commit_candidate_requires_clean_descendant,
        test_dirty_candidate_rejects_unowned_paths_without_partial_artifacts,
        test_prepare_binds_predecessor_candidate_proofs_and_budget,
        test_prepare_rejects_nonblocked_predecessor,
        test_prepare_rejects_proof_with_wrong_manifest,
        test_project_creates_bound_recovery_brief_without_dispatch,
        test_project_never_overwrites_brief,
        test_project_rejects_candidate_replaced_after_plan,
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
