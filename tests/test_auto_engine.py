"""Controller regression tests: real SQLite/Git, explicitly simulated Codex only.

No test in this module starts a model process or contacts any external service.
The autouse fixture fails closed unless a test installs its scripted client.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

import team_runtime.engine as runtime
from team_runtime.codex import CodexClient, CodexError
from team_runtime.engine import Engine, git, now
from team_runtime.rules import digest
from team_runtime.store import ConflictError


def proposal(*, multi=False, read_only=False):
    packages = [{
        "id": pid, "title": pid, "goal": "Inspect and implement assigned behavior",
        "depends_on": [], "write_paths": [] if read_only else [pid],
        "acceptance_notes": "The declared behavioral gate passes",
    } for pid in (["core", "docs"] if multi else ["core"])]
    return {
        "schema_version": "0.2", "objective": "Deliver a verified local change",
        "questions": [], "assumptions": [],
        "mode": "multi-session" if multi else "single-session",
        "allocation_reason": "Explicit disjoint source ownership",
        "checkpoint": {"title": "Review evidence", "requires_user_acceptance": True},
        "requirements": [{"id": "requirement-" + p["id"], "text": "Verify " + p["id"],
                          "owner": p["id"], "gate_ids": ["behavior"]} for p in packages],
        "work_packages": packages,
        "gates": [{"id": "behavior", "argv": ["python", "verify.py"],
                   "timeout_seconds": 10, "description": "Execute behavioral assertions"}],
    }


class ScriptedCodex:
    """In-process protocol double; its callbacks perform only test-owned edits."""

    def __init__(self, script, **callbacks):
        self.script = script
        self.callbacks = callbacks
        self.cwd = None
        self.payload = None
        self.output_schema = None
        self.commands = {}
        self.interrupted_commands = set()

    def __enter__(self):
        self.script["clients"].append(self)
        return self

    def __exit__(self, *args):
        return False

    def start_thread(self, cwd, **kwargs):
        self.cwd = Path(cwd)
        self.script["sessions"].append({"cwd": str(cwd), **kwargs})
        thread_id = self._next_thread_id()
        project_id = kwargs.get("project_id")
        if project_id is not None and "reported_project_id" in self.script:
            project_id = self.script["reported_project_id"]
        thread = self._thread_record(thread_id, cwd=cwd, project_id=project_id,
                                     model=kwargs["model"],
                                     reasoning=kwargs["effort"])
        self.script.setdefault("native_threads", {})[thread_id] = thread
        return {"approvalPolicy": "never", "approvalsReviewer": "user",
                "thread": thread,
                "cwd": str(self.script.get("reported_cwd", cwd)),
                "model": self.script.get("reported_model", kwargs["model"]),
                "modelProvider": "openai",
                "reasoningEffort": kwargs["effort"],
                "sandbox": self.sandbox(cwd, writable=kwargs.get("writable", False),
                                        network_access=kwargs.get("network_access", False))}

    def _next_thread_id(self):
        ids = self.script.get("start_thread_ids")
        if ids:
            return ids.pop(0)
        return self.script.get("start_thread_id", "simulated-thread")

    @staticmethod
    def _thread_record(thread_id, *, cwd=".", project_id=None, status=None,
                       model="gpt-5.6-luna", reasoning="max", name=None):
        """Return the Thread shape from protocol-0.153.4/v2."""
        status = dict(status or {"type": "idle"})
        if status.get("type") == "active":
            status.setdefault("activeFlags", [])
        return {
            "id": thread_id, "projectId": project_id,
            "cwd": str(Path(cwd).resolve()), "model": model,
            "modelProvider": "openai", "reasoningEffort": reasoning,
            "name": name, "cliVersion": "test-double", "createdAt": 0,
            "updatedAt": 0, "ephemeral": False, "preview": False,
            "sessionId": "session-" + str(thread_id), "source": "cli",
            "status": status or {"type": "idle"}, "turns": [],
        }

    @staticmethod
    def _project_record(project_id, name, roots, *, metadata=None, position=0):
        """Return the Project shape from protocol-0.153.4/v2."""
        return {
            "id": project_id, "name": name,
            "roots": [{"path": str(Path(root["path"] if isinstance(root, dict) else root).resolve())}
                      for root in roots],
            "metadata": dict(metadata or {}), "position": position,
            "createdAt": 0, "updatedAt": 0, "recencyAt": None,
        }

    def _projects(self):
        return self.script.setdefault("native_projects", [])

    def _find_project(self, project_id):
        for project in self._projects():
            if project.get("id") == project_id:
                return project
        raise CodexError("project not found: " + str(project_id))

    def _project_list(self, params):
        pages = self.script.get("native_project_pages")
        if pages is not None:
            cursor = params.get("cursor")
            index = int(cursor) if cursor is not None else 0
            page = pages[index] if index < len(pages) else []
            if isinstance(page, dict):
                return {"data": list(page.get("data", [])),
                        "nextCursor": page.get("nextCursor")}
            return {"data": list(page),
                    "nextCursor": str(index + 1) if index + 1 < len(pages) else None}
        return {"data": list(self._projects()),
                "nextCursor": self.script.get("native_project_next_cursor")}

    def _project_import(self, params):
        key = params["idempotencyKey"]
        imports = self.script.setdefault("native_project_imports", {})
        if key in imports:
            return {"project": self._find_project(imports[key])}
        project_id = self.script.get("next_native_project_id")
        if project_id is None:
            project_id = "native-project-" + str(len(self._projects()) + 1)
        project = self._project_record(project_id, params["name"], params["roots"],
                                       metadata=params.get("metadata"))
        self._projects().append(project)
        imports[key] = project_id
        self.script.setdefault("native_project_imports_seen", []).append(dict(params))
        return {"project": project}

    @staticmethod
    def sandbox(cwd, *, writable=True, network_access=False):
        return {"type": "workspaceWrite" if writable else "readOnly",
                "networkAccess": network_access, "writableRoots": [str(Path(cwd).resolve())] if writable else [],
                "excludeTmpdirEnvVar": True, "excludeSlashTmp": True}

    validate_sandbox = staticmethod(CodexClient.validate_sandbox)

    @property
    def active_command_ids(self):
        return tuple(self.commands)

    def interrupt_command(self, process_id):
        if process_id not in self.commands:
            raise CodexError("Test command is not owned by this client")
        self.interrupted_commands.add(process_id)
        self.commands[process_id].terminate()

    def command_exec(self, argv, cwd, *, network_access=False, timeout_seconds=120, tick=None, env=None):
        # Deliberately local test execution, NOT proof of any native sandbox capability.
        # Real processes are confined by fixture construction to interpreter probes
        # and test-created Gate scripts; no App Server or model is launched.
        process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(env or {})})
        process_id = "simulated-command-" + str(process.pid)
        self.commands[process_id] = process
        timed_out = False
        deadline = time.monotonic() + timeout_seconds
        try:
            while True:
                if tick:
                    tick()
                if time.monotonic() >= deadline:
                    timed_out = True
                    process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    continue
            result = {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr,
                      "sandbox": self.sandbox(cwd, network_access=network_access),
                      "timed_out": timed_out, "interrupted": process_id in self.interrupted_commands,
                      "process_id": process_id}
            self.script["commands"].append({"argv": list(argv), "cwd": str(cwd), "result": result,
                                            "test_double": True})
            return result
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            self.commands.pop(process_id, None)

    def mark(self):
        return 0

    def start_turn(self, thread_id, prompt, **kwargs):
        self.payload = json.loads(prompt)
        self.output_schema = kwargs.get("output_schema")
        self.script["turns"].append(self.payload)
        return {"id": "simulated-turn"}

    def wait_turn(self, *args, **kwargs):
        if self.payload is None and "native" in self.script:
            return {"id": args[1], "status": "interrupted"}
        if self.output_schema == runtime.SUPERVISION_SCHEMA:
            callback = self.script.get("supervisor")
            if callback:
                callback(self)
        if "assigned_package" in self.payload:
            callback = self.script.get("worker")
            if callback:
                callback(self)
            return {"id": "simulated-turn", "status": self.script.get("worker_status", "completed")}
        return {"id": "simulated-turn", "status": "completed"}

    def text_for_turn(self, *args):
        if "brief" in self.payload:
            return json.dumps(self.script["proposal"])
        if self.output_schema == runtime.SUPERVISION_SCHEMA:
            return json.dumps({"verdict": "on-track", "summary": "Explicit simulated supervision; no real model",
                               "feedback": "", "findings": []})
        if self.output_schema:
            return json.dumps({"verdict": "approved", "summary": "Simulated review only",
                               "findings": [], "requirements": [
                {"id": r["id"], "satisfied": True, "evidence": "Test fixture review"}
                for r in self.payload["proposal"]["requirements"]]})
        return "Explicit simulated worker result; no model was run."

    def request(self, method, params):
        self.script["requests"].append((method, params))
        if method == "project/list":
            return self._project_list(params)
        if method == "project/read":
            return {"project": self._find_project(params["projectId"])}
        if method == "project/import":
            return self._project_import(params)
        if method == "thread/metadata/update":
            thread_id = params["threadId"]
            native = self.script.get("native", {}).get(thread_id)
            thread = self.script.setdefault("native_threads", {}).setdefault(
                thread_id, self._thread_record(thread_id))
            if not self.script.get("ignore_metadata_update"):
                project_id = params.get("projectId")
                if "metadata_update_project_id" in self.script:
                    project_id = self.script["metadata_update_project_id"]
                thread["projectId"] = project_id
                if native is not None:
                    native["project_id"] = project_id
            return {"thread": thread}
        if method == "thread/name/set":
            thread_id = params["threadId"]
            thread = self.script.setdefault("native_threads", {}).setdefault(
                thread_id, self._thread_record(thread_id))
            thread["name"] = params["name"]
            return {}
        if "native" in self.script and method.startswith("thread/"):
            native = self.script["native"].get(params["threadId"])
            if native is None:
                raise CodexError("unknown native thread: " + params["threadId"])
            if method == "thread/resume":
                resumed_id = native.get("resume_thread_id", params["threadId"])
                thread = self._thread_record(
                    resumed_id, cwd=native.get("cwd", params["cwd"]),
                    project_id=native.get("resume_project_id"),
                    status={"type": native.get("resume_status", "idle")},
                    model=native.get("model", params["model"]),
                    reasoning=params["config"]["model_reasoning_effort"])
                if "resume_project_id" in native:
                    thread["projectId"] = native["resume_project_id"]
                return {"approvalPolicy": "never", "approvalsReviewer": "user",
                        "thread": thread,
                        "cwd": native.get("cwd", params["cwd"]), "model": native.get("model", params["model"]),
                        "modelProvider": "openai",
                        "reasoningEffort": params["config"]["model_reasoning_effort"],
                        "sandbox": native.get("sandbox", self.sandbox(params["cwd"], writable=params["sandbox"] == "workspace-write"))}
            if method == "thread/read":
                thread = self._thread_record(
                    params["threadId"], cwd=native.get("cwd", "."),
                    project_id=native.get("project_id"),
                    status={"type": native.get("read_status", "idle")},
                    model=native.get("model", "gpt-5.6-luna"))
                if "read_project_id" in native:
                    thread["projectId"] = native["read_project_id"]
                elif "project_id" in native:
                    thread["projectId"] = native["project_id"]
                return {"thread": thread}
            if method == "thread/backgroundTerminals/list":
                return {"data": native.get("terminals", []), "nextCursor": native.get("next_cursor")}
            raise AssertionError("Unexpected native request: " + method)
        if method == "thread/read":
            thread = self.script.setdefault("native_threads", {}).get(params["threadId"])
            if thread is None:
                raise CodexError("unknown thread: " + params["threadId"])
            return {"thread": thread}
        return {"turnId": params.get("expectedTurnId", "simulated-turn")}


@pytest.fixture(autouse=True)
def no_live_codex(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Live Codex is forbidden in controller tests")
    monkeypatch.setattr(runtime, "CodexClient", forbidden)


@pytest.fixture
def script(monkeypatch):
    state = {"proposal": proposal(), "clients": [], "sessions": [], "turns": [], "requests": [], "commands": [],
             "native_projects": [], "native_project_imports": {}, "native_threads": {}}
    monkeypatch.setattr(runtime, "CodexClient", lambda **kw: ScriptedCodex(state, **kw))
    return state


@pytest.fixture
def engine(tmp_path):
    return Engine(tmp_path / "state")


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "project"
    path.mkdir()
    git(path, "init", "-b", "main")
    (path / "verify.py").write_text("assert 2 + 2 == 4\n", encoding="utf-8")
    git(path, "add", "verify.py")
    git(path, "-c", "user.name=Test", "-c", "user.email=test@local.invalid",
        "commit", "-m", "Test fixture baseline")
    return path


def authorize(engine, repo, script, **policy):
    plan = engine.propose(str(repo), "Implement the bounded fixture", policy=policy)
    run = engine.approve(plan["id"], plan["data"]["digest"])
    return plan, run["id"]


def prepare(engine, repo, script, **policy):
    plan, rid = authorize(engine, repo, script, **policy)
    engine._prepare_workspaces(rid)
    return plan, rid


def prepare_native(engine, repo, script, **policy):
    plan, rid = prepare(engine, repo, script, **policy)
    engine._prepare_native_project(rid)
    return plan, rid


def finish_background(engine, rid):
    engine._jobs[rid].join(timeout=20)
    assert not engine._jobs[rid].is_alive(), "Controller failed to settle within test deadline"
    return engine._run(rid)


@pytest.mark.parametrize("field", ["repository", "base_commit", "proposal", "policy"])
def test_authorization_rejects_changed_binding(engine, repo, script, field):
    plan = engine.propose(str(repo), "Inspect repository")
    changed = deepcopy(plan["data"])
    if field == "proposal":
        changed[field]["objective"] = "Different objective"
    elif field == "policy":
        changed[field]["token_budget"] += 1
    else:
        changed[field] = "different-target"
    engine.store.put("plan", plan["id"], changed, expected_revision=plan["revision"])
    with pytest.raises(ValueError, match="changed"):
        engine.approve(plan["id"], plan["data"]["digest"])
    assert engine.store.list("run") == []


def test_new_plan_revision_requires_new_digest(engine, repo, script):
    first = engine.propose(str(repo), "Inspect repository")
    script["proposal"]["objective"] = "Revised objective"
    second = engine.propose(str(repo), "Inspect repository", answers={"scope": "revised"})
    assert first["data"]["digest"] != second["data"]["digest"]
    with pytest.raises(ValueError):
        engine.approve(second["id"], first["data"]["digest"])
    run = engine.approve(second["id"], second["data"]["digest"])
    assert run["data"]["authorization_digest"] == digest(run["data"]["plan"])
    assert script["sessions"][0]["model"] == "gpt-5.6-luna"
    assert script["sessions"][0]["effort"] == "max"


def test_duplicate_start_dispatches_once_and_other_controller_cannot_claim(engine, repo, script, monkeypatch):
    _, rid = authorize(engine, repo, script)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def held_job(run_id):
        calls.append(run_id)
        entered.set()
        assert release.wait(10)
    monkeypatch.setattr(engine, "_execute_run", held_job)
    try:
        engine.start(rid)
        assert entered.wait(5)
        assert engine.start(rid)["id"] == rid
        other = Engine(engine.root)
        assert not other.store.claim("run:" + rid, other.owner)
        with pytest.raises((ValueError, ConflictError)):
            other.start(rid)
        assert calls == [rid]
    finally:
        release.set()
        finish_background(engine, rid)


def test_duplicate_package_claim_prevents_dispatch(engine, repo, script):
    _, rid = prepare(engine, repo, script)
    assert engine.store.claim(f"package:{rid}:core", "another-controller")
    with pytest.raises(ConflictError, match="claimed"):
        engine._execute_package(rid, script["proposal"]["work_packages"][0])
    assert not any("assigned_package" in turn for turn in script["turns"])
    assert engine._run(rid)["packages"]["core"]["attempts"] == 0


def test_new_project_worktrees_survive_reopen_and_resume_preparation(engine, tmp_path, script):
    repo = tmp_path / "new-project"
    script["proposal"]["gates"][0]["argv"] = ["python", "core/verify.py"]
    _, rid = prepare(engine, repo, script)
    original = engine._run(rid)
    original_head = git(repo, "rev-parse", "HEAD")
    workspace = Path(original["packages"]["core"]["workspace"])
    (workspace / "core").mkdir()
    (workspace / "core" / "draft.txt").write_text("preserve partial result", encoding="utf-8")
    reopened = Engine(engine.root)
    reopened._prepare_workspaces(rid)
    assert git(repo, "rev-parse", "HEAD") == original_head
    assert reopened._run(rid)["packages"]["core"]["workspace"] == str(workspace)
    assert (workspace / "core" / "draft.txt").read_text(encoding="utf-8") == "preserve partial result"
    worktrees = git(repo, "worktree", "list", "--porcelain")
    assert worktrees.count("worktree ") == 3
    assert len([e for e in reopened.store.events(rid) if e["type"] == "new-project-created"]) == 1
    def finish_partial(client):
        assert (client.cwd / "core" / "draft.txt").read_text(encoding="utf-8") == "preserve partial result"
        (client.cwd / "core" / "verify.py").write_text(
            "from pathlib import Path\nassert Path('core/draft.txt').read_text() == 'preserve partial result'\n",
            encoding="utf-8")
    script["worker"] = finish_partial
    reopened.pause(rid)
    reopened.resume(rid)
    resumed = finish_background(reopened, rid)
    assert resumed["status"] == "awaiting-user", resumed.get("error")
    assert git(repo, "rev-parse", "HEAD") == original_head
    assert set(resumed["packages"]["core"]["changed_files"]) == {"core/draft.txt", "core/verify.py"}


def test_native_project_is_reused_for_the_same_repository_root(engine, repo, script):
    _, first_rid = prepare_native(engine, repo, script)
    _, second_rid = prepare_native(engine, repo, script)

    first = engine._run(first_rid)
    second = engine._run(second_rid)
    assert first["native_project_id"] == second["native_project_id"]
    assert len(script["native_projects"]) == 1
    assert len(script.get("native_project_imports_seen", [])) == 1
    project = script["native_projects"][0]
    assert {"id", "name", "roots", "metadata", "position", "createdAt", "updatedAt", "recencyAt"} <= set(project)
    assert project["roots"] == [{"path": str(repo.resolve())}]

    project_requests = [(method, params) for method, params in script["requests"]
                        if method.startswith("project/")]
    assert [method for method, _ in project_requests] == [
        "project/list", "project/import", "project/read", "project/list", "project/read"]
    imported = project_requests[1][1]
    assert set(imported) == {"idempotencyKey", "name", "roots", "metadata"}
    assert imported["roots"] == [{"path": str(repo.resolve())}]
    assert imported["metadata"] == {"managed_by": "codex-team"}


def test_native_project_root_mismatch_is_rejected_without_verification(engine, repo, tmp_path, script):
    _, rid = prepare(engine, repo, script)
    other_root = tmp_path / "unrelated-root"
    other_root.mkdir()
    project = ScriptedCodex._project_record("native-wrong-root", "unrelated", [other_root])
    script["native_projects"].append(project)
    engine._update("run", rid, lambda data: data.update(native_project_id=project["id"]))
    before = engine.store.get("run", rid)

    with pytest.raises(ValueError, match="root"):
        engine._prepare_native_project(rid)

    assert engine.store.get("run", rid) == before
    assert [method for method, _ in script["requests"] if method.startswith("project/")] == ["project/read"]
    assert not any(event["type"] == "native-project-verified"
                   for event in engine.store.events(rid))


@pytest.mark.parametrize("outcome", ["bound", "blocked"])
def test_session_project_mismatch_is_bound_only_after_native_readback_or_blocked(
        engine, repo, script, outcome):
    _, rid = prepare_native(engine, repo, script)
    project_id = engine._run(rid)["native_project_id"]
    script["reported_project_id"] = "unrelated-project"
    if outcome == "blocked":
        script["ignore_metadata_update"] = True

    package = script["proposal"]["work_packages"][0]
    if outcome == "blocked":
        with pytest.raises(ValueError, match="project assignment mismatch"):
            engine._execute_package(rid, package)
        assert engine._run(rid)["packages"]["core"]["status"] == "blocked"
        assert not any("assigned_package" in turn for turn in script["turns"])
    else:
        engine._execute_package(rid, package)
        saved = engine._run(rid)["packages"]["core"]
        assert saved["status"] == "completed"
        session = next(item for item in script["sessions"] if item.get("project_id"))
        assert session["project_id"] == project_id
        assert session["title"] == "core"

    thread_requests = [(method, params) for method, params in script["requests"]
                       if method.startswith("thread/")]
    methods = [method for method, _ in thread_requests]
    assert methods[:2] == (["thread/metadata/update", "thread/read"] if outcome == "bound"
                           else ["thread/metadata/update", "thread/read"])
    assert thread_requests[0][1] == {"threadId": "simulated-thread", "projectId": project_id}
    assert thread_requests[1][1] == {"threadId": "simulated-thread"}
    if outcome == "bound":
        assert methods[2:] == ["thread/name/set"]
    else:
        assert methods[2:] == []


def test_changed_original_target_blocks_execution_before_dispatch(engine, repo, script):
    _, rid = authorize(engine, repo, script)
    (repo / "user-draft.txt").write_text("user work", encoding="utf-8")
    engine.start(rid)
    result = finish_background(engine, rid)
    assert result["status"] == "blocked"
    assert "Repository changed" in result["error"]
    assert not any("assigned_package" in turn for turn in script["turns"])
    assert (repo / "user-draft.txt").read_text() == "user work"


def test_execution_rechecks_authorization_before_creating_workspaces(engine, repo, script):
    _, rid = authorize(engine, repo, script)
    def alter_plan(data):
        data["plan"]["proposal"]["objective"] = "Unapproved replacement objective"
    engine._update("run", rid, alter_plan)
    engine.start(rid)
    result = finish_background(engine, rid)
    assert result["status"] == "blocked"
    assert "Authorization" in result["error"]
    assert result["packages"]["core"]["workspace"] is None
    assert not any("assigned_package" in turn for turn in script["turns"])


@pytest.mark.parametrize("violation", ["ownership", "workspace", "model", "history"])
def test_worker_identity_and_scope_violations_block(engine, repo, script, violation):
    _, rid = prepare(engine, repo, script)
    workspace = Path(engine._run(rid)["packages"]["core"]["workspace"])
    if violation == "ownership":
        script["worker"] = lambda c: (c.cwd / "outside.txt").write_text("unauthorized", encoding="utf-8")
    elif violation == "workspace":
        script["reported_cwd"] = repo
    elif violation == "model":
        script["reported_model"] = "unauthorized-model"
    else:
        script["worker"] = lambda c: git(c.cwd, "-c", "user.name=Test", "-c",
            "user.email=test@local.invalid", "commit", "--allow-empty", "-m", "Unauthorized worker commit")
    with pytest.raises((ValueError, CodexError)):
        engine._execute_package(rid, script["proposal"]["work_packages"][0])
    result = engine._run(rid)["packages"]["core"]
    assert result["status"] == "blocked"
    assert result["result"] is None
    assert workspace.exists()
    assert engine.store.claim(f"package:{rid}:core", "probe")


def test_read_only_result_needs_no_commit_and_reaches_real_gate_checkpoint(engine, repo, script):
    script["proposal"] = proposal(read_only=True)
    _, rid = authorize(engine, repo, script)
    baseline = git(repo, "rev-parse", "HEAD")
    engine.start(rid)
    result = finish_background(engine, rid)
    assert result["status"] == "awaiting-user", result.get("error")
    package = result["packages"]["core"]
    assert package["changed_files"] == []
    assert package["commit"] == baseline
    assert Path(package["result"]["path"]).is_file()
    evidence = [json.loads(Path(ref["path"]).read_text(encoding="utf-8")) for ref in result["evidence"]]
    assert evidence[0]["exit_code"] == 0
    assert evidence[0]["status"] == "passed"
    qualified = result["toolchain"]["python"]
    assert qualified["sha256"] == hashlib.sha256(Path(qualified["path"]).read_bytes()).hexdigest()
    assert qualified["version"].startswith("Python ")
    assert evidence[0]["argv_resolved"] == [qualified["path"], "verify.py"]
    assert any(command["argv"] == [qualified["path"], "--version"] for command in script["commands"])
    assert all(not client.active_command_ids for client in script["clients"])
    assert engine.accept_checkpoint(rid, result["checkpoint_digest"])["data"]["status"] == "completed"


def test_collaboration_request_deduplication_and_recipient_validation(engine, repo, script):
    script["proposal"] = proposal(multi=True)
    _, rid = authorize(engine, repo, script)
    request = engine.request_collaboration(rid, "core", "docs", "Which API?", request_id="stable")
    again = engine.request_collaboration(rid, "core", "docs", "Which API?", request_id="stable")
    assert again["id"] == request["id"]
    assert len(engine.store.list("request")) == 1
    assert len([e for e in engine.store.events(rid) if e["type"] == "collaboration-requested"]) == 1
    with pytest.raises(ConflictError):
        engine.request_collaboration(rid, "core", "docs", "Different question", request_id="stable")
    message = {"method": "item/tool/call", "params": {"tool": "team_control", "arguments": {
        "action": "answer", "message": "Answer", "target": "", "request_id": request["id"]}}}
    with pytest.raises(ValueError, match="recipient"):
        engine._tool_request(rid, "core", message)
    assert engine._tool_request(rid, "docs", message)["success"] is True
    assert engine.store.get("request", request["id"])["data"]["answer"] == "Answer"


def test_request_id_cannot_be_rebound_to_opposite_recipient(engine, repo, script):
    script["proposal"] = proposal(multi=True)
    _, rid = authorize(engine, repo, script)
    engine.request_collaboration(rid, "core", "docs", "Same text", request_id="stable")
    with pytest.raises(ConflictError):
        engine.request_collaboration(rid, "docs", "core", "Same text", request_id="stable")


def test_cross_engine_correction_is_delivered_once_by_owner(engine, repo, script):
    _, rid = authorize(engine, repo, script)
    engine._update("run", rid, lambda d: d.update(status="running", started_at=now()))
    engine._package_update(rid, "core", status="running")
    other = Engine(engine.root)
    command = other.steer(rid, "core", "Preserve the public API")
    assert command["data"]["status"] == "queued"
    client = ScriptedCodex(script)
    engine._tick(rid, "core", client, "thread", "turn")
    engine._tick(rid, "core", client, "thread", "turn")
    assert len([r for r in script["requests"] if r[0] == "turn/steer"]) == 1
    assert other.store.get("command", command["id"])["data"]["status"] == "delivered"


def test_cross_engine_pause_remains_request_until_owner_interrupts(engine, repo, script):
    _, rid = authorize(engine, repo, script)
    engine._update("run", rid, lambda d: d.update(status="running", started_at=now()))
    assert engine.store.claim("run:" + rid, engine.owner)
    client = ScriptedCodex(script)
    engine._active[(rid, "core")] = {"client": client, "thread_id": "thread", "turn_id": "turn"}
    other = Engine(engine.root)
    other.pause(rid)
    assert other._run(rid)["status"] == "pause-requested"
    engine._tick(rid, "core", client, "thread", "turn")
    assert [r[0] for r in script["requests"]] == ["turn/interrupt"]


def test_cross_engine_resume_cannot_replace_live_owner_or_change_status(engine, repo, script):
    _, rid = authorize(engine, repo, script)
    engine._update("run", rid, lambda d: d.update(status="running", started_at=now()))
    assert engine.store.claim("run:" + rid, engine.owner)
    other = Engine(engine.root)
    before = other.store.get("run", rid)
    with pytest.raises(ConflictError):
        other.resume(rid)
    after = other.store.get("run", rid)
    assert after["data"]["status"] == before["data"]["status"] == "running"
    assert not other.store.claim("run:" + rid, other.owner)


@pytest.mark.parametrize("tamper", ["artifact", "source", "digest", "binding"])
def test_checkpoint_rejects_tampered_evidence_or_target(engine, repo, script, tamper):
    _, rid = authorize(engine, repo, script)
    engine.start(rid)
    result = finish_background(engine, rid)
    assert result["status"] == "awaiting-user", result.get("error")
    expected = result["checkpoint_digest"]
    if tamper == "artifact":
        Path(result["evidence"][0]["path"]).write_text("tampered", encoding="utf-8")
    elif tamper == "source":
        (Path(result["target"]["workspace"]) / "verify.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
    elif tamper == "binding":
        replacement = engine._artifact(rid, "substituted", {"status": "passed", "test_fixture": True})
        engine._update("run", rid, lambda d: d.update(evidence=[replacement]))
    else:
        expected = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        engine.accept_checkpoint(rid, expected)
    assert engine._run(rid)["status"] == "awaiting-user"


def test_token_usage_is_cumulative_per_thread_and_budget_stops_run(engine, repo, script):
    _, rid = authorize(engine, repo, script, token_budget=100)
    def usage(thread, amount):
        engine._on_event(rid, "core", {"method": "thread/tokenUsage/updated", "params": {
            "threadId": thread, "tokenUsage": {"total": {"totalTokens": amount}}}})
    usage("a", 60)
    usage("a", 50)
    usage("a", 60)
    assert engine._run(rid)["status"] == "authorized"
    usage("b", 41)
    result = engine._run(rid)
    assert result["usage_by_thread"] == {"a": 60, "b": 41}
    assert result["status"] == "pause-requested"
    assert "token budget" in result["error"]


def test_elapsed_budget_requests_native_interrupt_in_same_tick(engine, repo, script):
    _, rid = authorize(engine, repo, script, max_turn_seconds=1, max_run_seconds=1)
    earlier = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    engine._update("run", rid, lambda d: d.update(status="running", started_at=earlier, active_since=earlier))
    client = ScriptedCodex(script)
    engine._active[(rid, "core")] = {"client": client, "thread_id": "thread", "turn_id": "turn"}
    engine._tick(rid, "core", client, "thread", "turn")
    assert engine._run(rid)["status"] == "pause-requested"
    assert [r[0] for r in script["requests"]] == ["turn/interrupt"]


def test_resume_rejects_a_response_for_a_different_native_thread(engine, repo, script):
    _, rid = prepare(engine, repo, script)
    workspace = Path(engine._run(rid)["packages"]["core"]["workspace"])
    engine._package_update(rid, "core", thread_id="saved-thread")
    script["native"] = {"saved-thread": {"resume_thread_id": "different-thread"}}

    with pytest.raises(CodexError, match="identity/configuration mismatch"):
        engine._execute_package(rid, script["proposal"]["work_packages"][0])

    package = engine._run(rid)["packages"]["core"]
    assert package["status"] == "blocked"
    assert package["result"] is None
    assert not any("assigned_package" in turn for turn in script["turns"])
    assert [method for method, _ in script["requests"]] == ["thread/resume"]
    assert workspace.exists()


def test_failed_worker_never_creates_success_checkpoint(engine, repo, script):
    script["worker_status"] = "failed"
    _, rid = authorize(engine, repo, script)
    engine.start(rid)
    result = finish_background(engine, rid)
    assert result["status"] == "blocked"
    assert result["packages"]["core"]["status"] == "blocked"
    assert "checkpoint_digest" not in result
    assert "Worker turn failed" in result["error"]


def test_failing_real_gate_retains_failed_evidence_without_repair_budget(engine, repo, script):
    (repo / "verify.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    git(repo, "add", "verify.py")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@local.invalid", "commit", "-m", "Failing fixture gate")
    _, rid = authorize(engine, repo, script, max_repair_attempts=0)
    engine.start(rid)
    result = finish_background(engine, rid)
    assert result["status"] == "blocked"
    evidence = json.loads(Path(result["evidence"][0]["path"]).read_text(encoding="utf-8"))
    assert evidence["exit_code"] == 7
    assert evidence["status"] == "failed"
    assert "checkpoint_digest" not in result
    assert "Acceptance gate failed" in result["error"]


def test_amend_limits_creates_version_preserving_prior_authorization(engine, repo, script):
    plan, rid = authorize(engine, repo, script)
    before = engine._run(rid)
    engine.pause(rid)
    amended = engine.amend_limits(rid, {"token_budget": before["limits"]["token_budget"] + 100},
                                  before["authorization_digest"])["data"]
    assert amended["status"] == "paused"
    assert amended["authorization_digest"] != before["authorization_digest"]
    assert digest(amended["plan"]) == amended["authorization_digest"]
    assert amended["authorization"]["predecessor_digest"] == before["authorization_digest"]
    assert amended["limits"]["token_budget"] == before["limits"]["token_budget"] + 100
    assert amended["plan"]["proposal"] == before["plan"]["proposal"]
    assert engine.store.get("plan", plan["id"]) == plan
    revised_plan = engine.store.get("plan", amended["plan_id"])
    assert revised_plan["data"]["predecessor_plan_id"] == plan["id"]
    amendments = [e for e in engine.store.events(rid) if e["type"] == "authorization-amended"]
    assert len(amendments) == 1
    assert amendments[0]["payload"]["previous_limits"] == before["limits"]
    with pytest.raises(ValueError):
        engine.amend_limits(rid, {"token_budget": 500000}, before["authorization_digest"])
    assert len(engine.store.list("plan")) == 2


@pytest.mark.parametrize("state", ["running", "paused-with-owner"])
def test_amend_limits_rejects_active_controller_without_mutating_authority(engine, repo, script, state):
    _, rid = authorize(engine, repo, script)
    engine._update("run", rid, lambda d: d.update(status="running" if state == "running" else "paused"))
    assert engine.store.claim("run:" + rid, engine.owner)
    other = Engine(engine.root)
    before = other.store.get("run", rid)
    with pytest.raises((ValueError, ConflictError)):
        other.amend_limits(rid, {"token_budget": 500000}, before["data"]["authorization_digest"])
    assert other.store.get("run", rid) == before
    assert len(other.store.list("plan")) == 1


@pytest.mark.parametrize("policy", [{"model": "other"}, {"network_access": True}])
def test_amend_limits_cannot_change_model_or_permissions(engine, repo, script, policy):
    _, rid = authorize(engine, repo, script)
    engine.pause(rid)
    before = engine.store.get("run", rid)
    with pytest.raises(ValueError):
        engine.amend_limits(rid, policy, before["data"]["authorization_digest"])
    assert engine.store.get("run", rid) == before


def test_requalify_keeps_old_toolchain_evidence_when_interpreter_changes(engine, repo, script, monkeypatch, tmp_path):
    _, rid = prepare(engine, repo, script)
    old_toolchain = engine._qualify_toolchain(rid)
    old_environment = engine._run(rid)["toolchain"]
    old_event = next(event for event in engine.store.events(rid)
                     if event["type"] == "toolchain-qualified")
    old_evidence = old_event["payload"]["evidence"]
    old_evidence_bytes = Path(old_evidence["path"]).read_bytes()

    updated_python = tmp_path / "updated-python.exe"
    updated_python.write_bytes(Path(sys.executable).read_bytes() + b"codex-team-updated")
    monkeypatch.setenv("CODEX_TEAM_PYTHON", str(updated_python))
    engine._update("run", rid, lambda data: data.update(status="paused"))

    qualified = engine.requalify(rid)
    run = engine._run(rid)
    predecessor = run["previous_toolchains"][0]
    assert qualified["path"] == str(updated_python.resolve())
    assert qualified["sha256"] == hashlib.sha256(updated_python.read_bytes()).hexdigest()
    assert run["toolchain"]["python"] == qualified
    assert json.loads(Path(predecessor["path"]).read_text(encoding="utf-8")) == old_environment
    assert Path(old_evidence["path"]).read_bytes() == old_evidence_bytes
    assert any(event["type"] == "toolchain-invalidated" for event in engine.store.events(rid))
    assert any(event["type"] == "toolchain-requalified" for event in engine.store.events(rid))


def test_requalify_rejects_an_active_controller_without_mutating_toolchain(engine, repo, script):
    _, rid = prepare(engine, repo, script)
    old_toolchain = engine._qualify_toolchain(rid)
    engine._update("run", rid, lambda data: data.update(status="paused"))
    assert engine.store.claim("run:" + rid, engine.owner)
    before = engine.store.get("run", rid)
    command_count = len(script["commands"])

    try:
        with pytest.raises(ValueError, match="stopped"):
            engine.requalify(rid)
    finally:
        engine.store.release("run:" + rid, engine.owner)

    assert engine.store.get("run", rid) == before
    assert engine._run(rid)["toolchain"]["python"] == old_toolchain
    assert len(script["commands"]) == command_count


def test_history_notes_and_snapshot_survive_reopen_and_keep_run_scope(engine, repo, script):
    _, rid = authorize(engine, repo, script)
    event = engine._event(rid, "material-progress", {"package": "core", "message": "Verified fixture behavior"})
    first = {"current_goal": "Verify core", "decisions": ["Keep scope"], "verified": [],
             "remaining": ["Inspect behavior"], "next_action": "Inspect source", "references": []}
    engine.history.save_note(rid, "core", first)
    latest = {**first, "verified": ["Verified fixture behavior"], "remaining": [],
              "next_action": "Review checkpoint", "references": [{"event_seq": event["seq"]}]}
    saved = engine.history.save_note(rid, "core", latest)
    _, other_rid = authorize(engine, repo, script)
    engine.history.save_note(other_rid, "core", {**first, "current_goal": "Separate run"})
    reopened = Engine(engine.root)
    snapshot = reopened.snapshot(rid)
    assert [run["id"] for run in snapshot["runs"]] == [rid]
    assert snapshot["notes"] == [saved]
    assert reopened.get_note(rid, "core") == saved
    assert snapshot["runs"][0]["data"]["limits_digest"] == engine._run(rid)["authorization_digest"]
    matches = reopened.search_history(rid, "Verified fixture behavior", package_id="core")
    assert matches
    assert all(match["reference"]["run_id"] == rid for match in matches)
    assert any(match["reference"]["event_seq"] == event["seq"] for match in matches)
    assert reopened.search_history(rid, "Separate run") == []
    with pytest.raises(ValueError, match="Unknown package"):
        reopened.get_note(rid, "missing")


def test_paused_wall_time_does_not_consume_run_budget(engine, repo, script, monkeypatch):
    _, rid = authorize(engine, repo, script, max_turn_seconds=10, max_run_seconds=100)
    instant = datetime.now(timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant
    monkeypatch.setattr(runtime, "datetime", Clock)
    engine._update("run", rid, lambda d: d.update(status="running"))
    instant += timedelta(seconds=7)
    engine._update("run", rid, lambda d: d.update(status="paused"))
    stopped = engine._run(rid)
    assert stopped["active_since"] is None
    assert stopped["active_elapsed_seconds"] == pytest.approx(7)
    instant += timedelta(days=2)
    assert engine._run_deadline(rid) == pytest.approx(93)
    engine._update("run", rid, lambda d: d.update(status="running"))
    instant += timedelta(seconds=3)
    assert engine._run_deadline(rid) == pytest.approx(90)


def test_expired_controller_lease_is_observed_stale_without_changing_run(engine, repo, script, monkeypatch):
    import team_runtime.store as storage
    _, rid = authorize(engine, repo, script)
    engine._update("run", rid, lambda d: d.update(status="running"))
    epoch = time.time()
    monkeypatch.setattr(storage.time, "time", lambda: epoch)
    assert engine.store.claim("run:" + rid, engine.owner, ttl_seconds=30)
    assert engine.snapshot(rid)["runs"][0]["data"]["observation_state"] == "current"
    before = engine.store.get("run", rid)
    epoch += 31
    observed = Engine(engine.root).snapshot(rid)["runs"][0]["data"]
    assert observed["observation_state"] == "stale"
    assert observed["status"] == "running"
    assert engine.store.get("run", rid) == before


def paused_source(engine, repo, script):
    _, rid = prepare(engine, repo, script)
    source = Path(engine._run(rid)["packages"]["core"]["workspace"]) / "core" / "draft.txt"
    source.parent.mkdir()
    source.write_text("Preserved partial implementation", encoding="utf-8")
    engine.pause(rid)
    return rid, source


def test_supervision_binds_stable_source_and_preserves_paused_state(engine, repo, script):
    rid, source = paused_source(engine, repo, script)
    result = engine.supervise(rid)
    assert result["verdict"] == "on-track"
    assert len(result["evidence"]) == 1
    receipt = json.loads(Path(result["evidence"][0]["path"]).read_text(encoding="utf-8"))
    assert receipt["snapshot"]["files"]["core/draft.txt"]["sha256"] == "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    assert "simulated" in receipt["report"]["summary"]
    assert engine._run(rid)["status"] == "paused"
    assert engine.get_note(rid, "core") is not None
    assert engine.store.lease_owner("run:" + rid) is None
    assert not any("assigned_package" in turn for turn in script["turns"])


@pytest.mark.parametrize("state", ["running", "pause-requested", "owned-paused"])
def test_supervision_rejects_unstable_execution(engine, repo, script, state):
    rid, source = paused_source(engine, repo, script)
    if state == "owned-paused":
        assert engine.store.claim("run:" + rid, "other-controller")
    else:
        engine._update("run", rid, lambda d: d.update(status=state))
    before = engine.store.get("run", rid)
    with pytest.raises((ValueError, ConflictError)):
        engine.supervise(rid)
    assert engine.store.get("run", rid) == before
    assert len(script["turns"]) == 1
    assert source.read_text(encoding="utf-8") == "Preserved partial implementation"


def test_supervision_rejects_source_changed_during_review(engine, repo, script):
    rid, source = paused_source(engine, repo, script)
    script["supervisor"] = lambda client: source.write_text("Changed during review", encoding="utf-8")
    with pytest.raises(ValueError, match="Source changed"):
        engine.supervise(rid)
    assert engine._run(rid)["status"] == "paused"
    assert engine.store.lease_owner("run:" + rid) is None
    assert not any(e["type"] == "direction-reviewed" for e in engine.store.events(rid))
    assert source.read_text(encoding="utf-8") == "Changed during review"


def interrupted_source(engine, repo, script):
    rid, source = paused_source(engine, repo, script)
    receipt = engine._artifact(rid, "test-native-receipt", {
        "package": "core", "thread_id": "old-thread", "turn": {"id": "old-turn", "status": "interrupted"},
        "report": "Simulated native receipt; no real model was run."})
    engine._package_update(rid, "core", status="paused", thread_id="old-thread", turn_id="old-turn", result=receipt)
    note = engine.history.save_note(rid, "core", {
        "current_goal": "Finish preserved implementation", "decisions": ["Keep existing files"],
        "verified": [], "remaining": ["Run behavioral gate"], "next_action": "Continue existing source",
        "references": []})
    return rid, source, receipt, note


def test_replace_session_binds_receipt_notes_and_source_without_dispatch(engine, repo, script):
    rid, source, receipt, note = interrupted_source(engine, repo, script)
    old_bytes = Path(receipt["path"]).read_bytes()
    result = engine.replace_session(rid, "core", "Recover an interrupted test session")["data"]
    package = result["packages"]["core"]
    assert package["status"] == "pending"
    assert package["thread_id"] is None and package["turn_id"] is None
    assert package["previous_threads"] == ["old-thread"]
    handoff = json.loads(Path(package["handoff"]["path"]).read_text(encoding="utf-8"))
    assert handoff["previous_thread"] == "old-thread"
    assert handoff["previous_turn"] == "old-turn"
    assert handoff["interruption_receipt"] == receipt
    assert handoff["work_note_id"] == note["id"]
    assert handoff["source_snapshot"]["files"]["core/draft.txt"]["sha256"] == "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    assert Path(receipt["path"]).read_bytes() == old_bytes
    assert engine.get_note(rid, "core") == note
    assert source.read_text(encoding="utf-8") == "Preserved partial implementation"
    assert len(script["turns"]) == 1
    assert result["replacements_used"] == 1


@pytest.mark.parametrize("tamper", ["refhash", "source"])
def test_replacement_dispatch_rejects_changed_handoff_or_source(engine, repo, script, tamper):
    rid, source, _, _ = interrupted_source(engine, repo, script)
    result = engine.replace_session(rid, "core", "Recover before starting the replacement")
    handoff = result["data"]["packages"]["core"]["handoff"]
    if tamper == "refhash":
        Path(handoff["path"]).write_text("{}", encoding="utf-8")
        expected = "Session handoff evidence is invalid"
    else:
        source.write_text("Changed before replacement starts", encoding="utf-8")
        expected = "Source changed after session handoff was prepared"
    sessions = len(script["sessions"])
    turns = len(script["turns"])

    with pytest.raises(ValueError, match=expected):
        engine._execute_package(rid, script["proposal"]["work_packages"][0])

    assert engine._run(rid)["packages"]["core"]["status"] == "blocked"
    assert len(script["sessions"]) == sessions
    assert len(script["turns"]) == turns
    assert not any(event["type"] == "handoff-verified" for event in engine.store.events(rid))


@pytest.mark.parametrize("invalid", ["completed", "unknown", "missing", "tampered", "native-completed", "other-thread", "other-turn", "other-package"])
def test_replace_session_rejects_unproven_interruption(engine, repo, script, invalid):
    rid, source, receipt, note = interrupted_source(engine, repo, script)
    if invalid in {"completed", "unknown"}:
        engine._package_update(rid, "core", status="completed" if invalid == "completed" else "blocked")
    elif invalid == "missing":
        engine._package_update(rid, "core", result=None)
    elif invalid == "tampered":
        Path(receipt["path"]).write_text("{}", encoding="utf-8")
    else:
        payload = json.loads(Path(receipt["path"]).read_text(encoding="utf-8"))
        if invalid == "native-completed":
            payload["turn"]["status"] = "completed"
        elif invalid == "other-thread":
            payload["thread_id"] = "unrelated-thread"
        elif invalid == "other-turn":
            payload["turn"]["id"] = "unrelated-turn"
        else:
            payload["package"] = "unrelated-package"
        engine._package_update(rid, "core", result=engine._artifact(rid, "unrelated-receipt", payload))
    before = engine.store.get("run", rid)
    with pytest.raises(ValueError):
        engine.replace_session(rid, "core", "Attempt invalid transfer")
    assert engine.store.get("run", rid) == before
    assert source.read_text(encoding="utf-8") == "Preserved partial implementation"
    assert not any(e["type"] == "responsibility-transferred" for e in engine.store.events(rid))


def test_replace_session_requires_current_work_notes(engine, repo, script):
    rid, source = paused_source(engine, repo, script)
    before = engine.store.get("run", rid)
    with pytest.raises(ValueError, match="work notes"):
        engine.replace_session(rid, "core", "Transfer unfinished work")
    assert engine.store.get("run", rid) == before
    assert source.read_text(encoding="utf-8") == "Preserved partial implementation"


def test_first_material_observation_waits_for_prepared_workspace(engine, repo, script):
    _, rid = authorize(engine, repo, script)
    engine._update("run", rid, lambda d: d.update(status="running"))
    client = ScriptedCodex(script)
    engine._tick(rid, "core", client, "thread", "turn")
    assert engine._run(rid)["status"] == "running"
    assert engine._run(rid)["packages"]["core"]["workspace"] is None
    assert not any(e["type"] == "material-observed" for e in engine.store.events(rid))


def stale_supervision(engine, repo, script):
    rid, source, receipt, note = interrupted_source(engine, repo, script)
    engine._update("run", rid, lambda d: d.update(status="supervising", native_sessions={
        "registered-supervisor": {"package": "supervisor-core", "turn_id": "review-turn", "turn_status": "inProgress"},
        "finished-session": {"package": "core", "turn_id": "finished-turn", "turn_status": "completed"}}))
    script["native"] = {"registered-supervisor": {}}
    return rid, source, note


def test_reconcile_expired_supervision_preserves_source_notes_and_excludes_offline_gap(engine, repo, script, monkeypatch):
    import team_runtime.store as storage
    rid, source, note = stale_supervision(engine, repo, script)
    last_event = engine._event(rid, "test-observed-before-disconnect", {"test_double": True})
    observed_at = datetime.fromisoformat(last_event["created_at"])
    engine._update("run", rid, lambda d: d.update(active_elapsed_seconds=3,
        active_since=(observed_at - timedelta(seconds=7)).isoformat()))
    epoch = time.time()
    monkeypatch.setattr(storage.time, "time", lambda: epoch)
    assert engine.store.claim("run:" + rid, "lost-controller", ttl_seconds=30)
    epoch += 2 * 86400
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return observed_at + timedelta(days=2)
    monkeypatch.setattr(runtime, "datetime", Clock)
    before = engine._run(rid)
    result = engine.reconcile(rid)["data"]
    assert result["status"] == "paused"
    assert result["active_since"] is None
    assert result["active_elapsed_seconds"] == pytest.approx(10)
    assert engine._run_deadline(rid) == pytest.approx(result["limits"]["max_run_seconds"] - 10)
    ref = result["reconciliation"]
    payload_bytes = Path(ref["path"]).read_bytes()
    assert ref["sha256"] == "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
    payload = json.loads(payload_bytes)
    assert json.loads(Path(payload["before"]["path"]).read_text(encoding="utf-8")) == before
    assert payload["last_recorded_event"] == last_event
    assert payload["native_observations"][0]["thread_id"] == "registered-supervisor"
    assert payload["native_observations"][0]["background_terminals"] == []
    assert payload["source_snapshots"]["core"]["files"]["core/draft.txt"]["sha256"] == "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    assert engine.get_note(rid, "core") == note
    assert source.read_text(encoding="utf-8") == "Preserved partial implementation"
    assert len(script["turns"]) == 1
    assert len(script["sessions"]) == 1
    assert [method for method, _ in script["requests"]] == ["thread/resume", "thread/read", "thread/backgroundTerminals/list"]
    assert all(params["threadId"] == "registered-supervisor" for _, params in script["requests"])
    assert engine.store.lease_owner("run:" + rid) is None
    events = [e for e in engine.store.events(rid) if e["type"] == "reconciled"]
    assert len(events) == 1 and events[0]["payload"]["evidence"] == ref


def test_reconcile_rejects_live_owner_without_native_queries(engine, repo, script):
    rid, source, note = stale_supervision(engine, repo, script)
    assert engine.store.claim("run:" + rid, "active-controller")
    before = engine.store.get("run", rid)
    with pytest.raises(ConflictError, match="owner"):
        engine.reconcile(rid)
    assert engine.store.get("run", rid) == before
    assert script["requests"] == []
    assert engine.store.lease_owner("run:" + rid) == "active-controller"


def test_reconcile_running_package_can_continue_existing_session(engine, repo, script):
    rid, source, receipt, note = interrupted_source(engine, repo, script)
    engine._package_update(rid, "core", status="running")
    engine._update("run", rid, lambda d: d.update(status="running", native_sessions={}))
    script["native"] = {"old-thread": {}}
    result = engine.reconcile(rid)["data"]
    saved = result["packages"]["core"]
    assert saved["status"] == "paused"
    assert saved["thread_id"] == "old-thread"
    assert saved["turn_id"] == "old-turn"
    assert saved["result"] == receipt
    assert source.read_text(encoding="utf-8") == "Preserved partial implementation"
    assert engine.get_note(rid, "core") == note
    observed = json.loads(Path(result["reconciliation"]["path"]).read_text(encoding="utf-8"))
    assert observed["native_observations"][0]["thread_id"] == "old-thread"
    assert observed["native_observations"][0]["background_terminals"] == []
    script["worker"] = lambda client: client.payload.update(report="Continue preserved work")
    engine._execute_package(rid, result["plan"]["proposal"]["work_packages"][0])
    assert engine._run(rid)["packages"]["core"]["status"] == "completed"
    assert engine._run(rid)["packages"]["core"]["thread_id"] == "old-thread"


@pytest.mark.parametrize("obstruction", ["terminal", "more-terminals", "still-active", "unknown-turn", "model", "cwd", "sandbox"])
def test_reconcile_unconfirmed_native_state_preserves_original_run(engine, repo, script, obstruction):
    rid, source, note = stale_supervision(engine, repo, script)
    native = script["native"]["registered-supervisor"]
    if obstruction == "terminal":
        native["terminals"] = [{"id": "remaining-terminal"}]
    elif obstruction == "more-terminals":
        native["next_cursor"] = "more-results"
    elif obstruction == "still-active":
        native.update(resume_status="active", read_status="active")
    elif obstruction == "unknown-turn":
        native["resume_status"] = "active"
        def unknown(data):
            data["native_sessions"]["registered-supervisor"].pop("turn_id")
        engine._update("run", rid, unknown)
    elif obstruction == "model":
        native["model"] = "unapproved-model"
    elif obstruction == "cwd":
        native["cwd"] = str(repo)
    else:
        native["sandbox"] = ScriptedCodex.sandbox(source.parent.parent, writable=True)
    before = engine.store.get("run", rid)
    with pytest.raises((ValueError, CodexError)):
        engine.reconcile(rid)
    assert engine.store.get("run", rid) == before
    assert source.read_text(encoding="utf-8") == "Preserved partial implementation"
    assert engine.get_note(rid, "core") == note
    assert engine.store.lease_owner("run:" + rid) is None
    assert len(script["turns"]) == 1
    assert len(script["sessions"]) == 1
    events = engine.store.events(rid)
    assert len([e for e in events if e["type"] == "reconciliation-blocked"]) == 1
    assert not any(e["type"] == "reconciled" for e in events)
    interruptions = [params for method, params in script["requests"] if method == "turn/interrupt"]
    assert interruptions == ([{"threadId": "registered-supervisor", "turnId": "review-turn"}] if obstruction == "still-active" else [])
