#!/usr/bin/env python3
"""Run the release checks and compare the distributable bundle with its source."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([sys.executable, '-u', '-B', *map(str, args)], cwd=ROOT,
                   env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}, check=True)


def check_public_docs():
    files = list(ROOT.glob('*.md')) + list((ROOT/'docs').rglob('*.md'))
    for path in files:
        if not path.stem.endswith('.zh-CN') and not path.with_name(path.stem+'.zh-CN.md').is_file():
            raise RuntimeError('Missing Chinese documentation: ' + str(path))
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', text):
            target = target.strip('<>').split('#')[0]
            if not target or re.match(r'[a-zA-Z][\w+.-]*:', target):
                continue
            if not (path.parent/unquote(target)).exists():
                raise RuntimeError(f'Broken documentation link in {path}: {target}')
    print(f'PASS: {len(files)} bilingual public documents and their local links', flush=True)


def main():
    check_public_docs()
    run('-m', 'pytest', '-q', 'tests')
    with tempfile.TemporaryDirectory(prefix='codex-team-release-') as temp:
        bundle = Path(temp)/'codex-team'
        run('scripts/build-team-plugin.py', '--out', bundle)
        run(bundle/'skills/team/scripts/bundle-self-check.py', bundle/'skills/team')
        public = ROOT/'plugins/codex-team'
        expected = {p.relative_to(bundle).as_posix(): p.read_bytes() for p in bundle.rglob('*') if p.is_file()}
        actual = {p.relative_to(public).as_posix(): p.read_bytes() for p in public.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        if expected != actual:
            changed = sorted(k for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k))
            raise RuntimeError('Rebuild the checked-in plugin bundle: ' + ', '.join(changed))
    print('PASS: release checks and source-to-bundle comparison')


if __name__ == '__main__':
    main()
