"""Real storage and domain protocol checks; no model calls in this module."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

import pytest

from team_runtime.adaptive import Adaptive, digest
from team_runtime.store import Store, ConflictError


def work(identifier, **extra):
    return {"id": identifier, "title": identifier, "goal": "形成有来源的结论", "acceptance": "核对来源和结论", **extra}


@pytest.fixture
def setup(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    engine = Adaptive(tmp_path / "state")
    run_id = engine.create(project, "研究并比较方案", [work("a"), work("b", depends_on=["a"])],
                           authority="用户委托完成研究并核验", policy={"max_repair_attempts": 3})["run_id"]
    epoch = engine.controller(run_id, "owner")["epoch"]
    engine.start(run_id, "owner", epoch)
    return engine, run_id, epoch


def complete(engine, run_id, epoch, work_id="a", **kwargs):
    attempt = engine.prepare(run_id, work_id, "owner", epoch)["attempt"]
    engine.send_start(run_id, attempt["id"], "owner", epoch)
    engine.bind(run_id, attempt["id"], thread_id="thread-" + work_id, turn_id="turn-" + attempt["id"])
    ref = engine.artifact({"report": "真实来源及适用条件", "files": []})
    engine.complete_attempt(run_id, attempt["id"], ref, **kwargs)
    return attempt, ref


def test_command_atomic_rollback_and_deduplication(tmp_path):
    store = Store(tmp_path / "state.db")
    def crash(tx):
        tx.put("work", "a", {"state": "assigned"})
        tx.event("run", "assigned", {"work": "a"})
        tx.put("outbox", "a", {"state": "pending"})
        raise RuntimeError("crash before commit")
    with pytest.raises(RuntimeError):
        store.command("run", "assign", {"work": "a"}, crash)
    reopened = Store(tmp_path / "state.db")
    assert reopened.get("work", "a") is None
    assert reopened.get("outbox", "a") is None
    assert reopened.events("run") == []
    def commit(tx):
        tx.put("work", "a", {"state": "assigned"})
        tx.put("outbox", "a", {"state": "pending"})
        return tx.event("run", "assigned", {"work": "a"})
    first = reopened.command("run", "assign", {"work": "a"}, commit)
    assert reopened.command("run", "assign", {"work": "a"}, crash) == first
    with pytest.raises(ConflictError):
        reopened.command("run", "assign", {"work": "b"}, commit)
    assert len(reopened.events("run")) == 1


def test_command_serializes_real_processes(tmp_path):
    db = tmp_path / "multi.db"
    Store(db).put("counter", "one", {"count": 0})
    script = tmp_path / "increment.py"
    script.write_text('''import sys
from team_runtime.store import Store
s=Store(sys.argv[1])
def increment(tx):
    old=tx.get('counter','one')
    tx.put('counter','one',{'count':old['data']['count']+1},expected_revision=old['revision'])
    return tx.event('run','increment',{'from':old['data']['count']})
for i in range(8): s.command('run',sys.argv[2]+str(i),{},increment)
''', encoding="utf-8")
    import os
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    processes = [subprocess.Popen([sys.executable, "-B", str(script), str(db), str(i)], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(3)]
    for process in processes:
        out, err = process.communicate(timeout=30)
        assert process.returncode == 0, (out, err)
    store = Store(db)
    assert store.get("counter", "one")["data"]["count"] == 24
    assert [e["seq"] for e in store.events("run")] == list(range(1, 25))


def test_result_does_not_unlock_until_accepted(setup):
    engine, rid, epoch = setup
    attempt, ref = complete(engine, rid, epoch)
    with pytest.raises(ConflictError):
        engine.prepare(rid, "b", "owner", epoch)
    with pytest.raises(ValueError):
        engine.accept(rid, "a", ref["sha256"], "claim", actor="worker")
    with pytest.raises(ConflictError):
        engine.accept(rid, "a", "wrong", "stale result")
    accepted = engine.accept(rid, "a", ref["sha256"], "已检查来源")
    next_attempt = engine.prepare(rid, "b", "owner", epoch)["attempt"]
    assert next_attempt["inputs"]["a"] == accepted["acceptance"]["id"]


def test_claim_and_stop_are_serialized(setup):
    engine, rid, epoch = setup
    def claim(_):
        try:
            return engine.prepare(rid, "a", "owner", epoch)
        except ConflictError:
            return None
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(claim, range(4)))
    assert len([r for r in results if r]) == 1
    attempt_id = next(r for r in results if r)["attempt"]["id"]
    engine.stop(rid)
    with pytest.raises(ConflictError):
        engine.send_start(rid, attempt_id, "owner", epoch)
    assert engine.store.get("adaptive-dispatch", attempt_id)["data"]["state"] == "not-started"
    assert engine.settle(rid, "owner", epoch)["status"] == "paused"


def test_queue_request_waits_and_preserves_original_text(setup):
    engine, rid, epoch = setup
    attempt = engine.prepare(rid, "a", "owner", epoch)["attempt"]
    engine.send_start(rid, attempt["id"], "owner", epoch)
    response = engine.request(rid, attempt["id"], "b", "请核对原始资料，不要只转述摘要。", operation_id="same")
    assert engine.request(rid, attempt["id"], "b", "请核对原始资料，不要只转述摘要。", operation_id="same") == response
    with pytest.raises(ConflictError):
        engine.request(rid, attempt["id"], "b", "另一问题", operation_id="same")
    ref = engine.artifact({"report": "已保存当前工作，等待核对"})
    engine.complete_attempt(rid, attempt["id"], ref)
    state = engine.run(rid)["data"]
    assert state["works"]["a"]["state"] == "waiting"
    assert [w["id"] for w in engine.eligible(state)] == [response["work_id"]]
    assert engine.history(rid, "不要只转述摘要")["events"]


def test_unknown_attempt_prevents_takeover_and_terminal_reopen(setup):
    engine, rid, epoch = setup
    attempt, ref = complete(engine, rid, epoch, outcome="unknown")
    with pytest.raises(ConflictError):
        engine.settle(rid, "owner", epoch)
    with pytest.raises(ConflictError):
        engine.controller(rid, "next-owner")
    assert engine.run(rid)["data"]["status"] == "needs-reconciliation"


def test_revision_preserves_unaffected_acceptance(setup):
    engine, rid, epoch = setup
    _, ref = complete(engine, rid, epoch)
    accepted = engine.accept(rid, "a", ref["sha256"], "证据有效")
    engine.revise(rid, 1, "细化后续比较", update=[{"id": "b", "goal": "明确比较两种情况"}])
    state = engine.run(rid)["data"]
    assert state["works"]["a"]["acceptance_record"] == accepted["acceptance"]["id"]
    assert state["works"]["b"]["revision"] == 2
    with pytest.raises(ConflictError):
        engine.revise(rid, 2, "重开旧成果", update=[{"id": "a", "goal": "changed"}])


def test_cycles_and_workspace_escape_rejected(setup):
    engine, rid, epoch = setup
    with pytest.raises(ConflictError):
        engine.revise(rid, 1, "循环依赖", update=[{"id": "a", "depends_on": ["b"]}])
    assert engine.run(rid)["data"]["plan_revision"] == 1
    with pytest.raises(ValueError):
        engine.revise(rid, 1, "越界", add=[work("c", directory="../outside")])


def test_native_usage_deduplicates_and_counts_turn_reset(setup):
    engine, rid, epoch = setup
    attempt = engine.prepare(rid, "a", "owner", epoch)["attempt"]
    def event(turn, total, last):
        return {"method": "thread/tokenUsage/updated", "params": {"threadId": "tid", "turnId": turn,
                "tokenUsage": {"total": {"totalTokens": total}, "last": {"totalTokens": last}}}}
    engine.native_event(rid, attempt["id"], event("one", 100, 100))
    engine.native_event(rid, attempt["id"], event("one", 100, 100))
    engine.native_event(rid, attempt["id"], event("two", 40, 40))
    assert engine.run(rid)["data"]["usage"]["observed_tokens"] == 140


def test_stop_keeps_completed_attempt_evidence(setup):
    engine, rid, epoch = setup
    attempt = engine.prepare(rid, "a", "owner", epoch)["attempt"]
    engine.send_start(rid, attempt["id"], "owner", epoch)
    engine.stop(rid)
    ref = engine.artifact({"report": "停止请求到达前已完成"})
    engine.complete_attempt(rid, attempt["id"], ref, stopped=True)
    engine.settle(rid, "owner", epoch)
    state = engine.run(rid)["data"]
    assert state["status"] == "paused"
    assert state["attempts"][attempt["id"]]["state"] == "succeeded"
    assert state["works"]["a"]["state"] == "result-ready"


def test_history_cursor_and_tampered_artifact(setup):
    engine, rid, epoch = setup
    for i in range(5):
        engine.message(rid, "工作记录 " + str(i))
    first = engine.history(rid, "工作记录", limit=2)
    second = engine.history(rid, "工作记录", after=first["next_cursor"], limit=10)
    assert len(first["events"]) == 2 and len(second["events"]) == 3
    ref = engine.artifact({"report": "valid"})
    Path(ref["path"]).write_text("changed", encoding="utf-8")
    with pytest.raises(ConflictError):
        engine.read_artifact(ref)
