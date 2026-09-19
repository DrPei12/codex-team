"""Continue an actual v1.0.1 adaptive record without converting its format."""
import json
from pathlib import Path

from team_runtime.adaptive import Adaptive
from team_runtime.adaptive_runner import reconcile


def test_v101_record_preserves_intent_history_and_artifact_identity(tmp_path):
    fixture = json.loads((Path(__file__).parent/"fixtures/adaptive-0.3.json").read_text(encoding="utf-8"))
    state, workspace = tmp_path/"state", tmp_path/"workspace"
    workspace.mkdir()
    engine = Adaptive(state)

    def resolve(value):
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if isinstance(value, str):
            for marker, root in (("__STATE__", state), ("__WORKSPACE__", workspace)):
                if value.startswith(marker):
                    return str(root.joinpath(*value[len(marker):].replace("\\", "/").strip("/").split("/")))
        return value

    original = resolve(fixture["data"])
    rid = original["id"]
    for relative, content in fixture["artifacts"].items():
        target = state/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    engine.store.put("adaptive-run", rid, original)
    def restore(tx):
        for event in resolve(fixture["events"]):
            tx.event(rid, event["type"], event["payload"])
        return {"restored": True}
    engine.store.command(rid, "restore-test-fixture", {}, restore)

    before = engine.snapshot(rid)
    assert before["data"]["schema_version"] == "0.3"
    assert before["data"]["status"] == "pause-requested"
    assert "entry_count=3" in before["definition_text"]
    assert "Additional user direction" in json.dumps(engine.history(rid, "entry_count=3"))
    original_hash = before["data"]["definition"]["sha256"]
    reconcile(engine, rid)  # No attempts were dispatched in this old record.
    epoch = engine.controller(rid, "continuing-controller")["epoch"]
    engine.start(rid, "continuing-controller", epoch)
    after = engine.snapshot(rid)
    assert after["data"]["id"] == rid
    assert after["data"]["schema_version"] == "0.3"
    assert after["data"]["status"] == "running"
    assert after["data"]["definition"]["sha256"] == original_hash
    assert after["data"]["policy"] == original["policy"]
    assert after["data"]["works"] == original["works"]
    assert "entry_count=3" in after["definition_text"]
    assert len(engine.store.events(rid)) > len(fixture["events"])
    engine.stop(rid)
    engine.settle(rid, "continuing-controller", epoch)
