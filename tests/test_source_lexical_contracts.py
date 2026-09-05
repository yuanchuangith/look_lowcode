from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gxp_core.source_index import _scan_backend, _scan_frontend
from gxp_core.source_lex import LexedSource
from gxp_core.source_frontend import scan_requests


class SourceLexicalContracts(unittest.TestCase):
    def test_multiline_alias_functions_and_comments(self):
        text = """
export async function first() {
  const url = prefix + '/api/first';
  return request.post(
    url, { data: {} }
  );
}
export const second = async () => {
  const url = '/api/second';
  return request.get(url);
};
const third = function() { return request.put('/api/third'); };
// request.delete('/api/comment');
const prose = "request.get('/api/string')";
/* block
request.get('/api/block');
*/
"""
        source = LexedSource(text)
        data = scan_requests(source, "service.ts")
        self.assertEqual([("/api/first", "first"), ("/api/second", "second"), ("/api/third", "third")], [(item["route"], item["function"]) for item in data["requests"]])
        self.assertFalse(source.errors)

    def test_reassigned_url_and_unknown_suffix_do_not_close_contract(self):
        source = LexedSource("function sample() { let url='/api/first'; url='/api/second'; request.get(url); request.get('/api/dynamic/' + key); }")
        self.assertEqual([], scan_requests(source, "service.ts")["requests"])

    def test_template_nested_strings_regex_and_unclosed_input(self):
        tick = chr(96)
        text = "const load = () => request.get(" + tick + "/api/items/$" + "{choose('a', {key: 1})}" + tick + "); const regex = /request.get('no')/;"
        source = LexedSource(text)
        data = scan_requests(source, "service.ts")
        self.assertEqual(1, len(data["requests"]))
        self.assertTrue(data["requests"][0]["dynamic"])
        self.assertFalse(source.errors)
        self.assertTrue(LexedSource("/* missing end").errors)
        self.assertTrue(LexedSource("const value = 'missing").errors)

    def test_commented_component_registration_is_not_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "src/core/components/form/Test/designer/schema.ts"
            source.parent.mkdir(parents=True)
            source.write_text("// createBehavior({name: 'Other'});\ncreateBehavior({name: 'Test'});\n/* setFilter(props.dynamicFilter); */", encoding="utf-8")
            data, failures = _scan_frontend(root)
        self.assertFalse(failures)
        self.assertEqual(["Test"], [item["value"] for item in data["components"][0]["behavior_names"]])
        self.assertEqual([], data["component_contracts"][0]["anchors"])

    def test_backend_receivers_factories_namespaces_and_overloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "GxP2.Services/Services.cs"
            source.parent.mkdir(parents=True)
            source.write_text("""
namespace App {
public interface IWorker { bool Run(string value); }
public class Worker : IWorker {
 public bool Run(string value) { return true; }
 public bool Run(int value) { return false; }
}
public class Base {
 protected ZeroDbContext GetZeroDbContext(string table, out object descriptor) { descriptor=null; return null; }
}
public class Orders : Base {
 private readonly IWorker worker;
 public Orders(IWorker worker) { this.worker = worker; }
 public bool Save(string name) {
  using var session = GetZeroDbContext(name, out var descriptor);
  session.Insert(name);
  session.Update(name);
  return worker.Run(name);
 }
}
}
namespace Other {
 public class Worker { public bool Run(string value) { return true; } }
}
""", encoding="utf-8")
            data, failures = _scan_backend(root)
        self.assertFalse(failures)
        edges = [item for item in data["call_edges"] if item["caller"] == "Orders.Save"]
        self.assertEqual(["insert", "update"], [item["data_access"] for item in edges[:2]])
        self.assertEqual(["App.Worker.Run(string)"], edges[2]["target_ids"])

    def test_backend_unrelated_receiver_does_not_use_unique_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "GxP2.Services/Services.cs"
            source.parent.mkdir(parents=True)
            source.write_text("namespace App { public class Orders { public void Save(object ctx) { ctx.Update(); } } public class Other { public void Update() {} } }", encoding="utf-8")
            data, failures = _scan_backend(root)
        self.assertFalse(failures)
        self.assertEqual([], data["call_edges"][0]["target_ids"])
        self.assertIsNone(data["call_edges"][0]["data_access"])

    def test_inner_block_url_does_not_leak_to_outer_scope(self):
        source = LexedSource("function sample() { if (flag) { const url='/api/inner'; } request.get(url); }")
        self.assertEqual([], scan_requests(source, "service.ts")["requests"])

    def test_reassigned_receiver_does_not_retain_factory_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "GxP2.Services/Services.cs"
            source.parent.mkdir(parents=True)
            source.write_text("namespace App { public class Orders { protected ZeroDbContext Factory() { return null; } public void Save(object other) { var session=Factory(); session=other; session.Update(); } } }", encoding="utf-8")
            data, failures = _scan_backend(root)
        self.assertFalse(failures)
        edge = next(item for item in data["call_edges"] if item["callee_member"] == "Update")
        self.assertIsNone(edge["data_access"])
        self.assertEqual([], edge["target_ids"])


if __name__ == "__main__":
    unittest.main()
