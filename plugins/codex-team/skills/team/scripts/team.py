#!/usr/bin/env python3
"""Locate the portable Team runtime relative to this script."""
from pathlib import Path
import sys


def main(argv=None):
    here = Path(__file__).resolve().parent
    for root in (here, here.parent):
        if (root / "team_runtime" / "cli.py").is_file():
            sys.path.insert(0, str(root))
            break
    else:
        print("ERROR: Team runtime is missing; rebuild the complete plugin", file=sys.stderr)
        return 1
    from team_runtime.cli import main as controller
    return controller(argv)


if __name__ == "__main__":
    raise SystemExit(main())
