"""Codex Team 0.3 durable work, attempt, queue and acceptance semantics.

No model or external operation runs inside a database transaction. The native
runner consumes durable dispatch records and reports observations back here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import uuid

from .store import Store, ConflictError, _utc_now
from .rules import validate_policy
from .coordination import Coordination
from .workspace_claims import WorkspaceClaims


TERMINAL_WORK = {"accepted", "failed", "canceled", "rejected", "superseded"}
ACTIVE_ATTEMPTS = {"prepared", "dispatching", "running", "unknown"}


def ident(prefix):
    return prefix + "-" + uuid.uuid4().hex[:16]


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be nonempty text")
    return value


def directory(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("directory must be relative to the project")
    parts = relative.replace("\\", "/").split("/")
    if ".." in parts or ":" in relative:
        raise ValueError("directory escapes the project")
    result = (Path(root) / relative).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError("directory escapes the project through a link")
    return result


def overlap(first, second):
    first, second = Path(first).resolve(), Path(second).resolve()
    return first.is_relative_to(second) or second.is_relative_to(first)


class Adaptive(Coordination):
    def __init__(self, state):
        self.root = Path(state).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.root / "team.sqlite3")

    def artifact(self, value, suffix="json"):
        raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        sha = hashlib.sha256(raw).hexdigest()
        folder = self.root / "artifacts" / "v03"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (sha + "." + suffix)
        try:
            with path.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                import os
                os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ConflictError("Artifact content mismatch")
        return {"path": str(path), "sha256": sha}

    def read_artifact(self, ref):
        path = Path(ref["path"]).resolve()
        if not path.is_relative_to(self.root / "artifacts") or path.is_symlink():
            raise ValueError("Artifact reference outside this Team state")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ConflictError("Artifact changed after registration")
        return json.loads(raw)

    def run(self, run_id):
        record = self.store.get("adaptive-run", run_id)
        if record is None:
            raise ValueError("Unknown adaptive run: " + run_id)
        return record

    def _mutate(self, run_id, operation_id, action, payload, change, actor="operator"):
        request = {"action": action, "payload": payload, "actor": actor}
        def apply(tx):
            record = tx.get("adaptive-run", run_id)
            if record is None:
                raise ValueError("Unknown adaptive run")
            data = record["data"]
            result = change(tx, data)
            event = tx.event(run_id, action, {"actor": actor, "details": payload, "result": result})
            data["updated_at"] = event["created_at"]
            tx.put("adaptive-run", run_id, data, expected_revision=record["revision"])
            return {"run_id": run_id, "event_seq": event["seq"], **result}
        return self.store.command(run_id, operation_id, request, apply)

    def _work(self, data, spec):
        if not isinstance(spec, dict):
            raise ValueError("work must be an object")
        supported = {"id", "title", "goal", "role", "directory", "writable", "depends_on",
                     "acceptance", "kind", "priority", "member"}
        if set(spec) - supported:
            raise ValueError("Unknown work fields: " + ", ".join(sorted(set(spec) - supported)))
        work_id = spec.get("id") or ident("work")
        text(work_id, "id")
        if work_id in data["works"]:
            raise ConflictError("Work id already exists")
        relative = spec.get("directory", ".")
        directory(data["workspace"], relative)
        writable = spec.get("writable", False)
        if type(writable) is not bool:
            raise ValueError("writable must be boolean")
        dependencies = spec.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
            raise ValueError("depends_on must contain work ids")
        priority = spec.get("priority", 0)
        if type(priority) is not int or not -100 <= priority <= 100:
            raise ValueError("priority must be an integer from -100 to 100")
        work = {"id": work_id, "revision": 1, "title": text(spec.get("title"), "title"),
                "goal": text(spec.get("goal"), "goal"), "role": text(spec.get("role", work_id), "role"),
                "directory": relative, "writable": writable, "depends_on": list(dict.fromkeys(dependencies)),
                "acceptance": text(spec.get("acceptance"), "acceptance"), "kind": spec.get("kind", "execution"),
                "priority": priority, "state": "queued", "epoch": 0, "attempts": [],
                "result": None, "acceptance_record": None, "waiting_on": [], "note": "",
                "created_at": _utc_now()}
        work['member'] = text(spec.get('member', work['role']), 'member')
        work['changed_at_revision'] = data['plan_revision'] + 1
        if work["kind"] not in {"execution", "assistance", "review", "repair"}:
            raise ValueError("Unknown work kind")
        data["works"][work_id] = work
        return work

    @staticmethod
    def validate_graph(data):
        visited, active = set(), set()
        def visit(work_id):
            if work_id in active:
                raise ConflictError("Dependency/wait cycle at " + work_id)
            if work_id in visited:
                return
            if work_id not in data["works"]:
                raise ValueError("Unknown dependency: " + work_id)
            active.add(work_id)
            work = data["works"][work_id]
            for dependency in work["depends_on"] + work["waiting_on"]:
                visit(dependency)
            active.remove(work_id)
            visited.add(work_id)
        for work_id in data["works"]:
            visit(work_id)

    def create(self, workspace, definition, works, *, authority, policy=None, operation_id=None, title="Team项目"):
        workspace = Path(workspace).resolve()
        if overlap(workspace, self.root):
            raise ValueError("Project and Team state must be separate directories")
        if not workspace.is_dir():
            raise ValueError("Project workspace must exist")
        text(definition, "definition")
        text(authority, "authority")
        settings = validate_policy({'token_budget': 2000000, 'max_subagents_per_session': 0, **(policy or {}), "network_access": (policy or {}).get("network_access", True)})
        if settings['max_subagents_per_session']:
            raise ValueError('Adaptive Team schedules native sessions; max_subagents_per_session must be 0')
        definition_ref = self.artifact({"text": definition, "source": "operator supplied project definition"})
        run_id = ident("run")
        data = {"schema_version": "0.3", "id": run_id, "title": text(title, "title"),
                "workspace": str(workspace), "definition": definition_ref, "definition_revision": 1,
                "authority": authority, "policy": settings, "status": "ready", "stop_intent": None,
                "works": {}, "attempts": {}, "acceptances": [], "messages": [], "sessions": {},
                "plan_revision": 1, "changes": [], "controller": None, "controller_epoch": 0,
                "delegations": {}, "proposals": {}, "effects": {}, "handoffs": [],
                "usage": {"observed_tokens": 0, "turns": {}, "coverage": "notification-dependent"},
                "active_seconds": 0.0, "created_at": _utc_now(), "coordination_cursor": 0}
        if not isinstance(works, list):
            raise ValueError("works must be a list")
        for spec in works:
            self._work(data, spec)['changed_at_revision'] = 1
        self.validate_graph(data)
        request = {"workspace": str(workspace), "definition": definition, "works": works,
                   "authority": authority, "policy": settings, "title": title}
        def apply(tx):
            for other in tx.list("adaptive-run"):
                if (other["data"]["workspace"] == str(workspace)
                        and other["data"]["status"] not in {"completed", "canceled"}):
                    raise ConflictError("This project already has an unfinished run: " + other["id"])
            tx.put("adaptive-run", run_id, data)
            event = tx.event(run_id, "run-created", {"definition": definition_ref, "authority": authority})
            return {"run_id": run_id, "event_seq": event["seq"], "status": "ready"}
        return self.store.command("adaptive-create", operation_id or ident("create"), request, apply)

    def snapshot(self, run_id):
        record = self.run(run_id)
        return {**record, "definition_text": self.read_artifact(record["data"]["definition"])["text"],
                "events": self.store.tail_events(run_id, 100)}

    def events(self, run_id, after=0, limit=100):
        self.run(run_id)
        return self.store.events(run_id, after=after, limit=limit)

    def history(self, run_id, query, *, after=0, limit=20):
        self.run(run_id)
        if type(limit) is not int or not 1 <= limit <= 100 or type(after) is not int or after < 0:
            raise ValueError("Invalid history cursor/limit")
        terms = str(query).casefold().split()
        found, cursor = [], after
        while len(found) < limit:
            page = self.store.events(run_id, after=cursor, limit=100)
            if not page:
                break
            for event in page:
                cursor = event["seq"]
                if all(term in json.dumps(event, ensure_ascii=False).casefold() for term in terms):
                    found.append(event)
                if len(found) == limit:
                    break
        return {"events": found, "next_cursor": cursor}

    def controller(self, run_id, owner, *, epoch=None):
        def change(tx, data):
            current = data["controller"]
            if current and current["owner"] != owner and current["expires"] > time.time():
                raise ConflictError("Another controller owns this run")
            if epoch is not None:
                if not current or current["owner"] != owner or current["epoch"] != epoch or current["expires"] <= time.time():
                    raise ConflictError("Controller responsibility expired")
            else:
                if any(a["state"] in ACTIVE_ATTEMPTS for a in data["attempts"].values()):
                    raise ConflictError("In-flight attempts require reconciliation before controller replacement")
                data["controller_epoch"] += 1
                epoch_value = data["controller_epoch"]
                current = {"owner": owner, "epoch": epoch_value}
            current["expires"] = time.time() + 30
            data["controller"] = current
            return dict(current)
        return self._mutate(run_id, ident("lease"), "controller-claim", {"owner": owner, "epoch": epoch}, change)

    @staticmethod
    def _owner(data, owner, epoch):
        current = data["controller"]
        if not current or current["owner"] != owner or current["epoch"] != epoch or current["expires"] <= time.time():
            raise ConflictError("Controller responsibility is not current")

    def start(self, run_id, owner, epoch):
        def change(tx, data):
            self._owner(data, owner, epoch)
            if data["status"] not in {"ready", "paused", "waiting", "running"}:
                raise ConflictError("Run is not ready to start")
            if any(a["state"] in ACTIVE_ATTEMPTS for a in data["attempts"].values()):
                raise ConflictError("Reconcile previous attempts before starting")
            WorkspaceClaims().claim(self.root, run_id, data['workspace'])
            data.update(status="running", stop_intent=None)
            for work in data["works"].values():
                if work["state"] == "paused":
                    work["state"] = "queued"
            return {"status": "running"}
        return self._mutate(run_id, ident("start"), "run-started", {}, change)

    @staticmethod
    def eligible(data):
        eligible = []
        for work in data["works"].values():
            if work["state"] not in {"queued", "waiting"} or work.get("recovery_required"):
                continue
            if all(data["works"][dep]["state"] == "accepted" for dep in work["depends_on"] + work["waiting_on"]):
                eligible.append(work)
        return sorted(eligible, key=lambda w: (-(w["priority"] + w.get('queue_age', 0)), w["created_at"], w["id"]))

    def validate_result(self, run_id, work_id, expected_hash):
        data = self.run(run_id)["data"]
        work = data["works"].get(work_id)
        if not work or not work["result"] or work["result"]["sha256"] != expected_hash:
            raise ConflictError("Result identity changed")
        result = self.read_artifact(work["result"])
        for file in result.get("files", []):
            path = Path(file["path"])
            if not path.resolve().is_relative_to(Path(data["workspace"]).resolve()) or path.is_symlink():
                raise ConflictError("Result file escapes project or is a symlink")
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != file.get("sha256"):
                raise ConflictError("Result file changed since submission: " + str(path))
        for file in result.get("removed", []):
            path = Path(file["path"])
            if not path.resolve().is_relative_to(Path(data["workspace"]).resolve()) or path.exists():
                raise ConflictError("Removed result path no longer matches its receipt")
        return result

    @staticmethod
    def _reserve_budget(data, attempt):
        active = [a for a in data['attempts'].values() if a['state'] in ACTIVE_ATTEMPTS]
        reserved = sum(max(0, a.get('token_reservation', 0) - a.get('observed_tokens', 0)) for a in active)
        available = data['policy']['token_budget'] - data['usage']['observed_tokens'] - reserved
        if available < 1:
            raise ConflictError('Token budget is exhausted or reserved by in-flight work')
        slots = max(1, data['policy']['max_sessions'] - len(active))
        attempt.update(token_reservation=max(1, available // slots), observed_tokens=0)

    def prepare(self, run_id, work_id, owner, epoch, *, operation_id=None):
        current = self.run(run_id)["data"]
        target = current["works"].get(work_id)
        if target:
            for dep in target["depends_on"] + target["waiting_on"]:
                source = current["works"].get(dep)
                if source and source["state"] == "accepted":
                    self.validate_result(run_id, dep, source["result"]["sha256"])
        def change(tx, data):
            self._owner(data, owner, epoch)
            if data["status"] != "running" or data["stop_intent"]:
                raise ConflictError("Run is stopped or not running")
            work = data["works"].get(work_id)
            if not work or work not in self.eligible(data):
                raise ConflictError("Work is not eligible")
            active = [a for a in data["attempts"].values() if a["state"] in ACTIVE_ATTEMPTS]
            if len(active) >= data["policy"]["max_sessions"]:
                raise ConflictError("No authorized execution slot")
            if data["usage"]["observed_tokens"] >= data["policy"]["token_budget"]:
                raise ConflictError("Observed token budget exhausted")
            if len(work["attempts"]) >= data["policy"]["max_repair_attempts"] + 1:
                raise ConflictError("Work attempt budget exhausted")
            cwd = directory(data["workspace"], work["directory"])
            for attempt in active:
                if attempt.get('member', attempt['role']) == work.get('member', work['role']):
                    raise ConflictError("Role already has an active responsibility")
                if (work["writable"] or attempt["writable"]) and overlap(cwd, attempt["cwd"]):
                    raise ConflictError("Shared writable workspace already owned")
            work["epoch"] += 1
            for queued in self.eligible(data):
                queued['queue_age'] = 0 if queued['id'] == work_id else queued.get('queue_age', 0) + 1
            attempt_id = ident("attempt")
            attempt = {"id": attempt_id, "work_id": work_id, "work_revision": work["revision"],
                       "assignment_epoch": work["epoch"], "controller_epoch": epoch,
                       "role": work["role"], "cwd": str(cwd), "writable": work["writable"],
                       "state": "prepared", "thread_id": None, "turn_id": None,
                       "native_phase": "not-started",
                       "inputs": {dep: data["works"][dep]["acceptance_record"]
                                  for dep in work["depends_on"] + work["waiting_on"]},
                       "definition": data["definition"], "created_at": _utc_now()}
            attempt['member'] = work.get('member', work['role'])
            self._reserve_budget(data, attempt)
            data["attempts"][attempt_id] = attempt
            work["attempts"].append(attempt_id)
            work["state"] = "assigned"
            tx.put("adaptive-dispatch", attempt_id, {"run_id": run_id, "state": "pending", "attempt_id": attempt_id})
            return {"attempt": attempt}
        return self._mutate(run_id, operation_id or ident("prepare"), "work-assigned", {"work_id": work_id}, change)

    def send_start(self, run_id, attempt_id, owner, epoch):
        def change(tx, data):
            self._owner(data, owner, epoch)
            if data["stop_intent"] or data["status"] != "running":
                raise ConflictError("Stop intent prevents dispatch")
            attempt = data["attempts"][attempt_id]
            if attempt.get('delegation_id') and data.get('delegations', {}).get(attempt['delegation_id'], {}).get('state') != 'active':
                raise ConflictError('Temporary coordination was closed before dispatch')
            work = data["works"].get(attempt["work_id"])
            if attempt["state"] != "prepared" or (work and attempt["assignment_epoch"] != work["epoch"]):
                raise ConflictError("Attempt is not prepared/current")
            record = tx.get("adaptive-dispatch", attempt_id)
            attempt["state"] = "dispatching"
            attempt["native_phase"] = "thread-starting"
            if work:
                work["state"] = "acknowledged"
            tx.put("adaptive-dispatch", attempt_id, {**record["data"], "state": "in-flight"}, expected_revision=record["revision"])
            return {"attempt_id": attempt_id, "state": "dispatching"}
        return self._mutate(run_id, "send-start:" + attempt_id, "send-start", {}, change)

    def prepare_coordination(self, run_id, owner, epoch):
        def change(tx, data):
            self._owner(data, owner, epoch)
            if data["stop_intent"] or data["status"] != "running":
                raise ConflictError("Stopped run cannot start coordination")
            active = [a for a in data['attempts'].values() if a['state'] in ACTIVE_ATTEMPTS]
            if len(active) >= data['policy']['max_sessions']:
                raise ConflictError('No authorized coordination slot')
            if any(a.get('member', a['role']) == 'team-coordinator' or a['writable'] for a in active):
                raise ConflictError('Coordinate at a stable read boundary')
            if data["usage"]["observed_tokens"] >= data["policy"]["token_budget"]:
                raise ConflictError("Observed budget exhausted")
            members = {w.get('member', w['role']) for w in data['works'].values()}
            member = next(iter(members)) if len(members) == 1 else 'team-coordinator'
            if any(a.get('member', a['role']) == member for a in active):
                raise ConflictError('The overall coordinator member is busy')
            holder = next((w for w in data['works'].values() if w.get('member', w['role']) == member), None)
            attempt_id = ident("coordination")
            attempt = {"id": attempt_id, "work_id": None, "role": "team-coordinator",
                       "cwd": str(directory(data['workspace'], holder['directory'])) if holder else data["workspace"], "writable": False, "assignment_epoch": epoch,
                       "controller_epoch": epoch, "state": "prepared", "thread_id": None,
                       "native_phase": "not-started",
                       "turn_id": None, "member": member, "definition": data["definition"], "created_at": _utc_now()}
            self._reserve_budget(data, attempt)
            data["attempts"][attempt_id] = attempt
            tx.put("adaptive-dispatch", attempt_id, {"run_id": run_id, "state": "pending", "attempt_id": attempt_id})
            return {"attempt": attempt}
        return self._mutate(run_id, ident("prepare-control"), "coordination-prepared", {}, change)

    @staticmethod
    def _current_attempt(data, attempt_id):
        attempt = data["attempts"].get(attempt_id)
        if not attempt:
            raise ValueError("Unknown attempt")
        if attempt["work_id"] is None:
            return attempt, None
        work = data["works"][attempt["work_id"]]
        if attempt["assignment_epoch"] != work["epoch"] or attempt["work_revision"] != work["revision"]:
            raise ConflictError("Attempt belongs to an outdated assignment")
        return attempt, work

    def bind(self, run_id, attempt_id, *, thread_id, turn_id=None, configuration=None):
        def change(tx, data):
            attempt = data["attempts"][attempt_id]
            work = None
            if attempt["work_id"] is not None:
                attempt, work = self._current_attempt(data, attempt_id)
            if attempt["state"] not in {"dispatching", "running"}:
                raise ConflictError("Cannot bind a non-active attempt")
            if attempt["thread_id"] and attempt["thread_id"] != thread_id:
                raise ConflictError("Attempt already bound to another thread")
            attempt["thread_id"] = text(thread_id, "thread_id")
            attempt["native_phase"] = "thread-bound"
            if turn_id:
                if attempt["turn_id"] and attempt["turn_id"] != turn_id:
                    raise ConflictError("Attempt already bound to another turn")
                attempt.update(turn_id=turn_id, state="running", native_phase="turn-bound")
                if work:
                    work["state"] = "working"
            key = digest({"role": attempt.get('member', attempt['role']), "cwd": attempt["cwd"], "writable": attempt["writable"]})
            confirmed = configuration if configuration is not None else data["sessions"].get(key, {}).get("configuration", {})
            if configuration is not None:
                attempt["configuration"] = configuration
            data["sessions"][key] = {"thread_id": thread_id, "role": attempt["role"],
                                     "member": attempt.get('member', attempt['role']),
                                     "cwd": attempt["cwd"], "writable": attempt["writable"],
                                     "configuration": confirmed, "last_attempt": attempt_id}
            return {"attempt_id": attempt_id, "thread_id": thread_id, "turn_id": turn_id, "configuration": confirmed}
        return self._mutate(run_id, ident("bind"), "native-binding", {"attempt_id": attempt_id}, change)

    def native_event(self, run_id, attempt_id, event):
        method = event.get("method", "")
        params = event.get("params", {})
        if method not in {"turn/completed", "item/completed", "thread/tokenUsage/updated", "model/rerouted"}:
            return None
        from .history import _safe
        safe_event = _safe(event)
        def change(tx, data):
            if attempt_id not in data["attempts"]:
                raise ValueError("Unknown event attempt")
            if method == "thread/tokenUsage/updated":
                usage = params.get("tokenUsage", {})
                total = usage.get("total", {}).get("totalTokens")
                last = usage.get("last", {}).get("totalTokens")
                turn = params.get("turnId")
                thread = params.get("threadId")
                if turn and thread and type(total) is int and type(last) is int:
                    key = thread + ":" + turn
                    previous = data["usage"]["turns"].get(key, -1)
                    if total > previous:
                        data["usage"]["observed_tokens"] += last
                        data["usage"]["turns"][key] = total
                        attempt = data['attempts'][attempt_id]
                        attempt['observed_tokens'] = attempt.get('observed_tokens', 0) + last
                        if attempt.get('token_reservation') and attempt['observed_tokens'] >= attempt['token_reservation']:
                            data.update(stop_intent='pause', status='pause-requested')
                    if data["usage"]["observed_tokens"] >= data["policy"]["token_budget"]:
                        data.update(stop_intent="pause", status="pause-requested")
            if method == "model/rerouted":
                data.update(stop_intent="pause", status="pause-requested")
            return {"attempt_id": attempt_id, "native": safe_event}
        return self._mutate(run_id, "native:" + attempt_id + ":" + digest(safe_event),
                            "native-observation", {"attempt_id": attempt_id}, change, actor="native")

    def message(self, run_id, body, *, attempt_id=None, operation_id=None, note=False, author="operator"):
        text(body, "message")
        def change(tx, data):
            if not attempt_id and author == "operator" and data["status"] in {"completed", "canceled"}:
                raise ConflictError("This run has ended; start a successor for new user input")
            work_id = None
            if attempt_id:
                attempt, work = self._current_attempt(data, attempt_id)
                if attempt["state"] not in ACTIVE_ATTEMPTS:
                    raise ConflictError("Attempt is no longer active")
                work_id = work["id"] if work else None
                if note and work:
                    work["note"] = body
            message = {"id": ident("message"), "body": body, "work_id": work_id,
                       "attempt_id": attempt_id, "author": author, "type": "note" if note else "message", "created_at": _utc_now()}
            data["messages"].append(message)
            if not attempt_id and author == "operator":
                data["message_revision"] = data.get("message_revision", 0) + 1
            return {"message": message}
        return self._mutate(run_id, operation_id or ident("message"), "work-note" if note else "message",
                            {"body": body, "attempt_id": attempt_id, "note": note}, change, actor=attempt_id or author)

    def invalidate(self, run_id, work_id, reason, *, operation_id=None):
        """Preserve old acceptance and isolate only its dependency descendants."""
        text(reason, "reason")
        def change(tx, data):
            if data["status"] in {"completed", "canceled"}:
                raise ConflictError("Terminal run requires a successor")
            if work_id not in data["works"]:
                raise ValueError("Unknown work")
            affected = {work_id}
            while True:
                found = {w["id"] for w in data["works"].values()
                         if set(w["depends_on"] + w["waiting_on"]) & affected}
                if found <= affected:
                    break
                affected |= found
            if any(a["work_id"] in affected and a["state"] in ACTIVE_ATTEMPTS for a in data["attempts"].values()):
                raise ConflictError("Pause and confirm affected attempts before invalidation")
            for record in data["acceptances"]:
                if record["work_id"] in affected and record["valid"]:
                    record.update(valid=False, invalidated_at=_utc_now(), invalidation_reason=reason)
            for wid in affected:
                work = data["works"][wid]
                work['changed_at_revision'] = data['plan_revision'] + 1
                if work["state"] not in {"superseded", "canceled", "rejected"}:
                    work.update(state="waiting", recovery_required=True, invalidation_reason=reason)
            data["plan_revision"] += 1
            return {"affected_work_ids": sorted(affected), "reason": reason}
        return self._mutate(run_id, operation_id or ident("invalidate"), "evidence-invalidated",
                            {"work_id": work_id, "reason": reason}, change, actor="coordinator")

    def request(self, run_id, attempt_id, target_work, question, *, wait=True, operation_id=None):
        text(question, "question")
        if type(wait) is not bool:
            raise ValueError("wait must be boolean")
        def change(tx, data):
            attempt, source = self._current_attempt(data, attempt_id)
            if attempt["state"] not in {"dispatching", "running"} or data["stop_intent"]:
                raise ConflictError("Requesting attempt is not active")
            target = data["works"].get(target_work)
            if not source or not target or target_work == source["id"]:
                raise ValueError("Choose another registered work responsibility")
            request = self._work(data, {"title": "协助：" + source["title"], "goal": question,
                                       "role": target["role"], "directory": target["directory"],
                                       "member": target.get('member', target['role']),
                                       "writable": False, "kind": "assistance", "priority": source["priority"] + (1 if source["priority"] < 100 else 0),
                                       "acceptance": "根据原始资料回答请求并说明依据、适用条件与未知项。"})
            request["requested_by"] = source["id"]
            if wait:
                source["waiting_on"].append(request["id"])
                source['changed_at_revision'] = data['plan_revision'] + 1
            message = {"id": ident("message"), "body": question, "work_id": request["id"],
                       "from_work": source["id"], "target_work": target_work, "attempt_id": attempt_id,
                       "type": "request", "created_at": _utc_now()}
            data["messages"].append(message)
            self.validate_graph(data)
            data["plan_revision"] += 1
            return {"work_id": request["id"], "state": "queued", "waiting": wait,
                    "instruction": "请求已登记；等待时保存继续位置并结束当前回合，运行程序会在结果接受后继续本工作。"}
        return self._mutate(run_id, operation_id or ident("request"), "collaboration-requested",
                            {"attempt_id": attempt_id, "target": target_work, "question": question, "wait": wait}, change, actor=attempt_id)

    def complete_attempt(self, run_id, attempt_id, result, *, outcome="succeeded", stopped=False):
        if outcome not in {"succeeded", "failed", "interrupted", "canceled", "unknown", "not-started"}:
            raise ValueError("Unknown attempt outcome")
        self.read_artifact(result)
        def change(tx, data):
            attempt = data["attempts"].get(attempt_id)
            if not attempt:
                raise ValueError("Unknown attempt")
            if attempt["state"] not in ACTIVE_ATTEMPTS:
                raise ConflictError("Terminal attempt cannot be reopened")
            attempt.update(state=outcome, result=result, ended_at=_utc_now(), stop_confirmed=stopped)
            work = data["works"].get(attempt["work_id"])
            current = work is None or (attempt["assignment_epoch"] == work["epoch"] and attempt["work_revision"] == work["revision"])
            record = tx.get("adaptive-dispatch", attempt_id)
            tx.put("adaptive-dispatch", attempt_id, {**record["data"], "state": "unknown" if outcome == "unknown" else "observed"}, expected_revision=record["revision"])
            if current and work:
                if outcome == "succeeded":
                    if any(data["works"][dep]["state"] != "accepted" for dep in work["waiting_on"]):
                        work["state"] = "waiting"
                    else:
                        work.update(state="result-ready", result=result)
                elif outcome == "unknown":
                    work["state"] = "waiting"
                    data.update(status="needs-reconciliation", stop_intent="pause")
                elif data["stop_intent"] or outcome == "interrupted":
                    work["state"] = "paused" if stopped else "waiting"
                else:
                    work["state"] = "waiting"
                    work["recovery_required"] = True
            if outcome == "unknown":
                data.update(status="needs-reconciliation", stop_intent="pause")
            grant = data.get('delegations', {}).get(attempt.get('delegation_id'))
            if grant and grant['state'] == 'active':
                grant['last_fingerprint'] = attempt.get('coordination_fingerprint') if outcome == 'succeeded' else None
                failures = sum(a.get('delegation_id') == grant['id'] and a['state'] == 'failed' for a in data['attempts'].values())
                if failures > data['policy']['max_repair_attempts']:
                    self._close_grant(tx, data, grant, 'Local execution requires overall coordination after repeated failure', revoked=False)
            return {"attempt_id": attempt_id, "outcome": outcome, "late": not current, "work_state": work["state"] if work else None}
        return self._mutate(run_id, "complete:" + attempt_id + ":" + outcome, "attempt-finished",
                            {"attempt_id": attempt_id, "result": result, "outcome": outcome, "stopped": stopped}, change, actor="native")

    def accept(self, run_id, work_id, result_hash, rationale, *, actor="coordinator", operation_id=None, attempt_id=None):
        text(rationale, "rationale")
        self.validate_result(run_id, work_id, result_hash)
        if actor not in {"coordinator", "operator", "user"} and not attempt_id:
            raise ValueError("Acceptance requires the designated coordinator or operator")
        def change(tx, data):
            if data['stop_intent'] or data['status'] in {'completed', 'canceled'}:
                raise ConflictError('Cannot accept results after a stop or completion')
            if attempt_id:
                self._scope(data, attempt_id, [work_id], accept=True)
            work = data["works"].get(work_id)
            if not work or work["state"] != "result-ready" or work["result"]["sha256"] != result_hash:
                raise ConflictError("Work/result is not ready for this acceptance")
            self.read_artifact(work["result"])
            if any(a['state'] in ACTIVE_ATTEMPTS and a['writable'] and overlap(a['cwd'], directory(data['workspace'], work['directory'])) for a in data['attempts'].values()):
                raise ConflictError('Result workspace is still being modified')
            if any(e['state'] == 'unknown' and e['work_id'] == work_id for e in data.get('effects', {}).values()):
                raise ConflictError('Resolve this work external action before acceptance')
            record = {"id": ident("acceptance"), "work_id": work_id, "work_revision": work["revision"],
                      "result": work["result"], "criteria": work["acceptance"], "actor": attempt_id or actor,
                      "rationale": rationale, "created_at": _utc_now(), "valid": True}
            data["acceptances"].append(record)
            work.update(state="accepted", acceptance_record=record["id"])
            for grant in data.get('delegations', {}).values():
                if grant['state'] == 'active' and all(data['works'][wid]['state'] in {'accepted', 'superseded'} for wid in grant['work_ids']):
                    self._close_grant(tx, data, grant, 'Delegated outcomes accepted', revoked=False)
            return {"acceptance": record}
        return self._mutate(run_id, operation_id or ident("accept"), "result-accepted",
                            {"work_id": work_id, "result_hash": result_hash, "rationale": rationale}, change, actor=actor)

    def revise(self, run_id, base_revision, reason, *, add=None, update=None, definition=None, operation_id=None, attempt_id=None):
        text(reason, "reason")
        definition_ref = self.artifact({"text": text(definition, "definition"), "reason": reason}) if definition is not None else None
        payload = {"base_revision": base_revision, "reason": reason, "add": add or [], "update": update or [], "definition": definition_ref}
        def change(tx, data):
            if data["plan_revision"] != base_revision:
                touched = {p.get('id') for p in update or []}
                touched |= {dep for p in (add or []) + (update or []) for dep in p.get('depends_on', [])}
                if (type(base_revision) is not int or base_revision < 1 or base_revision > data['plan_revision']
                        or definition_ref or data.get('definition_plan_revision', 0) > base_revision
                        or any(data['works'].get(wid, {}).get('changed_at_revision', data['plan_revision']) > base_revision for wid in touched)):
                    raise ConflictError("Plan changed; inspect affected work before retrying")
            if data["status"] in {"completed", "canceled"}:
                raise ConflictError("Terminal run requires a successor")
            if data['stop_intent'] and attempt_id:
                raise ConflictError('Stopped execution cannot revise the plan')
            grant = None
            if attempt_id:
                if definition_ref:
                    raise ConflictError('Local coordination cannot change the project definition')
                grant = self._scope(data, attempt_id, [p.get('id') for p in update or []])
                for spec in add or []:
                    candidates = [data['works'][wid] for wid in grant['work_ids']]
                    target = directory(data['workspace'], spec.get('directory', '.'))
                    if not any(target.is_relative_to(directory(data['workspace'], w['directory'])) and (not spec.get('writable') or w['writable']) for w in candidates):
                        raise ConflictError('New work exceeds delegated workspace permissions')
                    if not set(spec.get('depends_on', [])) <= set(grant['work_ids']):
                        raise ConflictError('New dependencies exceed local coordination scope')
            updated_ids = set()
            for patch in update or []:
                work_id = patch.get("id")
                work = data["works"].get(work_id)
                if not work:
                    raise ValueError("Unknown work for update")
                if any(data["attempts"][aid]["state"] in ACTIVE_ATTEMPTS for aid in work["attempts"]):
                    raise ConflictError("Affected work must reach a confirmed boundary before revision")
                if set(patch) - {"id", "goal", "acceptance", "depends_on", "priority", "role", "member", "state", "note"}:
                    raise ValueError("Unknown or unauthorized work change")
                if patch.get("state") not in {None, "queued", "superseded", "rejected", "failed"}:
                    raise ValueError("Use result acceptance or control actions for this state")
                if work["state"] in TERMINAL_WORK:
                    raise ConflictError("Terminal work requires a successor, not reopening")
                old = json.loads(json.dumps(work))
                if grant and ('acceptance' in patch or ('depends_on' in patch and not set(patch['depends_on']) <= set(grant['work_ids']))):
                    raise ConflictError('Local changes preserve acceptance criteria and dependency scope')
                work.update({key: val for key, val in patch.items() if key != "id"})
                if grant and patch.get('state') == 'superseded':
                    proposal = {'id':ident('proposal'), 'member':grant['member'], 'from_work':work_id,
                                'work_ids':[work_id], 'body':'Review removal or consolidation of this delivery responsibility: '+reason,
                                'original_goal':old['goal'], 'original_acceptance':old['acceptance'],
                                'state':'pending', 'created_at':_utc_now()}
                    data.setdefault('proposals', {})[proposal['id']] = proposal
                text(work["goal"], "goal")
                text(work["acceptance"], "acceptance")
                text(work["role"], "role")
                text(work.get('member', work['role']), 'member')
                if type(work["priority"]) is not int or not -100 <= work["priority"] <= 100:
                    raise ValueError("Invalid priority")
                if not isinstance(work["depends_on"], list) or any(not isinstance(dep, str) for dep in work["depends_on"]):
                    raise ValueError("Invalid dependencies")
                work["revision"] += 1
                work['changed_at_revision'] = data['plan_revision'] + 1
                work["epoch"] += 1
                work.pop("recovery_required", None)
                if work["state"] not in {"superseded", "rejected", "failed"}:
                    work.update(state="queued", result=None)
                data["changes"].append({"old_work": old, "reason": reason})
                updated_ids.add(work_id)
            for spec in add or []:
                created = self._work(data, spec)
                if grant:
                    created['scope_criteria'] = [{'work_id':wid, 'goal':data['works'][wid]['goal'],
                                                  'acceptance':data['works'][wid]['acceptance']} for wid in grant['work_ids']]
                    grant['work_ids'].append(created['id'])
            members = {w.get('member', w['role']) for w in data['works'].values()}
            for current_grant in data.get('delegations', {}).values():
                if current_grant['state'] == 'active' and current_grant['member'] not in members:
                    self._close_grant(tx, data, current_grant, 'Member responsibility was transferred')
            self.validate_graph(data)
            if definition_ref:
                if any(a["state"] in ACTIVE_ATTEMPTS for a in data["attempts"].values()):
                    raise ConflictError("Definition revision requires a safe boundary for active work")
                data["definition"] = definition_ref
                data["definition_revision"] += 1
                data['definition_plan_revision'] = data['plan_revision'] + 1
            data["plan_revision"] += 1
            data["changes"].append({"plan_revision": data["plan_revision"], **payload})
            return {"plan_revision": data["plan_revision"], "updated_work_ids": sorted(updated_ids)}
        return self._mutate(run_id, operation_id or ident("change"), "plan-revised", payload, change, actor=attempt_id or "coordinator")

    def stop(self, run_id, intent="pause"):
        if intent not in {"pause", "cancel"}:
            raise ValueError("Unknown stop intent")
        def change(tx, data):
            if data["status"] in {"completed", "canceled"}:
                return {"status": data["status"], "already_terminal": True}
            data.update(stop_intent=intent, status=intent + "-requested")
            for attempt in data["attempts"].values():
                if attempt["state"] == "prepared":
                    attempt.update(state="not-started", stop_confirmed=True)
                    work = data["works"].get(attempt["work_id"])
                    if work:
                        work["state"] = "paused"
                    dispatch = tx.get("adaptive-dispatch", attempt["id"])
                    tx.put("adaptive-dispatch", attempt["id"], {**dispatch["data"], "state": "not-started"}, expected_revision=dispatch["revision"])
            return {"status": data["status"]}
        return self._mutate(run_id, ident("stop"), "stop-requested", {"intent": intent}, change)

    def settle(self, run_id, owner, epoch, *, elapsed=0):
        def change(tx, data):
            self._owner(data, owner, epoch)
            data["active_seconds"] += max(0, elapsed)
            active = [a for a in data["attempts"].values() if a["state"] in ACTIVE_ATTEMPTS]
            if active:
                data.update(status='needs-reconciliation', stop_intent='pause', controller=None)
                return {'status': 'needs-reconciliation', 'unconfirmed_attempts': [a['id'] for a in active]}
            if data["stop_intent"]:
                data["status"] = "canceled" if data["stop_intent"] == "cancel" else "paused"
                if data["status"] == "canceled":
                    for work in data["works"].values():
                        if work["state"] not in TERMINAL_WORK:
                            work["state"] = "canceled"
            elif data["status"] != "completed":
                data["status"] = "waiting"
            data["controller"] = None
            return {"status": data["status"]}
        result = self._mutate(run_id, ident("settle"), "controller-settled", {"elapsed": elapsed}, change)
        if result.get('unconfirmed_attempts'):
            raise ConflictError('Native work remains in flight; reconciliation is required')
        WorkspaceClaims().release(self.root, run_id)
        return result

    def reconcile_observations(self, run_id, observations, snapshot_ref):
        receipt = self.read_artifact(snapshot_ref)
        before = receipt.get('before', {})
        if before.get('id') != run_id or receipt.get('observations') != observations or not isinstance(receipt.get('files'), list):
            raise ConflictError('Recovery receipt does not bind this run and its observations')
        def change(tx, data):
            current = data["controller"]
            if current and current["expires"] > time.time():
                raise ConflictError("Controller still active; request pause and wait for settlement")
            for attempt in data["attempts"].values():
                if attempt["state"] not in ACTIVE_ATTEMPTS:
                    continue
                observation = observations.get(attempt["id"])
                recorded = before.get('attempts', {}).get(attempt['id'], {})
                if any(recorded.get(key) != attempt.get(key) for key in ('thread_id','turn_id','configuration','controller_epoch','assignment_epoch')):
                    raise ConflictError('Recovery receipt belongs to another execution binding')
                if not observation or observation.get("state") not in {"idle", "not-started"}:
                    raise ConflictError("Missing stop observation for " + attempt["id"])
                if observation['state'] == 'not-started':
                    if attempt.get('thread_id') or attempt.get('native_phase') not in {'not-started', 'thread-starting'}:
                        raise ConflictError('Bound native execution requires an idle observation')
                elif (observation.get('thread_id') != attempt.get('thread_id')
                      or observation.get('turn_id') != attempt.get('turn_id')
                      or observation.get('background_terminals') != []
                      or observation.get('configuration') != attempt.get('configuration', {})):
                    raise ConflictError('Stop observation does not match the native execution binding')
                attempt.update(state="not-started" if observation["state"] == "not-started" else "interrupted",
                               stop_confirmed=True, reconciliation=observation, ended_at=_utc_now())
                work = data["works"].get(attempt["work_id"])
                if work and work["state"] not in TERMINAL_WORK:
                    work["state"] = "paused"
                    work["note"] = work["note"] or "从当前产物和原始记录继续；此前没有业务完成证明。"
                dispatch = tx.get("adaptive-dispatch", attempt["id"])
                tx.put("adaptive-dispatch", attempt["id"], {**dispatch["data"], "state": "reconciled"}, expected_revision=dispatch["revision"])
            data.update(status="paused", stop_intent="pause", controller=None, reconciliation=snapshot_ref)
            return {"status": "paused", "observations": observations, "snapshot": snapshot_ref}
        result = self._mutate(run_id, ident("reconcile"), "run-reconciled", {"snapshot": snapshot_ref}, change)
        WorkspaceClaims().release(self.root, run_id)
        return result

    def amend_policy(self, run_id, policy, reason, *, operation_id=None):
        settings = validate_policy({'token_budget': 2000000, 'max_subagents_per_session': 0, **policy})
        if settings['max_subagents_per_session']:
            raise ValueError('Adaptive Team schedules native sessions; max_subagents_per_session must be 0')
        text(reason, "reason")
        def change(tx, data):
            if data["status"] not in {"ready", "paused", "waiting"} or any(a["state"] in ACTIVE_ATTEMPTS for a in data["attempts"].values()):
                raise ConflictError("Reconcile/stop the run before amending resource policy")
            previous = data["policy"]
            data["policy"] = settings
            data["changes"].append({"previous_policy": previous, "policy": settings, "reason": reason})
            return {"policy": settings, "previous_policy": previous}
        return self._mutate(run_id, operation_id or ident("policy"), "policy-amended",
                            {"policy": settings, "reason": reason}, change, actor="operator")

    def finish(self, run_id, summary, *, actor="coordinator", expected_message_revision=None):
        text(summary, "summary")
        def change(tx, data):
            if data["stop_intent"] or data["status"] != "running":
                raise ConflictError("Cannot finish a stopped run")
            if expected_message_revision is not None and data.get("message_revision", 0) != expected_message_revision:
                raise ConflictError("New user input requires another coordination judgment")
            if not data["works"] or any(w["state"] not in {"accepted", "superseded"} for w in data["works"].values()):
                raise ConflictError("Unaccepted work remains")
            if any(a["state"] in ACTIVE_ATTEMPTS for a in data["attempts"].values()):
                raise ConflictError("Native execution still active")
            if any(e['state'] == 'unknown' for e in data.get('effects', {}).values()):
                raise ConflictError('Unresolved external actions remain')
            if any(p['state'] == 'pending' for p in data.get('proposals', {}).values()):
                raise ConflictError('Unresolved coordination proposals remain')
            for grant in data.get('delegations', {}).values():
                if grant['state'] == 'active':
                    grant.update(state='closed', ended_at=_utc_now(), end_reason='Run delivered')
            data.update(status="completed", final_summary=summary, accepted_by=actor, completed_at=_utc_now())
            return {"status": "completed", "summary": summary, "actor": actor}
        result = self._mutate(run_id, ident("finish"), "run-completed", {"summary": summary}, change, actor=actor)
        WorkspaceClaims().release(self.root, run_id)
        return result
