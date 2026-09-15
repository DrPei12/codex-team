"""Durable, per-user workspace occupancy shared by all Team state directories."""
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager

from .store import ConflictError


class WorkspaceClaims:
    def __init__(self):
        self.path = Path(os.environ.get('CODEX_TEAM_CLAIMS', str(Path.home() / '.codex-team' / 'workspaces.sqlite3')))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS claims (owner TEXT PRIMARY KEY, workspace TEXT NOT NULL)')
                db.execute('BEGIN IMMEDIATE')
                yield db
        finally:
            db.close()

    def claim(self, state, run_id, workspace):
        owner = str(Path(state).resolve()) + ':' + run_id
        root = Path(workspace).resolve()
        with self._connect() as db:
            for other, occupied in db.execute('SELECT owner, workspace FROM claims'):
                path = Path(occupied).resolve()
                if other != owner and (root.is_relative_to(path) or path.is_relative_to(root)):
                    raise ConflictError('Workspace is held by another Team run; reconcile its original state: ' + other)
            db.execute('INSERT OR REPLACE INTO claims VALUES (?, ?)', (owner, str(root)))

    def release(self, state, run_id):
        with self._connect() as db:
            db.execute('DELETE FROM claims WHERE owner=?', (str(Path(state).resolve()) + ':' + run_id,))
