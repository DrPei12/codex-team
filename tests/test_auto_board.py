"""HTTP boundary tests for the local Team board.

``FakeEngine`` is intentionally a tiny test-only substitute. The production
board has no fallback state and receives a real Engine through ``make_server``.
"""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest

from team_runtime.board import make_server


class FakeEngine:
    """A small Engine substitute used only to exercise HTTP routing."""

    def __init__(self, *, fail_propose: bool = False) -> None:
        self.fail_propose = fail_propose
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.plans: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.requests: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def snapshot(self, run_id: str | None = None) -> dict[str, Any]:
        self.calls.append(("snapshot", (run_id,)))
        runs = self.runs if run_id is None else [run for run in self.runs if run["id"] == run_id]
        events = self.events if run_id is None else [event for event in self.events if event["run_id"] == run_id]
        requests = self.requests if run_id is None else [item for item in self.requests if item["run_id"] == run_id]
        return {
            "plans": list(self.plans),
            "runs": list(runs),
            "requests": list(requests),
            "events": list(events),
            "capabilities": {"engine": "test-only"},
        }

    def propose(self, repository: str, brief: str, *, answers: dict | None = None, policy: dict | None = None) -> dict[str, Any]:
        self.calls.append(("propose", (repository, brief, answers, policy)))
        if self.fail_propose:
            raise RuntimeError("test proposal failed")
        plan = {
            "id": "plan-test-1",
            "kind": "plan",
            "revision": 1,
            "data": {
                "brief": brief,
                "repository": repository,
                "status": "proposed",
                "questions": [],
                "proposal": {
                    "resources": [repository],
                    "actions": ["read", "write"],
                },
                "digest": "sha256:test-plan",
            },
        }
        self.plans[:] = [plan]
        return plan

    def approve(self, plan_id: str, expected_digest: str) -> dict[str, Any]:
        self.calls.append(("approve", (plan_id, expected_digest)))
        run = {
            "id": "run-test-1",
            "kind": "run",
            "revision": 1,
            "data": {
                "plan_id": plan_id,
                "status": "approved",
                "packages": [{"id": "package-a", "status": "running", "workspace": str(Path.cwd())}],
                "checkpoint": {"status": "waiting_user", "digest": "sha256:checkpoint"},
                "limits": {"max_attempts": 2},
                "created_at": "2026-09-05T00:00:00Z",
            },
        }
        self.runs[:] = [run]
        return run

    def _run_action(self, action: str, run_id: str) -> dict[str, Any]:
        self.calls.append((action, (run_id,)))
        return self.runs[0] if self.runs else {"id": run_id, "data": {"status": action}}

    def start(self, run_id: str) -> dict[str, Any]:
        return self._run_action("start", run_id)

    def pause(self, run_id: str) -> dict[str, Any]:
        return self._run_action("pause", run_id)

    def resume(self, run_id: str) -> dict[str, Any]:
        return self._run_action("resume", run_id)

    def cancel(self, run_id: str) -> dict[str, Any]:
        return self._run_action("cancel", run_id)

    def request_collaboration(self, run_id: str, from_package: str, to_package: str, question: str, *, request_id: str | None = None) -> dict[str, Any]:
        self.calls.append(("request_collaboration", (run_id, from_package, to_package, question, request_id)))
        item = {"id": request_id or "request-test-1", "run_id": run_id, "status": "open", "from_package": from_package, "to_package": to_package, "question": question}
        self.requests[:] = [item]
        return item

    def resolve_request(self, run_id: str, request_id: str, answer: str) -> dict[str, Any]:
        self.calls.append(("resolve_request", (run_id, request_id, answer)))
        return {"id": request_id, "run_id": run_id, "status": "resolved", "answer": answer}

    def steer(self, run_id: str, package_id: str, message: str) -> dict[str, Any]:
        self.calls.append(("steer", (run_id, package_id, message)))
        return {"run_id": run_id, "package_id": package_id, "status": "accepted"}

    def get_note(self, run_id: str, package_id: str) -> dict[str, Any]:
        self.calls.append(("get_note", (run_id, package_id)))
        return {"run_id": run_id, "package_id": package_id, "current_goal": "test-only note"}

    def search_history(self, run_id: str, query: str, package_id: str | None = None, limit: int = 20) -> list:
        self.calls.append(("search_history", (run_id, query, package_id, limit)))
        return [{"seq": 1, "text": "test-only history"}]

    def amend_limits(self, run_id: str, policy: dict, expected_digest: str) -> dict:
        self.calls.append(("amend_limits", (run_id, policy, expected_digest)))
        if expected_digest != "sha256:limits":
            raise ValueError("stale limits digest")
        return {"id": run_id, "limits": policy}

    def accept_checkpoint(self, run_id: str, expected_digest: str) -> dict[str, Any]:
        self.calls.append(("accept_checkpoint", (run_id, expected_digest)))
        return {"id": run_id, "status": "accepted", "digest": expected_digest}


@pytest.fixture()
def running_server() -> Any:
    engine = FakeEngine()
    server = make_server(engine, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, engine
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def request(server: Any, method: str, path: str, body: dict[str, Any] | None = None, *, token: str | None = None, origin: str | None = "correct") -> tuple[int, dict[str, Any] | str]:
    host, port = server.server_address[0], server.server_address[1]
    connection = HTTPConnection(host, port, timeout=3)
    headers: dict[str, str] = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    else:
        encoded = None
    if token is not None:
        headers["X-Team-Token"] = token
    if origin == "correct":
        headers["Origin"] = f"http://127.0.0.1:{port}"
    elif origin is not None:
        headers["Origin"] = origin
    connection.request(method, path, body=encoded, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    try:
        return response.status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return response.status, raw.decode("utf-8", "replace")


def wait_for_job(server: Any, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        status, payload = request(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        assert isinstance(payload, dict)
        job = payload["data"]
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_loopback_static_and_snapshot(running_server: Any) -> None:
    server, engine = running_server
    status, page = request(server, "GET", "/", origin=None)
    assert status == 200
    assert isinstance(page, str)
    assert "Team 控制台" in page
    assert server.token in page
    status, snapshot = request(server, "GET", "/api/snapshot", origin=None)
    assert status == 200
    assert isinstance(snapshot, dict)
    assert snapshot["data"]["plans"] == []
    assert engine.calls[-1] == ("snapshot", (None,))


def test_proposal_job_and_engine_routes(running_server: Any) -> None:
    server, engine = running_server
    status, payload = request(
        server,
        "POST",
        "/api/propose",
        {"repository": "D:/repo", "brief": "完成一个小改动"},
        token=server.token,
    )
    assert status == 202
    assert isinstance(payload, dict)
    job = wait_for_job(server, payload["data"]["job_id"])
    assert job["status"] == "succeeded"
    assert job["result"]["data"]["digest"] == "sha256:test-plan"

    status, _ = request(server, "POST", "/api/plans/plan-test-1/approve", {"expected_digest": "sha256:test-plan"}, token=server.token)
    assert status == 200
    for action in ("start", "pause", "resume", "cancel"):
        status, _ = request(server, "POST", f"/api/runs/run-test-1/{action}", {}, token=server.token)
        assert status == 200
    status, _ = request(
        server,
        "POST",
        "/api/runs/run-test-1/collaboration",
        {"from_package": "package-a", "to_package": "package-b", "question": "需要什么输入？"},
        token=server.token,
    )
    assert status == 200
    status, _ = request(server, "POST", "/api/runs/run-test-1/requests/request-test-1/resolve", {"answer": "已提供。"}, token=server.token)
    assert status == 200
    status, _ = request(server, "POST", "/api/runs/run-test-1/steer", {"package_id": "package-a", "message": "先运行检查。"}, token=server.token)
    assert status == 200
    status, _ = request(server, "POST", "/api/runs/run-test-1/checkpoint/accept", {"expected_digest": "sha256:checkpoint"}, token=server.token)
    assert status == 200
    assert {name for name, _args in engine.calls} >= {
        "propose", "approve", "start", "pause", "resume", "cancel", "request_collaboration", "resolve_request", "steer", "accept_checkpoint"
    }


def test_mutation_requires_token_and_same_origin(running_server: Any) -> None:
    server, _engine = running_server
    body = {"repository": "D:/repo", "brief": "test"}
    status, payload = request(server, "POST", "/api/propose", body, origin="http://evil.example")
    assert status == 403
    assert payload["error"]["code"] == "cross_origin"
    status, payload = request(server, "POST", "/api/propose", body, token=server.token, origin=None)
    assert status == 403
    assert payload["error"]["code"] == "origin_required"
    status, payload = request(server, "POST", "/api/propose", body, token="wrong")
    assert status == 403
    assert payload["error"]["code"] == "invalid_token"
    status, payload = request(server, "GET", "/api/snapshot", origin="http://evil.example")
    assert status == 403
    assert payload["error"]["code"] == "cross_origin"
    status, payload = request(server, "GET", "/api/snapshot?token=secret", origin=None)
    assert status == 400
    assert payload["error"]["code"] == "token_in_query"


def test_loopback_and_path_boundaries(tmp_path: Path) -> None:
    engine = FakeEngine()
    with pytest.raises(ValueError):
        make_server(engine, host="0.0.0.0", port=0)
    with pytest.raises(ValueError):
        make_server(engine, host="192.0.2.10", port=0)
    server = make_server(engine, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, payload = request(server, "GET", "/static/../board.py", origin=None)
        assert status == 400
        assert payload["error"]["code"] == "invalid_path"
        status, payload = request(server, "GET", "/missing", origin=None)
        assert status == 404
        assert payload["error"]["code"] == "not_found"
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_failed_proposal_is_visible(running_server: Any) -> None:
    server, _engine = running_server
    server.engine.fail_propose = True
    status, payload = request(server, "POST", "/api/propose", {"repository": "D:/repo", "brief": "失败路径"}, token=server.token)
    assert status == 202
    job = wait_for_job(server, payload["data"]["job_id"])
    assert job["status"] == "failed"
    assert job["error"]["type"] == "RuntimeError"
    assert "test proposal failed" in job["error"]["message"]


def test_notes_history_and_limits_routes_offline_fake(running_server: Any) -> None:
    """HTTP contract only; no real model, history store, or browser execution."""
    server, engine = running_server
    status, payload = request(server, "GET", "/api/notes?run_id=run-test&package_id=pkg-a")
    assert status == 200
    assert payload["data"]["current_goal"] == "test-only note"
    assert engine.calls[-1] == ("get_note", ("run-test", "pkg-a"))
    status, payload = request(server, "GET", "/api/history?run_id=run-test&query=needle&package_id=pkg-a&limit=7")
    assert status == 200
    assert engine.calls[-1] == ("search_history", ("run-test", "needle", "pkg-a", 7))
    for query in ("limit=101", "limit=oops", "limit=0"):
        status, _ = request(server, "GET", "/api/history?run_id=run-test&query=needle&" + query)
        assert status == 400
    policy = {"token_budget": 240000}
    status, _ = request(server, "POST", "/api/runs/run-test/limits", {"policy": policy, "expected_digest": "sha256:limits"}, token=server.token)
    assert status == 200
    assert engine.calls[-1] == ("amend_limits", ("run-test", policy, "sha256:limits"))
    status, _ = request(server, "POST", "/api/runs/run-test/limits", {"policy": policy, "expected_digest": "stale"}, token=server.token)
    assert status == 400
    status, _ = request(server, "POST", "/api/runs/run-test/limits", {"policy": policy, "expected_digest": "sha256:limits"})
    assert status == 403
    engine.get_note = None
    status, payload = request(server, "GET", "/api/notes?run_id=run-test&package_id=pkg-a")
    assert status == 501
    assert payload["error"]["code"] == "unavailable"
    engine.search_history = None
    status, _ = request(server, "GET", "/api/history?run_id=run-test&query=needle")
    assert status == 501
    engine.amend_limits = None
    status, _ = request(server, "POST", "/api/runs/run-test/limits", {"policy": policy, "expected_digest": "sha256:limits"}, token=server.token)
    assert status == 501
