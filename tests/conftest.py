"""Keep test workspace claims out of the signed-in user's runtime registry."""
import pytest


@pytest.fixture(autouse=True)
def isolated_claims(tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_TEAM_CLAIMS', str(tmp_path / 'claims.sqlite3'))
