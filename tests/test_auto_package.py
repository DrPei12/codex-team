"""Portable Auto package checks; no model calls, authentication, or installation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AutoPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="team-auto-package-")
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
        result = self.command(ROOT / "scripts/team-auto.py", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("propose", result.stdout)
        self.assertIn("approve", result.stdout)

    def test_moved_bundle_imports_schema_board_and_cli(self):
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
            "import team_runtime, team_runtime.board; "
            "from team_runtime.engine import Engine; "
            "from team_runtime.rules import PROPOSAL_SCHEMA; "
            "assert PROPOSAL_SCHEMA['type']=='object'; "
            "assert Path(team_runtime.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve()); "
            "assert (Path(team_runtime.__file__).parent/'static'/'index.html').is_file(); "
            "print('portable-import-ok')"
        )
        imported = self.command("-I", "-c", probe, runtime)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertIn("portable-import-ok", imported.stdout)
        help_result = self.command(runtime / "team-auto.py", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        checked = self.command(runtime / "bundle-self-check.py")
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_static_asset_tamper_and_extra_file_are_rejected(self):
        plugin = self.build()
        runtime = plugin / "skills/team/scripts"
        static = runtime / "team_runtime/static/app.js"
        original = static.read_bytes()
        static.write_bytes(original + b"\n/* altered */\n")
        checked = self.command(runtime / "bundle-self-check.py")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("hash mismatch", checked.stderr)
        static.write_bytes(original)
        (runtime / "team_runtime/static/unlisted.txt").write_text("unexpected", encoding="utf-8")
        checked = self.command(runtime / "bundle-self-check.py")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("inventory mismatch", checked.stderr)

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
        script = self.external / "isolated/team-auto.py"
        script.parent.mkdir()
        shutil.copyfile(ROOT / "scripts/team-auto.py", script)
        result = self.command(script, "--help")
        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime is missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
