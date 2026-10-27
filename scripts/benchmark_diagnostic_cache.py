"""Paired offline first-page/continuation benchmark with exact evidence checks."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def worker(args):
    repository = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(Path(args.implementation_root) / "mcp"), str(repository / "tests")]
    from diagnostic_fixture import FixtureDatabase, STACK
    from gxp_core.service import GxpReadonlyService
    try:
        from gxp_core.diagnostic_cache import DIAGNOSTIC_CACHE
    except ImportError:
        DIAGNOSTIC_CACHE = None
    results = {}
    for operation in ("filter", "exception"):
        if DIAGNOSTIC_CACHE:
            DIAGNOSTIC_CACHE.clear()
        database = FixtureDatabase(count=600, history=8)
        def run(cursor=None):
            service = GxpReadonlyService(database)
            if operation == "filter":
                return service.inspect_component_filters("ACTION01", "picker", limit=1, cursor=cursor)
            return service.trace_dynamic_exception(STACK, limit=1, cursor=cursor)
        started = time.perf_counter()
        first = run()
        cold = time.perf_counter() - started
        cold_reads = database.body_reads
        started = time.perf_counter()
        second = run(first["next_cursor"])
        hot = time.perf_counter() - started
        semantic = [{key: value for key, value in page.items() if key not in {"evidence_gaps", "fallback"}}
                    for page in (first, second)]
        results[operation] = {"cold_seconds": cold, "hot_seconds": hot,
                              "cold_body_reads": cold_reads, "hot_body_reads": database.body_reads - cold_reads,
                              "semantic_sha256": digest(semantic)}
    print(json.dumps(results))


def main(args):
    repository = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="look-diagnostic-paired-") as temporary:
        baseline = Path(temporary) / "baseline"
        archive = subprocess.run(["git", "archive", "--format=zip", args.baseline_ref, "mcp"], cwd=repository,
                                 check=True, capture_output=True).stdout
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            package.extractall(baseline)
        rounds = []
        for index in range(args.rounds):
            order = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
            pair = {"round": index + 1, "order": order}
            for name in order:
                command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--implementation-root",
                           str(baseline if name == "baseline" else repository)]
                output = subprocess.run(command, cwd=repository, check=True, capture_output=True, text=True, timeout=60)
                pair[name] = json.loads(output.stdout)
            pair["equivalent"] = all(pair["baseline"][tool]["semantic_sha256"] == pair["candidate"][tool]["semantic_sha256"] for tool in ("filter", "exception"))
            if not pair["equivalent"]:
                raise RuntimeError("Diagnostic evidence or cursor changed: " + json.dumps(pair))
            rounds.append(pair)
            print(f"paired round {index + 1}/{args.rounds}: equivalent", flush=True)
        medians = {name: {tool: {metric: statistics.median(pair[name][tool][metric] for pair in rounds)
                               for metric in ("cold_seconds", "hot_seconds")}
                          for tool in ("filter", "exception")} for name in ("baseline", "candidate")}
        ratios = {tool: {metric: medians["candidate"][tool][metric] / medians["baseline"][tool][metric]
                         for metric in ("cold_seconds", "hot_seconds")} for tool in ("filter", "exception")}
        accepted = all(ratios[tool]["cold_seconds"] <= 1.05 and ratios[tool]["hot_seconds"] < 1 for tool in ratios)
        record = {"kind": "synthetic_local_only", "baseline_ref": args.baseline_ref, "round_count": args.rounds,
                  "python": sys.version, "platform": platform.platform(),
                  "scope": "Query-only in-memory DB fixture: 600 canvas writers, 8 published history rows plus draft. Fresh service/repository per call; no credentials, business DB, configured source repositories or network.",
                  "comparison": "Exact canonical first/continuation JSON including evidence and v2 cursors; only additive transport evidence_gaps/fallback removed. Startup and fixture creation excluded.",
                  "limits": "No real SQL latency/permissions, connection setup or model end-to-end measurement. Serialized cache bytes are not a Python heap hard cap.",
                  "medians_seconds": medians, "candidate_over_baseline": ratios, "acceptance_passed": accepted, "rounds": rounds}
        Path(args.output).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"acceptance_passed": accepted, "candidate_over_baseline": ratios}))
        if not accepted:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--implementation-root")
    parser.add_argument("--baseline-ref", default="4986e2c3b71e74911aa6671a0061863e3c3b15d3")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--output", default="docs/diagnostic-cache-benchmark-20261027.json")
    arguments = parser.parse_args()
    if arguments.rounds < 5:
        parser.error("Use at least five paired rounds")
    worker(arguments) if arguments.worker else main(arguments)
