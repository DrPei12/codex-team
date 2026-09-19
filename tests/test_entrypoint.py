"""Current Team commands operate on portable state through one launcher."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ("team-plan", "team-run", "team-status", "team-integrate",
           "team-finish", "team-recover", "team-auto", "team-next")


def command(args, cwd):
    result = subprocess.run([sys.executable, "-B", *map(str, args)], cwd=cwd,
        env={**os.environ, "PYTHONUTF8": "1"}, capture_output=True,
        text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_source_has_one_skill_and_current_runtime():
    assert {p.parent.name for p in (ROOT/"skills").glob("*/SKILL.md")} == {"team"}
    assert {p.name for p in (ROOT/"team_runtime").glob("*.py")} == {
        "__init__.py", "__main__.py", "cli.py", "adaptive.py", "adaptive_runner.py",
        "codex.py", "coordination.py", "workspace_claims.py", "store.py",
        "policy.py", "redaction.py"}
    for name in RETIRED:
        assert not (ROOT/"scripts"/(name+".py")).exists()
    text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT/"skills/team").rglob("*.md"))
    for name in RETIRED:
        assert name not in text


def test_module_and_script_share_the_cli():
    script = command([ROOT/"scripts/team.py", "--help"], ROOT)
    module = command(["-m", "team_runtime", "--help"], ROOT)
    assert module == script
    assert "team-next" not in script


def test_relocated_bundle_registers_steers_and_continues_saved_context(tmp_path):
    plugin = tmp_path/"codex-team"
    command([ROOT/"scripts/build-team-plugin.py", "--out", plugin], tmp_path)
    cli = plugin/"skills/team/scripts/team.py"
    state, workspace = tmp_path/"state", tmp_path/"project with spaces"
    workspace.mkdir()
    definition, authority, plan = (tmp_path/name for name in ("definition.md", "authority.md", "plan.json"))
    definition.write_text("Compare release options with evidence.", encoding="utf-8")
    authority.write_text("Read the supplied documents and recommend an option.", encoding="utf-8")
    plan.write_text('[]', encoding="utf-8")
    base = [cli, "--state", state]
    def run(*args):
        return json.loads(command([*base, *args], tmp_path))
    created = run("create", "--workspace", workspace, "--definition-file", definition,
                 "--authority-file", authority, "--plan-file", plan, "--operation-id", "create")
    rid = created["run_id"]
    before = run("snapshot", rid)
    user_message = tmp_path/"message.md"
    user_message.write_text("Prioritize maintainability. 可检索的最新要求。", encoding="utf-8")
    first = run("message", rid, "--file", user_message, "--operation-id", "user-update")
    assert run("message", rid, "--file", user_message, "--operation-id", "user-update") == first
    changes = tmp_path/"changes.json"
    changes.write_text(json.dumps({"base_revision": before["data"]["plan_revision"], "reason": "Adopt user priority",
        "definition": "Compare release options, prioritizing maintainability.",
        "add": [{"id": "research", "title": "Research", "goal": "Read the supplied documents",
                 "acceptance": "Evidence supports the maintainability comparison"}]}), encoding="utf-8")
    run("revise", rid, "--changes-file", changes, "--operation-id", "revise")
    run("pause", rid)
    after = run("snapshot", rid)
    assert "maintainability" in after["definition_text"]
    assert after["data"]["plan_revision"] > before["data"]["plan_revision"]
    assert run("list")["runs"][0]["id"] == rid
    found = run("history", rid, "可检索的最新要求")
    assert "可检索的最新要求" in json.dumps(found, ensure_ascii=False)
    assert (state/"team.sqlite3").is_file()
    assert not list(workspace.iterdir())
