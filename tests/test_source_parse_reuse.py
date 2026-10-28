from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from gxp_core import source_index
from gxp_core.source_parse_cache import SOURCE_PARSE_CACHE, SourceParseCache


class SourceParseReuseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        SOURCE_PARSE_CACHE.clear()
        self.addCleanup(SOURCE_PARSE_CACHE.clear)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def semantics(self, data):
        return {key: value for key, value in data.items() if key != "parse_stats"}

    def test_frontend_reuses_unchanged_file_but_reads_new_bytes_and_matches_full_scan(self):
        first = self.write("src/core/common/api.ts", "export function first() { return request.get('/api/old'); }")
        self.write("src/core/common/service.ts", "export function second() { return request.get('/api/other'); }")
        initial, _ = source_index._scan_frontend(self.root)
        stamp = first.stat()
        first.write_bytes(first.read_bytes().replace(b"/api/old", b"/api/new"))
        os.utime(first, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with patch.object(source_index, "_parse_frontend_file", wraps=source_index._parse_frontend_file) as parse:
            incremental, failures = source_index._scan_frontend(self.root)
        self.assertEqual(failures, [])
        self.assertEqual(parse.call_count, 1)
        self.assertEqual(incremental["parse_stats"], {"parsed_files": 1, "reused_files": 1})
        self.assertNotEqual(initial["file_fingerprints"]["src/core/common/api.ts"], incremental["file_fingerprints"]["src/core/common/api.ts"])
        self.assertEqual(incremental["file_fingerprints"]["src/core/common/api.ts"], hashlib.sha256(first.read_bytes()).hexdigest())
        full, _ = source_index._scan_frontend(self.root, reuse_parse=False)
        self.assertEqual(self.semantics(incremental), self.semantics(full))

    def test_backend_rebinds_all_files_after_deletion_and_rename(self):
        self.write("GxP2.IServices/ITest.cs", "public interface ITest { bool Run(); }")
        implementation = self.write("GxP2.Services/Test.cs", "public class Test : ITest { public bool Run() { return true; } }")
        self.write("GxP2.Web/Controllers/TestController.cs", "public class TestController { private ITest service; public bool Get() { return service.Run(); } }")
        first, _ = source_index._scan_backend(self.root)
        self.assertTrue(first["service_bindings"])
        implementation.unlink()
        with patch.object(source_index, "parse_backend_file", wraps=source_index.parse_backend_file) as parse, patch.object(source_index, "bind_backend", wraps=source_index.bind_backend) as bind:
            changed, failures = source_index._scan_backend(self.root)
        self.assertEqual(failures, [])
        self.assertEqual(parse.call_count, 0)
        self.assertEqual(bind.call_count, 1)
        self.assertEqual(changed["service_bindings"], [])
        self.assertFalse(any("Test.Run()" in edge["target_ids"] for edge in changed["call_edges"]))
        full, _ = source_index._scan_backend(self.root, reuse_parse=False)
        self.assertEqual(self.semantics(changed), self.semantics(full))
        original = self.root / "GxP2.IServices/ITest.cs"
        original.rename(original.with_name("Renamed.cs"))
        with patch.object(source_index, "parse_backend_file", wraps=source_index.parse_backend_file) as parse:
            renamed, _ = source_index._scan_backend(self.root)
        self.assertEqual(parse.call_count, 1)
        self.assertNotIn("GxP2.IServices/ITest.cs", renamed["file_fingerprints"])
        self.assertTrue(any(symbol["path"].endswith("Renamed.cs") for symbol in renamed["symbols"]))
        full, _ = source_index._scan_backend(self.root, reuse_parse=False)
        self.assertEqual(self.semantics(renamed), self.semantics(full))

    def test_configuration_and_parser_version_invalidate_per_file_results(self):
        self.write("src/core/common/api.ts", "export function first() { return request.get('/api/old'); }")
        config = self.write("tsconfig.json", '{"strict":true}')
        source_index._scan_frontend(self.root)
        config.write_text('{"strict":false}', encoding="utf-8")
        with patch.object(source_index, "_parse_frontend_file", wraps=source_index._parse_frontend_file) as parse:
            source_index._scan_frontend(self.root)
        self.assertEqual(parse.call_count, 1)
        with patch.object(source_index, "SOURCE_PARSE_VERSION", source_index.SOURCE_PARSE_VERSION + 1), patch.object(source_index, "_parse_frontend_file", wraps=source_index._parse_frontend_file) as parse:
            source_index._scan_frontend(self.root)
        self.assertEqual(parse.call_count, 1)

    def test_cached_success_does_not_hide_unreadable_current_file_or_parse_error(self):
        file = self.write("src/core/common/api.ts", "export function first() { return request.get('/api/old'); }")
        source_index._scan_frontend(self.root)
        read = source_index._read_bytes

        def denied(path):
            if path == file:
                raise PermissionError("fixture denied")
            return read(path)

        with patch.object(source_index, "_read_bytes", side_effect=denied):
            data, failures = source_index._scan_frontend(self.root)
        self.assertEqual(data["requests"], [])
        self.assertEqual(data["file_fingerprints"], {})
        self.assertEqual(len(failures), 1)
        file.write_text("request.get('unclosed", encoding="utf-8")
        with patch.object(source_index, "_parse_frontend_file", wraps=source_index._parse_frontend_file) as parse:
            source_index._scan_frontend(self.root)
            _, failures = source_index._scan_frontend(self.root)
        self.assertEqual(parse.call_count, 2)
        self.assertTrue(failures)

    def test_refresh_publishes_new_ledger_and_keeps_force_as_full_parse(self):
        self.write("src/core/common/api.ts", "export function first() { return request.get('/api/old'); }")
        index = self.root / "index"
        identity = {"path": str(self.root), "fingerprint": "one"}
        with patch.object(source_index, "source_index_root", return_value=index), patch.object(source_index, "source_index_lock_path", return_value=self.root / "index.lock"), patch.object(source_index, "resolve_repository", side_effect=lambda layer: {"selected": deepcopy(identity)}):
            source_index.refresh_source_index(layers=("frontend",))
            first = json.loads((index / "frontend/file-fingerprints.json").read_text())
            identity["fingerprint"] = "two"
            result = source_index.refresh_source_index(layers=("frontend",))
            ledger = json.loads((index / "frontend/file-fingerprints.json").read_text())
            manifest = json.loads((index / "manifest.json").read_text())
            self.assertEqual(result["repositories"]["frontend"]["reused_files"], 1)
            self.assertNotEqual(first["generation"], ledger["generation"])
            self.assertEqual(ledger["generation"], manifest["repositories"]["frontend"]["fingerprint_generation"])
            self.assertEqual(ledger["files"], first["files"])
            forced = source_index.refresh_source_index(force=True, layers=("frontend",))
            self.assertEqual(forced["repositories"]["frontend"]["reused_files"], 0)
            self.assertEqual(forced["repositories"]["frontend"]["parsed_files"], 1)

    def test_cache_is_bounded_and_never_shares_mutable_parse_results(self):
        cache = SourceParseCache(max_entries=1)
        value = {"routes": [{"dto_symbol_ids": []}]}
        cache.put(("first",), value)
        value["routes"][0]["dto_symbol_ids"].append("outside")
        one = cache.get(("first",))
        one["routes"][0]["dto_symbol_ids"].append("consumer")
        self.assertEqual(cache.get(("first",))["routes"][0]["dto_symbol_ids"], [])
        cache.put(("second",), {})
        self.assertIsNone(cache.get(("first",)))
        self.assertIsNotNone(cache.get(("second",)))
        tiny = SourceParseCache(max_bytes=1)
        tiny.put(("large",), value)
        self.assertIsNone(tiny.get(("large",)))

    def test_backend_lexical_containers_are_isolated_without_copying_immutable_tokens(self):
        parsed, lexed = source_index.parse_backend_file("public class Test { public bool Run() { return true; } }", "Test.cs")
        cache = SourceParseCache()
        cache.put(("backend",), (parsed, lexed))
        first_data, first_lexed = cache.get(("backend",))
        first_data["types"][0]["fields"]["changed"] = "string"
        first_lexed.errors.append("changed")
        first_lexed.tokens.clear()
        first_lexed.pairs.clear()
        next_data, next_lexed = cache.get(("backend",))
        self.assertNotIn("changed", next_data["types"][0]["fields"])
        self.assertEqual(next_lexed.errors, [])
        self.assertTrue(next_lexed.tokens)
        self.assertTrue(next_lexed.pairs)
        self.assertIs(next_lexed.tokens[0], lexed.tokens[0])

    def test_unreadable_configuration_disables_reuse(self):
        self.write("src/core/common/api.ts", "export function first() { return request.get('/api/old'); }")
        config = self.write("tsconfig.json", '{}')
        source_index._scan_frontend(self.root)
        read = source_index._read_bytes

        def denied(path):
            if path == config:
                raise PermissionError("fixture denied")
            return read(path)

        with patch.object(source_index, "_read_bytes", side_effect=denied), patch.object(source_index, "_parse_frontend_file", wraps=source_index._parse_frontend_file) as parse:
            data, failures = source_index._scan_frontend(self.root)
        self.assertEqual(parse.call_count, 1)
        self.assertEqual(failures, [])
        self.assertEqual(data["parse_stats"]["reused_files"], 0)


if __name__ == "__main__":
    unittest.main()
