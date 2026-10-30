"""Mutation checks for accidental publication of private data."""

import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_export", ROOT / "scripts/check_public_export.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class PublicExportTests(unittest.TestCase):
    def setUp(self):
        self.workflow = json.loads((ROOT / "workflow.public.json").read_text())

    def test_public_files_pass(self):
        for path in (".env.example", ".gitignore", "README.md", "workflow.public.json"):
            with self.subTest(path=path):
                self.assertEqual(CHECK.check_file(path, (ROOT / path).read_bytes()), [])

    def test_private_export_and_database_names_fail(self):
        for path in (
            ".env", "local.env", "database.sqlite-wal", "database.sqlite-shm",
            "database.sqlite3-wal", "database.db", "credentials.json", "workflow.json",
            "n8n_data/config", "backups/n8n.zip", "exports/credentials.json",
            "nested/.env.example", "nested/workflow.public.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(CHECK.check_file(path, b"{}"))

    def test_filled_environment_template_fails(self):
        self.assertTrue(CHECK.check_file(".env.example", b"TAXCOM_PASSWORD=not-a-real-secret\n"))

    def test_private_n8n_payloads_fail(self):
        for key, value in (
            ("pinData", {"Login": [{"json": {"demo": "synthetic"}}]}),
            ("credentials", {"telegramApi": {"name": "local", "id": "local"}}),
            ("meta", {"instanceId": "synthetic-instance"}),
            ("staticData", {}),
            ("active", True),
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.workflow)
                changed[key] = value
                self.assertTrue(CHECK.check_workflow(changed))

    def test_literal_chat_id_fails(self):
        telegram = next(n for n in self.workflow["nodes"] if n["type"].endswith(".telegram"))
        telegram["parameters"]["chatId"] = str(100000000 + 12345)
        self.assertTrue(CHECK.check_workflow(self.workflow))

    def test_literal_authentication_and_external_destination_fail(self):
        login = next(n for n in self.workflow["nodes"] if n["name"] == "Taxcom Login")
        for field, value in (("url", "https://example.invalid/collect"), ("jsonBody", "{}")):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.workflow)
                node = next(n for n in changed["nodes"] if n["name"] == login["name"])
                node["parameters"][field] = value
                self.assertTrue(CHECK.check_workflow(changed))

    def test_literal_taxcom_identifier_fails(self):
        node = next(n for n in self.workflow["nodes"] if n["name"] == "Get KKT")
        node["parameters"]["queryParameters"]["parameters"][0]["value"] = "synthetic-outlet"
        self.assertTrue(CHECK.check_workflow(self.workflow))

    def test_raw_exports_are_rejected_even_when_renamed(self):
        payloads = (
            self.workflow,
            [{"type": "telegramApi", "data": {"sample": "synthetic"}}],
            {"password": "not-a-real-secret"},
        )
        for payload in payloads:
            with self.subTest(payload_type=type(payload).__name__):
                self.assertTrue(CHECK.check_file("renamed.json", json.dumps(payload).encode()))

    def test_deleted_token_is_still_detected_in_history_without_logging_it(self):
        synthetic = str(123456789) + ":" + "A" * 35
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True)
            git("init", "-q")
            git("config", "user.name", "Publication checks")
            git("config", "user.email", "tests@example.invalid")
            (root / "notes.txt").write_text(synthetic)
            git("add", "notes.txt")
            git("commit", "-qm", "Synthetic history fixture")
            (root / "notes.txt").write_text("Clean current version\n")
            git("add", "notes.txt")
            git("commit", "-qm", "Remove synthetic token")
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(CHECK, "ROOT", root), patch("sys.argv", ["check", "--history"]):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    self.assertEqual(CHECK.main(), 1)
            self.assertIn("history", errors.getvalue())
            self.assertNotIn(synthetic, output.getvalue() + errors.getvalue())

    def test_known_token_is_detected_without_disclosing_value(self):
        synthetic = str(123456789) + ":" + "A" * 35
        errors = CHECK.scan_text("example\n" + synthetic)
        self.assertTrue(errors)
        self.assertIn("line 2", errors[0])
        self.assertNotIn(synthetic, " ".join(errors))

    def test_retention_is_required_only_for_current_export(self):
        for key in CHECK.RETENTION:
            changed = copy.deepcopy(self.workflow)
            del changed["settings"][key]
            self.assertTrue(CHECK.check_workflow(changed))
            self.assertEqual(CHECK.check_workflow(changed, current=False), [])

    def test_malformed_and_binary_exports_fail(self):
        for payload in (b"null", b"[]", b"{", b"\xff"):
            with self.subTest(payload=repr(payload)):
                self.assertTrue(CHECK.check_file("workflow.public.json", payload))

    def test_gitignore_blocks_private_files_and_keeps_public_files(self):
        blocked = (
            ".env", ".env.production", "local.env", "secrets.env", ".n8n/config",
            "database.sqlite", "database.sqlite-wal", "database.sqlite-shm",
            "database.sqlite3-wal", "database.db", "credentials.json",
            "credentials.decrypted.json", "workflow.json", "workflow.private.json",
            "n8n_data/config", "n8n_data/binaryData/receipt.json", "backups/n8n.zip",
            "exports/credentials.json",
        )
        allowed = (".env.example", "workflow.public.json", "README.md", ".gitignore")
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(["git", "init", "-q", directory], check=True)
            (Path(directory) / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
            for expected, paths in ((0, blocked), (1, allowed)):
                for path in paths:
                    with self.subTest(path=path):
                        result = subprocess.run(
                            ["git", "-C", directory, "check-ignore", "--no-index", path],
                            capture_output=True,
                        )
                        self.assertEqual(result.returncode, expected)


if __name__ == "__main__":
    unittest.main()
