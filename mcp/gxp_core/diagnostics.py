from __future__ import annotations

import json
import re
from typing import Any

from .canvas import CanvasInspector
from .repository import GxpRepository


STACK_FRAME = re.compile(
    r"\bat\s+(?P<namespace>[A-Za-z_][\w.]*)\.(?P<method>[A-Za-z_]\w*)"
    r"\s*\([^)]*\).*?\bline\s+(?P<line>\d+)",
    re.IGNORECASE | re.DOTALL,
)
QUOTED_IDENTIFIER = re.compile(r"[\"']([A-Za-z0-9][A-Za-z0-9_-]{5,127})[\"']")
ACTION_TOKEN = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9_-]{5,127}\b")
TABLE_TOKEN = re.compile(r"\bgxp_[A-Za-z0-9_]+\b", re.IGNORECASE)
PAGE_SEMANTICS = re.compile(r"(?:页面|流程|申请|修订|变更|岗位矩阵|培训矩阵|岗位培训)")
PAGE_NAME_PATTERN = re.compile(
    r"(?:岗位|培训)(?:矩阵|培训)(?:申请|修订|变更)(?:流程|页面)?"
)
ACTION_NAME_PREFIX = re.compile(
    r"(?:公共动作|表单动作|动作)[：:\s]*[“\"']?"
    r"(?P<name>[\u4e00-\u9fffA-Za-z0-9_-]{2,80})",
    re.IGNORECASE,
)
ACTION_NAME_STOP = re.compile(
    r"(?:没有|应该|怎么|如何|出现|这个|是否|为什么|报错|异常|问题|失败|成功|查看|排查)"
)


def action_name_queries(text: str) -> list[str]:
    candidates: list[str] = []
    for match in ACTION_NAME_PREFIX.finditer(text or ""):
        candidate = ACTION_NAME_STOP.split(match.group("name"), maxsplit=1)[0].strip()
        if len(candidate) >= 2:
            candidates.append(candidate)
    for quoted in re.findall(r"[“\"']([^”\"']{2,80})[”\"']", text or ""):
        candidate = ACTION_NAME_STOP.split(quoted, maxsplit=1)[0].strip()
        if len(candidate) >= 2:
            candidates.append(candidate)
    return list(dict.fromkeys(candidates))[:5]


def page_name_queries(text: str) -> list[str]:
    text = text or ""
    candidates = PAGE_NAME_PATTERN.findall(text)
    for prefix in ("岗位矩阵", "培训矩阵", "岗位培训"):
        if re.search(rf"{prefix}申请\s*[/／、]\s*修订", text):
            apply_name = f"{prefix}申请"
            insert_at = candidates.index(apply_name) + 1 if apply_name in candidates else 0
            candidates.insert(insert_at, f"{prefix}修订")
    return list(dict.fromkeys(candidates))[:5]


def parse_dynamic_exception(text: str) -> dict[str, Any]:
    text = text or ""
    matches = list(STACK_FRAME.finditer(text))
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    message = re.sub(r"^[\w.]+:\s*", "", first_line).strip()
    if not matches:
        return {"matched": False, "message": message}
    repeated_class_frames = []
    for candidate in matches:
        parts = candidate.group("namespace").split(".")
        if len(parts) >= 2 and parts[-1] == parts[-2]:
            repeated_class_frames.append(candidate)
    match = repeated_class_frames[-1] if repeated_class_frames else matches[-1]
    namespace = match.group("namespace")
    components = namespace.split(".")
    generated_class = components[-1]
    return {
        "matched": True,
        "message": message,
        "namespace": namespace,
        "generated_class": generated_class,
        "method": match.group("method"),
        "generated_csharp_line": int(match.group("line")),
    }


class DiagnosticEngine:
    def __init__(self, repository: GxpRepository, inspector: CanvasInspector):
        self.repository = repository
        self.inspector = inspector

    def _candidate_actions(self, generated_class: str) -> list[dict[str, Any]]:
        direct = self.repository.resolve_action(generated_class)
        if direct:
            return direct
        seen = {str(item.get("ref_id")) for item in direct}
        for item in self.repository.find_designs_by_generated_class(generated_class):
            ref_id = str(item.get("ref_id", ""))
            if not ref_id or ref_id in seen:
                continue
            metadata = item.get("metadata") or self.repository.action_metadata(ref_id)
            direct.append(metadata)
            seen.add(ref_id)
        return direct

    @staticmethod
    def _published_at(version: dict[str, Any]) -> str:
        return str(
            version.get("created_time")
            or version.get("modified_time")
            or ""
        )

    def _runtime_published_versions(
        self,
        ref_id: str,
        *,
        at_time: str | None,
        exact_at_time: bool,
    ) -> list[dict[str, Any]]:
        versions = [
            item
            for item in self.repository.get_design_versions(
                ref_id, include_deleted=True, include_content=True
            )
            if item.get("version") == "published"
        ]
        versions.sort(key=self._published_at, reverse=True)
        cutoff = at_time.replace("T", " ") if at_time else None
        if cutoff:
            versions = [
                item
                for item in versions
                if not self._published_at(item) or self._published_at(item) <= cutoff
            ]
            if exact_at_time:
                versions = versions[:1]
        for index, item in enumerate(versions):
            item["published_at"] = self._published_at(item)
            item["runtime_snapshot_role"] = (
                "runtime_snapshot_at_exception_time"
                if cutoff and index == 0
                else "current_runtime_copy"
                if not bool(item.get("is_deleted"))
                else "superseded_published_snapshot"
            )
            item["eligible_runtime_evidence"] = True
        return versions

    def _current_copy_sync(self, ref_id: str) -> dict[str, Any]:
        """Compare only the two active copies, independently of exception history."""
        current_versions = self.repository.get_design_versions(
            ref_id, include_deleted=False, include_content=True
        )
        current_published = next(
            (
                item
                for item in current_versions
                if item.get("version") == "published"
                and not bool(item.get("is_deleted"))
            ),
            None,
        )
        current_draft = next(
            (
                item
                for item in current_versions
                if item.get("version") == "draft"
                and not bool(item.get("is_deleted"))
            ),
            None,
        )
        if not current_published or not current_draft:
            return {
                "available": False,
                "reason": "Active published or draft copy is missing",
                "comparison_purpose": "detect_unpublished_changes",
                "runtime_copy": "published",
                "editable_copy": "draft",
                "draft_edits_affect_runtime": False,
            }
        try:
            data = self.inspector.compare(
                json.loads(str(current_published.get("data") or "{}")),
                json.loads(str(current_draft.get("data") or "{}")),
            )
        except json.JSONDecodeError as exc:
            return {
                "available": False,
                "reason": str(exc),
                "comparison_purpose": "detect_unpublished_changes",
                "runtime_copy": "published",
                "editable_copy": "draft",
                "draft_edits_affect_runtime": False,
            }
        csharp_same = (
            current_published.get("csharp_sha256")
            == current_draft.get("csharp_sha256")
        )
        has_unpublished_changes = not bool(data.get("same") and csharp_same)

        def summary(item: dict[str, Any], copy_role: str) -> dict[str, Any]:
            return {
                "design_id": item.get("design_id"),
                "version": item.get("version"),
                "created_time": item.get("created_time"),
                "modified_time": item.get("modified_time"),
                "data_sha256": item.get("data_sha256"),
                "csharp_sha256": item.get("csharp_sha256"),
                "copy_role": copy_role,
            }

        return {
            "available": True,
            "comparison_purpose": "detect_unpublished_changes",
            "sync_status": (
                "unpublished_draft_changes"
                if has_unpublished_changes
                else "synchronized"
            ),
            "sync_status_label": (
                "存在未发布草稿改动"
                if has_unpublished_changes
                else "已同步"
            ),
            "has_unpublished_changes": has_unpublished_changes,
            "data": data,
            "csharp_same": csharp_same,
            "runtime_copy": "published",
            "runtime_copy_label": "发布副本",
            "editable_copy": "draft",
            "draft_edits_affect_runtime": False,
            "current_published": summary(
                current_published, "runtime_published_copy"
            ),
            "current_draft": summary(current_draft, "editable_draft_copy"),
        }

    @staticmethod
    def _line_tokens(context: dict[str, Any]) -> list[str]:
        text = "\n".join(str(item.get("text", "")) for item in context.get("lines", []))
        quoted = QUOTED_IDENTIFIER.findall(text)
        generic = ACTION_TOKEN.findall(text) if not quoted else []
        ignored = {
            "Dictionary",
            "Exception",
            "CallPublicAction",
            "CallAction",
            "IsSuccess",
            "System",
            "String",
            "Object",
            "Params",
        }
        return [
            token
            for token in dict.fromkeys([*quoted, *generic])
            if token not in ignored and not token.startswith("gxp_")
        ][:12]

    def _called_action_history(
        self,
        called_actions: list[dict[str, Any]],
        *,
        message: str,
        at_time: str | None,
    ) -> list[dict[str, Any]]:
        results = []
        seen_ref_ids: set[str] = set()
        for action in called_actions:
            ref_id = str(action.get("ref_id", ""))
            if not ref_id or ref_id in seen_ref_ids:
                continue
            seen_ref_ids.add(ref_id)
            versions = self._runtime_published_versions(
                ref_id,
                at_time=at_time,
                exact_at_time=bool(at_time),
            )
            evidence = []
            seen_hashes: set[tuple[str, str]] = set()
            for version in versions:
                csharp = str(version.get("csharp_code", ""))
                data_text = str(version.get("data", ""))
                if message and message not in csharp and message not in data_text:
                    continue
                signature = (
                    str(version.get("data_sha256", "")),
                    str(version.get("csharp_sha256", "")),
                )
                if signature in seen_hashes:
                    continue
                seen_hashes.add(signature)
                try:
                    data = json.loads(data_text or "{}")
                except json.JSONDecodeError:
                    data = {}
                exception_nodes = self.inspector.inspect(data, terms=[message]) if message else []
                nearby_nodes = []
                for exception_node in exception_nodes:
                    index = int(exception_node.get("internal_index", 0))
                    group = str(exception_node.get("group_key", ""))
                    nearby_nodes.extend(
                        self.inspector.inspect(
                            data,
                            group=group,
                            start=max(0, index - 3),
                            end=index + 1,
                            include_params=False,
                        )
                    )
                predicate_nodes = [
                    node
                    for node in nearby_nodes
                    if (node.get("facts") or {}).get("filters")
                    or (node.get("facts") or {}).get("condition")
                ]
                contexts = self.inspector.search_csharp(csharp, [message], context=4)
                evidence.append(
                    {
                        "design_id": version.get("design_id"),
                        "version": version.get("version"),
                        "published_at": version.get("published_at"),
                        "runtime_snapshot_role": version.get("runtime_snapshot_role"),
                        "is_deleted": bool(version.get("is_deleted")),
                        "modified_time": version.get("modified_time"),
                        "data_sha256": version.get("data_sha256"),
                        "csharp_sha256": version.get("csharp_sha256"),
                        "exception_nodes": exception_nodes,
                        "predicate_nodes_before_exception": predicate_nodes,
                        "generated_csharp_matches": contexts,
                    }
                )
            evidence.sort(
                key=lambda item: (
                    not bool(item.get("is_deleted")),
                    str(item.get("modified_time", "")),
                ),
                reverse=True,
            )
            results.append(
                {
                    "action": action,
                    "exception_history": evidence[:10],
                    "history_count_after_deduplication": len(evidence),
                }
            )
        return results

    def trace_dynamic_exception(
        self,
        text: str,
        *,
        at_time: str | None = None,
        context_lines: int = 4,
    ) -> dict[str, Any]:
        parsed = parse_dynamic_exception(text)
        if not parsed.get("matched"):
            return {
                "parsed": parsed,
                "error": "No generated C# stack frame with a line number was found",
            }
        generated_class = str(parsed["generated_class"])
        line_number = int(parsed["generated_csharp_line"])
        message = str(parsed.get("message", ""))
        actions = self._candidate_actions(generated_class)
        action_results: list[dict[str, Any]] = []
        for action in actions:
            ref_id = str(action.get("ref_id", ""))
            if not ref_id:
                continue
            versions = self._runtime_published_versions(
                ref_id,
                at_time=at_time,
                exact_at_time=bool(at_time),
            )
            version_results = []
            all_resolved_calls: list[dict[str, Any]] = []
            for version in versions:
                csharp = str(version.get("csharp_code", ""))
                context = self.inspector.csharp_context(
                    csharp, line_number, context=context_lines
                )
                if not context.get("lines"):
                    continue
                target_text = next(
                    (
                        str(item.get("text", ""))
                        for item in context["lines"]
                        if item.get("target")
                    ),
                    "",
                )
                tokens = self._line_tokens(context)
                resolved_calls = self.repository.resolve_actions(tokens)
                all_resolved_calls.extend(resolved_calls)
                try:
                    data = json.loads(str(version.get("data", "{}")))
                except json.JSONDecodeError:
                    data = {}
                call_codes = {
                    str(item.get("action_code", ""))
                    for item in resolved_calls
                    if item.get("action_code")
                }
                call_ids = {
                    str(item.get("ref_id", ""))
                    for item in resolved_calls
                    if item.get("ref_id")
                }
                canvas_nodes = []
                for node in self.inspector.inspect(data):
                    called = (node.get("facts") or {}).get("called_action") or {}
                    if (
                        str(called.get("code", "")) in call_codes
                        or str(called.get("id", "")) in call_ids
                    ):
                        canvas_nodes.append(node)
                score = 0
                if generated_class in csharp:
                    score += 2
                if message and message in csharp:
                    score += 5
                if resolved_calls:
                    score += 4
                if canvas_nodes:
                    score += 4
                if target_text:
                    score += 1
                if not bool(version.get("is_deleted")):
                    score += 2
                version_results.append(
                    {
                        "design_id": version.get("design_id"),
                        "version": version.get("version"),
                        "published_at": version.get("published_at"),
                        "runtime_snapshot_role": version.get("runtime_snapshot_role"),
                        "eligible_runtime_evidence": True,
                        "is_deleted": bool(version.get("is_deleted")),
                        "modified_time": version.get("modified_time"),
                        "data_sha256": version.get("data_sha256"),
                        "csharp_sha256": version.get("csharp_sha256"),
                        "generated_csharp": context,
                        "resolved_called_actions": resolved_calls,
                        "matching_canvas_nodes": canvas_nodes,
                        "exception_text_present": bool(message and message in csharp),
                        "evidence_score": score,
                    }
                )
            version_results.sort(
                key=lambda item: (item.get("evidence_score", 0), str(item.get("modified_time", ""))),
                reverse=True,
            )
            # This comparison must not reuse `versions`: with at_time those are
            # historical runtime snapshots, not the current published copy.
            current_compare = self._current_copy_sync(ref_id)
            action_results.append(
                {
                    "action": action,
                    "runtime_published_candidates": version_results,
                    "candidate_versions": version_results,
                    "called_action_exception_history": self._called_action_history(
                        all_resolved_calls,
                        message=message,
                        at_time=at_time,
                    ),
                    "current_copy_sync": current_compare,
                    "current_published_vs_draft": current_compare,
                }
            )
        return {
            "parsed": parsed,
            "at_time": at_time,
            "actions": action_results,
            "selection_rule": (
                "Only published snapshots are runtime candidates. When an exception time is "
                "supplied, select the latest published snapshot at or before that time. "
                "The editable draft is comparison-only and never runtime evidence."
            ),
            "draft_edits_affect_runtime": False,
        }

    def diagnose_codex_input(self, text: str, *, at_time: str | None = None) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise ValueError("Codex input cannot be empty")
        parsed = parse_dynamic_exception(text)
        if parsed.get("matched"):
            return {
                "input_kind": "dynamic_exception",
                "diagnosis": self.trace_dynamic_exception(text, at_time=at_time),
                "next_tools": [
                    "inspect_action",
                    "get_records",
                    "evaluate_node_predicate",
                ],
            }
        tokens = list(dict.fromkeys(ACTION_TOKEN.findall(text)))[:30]
        actions = self.repository.resolve_actions(tokens)
        token_matches = [
            {
                "query": token,
                "matches": [
                    item
                    for item in actions
                    if token
                    in {
                        str(item.get("ref_id", "")),
                        str(item.get("action_code", "")),
                    }
                ],
            }
            for token in tokens
        ]
        ambiguous_tokens = [
            item["query"] for item in token_matches if len(item["matches"]) > 1
        ]
        name_queries = action_name_queries(text)
        name_matches = []
        seen_ref_ids = {str(item.get("ref_id", "")) for item in actions}
        for query in name_queries:
            for item in self.repository.search_actions(query, limit=20):
                ref_id = str(item.get("ref_id", ""))
                if not ref_id or ref_id in seen_ref_ids:
                    continue
                item["matched_query"] = query
                name_matches.append(item)
                seen_ref_ids.add(ref_id)
        actions.extend(name_matches)
        page_queries = page_name_queries(text) if PAGE_SEMANTICS.search(text) else []
        page_candidates = []
        seen_pages: set[str] = set()
        if not actions and hasattr(self.repository, "search_pages"):
            for query in page_queries:
                for item in self.repository.search_pages(query, limit=5):
                    page_key = str(
                        item.get("page_id") or item.get("route") or item.get("out_id") or ""
                    )
                    if not page_key or page_key in seen_pages:
                        continue
                    item["matched_query"] = query
                    page_candidates.append(item)
                    seen_pages.add(page_key)
            page_candidates = page_candidates[:10]
        tables = list(dict.fromkeys(TABLE_TOKEN.findall(text)))[:20]
        design_text_matches = []
        quoted_chinese = re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fff\w]{5,80}", text)
        if quoted_chinese and not page_candidates:
            try:
                design_text_matches = self.repository.search_design_text(
                    quoted_chinese[0], max_rows=20
                )
            except Exception:
                design_text_matches = []
        return {
            "input_kind": "natural_language",
            "resolved_actions": actions,
            "mentioned_tables": tables,
            "design_text_matches": design_text_matches,
            "recognized_action_tokens": tokens,
            "action_token_matches": token_matches,
            "ambiguous_action_tokens": ambiguous_tokens,
            "recognized_action_name_queries": name_queries,
            "recognized_page_queries": page_queries,
            "page_candidates": page_candidates,
            "page_resolution_status": (
                "not_applicable"
                if not page_queries
                else "not_found"
                if not page_candidates
                else "unique"
                if len(page_candidates) == 1
                else "candidates"
            ),
            "action_resolution_status": (
                "not_found"
                if not actions
                else "ambiguous"
                if ambiguous_tokens or len({str(item.get("ref_id", "")) for item in actions}) > 1
                else "unique"
            ),
            "requires_action_selection": bool(
                ambiguous_tokens
                or len({str(item.get("ref_id", "")) for item in actions}) > 1
            ),
            "next_tools": [
                "inspect_action"
                if actions
                else "list_page_actions"
                if page_candidates
                else "resolve_action",
                "describe_table" if tables else "get_design_versions",
                "readonly_sql only when structured tools are insufficient",
            ],
            "page_next_step": (
                "Select one page Route/Id/OutId, then call list_page_actions to locate its "
                "form/subform actions."
                if page_candidates
                else ""
            ),
        }

    def evaluate_node_predicate(
        self,
        *,
        ref_id: str,
        group: str,
        node_key: str,
        record: dict[str, Any],
        version: str = "published",
    ) -> dict[str, Any]:
        design = self.repository.load_design(ref_id, version=version)
        nodes = self.inspector.inspect(
            design["data_json"], group=group, node_key=node_key, include_params=True
        )
        if not nodes:
            raise ValueError("The requested group/node was not found")
        node = nodes[0]
        filters = (node.get("facts") or {}).get("filters") or []
        evaluations = []
        for item in filters:
            field = str(item.get("field", ""))
            operator = str(item.get("operator", ""))
            expression = str(item.get("expression", ""))
            current = record.get(field)
            literal: Any = expression
            resolved = False
            if expression.lower() == "null":
                literal = None
                resolved = True
            elif (expression.startswith("\"") and expression.endswith("\"")) or (
                expression.startswith("'") and expression.endswith("'")
            ):
                literal = expression[1:-1]
                resolved = True
            elif re.fullmatch(r"-?\d+(?:\.\d+)?", expression):
                literal = float(expression) if "." in expression else int(expression)
                resolved = True
            elif expression.lower() in {"true", "false"}:
                literal = expression.lower() == "true"
                resolved = True
            matched = None
            if resolved:
                op = operator.lower()
                if op in {"=", "==", "equal", "equalto"}:
                    matched = current == literal
                elif op in {"<>", "!=", "notequal", "notequalto"}:
                    matched = current != literal
                elif op in {"isnull"}:
                    matched = current is None
                elif op in {"isnotnull"}:
                    matched = current is not None
            evaluations.append(
                {
                    **item,
                    "record_value": current,
                    "literal_resolved": resolved,
                    "matched": matched,
                }
            )
        definite = [item["matched"] for item in evaluations if item["matched"] is not None]
        return {
            "action": design.get("metadata"),
            "version": version,
            "node": node,
            "evaluations": evaluations,
            "all_definite_filters_match": all(definite) if definite else None,
            "note": "Expression-based values remain unresolved and require caller variables.",
        }
