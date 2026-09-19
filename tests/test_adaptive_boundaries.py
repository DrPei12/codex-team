"""Real CLI/storage boundaries; native fault doubles are labeled explicitly."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from team_runtime.adaptive import Adaptive, ConflictError
from team_runtime.adaptive_runner import Runner
from team_runtime.codex import CodexError
from test_adaptive import work, complete, setup


def test_invalidation_preserves_unrelated_evidence_and_old_acceptance(setup):
    e, rid, epoch = setup
    _, a = complete(e, rid, epoch)
    e.accept(rid, "a", a["sha256"], "checked")
    _, b = complete(e, rid, epoch, "b")
    e.accept(rid, "b", b["sha256"], "checked")
    d = e.run(rid)["data"]
    e.revise(rid, d["plan_revision"], "independent evidence", add=[work("c")])
    _, c = complete(e, rid, epoch, "c")
    e.accept(rid, "c", c["sha256"], "checked")
    out = e.invalidate(rid, "a", "source withdrawn")
    assert out["affected_work_ids"] == ["a", "b"]
    d = e.run(rid)["data"]
    assert [a["valid"] for a in d["acceptances"]] == [False, False, True]
    assert d["works"]["c"]["state"] == "accepted"
    assert not e.eligible(d)
    e.revise(rid, d["plan_revision"], "repair affected source", update=[{"id": "a", "state": "queued"}])
    assert [w["id"] for w in e.eligible(e.run(rid)["data"])] == ["a"]


def test_new_user_message_prevents_stale_completion(setup):
    e, rid, epoch = setup
    for wid in ["a", "b"]:
        _, ref = complete(e, rid, epoch, wid)
        e.accept(rid, wid, ref["sha256"], "checked")
    fingerprint = Runner.decision_fingerprint(e.run(rid)["data"])
    e.message(rid, "runtime observation", author="runtime")
    assert Runner.decision_fingerprint(e.run(rid)["data"]) == fingerprint
    e.message(rid, "Please change the audience")
    assert Runner.decision_fingerprint(e.run(rid)["data"]) != fingerprint
    with pytest.raises(ConflictError, match="New user input"):
        e.finish(rid, "old judgment", expected_message_revision=0)
    assert e.run(rid)["data"]["status"] == "running"
    e.finish(rid, "new judgment", expected_message_revision=1)
    with pytest.raises(ConflictError, match="successor"):
        e.message(rid, "Another delegation")


def test_coordinator_note_does_not_become_user_input(setup):
    e, rid, epoch = setup
    attempt = e.prepare_coordination(rid, "owner", epoch)["attempt"]
    e.send_start(rid, attempt["id"], "owner", epoch)
    e.message(rid, "Reviewed evidence", note=True, attempt_id=attempt["id"])
    d = e.run(rid)["data"]
    assert d["messages"][-1]["attempt_id"] == attempt["id"]
    assert d.get("message_revision", 0) == 0


def test_turn_binding_retains_verified_native_configuration(setup):
    e, rid, epoch = setup
    a = e.prepare(rid, "a", "owner", epoch)["attempt"]
    e.send_start(rid, a["id"], "owner", epoch)
    config = {"model": "gpt-5.6-luna", "effort": "max", "sandbox": {"type": "readOnly"}}
    e.bind(rid, a["id"], thread_id="real-config-test", configuration=config)
    e.bind(rid, a["id"], thread_id="real-config-test", turn_id="turn")
    d = e.run(rid)["data"]
    assert d["attempts"][a["id"]]["configuration"] == config
    assert next(iter(d["sessions"].values()))["configuration"] == config


def test_interrupt_rpc_fault_is_sent_once(setup):
    """Injected native RPC timeout with an already observed terminal event."""
    e, rid, epoch = setup
    r = Runner(e, rid)
    r.owner, r.epoch, r.deadline, r._heartbeat = "owner", epoch, time.monotonic() + 60, time.monotonic()
    e.stop(rid)
    class NativeFault:
        calls = 0
        def request(self, *args, **kwargs):
            self.calls += 1
            raise CodexError("injected timeout after delivery")
        def _terminal_turn(self, *args):
            return {"status": "interrupted"}
    client = NativeFault()
    r.tick(client, "t", "turn")
    r.tick(client, "t", "turn")
    assert client.calls == 1


def test_cli_uses_actual_files_and_persistent_state(tmp_path):
    project = tmp_path / "ordinary-research-folder"
    project.mkdir()
    definition = tmp_path / "definition.md"
    definition.write_text("A complete narrative definition", encoding="utf-8")
    authority = tmp_path / "authority.md"
    authority.write_text("Read-only investigation", encoding="utf-8")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([work("research")]), encoding="utf-8")
    cli = Path(__file__).resolve().parents[1] / "scripts/team.py"
    base = [sys.executable, "-B", str(cli), "--state", str(tmp_path / "state")]
    def run(*args):
        p = subprocess.run(base + list(args), capture_output=True, text=True, encoding="utf-8", timeout=15)
        assert p.returncode == 0, p.stdout + p.stderr
        return json.loads(p.stdout)
    created = run("create", "--workspace", str(project), "--definition-file", str(definition),
                  "--authority-file", str(authority), "--plan-file", str(plan), "--operation-id", "new-project")
    snap = run("snapshot", created["run_id"])
    assert snap["definition_text"] == definition.read_text(encoding="utf-8")
    assert not (project / ".git").exists()
    assert run("list")["runs"][0]["id"] == created["run_id"]


def test_process_exit_rolls_back_state_event_and_outbox(tmp_path):
    from team_runtime.store import Store
    db = tmp_path / "crash.sqlite3"
    Store(db)
    script = """import os,sys
from team_runtime.store import Store
s=Store(sys.argv[1])
def crash(tx):
 tx.put('work','a',{'state':'assigned'})
 tx.event('run','assigned',{})
 tx.put('outbox','a',{'state':'pending'})
 os._exit(17)
s.command('run','one',{},crash)
"""
    p = subprocess.run([sys.executable, "-B", "-c", script, str(db)], timeout=15)
    assert p.returncode == 17
    s = Store(db)
    assert s.get("work", "a") is None and s.get("outbox", "a") is None
    assert s.events("run") == []
