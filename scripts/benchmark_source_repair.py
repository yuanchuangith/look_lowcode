from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.implementation_root) / "mcp"))
    from gxp_core import source_index
    from gxp_core.source_analysis import inspect_component_source, trace_api_contract, trace_backend_call_chain, trace_component_filter_contract
    from gxp_core.source_config import resolve_repository
    repositories = {layer: resolve_repository(layer) for layer in ("frontend", "backend")}
    timings = {"build": [], "query": []}
    results = {}
    with tempfile.TemporaryDirectory(prefix="look-source-benchmark-") as temporary:
        root = Path(temporary)
        with patch.object(source_index, "source_index_root", return_value=root / "index"), patch.object(source_index, "source_index_lock_path", return_value=root / "index.lock"):
            for iteration in range(5):
                started = time.perf_counter()
                result = source_index.refresh_source_index(force=True)
                timings["build"].append(time.perf_counter() - started)
                if result.get("status") != "ok":
                    raise RuntimeError(json.dumps(result, ensure_ascii=False))
                print(f"build {iteration + 1}: {timings['build'][-1]:.3f}s", flush=True)
            for iteration in range(5):
                started = time.perf_counter()
                results = {
                    "component": inspect_component_source("TestPaper"),
                    "save": trace_api_contract("/api/datasets/save"),
                    "search": trace_api_contract("/api/datasets/search"),
                    "backend": trace_backend_call_chain("DataSetServices.BatchSaveData"),
                    "filter": trace_component_filter_contract("TestPaper"),
                }
                timings["query"].append(time.perf_counter() - started)
                print(f"query {iteration + 1}: {timings['query'][-1]:.3f}s", flush=True)
            requests = source_index.load_index_file("frontend/requests.json", [])
            frontend = Path(repositories["frontend"]["selected"]["path"])
            file_lines = {}
            comments = []
            for request in requests:
                relative = request["path"]
                if relative not in file_lines:
                    file_lines[relative] = (frontend / relative).read_text(encoding="utf-8", errors="replace").splitlines()
                if file_lines[relative][request["line"] - 1].strip().startswith("//"):
                    comments.append(request)
            output = {
                "repositories": {layer: value["selected"] for layer, value in repositories.items()},
                "timings": timings,
                "medians": {key: statistics.median(values) for key, values in timings.items()},
                "requests": len(requests), "line_comment_requests": comments,
                "payload_bytes": {key: len(json.dumps(value, ensure_ascii=False).encode("utf-8")) for key, value in results.items()},
                "results": results,
            }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"medians": output["medians"], "requests": output["requests"], "comments": len(comments), "payload_bytes": output["payload_bytes"]}))


if __name__ == "__main__":
    main()

