"""Scoped organizational responsibility, readable proposals, and action receipts."""
from __future__ import annotations

from .store import ConflictError, _utc_now


class Coordination:
    @staticmethod
    def _close_grant(tx, data, grant, reason, *, revoked=True):
        grant.update(state='closed', ended_at=_utc_now(), end_reason=reason, revoked=revoked)
        for attempt in data['attempts'].values():
            if attempt.get('delegation_id') == grant['id'] and attempt['state'] == 'prepared':
                attempt.update(state='not-started', stop_confirmed=True, ended_at=_utc_now())
                record = tx.get('adaptive-dispatch', attempt['id'])
                tx.put('adaptive-dispatch', attempt['id'], {**record['data'], 'state':'not-started'}, expected_revision=record['revision'])

    def _acting(self, data, attempt_id):
        attempt, work = self._current_attempt(data, attempt_id)
        if attempt['state'] not in {'running', 'dispatching'} or data['stop_intent']:
            raise ConflictError('This execution no longer holds an active responsibility')
        grant = data.get('delegations', {}).get(attempt.get('delegation_id'), {})
        if grant.get('revoked'):
            raise ConflictError('This temporary coordination turn was revoked')
        return attempt, work

    def _scope(self, data, attempt_id, work_ids, *, accept=False):
        attempt, _ = self._acting(data, attempt_id)
        grant = data.get('delegations', {}).get(attempt.get('delegation_id'))
        if not grant and not attempt.get('delegation_id'):
            matches = [g for g in data.get('delegations', {}).values() if g['state'] == 'active'
                       and g['member'] == attempt.get('member', attempt['role'])
                       and set(work_ids) <= set(g['work_ids'])]
            if len(matches) == 1:
                grant = matches[0]
        if not grant or grant['state'] != 'active':
            raise ConflictError('No active local coordination delegation')
        if not set(work_ids) <= set(grant['work_ids']):
            raise ConflictError('Change exceeds the delegated work scope')
        if accept:
            for wid in work_ids:
                work = data['works'][wid]
                producer = data['attempts'].get(work['attempts'][-1], {}) if work['attempts'] else {}
                if producer.get('member', producer.get('role')) == grant['member']:
                    raise ConflictError('A local coordinator cannot accept its own result')
        return grant

    def propose(self, run_id, attempt_id, body, work_ids, *, operation_id=None):
        from .adaptive import ident, text
        text(body, 'proposal')
        def change(tx, data):
            attempt, work = self._acting(data, attempt_id)
            if not work or not work_ids or not set(work_ids) <= data['works'].keys():
                raise ValueError('A proposal needs an executing member and existing work IDs')
            proposal = {'id': ident('proposal'), 'member': attempt.get('member', attempt['role']),
                        'from_work': work['id'], 'work_ids': list(dict.fromkeys(work_ids)),
                        'body': body, 'state': 'pending', 'created_at': _utc_now()}
            data.setdefault('proposals', {})[proposal['id']] = proposal
            return {'proposal': proposal, 'instruction': 'Proposal recorded. Continue independent work or save your position and end this turn.'}
        return self._mutate(run_id, operation_id or ident('proposal'), 'coordination-proposed',
                            {'body': body, 'work_ids': work_ids}, change, actor=attempt_id)

    def delegate(self, run_id, member, work_ids, reason, *, proposal_id=None, operation_id=None):
        from .adaptive import ident, text
        text(member, 'member'); text(reason, 'reason')
        def change(tx, data):
            if data['stop_intent'] or data['status'] in {'completed', 'canceled'}:
                raise ConflictError('Run is stopped')
            if not work_ids or not set(work_ids) <= data['works'].keys():
                raise ValueError('Delegation requires existing work IDs')
            if not any(w.get('member', w['role']) == member for w in data['works'].values()):
                raise ValueError('Delegate must be an existing member')
            grants = data.setdefault('delegations', {})
            if any(g['state'] == 'active' and set(g['work_ids']) & set(work_ids) for g in grants.values()):
                raise ConflictError('A work responsibility already has a local coordinator')
            grant = {'id': ident('delegation'), 'member': member, 'work_ids': list(dict.fromkeys(work_ids)),
                     'reason': reason, 'state': 'active', 'created_at': _utc_now(), 'last_fingerprint': None}
            grants[grant['id']] = grant
            if proposal_id:
                proposal = data.get('proposals', {}).get(proposal_id)
                if not proposal or proposal['state'] != 'pending':
                    raise ConflictError('Proposal is not pending')
                proposal.update(state='adopted', delegation_id=grant['id'])
            return {'delegation': grant}
        return self._mutate(run_id, operation_id or ident('delegate'), 'coordination-delegated',
                            {'member': member, 'work_ids': work_ids, 'reason': reason, 'proposal_id': proposal_id}, change)

    def close_delegation(self, run_id, delegation_id, reason, *, attempt_id=None, operation_id=None):
        from .adaptive import ident, text
        text(reason, 'reason')
        def change(tx, data):
            grant = data.get('delegations', {}).get(delegation_id)
            if not grant:
                raise ValueError('Unknown delegation')
            if attempt_id:
                current, _ = self._acting(data, attempt_id)
                if current.get('member', current['role']) != grant['member']:
                    raise ConflictError('Only the delegated member can return this responsibility')
            self._close_grant(tx, data, grant, reason, revoked=attempt_id is None)
            return {'delegation': grant}
        return self._mutate(run_id, operation_id or ident('release'), 'coordination-returned',
                            {'delegation_id': delegation_id, 'reason': reason}, change, actor=attempt_id or 'coordinator')

    def resolve_proposal(self, run_id, proposal_id, reason, *, operation_id=None):
        from .adaptive import ident, text
        text(reason, 'reason')
        def change(tx, data):
            proposal = data.get('proposals', {}).get(proposal_id)
            if not proposal or proposal['state'] != 'pending':
                raise ConflictError('Proposal is not pending')
            proposal.update(state='resolved', resolution=reason)
            return {'proposal': proposal}
        return self._mutate(run_id, operation_id or ident('resolve'), 'proposal-resolved',
                            {'proposal_id': proposal_id, 'reason': reason}, change)

    @staticmethod
    def delegation_fingerprint(data, grant):
        from .adaptive import digest
        return digest({wid: data['works'][wid] for wid in grant['work_ids']})

    def prepare_local(self, run_id, delegation_id, owner, epoch):
        from .adaptive import ACTIVE_ATTEMPTS, ident, directory
        def change(tx, data):
            self._owner(data, owner, epoch)
            grant = data.get('delegations', {}).get(delegation_id)
            if not grant or grant['state'] != 'active' or data['stop_intent'] or data['status'] != 'running':
                raise ConflictError('Local coordination is not available')
            active = [a for a in data['attempts'].values() if a['state'] in ACTIVE_ATTEMPTS]
            if len(active) >= data['policy']['max_sessions']:
                raise ConflictError('No execution slot')
            if data['usage']['observed_tokens'] >= data['policy']['token_budget']:
                raise ConflictError('Observed budget exhausted')
            if any(a.get('member', a['role']) == grant['member'] for a in active):
                raise ConflictError('Member is currently busy; coordination remains queued')
            holder = next((w for w in data['works'].values() if w.get('member', w['role']) == grant['member']), None)
            if holder is None:
                raise ConflictError('Delegated member no longer has an assigned workspace')
            cwd = str(directory(data['workspace'], holder['directory']))
            from .adaptive import overlap
            if any(overlap(cwd, a['cwd']) and a['writable'] for a in active):
                raise ConflictError('Coordination inputs are being modified')
            attempt = {'id': ident('local'), 'work_id': None, 'delegation_id': grant['id'],
                       'member': grant['member'], 'role': holder['role'], 'cwd': cwd,
                       'writable': False, 'state': 'prepared', 'controller_epoch': epoch,
                       'assignment_epoch': epoch, 'thread_id': None, 'turn_id': None,
                       'native_phase': 'not-started', 'definition': data['definition'], 'created_at': _utc_now()}
            self._reserve_budget(data, attempt)
            attempt['coordination_fingerprint'] = self.delegation_fingerprint(data, grant)
            data['attempts'][attempt['id']] = attempt
            tx.put('adaptive-dispatch', attempt['id'], {'run_id': run_id, 'state': 'pending', 'attempt_id': attempt['id']})
            return {'attempt': attempt}
        return self._mutate(run_id, ident('prepare-local'), 'local-coordination-prepared',
                            {'delegation_id': delegation_id}, change)

    def replace_session(self, run_id, member, reason, *, operation_id=None):
        from .adaptive import ACTIVE_ATTEMPTS, ident, text
        text(reason, 'reason')
        def change(tx, data):
            if any(a.get('member', a['role']) == member and a['state'] in ACTIVE_ATTEMPTS for a in data['attempts'].values()):
                raise ConflictError('Confirm the previous member execution stopped before replacement')
            retired = {k: s for k, s in data['sessions'].items() if s.get('member', s['role']) == member}
            if not retired:
                raise ValueError('No saved session for this member')
            for key in retired:
                del data['sessions'][key]
            handoff = {'member': member, 'sessions': retired, 'reason': reason,
                       'definition': data['definition'], 'plan_revision': data['plan_revision'],
                       'work_ids': [w['id'] for w in data['works'].values() if w.get('member', w['role']) == member],
                       'created_at': _utc_now()}
            data.setdefault('handoffs', []).append(handoff)
            return {'handoff': handoff}
        return self._mutate(run_id, operation_id or ident('replace'), 'session-replaced',
                            {'member': member, 'reason': reason}, change)

    def effect(self, run_id, attempt_id, key, target, description, *, outcome=None, evidence=None, operation_id=None):
        """Reserve an action once; unknown outcomes require observation, not replay."""
        from .adaptive import ident, text, digest
        text(key, 'key'); text(target, 'target'); text(description, 'description')
        if outcome not in {None, 'succeeded', 'not-applied'}:
            raise ValueError('Outcome must be succeeded or not-applied after checking the target')
        if outcome:
            text(evidence, 'evidence')
        payload = {'key': key, 'target': target, 'description': description, 'outcome': outcome, 'evidence': evidence}
        def change(tx, data):
            attempt, work = self._acting(data, attempt_id)
            if operation_id:
                operations = data.setdefault('effect_operations', {})
                fingerprint = digest({'attempt_id': attempt_id, **payload})
                if operation_id in operations and operations[operation_id] != fingerprint:
                    raise ConflictError('Operation ID already identifies another external action')
                operations[operation_id] = fingerprint
            actions = data.setdefault('effects', {})
            previous = actions.get(key)
            binding = digest({'target': target, 'description': description})
            if previous and previous['binding'] != binding:
                raise ConflictError('Action key already identifies different content')
            if outcome:
                if not previous:
                    raise ConflictError('Register an action before recording its observation')
                if previous['state'] != 'unknown':
                    if previous['state'] != outcome:
                        raise ConflictError('Resolved action cannot be rewritten')
                    return {'effect': previous, 'execute': False}
                if previous['work_id'] != (work['id'] if work else None):
                    raise ConflictError('Only the originating responsibility can resolve this action')
                previous.update(state=outcome, evidence=evidence, observed_at=_utc_now(), observed_by=attempt_id)
                return {'effect': previous, 'execute': False}
            if previous:
                return {'effect': previous, 'execute': False, 'instruction': 'Inspect the target and record its actual outcome. Do not replay this action.'}
            record = {'key': key, 'target': target, 'description': description, 'binding': binding,
                      'state': 'unknown', 'work_id': work['id'] if work else None,
                      'attempt_id': attempt_id, 'created_at': _utc_now()}
            actions[key] = record
            return {'effect': record, 'execute': True, 'instruction': 'Perform once under the existing user authority; record the target observation before completion.'}
        # Do not return a cached execute=True receipt to a retransmitted native call.
        result = self._mutate(run_id, ident('effect'), 'external-action',
                              {**payload, 'operation_id': operation_id}, change, actor=attempt_id)
        return result
