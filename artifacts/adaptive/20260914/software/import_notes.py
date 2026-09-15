#!/usr/bin/env python3
"""Import profile notes from a CSV file into a local SQLite database.

The module intentionally uses only Python's standard library.  The public
``import_csv`` function is useful to callers that want the same transactional
behavior as the command-line interface.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence, TextIO, Union
from urllib.parse import urlsplit


EXPECTED_COLUMNS = ("id", "title", "url")
TABLE_NAME = "notes"
PathLike = Union[str, Path]


class ImportNotesError(Exception):
    """An expected, user-facing import failure."""

    code = "import_error"


class InputFileError(ImportNotesError):
    code = "input_error"


class CsvFormatError(ImportNotesError):
    code = "csv_error"


class ValidationError(ImportNotesError):
    code = "validation_error"


class ConflictError(ImportNotesError):
    code = "conflict"


class DatabaseError(ImportNotesError):
    code = "database_error"


class UsageError(ImportNotesError):
    code = "usage_error"


class Record(NamedTuple):
    row_number: int
    id: str
    title: str
    url: str


CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL
)
"""


def is_valid_http_url(value: str) -> bool:
    """Return whether *value* has an HTTP(S) scheme and a non-empty host.

    This is deliberately syntactic validation.  The importer never makes a
    network request and therefore does not claim that the host is reachable.
    """

    if not value or any(character.isspace() for character in value):
        return False

    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            return False
        if not parsed.netloc or not parsed.hostname:
            return False
        # Accessing .port validates malformed and out-of-range port values.
        parsed.port
    except ValueError:
        return False

    return True


def _read_records(input_path: Path) -> List[Record]:
    """Read, normalize, and validate all CSV records before touching SQLite."""

    try:
        stream = input_path.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as exc:
        raise InputFileError(f"无法读取输入文件：{exc}") from exc

    records: List[Record] = []
    try:
        with stream:
            reader = csv.reader(stream, strict=True)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise CsvFormatError("CSV 文件为空，首行必须是 id、title、url") from exc

            if len(header) != len(EXPECTED_COLUMNS) or set(header) != set(EXPECTED_COLUMNS):
                expected = ",".join(EXPECTED_COLUMNS)
                actual = ",".join(header) if header else "（空）"
                raise CsvFormatError(
                    f"CSV 首行必须恰好包含列 {expected}，实际为 {actual}"
                )
            positions = {name: header.index(name) for name in EXPECTED_COLUMNS}

            for row in reader:
                row_number = reader.line_num
                # A blank physical line is not a profile entry.  Rows such as
                # ",," are retained and correctly fail empty-field checks.
                if not row:
                    continue
                if len(row) != len(EXPECTED_COLUMNS):
                    raise CsvFormatError(
                        f"CSV 第 {row_number} 行应有 3 列，实际有 {len(row)} 列"
                    )

                item_id = row[positions["id"]].strip()
                title = row[positions["title"]].strip()
                url = row[positions["url"]]

                if not item_id:
                    raise ValidationError(f"CSV 第 {row_number} 行的 id 去除首尾空白后不能为空")
                if not title:
                    raise ValidationError(f"CSV 第 {row_number} 行的 title 去除首尾空白后不能为空")
                if not is_valid_http_url(url):
                    raise ValidationError(
                        f"CSV 第 {row_number} 行的 url 必须是带主机的 http/https URL"
                    )

                records.append(Record(row_number, item_id, title, url))
    except UnicodeDecodeError as exc:
        raise InputFileError(f"输入文件不是有效的 UTF-8：{exc}") from exc
    except csv.Error as exc:
        line_number = getattr(locals().get("reader"), "line_num", "未知")
        raise CsvFormatError(f"CSV 格式错误（第 {line_number} 行）：{exc}") from exc

    seen_rows = {}
    for record in records:
        previous_row = seen_rows.get(record.id)
        if previous_row is not None:
            raise ConflictError(
                f"CSV 第 {record.row_number} 行的 id {record.id!r} "
                f"与第 {previous_row} 行重复"
            )
        seen_rows[record.id] = record.row_number

    return records


def _rollback(connection: sqlite3.Connection) -> None:
    """Rollback while preserving the original exception if rollback fails."""

    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def import_csv(input_path: PathLike, db_path: PathLike) -> int:
    """Atomically import *input_path* into *db_path* and return row count.

    The entire input is parsed and validated before the database transaction is
    opened.  Database creation, conflict checking, and inserts then happen in
    one SQLite transaction.  Any expected failure leaves existing rows intact.
    """

    source = Path(input_path)
    database = Path(db_path)
    records = _read_records(source)

    connection: Optional[sqlite3.Connection] = None
    try:
        connection = sqlite3.connect(str(database), timeout=5.0)
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise DatabaseError(f"无法打开 SQLite 数据库：{exc}") from exc

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(CREATE_TABLE_SQL)

        for record in records:
            existing = connection.execute(
                f"SELECT 1 FROM {TABLE_NAME} WHERE id = ? LIMIT 1", (record.id,)
            ).fetchone()
            if existing is not None:
                raise ConflictError(
                    f"CSV 第 {record.row_number} 行的 id {record.id!r} "
                    "已存在于数据库中"
                )

        connection.executemany(
            f"INSERT INTO {TABLE_NAME} (id, title, url) VALUES (?, ?, ?)",
            ((record.id, record.title, record.url) for record in records),
        )
        connection.commit()
        return len(records)
    except ImportNotesError:
        _rollback(connection)
        raise
    except sqlite3.Error as exc:
        _rollback(connection)
        raise DatabaseError(f"SQLite 操作失败：{exc}") from exc
    finally:
        connection.close()


# A descriptive alias for callers that use the script name as the operation.
import_notes = import_csv


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(
        description="将 UTF-8 CSV 个人资料条目原子导入 SQLite"
    )
    parser.add_argument("input_csv", metavar="INPUT.csv", type=Path)
    parser.add_argument("--db", required=True, metavar="PATH", type=Path)
    return parser


def _write_json(payload: object, stream: TextIO) -> None:
    print(json.dumps(payload, ensure_ascii=False), file=stream)


def _configure_utf8_output() -> None:
    """Make JSON output portable across Windows console code pages."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return a process exit status."""

    _configure_utf8_output()
    try:
        args = _build_parser().parse_args(argv)
        count = import_csv(args.input_csv, args.db)
    except ImportNotesError as exc:
        _write_json({"error": exc.code, "message": str(exc)}, sys.stderr)
        return 1

    _write_json({"imported": count}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
