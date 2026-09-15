"""Team-owned working notes and literal search over the Store event journal.

Notes are complete current working state, not a chain of summaries. Their event
sequence is also a durable retrieval reference. No transcript, external index,
filesystem contents, or Codex private storage is accessed here.
"""
from __future__ import annotations

import json
import re
import uuid

from .store import Store


_FIELDS = {"current_goal", "decisions", "verified", "remaining", "next_action", "references"}
_SECRET_KEY = re.compile(r"(?i)^(?:password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie|credential)s?$")
_SECRETS = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}|(?i:Bearer\s+[A-Za-z0-9._~+/-]+=*)|(?i:(?:password|api[_-]?key|access[_-]?token|refresh[_-]?token|secret)\s*[=:]\s*[^\s,;]+)")


def _text(value, name, maximum=2048):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if len(value) > maximum:
        raise ValueError(f"{name} is too long")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError(f"{name} must be UTF-8 text") from exc
    return value


def _identifier(value, name):
    if not _text(value, name, 200).strip():
        raise ValueError(f"{name} must not be blank")
    if _SECRETS.search(value):
        raise ValueError(f"{name} contains credential-like text")


def _safe(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SECRET_KEY.match(key) else _safe(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, str):
        return _SECRETS.sub("[REDACTED]", value)
    return value


class History:
    """Append notes and search one run; all writes go through Store."""

    def __init__(self, store: Store):
        self.store = store

    def _events(self, run_id):
        after = 0
        while True:
            page = self.store.events(run_id, after=after, limit=500)
            if not page:
                return
            yield from page
            after = page[-1]["seq"]
            if len(page) < 500:
                return

    @staticmethod
    def _note(event):
        return {**event["payload"], "seq": event["seq"],
                "run_id": event["run_id"], "created_at": event["created_at"]}

    def save_note(self, run_id, package_id, note: dict) -> dict:
        _identifier(run_id, "run_id")
        _identifier(package_id, "package_id")
        if not isinstance(note, dict) or set(note) != _FIELDS:
            raise ValueError("note requires exactly the documented fields")
        for key in ("current_goal", "next_action"):
            _text(note[key], key)
        for key in ("decisions", "verified", "remaining"):
            if not isinstance(note[key], list) or len(note[key]) > 32:
                raise ValueError(f"{key} must be a list of at most 32 strings")
            for item in note[key]:
                _text(item, key)
        refs = note["references"]
        if not isinstance(refs, list) or len(refs) > 32:
            raise ValueError("references must be a list of at most 32 references")
        for ref in refs:
            if not isinstance(ref, dict):
                raise ValueError("reference must be an object")
            if set(ref) == {"event_seq"}:
                seq = ref["event_seq"]
                if type(seq) is not int or seq < 1:
                    raise ValueError("event_seq must be a positive integer")
                found = self.store.events(run_id, after=seq - 1, limit=1)
                if not found or found[0]["seq"] != seq:
                    raise ValueError("event reference does not exist in this run")
            elif set(ref) == {"path", "sha256"}:
                if not _text(ref["path"], "reference path").strip():
                    raise ValueError("reference path must not be empty")
                if not isinstance(ref["sha256"], str) or not re.fullmatch(r"(?:sha256:)?[a-fA-F0-9]{64}", ref["sha256"]):
                    raise ValueError("sha256 must be 64 hexadecimal characters, optionally prefixed with sha256:")
            else:
                raise ValueError("reference requires event_seq or path and sha256")
        encoded = json.dumps(note, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 65536:
            raise ValueError("note exceeds 64 KiB")
        if _SECRETS.search(encoded):
            raise ValueError("note contains credential-like text")
        event = self.store.append_event(run_id, "work_note", {
            **note, "id": "note-" + uuid.uuid4().hex, "package_id": package_id,
        })
        return self._note(event)

    def latest_note(self, run_id, package_id) -> dict | None:
        _identifier(run_id, "run_id")
        _identifier(package_id, "package_id")
        latest = None
        for event in self._events(run_id):
            if event["type"] == "work_note" and event["payload"].get("package_id") == package_id:
                latest = event
        return None if latest is None else self._note(latest)

    def search(self, run_id, query, *, package_id=None, limit=20) -> list[dict]:
        """Case-insensitive AND substrings, in event order, capped at 100 hits.

        Matching reads complete safe event text; only the returned excerpt is
        truncated (800 characters). File references are locators, not assertions
        that a file exists or still has the recorded digest.
        """
        _identifier(run_id, "run_id")
        _text(query, "query", 512)
        if package_id is not None:
            _identifier(package_id, "package_id")
        if type(limit) is not int or not 0 <= limit <= 100:
            raise ValueError("limit must be an integer between 0 and 100")
        terms = query.casefold().split()
        if not terms or not limit:
            return []
        results = []
        for event in self._events(run_id):
            payload = event["payload"]
            packages = [payload.get(key) for key in ("package_id", "package", "from_package", "to_package")]
            if package_id is not None and package_id not in packages:
                continue
            text = json.dumps(_safe({"type": event["type"], "payload": payload}), ensure_ascii=False)
            folded = text.casefold()
            if not all(term in folded for term in terms):
                continue
            # Anchor the excerpt near the first matching term for long events.
            start = max(0, folded.find(terms[0]) - 120)
            excerpt = text[start:start + 798]
            excerpt = ("…" if start else "") + excerpt + ("…" if start + 798 < len(text) else "")
            result = {"source_kind": "note" if event["type"] == "work_note" else "event",
                      "seq": event["seq"], "time": event["created_at"], "text": excerpt,
                      "reference": {"run_id": run_id, "event_seq": event["seq"]}}
            if event["type"] == "work_note":
                result["id"] = payload["id"]
            results.append(result)
            if len(results) == limit:
                break
        return results
