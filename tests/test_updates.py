"""Update policy, verified packages, native-install boundaries and failure recovery."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import urllib.error
import zipfile

import pytest

from team_runtime import updates as u

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def release(tmp_path, monkeypatch):
    home = tmp_path/'codex'
    home.mkdir()
    monkeypatch.setenv('CODEX_HOME', str(home))
    (home/'config.toml').write_text('[marketplaces.codex-team-local]\nsource_type="git"\nsource="https://github.com/DrPei12/codex-team.git"\n[plugins."codex-team@codex-team-local"]\nenabled=true\n')
    old = u.installed_path(u.VERSION)
    old.parent.mkdir(parents=True)
    subprocess.run([sys.executable, '-B', str(ROOT/'scripts/build-team-plugin.py'), '--out', str(tmp_path/'codex-team')], check=True, capture_output=True)
    shutil.copytree(tmp_path/'codex-team', old)
    monkeypatch.setattr(u, 'plugin_root', lambda: old)
    next_version = '2.1.1'
    source = tmp_path/'future/codex-team'
    shutil.copytree(old, source)
    manifest = source/'.codex-plugin/plugin.json'
    data = u.read_json(manifest)
    data['version'] = next_version
    u.write_json(manifest, data)
    inventory = u.read_json(source/u.MANIFEST)
    inventory['plugin_version'] = next_version
    inventory['files']['.codex-plugin/plugin.json'] = 'sha256:'+hashlib.sha256(manifest.read_bytes()).hexdigest()
    u.write_json(source/u.MANIFEST, inventory)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as out:
        for path in source.rglob('*'):
            if path.is_file():
                out.write(path, path.relative_to(source.parent).as_posix())
    details = {'schema': 1, 'version': next_version, 'automatic': True, 'state_schema': '0.3',
               'highlights': {'en': ['Improved continuity.'], 'zh-CN': ['改善任务续接。']}}
    descriptor = {'tag_name': 'v'+next_version, 'draft': False, 'prerelease': False, 'assets': []}
    responses = {}
    for name, value in [('update.json', json.dumps(details).encode()), ('codex-team-'+next_version+'.zip', archive.getvalue())]:
        url = u.REPOSITORY+'/releases/download/v'+next_version+'/'+name
        descriptor['assets'].append({'name': name, 'browser_download_url': url, 'digest': 'sha256:'+hashlib.sha256(value).hexdigest()})
        responses[url] = value
    responses[u.API] = json.dumps(descriptor).encode()
    calls = []
    def fetch(url, limit):
        calls.append(url)
        return responses[url]
    monkeypatch.setattr(u, 'download', fetch)
    installs = []
    def install(catalog):
        installs.append(catalog)
        root = catalog.parents[2]
        plugin = root/'codex-team'
        value = u.read_json(plugin/'.codex-plugin/plugin.json')['version']
        destination = u.installed_path(value)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(plugin, destination)
    monkeypatch.setattr(u, 'native_install', install)
    return {'old': old, 'source': source, 'calls': calls, 'installs': installs, 'responses': responses, 'descriptor': descriptor}


def test_default_auto_installs_verified_release_and_returns_new_paths(release):
    result = u.check(language='zh-CN')
    assert result['status'] == 'updated' and result['notify']
    assert result['highlights'] == ['改善任务续接。']
    assert Path(result['runtime_path']).is_file()
    assert len(release['installs']) == 1
    calls = len(release['calls'])
    assert u.check()['status'] == 'cached'
    assert len(release['calls']) == calls


def test_notify_and_off_preferences_survive_checks(release):
    assert u.check(mode='notify') == {'status': 'configured', 'mode': 'notify'}
    assert not release['calls']
    assert u.check()['status'] == 'available'
    assert not u.check(force=True)['notify']
    assert not release['installs']
    u.check(mode='off')
    release['calls'].clear()
    assert u.check(force=True)['status'] == 'disabled'
    assert not release['calls']


@pytest.mark.parametrize('reason,configuration', [
    ('local-marketplace', 'source_type="local"\nsource="some-checkout"'),
    ('pinned-version', 'source_type="git"\nsource="https://github.com/DrPei12/codex-team.git"\nref="v2.1.0"'),
    ('different-source', 'source_type="git"\nsource="https://github.com/another/repo.git"'),
])
def test_user_installation_choice_is_preserved(release, reason, configuration):
    config = u.codex_home()/'config.toml'
    config.write_text('[marketplaces.codex-team-local]\n'+configuration+'\n[plugins."codex-team@codex-team-local"]\nenabled=true\n')
    result = u.check()
    assert result['status'] == 'available' and result['reason'] == reason
    assert not release['installs']


@pytest.mark.parametrize('change', ['major', 'schema', 'automatic'])
def test_incompatible_release_only_notifies(release, monkeypatch, change):
    candidate = u.latest()
    if change == 'major':
        candidate['version'] = '3.0.0'
    elif change == 'schema':
        candidate['details']['state_schema'] = '0.4'
    else:
        candidate['details']['automatic'] = False
    monkeypatch.setattr(u, 'latest', lambda: candidate)
    result = u.check()
    assert result['reason'] == 'manual-upgrade' and result['status'] == 'available'
    assert not release['installs']


def test_offline_check_retries_without_blocking_project(release, monkeypatch):
    def offline(*args):
        raise OSError('network offline')
    monkeypatch.setattr(u, 'download', offline)
    assert u.check()['status'] == 'unavailable'
    assert u.check()['status'] == 'cached'
    assert not release['installs']


@pytest.mark.parametrize('failure', ['digest', 'url', 'prerelease', 'version'])
def test_release_identity_failures_never_install(release, failure):
    descriptor = release['descriptor']
    if failure == 'digest':
        descriptor['assets'][0]['digest'] = 'sha256:'+'0'*64
    elif failure == 'url':
        descriptor['assets'][0]['browser_download_url'] = 'https://example.com/payload'
    elif failure == 'version':
        descriptor['tag_name'] = 'v2.1.1/../../bad'
    else:
        descriptor['prerelease'] = True
    release['responses'][u.API] = json.dumps(descriptor).encode()
    assert u.check()['status'] == 'unavailable'
    assert not release['installs']


def test_active_controller_and_unknown_old_run_defer_installation(release):
    with u.gate():
        assert u.check()['status'] == 'deferred'
    with u.WorkspaceClaims()._connect() as db:
        db.execute('INSERT INTO claims VALUES (?, ?)', ('unknown-state:run', 'workspace'))
    assert u.check(force=True)['reason'] == 'active-or-unknown-work'
    assert not release['installs']
    assert not any(url.endswith('.zip') for url in release['calls'])


def test_parallel_checks_do_not_duplicate_installation(release):
    with sqlite3.connect(u.update_home()/'checks.sqlite3') as lock:
        lock.execute('BEGIN IMMEDIATE')
        assert u.check()['status'] == 'busy'
    assert not release['calls']


def test_failed_native_install_restores_previous_version(release, monkeypatch):
    real = u.native_install
    calls = []
    def fail_once(catalog):
        calls.append(catalog)
        if len(calls) == 1:
            shutil.rmtree(release['old'])
            raise OSError('interrupted copy')
        return real(catalog)
    monkeypatch.setattr(u, 'native_install', fail_once)
    result = u.check()
    assert result['status'] == 'rolled-back' and result['notify']
    u.verify_bundle(release['old'], u.VERSION)
    assert len(calls) == 2


def test_lost_native_response_observes_installed_version(release, monkeypatch):
    real = u.native_install
    def lost_response(catalog):
        real(catalog)
        raise OSError('lost response')
    monkeypatch.setattr(u, 'native_install', lost_response)
    assert u.check()['status'] == 'updated'
    assert len(release['installs']) == 1


def test_failed_rollback_retains_recovery_then_retries_it(release, monkeypatch):
    real = u.native_install
    def fail(catalog):
        raise OSError('installer unavailable')
    monkeypatch.setattr(u, 'native_install', fail)
    result = u.check()
    assert result['status'] == 'needs-recovery'
    assert Path(result['runtime_path']).is_file()
    retry = u.check()
    assert retry['status'] == 'needs-recovery' and retry['notify']
    monkeypatch.setattr(u, 'native_install', real)
    assert u.check()['status'] == 'rolled-back'
    u.verify_bundle(release['old'], u.VERSION)


@pytest.mark.parametrize('name', ['../escape', 'codex-team/../../escape', 'codex-team/..\\escape', 'codex-team/C:/escape'])
def test_zip_traversal_is_rejected(tmp_path, name):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(name, 'data')
    with pytest.raises(ValueError, match='unsafe path'):
        u.unpack(buffer.getvalue(), tmp_path/'extract', '2.1.1')


def test_bundle_tampering_never_reaches_installer(release):
    (release['source']/'skills/team/SKILL.md').write_text('tampered')
    with pytest.raises(ValueError, match='checksum'):
        u.verify_bundle(release['source'], '2.1.1')


def test_update_preference_cli_needs_no_project_state(tmp_path):
    result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/team.py'), 'updates', '--mode', 'off'],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and json.loads(result.stdout)['mode'] == 'off'


def test_published_descriptor_matches_current_runtime():
    details = u.read_json(ROOT/'update.json')
    assert details['version'] == u.VERSION
    assert details['schema'] == 1 and details['state_schema'] == '0.3'
    assert set(details['highlights']) == {'en', 'zh-CN'}


def test_public_release_fallback_uses_the_official_checksum_file(release, monkeypatch):
    original = u.download
    descriptor = release['descriptor']
    class Redirect:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def geturl(self):
            return u.REPOSITORY+'/releases/tag/v2.1.1'
    monkeypatch.setattr(u, 'open_url', lambda *a, **k: Redirect())
    def rate_limited(url, limit):
        if url == u.API:
            raise urllib.error.HTTPError(url, 403, 'Rate limit exceeded', None, None)
        if url.endswith('SHA256SUMS.txt'):
            return ''.join(item['digest'][7:]+'  '+item['name']+'\n' for item in descriptor['assets']).encode()
        return original(url, limit)
    monkeypatch.setattr(u, 'download', rate_limited)
    assert u.check()['status'] == 'updated'


def test_crash_after_success_is_observed_before_another_install(release):
    assert u.check()['status'] == 'updated'
    journal = u.update_home()/'installation.json'
    receipt = u.read_json(journal)
    receipt['state'] = 'prepared'
    u.write_json(journal, receipt)
    assert u.check()['status'] == 'updated'
    assert len(release['installs']) == 1


def test_runtime_gate_blocks_a_separate_installer_process(tmp_path):
    code = ('from team_runtime.updates import gate\n'
            'import sqlite3\n'
            'try:\n'
            ' with gate(exclusive=True): print("installed")\n'
            'except sqlite3.OperationalError: print("deferred")\n')
    with u.gate():
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout.strip() == 'deferred'


def test_network_budget_covers_a_stalled_resolver():
    unblock = threading.Event()
    try:
        with pytest.raises(TimeoutError, match='timed out'):
            u.network(lambda: unblock.wait(), seconds=0.01)
    finally:
        unblock.set()


def test_turning_checks_off_still_recovers_an_interrupted_install(release, monkeypatch):
    real = u.native_install
    def fail(catalog):
        if release['old'].exists():
            shutil.rmtree(release['old'])
        raise OSError('controlled failure')
    monkeypatch.setattr(u, 'native_install', fail)
    assert u.check()['status'] == 'needs-recovery'
    assert not release['old'].exists()
    monkeypatch.setattr(u, 'native_install', real)
    release['calls'].clear()
    assert u.check(mode='off')['status'] == 'rolled-back'
    u.verify_bundle(release['old'], u.VERSION)
    assert u.check()['status'] == 'disabled'
    assert not release['calls']


def test_download_transport_honors_explicit_cli_proxy_settings(monkeypatch):
    configured = {'https': 'http://proxy.example:8080', 'no': 'localhost'}
    monkeypatch.setattr(u.urllib.request, 'getproxies_environment', lambda: configured)
    observed = []
    class Opener:
        def open(self, request, timeout):
            assert timeout == 8
            return 'response'
    def build(handler):
        observed.append(handler.proxies)
        return Opener()
    monkeypatch.setattr(u.urllib.request, 'build_opener', build)
    assert u.open_url(object()) == 'response'
    assert observed == [configured]
