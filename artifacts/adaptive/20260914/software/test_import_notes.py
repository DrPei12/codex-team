import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


SCRIPT = Path(__file__).with_name("import_notes.py")


class ImportNotesCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.csv_path = self.root / "profiles.csv"
        self.db_path = self.root / "notes.sqlite3"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_csv(self, rows, *, bom=False, header=("id", "title", "url")):
        encoding = "utf-8-sig" if bom else "utf-8"
        with self.csv_path.open("w", encoding=encoding, newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)

    def run_cli(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.csv_path), "--db", str(self.db_path)],
            cwd=str(SCRIPT.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def create_database(self, rows):
        with closing(sqlite3.connect(self.db_path)) as connection:
            with connection:
                connection.execute(
                    "CREATE TABLE notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL)"
                )
                connection.executemany(
                    "INSERT INTO notes (id, title, url) VALUES (?, ?, ?)", rows
                )

    def database_rows(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            return connection.execute(
                "SELECT id, title, url FROM notes ORDER BY id"
            ).fetchall()

    def assert_error(self, result, code):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertEqual(payload["error"], code)
        self.assertTrue(payload["message"])
        return payload

    def test_success_supports_bom_chinese_quoting_and_normalizes_id_title(self):
        self.write_csv(
            [
                [
                    "  资料-1  ",
                    "  中文标题, 第一篇\n第二行  ",
                    "https://example.com/notes/1?tag=a,b",
                ],
                ["资料-2", "带引号的 \"标题\"", "http://localhost:8080/path"],
            ],
            bom=True,
        )

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"imported": 2})
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            self.database_rows(),
            [
                ("资料-1", "中文标题, 第一篇\n第二行", "https://example.com/notes/1?tag=a,b"),
                ("资料-2", '带引号的 "标题"', "http://localhost:8080/path"),
            ],
        )

    def test_empty_id_or_title_is_rejected_and_new_database_has_no_rows(self):
        cases = (
            (["   ", "有效标题", "https://example.com"], "id"),
            (["valid-id", " \t ", "https://example.com"], "title"),
        )

        for row, field in cases:
            with self.subTest(field=field):
                self.write_csv([row])
                result = self.run_cli()
                payload = self.assert_error(result, "validation_error")
                self.assertIn(field, payload["message"])
                self.assertFalse(self.db_path.exists())

    def test_invalid_urls_are_rejected_without_touching_existing_rows(self):
        invalid_urls = ("ftp://example.com", "example.com/path", "https:///missing-host")

        for index, url in enumerate(invalid_urls):
            with self.subTest(url=url):
                self.db_path = self.root / f"invalid-{index}.sqlite3"
                self.create_database(
                    [("keep", "保留的数据", "https://existing.example/keep")]
                )
                self.write_csv(
                    [["new", "不会写入", "https://new.example"], ["bad", "错误 URL", url]]
                )

                result = self.run_cli()

                payload = self.assert_error(result, "validation_error")
                self.assertIn("url", payload["message"])
                self.assertEqual(
                    self.database_rows(),
                    [("keep", "保留的数据", "https://existing.example/keep")],
                )

    def test_duplicate_id_within_batch_rolls_back_all_rows(self):
        self.create_database(
            [("keep", "已有数据", "https://existing.example/keep")]
        )
        self.write_csv(
            [
                ["new", "新资料", "https://new.example"],
                [" new ", "重复资料", "https://duplicate.example"],
            ]
        )

        result = self.run_cli()

        payload = self.assert_error(result, "conflict")
        self.assertIn("重复", payload["message"])
        self.assertEqual(
            self.database_rows(),
            [("keep", "已有数据", "https://existing.example/keep")],
        )

    def test_conflict_with_existing_id_rolls_back_prior_new_rows(self):
        self.create_database(
            [("keep", "已有数据", "https://existing.example/keep")]
        )
        self.write_csv(
            [
                ["new", "本应回滚", "https://new.example"],
                ["keep", "不应覆盖", "https://other.example"],
            ]
        )

        result = self.run_cli()

        payload = self.assert_error(result, "conflict")
        self.assertIn("已存在", payload["message"])
        self.assertEqual(
            self.database_rows(),
            [("keep", "已有数据", "https://existing.example/keep")],
        )

    def test_header_and_csv_shape_errors_are_json_and_nonzero(self):
        self.write_csv([["id", "title", "url", "extra"]], header=("id", "title", "url"))

        result = self.run_cli()

        self.assert_error(result, "csv_error")
        self.assertFalse(self.db_path.exists())


if __name__ == "__main__":
    unittest.main()
