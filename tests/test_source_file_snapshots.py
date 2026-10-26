from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core import source_analysis, source_index
from gxp_core.source_config import SOURCE_INDEX_VERSION


class SourceFileSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.index = self.root / "index"
        self.checkout = self.root / "checkout"
        self.relative = "src/core/common/service.ts"
        self.file = self.checkout / self.relative
        self.file.parent.mkdir(parents=True)
        self.raw = b"const sampleModel = 'old';\r\n"
        self.file.write_bytes(self.raw)
        self.enterContext(patch.object(source_index, "source_index_root", return_value=self.index))
        self.enterContext(patch.object(source_index, "source_index_lock_path", return_value=self.root / "index.lock"))
        self.status = {"index": {"generation": "gen"}, "repositories": {"frontend": {
            "stale": False, "selected": {"path": str(self.checkout)}, "index": {"fingerprint_generation": "gen"}}}}
        (self.index / "frontend").mkdir(parents=True)
        self.ledger = self.index / "frontend/file-fingerprints.json"
        self.ledger.write_text(json.dumps({"version": 1, "generation": "gen", "files": {
            self.relative: hashlib.sha256(self.raw).hexdigest()}}), encoding="utf-8")

    def test_scan_hashes_original_bytes_used_for_parse(self):
        data, failures = source_index._scan_frontend(self.checkout)
        self.assertEqual(failures, [])
        self.assertEqual(data["file_fingerprints"][self.relative], hashlib.sha256(self.raw).hexdigest())

    def test_same_size_same_mtime_edit_never_matches_old_index(self):
        stamp = self.file.stat()
        with source_index.source_read_view(self.status):
            self.assertEqual(source_index.verified_source_text(self.checkout, self.relative, "frontend"), self.raw.decode().replace("\r\n", "\n"))
            self.file.write_bytes(self.raw.replace(b"old", b"new"))
            os.utime(self.file, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            with self.assertRaisesRegex(source_index.SourceSnapshotChanged, "CHANGED_SINCE_INDEX"):
                source_index.verified_source_text(self.checkout, self.relative, "frontend")

    def test_lexing_reuses_verified_bytes_instead_of_second_file_read(self):
        original = source_index._read_bytes
        reads = []

        def read_then_change(path):
            content = original(path)
            reads.append(path)
            self.file.write_bytes(self.raw.replace(b"old", b"new"))
            return content

        with source_index.source_read_view(self.status), patch.object(source_index, "_read_bytes", side_effect=read_then_change):
            text = source_index.verified_source_text(self.checkout, self.relative, "frontend")
        self.assertIn("old", text)
        self.assertEqual(len(reads), 1)

    def test_public_guard_retries_once_and_returns_no_mixed_evidence(self):
        calls = []

        @source_analysis._source_layers("frontend")
        def query():
            calls.append(1)
            self.file.write_bytes(self.raw.replace(b"old", b"new"))
            text = source_index.verified_source_text(self.checkout, self.relative, "frontend")
            return {"status": "ok", "evidence": [text]}

        with patch.object(source_analysis, "ensure_source_index", return_value=self.status), patch.object(source_analysis, "source_index_generation", return_value="gen"):
            result = query()
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["errors"][0]["code"], "SOURCE_FILE_CHANGED_SINCE_INDEX")

    def test_refresh_publishes_ledger_with_layer_and_manifest_generation(self):
        resolution = {"selected": {"path": str(self.checkout), "fingerprint": "repo"}}
        with patch.object(source_index, "resolve_repository", return_value=resolution):
            result = source_index.refresh_source_index(force=True, layers=("frontend",))
        self.assertEqual(result["status"], "ok")
        manifest = json.loads((self.index / "manifest.json").read_text())
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual(ledger["generation"], manifest["generation"])
        self.assertEqual(ledger["generation"], manifest["repositories"]["frontend"]["fingerprint_generation"])
        self.assertEqual(ledger["files"][self.relative], hashlib.sha256(self.raw).hexdigest())
        self.ledger.unlink()
        with patch.object(source_index, "resolve_repository", return_value=resolution):
            self.assertTrue(source_index.source_index_status(("frontend",))["repositories"]["frontend"]["stale"])
            self.assertFalse(source_index.refresh_source_index(layers=("frontend",))["skipped"])

    def test_failed_ledger_write_keeps_previous_layer(self):
        before = self.ledger.read_bytes()
        resolution = {"selected": {"path": str(self.checkout), "fingerprint": "repo"}}
        original = source_index._write_json

        def fail_ledger(path, value):
            if path.name == "file-fingerprints.json":
                raise OSError("fixture")
            return original(path, value)

        with patch.object(source_index, "resolve_repository", return_value=resolution), patch.object(source_index, "_write_json", side_effect=fail_ledger):
            result = source_index.refresh_source_index(force=True, layers=("frontend",))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(self.ledger.read_bytes(), before)
