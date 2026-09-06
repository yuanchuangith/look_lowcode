from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


def measure(root: str) -> dict:
    sys.path.insert(0, str(Path(root).resolve() / "mcp"))
    from gxp_core.canvas import CanvasInspector
    from gxp_core.service import GxpReadonlyService

    class FixtureRepository:
        reads = 0
        current = None

        def resolve_action(self, identifier):
            return [{"ref_id": "fixture", "action_code": "FIXTURE1"}]

        def load_design(self, ref_id, **kwargs):
            self.reads += 1
            return self.current

    repository = FixtureRepository()
    service = object.__new__(GxpReadonlyService)
    service.repository = repository
    service.inspector = CanvasInspector()
    results = []
    for name, count, expression, arguments in (
        ("compact_20_nodes", 20, 'row["file_ver_id"]', {}),
        ("field_reference", 1, 'row["file_ver_id"]', {"focus_fields": ["file_ver_id"]}),
        ("large_single_node", 1, '"' + "中文" * 24000 + '"', {"include_params": True}),
    ):
        nodes = [{"key": f"node{index}", "title": "Define", "elementKey": "SetVariable", "paramsValue": {"inputParams": {"variableType": "string", "variableValue": {"code": expression}}, "outputParams": {"variableName": {"code": f"value{index}"}}}} for index in range(count)]
        repository.current = {"design_id": "fixture-v1", "version": "published", "is_deleted": 0, "metadata": repository.resolve_action("fixture")[0], "csharp_code": "", "data_json": {"actionData": [{"key": "main", "title": "main", "data": nodes}]}}
        for _ in range(2):
            service.inspect_action("fixture", group="main", **arguments)
        rounds = []
        before = repository.reads
        for _ in range(5):
            started = time.perf_counter()
            for _ in range(10):
                payload = service.inspect_action("fixture", group="main", **arguments)
                encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            rounds.append((time.perf_counter() - started) * 100)
        results.append({"fixture": name, "milliseconds_per_call_median": round(statistics.median(rounds), 3), "round_milliseconds_per_call": [round(value, 3) for value in rounds], "response_bytes": len(encoded), "field_match_count": payload.get("field_match_count"), "design_reads": repository.reads - before, "calls": 50, "response_truncated": payload.get("response_truncated", False)})
    return {"fixtures": results, "business_database_access": False, "source_scan_access": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired synthetic canvas benchmarks without database or source scans")
    parser.add_argument("--baseline")
    parser.add_argument("--output")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(args.worker)))
        return
    if not args.baseline or not args.output:
        parser.error("--baseline and --output are required")
    result = {"measurement": "fixed_synthetic_fixtures_five_rounds_not_live_latency", "runs": {}}
    for label, root in (("baseline", args.baseline), ("candidate", str(Path(__file__).resolve().parents[1]))):
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", root], capture_output=True, text=True, encoding="utf-8", timeout=120, check=True)
        result["runs"][label] = json.loads(completed.stdout)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
