"""Version-observed Codex App Server stdio client, with no third-party runtime."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import uuid
from typing import Callable


class CodexError(RuntimeError):
    pass


def codex_command() -> list[str]:
    explicit = os.environ.get('CODEX_TEAM_CODEX')
    if explicit:
        path = Path(explicit).resolve(strict=True)
        return [str(path)]
    found = shutil.which('codex.exe') or shutil.which('codex')
    if not found:
        raise CodexError('Codex executable is not installed or not on PATH')
    path = Path(found)
    if os.name == 'nt' and path.suffix.lower() in {'.cmd', '.ps1'}:
        vendor = path.parent / 'node_modules' / '@openai' / 'codex'
        matches = list(vendor.glob('node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe'))
        if len(matches) == 1:
            return [str(matches[0])]
        node = shutil.which('node')
        launcher = vendor / 'bin' / 'codex.js'
        if node and launcher.is_file():
            return [node, str(launcher)]
        raise CodexError('Cannot resolve native Codex launcher; set CODEX_TEAM_CODEX')
    return [str(path)]


class CodexClient:
    # A turn interruption is a control operation, so it must be bounded even
    # when the App Server has stopped answering.  The caller still receives an
    # explicit unknown outcome if this window cannot establish a stop receipt.
    _TURN_CONFIRM_TIMEOUT = 10.0

    def __init__(self, *, on_event: Callable[[dict], None] | None = None,
                 on_request: Callable[[dict], dict] | None = None):
        self.on_event = on_event or (lambda event: None)
        self.on_request = on_request
        self._lock = threading.Lock()
        self._pending: dict[int, queue.Queue] = {}
        self._counter = 0
        self._events: list[dict] = []
        self._condition = threading.Condition()
        self._closed = False
        self._current_turn = None
        self._reader_ident = None
        self.callback_errors: list[str] = []
        self._commands: dict[str, dict] = {}
        self.command_outcomes: dict[str, dict] = {}
        self.stderr: list[str] = []
        self.process = subprocess.Popen(
            codex_command() + ['app-server', '--stdio'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding='utf-8', errors='replace', bufsize=1,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        try:
            self.info = self.request('initialize', {
                'clientInfo': {'name': 'codex_team', 'title': 'Codex Team', 'version': '0.2.0'},
                'capabilities': {'experimentalApi': True},
            })
            self.notify('initialized', {})
        except BaseException as exc:
            try:
                self.close()
            except Exception as cleanup:
                exc.add_note('App Server cleanup also failed: ' + str(cleanup))
            raise

    def _read_stderr(self):
        for line in self.process.stderr:
            self.stderr.append(line.rstrip())
            self.stderr[:] = self.stderr[-50:]

    def _write(self, message):
        with self._lock:
            if self._closed or self.process.poll() is not None:
                raise CodexError('App Server disconnected')
            self.process.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
            self.process.stdin.flush()

    def _answer(self, message):
        try:
            if self.on_request:
                result = self.on_request(message)
            elif 'requestApproval' in message['method']:
                result = {'decision': 'decline'}
            else:
                raise CodexError('Unhandled server request: ' + message['method'])
            self._write({'id': message['id'], 'result': result})
        except Exception as exc:
            try:
                self._write({'id': message['id'], 'error': {'code': -32603, 'message': str(exc)}})
            except CodexError:
                pass

    def _read(self):
        reader_ident = threading.get_ident()
        with self._lock:
            self._reader_ident = reader_ident
        try:
            for line in self.process.stdout:
                message = json.loads(line)
                if 'method' in message:
                    try:
                        self.on_event(message)
                    except Exception as exc:
                        with self._condition:
                            self.callback_errors.append(str(exc))
                            self._condition.notify_all()
                    else:
                        # Publish only after the durable callback succeeds. A terminal
                        # event must never outrun its persistence or a callback failure.
                        with self._condition:
                            self._events.append(message)
                            self._condition.notify_all()
                    if 'id' in message:
                        threading.Thread(target=self._answer, args=(message,), daemon=True).start()
                else:
                    with self._lock:
                        waiter = self._pending.get(message.get('id'))
                    if waiter:
                        waiter.put(message)
        except Exception as exc:
            failure = str(exc)
        else:
            failure = 'App Server stdout closed'
        with self._lock:
            for waiter in self._pending.values():
                waiter.put({'error': {'message': failure}})
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        with self._lock:
            if self._reader_ident == reader_ident:
                self._reader_ident = None

    def request(self, method: str, params: dict, timeout: float = 40) -> dict:
        waiter = queue.Queue()
        with self._lock:
            self._counter += 1
            request_id = self._counter
            self._pending[request_id] = waiter
        try:
            self._write({'id': request_id, 'method': method, 'params': params})
            try:
                response = waiter.get(timeout=timeout)
            except queue.Empty as exc:
                raise CodexError(f'{method} timed out; outcome unknown') from exc
            if 'error' in response:
                raise CodexError(f'{method}: {response["error"]}')
            return response.get('result', {})
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def notify(self, method, params):
        self._write({'method': method, 'params': params})

    def mark(self) -> int:
        with self._condition:
            return len(self._events)

    def events(self, after=0) -> list[dict]:
        with self._condition:
            return list(self._events[after:])

    def _set_current_turn(self, thread_id, turn_id):
        with self._lock:
            self._current_turn = (thread_id, turn_id)

    def _clear_current_turn(self, thread_id, turn_id):
        with self._lock:
            if self._current_turn == (thread_id, turn_id):
                self._current_turn = None

    def _current_turn_snapshot(self):
        with self._lock:
            return getattr(self, '_current_turn', None)

    @staticmethod
    def _terminal_turn_from_event(event, thread_id, turn_id):
        if not isinstance(event, dict) or event.get('method') != 'turn/completed':
            return None
        params = event.get('params', {})
        turn = params.get('turn', {}) if isinstance(params, dict) else {}
        if (isinstance(params, dict) and params.get('threadId') == thread_id
                and isinstance(turn, dict) and turn.get('id') == turn_id):
            return turn
        return None

    def _terminal_turn(self, thread_id, turn_id):
        with self._condition:
            for event in self._events:
                turn = self._terminal_turn_from_event(event, thread_id, turn_id)
                if turn is not None:
                    return turn
        return None

    @staticmethod
    def _same_thread_is_idle(response, thread_id):
        if not isinstance(response, dict):
            return False
        thread = response.get('thread')
        status = thread.get('status') if isinstance(thread, dict) else None
        return (isinstance(thread, dict) and thread.get('id') == thread_id
                and isinstance(status, dict) and status.get('type') == 'idle')

    def _interrupt_and_confirm(self, thread_id, turn_id):
        """Stop one owned turn and require a native stop observation.

        This method is called by the waiter or context owner, never by
        ``_read`` while it is running an event persistence callback.  That
        separation is deliberate: a callback may block the reader, and a
        synchronous request from that same thread would deadlock the client.
        """
        if self._terminal_turn(thread_id, turn_id) is not None:
            return True, 'terminal event'

        with self._lock:
            reader_ident = self._reader_ident
            has_transport = ('request' in self.__dict__ or hasattr(self, 'process'))
        if reader_ident == threading.get_ident():
            return False, 'cannot synchronously interrupt from the App Server reader callback thread'
        if not has_transport:
            return False, 'App Server transport is unavailable'

        params = {'threadId': thread_id, 'turnId': turn_id}
        failures = []
        interrupt_sent = False
        try:
            self.request('turn/interrupt', params, timeout=self._TURN_CONFIRM_TIMEOUT)
            interrupt_sent = True
        except Exception as exc:
            failures.append('turn/interrupt failed: ' + str(exc))

        if self._terminal_turn(thread_id, turn_id) is not None:
            return True, 'terminal event'

        # A failed interrupt cannot be treated as a stop acknowledgement.  A
        # single read still checks the race where the native turn ended just
        # before the request failed; any active/wrong/error response remains
        # explicitly unknown instead of being retried against an unverified
        # target.
        try:
            observed = self.request('thread/read', {'threadId': thread_id},
                                    timeout=self._TURN_CONFIRM_TIMEOUT)
        except Exception as exc:
            failures.append('thread/read failed: ' + str(exc))
            if not interrupt_sent:
                return False, '; '.join(failures)
            observed = None
        if self._same_thread_is_idle(observed, thread_id):
            return True, 'thread/read idle'
        if observed is not None:
            thread = observed.get('thread') if isinstance(observed, dict) else None
            if not isinstance(thread, dict) or thread.get('id') != thread_id:
                failures.append('thread/read returned another or invalid thread')
                return False, '; '.join(failures)
            else:
                failures.append('thread/read status is not idle: ' + repr(thread.get('status')))

        # The terminal event may be delivered asynchronously after the
        # interrupt/read responses.  Wait only for the event publication path;
        # persistence has already completed before _events is notified.
        deadline = time.monotonic() + self._TURN_CONFIRM_TIMEOUT
        while interrupt_sent and time.monotonic() < deadline:
            if self._terminal_turn(thread_id, turn_id) is not None:
                return True, 'terminal event'
            with self._condition:
                self._condition.wait(timeout=min(0.1, max(0, deadline-time.monotonic())))
        if self._terminal_turn(thread_id, turn_id) is not None:
            return True, 'terminal event'
        return False, '; '.join(failures) or 'no terminal event or same-thread idle observation'

    def _raise_turn_failure(self, thread_id, turn_id, error):
        confirmed, detail = self._interrupt_and_confirm(thread_id, turn_id)
        if confirmed:
            self._clear_current_turn(thread_id, turn_id)
        else:
            # Keep the original exception object/type/message for callers such
            # as the engine's lease/conflict handling, while making the native
            # outcome impossible to mistake for a successful stop.
            error.add_note('Turn interruption outcome unknown for ' +
                           repr((thread_id, turn_id)) + ': ' + detail)
        raise error

    def wait_turn(self, thread_id, turn_id, *, timeout=600, after=0, tick=None) -> dict:
        self._set_current_turn(thread_id, turn_id)
        deadline = time.monotonic() + timeout
        cursor = after
        while time.monotonic() < deadline:
            with self._condition:
                pending = self._events[cursor:]
                cursor = len(self._events)
                closed = self._closed
                persistence_error = self.callback_errors[-1] if self.callback_errors else None
            if persistence_error is not None:
                self._raise_turn_failure(thread_id, turn_id,
                                         CodexError('Event persistence failed: ' + persistence_error))
            for event in pending:
                turn = self._terminal_turn_from_event(event, thread_id, turn_id)
                if turn is not None:
                    self._clear_current_turn(thread_id, turn_id)
                    return turn
            if closed:
                raise CodexError('App Server disconnected while a turn was running; reconcile before retry')
            with self._condition:
                persistence_error = self.callback_errors[-1] if self.callback_errors else None
            if persistence_error is not None:
                self._raise_turn_failure(thread_id, turn_id,
                                         CodexError('Event persistence failed: ' + persistence_error))
            if tick:
                try:
                    tick()
                except Exception as exc:
                    self._raise_turn_failure(thread_id, turn_id, exc)
            with self._condition:
                self._condition.wait(timeout=min(1, max(0, deadline-time.monotonic())))
        with self._condition:
            persistence_error = self.callback_errors[-1] if self.callback_errors else None
        if persistence_error is not None:
            self._raise_turn_failure(thread_id, turn_id,
                                     CodexError('Event persistence failed: ' + persistence_error))
        self._raise_turn_failure(thread_id, turn_id,
                                 CodexError('Turn deadline exceeded; interruption and reconciliation required'))

    def start_thread(self, cwd, *, instructions='', model='gpt-5.6-luna', effort='max',
                     writable=False, max_subagents=0, dynamic_tools=None, network_access=False,
                     project_id=None, title=None, web_search=None) -> dict:
        if not isinstance(network_access, bool):
            raise ValueError('network_access must be boolean')
        config = {'model_reasoning_effort': effort, 'features.plugins': False, 'agents.enabled': max_subagents > 0,
                  'agents.default_subagent_model': model,
                  'agents.default_subagent_reasoning_effort': effort,
                  'sandbox_workspace_write.network_access': network_access,
                  'sandbox_workspace_write.writable_roots': [],
                  'sandbox_workspace_write.exclude_tmpdir_env_var': True,
                  'sandbox_workspace_write.exclude_slash_tmp': True}
        if max_subagents:
            config['agents.max_concurrent_threads_per_session'] = max_subagents
        if web_search is not None:
            if web_search not in {'disabled', 'cached', 'live'}:
                raise ValueError('Unknown native web search mode')
            config['web_search'] = web_search
        params = {
            'cwd': str(Path(cwd).resolve()), 'model': model, 'approvalPolicy': 'never',
            'sandbox': 'workspace-write' if writable else 'read-only',
            'config': config, 'developerInstructions': instructions,
        }
        if dynamic_tools:
            params['dynamicTools'] = dynamic_tools
        if project_id is not None:
            params['projectId'] = project_id
        result = self.request('thread/start', params)
        if result.get('model') != model or result.get('reasoningEffort') != effort:
            raise CodexError('Requested model/effort not confirmed by thread/start: ' +
                             repr((result.get('model'), result.get('reasoningEffort'))))
        self.validate_sandbox(result.get('sandbox'), cwd, writable=writable,
                              network_access=network_access)
        thread = result.get('thread')
        if project_id is not None:
            if (not isinstance(thread, dict) or thread.get('projectId') != project_id):
                raise CodexError('thread/start did not confirm requested project binding: ' +
                                 repr(thread.get('projectId') if isinstance(thread, dict) else None))
        if title is not None:
            if not isinstance(thread, dict) or not thread.get('id'):
                raise CodexError('thread/start did not return a thread id for naming')
            self.request('thread/name/set', {'threadId': thread['id'], 'name': title})
        return result

    @staticmethod
    def validate_sandbox(sandbox, cwd, *, writable, network_access=False):
        expected_type = 'workspaceWrite' if writable else 'readOnly'
        if (not isinstance(sandbox, dict) or sandbox.get('type') != expected_type
                or sandbox.get('networkAccess', False) is not network_access):
            raise CodexError('Requested sandbox/network policy not confirmed: ' + repr(sandbox))
        if writable:
            root = Path(cwd).resolve()
            for value in sandbox.get('writableRoots', []):
                path = Path(value).resolve()
                if path != root and root not in path.parents:
                    raise CodexError('Native sandbox includes an unauthorized writable root: ' + str(path))
            if not sandbox.get('excludeTmpdirEnvVar') or not sandbox.get('excludeSlashTmp'):
                raise CodexError('Native sandbox did not exclude ambient temporary write roots')

    @property
    def active_command_ids(self):
        with self._lock:
            return tuple(self._commands)

    def interrupt_command(self, process_id):
        with self._lock:
            record = self._commands.get(process_id)
            if record is None:
                raise CodexError('Command is not owned by this client')
            if record.get('interrupted'):
                return
            record['interrupted'] = True
        try:
            self.request('command/exec/terminate', {'processId': process_id}, timeout=10)
        except Exception as exc:
            with self._lock:
                # A native launch failure plus a native no-active response is
                # evidence that there is no command to reap. Neither fact alone
                # permits treating an arbitrary transport failure as resolved.
                if record.get('launch_failure') and 'no active command/exec' in str(exc).casefold():
                    self.command_outcomes[process_id] = {
                        'status': 'not-started', 'error': record['launch_failure'],
                        'confirmation': str(exc),
                    }
                    self._commands.pop(process_id, None)
                    return
                record['termination_error'] = str(exc)
            raise

    def command_exec(self, argv, cwd, *, network_access=False, timeout_seconds=120, tick=None, env=None):
        """Execute in the native sandbox; only an actual exec response confirms exit.

        Terminate acknowledgement alone is not an exit receipt. Unknown outcomes
        remain in active_command_ids and raise rather than becoming a passed gate.
        """
        if (not isinstance(argv, (list, tuple)) or not argv
                or any(not isinstance(value, str) or '\x00' in value for value in argv)):
            raise ValueError('command requires a nonempty argv string vector')
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError('command timeout must be finite and positive')
        if not isinstance(network_access, bool):
            raise ValueError('network_access must be boolean')
        if env is not None and (not isinstance(env, dict) or any(
                not isinstance(key, str) or not key or '\x00' in key or '=' in key
                or (value is not None and (not isinstance(value, str) or '\x00' in value))
                for key, value in env.items())):
            raise ValueError('env must map environment names to strings or None')
        command_env = {'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        command_env.update(env or {})
        sandbox = {'type': 'workspaceWrite', 'writableRoots': [str(Path(cwd).resolve())],
                   'networkAccess': network_access, 'excludeTmpdirEnvVar': True, 'excludeSlashTmp': True}
        process_id = 'team-command-' + uuid.uuid4().hex
        waiter = queue.Queue()
        record = {'interrupted': False}
        with self._lock:
            self._counter += 1
            request_id = self._counter
            self._pending[request_id] = waiter
            self._commands[process_id] = record
        known_exit = False
        timed_out = False
        tick_error = None
        try:
            self._write({'id': request_id, 'method': 'command/exec', 'params': {
                'command': list(argv), 'cwd': str(Path(cwd).resolve()), 'processId': process_id,
                'sandboxPolicy': sandbox, 'timeoutMs': max(1, int(timeout_seconds * 1000)),
                'env': command_env,
            }})
            deadline = time.monotonic() + timeout_seconds
            stop_deadline = None
            while True:
                try:
                    response = waiter.get(timeout=0.05)
                except queue.Empty:
                    response = None
                if response is not None:
                    if 'error' in response:
                        failure = str(response['error'])
                        if 'spawnchild' in failure.casefold() and 'createprocessasuserw' in failure.casefold():
                            record['launch_failure'] = failure
                        raise CodexError('command/exec failed; exit not confirmed: ' + str(response['error']))
                    result = response.get('result', {})
                    if (type(result.get('exitCode')) is not int
                            or not isinstance(result.get('stdout'), str)
                            or not isinstance(result.get('stderr'), str)):
                        raise CodexError('command/exec returned no valid exit receipt')
                    known_exit = True
                    if self.callback_errors:
                        raise CodexError('Event persistence failed: ' + self.callback_errors[-1])
                    if tick_error:
                        raise CodexError('Command control failed after confirmed termination: ' + str(tick_error))
                    return {'process_id': process_id, 'exit_code': result['exitCode'],
                            'stdout': result['stdout'], 'stderr': result['stderr'], 'sandbox': sandbox,
                            'timed_out': timed_out, 'interrupted': record['interrupted']}
                if self.callback_errors and tick_error is None:
                    tick_error = CodexError('Event persistence failed: ' + self.callback_errors[-1])
                if tick and tick_error is None and stop_deadline is None:
                    try:
                        tick()
                    except Exception as exc:
                        tick_error = exc
                timed_out = timed_out or time.monotonic() >= deadline
                if (timed_out or tick_error or record['interrupted']) and stop_deadline is None:
                    stop_deadline = time.monotonic() + 10
                    if not record['interrupted']:
                        try:
                            self.interrupt_command(process_id)
                        except Exception:
                            # The process may have exited just before terminate. Only
                            # its original response, consumed above, resolves that race.
                            pass
                if stop_deadline is not None and time.monotonic() >= stop_deadline:
                    raise CodexError('Command termination outcome unknown: ' + process_id +
                                     ('; ' + record['termination_error'] if record.get('termination_error') else ''))
                if self._closed:
                    raise CodexError('App Server disconnected; command exit unknown: ' + process_id)
        finally:
            with self._lock:
                self._pending.pop(request_id, None)
                if known_exit:
                    self._commands.pop(process_id, None)

    def start_turn(self, thread_id, prompt, *, model='gpt-5.6-luna', effort='max', output_schema=None):
        params = {'threadId': thread_id, 'model': model, 'effort': effort,
                  'input': [{'type': 'text', 'text': prompt}]}
        if output_schema is not None:
            params['outputSchema'] = output_schema
        turn = self.request('turn/start', params)['turn']
        if isinstance(turn, dict) and turn.get('id') is not None:
            self._set_current_turn(thread_id, turn['id'])
        return turn

    def text_for_turn(self, thread_id, turn_id, after=0) -> str:
        texts = []
        finals = []
        for event in self.events(after):
            params = event.get('params', {})
            item = params.get('item', {})
            if (event.get('method') == 'item/completed' and params.get('threadId') == thread_id
                    and params.get('turnId') == turn_id and item.get('type') == 'agentMessage'):
                texts.append(item.get('text', ''))
                if item.get('phase') in {'final_answer', 'final'}:
                    finals.append(item.get('text', ''))
        return '\n'.join(finals) if finals else (texts[-1] if texts else '')

    def close(self):
        current_turn = self._current_turn_snapshot()
        if getattr(self, 'process', None) is None and current_turn is None:
            return
        failures = []
        if current_turn is not None:
            thread_id, turn_id = current_turn
            confirmed, detail = self._interrupt_and_confirm(thread_id, turn_id)
            if confirmed:
                self._clear_current_turn(thread_id, turn_id)
            else:
                failures.append('Turn interruption outcome unknown for ' +
                                repr((thread_id, turn_id)) + ': ' + detail)
        for process_id in self.active_command_ids:
            try:
                self.interrupt_command(process_id)
            except Exception as exc:
                failures.append(str(exc))
        process = getattr(self, 'process', None)
        if process is not None and process.poll() is None:
            try:
                process.stdin.close()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        # This Popen belongs solely to this client, never a shared
                        # desktop server or a process discovered by name.
                        process.kill()
                        process.wait(timeout=5)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        failures.append('Owned App Server exit unknown: ' + str(exc))
        self._closed = True
        if self.active_command_ids:
            failures.append('Command exits remain unconfirmed: ' + ', '.join(self.active_command_ids))
        if failures:
            raise CodexError('; '.join(failures))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.close()
        except Exception as cleanup:
            if exc is None:
                raise
            exc.add_note('App Server cleanup also failed: ' + str(cleanup))
        return False
