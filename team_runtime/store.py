"""SQLite backed state store for the Team Auto runtime.

The runtime keeps all mutable state in this module so that the controller and
the HTTP board can use the same durable facts.  Connections are intentionally
short lived: every operation opens its own connection, performs one complete
transaction (for writes), and closes it.  SQLite therefore provides the
cross-thread and cross-process serialization needed by CAS updates, event
sequence allocation, and leases without a process-local lock.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import uuid
from typing import Any, Iterator


class ConflictError(RuntimeError):
    """Raised when an optimistic update does not match the stored revision."""


_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS entities (
        kind TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision >= 1),
        data_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (kind, entity_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS entities_updated_at
        ON entities (updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        run_id TEXT NOT NULL,
        seq INTEGER NOT NULL CHECK (seq >= 1),
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        dedupe_key TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (run_id, seq),
        UNIQUE (run_id, dedupe_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS events_run_seq
        ON events (run_id, seq)
    """,
    """
    CREATE TABLE IF NOT EXISTS leases (
        resource TEXT PRIMARY KEY,
        owner TEXT NOT NULL,
        expires_at REAL NOT NULL
    )
    """,
)


def _utc_now() -> str:
    """Return a canonical ISO-8601 UTC timestamp for persisted envelopes."""

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _json_object(value: dict[str, Any], name: str) -> str:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    try:
        # SQLite stores Python str as UTF-8.  Disallow NaN/Infinity so a value
        # written by one process is valid JSON for every reader.
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc


def _decoded_object(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        # This should be impossible through the public API, but keeping the
        # invariant explicit makes corrupt/manual databases fail loudly.
        raise ValueError("stored JSON value is not an object")
    return decoded


class Store:
    """Durable state, append-only events, and cross-process leases in SQLite."""

    _busy_timeout_ms = 30_000

    def __init__(self, path: str | Path):
        raw_path = os.fspath(path)
        if not isinstance(raw_path, str):
            raise TypeError("path must be a string or Path")

        self._memory_keeper: sqlite3.Connection | None = None
        if raw_path == ":memory:":
            # A normal ':memory:' database is scoped to one SQLite connection,
            # which would defeat the per-operation connection contract.  A
            # private shared-cache database keeps the convenience of an
            # in-memory Store while still allowing each operation its own
            # connection.  The keeper keeps that database alive.
            self._uri = True
            self._database = (
                f"file:codex_team_store_{uuid.uuid4().hex}?mode=memory&cache=shared"
            )
            self._memory_keeper = self._connect()
            self._initialize(self._memory_keeper)
        else:
            database_path = Path(raw_path)
            database_path.parent.mkdir(parents=True, exist_ok=True)
            self._uri = False
            self._database = str(database_path)
            connection = self._connect()
            try:
                self._initialize(connection)
            finally:
                connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database,
            timeout=self._busy_timeout_ms / 1000,
            isolation_level=None,
            check_same_thread=False,
            uri=self._uri,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        if not self._uri:
            # WAL lets board reads proceed while a controller writes.  This is
            # a database setting, so set it once while constructing the Store.
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA:
                connection.execute(statement)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    @contextmanager
    def _write_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            # BEGIN IMMEDIATE reserves the single SQLite writer slot before a
            # read/compare/write sequence.  This makes the CAS and sequence
            # allocation atomic across threads and processes.
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        finally:
            connection.close()

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _entity_envelope(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["entity_id"],
            "kind": row["kind"],
            "revision": int(row["revision"]),
            "data": _decoded_object(row["data_json"]),
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _event_envelope(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "seq": int(row["seq"]),
            "run_id": row["run_id"],
            "type": row["event_type"],
            "payload": _decoded_object(row["payload_json"]),
            "created_at": row["created_at"],
        }

    def put(
        self,
        kind: str,
        entity_id: str,
        data: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create or compare-and-swap update an entity envelope."""

        kind = _text(kind, "kind")
        entity_id = _text(entity_id, "entity_id")
        encoded = _json_object(data, "data")
        if expected_revision is not None:
            if isinstance(expected_revision, bool) or not isinstance(
                expected_revision, int
            ):
                raise TypeError("expected_revision must be an integer or None")
            if expected_revision < 0:
                raise ValueError("expected_revision must be non-negative")

        with self._write_connection() as connection:
            row = connection.execute(
                """
                SELECT kind, entity_id, revision, data_json, updated_at
                FROM entities
                WHERE kind = ? AND entity_id = ?
                """,
                (kind, entity_id),
            ).fetchone()

            if expected_revision is None:
                if row is not None:
                    raise ConflictError(
                        f"entity already exists: {kind}/{entity_id}"
                    )
                revision = 1
                updated_at = _utc_now()
                connection.execute(
                    """
                    INSERT INTO entities
                        (kind, entity_id, revision, data_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (kind, entity_id, revision, encoded, updated_at),
                )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    actual = None if row is None else int(row["revision"])
                    raise ConflictError(
                        f"revision conflict for {kind}/{entity_id}: "
                        f"expected {expected_revision}, actual {actual}"
                    )
                revision = expected_revision + 1
                updated_at = _utc_now()
                changed = connection.execute(
                    """
                    UPDATE entities
                    SET revision = ?, data_json = ?, updated_at = ?
                    WHERE kind = ? AND entity_id = ? AND revision = ?
                    """,
                    (
                        revision,
                        encoded,
                        updated_at,
                        kind,
                        entity_id,
                        expected_revision,
                    ),
                )
                if changed.rowcount != 1:
                    # BEGIN IMMEDIATE should make this unreachable, but retain
                    # the conditional write as the final CAS guard.
                    raise ConflictError(
                        f"revision conflict for {kind}/{entity_id}"
                    )

            # Decode the exact serialized value so callers never retain a
            # mutable reference to a value that the Store has accepted.
            return {
                "id": entity_id,
                "kind": kind,
                "revision": revision,
                "data": _decoded_object(encoded),
                "updated_at": updated_at,
            }

    def get(self, kind: str, entity_id: str) -> dict[str, Any] | None:
        kind = _text(kind, "kind")
        entity_id = _text(entity_id, "entity_id")
        with self._read_connection() as connection:
            row = connection.execute(
                """
                SELECT kind, entity_id, revision, data_json, updated_at
                FROM entities
                WHERE kind = ? AND entity_id = ?
                """,
                (kind, entity_id),
            ).fetchone()
        return None if row is None else self._entity_envelope(row)

    def list(self, kind: str) -> list[dict[str, Any]]:
        kind = _text(kind, "kind")
        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT kind, entity_id, revision, data_json, updated_at
                FROM entities
                WHERE kind = ?
                ORDER BY updated_at DESC, entity_id ASC
                """,
                (kind,),
            ).fetchall()
        return [self._entity_envelope(row) for row in rows]

    def append_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        """Append one event, returning the existing event for a duplicate key."""

        run_id = _text(run_id, "run_id")
        event_type = _text(event_type, "event_type")
        encoded = _json_object(payload, "payload")
        if dedupe_key is not None:
            dedupe_key = _text(dedupe_key, "dedupe_key")

        with self._write_connection() as connection:
            if dedupe_key is not None:
                existing = connection.execute(
                    """
                    SELECT run_id, seq, event_type, payload_json, created_at
                    FROM events
                    WHERE run_id = ? AND dedupe_key = ?
                    """,
                    (run_id, dedupe_key),
                ).fetchone()
                if existing is not None:
                    return self._event_envelope(existing)

            previous = connection.execute(
                "SELECT MAX(seq) AS max_seq FROM events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            seq = 1 if previous["max_seq"] is None else int(previous["max_seq"]) + 1
            created_at = _utc_now()
            connection.execute(
                """
                INSERT INTO events
                    (run_id, seq, event_type, payload_json, dedupe_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, seq, event_type, encoded, dedupe_key, created_at),
            )
            return {
                "seq": seq,
                "run_id": run_id,
                "type": event_type,
                "payload": _decoded_object(encoded),
                "created_at": created_at,
            }

    def events(
        self,
        run_id: str,
        after: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        run_id = _text(run_id, "run_id")
        if isinstance(after, bool) or not isinstance(after, int):
            raise TypeError("after must be an integer")
        if after < 0:
            raise ValueError("after must be non-negative")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must be non-negative")
        if limit == 0:
            return []

        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT run_id, seq, event_type, payload_json, created_at
                FROM events
                WHERE run_id = ? AND seq > ?
                ORDER BY seq ASC
                LIMIT ?
                """,
                (run_id, after, limit),
            ).fetchall()
        return [self._event_envelope(row) for row in rows]

    @staticmethod
    def _ttl(value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("ttl_seconds must be a number")
        ttl = float(value)
        if not math.isfinite(ttl) or ttl < 0:
            raise ValueError("ttl_seconds must be finite and non-negative")
        return ttl

    def tail_events(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """Read recent facts without rescanning an ever-growing run history."""
        run_id = _text(run_id, "run_id")
        if type(limit) is not int or not 0 <= limit <= 1000:
            raise ValueError("limit must be between 0 and 1000")
        with self._read_connection() as connection:
            rows = connection.execute(
                "SELECT run_id, seq, event_type, payload_json, created_at FROM events WHERE run_id = ? ORDER BY seq DESC LIMIT ?",
                (run_id, limit),
            ).fetchall()
        return [self._event_envelope(row) for row in reversed(rows)]

    def claim(
        self,
        resource: str,
        owner: str,
        *,
        ttl_seconds: float = 60,
    ) -> bool:
        """Atomically acquire or renew a lease for ``resource``."""

        resource = _text(resource, "resource")
        owner = _text(owner, "owner")
        ttl = self._ttl(ttl_seconds)
        now = time.time()
        expires_at = now + ttl

        with self._write_connection() as connection:
            row = connection.execute(
                "SELECT owner, expires_at FROM leases WHERE resource = ?",
                (resource,),
            ).fetchone()
            if (
                row is not None
                and row["owner"] != owner
                and float(row["expires_at"]) > now
            ):
                return False

            if row is None:
                connection.execute(
                    "INSERT INTO leases (resource, owner, expires_at) VALUES (?, ?, ?)",
                    (resource, owner, expires_at),
                )
            else:
                connection.execute(
                    """
                    UPDATE leases
                    SET owner = ?, expires_at = ?
                    WHERE resource = ?
                    """,
                    (owner, expires_at, resource),
                )
            return True

    def release(self, resource: str, owner: str) -> bool:
        """Release a lease only when its current owner matches ``owner``."""

        resource = _text(resource, "resource")
        owner = _text(owner, "owner")
        with self._write_connection() as connection:
            deleted = connection.execute(
                "DELETE FROM leases WHERE resource = ? AND owner = ?",
                (resource, owner),
            )
            return deleted.rowcount == 1

    def lease_owner(self, resource: str) -> str | None:
        """Observe an unexpired lease without acquiring or renewing it."""
        resource = _text(resource, "resource")
        with self._read_connection() as connection:
            row = connection.execute("SELECT owner, expires_at FROM leases WHERE resource = ?", (resource,)).fetchone()
        return row['owner'] if row and float(row['expires_at']) > time.time() else None

    def close(self) -> None:
        """Close the shared in-memory keeper, leaving file data untouched."""

        keeper = self._memory_keeper
        self._memory_keeper = None
        if keeper is not None:
            keeper.close()


__all__ = ["ConflictError", "Store"]
