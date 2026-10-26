"""Paired synthetic work benchmark; never reads configured repositories or business data."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from unittest.mock import patch


def measured(function):
    started = time.perf_counter()
    value = function()
    return value, time.perf_counter() - started


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def worker(args):
    sys.path.insert(0, str(Path(args.implementation_root) / "mcp"))
    from gxp_core.business_graph_store import BusinessGraphStore
    from gxp_core import source_analysis
    store = BusinessGraphStore(Path(args.database), scope_id="test")
    statements = []
    with store._transaction() as connection:
        connection.set_trace_callback(statements.append)
        snapshot, snapshot_seconds = measured(lambda: store._snapshot(connection, "test", "development", True))
    search, search_seconds = measured(lambda: store.search(limit=20))
    search.pop("matched_count_complete", None)  # Intentional additive completeness metadata.
    symbols = [{"kind": "method", "symbol_id": "Bench.Root.Run()", "name": "Root.Run", "path": "Synthetic.cs", "line": 1}]
    symbols.extend({"kind": "method", "symbol_id": f"Bench.Worker.Run{index}()", "name": f"Worker.Run{index}", "path": "Synthetic.cs", "line": index + 2} for index in range(25000))
    def edge(caller, target, index):
        return {"caller_id": caller, "target_ids": [target], "callee_member": "Run", "path": "Synthetic.cs", "line": index + 1}
    edges = [edge("Bench.Root.Run()", f"Bench.Worker.Run{index}()", index) for index in range(100)]
    edges.extend(edge(f"Bench.Worker.Run{index}()", "Bench.Root.Run()", index) for index in range(35000))
    files = {"backend/symbols.json": symbols, "graph/backend-call-edges.json": edges}
    with patch.object(source_analysis, "ensure_source_index", return_value={}), patch.object(source_analysis, "load_index_file", side_effect=lambda name, default: files.get(name, default)):
        backend, backend_seconds = measured(lambda: source_analysis.trace_backend_call_chain.__wrapped__("Bench.Root.Run()"))
    print(json.dumps({"seconds": {"graph_snapshot": snapshot_seconds, "graph_search": search_seconds, "backend_trace": backend_seconds},
        "semantic_sha256": {"graph_snapshot": fingerprint(snapshot), "graph_search": fingerprint(search), "backend_trace": fingerprint(backend)},
        "snapshot_select_count": sum(statement.lstrip().upper().startswith(("SELECT", "WITH")) for statement in statements),
        "counts": {"nodes": len(snapshot["nodes"]), "edges": len(snapshot["edges"]), "search_matches": search["matched_count"], "backend_calls": len(backend["call_tree"])}}))


def main(args):
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "mcp"))
    sys.path.insert(0, str(repository / "tests"))
    from gxp_core.business_graph_store import BusinessGraphStore
    from gxp_core.business_graph_model import normalize_v3
    from test_business_graph import observation
    with tempfile.TemporaryDirectory(prefix="look-synthetic-query-") as temporary:
        root = Path(temporary)
        baseline = root / "baseline"
        archive = subprocess.run(["git", "archive", "--format=zip", args.baseline_ref, "mcp"], cwd=repository, check=True, capture_output=True).stdout
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            package.extractall(baseline)
        database = root / "synthetic.sqlite3"
        store = BusinessGraphStore(database, scope_id="test")
        with store._transaction(write=True) as connection:
            for index in range(1000):
                raw = observation(f"synthetic-{index}", f"N{index}", f"N{index + 1}")
                if index % 5 == 0:
                    raw["entities"][0]["boundary"] = "source"
                store._put(connection, normalize_v3(raw, "test"), "active" if index % 4 == 0 else "stale")
            store._bump(connection)
        rounds = []
        for index in range(args.rounds):
            order = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
            result = {"round": index + 1, "order": list(order)}
            for name in order:
                command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--implementation-root", str(baseline if name == "baseline" else repository), "--database", str(database)]
                output = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
                result[name] = json.loads(output.stdout)
            result["equivalent"] = result["baseline"]["semantic_sha256"] == result["candidate"]["semantic_sha256"]
            if not result["equivalent"]:
                raise RuntimeError("Semantic output changed: " + json.dumps(result, ensure_ascii=False))
            rounds.append(result)
            print(f"paired round {index + 1}/{args.rounds}: equivalent", flush=True)
        medians = {name: {metric: statistics.median(result[name]["seconds"][metric] for result in rounds)
                         for metric in rounds[0][name]["seconds"]} for name in ("baseline", "candidate")}
        record = {"kind": "synthetic_local_only", "baseline_ref": args.baseline_ref, "round_count": args.rounds,
                  "scope": "same synthetic SQLite snapshot; in-memory backend index; no configured source roots, business DB or MCP",
                  "comparison": "Exact canonical JSON hashes; only new matched_count_complete metadata removed for search",
                  "worker_startup_included": False, "medians_seconds": medians,
                  "speedup": {metric: medians["baseline"][metric] / medians["candidate"][metric] for metric in medians["baseline"]}, "rounds": rounds}
        Path(args.output).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"medians_seconds": medians, "speedup": record["speedup"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--implementation-root")
    parser.add_argument("--database")
    parser.add_argument("--baseline-ref", default="15f7e89")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--output", default="docs/query-work-benchmark-20261026.json")
    args = parser.parse_args()
    if args.rounds < 5:
        parser.error("Use at least 5 paired rounds")
    worker(args) if args.worker else main(args)
