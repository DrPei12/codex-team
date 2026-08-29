from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build-team-plugin.py"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_NAME = "codex-team"
SKILLS = {
    "team",
    "team-plan",
    "team-run",
    "team-status",
    "team-integrate",
    "team-finish",
    "team-recover",
}


def load_support(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load test support: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN_SUPPORT = load_support("team_run_test_support_plugin", "tests/test_team_run.py")
INTEGRATE_SUPPORT = load_support("team_integrate_test_support_plugin", "tests/test_team_integrate.py")
RECOVER_SUPPORT = load_support("team_recover_test_support_plugin", "tests/test_team_recover.py")


def run_command(args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_plugin(parent: Path, bucket: str = "build") -> tuple[subprocess.CompletedProcess[str], Path]:
    output = parent / bucket / PLUGIN_NAME
    output.parent.mkdir(parents=True)
    result = run_command(
        [sys.executable, "-B", str(BUILDER), "--out", str(output)],
    )
    return result, output


def file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def runtime(plugin: Path, name: str) -> Path:
    return plugin / "skills" / "team" / "scripts" / name


def test_entrypoint_exists() -> None:
    assert BUILDER.is_file()


def test_repo_marketplace_contract() -> None:
    marketplace = read_json(MARKETPLACE)
    assert marketplace["name"] == "codex-team-local"
    assert marketplace["interface"]["displayName"] == "Codex Team Local"
    assert marketplace["plugins"] == [
        {
            "category": "Productivity",
            "name": PLUGIN_NAME,
            "policy": {"authentication": "ON_INSTALL", "installation": "AVAILABLE"},
            "source": {"path": "./plugins/codex-team", "source": "local"},
        }
    ]
    assert "plugins/codex-team/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_build_creates_valid_relocatable_layout(tmp_path: Path) -> None:
    result, plugin = build_plugin(tmp_path)
    assert result.returncode == 0, result.stderr
    manifest = read_json(plugin / ".codex-plugin" / "plugin.json")
    assert manifest["name"] == PLUGIN_NAME
    assert manifest["version"] == "0.1.1"
    assert manifest["skills"] == "./skills/"
    assert {path.name for path in (plugin / "skills").iterdir() if path.is_dir()} == SKILLS
    runtime = plugin / "skills" / "team" / "scripts"
    assert {path.name for path in runtime.glob("team*.py")} == {
        "team.py",
        "team-plan.py",
        "team-run.py",
        "team-status.py",
        "team-integrate.py",
        "team-finish.py",
        "team-recover.py",
    }
    packaged_text = "\n".join(path.read_text(encoding="utf-8") for path in plugin.rglob("*.md"))
    assert "<TEAM_SKILL_DIR>" in packaged_text
    assert "python scripts/team" not in packaged_text
    assert "tests/test_team" not in packaged_text
    assert "`schemas/team-" not in packaged_text
    assert str(ROOT) not in packaged_text


def test_build_is_byte_deterministic(tmp_path: Path) -> None:
    first_result, first = build_plugin(tmp_path, "first")
    second_result, second = build_plugin(tmp_path, "second")
    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert file_bytes(first) == file_bytes(second)


def test_builder_rejects_wrong_name_and_existing_output(tmp_path: Path) -> None:
    wrong = tmp_path / "wrong-name"
    result = run_command([sys.executable, "-B", str(BUILDER), "--out", str(wrong)])
    assert result.returncode == 1
    assert "codex-team" in result.stderr.lower()
    assert not wrong.exists()
    result, plugin = build_plugin(tmp_path)
    assert result.returncode == 0, result.stderr
    original = file_bytes(plugin)
    second = run_command([sys.executable, "-B", str(BUILDER), "--out", str(plugin)])
    assert second.returncode == 1
    assert file_bytes(plugin) == original


def test_bundle_self_check_detects_tampering(tmp_path: Path) -> None:
    result, plugin = build_plugin(tmp_path)
    assert result.returncode == 0, result.stderr
    self_check = plugin / "skills" / "team" / "scripts" / "bundle-self-check.py"
    clean = run_command([sys.executable, "-B", str(self_check)], cwd=tmp_path)
    assert clean.returncode == 0, clean.stderr
    target = plugin / "skills" / "team-plan" / "references" / "manifest-fields.md"
    target.write_text(target.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")
    tampered = run_command([sys.executable, "-B", str(self_check)], cwd=tmp_path)
    assert tampered.returncode == 1
    assert "hash mismatch" in tampered.stderr.lower()


def test_packaged_runtime_runs_outside_source_repo(tmp_path: Path) -> None:
    result, plugin = build_plugin(tmp_path)
    assert result.returncode == 0, result.stderr
    fixture = RUN_SUPPORT.create_fixture(tmp_path / "fixture")
    runtime = plugin / "skills" / "team" / "scripts"
    validated = run_command(
        [sys.executable, "-B", str(runtime / "team-plan.py"), "validate", str(fixture["manifest_path"])],
        cwd=tmp_path,
    )
    assert validated.returncode == 0, validated.stderr
    run_root = Path(fixture["artifact_root"]) / "plugin-run"
    prepared = run_command(
        [
            sys.executable,
            "-B",
            str(runtime / "team-run.py"),
            "prepare",
            str(fixture["manifest_path"]),
            "--briefs",
            str(fixture["briefs"]),
            "--out",
            str(run_root),
        ],
        cwd=tmp_path,
    )
    assert prepared.returncode == 0, prepared.stderr
    facts = run_root / "status-facts.json"
    initialized = run_command(
        [
            sys.executable,
            "-B",
            str(runtime / "team-status.py"),
            "init-facts",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
            "--out",
            str(facts),
        ],
        cwd=tmp_path,
    )
    assert initialized.returncode == 0, initialized.stderr
    routed = run_command(
        [
            sys.executable,
            "-B",
            str(runtime / "team.py"),
            "route",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(run_root),
        ],
        cwd=tmp_path,
    )
    assert routed.returncode == 0, routed.stderr
    assert json.loads(routed.stdout)["next_action"] == "render-status"


def test_packaged_integrate_and_finish_runtime(tmp_path: Path) -> None:
    result, plugin = build_plugin(tmp_path)
    assert result.returncode == 0, result.stderr
    fixture = INTEGRATE_SUPPORT.create_handoff_fixture(
        tmp_path / "fixture",
        team_run_path=runtime(plugin, "team-run.py"),
        team_status_path=runtime(plugin, "team-status.py"),
    )
    facts = read_json(Path(fixture["integration_facts"]))
    for lane_id in ("core", "cli"):
        item = INTEGRATE_SUPPORT.STATUS_SUPPORT.lane_facts(facts, lane_id)
        candidate = Path(fixture["candidates"]) / f"{lane_id}.json"
        created = run_command(
            [
                sys.executable,
                "-B",
                str(runtime(plugin, "team-integrate.py")),
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
                str(candidate),
            ],
            cwd=tmp_path,
        )
        assert created.returncode == 0, created.stderr
    plan = Path(fixture["run_root"]) / "integration-plan.json"
    prepared = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-integrate.py")),
            "prepare",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--status",
            str(fixture["status_snapshot"]),
            "--candidates",
            str(fixture["candidates"]),
            "--out",
            str(plan),
        ],
        cwd=tmp_path,
    )
    assert prepared.returncode == 0, prepared.stderr
    apply_receipt = Path(fixture["run_root"]) / "integration-apply.json"
    applied = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-integrate.py")),
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
        cwd=tmp_path,
    )
    assert applied.returncode == 0, applied.stderr
    gate_receipt = Path(fixture["run_root"]) / "gate-receipt.json"
    gated = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-integrate.py")),
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
        cwd=tmp_path,
    )
    assert gated.returncode == 0, gated.stderr
    reviewer_receipt = Path(fixture["run_root"]) / "worker-receipts" / "reviewer.json"
    reviewer_preflight = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-run.py")),
            "worker-preflight",
            str(fixture["manifest_path"]),
            "--brief",
            str(Path(fixture["briefs"]) / "reviewer.task-brief.json"),
            "--receipt",
            str(reviewer_receipt),
            "--gate-receipt",
            str(gate_receipt),
        ],
        cwd=Path(fixture["integrator"]),
    )
    assert reviewer_preflight.returncode == 0, reviewer_preflight.stderr
    reviewer_document = read_json(reviewer_receipt)
    assert reviewer_document["status"] == "passed"
    assert reviewer_document["target"] == read_json(gate_receipt)["target"]
    findings = Path(fixture["run_root"]) / "review-findings.json"
    findings.write_text('{"findings": []}\n', encoding="utf-8")
    review = Path(fixture["run_root"]) / "review-receipt.json"
    reviewed = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-finish.py")),
            "review",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--gate-receipt",
            str(gate_receipt),
            "--reviewer-lane",
            "reviewer",
            "--decision",
            "approved",
            "--findings",
            str(findings),
            "--out",
            str(review),
        ],
        cwd=tmp_path,
    )
    assert reviewed.returncode == 0, reviewed.stderr
    audit = Path(fixture["run_root"]) / "finish-audit.json"
    audited = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-finish.py")),
            "audit",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--gate-receipt",
            str(gate_receipt),
            "--review-receipt",
            str(review),
            "--out",
            str(audit),
        ],
        cwd=tmp_path,
    )
    assert audited.returncode == 0, audited.stderr
    milestone = Path(fixture["run_root"]) / "milestone-result.json"
    finalized = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-finish.py")),
            "finalize",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--gate-receipt",
            str(gate_receipt),
            "--review-receipt",
            str(review),
            "--audit",
            str(audit),
            "--out",
            str(milestone),
        ],
        cwd=tmp_path,
    )
    assert finalized.returncode == 0, finalized.stderr
    assert read_json(milestone)["status"] == "completed"


def test_packaged_recovery_runtime(tmp_path: Path) -> None:
    result, plugin = build_plugin(tmp_path)
    assert result.returncode == 0, result.stderr
    fixture = RECOVER_SUPPORT.create_blocked_fixture(tmp_path / "fixture")
    candidate = Path(fixture["run_root"]) / "recovery-candidate.json"
    frozen = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-recover.py")),
            "candidate",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--lane",
            "core",
            "--mode",
            "dirty",
            "--out",
            str(candidate),
        ],
        cwd=tmp_path,
    )
    assert frozen.returncode == 0, frozen.stderr
    plan = Path(fixture["run_root"]) / "recovery-plan.json"
    prepared = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-recover.py")),
            "prepare",
            str(fixture["manifest_path"]),
            "--run-dir",
            str(fixture["run_root"]),
            "--predecessor",
            str(fixture["predecessor"]),
            "--candidate",
            str(candidate),
            "--proofs",
            str(fixture["proofs"]),
            "--new-fact",
            "Verify the corrected parent precondition.",
            "--command",
            "python -m unittest",
            "--allow-path",
            "src/core.py",
            "--max-commands",
            "1",
            "--out",
            str(plan),
        ],
        cwd=tmp_path,
    )
    assert prepared.returncode == 0, prepared.stderr
    brief = Path(fixture["run_root"]) / "recovery-brief.json"
    projected = run_command(
        [
            sys.executable,
            "-B",
            str(runtime(plugin, "team-recover.py")),
            "project",
            str(plan),
            "--out",
            str(brief),
        ],
        cwd=tmp_path,
    )
    assert projected.returncode == 0, projected.stderr
    assert read_json(brief)["task_creation_authorized"] is False


def main() -> int:
    failures = 0
    tests_without_tmp = [test_entrypoint_exists, test_repo_marketplace_contract]
    tests_with_tmp = [
        test_build_creates_valid_relocatable_layout,
        test_build_is_byte_deterministic,
        test_builder_rejects_wrong_name_and_existing_output,
        test_bundle_self_check_detects_tampering,
        test_packaged_runtime_runs_outside_source_repo,
        test_packaged_integrate_and_finish_runtime,
        test_packaged_recovery_runtime,
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
