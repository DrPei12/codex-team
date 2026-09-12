#!/usr/bin/env python3
"""Locate the bundled or source Team Auto controller without relying on cwd."""

from pathlib import Path
import sys


def main(argv=None):
    script_dir = Path(__file__).resolve().parent
    for root in (script_dir, script_dir.parent):
        if (root / "team_runtime" / "__init__.py").is_file():
            sys.path.insert(0, str(root))
            break
    else:
        print("ERROR: Team Auto runtime is missing; rebuild the complete Team bundle", file=sys.stderr)
        return 1
    from team_runtime.cli import main as controller_main
    return controller_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
