from copy import deepcopy
from datetime import datetime

import pytest

from team_runtime.history import History
from team_runtime.store import Store


@pytest.fixture
def history(tmp_path):
    store = Store(tmp_path / "team.sqlite3")
    yield History(store)
    store.close()


def note(**changes):
    return {"current_goal": "检查中文 search", "decisions": ["使用原始证据"],
            "verified": ["tests passed"], "remaining": ["发布"],
            "next_action": "核验", "references": [], **changes}


def test_note_generations_reopen_and_original_references(history):
    original = history.store.append_event("run", "proof", {"message": "原始证据"})
    first = history.save_note("run", "a", note(references=[{"event_seq": original["seq"]}]))
    second = history.save_note("run", "a", note(current_goal="第二代", references=[{"event_seq": 1}]))
    history.save_note("run", "b", note())
    assert first["id"] != second["id"]
    assert datetime.fromisoformat(second["created_at"].replace("Z", "+00:00")).tzinfo
    assert history.latest_note("run", "a") == second
    assert history.latest_note("missing", "a") is None
    assert history.latest_note("run", "unknown") is None
    events = history.store.events("run")
    assert events[0] == original
    assert events[1]["payload"]["current_goal"] == first["current_goal"]
    reopened = Store(history.store._database)
    try:
        assert History(reopened).latest_note("run", "a") == second
    finally:
        reopened.close()


def test_search_language_and_source_retrieval(history):
    history.save_note("run", "a", note())
    history.store.append_event("run", "proof", {"package": "a", "message": "中文 Search evidence"})
    matches = history.search("run", "中文 SEARCH")
    assert [row["source_kind"] for row in matches] == ["note", "event"]
    for match in matches:
        assert history.store.events(match["reference"]["run_id"], after=match["seq"] - 1, limit=1)
    assert history.search("run", "中文 absent") == []
    assert history.search("run", "  ") == []


def test_pagination_isolation_and_package_filter(history):
    for index in range(510):
        history.store.append_event("run", "proof", {"package": "a", "message": f"filler {index}"})
    history.store.append_event("run", "proof", {"package": "a", "message": "needle 中文"})
    history.store.append_event("other", "proof", {"package": "a", "message": "needle 中文"})
    history.save_note("run", "b", note(current_goal="needle 中文"))
    assert len(history.search("run", "needle")) == 2
    assert [row["seq"] for row in history.search("run", "needle", package_id="a")] == [511]
    assert history.search("run", "needle", package_id="b")[0]["source_kind"] == "note"
    assert history.latest_note("run", "b")["seq"] == 512


@pytest.mark.parametrize("changes", [
    {"extra": 1}, {"current_goal": 1}, {"decisions": "wrong"}, {"verified": [True]},
    {"remaining": ["x"] * 33}, {"references": [{"event_seq": True}]},
    {"references": [{"event_seq": 999}]}, {"references": [{"path": "x"}]},
    {"references": [{"path": "x", "sha256": "bad"}]},
    {"references": [{"event_seq": 1, "unknown": "x"}]},
    {"next_action": "x" * 2049}, {"current_goal": "\ud800"},
    {"current_goal": "Bearer abcdefghi"},
])
def test_invalid_note_never_written(history, changes):
    before = history.store.events("run")
    with pytest.raises(ValueError):
        history.save_note("run", "a", note(**changes))
    assert history.store.events("run") == before


def test_note_input_copy_and_file_reference(history):
    value = note(references=[{"path": "证据/result.json", "sha256": "a" * 64}])
    saved = history.save_note("run", "a", value)
    expected = deepcopy(saved)
    value["references"][0]["path"] = "changed"
    saved["verified"].append("changed")
    assert history.latest_note("run", "a") == expected


def test_missing_fields_total_size_and_foreign_event_reference(history):
    history.store.append_event("other", "proof", {"message": "foreign"})
    missing = note()
    missing.pop("remaining")
    oversized = note(decisions=["中" * 2048] * 32)
    for invalid in (missing, oversized, note(references=[{"event_seq": 1}]), None):
        with pytest.raises(ValueError):
            history.save_note("run", "a", invalid)
    assert history.store.events("run") == []


def test_bounded_safe_output_and_query_validation(history):
    history.store.append_event("run", "proof", {"message": "x" * 3000 + " needle",
        "api_key": "arbitrary-sensitive", "nested": {"password": "private"},
        "authorization": "Bearer abcdefghi", "detail": "sk-" + "a" * 30})
    row = history.search("run", "needle")[0]
    assert "needle" in row["text"] and len(row["text"]) <= 800
    assert history.search("run", "arbitrary-sensitive") == []
    assert history.search("run", "private") == []
    assert history.search("run", "abcdefghi") == []
    assert history.search("run", "a" * 30) == []
    assert history.search("run", "needle", limit=0) == []
    for limit in (True, -1, 101, "20"):
        with pytest.raises(ValueError):
            history.search("run", "needle", limit=limit)
    with pytest.raises(ValueError):
        history.search("run", "x" * 513)
    for index in range(110):
        history.store.append_event("run", "match", {"value": index})
    assert len(history.search("run", "match", limit=100)) == 100
