from __future__ import annotations

from typing import Any

from .canvas import CanvasInspector
from .config import ConfigurationError, default_config_path
from .db import ReadOnlyDatabase
from .diagnostics import DiagnosticEngine
from .repository import GxpRepository


class GxpReadonlyService:
    def __init__(self, database: ReadOnlyDatabase | None = None):
        self.database = database or ReadOnlyDatabase()
        self.repository = GxpRepository(self.database)
        self.inspector = CanvasInspector()
        self.diagnostics = DiagnosticEngine(self.repository, self.inspector)

    @classmethod
    def connection_status(cls) -> dict[str, Any]:
        try:
            return cls().database.status()
        except ConfigurationError as exc:
            return {
                "configured": False,
                "config_path": str(default_config_path()),
                "error": str(exc),
            }
        except Exception as exc:
            return {
                "configured": True,
                "reachable": False,
                "config_path": str(default_config_path()),
                "error": str(exc),
            }

    def resolve_action(self, identifier: str) -> dict[str, Any]:
        matches = self.repository.resolve_action(identifier)
        resolution_mode = "exact_identifier"
        if not matches:
            matches = self.repository.search_actions(identifier)
            resolution_mode = "catalog_name_search"
        return {
            "identifier": identifier,
            "resolution_mode": resolution_mode,
            "matches": matches,
            "count": len(matches),
        }

    def search_actions(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        matches = self.repository.search_actions(query, limit=limit)
        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
            "selection_rule": (
                "Prefer an exact action code or RefId. For name matches, confirm action type, "
                "action code, RefId and form page before inspecting the design."
            ),
        }

    def search_pages(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        matches = self.repository.search_pages(query, limit=limit)
        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
            "selection_rule": (
                "Prefer an exact Route, Id or OutId. Otherwise confirm the localized display "
                "name before calling list_page_actions. Chinese fuzzy results are bounded and "
                "ranked by bigram similarity."
            ),
        }

    def list_page_actions(
        self, page_identifier: str, *, limit: int = 50
    ) -> dict[str, Any]:
        pages = self.repository.resolve_pages(page_identifier)
        if len(pages) != 1:
            candidates = (
                self.repository.search_pages(page_identifier, limit=min(limit, 20))
                if not pages
                else pages
            )
            return {
                "page_identifier": page_identifier,
                "resolution_status": "not_found" if not candidates else "ambiguous",
                "page_candidates": candidates,
                "actions": [],
                "count": 0,
                "next_step": (
                    "Select one page Route, Id or OutId from page_candidates and retry "
                    "list_page_actions."
                ),
            }
        page = pages[0]
        actions = self.repository.list_page_actions(page, limit=limit)
        return {
            "page_identifier": page_identifier,
            "resolution_status": "unique",
            "page": page,
            "actions": actions,
            "count": len(actions),
            "selection_rule": (
                "Use the action display name together with its code and RefId; do not infer a "
                "subform action from the page name alone."
            ),
        }

    @staticmethod
    def _copy_summary(design: dict[str, Any], role: str) -> dict[str, Any]:
        runtime = role == "published"
        return {
            key: design.get(key)
            for key in (
                "design_id",
                "version",
                "is_publish",
                "is_deleted",
                "created_time",
                "modified_time",
                "data_length",
                "data_sha256",
                "csharp_length",
                "csharp_sha256",
            )
        } | {
            "copy_role": "runtime_published_copy" if runtime else "editable_draft_copy",
            "used_by_runtime": runtime,
            "editing_affects_runtime": False,
        }

    @staticmethod
    def _version_semantics() -> dict[str, Any]:
        return {
            "model": "same_action_two_copies",
            "published": "runtime copy; changes only when the action is published",
            "draft": "editable copy of the action; editing or saving it does not affect runtime",
            "runtime_copy": "published",
            "draft_edits_affect_runtime": False,
            "comparison_purpose": "detect unpublished draft changes, not logical correctness",
            "publish_effect": "publishing copies the editable design into the runtime copy",
        }

    def get_design_versions(
        self,
        ref_id: str,
        *,
        include_deleted: bool = False,
        include_history: bool = False,
    ) -> dict[str, Any]:
        include_history = bool(include_history or include_deleted)
        versions = self.repository.get_design_versions(
            ref_id, include_deleted=include_history, include_content=False
        )
        current_published = next(
            (
                item
                for item in versions
                if item.get("version") == "published"
                and not bool(item.get("is_deleted"))
            ),
            None,
        )
        current_draft = next(
            (
                item
                for item in versions
                if item.get("version") == "draft"
                and not bool(item.get("is_deleted"))
            ),
            None,
        )
        current = [item for item in (current_published, current_draft) if item]
        history = [item for item in versions if item not in current]
        for item in current:
            role = str(item.get("version"))
            item.update(self._copy_summary(item, role))
            item["snapshot_status"] = "current_copy"
        for item in history:
            item["copy_role"] = (
                "superseded_published_snapshot"
                if item.get("version") == "published"
                else "historical_draft_copy"
            )
            item["used_by_runtime"] = False
            item["editing_affects_runtime"] = False
            item["snapshot_status"] = "historical"
        hashes_match = bool(
            current_published
            and current_draft
            and current_published.get("data_sha256") == current_draft.get("data_sha256")
            and current_published.get("csharp_sha256")
            == current_draft.get("csharp_sha256")
        )
        sync_status = (
            "synchronized"
            if hashes_match
            else "unpublished_draft_changes"
            if current_published and current_draft
            else "missing_current_copy"
        )
        status_labels = {
            "synchronized": "已同步",
            "unpublished_draft_changes": "存在未发布草稿改动",
            "missing_current_copy": "当前副本缺失",
        }
        return {
            "action": self.repository.action_metadata(ref_id),
            "version_semantics": self._version_semantics(),
            "current_published": current_published,
            "current_draft": current_draft,
            "sync_status": sync_status,
            "sync_status_label": status_labels[sync_status],
            "has_unpublished_changes": bool(
                current_published and current_draft and not hashes_match
            ),
            "runtime_copy": "published",
            "runtime_copy_label": "发布副本",
            "draft_edits_affect_runtime": False,
            "sync_check_scope": "copy_content_only_not_logical_correctness_or_runtime_success",
            "versions": current + (history if include_history else []),
            "history": history if include_history else [],
            "count": len(current) + (len(history) if include_history else 0),
            "history_included": include_history,
            "history_count": len(history) if include_history else None,
        }

    def inspect_action(
        self,
        identifier: str,
        *,
        version: str = "published",
        group: str | None = None,
        terms: list[str] | None = None,
        node_key: str | None = None,
        start: int | None = None,
        end: int | None = None,
        include_params: bool = False,
        csharp_line: int | None = None,
        csharp_context: int = 3,
        design_id: str | None = None,
        at_time: str | None = None,
        focus_fields: list[str] | None = None,
        include_generated_csharp: bool = False,
        max_nodes: int = 20,
    ) -> dict[str, Any]:
        matches = self.repository.resolve_action(identifier)
        if not matches:
            matches = self.repository.search_actions(identifier)
        if len(matches) != 1:
            return {
                "identifier": identifier,
                "resolution_status": "not_found" if not matches else "ambiguous",
                "matches": matches,
                "count": len(matches),
                "next_step": (
                    "Call search_actions and select one exact action code or RefId before inspection."
                ),
            }
        ref_id = str(matches[0]["ref_id"])
        design = self.repository.load_design(
            ref_id,
            version=version,
            design_id=design_id,
            at_time=at_time,
            include_deleted=bool(design_id or at_time),
        )
        nodes = self.inspector.inspect(
            design["data_json"],
            group=group,
            terms=terms,
            node_key=node_key,
            start=start,
            end=end,
            include_params=False,
        )
        published = design.get("version") == "published"
        current_runtime_copy = published and not bool(design.get("is_deleted"))
        field_evidence = self.inspector.focus_fields(nodes, focus_fields or [])
        reported_nodes = nodes
        if focus_fields and not terms and not node_key:
            focused_locations = {
                (
                    item.get("group_key"),
                    item.get("node_key"),
                    item.get("internal_index"),
                )
                for item in field_evidence
            }
            reported_nodes = [
                node
                for node in nodes
                if (
                    node.get("group_key"),
                    node.get("node_key"),
                    node.get("internal_index"),
                )
                in focused_locations
            ]
        matched_node_count = len(reported_nodes)
        too_broad_for_params = bool(include_params and matched_node_count > 10)
        if include_params and not too_broad_for_params:
            parameterized_nodes = self.inspector.inspect(
                design["data_json"],
                group=group,
                terms=terms,
                node_key=node_key,
                start=start,
                end=end,
                include_params=True,
            )
            if focus_fields and not terms and not node_key:
                focused_locations = {
                    (
                        item.get("group_key"),
                        item.get("node_key"),
                        item.get("internal_index"),
                    )
                    for item in field_evidence
                }
                parameterized_nodes = [
                    node
                    for node in parameterized_nodes
                    if (
                        node.get("group_key"),
                        node.get("node_key"),
                        node.get("internal_index"),
                    )
                    in focused_locations
                ]
            reported_nodes = parameterized_nodes

        safe_max_nodes = max(1, min(int(max_nodes), 100))
        limited_nodes = reported_nodes[:safe_max_nodes]
        result = {
            "action": design.get("metadata"),
            "design": {
                key: design.get(key)
                for key in (
                    "design_id",
                    "version",
                    "is_deleted",
                    "modified_time",
                    "data_sha256",
                    "csharp_sha256",
                )
            }
            | {
                "copy_role": (
                    "runtime_published_copy"
                    if current_runtime_copy
                    else "historical_published_snapshot"
                    if published
                    else "editable_draft_copy"
                ),
                "used_by_runtime": current_runtime_copy,
                "used_by_runtime_now": current_runtime_copy,
                "eligible_as_historical_runtime_evidence": bool(
                    published and (design_id or at_time)
                ),
                "editing_affects_runtime": False,
            },
            "version_semantics": self._version_semantics(),
            "nodes": limited_nodes,
            "matched_node_count": matched_node_count,
            "node_count": len(limited_nodes),
            "nodes_truncated": matched_node_count > len(limited_nodes),
            "max_nodes": safe_max_nodes,
            "scanned_node_count": len(nodes),
            "too_broad_for_params": too_broad_for_params,
        }
        if too_broad_for_params:
            result["params_omitted"] = True
            result["params_next_step"] = (
                "Narrow by group, node_key or start/end until 10 or fewer nodes match, then "
                "retry include_params=true."
            )
        if result["nodes_truncated"]:
            result["nodes_next_step"] = (
                "Narrow by group, node_key or start/end to inspect the remaining matched nodes."
            )
        if focus_fields:
            result["requested_focus_fields"] = focus_fields
            result["field_evidence"] = field_evidence[:safe_max_nodes]
            result["field_match_count"] = len(field_evidence)
            result["field_evidence_truncated"] = len(field_evidence) > safe_max_nodes
        if csharp_line:
            result["generated_csharp"] = self.inspector.csharp_context(
                str(design.get("csharp_code", "")), csharp_line, csharp_context
            )
        elif include_generated_csharp and terms:
            csharp_result = self.inspector.search_csharp_with_metadata(
                str(design.get("csharp_code", "")),
                terms,
                csharp_context,
                max_matches=20,
            )
            result["generated_csharp_matches"] = csharp_result["matches"]
            result["generated_csharp_match_count"] = csharp_result[
                "matched_line_count"
            ]
            result["generated_csharp_matches_truncated"] = csharp_result[
                "matches_truncated"
            ]
        elif include_generated_csharp and limited_nodes:
            generated_terms = self.inspector.node_csharp_terms(
                limited_nodes, focus_fields
            )
            result["generated_csharp_search_terms"] = generated_terms
            csharp_result = self.inspector.search_csharp_with_metadata(
                str(design.get("csharp_code", "")),
                generated_terms,
                csharp_context,
                max_matches=20,
            )
            result["generated_csharp_matches"] = csharp_result["matches"]
            result["generated_csharp_match_count"] = csharp_result[
                "matched_line_count"
            ]
            result["generated_csharp_matches_truncated"] = csharp_result[
                "matches_truncated"
            ]
            result[
                "generated_csharp_evidence_kind"
            ] = "term_match_candidate_not_exact_source_map"
            result["node_generated_csharp_evidence"] = (
                self.inspector.generated_csharp_node_evidence(
                    limited_nodes,
                    str(design.get("csharp_code", "")),
                    focus_fields=focus_fields,
                    context=csharp_context,
                    max_nodes=min(10, safe_max_nodes),
                )
            )
        return result

    def inspect_component_filters(
        self,
        identifier: str,
        component: str,
        *,
        version: str = "published",
        include_params: bool = False,
        design_id: str | None = None,
        at_time: str | None = None,
    ) -> dict[str, Any]:
        matches = self.repository.resolve_action(identifier)
        if not matches:
            matches = self.repository.search_actions(identifier)
        if len(matches) != 1:
            return {
                "identifier": identifier,
                "component_query": component,
                "resolution_status": "not_found" if not matches else "ambiguous",
                "matches": matches,
                "count": len(matches),
                "next_step": (
                    "Select one exact action code or RefId before inspecting component filters."
                ),
            }
        ref_id = str(matches[0]["ref_id"])
        design = self.repository.load_design(
            ref_id,
            version=version,
            design_id=design_id,
            at_time=at_time,
            include_deleted=bool(design_id or at_time),
        )
        filters = self.inspector.inspect_component_filters(
            design["data_json"], component, include_params=False
        )
        too_broad_for_params = bool(
            include_params and int(filters.get("writer_count", 0)) > 10
        )
        if include_params and not too_broad_for_params:
            filters = self.inspector.inspect_component_filters(
                design["data_json"], component, include_params=True
            )
        published = design.get("version") == "published"
        current_runtime_copy = published and not bool(design.get("is_deleted"))
        return {
            "action": design.get("metadata"),
            "design": {
                key: design.get(key)
                for key in (
                    "design_id",
                    "version",
                    "is_deleted",
                    "modified_time",
                    "data_sha256",
                )
            }
            | {
                "copy_role": (
                    "runtime_published_copy"
                    if current_runtime_copy
                    else "historical_published_snapshot"
                    if published
                    else "editable_draft_copy"
                ),
                "used_by_runtime": current_runtime_copy,
            },
            "component_filters": filters,
            "too_broad_for_params": too_broad_for_params,
            "params_omitted": too_broad_for_params,
            "params_next_step": (
                "Retry with the exact component key; params are omitted when more than 10 "
                "writers match."
                if too_broad_for_params
                else ""
            ),
            "generated_csharp_included": False,
        }

    def compare_designs(self, ref_id: str) -> dict[str, Any]:
        published = self.repository.load_design(
            ref_id, version="published", include_deleted=False
        )
        draft = self.repository.load_design(ref_id, version="draft", include_deleted=False)
        data = self.inspector.compare(published["data_json"], draft["data_json"])
        csharp_same = published.get("csharp_sha256") == draft.get("csharp_sha256")
        has_unpublished_changes = not bool(data.get("same") and csharp_same)
        sync_status = (
            "unpublished_draft_changes"
            if has_unpublished_changes
            else "synchronized"
        )
        return {
            "action": published.get("metadata"),
            "version_semantics": self._version_semantics(),
            "comparison_purpose": "detect_unpublished_changes",
            "sync_status": sync_status,
            "sync_status_label": (
                "存在未发布草稿改动"
                if has_unpublished_changes
                else "已同步"
            ),
            "has_unpublished_changes": has_unpublished_changes,
            "draft_edits_affect_runtime": False,
            "runtime_copy": "published",
            "editable_copy": "draft",
            "runtime_copy_label": "发布副本",
            "sync_check_scope": "copy_content_only_not_logical_correctness_or_runtime_success",
            "data": data,
            "csharp_same": csharp_same,
            "published": self._copy_summary(published, "published"),
            "draft": self._copy_summary(draft, "draft"),
        }

    def trace_dynamic_exception(
        self, text: str, *, at_time: str | None = None, context_lines: int = 4
    ) -> dict[str, Any]:
        return self.diagnostics.trace_dynamic_exception(
            text, at_time=at_time, context_lines=context_lines
        )

    def diagnose_codex_input(
        self, text: str, *, at_time: str | None = None
    ) -> dict[str, Any]:
        return self.diagnostics.diagnose_codex_input(text, at_time=at_time)

    def describe_table(self, table: str) -> dict[str, Any]:
        return self.repository.describe_table(table)

    def get_records(
        self,
        table: str,
        *,
        filters: list[dict[str, Any]],
        columns: list[str] | None = None,
        order_by: str | None = None,
        descending: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self.repository.get_records(
            table,
            filters=filters,
            columns=columns,
            order_by=order_by,
            descending=descending,
            limit=limit,
        )

    def evaluate_node_predicate(
        self,
        *,
        ref_id: str,
        group: str,
        node_key: str,
        record: dict[str, Any],
        version: str = "published",
    ) -> dict[str, Any]:
        return self.diagnostics.evaluate_node_predicate(
            ref_id=ref_id,
            group=group,
            node_key=node_key,
            record=record,
            version=version,
        )

    def readonly_sql(
        self,
        *,
        reason: str,
        sql: str,
        params: dict[str, Any] | None = None,
        max_rows: int = 200,
        timeout_ms: int = 5000,
    ) -> dict[str, Any]:
        return self.database.raw_query(
            reason=reason,
            sql=sql,
            params=params,
            max_rows=max_rows,
            timeout_ms=timeout_ms,
        )
