from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "mcp"), str(ROOT / "tests")]

from gxp_core import source_analysis, source_index
from gxp_core.canvas import condition_ast, evaluate_condition_ast
from gxp_core.source_config import repository_metadata
from gxp_core.policy_client import relation_id
from gxp_core.schema_config import SchemaSnapshotConfig
from gxp_core.schema_snapshot import SchemaSnapshotManager
from test_schema_snapshot import FakeDatabase, FakePolicy, FakeRepository, SCHEMA, bigint, make_table
from test_control_flow import predicate


def source_probes(root):
    frontend = root / "frontend"
    source = frontend / "src/core/common/service.ts"
    source.parent.mkdir(parents=True)
    source.write_text(
        "export function previous() { return 1; }\n"
        "// request.get('/api/commented');\n"
        "/* request.post('/api/block-commented'); */\n"
        "const explanation = '/api/not-a-request';\n"
        "export const actual = () => request.post('/api/actual');\n",
        encoding="utf-8",
    )
    data, failures = source_index._scan_frontend(frontend)
    print(json.dumps({"probe": "frontend_comments_and_scope", "requests": data["requests"], "failures": failures}))
    status = {
        "status": "error",
        "index": {"version": 1, "exists": True},
        "repositories": {},
        "errors": [{"layer": "frontend", "code": "REPOSITORY_AMBIGUOUS"}],
    }
    indexes = {
        "frontend/components.json": [{
            "component_type": "TestPaper", "behavior_names": [{"value": "TestPaper", "path": "old/designer/schema.tsx", "line": 7}], "selectors": [],
            "files": [{"path": "old/preview/web/index.tsx", "role": "runtime_web"}],
        }],
    }
    with patch.object(source_index, "source_index_status", return_value=status), patch.object(
        source_index, "refresh_source_index"
    ) as refresh, patch.object(
        source_analysis, "load_index_file", side_effect=lambda path, default: indexes.get(path, default)
    ):
        result = source_analysis.inspect_component_source("TestPaper")
    print(json.dumps({
        "probe": "stale_exact", "status": result["status"], "index": result["index"],
        "evidence": result["evidence"], "refresh_calls": refresh.call_count,
        "top_level_errors": result.get("errors"),
    }))
    symbols = [
        {"kind": "method", "name": "OrderServices.Save", "path": "Orders.cs", "line": 1},
        {"kind": "method", "name": "UnrelatedServices.Update", "path": "Other.cs", "line": 1},
    ]
    edges = [{"caller": "OrderServices.Save", "receiver": "ctx", "callee_member": "Update", "path": "Orders.cs", "line": 2}]
    indexes = {"backend/symbols.json": symbols, "graph/backend-call-edges.json": edges}
    fresh = {"index": {"version": 1, "exists": True}, "repositories": {"backend": {"stale": False}}}
    with patch.object(source_analysis, "ensure_source_index", return_value=fresh), patch.object(
        source_analysis, "load_index_file", side_effect=lambda path, default: indexes.get(path, default)
    ):
        result = source_analysis.trace_backend_call_chain("OrderServices.Save")
    print(json.dumps({"probe": "unrelated_unique_short_name", "call_tree": result["call_tree"], "evidence": result["evidence"]}))


def manager(root, name, policy, repository=None):
    config = SchemaSnapshotConfig(snapshot_dir=str(root / name), policy_scope_id="shared-dev")
    instance = SchemaSnapshotManager(config, database=FakeDatabase(), policy=policy)
    instance.repository = repository or FakeRepository()
    return instance


def schema_probes(root):
    class PartialRepository(FakeRepository):
        def load_schema(self, **kwargs):
            schema = json.loads(json.dumps(SCHEMA))
            schema["tables"].append(make_table("user", [bigint("id")], [
                {"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}
            ]))
            return schema

        def validate_relation(self, source_table, source_columns, target_table, target_columns, **kwargs):
            if target_table == "user":
                raise TimeoutError("query timeout")
            return super().validate_relation(source_table, source_columns, target_table, target_columns, **kwargs)

    with patch("gxp_core.schema_snapshot.schema_lock_path", return_value=root / "schema.lock"), patch(
        "gxp_core.schema_snapshot.schema_status_path", return_value=root / "schema-status.json"
    ):
        partial = manager(root, "partial", FakePolicy(), PartialRepository())
        partial.refresh(force=True)
        attempts = json.loads((partial.root / "validation-attempts.json").read_text(encoding="utf-8"))
        result = partial.resolve("orders", ["user_id"])
        print(json.dumps({
            "probe": "partial_target_validation", "attempts": [{"target": item["target_table"], "status": item["status"]} for item in attempts],
            "resolve_status": result["status"], "selected_target": result.get("relation", {}).get("target_table"),
        }))
        policy = FakePolicy()
        first = manager(root, "machine-first", policy)
        second = manager(root, "machine-second", policy)
        first.refresh(force=True)
        second.refresh(force=True)
        relation = relation_id("shared-dev", "orders", ["user_id"], "users", ["id"])
        first.reject(relation)
        before_restore = second.inspect("orders")["relations"]
        first.restore(relation)
        second.repository.evidence = {**second.repository.evidence, "passed": False, "reason": "unmatched_values", "unmatched_count": 1}
        calls = second.repository.validation_calls
        result = second.resolve("orders", ["user_id"], target_table="users", target_columns=["id"])
        print(json.dumps({
            "probe": "cross_machine_restore", "relations_while_rejected": len(before_restore),
            "resolve_after_restore": result["status"], "revalidation_calls": second.repository.validation_calls - calls,
            "current_data_would_pass": second.repository.evidence["passed"],
        }))


def compatibility_probes(root):
    evaluations = {}
    for operator in ("Equal", "=", "==", "!=", "<>"):
        ast = condition_ast({"Logic": "And", "Filters": [predicate("name", operator, "'A'")]})
        evaluations[operator] = evaluate_condition_ast(ast, {"name": "A"})["result"]
    print(json.dumps({"probe": "operator_compatibility", "evaluations": evaluations}))
    checkout = root / "dirty-checkout"
    checkout.mkdir()
    source = checkout / "service.ts"
    source.write_text("before", encoding="utf-8")

    def git_response(arguments, **kwargs):
        command = arguments[1:]
        if command == ["rev-parse", "--show-toplevel", "HEAD", "--abbrev-ref", "HEAD"]:
            text = str(checkout) + "\n" + "a" * 40 + "\nmain"
        elif command == ["rev-parse", "HEAD"]:
            text = "a" * 40
        elif command == ["branch", "--show-current"]:
            text = "main"
        elif command == ["remote", "get-url", "origin"]:
            text = "fixture-origin"
        else:
            text = " M service.ts\0"
        return SimpleNamespace(returncode=0, stdout=(text if "\0" in text else text + "\n").encode("utf-8"))

    with patch("gxp_core.source_config.subprocess.run", side_effect=git_response):
        before = repository_metadata(checkout)
        source.write_text("after-change-with-a-different-size", encoding="utf-8")
        after = repository_metadata(checkout)
    print(json.dumps({"probe": "dirty_fingerprint", "dirty_files": after["dirty_files"], "fingerprint_changed": before["fingerprint"] != after["fingerprint"]}))


def main():
    with tempfile.TemporaryDirectory(prefix="look-optimization-review-") as directory:
        root = Path(directory)
        source_probes(root)
        schema_probes(root)
        compatibility_probes(root)


if __name__ == "__main__":
    main()
