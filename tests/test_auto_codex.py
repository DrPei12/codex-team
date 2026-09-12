"""Offline protocol and lifecycle tests. Never starts a Codex App Server/model."""
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock

from team_runtime.codex import CodexClient, CodexError


def client_fixture():
    client = CodexClient.__new__(CodexClient)
    client._lock = threading.Lock()
    client._pending = {}
    client._counter = 0
    client._events = []
    client._condition = threading.Condition()
    client._closed = False
    client._current_turn = None
    client._reader_ident = None
    client.callback_errors = []
    client._commands = {}
    client.command_outcomes = {}
    client.on_request = None
    client.on_event = lambda event: None
    return client


class EventTests(unittest.TestCase):
    def test_terminal_event_waits_for_persistence(self):
        client = client_fixture()
        entered, release = threading.Event(), threading.Event()
        event = {'method': 'turn/completed', 'params': {
            'threadId': 't', 'turn': {'id': 'u', 'status': 'completed'}}}
        client.process = Mock(stdout=io.StringIO(json.dumps(event) + '\n'))
        def persist(value):
            entered.set()
            self.assertTrue(release.wait(2))
        client.on_event = persist
        reader = threading.Thread(target=client._read)
        reader.start()
        self.assertTrue(entered.wait(2))
        self.assertEqual(client.events(), [])
        release.set()
        reader.join(2)
        self.assertFalse(reader.is_alive())
        self.assertEqual(client.wait_turn('t', 'u', timeout=1)['status'], 'completed')

    def test_failed_persistence_never_publishes_terminal_event(self):
        client = client_fixture()
        event = {'method': 'turn/completed', 'params': {
            'threadId': 't', 'turn': {'id': 'u', 'status': 'completed'}}}
        client.process = Mock(stdout=io.StringIO(json.dumps(event) + '\n'))
        client.on_event = Mock(side_effect=RuntimeError('database unavailable'))
        client._read()
        self.assertEqual(client.events(), [])
        with self.assertRaisesRegex(CodexError, 'persistence failed'):
            client.wait_turn('t', 'u', timeout=1)

    def test_existing_callback_failure_prevents_completed_return(self):
        client = client_fixture()
        client._events = [{'method': 'turn/completed', 'params': {
            'threadId': 't', 'turn': {'id': 'u', 'status': 'completed'}}}]
        client.callback_errors = ['database unavailable']
        with self.assertRaisesRegex(CodexError, 'persistence failed'):
            client.wait_turn('t', 'u', timeout=1)


class TurnInterruptTests(unittest.TestCase):
    def event_rpc(self, client, *, confirmation='event'):
        calls = []

        def request(method, params, timeout=40):
            calls.append((method, params))
            if method == 'turn/interrupt':
                if confirmation == 'event':
                    with client._condition:
                        client._events.append({'method': 'turn/completed', 'params': {
                            'threadId': params['threadId'],
                            'turn': {'id': params['turnId'], 'status': 'interrupted'}}})
                        client._condition.notify_all()
                return {}
            if method == 'thread/read':
                if confirmation == 'idle':
                    return {'thread': {'id': params['threadId'], 'status': {'type': 'idle'}}}
                return {'thread': {'id': params['threadId'], 'status': {'type': 'active'}}}
            raise AssertionError('unexpected RPC: ' + method)

        client.request = request
        return calls

    def test_timeout_interrupts_and_confirms_only_current_turn(self):
        client = client_fixture()
        calls = self.event_rpc(client)
        with self.assertRaisesRegex(CodexError, 'Turn deadline exceeded'):
            client.wait_turn('current-thread', 'current-turn', timeout=0)
        self.assertEqual(calls, [('turn/interrupt', {
            'threadId': 'current-thread', 'turnId': 'current-turn'})])
        self.assertIsNone(client._current_turn)

    def test_tick_failure_preserves_original_error_after_confirmed_interrupt(self):
        client = client_fixture()
        calls = self.event_rpc(client)
        failure = RuntimeError('lease ownership lost')

        def tick():
            raise failure

        with self.assertRaisesRegex(RuntimeError, 'lease ownership lost') as caught:
            client.wait_turn('t', 'u', timeout=10, tick=tick)
        self.assertIs(caught.exception, failure)
        self.assertEqual(calls[0], ('turn/interrupt', {'threadId': 't', 'turnId': 'u'}))
        self.assertIsNone(client._current_turn)

    def test_persistence_failure_interrupts_and_confirms_via_same_thread_idle(self):
        client = client_fixture()
        calls = self.event_rpc(client, confirmation='idle')
        client.callback_errors = ['database unavailable']
        with self.assertRaisesRegex(CodexError, 'persistence failed'):
            client.wait_turn('t', 'u', timeout=1)
        self.assertEqual([method for method, _ in calls], ['turn/interrupt', 'thread/read'])
        self.assertEqual(calls[1][1], {'threadId': 't'})
        self.assertIsNone(client._current_turn)

    def test_unconfirmed_interrupt_keeps_original_error_and_marks_unknown(self):
        client = client_fixture()
        calls = self.event_rpc(client, confirmation='active')
        client._TURN_CONFIRM_TIMEOUT = 0
        with self.assertRaisesRegex(CodexError, 'Turn deadline exceeded') as caught:
            client.wait_turn('t', 'u', timeout=0)
        self.assertIn('Turn interruption outcome unknown', caught.exception.__notes__[0])
        self.assertEqual([method for method, _ in calls], ['turn/interrupt', 'thread/read'])
        self.assertEqual(client._current_turn, ('t', 'u'))


class SandboxTests(unittest.TestCase):
    def response(self, writable=True, network=False):
        return {'model': 'gpt-5.6-luna', 'reasoningEffort': 'max', 'sandbox': {
            'type': 'workspaceWrite' if writable else 'readOnly', 'networkAccess': network,
            'writableRoots': [], 'excludeSlashTmp': True, 'excludeTmpdirEnvVar': True}}

    def test_explicit_policy_and_native_confirmation(self):
        client = client_fixture()
        client.request = Mock(return_value=self.response(network=True))
        client.start_thread('.', writable=True, network_access=True)
        params = client.request.call_args.args[1]
        self.assertIs(params['config']['sandbox_workspace_write.network_access'], True)
        self.assertEqual(params['config']['sandbox_workspace_write.writable_roots'], [])

    def test_read_only_default_is_checked(self):
        client = client_fixture()
        client.request = Mock(return_value=self.response(writable=False))
        client.start_thread('.')
        client.request = Mock(return_value=self.response(writable=False, network=True))
        with self.assertRaisesRegex(CodexError, 'not confirmed'):
            client.start_thread('.')

    def test_network_or_scope_drift_is_rejected(self):
        client = client_fixture()
        response = self.response(network=True)
        client.request = Mock(return_value=response)
        with self.assertRaisesRegex(CodexError, 'not confirmed'):
            client.start_thread('.', writable=True)
        response['sandbox']['networkAccess'] = False
        response['sandbox']['writableRoots'] = [str(Path.cwd().parent)]
        with self.assertRaisesRegex(CodexError, 'unauthorized writable root'):
            client.start_thread('.', writable=True)

    def test_project_binding_is_forwarded_and_title_is_set_separately(self):
        client = client_fixture()
        calls = []

        def request(method, params):
            calls.append((method, params))
            if method == 'thread/start':
                return {**self.response(writable=False),
                        'thread': {'id': 'native-thread', 'projectId': 'project-1'}}
            if method == 'thread/name/set':
                return {}
            raise AssertionError('unexpected RPC: ' + method)

        client.request = request
        client.start_thread('.', instructions='prompt text', project_id='project-1', title='中文标题')
        self.assertEqual(calls[0][0], 'thread/start')
        self.assertEqual(calls[0][1]['projectId'], 'project-1')
        self.assertNotIn('title', calls[0][1])
        self.assertEqual(calls[1], ('thread/name/set', {
            'threadId': 'native-thread', 'name': '中文标题'}))

    def test_project_binding_mismatch_is_rejected_before_naming(self):
        client = client_fixture()
        calls = []

        def request(method, params):
            calls.append((method, params))
            return {**self.response(writable=False),
                    'thread': {'id': 'native-thread', 'projectId': 'other-project'}}

        client.request = request
        with self.assertRaisesRegex(CodexError, 'project binding'):
            client.start_thread('.', project_id='project-1', title='标题')
        self.assertEqual([method for method, _ in calls], ['thread/start'])


class CommandTests(unittest.TestCase):
    def test_optional_environment_is_forwarded_with_defaults(self):
        client = client_fixture()
        sent = []
        def write(message):
            sent.append(message)
            client._pending[message['id']].put({'result': {'exitCode': 0, 'stdout': '', 'stderr': ''}})
        client._write = write
        client.command_exec(['fixture'], '.', env={'TEMP': str(Path.cwd()), 'UNSET_ME': None})
        self.assertEqual(sent[0]['params']['env']['TEMP'], str(Path.cwd()))
        self.assertEqual(sent[0]['params']['env']['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertIsNone(sent[0]['params']['env']['UNSET_ME'])
        with self.assertRaisesRegex(ValueError, 'env must map'):
            client.command_exec(['fixture'], '.', env={'BAD=KEY': 'value'})

    def test_command_uses_native_sandbox_and_actual_output(self):
        client = client_fixture()
        sent = []
        def write(message):
            sent.append(message)
            client._pending[message['id']].put({'result': {
                'exitCode': 7, 'stdout': 'out', 'stderr': 'err'}})
        client._write = write
        result = client.command_exec(['python', 'test.py'], '.', network_access=False)
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(result['stderr'], 'err')
        self.assertEqual(client.active_command_ids, ())
        self.assertEqual(sent[0]['method'], 'command/exec')
        self.assertFalse(sent[0]['params']['sandboxPolicy']['networkAccess'])
        self.assertEqual(sent[0]['params']['processId'], result['process_id'])
        self.assertEqual(sent[0]['params']['sandboxPolicy']['writableRoots'], [str(Path.cwd())])

    def test_timeout_requires_original_exec_exit_after_terminate(self):
        client = client_fixture()
        sent = []
        client._write = sent.append
        def terminate(method, params, timeout):
            self.assertEqual(method, 'command/exec/terminate')
            self.assertEqual(params['processId'], sent[0]['params']['processId'])
            client._pending[sent[0]['id']].put({'result': {
                'exitCode': 130, 'stdout': '', 'stderr': 'terminated'}})
            return {}
        client.request = terminate
        result = client.command_exec(['python', 'test.py'], '.', timeout_seconds=0.001)
        self.assertTrue(result['timed_out'])
        self.assertTrue(result['interrupted'])
        self.assertEqual(result['exit_code'], 130)
        self.assertEqual(client.active_command_ids, ())

    def test_tick_can_interrupt_owned_command(self):
        client = client_fixture()
        sent = []
        client._write = sent.append
        def terminate(method, params, timeout):
            client._pending[sent[0]['id']].put({'result': {
                'exitCode': 130, 'stdout': '', 'stderr': ''}})
            return {}
        client.request = terminate
        result = client.command_exec(['python', 'test.py'], '.',
            tick=lambda: client.interrupt_command(client.active_command_ids[0]))
        self.assertTrue(result['interrupted'])
        with self.assertRaisesRegex(CodexError, 'not owned'):
            client.interrupt_command('someone-elses-command')

    def test_request_error_is_not_a_success_receipt(self):
        client = client_fixture()
        def write(message):
            client._pending[message['id']].put({'error': {'message': 'sandbox denied'}})
        client._write = write
        with self.assertRaisesRegex(CodexError, 'sandbox denied'):
            client.command_exec(['python', 'test.py'], '.')
        self.assertEqual(len(client.active_command_ids), 1)

    def test_terminate_ack_without_exit_stays_unknown(self):
        client = client_fixture()
        client._write = Mock()
        client.request = Mock(return_value={})
        # Advance only this module's monotonic clock, without sleeping ten seconds.
        from unittest.mock import patch
        with patch('team_runtime.codex.time.monotonic', side_effect=[0, 1, 1, 12]):
            with self.assertRaisesRegex(CodexError, 'termination outcome unknown'):
                client.command_exec(['python', 'test.py'], '.', timeout_seconds=0.001)
        self.assertEqual(len(client.active_command_ids), 1)

    def test_callback_failure_cannot_hide_behind_command_success(self):
        client = client_fixture()
        client.callback_errors = ['write failed']
        def write(message):
            client._pending[message['id']].put({'result': {'exitCode': 0, 'stdout': '', 'stderr': ''}})
        client._write = write
        with self.assertRaisesRegex(CodexError, 'persistence failed'):
            client.command_exec(['python', 'test.py'], '.')


class CloseTests(unittest.TestCase):
    def test_close_interrupts_tracked_turn_before_owned_process_exit(self):
        client = client_fixture()
        calls = []

        def request(method, params, timeout=40):
            calls.append((method, params))
            if method == 'turn/start':
                return {'turn': {'id': 'u'}}
            if method == 'turn/interrupt':
                with client._condition:
                    client._events.append({'method': 'turn/completed', 'params': {
                        'threadId': params['threadId'],
                        'turn': {'id': params['turnId'], 'status': 'interrupted'}}})
                    client._condition.notify_all()
                return {}
            raise AssertionError('unexpected RPC: ' + method)

        client.request = request
        client.start_turn('t', 'prompt')
        client.close()
        self.assertEqual(calls, [
            ('turn/start', {'threadId': 't', 'model': 'gpt-5.6-luna', 'effort': 'max',
                            'input': [{'type': 'text', 'text': 'prompt'}]}),
            ('turn/interrupt', {'threadId': 't', 'turnId': 'u'}),
        ])
        self.assertIsNone(client._current_turn)

    def test_with_body_error_survives_cleanup_error(self):
        client = client_fixture()
        client.close = Mock(side_effect=CodexError('cleanup exit unknown'))
        error = CodexError('original SpawnChild failure')
        with self.assertRaises(CodexError) as caught:
            with client:
                raise error
        self.assertIs(caught.exception, error)
        self.assertIn('cleanup exit unknown', caught.exception.__notes__[0])

    def test_close_error_without_body_error_is_not_hidden(self):
        client = client_fixture()
        client.close = Mock(side_effect=CodexError('cleanup exit unknown'))
        with self.assertRaisesRegex(CodexError, 'cleanup exit unknown'):
            with client:
                pass

    def test_native_launch_failure_and_no_active_confirm_not_started(self):
        client = client_fixture()
        def write(message):
            client._pending[message['id']].put({'error': {
                'message': 'Windows Sandbox SpawnChild/CreateProcessAsUserW error 5'}})
        client._write = write
        client.request = Mock(side_effect=CodexError('command/exec/terminate: -32600 no active command/exec'))
        client.process = Mock()
        client.process.poll.return_value = 0
        with self.assertRaisesRegex(CodexError, 'SpawnChild/CreateProcessAsUserW') as caught:
            with client:
                client.command_exec(['fixture'], '.')
        self.assertFalse(getattr(caught.exception, '__notes__', []))
        self.assertEqual(client.active_command_ids, ())
        self.assertEqual(next(iter(client.command_outcomes.values()))['status'], 'not-started')

    def test_unknown_exec_error_and_no_active_remain_unknown(self):
        client = client_fixture()
        def write(message):
            client._pending[message['id']].put({'error': {'message': 'transport outcome unknown'}})
        client._write = write
        client.request = Mock(side_effect=CodexError('command/exec/terminate: -32600 no active command/exec'))
        client.process = Mock()
        client.process.poll.return_value = 0
        with self.assertRaisesRegex(CodexError, 'transport outcome unknown') as caught:
            with client:
                client.command_exec(['fixture'], '.')
        self.assertIn('Command exits remain unconfirmed', caught.exception.__notes__[0])
        self.assertEqual(len(client.active_command_ids), 1)
        self.assertEqual(client.command_outcomes, {})

    def test_close_escalates_only_its_owned_process(self):
        client = client_fixture()
        client.process = Mock()
        client.process.poll.return_value = None
        client.process.wait.side_effect = [subprocess.TimeoutExpired('owned', 5),
                                          subprocess.TimeoutExpired('owned', 5), 9]
        client.close()
        client.process.terminate.assert_called_once_with()
        client.process.kill.assert_called_once_with()

    def test_close_retains_unknown_exit_failure(self):
        client = client_fixture()
        client.process = Mock()
        client.process.poll.return_value = None
        client.process.wait.side_effect = subprocess.TimeoutExpired('owned', 5)
        with self.assertRaisesRegex(CodexError, 'exit unknown'):
            client.close()


class TransportTests(unittest.TestCase):
    def test_real_stdio_round_trip_with_local_python_fixture(self):
        # This program implements only a test JSON transport. It cannot execute
        # argv, initialize Codex, access an API, or start a model session.
        fixture = '''
import json,sys
for line in sys.stdin:
    message=json.loads(line)
    if message.get('method')=='command/exec':
        result={'exitCode':3,'stdout':'fixture stdout','stderr':'fixture stderr'}
    else:
        result={}
    print(json.dumps({'id':message['id'],'result':result}),flush=True)
'''
        client = client_fixture()
        client.process = subprocess.Popen([sys.executable, '-u', '-c', fixture],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        reader = threading.Thread(target=client._read)
        reader.start()
        try:
            result = client.command_exec(['fixture-only'], '.', timeout_seconds=2)
            self.assertEqual(result['exit_code'], 3)
            self.assertEqual(result['stdout'], 'fixture stdout')
            self.assertEqual(result['stderr'], 'fixture stderr')
        finally:
            client.close()
            reader.join(2)
            client.process.stdout.close()
            client.process.stderr.close()
        self.assertFalse(reader.is_alive())


if __name__ == '__main__':
    unittest.main()
