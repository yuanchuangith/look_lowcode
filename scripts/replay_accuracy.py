from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


EQUIVALENT_CLASSIFICATIONS = {
    "scope-counterexample": {"passed", "pending_review", "risk"},
    "shared-type": {"risk", "clarification", "pending_review"},
    "normal-numbered-item": {"passed", "clarification"},
    "new-version-real-callee": {"implementation", "pending_review"},
}


def replay_settings(path: Path) -> dict:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib
    except ImportError:
        return fallback_settings(text)
    return tomllib.loads(text)


def fallback_settings(text: str) -> dict:
    result = {"mcp_servers": {}}
    section_seen = False
    string_pattern = r'(?:"(?:[^"\\]|\\.)*"|\'[^\']*\')'
    for line in text.splitlines():
        if line.lstrip().startswith("["):
            section_seen = True
        server = re.match(r'\s*\[mcp_servers\.(' + string_pattern + r'|[A-Za-z0-9_-]+)(?:\.[^\]]+)?\]\s*(?:#.*)?$', line)
        if server:
            name = server[1]
            name = json.loads(name) if name.startswith('"') else name.strip("'")
            result["mcp_servers"][name] = {}
        model = re.match(r'\s*model\s*=\s*(' + string_pattern + r')\s*(?:#.*)?$', line) if not section_seen else None
        if model:
            value = model[1]
            result["model"] = json.loads(value) if value.startswith('"') else value[1:-1]
    return result


def grade_case(case, actual):
    expected = case["expected"]
    accepted = EQUIVALENT_CLASSIFICATIONS.get(case["id"], {expected["classification"]})
    if actual.get("decision") != expected["decision"] or actual.get("classification") not in accepted:
        return {"id": case["id"], "reason": "decision_or_classification", "actual": actual}
    if expected["classification"] in {"passed", "excluded"} and actual.get("headline", "").startswith("问题1"):
        return {"id": case["id"], "reason": "normal_result_labeled_problem"}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Paired fixed-evidence conversation replay; never submits platform data")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = json.loads((root / "tests/accuracy_replay_cases.json").read_text(encoding="utf-8"))
    config_path = Path.home() / ".codex/config.toml"
    config = replay_settings(config_path)
    model = config.get("model")
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex CLI is required for model replay")
    work = Path(tempfile.mkdtemp(prefix="look-fixed-evidence-replay-"))
    schema = {"type": "object", "additionalProperties": False, "required": ["results"], "properties": {"results": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["id", "classification", "decision", "headline", "reason"], "properties": {name: {"type": "string"} for name in ("id", "classification", "decision", "headline", "reason")}}}}}
    schema_path = output / "output-schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    runs = []
    for label, source in (("baseline", Path(args.baseline)), ("candidate", root)):
        skill = source / "skills/gxp-lowcode-debug"
        contract = (skill / "SKILL.md").read_text(encoding="utf-8") + "\n" + (skill / "references/report-contract.md").read_text(encoding="utf-8")
        extra = skill / "references/conversation-contract.md"
        if extra.is_file():
            contract += "\n" + extra.read_text(encoding="utf-8")
        visible_cases = [{key: value for key, value in case.items() if key != "expected"} for case in cases]
        decisions = [case["expected"]["decision"] for case in cases] + ["replace_with_global_array", "confirmed_scope_bug", "confirmed_null_bug", "mark_fixed_without_read", "follow_similar_A", "add_new_sort"]
        prompt = "这是用户要求的固定证据多轮回放，不是代码实施任务。所有数据是合成案例。不要调用任何工具、不要读取文件、不要联网或提交业务。根据下面提供的技能契约对12个独立案例作出当前这一轮回复决策。每个案例输出独立headline（自然回复首句）和简短reason。classification选bug/risk/passed/pending_review/excluded/implementation/clarification。decision从所列选项选最符合案例的一个，选项顺序不代表答案。字段evidence是本次全部已取证内容，不要假设执行了额外验证。\n<skill>" + contract + "</skill>\n<decisions>" + json.dumps(sorted(decisions)) + "</decisions>\n<cases>" + json.dumps(visible_cases, ensure_ascii=False) + "</cases>"
        prompt_path = output / f"{label}-prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        command = [executable, "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only", "--cd", str(work), "--json", "--output-schema", str(schema_path), "--output-last-message", str(output / f"{label}-answer.json")]
        if model:
            command += ["--model", model]
        for name in config.get("mcp_servers", {}):
            command += ["--config", f"mcp_servers.{name}.enabled=false"]
        command += ["-"]
        begin = time.perf_counter()
        completed = subprocess.run(command, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=900)
        elapsed = time.perf_counter() - begin
        (output / f"{label}-events.jsonl").write_text(completed.stdout, encoding="utf-8")
        (output / f"{label}-stderr.txt").write_text(completed.stderr, encoding="utf-8")
        events = []
        for line in completed.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        calls = [event for event in events if event.get("type") == "item.completed" and event.get("item", {}).get("type") not in {"agent_message", "reasoning", "todo_list"}]
        if completed.returncode:
            print(json.dumps({"run": label, "returncode": completed.returncode, "output": str(output)}))
            return completed.returncode
        answer = json.loads((output / f"{label}-answer.json").read_text(encoding="utf-8"))
        indexed = {item["id"]: item for item in answer["results"]}
        failures = []
        for case in cases:
            actual = indexed.get(case["id"], {})
            failure = grade_case(case, actual)
            if failure:
                failures.append(failure)
        if len(indexed) != len(cases) or calls:
            failures.append({"reason": "case_count_or_unexpected_tool_use", "tool_calls": len(calls)})
        runs.append({"label": label, "model": model or "same_cli_default", "cases": len(cases), "failures": failures, "elapsed_seconds": round(elapsed, 3), "tool_calls": len(calls), "event_bytes": len(completed.stdout.encode("utf-8")), "usage": [event.get("usage") for event in events if event.get("usage")]})
        (output / "results.json").write_text(json.dumps({"runs": runs, "measurement": "fixed_evidence_batch_not_live_platform_or_population_accuracy"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"run": label, "cases": len(cases), "failures": len(failures), "seconds": round(elapsed, 3)}), flush=True)
    return 1 if runs[-1]["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
