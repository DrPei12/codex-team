from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build-team-plugin.py"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_NAME = "codex-team"
SKILLS = {"team"}


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
    assert "plugins/codex-team/" not in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_build_creates_valid_relocatable_layout(tmp_path: Path) -> None:
    result, plugin = build_plugin(tmp_path)
    assert result.returncode == 0, result.stderr
    manifest = read_json(plugin / ".codex-plugin" / "plugin.json")
    assert manifest["name"] == PLUGIN_NAME
    assert manifest["version"] == "2.1.0"
    for field in ("composerIcon", "logo", "logoDark"):
        assert manifest["interface"][field] == "./assets/codex-team.png"
    assert (plugin / "assets/codex-team.png").read_bytes() == (ROOT / "assets/codex-team.png").read_bytes()
    assert (plugin / "assets/codex-team.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert manifest["skills"] == "./skills/"
    assert {path.name for path in (plugin / "skills").iterdir() if path.is_dir()} == SKILLS
    runtime = plugin / "skills" / "team" / "scripts"
    assert {path.name for path in runtime.glob("team*.py")} == {"team.py"}
    source_runtime = ROOT / "team_runtime"
    expected_runtime = {
        path.relative_to(source_runtime).as_posix(): path.read_bytes()
        for path in source_runtime.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and path.suffix == ".py"
    }
    assert file_bytes(runtime / "team_runtime") == expected_runtime
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
    target = plugin / "skills" / "team" / "references" / "runtime.md"
    target.write_text(target.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")
    tampered = run_command([sys.executable, "-B", str(self_check)], cwd=tmp_path)
    assert tampered.returncode == 1
    assert "hash mismatch" in tampered.stderr.lower()
