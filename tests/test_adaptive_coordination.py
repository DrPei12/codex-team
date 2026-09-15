"""Real SQLite, workspace, CLI and HTTP checks for adaptive organization."""
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from team_runtime.adaptive import Adaptive, ConflictError
from team_runtime.adaptive_runner import Runner
from test_adaptive import work, complete


@pytest.fixture
def team(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    for folder in ['lead', 'a', 'b', 'other']:
        (root / folder).mkdir()
    e = Adaptive(tmp_path / 'state')
    rid = e.create(root, 'Investigate, divide work when useful, and deliver verified outcomes',
                   [work(w, directory=w, writable=True, member=w) for w in ['lead', 'a', 'b', 'other']],
                   authority='Edit the project and coordinate within the delegated outcome',
                   policy={'max_sessions': 3})['run_id']
    epoch = e.controller(rid, 'owner')['epoch']
    e.start(rid, 'owner', epoch)
    return e, rid, epoch


def active(e, rid, epoch, wid):
    a = e.prepare(rid, wid, 'owner', epoch)['attempt']
    e.send_start(rid, a['id'], 'owner', epoch)
    e.bind(rid, a['id'], thread_id='native-' + wid, turn_id=a['id'])
    return a


def test_member_proposes_then_coordinates_and_returns_with_same_native_identity(team):
    e, rid, epoch = team
    a = active(e, rid, epoch, 'lead')
    proposal = e.propose(rid, a['id'], 'I understand the failure and can coordinate its two investigations', ['a', 'b'])['proposal']
    assert proposal['state'] == 'pending'
    with pytest.raises(ConflictError):
        e._scope(e.run(rid)['data'], a['id'], ['a'])
    e.complete_attempt(rid, a['id'], e.artifact({'report': 'Root cause context', 'files': []}), stopped=True)
    grant = e.delegate(rid, 'lead', ['a', 'b'], 'Investigator has the relevant context', proposal_id=proposal['id'])['delegation']
    _, ref = complete(e, rid, epoch, 'a')
    unrelated = active(e, rid, epoch, 'other')
    local = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    assert local['member'] == 'lead' and not local['writable']
    e.send_start(rid, local['id'], 'owner', epoch)
    e.bind(rid, local['id'], thread_id='native-lead', turn_id='coordinate')
    e.accept(rid, 'a', ref['sha256'], 'Evidence checked', attempt_id=local['id'])
    data = e.run(rid)['data']
    e.revise(rid, data['plan_revision'], 'Consolidate follow-up', update=[{'id': 'b', 'goal': 'Validate the root cause'}], attempt_id=local['id'])
    assert e.run(rid)['data']['attempts'][unrelated['id']]['state'] == 'running'
    e.close_delegation(rid, grant['id'], 'Investigation handed back', attempt_id=local['id'])
    with pytest.raises(ConflictError, match='No active'):
        e.revise(rid, e.run(rid)['data']['plan_revision'], 'stale permission', update=[{'id': 'b', 'priority': 2}], attempt_id=local['id'])
    history = e.history(rid, 'coordination')
    assert history['events']


def test_local_scope_cannot_expand_authority_or_accept_own_output(team):
    e, rid, epoch = team
    grant = e.delegate(rid, 'lead', ['lead', 'a'], 'Bounded inspection')['delegation']
    _, ref = complete(e, rid, epoch, 'lead')
    a = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    e.send_start(rid, a['id'], 'owner', epoch)
    for changes in [dict(update=[{'id': 'other', 'priority': 1}]),
                    dict(update=[{'id': 'a', 'acceptance': 'skip validation'}]),
                    dict(add=[work('escape', directory='other', writable=True)]),
                    dict(definition='another goal')]:
        with pytest.raises(ConflictError):
            e.revise(rid, e.run(rid)['data']['plan_revision'], 'change', attempt_id=a['id'], **changes)
    with pytest.raises(ConflictError, match='own result'):
        e.accept(rid, 'lead', ref['sha256'], 'self approval', attempt_id=a['id'])
    with pytest.raises(ConflictError, match='already has'):
        e.delegate(rid, 'other', ['a'], 'overlap')


def test_local_new_work_and_automatic_end(team):
    e, rid, epoch = team
    grant = e.delegate(rid, 'lead', ['a'], 'Check evidence')['delegation']
    _, ref = complete(e, rid, epoch, 'a')
    a = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    e.send_start(rid, a['id'], 'owner', epoch)
    e.revise(rid, e.run(rid)['data']['plan_revision'], 'An independent check is useful',
             add=[work('check', directory='a', member='checker', depends_on=['a'])], attempt_id=a['id'])
    e.accept(rid, 'a', ref['sha256'], 'Checked', attempt_id=a['id'])
    e.complete_attempt(rid, a['id'], e.artifact({'report': 'Added check'}), stopped=True)
    _, check = complete(e, rid, epoch, 'check')
    a = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    e.send_start(rid, a['id'], 'owner', epoch)
    e.accept(rid, 'check', check['sha256'], 'Checked', attempt_id=a['id'])
    assert e.run(rid)['data']['delegations'][grant['id']]['state'] == 'closed'


def test_disjoint_revision_rebases_and_same_work_conflicts(team):
    e, rid, epoch = team
    base = e.run(rid)['data']['plan_revision']
    e.revise(rid, base, 'first', update=[{'id': 'a', 'priority': 4}])
    e.revise(rid, base, 'independent', update=[{'id': 'b', 'priority': 5}])
    with pytest.raises(ConflictError):
        e.revise(rid, base, 'conflict', update=[{'id': 'a', 'priority': 6}])


def test_readers_and_writers_do_not_race_but_independent_coordination_runs(team):
    e, rid, epoch = team
    active(e, rid, epoch, 'a')
    e.revise(rid, e.run(rid)['data']['plan_revision'], 'review', add=[work('read', directory='a')])
    with pytest.raises(ConflictError, match='workspace'):
        e.prepare(rid, 'read', 'owner', epoch)
    with pytest.raises(ConflictError, match='read boundary'):
        e.prepare_coordination(rid, 'owner', epoch)


def test_cross_state_claim_survives_controller_loss_and_releases_after_reconcile(team, tmp_path):
    e, rid, epoch = team
    a = active(e, rid, epoch, 'a')
    second = Adaptive(tmp_path / 'other-state')
    other = second.create(e.run(rid)['data']['workspace'], 'Other run', [work('x')], authority='Same project')['run_id']
    other_epoch = second.controller(other, 'other')['epoch']
    with pytest.raises(ConflictError, match='another Team'):
        second.start(other, 'other', other_epoch)
    def expire(tx, data):
        data['controller']['expires'] = 0
        return {}
    e._mutate(rid, 'expire', 'test-controller-crash', {}, expire)
    with pytest.raises(ConflictError, match='another Team'):
        second.start(other, 'other', other_epoch)
    observation = {'state': 'idle', 'thread_id': 'native-a', 'turn_id': a['id'],
                   'configuration': {}, 'background_terminals': []}
    for bad in [{'state': 'not-started'}, {**observation, 'thread_id': 'other'},
                {**observation, 'configuration': {'model': 'other'}}]:
        with pytest.raises(ConflictError):
            e.reconcile_observations(rid, {a['id']: bad}, e.artifact({'observation': bad}))
    with pytest.raises(ConflictError, match='receipt'):
        e.reconcile_observations(rid, {a['id']: observation}, e.artifact({'unrelated':True}))
    receipt = e.artifact({'before':e.run(rid)['data'], 'observations':{a['id']:observation}, 'files':[]})
    e.reconcile_observations(rid, {a['id']: observation}, receipt)
    second.start(other, 'other', other_epoch)


def test_session_replacement_keeps_work_history_and_refuses_active_member(team):
    e, rid, epoch = team
    a = active(e, rid, epoch, 'a')
    e.message(rid, 'Original evidence remains searchable', attempt_id=a['id'], note=True)
    with pytest.raises(ConflictError):
        e.replace_session(rid, 'a', 'fresh context')
    e.complete_attempt(rid, a['id'], e.artifact({'report': 'interrupted'}), outcome='interrupted', stopped=True)
    handoff = e.replace_session(rid, 'a', 'fresh context')['handoff']
    assert handoff['sessions'] and handoff['definition'] and handoff['work_ids'] == ['a']
    assert not e.run(rid)['data']['sessions']
    assert e.history(rid, 'Original evidence')['events']


def test_external_http_success_with_lost_response_is_observed_without_replay(team):
    e, rid, epoch = team
    a = active(e, rid, epoch, 'a')
    class Endpoint(BaseHTTPRequestHandler):
        writes = 0
        def log_message(self, *args):
            pass
        def do_POST(self):
            type(self).writes += 1
            self.close_connection = True  # action commits, response is lost
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'writes': self.writes, 'id': 'receipt-1'}).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    target = 'http://127.0.0.1:' + str(server.server_port)
    try:
        first = e.effect(rid, a['id'], 'publish-1', target, 'Publish one receipt', operation_id='native-retry')
        assert first['execute']
        with pytest.raises(Exception):
            urlopen(Request(target, data=b'x', method='POST'), timeout=3)
        assert not e.effect(rid, a['id'], 'publish-1', target, 'Publish one receipt', operation_id='native-retry')['execute']
        with pytest.raises(ConflictError, match='Operation ID'):
            e.effect(rid, a['id'], 'publish-2', target, 'Publish one receipt', operation_id='native-retry')
        with urlopen(target, timeout=3) as response:
            observed = response.read().decode()
        e.effect(rid, a['id'], 'publish-1', target, 'Publish one receipt', outcome='succeeded', evidence=observed)
        assert Endpoint.writes == 1
        assert e.run(rid)['data']['effects']['publish-1']['state'] == 'succeeded'
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_stop_revokes_native_mutating_tools(team):
    e, rid, epoch = team
    a = active(e, rid, epoch, 'a')
    e.stop(rid)
    result = Runner(e, rid)._request(a['id'], False, {'id': '1', 'method': 'item/tool/call',
                     'params': {'tool': 'team_propose', 'arguments': {'text': 'new plan', 'work_ids': ['b']}}})
    assert not result['success']


def test_current_worker_can_use_its_granted_local_responsibility(team):
    e, rid, epoch = team
    lead = active(e, rid, epoch, 'lead')
    e.delegate(rid, 'lead', ['a'], 'Relevant investigator')
    _, ref = complete(e, rid, epoch, 'a')
    result = Runner(e, rid)._request(lead['id'], False, {'id':'accept-local','method':'item/tool/call',
        'params':{'tool':'team_accept','arguments':{'work_id':'a','result_sha256':ref['sha256'],'rationale':'Checked the actual result'}}})
    assert result['success']
    assert e.run(rid)['data']['works']['a']['state'] == 'accepted'


def test_single_member_can_keep_identity_for_overall_coordination(tmp_path):
    root=tmp_path/'small';root.mkdir()
    e=Adaptive(tmp_path/'single-state')
    rid=e.create(root,'Single outcome',[work('one')],authority='Deliver the outcome')['run_id']
    epoch=e.controller(rid,'owner')['epoch'];e.start(rid,'owner',epoch)
    complete(e,rid,epoch,'one')
    a=e.prepare_coordination(rid,'owner',epoch)['attempt']
    assert a['member']=='one'


def test_budget_reservations_cover_inflight_and_release_unused_tokens(tmp_path):
    root = tmp_path/'project'; root.mkdir()
    e = Adaptive(tmp_path/'state')
    rid = e.create(root, 'Bounded task', [work('a'), work('b')], authority='Local work',
                   policy={'token_budget': 1, 'max_sessions': 2})['run_id']
    epoch = e.controller(rid, 'owner')['epoch']; e.start(rid, 'owner', epoch)
    a = e.prepare(rid, 'a', 'owner', epoch)['attempt']
    assert a['token_reservation'] == 1
    with pytest.raises(ConflictError, match='reserved'):
        e.prepare(rid, 'b', 'owner', epoch)
    e.complete_attempt(rid, a['id'], e.artifact({'report': 'No model started'}), outcome='not-started', stopped=True)
    assert e.prepare(rid, 'b', 'owner', epoch)['attempt']['token_reservation'] == 1


def test_revocation_interrupts_only_temporary_coordinator(team):
    import time
    e, rid, epoch = team
    grant = e.delegate(rid, 'lead', ['a'], 'Scoped coordination')['delegation']
    a = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    e.send_start(rid, a['id'], 'owner', epoch)
    e.bind(rid, a['id'], thread_id='lead-native', turn_id='local-turn')
    worker = active(e, rid, epoch, 'other')
    e.close_delegation(rid, grant['id'], 'The work has changed')
    with pytest.raises(ConflictError, match='revoked'):
        e._acting(e.run(rid)['data'], a['id'])
    calls = []
    class Client:
        def request(self, method, params, **kwargs): calls.append((method, params))
    runner = Runner(e, rid); runner.owner = 'owner'; runner.epoch = epoch
    runner.deadline = time.monotonic()+60; runner._heartbeat = time.monotonic()
    runner.tick(Client(), 'lead-native', 'local-turn')
    runner.tick(Client(), 'lead-native', 'local-turn')
    runner.tick(Client(), 'native-other', worker['id'])
    assert len(calls) == 1 and calls[0][0] == 'turn/interrupt'
    assert not e.run(rid)['data']['stop_intent']


def test_fresh_local_coordinator_starts_a_native_session(team, monkeypatch):
    import time
    import team_runtime.adaptive_runner as module
    e, rid, epoch = team
    grant = e.delegate(rid, 'lead', ['a'], 'Investigate together')['delegation']
    a = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    titles = []
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def start_thread(self, cwd, **kwargs):
            titles.append(kwargs['title'])
            return {'thread': {'id': 'new-local'}, 'model': 'gpt-5.6-luna', 'reasoningEffort': 'max', 'sandbox': {'type': 'readOnly'}}
        def mark(self): return 0
        def start_turn(self, *args, **kwargs): return {'id': 'turn-local'}
        def wait_turn(self, *args, **kwargs): return {'status': 'completed'}
        def text_for_turn(self, *args): return 'Reviewed current scope'
        def request(self, *args): return {'data': []}
    monkeypatch.setattr(module, 'CodexClient', Client)
    runner = Runner(e, rid); runner.owner = 'owner'; runner.epoch = epoch
    runner.deadline = time.monotonic()+60
    assert runner.execute(a)['outcome'] == 'succeeded'
    assert titles == ['Team · Local coordination · lead']
    assert e.run(rid)['data']['attempts'][a['id']]['thread_id'] == 'new-local'


def test_noop_coordinator_does_not_abandon_active_results(tmp_path):
    import time
    root = tmp_path/'project'; root.mkdir()
    e = Adaptive(tmp_path/'state')
    rid = e.create(root, 'Two independent checks', [work('a'), work('b')], authority='Read and check',
                   policy={'max_sessions': 3})['run_id']
    release = threading.Event()
    class ControlledRunner(Runner):
        coordination_count = 0
        def qualify_python(self): pass
        def qualify_project(self): pass
        def execute(self, attempt, *, coordinator=False):
            aid = attempt['id']
            e.send_start(rid, aid, self.owner, self.epoch)
            e.bind(rid, aid, thread_id='native-'+aid, turn_id='turn-'+aid)
            if coordinator:
                self.coordination_count += 1
                if self.coordination_count == 1:
                    release.set()
                else:
                    data = self._data()
                    for w in data['works'].values():
                        if w['state'] == 'result-ready': e.accept(rid, w['id'], w['result']['sha256'], 'Verified')
                    self.completion_request = 'Both results verified'
                    self.coordination_message_revision = self._data().get('message_revision', 0)
            elif attempt['work_id'] == 'b':
                assert release.wait(5)
                time.sleep(.15)
            ref = e.artifact({'report': 'Observed outcome', 'files': []})
            e.complete_attempt(rid, aid, ref, stopped=True)
    runner = ControlledRunner(e, rid)
    result = runner.run()
    assert result['status'] == 'completed', result
    assert runner.coordination_count >= 2


def test_revocation_before_dispatch_cancels_local_without_stopping_others(team):
    import time
    e, rid, epoch = team
    grant = e.delegate(rid, 'lead', ['a'], 'Coordinate')['delegation']
    local = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    other = active(e, rid, epoch, 'other')
    e.close_delegation(rid, grant['id'], 'Reorganize')
    with pytest.raises(ConflictError): e.send_start(rid, local['id'], 'owner', epoch)
    runner = Runner(e, rid); runner.owner='owner'; runner.epoch=epoch; runner.deadline=time.monotonic()+10
    assert runner.execute(local)['outcome'] == 'not-started'
    assert e.run(rid)['data']['attempts'][other['id']]['state'] == 'running'
    assert not e.run(rid)['data']['stop_intent']


def test_member_transfer_closes_orphan_delegation(team):
    e, rid, epoch = team
    grant = e.delegate(rid, 'lead', ['a'], 'Coordinate')['delegation']
    local = e.prepare_local(rid, grant['id'], 'owner', epoch)['attempt']
    e.revise(rid, 1, 'Transfer responsibility', update=[{'id':'lead','member':'other'}])
    data = e.run(rid)['data']
    assert data['delegations'][grant['id']]['state'] == 'closed'
    assert data['attempts'][local['id']]['state'] == 'not-started'
    with pytest.raises(ConflictError): e.prepare_local(rid, grant['id'], 'owner', epoch)


def test_claim_from_rolled_back_start_is_reclaimed_after_lease_expires(tmp_path):
    from team_runtime.workspace_claims import WorkspaceClaims
    project=tmp_path/'project'; project.mkdir()
    first=Adaptive(tmp_path/'first'); second=Adaptive(tmp_path/'second')
    rid=first.create(project,'First',[work('a')],authority='Local work')['run_id']
    first.controller(rid,'owner')
    def crash(tx,data):
        WorkspaceClaims().claim(first.root,rid,data['workspace'])
        raise RuntimeError('Process failed before run transaction committed')
    with pytest.raises(RuntimeError): first._mutate(rid,'crash','crash',{},crash)
    other=second.create(project,'Second',[work('b')],authority='Local work')['run_id']
    epoch=second.controller(other,'other')['epoch']
    with pytest.raises(ConflictError): second.start(other,'other',epoch)
    def expire(tx,data):
        data['controller']['expires']=0
        return {}
    first._mutate(rid,'expire','expire',{},expire)
    assert second.start(other,'other',epoch)['status']=='running'


def test_local_consolidation_keeps_original_criteria_for_overall_review(team):
    e,rid,epoch=team
    grant=e.delegate(rid,'lead',['a','b'],'Coordinate')['delegation']
    local=e.prepare_local(rid,grant['id'],'owner',epoch)['attempt']
    e.send_start(rid,local['id'],'owner',epoch)
    e.revise(rid,1,'Consolidate outcomes',update=[{'id':'a','state':'superseded'}],
             add=[work('replacement',directory='a')],attempt_id=local['id'])
    data=e.run(rid)['data']
    assert any(p['state']=='pending' and p['original_acceptance']==data['works']['a']['acceptance'] for p in data['proposals'].values())
    assert data['works']['replacement']['scope_criteria'][0]['work_id']=='a'


def test_direct_finish_releases_workspace_claim(tmp_path):
    import sqlite3
    from team_runtime.workspace_claims import WorkspaceClaims
    project=tmp_path/'project'; project.mkdir()
    e=Adaptive(tmp_path/'state')
    rid=e.create(project,'One result',[work('a')],authority='Local work')['run_id']
    epoch=e.controller(rid,'owner')['epoch']; e.start(rid,'owner',epoch)
    _, ref=complete(e,rid,epoch)
    e.accept(rid,'a',ref['sha256'],'Verified')
    assert e.finish(rid,'Delivered')['status']=='completed'
    with sqlite3.connect(WorkspaceClaims().path) as db:
        assert db.execute('SELECT count(*) FROM claims').fetchone()[0]==0
