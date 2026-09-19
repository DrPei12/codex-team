from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from team_runtime.store import ConflictError, Store


ROOT = Path(__file__).resolve().parents[1]


def test_put_get_list_reopen_and_strict_cas(tmp_path: Path) -> None:
    database = tmp_path / "state" / "team.sqlite3"
    store = Store(database)
    data = {
        "brief": "整理衣物 ♻️",
        "nested": {"items": [1, True, None, "中文"]},
    }

    created = store.put("plan", "plan-1", data)
    assert created["revision"] == 1
    assert created["id"] == "plan-1"
    assert created["kind"] == "plan"
    assert created["data"] == data
    assert datetime.fromisoformat(created["updated_at"].replace("Z", "+00:00")).tzinfo

    # The Store persists a JSON copy, so mutating an input or returned value
    # cannot silently mutate durable state.
    data["nested"]["items"].append("caller mutation")
    fetched = store.get("plan", "plan-1")
    assert fetched is not None
    assert fetched["data"]["nested"]["items"] == [1, True, None, "中文"]

    with pytest.raises(ConflictError):
        store.put("plan", "plan-1", {"status": "overwritten"})

    updated = store.put(
        "plan",
        "plan-1",
        {"status": "approved"},
        expected_revision=created["revision"],
    )
    assert updated["revision"] == 2
    with pytest.raises(ConflictError):
        store.put("plan", "plan-1", {"status": "stale"}, expected_revision=1)

    store.put("plan", "plan-2", {"status": "draft"})
    listed = store.list("plan")
    assert {item["id"] for item in listed} == {"plan-1", "plan-2"}
    assert store.get("missing", "none") is None

    store.close()
    reopened = Store(database)
    assert reopened.get("plan", "plan-1") == updated
    assert reopened.get("plan", "plan-2")["revision"] == 1
    reopened.close()


def test_concurrent_cas_allows_one_winner(tmp_path: Path) -> None:
    database = tmp_path / "cas.sqlite3"
    setup = Store(database)
    initial = setup.put("run", "run-1", {"winner": None})
    setup.close()

    worker_count = 8
    barrier = threading.Barrier(worker_count)

    def update(worker_id: int) -> bool:
        worker = Store(database)
        try:
            observed = worker.get("run", "run-1")
            assert observed is not None
            barrier.wait(timeout=10)
            try:
                worker.put(
                    "run",
                    "run-1",
                    {"winner": worker_id},
                    expected_revision=observed["revision"],
                )
            except ConflictError:
                return False
            return True
        finally:
            worker.close()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(update, range(worker_count)))

    assert sum(results) == 1
    final = Store(database).get("run", "run-1")
    assert final is not None
    assert final["revision"] == initial["revision"] + 1
    assert final["data"]["winner"] in range(worker_count)


def test_append_event_is_idempotent_and_paginated(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    store = Store(database)

    first = store.append_event(
        "run-1", "started", {"message": "开始"}, dedupe_key="start"
    )
    duplicate = store.append_event(
        "run-1",
        "different-type",
        {"message": "must be ignored"},
        dedupe_key="start",
    )
    second = store.append_event("run-1", "progress", {"percent": 50})
    other_run = store.append_event("run-2", "started", {})

    assert duplicate == first
    assert first["seq"] == 1
    assert second["seq"] == 2
    assert other_run["seq"] == 1
    assert store.events("run-1") == [first, second]
    assert store.events("run-1", after=1) == [second]
    assert store.events("run-1", limit=1) == [first]
    assert store.events("run-1", limit=0) == []
    assert datetime.fromisoformat(first["created_at"].replace("Z", "+00:00")).tzinfo

    store.close()
    reopened = Store(database)
    assert reopened.events("run-1") == [first, second]
    reopened.close()


def _claim_in_subprocess(
    database: Path,
    resource: str,
    owner: str,
    ttl_seconds: float,
) -> bool:
    code = """
import json
import sys
from team_runtime.store import Store

store = Store(sys.argv[1])
try:
    print(json.dumps(store.claim(sys.argv[2], sys.argv[3], ttl_seconds=float(sys.argv[4]))))
finally:
    store.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(database), resource, owner, str(ttl_seconds)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_lease_is_exclusive_renews_expires_and_checks_owner(tmp_path: Path) -> None:
    database = tmp_path / "leases.sqlite3"
    store = Store(database)
    assert store.claim("controller", "owner-a", ttl_seconds=0.12)
    assert not store.claim("controller", "owner-b", ttl_seconds=1)
    assert store.claim("controller", "owner-a", ttl_seconds=0.12)
    assert not store.release("controller", "owner-b")
    assert store.release("controller", "owner-a")
    assert not store.release("controller", "owner-a")

    # A separate process observes the same SQLite lease and cannot acquire it
    # while it is live.  After expiry, it can atomically take ownership.
    # Keep the live window comfortably above Windows interpreter startup time.
    assert store.claim("worker:1", "owner-a", ttl_seconds=3)
    assert not _claim_in_subprocess(database, "worker:1", "owner-b", 1)
    time.sleep(3.20)
    assert _claim_in_subprocess(database, "worker:1", "owner-b", 1)
    assert not store.release("worker:1", "owner-a")
    assert store.release("worker:1", "owner-b")
    store.close()
