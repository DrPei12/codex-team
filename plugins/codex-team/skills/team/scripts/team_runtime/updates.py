"""Use-time updates from published Team releases, installed by native Codex."""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import shutil
import sqlite3
import stat
import threading
import time
import tomllib
import urllib.error
import urllib.request
import uuid
import zipfile

from .codex import CodexClient
from .workspace_claims import WorkspaceClaims

VERSION = '2.1.0'
REPOSITORY = 'https://github.com/DrPei12/codex-team'
API = 'https://api.github.com/repos/DrPei12/codex-team/releases/latest'
MARKETPLACE = 'codex-team-local'
INTERVAL = 3600
MANIFEST = 'skills/team/references/bundle-manifest.json'


def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))).expanduser().resolve()


def update_home():
    path = Path(os.environ.get('CODEX_TEAM_UPDATE_HOME', str(codex_home()/'team-updates')))
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path, data):
    temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temp.replace(path)


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('Expected a stable semantic version')
    return tuple(map(int, value.split('.')))


@contextmanager
def gate(exclusive=False):
    """Readers protect running controllers; one installer needs exclusive access."""
    db = sqlite3.connect(update_home()/'runtime-gate.sqlite3', timeout=0.2 if exclusive else 30)
    try:
        db.execute('BEGIN EXCLUSIVE' if exclusive else 'BEGIN')
        db.execute('SELECT name FROM sqlite_master').fetchall()
        yield
    finally:
        db.rollback()
        db.close()


def protected_runtime(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with gate():
            return function(*args, **kwargs)
    return wrapped


def network(operation, seconds=8):
    """Bound DNS, redirects and slow reads as well as individual socket calls."""
    result = queue.Queue(maxsize=1)
    def perform():
        try:
            result.put((True, operation()))
        except Exception as exc:
            result.put((False, exc))
    threading.Thread(target=perform, daemon=True).start()
    try:
        success, value = result.get(timeout=seconds)
    except queue.Empty as exc:
        raise TimeoutError('Release connection timed out') from exc
    if not success:
        raise value
    return value


def open_url(request):
    # Match command-line proxy configuration instead of importing Windows
    # browser/WinINet proxy settings into an otherwise direct Codex CLI install.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(urllib.request.getproxies_environment()))
    return opener.open(request, timeout=8)


def download(url, limit):
    def read():
        request = urllib.request.Request(url, headers={'User-Agent': 'codex-team-updater/'+VERSION,
                                                       'Accept': 'application/vnd.github+json'})
        with open_url(request) as response:
            return response.read(limit+1)
    data = network(read)
    if len(data) > limit:
        raise ValueError('Release download exceeds its size limit')
    return data


def asset(release, name, limit):
    matches = [item for item in release.get('assets', []) if item.get('name') == name]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous release asset: '+name)
    item = matches[0]
    expected = REPOSITORY+'/releases/download/'+release['tag_name']+'/'+name
    if item.get('browser_download_url') != expected or not re.fullmatch(r'sha256:[0-9a-f]{64}', item.get('digest', '')):
        raise ValueError('Release asset identity is invalid')
    data = download(expected, limit)
    if 'sha256:'+hashlib.sha256(data).hexdigest() != item['digest']:
        raise ValueError('Release asset checksum differs: '+name)
    return data


def public_release():
    """The public release redirect works without GitHub API rate-limit capacity."""
    def redirect():
        request = urllib.request.Request(REPOSITORY+'/releases/latest', headers={'User-Agent': 'codex-team-updater/'+VERSION})
        with open_url(request) as response:
            return response.geturl()
    url = network(redirect)
    prefix = REPOSITORY+'/releases/tag/v'
    if not url.startswith(prefix):
        raise ValueError('Latest release redirected outside the official repository')
    value = url[len(prefix):]
    version(value)
    release = {'tag_name': 'v'+value, 'draft': False, 'prerelease': False, 'assets': []}
    if version(value) > version(VERSION):
        base = REPOSITORY+'/releases/download/v'+value+'/'
        lines = download(base+'SHA256SUMS.txt', 8192).decode('ascii').splitlines()
        checksums = {}
        for line in lines:
            match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
            if not match or match[2] in checksums:
                raise ValueError('Invalid release checksum manifest')
            checksums[match[2]] = match[1]
        for name in ('update.json', 'codex-team-'+value+'.zip'):
            if name not in checksums:
                raise ValueError('Release checksum manifest is incomplete')
            release['assets'].append({'name': name, 'browser_download_url': base+name, 'digest': 'sha256:'+checksums[name]})
    return release


def latest():
    try:
        release = json.loads(download(API, 1024*1024))
    except (urllib.error.URLError, TimeoutError):
        release = public_release()
    tag = release.get('tag_name', '')
    value = tag.removeprefix('v')
    version(value)
    if tag != 'v'+value or release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('Only published stable releases can update Team')
    if version(value) <= version(VERSION):
        return {'version': value}
    details = json.loads(asset(release, 'update.json', 32768))
    if details.get('version') != value or details.get('schema') != 1:
        raise ValueError('Update metadata does not match the release')
    notes = details.get('highlights', {})
    for language in ('en', 'zh-CN'):
        if not isinstance(notes.get(language), list) or not 1 <= len(notes[language]) <= 5:
            raise ValueError('Missing concise bilingual release highlights')
        if any(not isinstance(line, str) or not 1 <= len(line) <= 400 for line in notes[language]):
            raise ValueError('Invalid release highlight')
    return {'version': value, 'details': details, 'release': release}


def plugin_root():
    for root in Path(__file__).resolve().parents:
        if (root/'.codex-plugin/plugin.json').is_file():
            return root
    return None


def install_source(root):
    """Honor source checkouts, local marketplaces and explicit revision pins."""
    if root is None:
        return 'source-checkout'
    expected = codex_home()/'plugins/cache'/MARKETPLACE/'codex-team'/VERSION
    if root.resolve() != expected.resolve():
        return 'unmanaged-installation'
    manifest = read_json(root/'.codex-plugin/plugin.json')
    if manifest.get('repository') != REPOSITORY or manifest.get('version') != VERSION:
        return 'different-source'
    with (codex_home()/'config.toml').open('rb') as stream:
        config = tomllib.load(stream)
    source = config.get('marketplaces', {}).get(MARKETPLACE, {})
    if source.get('source_type') != 'git':
        return 'local-marketplace'
    if source.get('source', '').rstrip('/') not in (REPOSITORY, REPOSITORY+'.git'):
        return 'different-source'
    if source.get('ref') not in (None, '', 'main', 'refs/heads/main'):
        return 'pinned-version'
    if config.get('plugins', {}).get('codex-team@'+MARKETPLACE, {}).get('enabled') is not True:
        return 'plugin-disabled'
    return None


def verify_bundle(root, expected_version):
    manifest = read_json(root/'.codex-plugin/plugin.json')
    if not manifest or (manifest.get('name'), manifest.get('version'), manifest.get('repository')) != ('codex-team', expected_version, REPOSITORY):
        raise ValueError('Installed plugin identity differs from the release')
    inventory = read_json(root/MANIFEST, {})
    files = inventory.get('files', {})
    actual = {p.relative_to(root).as_posix(): p for p in root.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.relative_to(root).as_posix() != MANIFEST}
    if not files or set(files) != set(actual):
        raise ValueError('Bundle file inventory differs')
    for name, path in actual.items():
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Bundle contains a linked file')
        if 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest() != files[name]:
            raise ValueError('Bundle checksum differs: '+name)
    if not (root/'skills/team/scripts/team.py').is_file():
        raise ValueError('Team launcher is missing')


def unpack(data, target, expected_version):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 256 or sum(item.file_size for item in entries) > 32*1024*1024:
            raise ValueError('Release archive exceeds its size limit')
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            if ('\\' in item.filename or ':' in item.filename or path.is_absolute() or '..' in path.parts
                    or not path.parts or path.parts[0] != 'codex-team' or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Release archive contains an unsafe path')
            key = item.filename.casefold()
            if key in seen:
                raise ValueError('Release archive contains duplicate paths')
            seen.add(key)
            if not item.is_dir():
                destination = target.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(item))
    root = target/'codex-team'
    verify_bundle(root, expected_version)
    return root


def marketplace(root, plugin):
    path = root/'.agents/plugins/marketplace.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {'name': MARKETPLACE, 'interface': {'displayName': 'Codex Team Local'},
        'plugins': [{'name': 'codex-team', 'source': {'source': 'local', 'path': './'+plugin.relative_to(root).as_posix()},
                     'policy': {'authentication': 'ON_INSTALL', 'installation': 'AVAILABLE'}, 'category': 'Productivity'}]})
    return path


def native_install(catalog):
    with CodexClient() as client:
        client.request('plugin/install', {'pluginName': 'codex-team', 'marketplacePath': str(catalog.resolve())}, timeout=40)


def installed_path(value):
    return codex_home()/'plugins/cache'/MARKETPLACE/'codex-team'/value


def paths(root):
    return {'installed_path': str(root), 'skill_path': str(root/'skills/team/SKILL.md'),
            'runtime_path': str(root/'skills/team/scripts/team.py')}


def install(candidate, old_root):
    """Stage and verify before acquiring the short installation boundary."""
    with gate(exclusive=True), WorkspaceClaims()._connect() as claims:
        if any(not WorkspaceClaims._can_release(owner) for owner, in claims.execute('SELECT owner FROM claims')):
            return {'status': 'deferred', 'reason': 'active-or-unknown-work'}
    value = candidate['version']
    work = update_home()/'installations'/uuid.uuid4().hex
    work.mkdir(parents=True)
    package = unpack(asset(candidate['release'], 'codex-team-'+value+'.zip', 32*1024*1024), work/'release', value)
    catalog = marketplace(work/'release', package)
    rollback = work/'rollback/codex-team'
    shutil.copytree(old_root, rollback, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    verify_bundle(rollback, VERSION)
    fallback = marketplace(work/'rollback', rollback)
    receipt = {'from_version': VERSION, 'to_version': value, 'catalog': str(catalog),
               'rollback_catalog': str(fallback), 'started': time.time(), 'state': 'prepared'}
    # This journal survives a crashed installer independently of the check lock.
    journal = update_home()/'installation.json'
    with gate(exclusive=True), WorkspaceClaims()._connect() as claims:
        if any(not WorkspaceClaims._can_release(owner) for owner, in claims.execute('SELECT owner FROM claims')):
            return {'status': 'deferred', 'reason': 'active-or-unknown-work'}
        write_json(journal, receipt)
        try:
            native_install(catalog)
            target = installed_path(value)
            verify_bundle(target, value)
        except Exception as exc:
            # The installer may have completed even when its response was lost.
            try:
                verify_bundle(installed_path(value), value)
            except Exception:
                try:
                    native_install(fallback)
                    verify_bundle(old_root, VERSION)
                    receipt.update(state='rolled-back', error=str(exc))
                except Exception as recovery:
                    receipt.update(state='needs-recovery', error=str(exc), recovery_error=str(recovery))
                write_json(journal, receipt)
                return {'status': receipt['state'], 'receipt_path': str(journal), 'reason': 'installation-failed',
                        **paths(old_root if receipt['state'] == 'rolled-back' else rollback)}
        receipt.update(state='installed', finished=time.time())
        write_json(journal, receipt)
        return {'status': 'updated', **paths(installed_path(value)), 'receipt_path': str(journal)}


def recover_installation():
    """Observe a interrupted installation before attempting another update."""
    journal = update_home()/'installation.json'
    receipt = read_json(journal, {})
    if receipt.get('state') not in {'prepared', 'needs-recovery'}:
        return None
    value, previous = receipt['to_version'], receipt['from_version']
    version(value)
    version(previous)
    with gate(exclusive=True), WorkspaceClaims()._connect() as claims:
        if any(not WorkspaceClaims._can_release(owner) for owner, in claims.execute('SELECT owner FROM claims')):
            return {'status': 'deferred', 'reason': 'active-or-unknown-work', 'notify': False}
        try:
            verify_bundle(installed_path(value), value)
        except Exception:
            fallback = Path(receipt['rollback_catalog']).resolve()
            if not fallback.is_relative_to((update_home()/'installations').resolve()):
                raise ValueError('Recovery catalog is outside the update store')
            backup = fallback.parents[2]/'codex-team'
            verify_bundle(backup, previous)
            try:
                native_install(fallback)
                verify_bundle(installed_path(previous), previous)
            except Exception as exc:
                receipt.update(state='needs-recovery', recovery_error=str(exc))
                write_json(journal, receipt)
                return {'status': 'needs-recovery', 'notify': True, 'reason': 'recovery-failed',
                        'receipt_path': str(journal), **paths(backup)}
            receipt['state'] = 'rolled-back'
            result = {'status': 'rolled-back', **paths(installed_path(previous))}
        else:
            receipt['state'] = 'installed'
            result = {'status': 'updated', **paths(installed_path(value))}
        write_json(journal, receipt)
        return {**result, 'notify': True, 'receipt_path': str(journal), 'latest_version': value}


def check(*, mode=None, force=False, language='en'):
    """Never block the delegated task on a failed availability check."""
    home = update_home()
    settings = home/'settings.json'
    cache_path = home/'check.json'
    db = sqlite3.connect(home/'checks.sqlite3', timeout=0.2)
    try:
        db.execute('BEGIN IMMEDIATE')
        preference = read_json(settings, {'mode': 'auto'})
        if mode is not None:
            if mode not in {'auto', 'notify', 'off'}:
                raise ValueError('Update mode must be auto, notify or off')
            preference['mode'] = mode
            write_json(settings, preference)
            recovery = recover_installation()
            if recovery:
                return {**recovery, 'mode': mode}
            return {'status': 'configured', 'mode': mode}
        selected = preference['mode']
        recovery = recover_installation()
        if recovery:
            return recovery
        if selected == 'off':
            return {'status': 'disabled', 'notify': False}
        cache = read_json(cache_path, {})
        now = time.time()
        if not force and now < cache.get('next_check', 0):
            return {'status': 'cached', 'notify': False, 'version': VERSION}
        # Reserve the check before network work; transient failures retry in 5 minutes.
        cache['next_check'] = now+300
        write_json(cache_path, cache)
        candidate = latest()
        value = candidate['version']
        result = {'version': VERSION, 'latest_version': value, 'mode': selected, 'notify': False}
        if version(value) <= version(VERSION):
            result['status'] = 'current'
        else:
            result.update(status='available', highlights=candidate['details']['highlights'][language],
                          release_url=REPOSITORY+'/releases/tag/v'+value)
            reason = install_source(plugin_root())
            details = candidate['details']
            if version(value)[0] != version(VERSION)[0] or details.get('state_schema') != '0.3' or details.get('automatic') is not True:
                reason = 'manual-upgrade'
            if selected == 'auto' and reason is None:
                try:
                    result.update(install(candidate, plugin_root()))
                except sqlite3.OperationalError:
                    result.update(status='deferred', reason='runtime-busy')
            elif reason:
                result['reason'] = reason
            notice = result['status']+':'+value
            result['notify'] = result['status'] != 'deferred' and cache.get('notified') != notice
            if result['notify']:
                cache['notified'] = notice
        cache['next_check'] = now+(300 if result['status'] in {'deferred', 'rolled-back', 'needs-recovery'} else INTERVAL)
        write_json(cache_path, cache)
        return result
    except sqlite3.OperationalError:
        return {'status': 'busy', 'notify': False}
    except Exception as exc:
        return {'status': 'unavailable', 'notify': False, 'reason': str(exc), 'version': VERSION}
    finally:
        db.rollback()
        db.close()
