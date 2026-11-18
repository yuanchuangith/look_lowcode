"""Replay a fixed evidence set offline, optionally including a native JS candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


LOOK_ROOT = Path(__file__).resolve().parents[1]
IDENTITY = {"ref_id": "benchmark-ref", "action_code": "BenchmarkAction", "action_name": "Offline action"}
CONFIG = {"host": "fixture.invalid", "port": 3306, "database": "offline_fixture"}
FIELDS = ("inputParams/variableType", "inputParams/variableValue/code",
          "inputParams/variableValue/label", "outputParams/variableName/code")

VERIFY_WRITE = """
import hashlib, json, sys, time
from pathlib import Path
from unittest.mock import patch
from gxp_editor.handoff_import import inspect_handoff
from gxp_editor.handoff_store import HandoffStore

data = json.load(sys.stdin)
store = HandoffStore(Path(data["root"]))
with patch("gxp_editor.handoff_import.HandoffStore", return_value=store):
    result = inspect_handoff(data["ref"], data["draft"], data["environment"])
record = store.read(**data["ref"])
def field_value(target, field):
    value = target["paramsValue"]
    for name in field.split("/"):
        value = value[name]
    return value
values = [[target["group_key"], target["node_key"], field, field_value(target, field)]
          for target in record["targets"] for field in data["fields"]]
encoded = json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
report = {"status": result["status"], "coverage_sha256": hashlib.sha256(encoded).hexdigest(),
          "target_count": len(result["targets"]), "authorization_inherited": result["authorization_inherited"],
          "approval_inherited": result["approval_inherited"],
          "response_bytes": len(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))}
if data.get("native_bridge"):
    if result["status"] != "matched" or report["coverage_sha256"] != data["expected_coverage_sha256"]:
        raise ValueError("Native candidate requires complete matched handoff coverage")
    from gxp_editor.compiler import CompilerBridge
    from gxp_editor.config import DatabaseConfig, EditorConfig, RuntimeReferenceConfig
    bridge_path = Path(data["native_bridge"])
    config = EditorConfig(database=DatabaseConfig(**data["environment"], user="offline"),
                          frontend_repo=str(bridge_path.parents[2]), compiler_bridge=str(bridge_path),
                          runtime_references=RuntimeReferenceConfig(directory=data["root"]), backend_repo=data["root"])
    compiler = CompilerBridge(config)
    first = record["targets"][0]
    old = field_value(first, "inputParams/variableValue")
    new = {**old, "value": "404", "code": "404", "label": "404"}
    anchor = {"action_group_key": first["group_key"], "target_node_key": first["node_key"]}
    operations = [{"operation": "set_parameter", **anchor, "expected_element_key": "SetVariable",
                   "path": "/inputParams/variableValue", "expected_old_value": old, "value": new},
                  {"operation": "insert_before", "action_group_key": first["group_key"],
                   "anchor_node_key": first["node_key"], "element_key": "CustomExt",
                   "input_params": {"content": "Default for the offline benchmark; preserve the other variables."}}]
    started = time.perf_counter()
    candidate = compiler.compile_patch(json.loads(data["draft"]["data"]), operations)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    nodes = candidate["design"]["actionData"][0]["data"]
    assert candidate["validation"]["valid"] and candidate["js_code"]
    assert nodes[0]["elementKey"] == "CustomExt" and nodes[1]["key"] == first["node_key"]
    assert nodes[1]["paramsValue"]["inputParams"]["variableValue"] == new
    report["native_candidate"] = {"elapsed_ms": elapsed_ms, "validated": True, "operation_count": len(operations),
                                  "generated_js_bytes": len(candidate["js_code"].encode("utf-8"))}
print(json.dumps(report))
"""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def fixture():
    def param(code):
        return {"paramTypes": "custom", "value": code, "code": code, "label": code, "dataType": "number"}

    groups, targets, evidence = [], [], []
    for group_index in range(4):
        group_key = f"group{group_index}"
        nodes = []
        for node_index in range(2):
            node_key = f"target-{group_index}-{node_index}"
            value, name = str(group_index * 2 + node_index), f"setting{group_index}_{node_index}"
            values = {"inputParams": {"variableType": "number", "variableValue": param(value)},
                      "outputParams": {"variableName": param(name)}}
            nodes.append({"key": node_key, "title": name, "elementKey": "SetVariable", "depth": [], "paramsValue": values})
            paths = [f"/paramsValue/{field}" for field in FIELDS]
            targets.append({"group_key": group_key, "node_key": node_key, "value_paths": paths})
            evidence.extend([group_key, node_key, field, expected] for field, expected in zip(FIELDS, ("number", value, value, name), strict=True))
        groups.append({"key": group_key, "title": f"Phase {group_index}", "actionType": "js", "data": nodes})
    return {"actionData": groups, "globalVariables": [], "code": IDENTITY["action_code"]}, targets, evidence


class FixtureRepository:
    def __init__(self, data):
        self.data = data
        self.raw = json.dumps(data, ensure_ascii=False, indent=2)
        self.loads = 0

    def resolve_action(self, identifier):
        return [IDENTITY] if identifier in (IDENTITY["action_code"], IDENTITY["ref_id"]) else []

    def load_design(self, ref_id, *, version, **_):
        assert ref_id == IDENTITY["ref_id"]
        self.loads += 1
        return {"design_id": version + "-fixture", "version": version, "is_deleted": False,
                "metadata": IDENTITY, "data": self.raw, "data_json": self.data,
                "data_sha256": hashlib.sha256(self.raw.encode("utf-8")).hexdigest(), "csharp_sha256": "0" * 64}


def _extract(page):
    if not page["complete"]:
        raise AssertionError("Fixture field did not fit the selected read")
    return page["text"] if page["encoding"] == "text" else json.loads(page["text"])


def run(write_root: Path, native_bridge: Path | None = None) -> dict:
    sys.path.insert(0, str(LOOK_ROOT / "mcp"))
    from gxp_core.canvas import CanvasInspector
    from gxp_core.canvas_budget import payload_size
    from gxp_core.handoff_store import HandoffStore
    from gxp_core.service import GxpReadonlyService

    data, targets, expected = fixture()
    service = object.__new__(GxpReadonlyService)
    repo = FixtureRepository(data)
    service.repository, service.inspector = repo, CanvasInspector()
    service.database = SimpleNamespace(config=CONFIG)
    identifier = IDENTITY["action_code"]

    legacy_counts = {}
    for version in ("published", "draft"):
        lengths, values = [], []
        started = time.perf_counter()
        for target in targets:
            for field, path in zip(FIELDS, target["value_paths"], strict=True):
                result = service.inspect_action(identifier, version=version, group=target["group_key"],
                                                node_key=target["node_key"], value_path=path)
                lengths.append(payload_size(result))
                values.append([target["group_key"], target["node_key"], field, _extract(result["value_page"])])
        if values != expected:
            raise AssertionError(f"Legacy {version} evidence did not match the frozen fixture")
        legacy_counts[version] = {"calls": len(lengths), "response_bytes": sum(lengths),
                                  "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}

    legacy_loads = repo.loads
    batched_started = started = time.perf_counter()
    batch = service.inspect_action(identifier, version="published", targets=targets)
    batched_counts = {"calls": 1, "response_bytes": payload_size(batch), "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
    batch_loads = repo.loads - legacy_loads
    if batch_loads != 1:
        raise AssertionError(f"Batch loaded the design {batch_loads} times")
    if not batch["evidence_complete"]:
        raise AssertionError("Batch did not return every fixture target and field")
    seen = [
        [target["group_key"], target["node_key"], field, _extract(value)]
        for target in batch["targets"] for field, value in zip(FIELDS, target["values"], strict=True)
    ]
    if seen != expected:
        raise AssertionError("Batch result changed fixture evidence")

    with tempfile.TemporaryDirectory(prefix="gxp-evidence-replay-") as directory:
        root = Path(directory)
        started = time.perf_counter()
        with patch("gxp_core.edit_handoff.HandoffStore", return_value=HandoffStore(root)):
            exported = service.export_edit_handoff(
                identifier, [{"group_key": row["group_key"], "node_key": row["node_key"]} for row in targets],
                {"user_request": "Verify offline action evidence", "summary": "Read the same selected fixture fields"}, batch["design"],
            )
        export_counts = {"calls": 1, "response_bytes": payload_size(exported), "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
        if not exported.get("available"):
            raise AssertionError(f"Fixture handoff could not be exported: {exported.get('error_code')}")
        command = [sys.executable, "-c", VERIFY_WRITE]
        request = {"root": directory, "ref": exported["handoff_ref"], "fields": FIELDS, "environment": CONFIG,
                   "native_bridge": str(native_bridge) if native_bridge else None, "expected_coverage_sha256": digest(expected),
                   "draft": {"ref_id": IDENTITY["ref_id"], "id": "draft-fixture", "code": "different-row-code", "data": repo.raw,
                             "metadata": {"action_code": identifier}}}
        finish = subprocess.run(command, cwd=write_root, input=json.dumps(request), encoding="utf-8", capture_output=True,
                                timeout=60, env={**os.environ, "PYTHONPATH": str(write_root / "mcp"), "LOCALAPPDATA": directory})
        elapsed_batched = round((time.perf_counter() - batched_started) * 1000, 3)
        if finish.returncode:
            raise RuntimeError(f"Offline Write worker failed: {finish.stderr.strip()}")
        imported = json.loads(finish.stdout)
    if (imported["status"] != "matched" or imported["coverage_sha256"] != digest(expected)
        or imported["target_count"] != len(targets) or imported["authorization_inherited"] or imported["approval_inherited"]):
        raise AssertionError("Write did not verify the expected current targets or the authority boundary")

    legacy_calls = sum(item["calls"] for item in legacy_counts.values())
    legacy_bytes = sum(item["response_bytes"] for item in legacy_counts.values())
    if legacy_loads != legacy_calls:
        raise AssertionError("Legacy path did not produce one design load per measured read")
    batch_calls = batched_counts["calls"] + export_counts["calls"] + 1
    batch_bytes = batched_counts["response_bytes"] + export_counts["response_bytes"] + imported["response_bytes"]
    reduction = {"calls": round(1 - batch_calls / legacy_calls, 4), "response_bytes": round(1 - batch_bytes / legacy_bytes, 4)}
    candidate = imported.pop("native_candidate", None)
    return {
        "scope": ("Offline synthetic fixture; structured response bytes, not MCP wire traffic or live Codex timing. "
                  + ("Native candidate generated and validated; no database, runtime, or approval tests." if candidate else "No candidate generated.")),
        "fixture": {"sha256": digest(data), "targets": len(targets), "paths_per_target": len(FIELDS), "coverage_sha256": digest(expected)},
        "fragmented": {"calls": legacy_calls, "response_bytes": legacy_bytes, "look_design_loads": legacy_loads, "look_reads": legacy_counts},
        "batched_handoff": {"calls": batch_calls, "response_bytes": batch_bytes, "look_batch": batched_counts,
                            "look_handoff_export": export_counts, "write_local_validation": imported,
                            "look_design_loads": repo.loads - legacy_loads, "write_followup_look_reads": 0,
                            "end_to_end_elapsed_ms": elapsed_batched},
        **({"native_candidate": candidate} if candidate else {}),
        "reduction_ratio": reduction, "goal_met": min(reduction.values()) >= 0.5,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-root", type=Path, default=LOOK_ROOT.parent / "write", help="Path to the Write checkout")
    parser.add_argument("--native-bridge", type=Path, help="Path to a built frontend native compiler bridge")
    args = parser.parse_args()
    root = args.write_root.resolve()
    if not (root / "mcp/gxp_editor/handoff_import.py").is_file():
        parser.error("--write-root must point to a Write checkout")
    native_bridge = args.native_bridge.resolve() if args.native_bridge else None
    if native_bridge and not native_bridge.is_file():
        parser.error("--native-bridge must point to a built compiler bridge file")
    result = run(root, native_bridge)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["goal_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
