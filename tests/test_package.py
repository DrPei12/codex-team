"""Portable Team package checks; no model calls, authentication, or installation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TeamPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="team-package-")
        self.addCleanup(self.temporary.cleanup)
        self.external = Path(self.temporary.name)

    def command(self, *args, cwd=None):
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "-B", *map(str, args)],
            cwd=cwd or self.external, env=environment,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, check=False,
        )

    def build(self):
        plugin = self.external / "codex-team"
        result = self.command(ROOT / "scripts/build-team-plugin.py", "--out", plugin)
        self.assertEqual(result.returncode, 0, result.stderr)
        return plugin

    def test_source_wrapper_ignores_working_directory(self):
        result = self.command(ROOT / "scripts/team.py", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("create", result.stdout)
        self.assertIn("reconcile", result.stdout)

    def test_moved_bundle_imports_current_runtime_and_cli(self):
        plugin = self.build()
        destination = self.external / "moved folder"
        destination.mkdir()
        moved = destination / "codex-team"
        shutil.move(str(plugin), str(moved))
        runtime = moved / "skills/team/scripts"
        # -I excludes cwd, PYTHONPATH, and user site-packages; only the packaged
        # runtime is explicitly added. Import and schema assertions do not run Codex.
        probe = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0,sys.argv[1]); "
            "import team_runtime, team_runtime.cli; "
            "from team_runtime.adaptive import Adaptive; "
            "from team_runtime.policy import validate_policy; "
            "assert validate_policy({})['max_subagents_per_session']==0; "
            "assert Path(team_runtime.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve()); "
            "print('portable-import-ok')"
        )
        imported = self.command("-I", "-c", probe, runtime)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertIn("portable-import-ok", imported.stdout)
        help_result = self.command(runtime / "team.py", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        checked = self.command(runtime / "bundle-self-check.py")
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_icon_tamper_and_extra_file_are_rejected(self):
        plugin = self.build()
        runtime = plugin / "skills/team/scripts"
        icon = plugin / "assets/codex-team.png"
        original = icon.read_bytes()
        icon.write_bytes(original + b"altered")
        checked = self.command(runtime / "bundle-self-check.py")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("hash mismatch", checked.stderr)
        icon.write_bytes(original)
        (plugin / "assets/unlisted.txt").write_text("unexpected", encoding="utf-8")
        checked = self.command(runtime / "bundle-self-check.py")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("inventory mismatch", checked.stderr)

    def test_removed_web_entrypoints_are_unavailable_in_source_and_bundle(self):
        plugin = self.build()
        roots = [ROOT, plugin / "skills/team"]
        for base in roots:
            for entry in ("team.py",):
                with self.subTest(root=str(base), entry=entry):
                    help_result = self.command(base / "scripts" / entry, "--help")
                    self.assertEqual(help_result.returncode, 0, help_result.stderr)
                    self.assertNotIn("serve", help_result.stdout)
                    state = self.external / (base.name + entry + "-rejected-state")
                    result = self.command(base / "scripts" / entry, "--state", state, "serve")
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("invalid choice", result.stderr)
                    self.assertFalse(state.exists())
        package = plugin / "skills/team/scripts/team_runtime"
        self.assertFalse((package / "board.py").exists())
        self.assertFalse((package / "adaptive_board.py").exists())
        self.assertFalse((package / "static").exists())

    def test_manifest_paths_cannot_escape_bundle(self):
        plugin = self.build()
        manifest = plugin / "skills/team/references/bundle-manifest.json"
        original = json.loads(manifest.read_text(encoding="utf-8"))
        for unsafe in ("../outside.txt", "C:/outside.txt", "C:\\outside.txt",
                       "skills/../../outside.txt", "/outside.txt", "./skills/x", "skills//x"):
            with self.subTest(path=unsafe):
                altered = dict(original)
                altered["files"] = {unsafe: "sha256:" + "0" * 64}
                manifest.write_text(json.dumps(altered), encoding="utf-8")
                checked = self.command(plugin / "skills/team/scripts/bundle-self-check.py")
                self.assertNotEqual(checked.returncode, 0)
                self.assertIn("unsafe bundle path", checked.stderr)

    def test_missing_runtime_does_not_fall_back_to_external_package(self):
        script = self.external / "isolated/team.py"
        script.parent.mkdir()
        shutil.copyfile(ROOT / "scripts/team.py", script)
        result = self.command(script, "--help")
        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime is missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
