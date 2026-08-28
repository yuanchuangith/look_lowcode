from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from mcp.server.fastmcp import FastMCP

from gxp_core.service import GxpReadonlyService
from gxp_core.cpm_snapshot import (
    cpm_snapshot_status,
    refresh_cpm_snapshot,
    search_platform_snapshot,
    inspect_page_snapshot,
    get_cpm_knowledge,
)


def service() -> GxpReadonlyService:
    return GxpReadonlyService()


def connection_status() -> dict[str, Any]:
    """Check whether external configuration and the read-only database connection work."""
    return GxpReadonlyService.connection_status()


def resolve_action(identifier: str) -> dict[str, Any]:
    """Resolve an exact action code/RefId, falling back to an action-name search."""
    return service().resolve_action(identifier)


def search_actions(query: str, limit: int = 20) -> dict[str, Any]:
    """Search public/form actions by business name, code or RefId."""
    return service().search_actions(query, limit=limit)


def search_pages(query: str, limit: int = 20) -> dict[str, Any]:
    """Find active GXP pages by Route/Id/OutId, localized name or bounded Chinese similarity."""
    return service().search_pages(query, limit=limit)


def list_page_actions(page_identifier: str, limit: int = 50) -> dict[str, Any]:
    """List every active form action belonging to one exact page Route, Id or OutId."""
    return service().list_page_actions(page_identifier, limit=limit)


def get_design_versions(
    ref_id: str,
    include_deleted: bool = False,
    include_history: bool = False,
) -> dict[str, Any]:
    """Return the editable draft/runtime published copies and optional published history.

    Draft and published are two copies of the same action. Saving the draft does not affect
    runtime; only publication changes the runtime published copy. Use history only when tracing
    a past runtime exception.
    """
    return service().get_design_versions(
        ref_id,
        include_deleted=include_deleted,
        include_history=include_history,
    )


def inspect_action(
    identifier: str,
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
    """Inspect compact node facts; opt in to params/C# only after narrowing the location."""
    return service().inspect_action(
        identifier,
        version=version,
        group=group,
        terms=terms,
        node_key=node_key,
        start=start,
        end=end,
        include_params=include_params,
        csharp_line=csharp_line,
        csharp_context=csharp_context,
        design_id=design_id,
        at_time=at_time,
        focus_fields=focus_fields,
        include_generated_csharp=include_generated_csharp,
        max_nodes=max_nodes,
    )


def inspect_component_filters(
    identifier: str,
    component: str,
    version: str = "published",
    include_params: bool = False,
    design_id: str | None = None,
    at_time: str | None = None,
) -> dict[str, Any]:
    """Inspect every DataFilter writer for one component across all action groups, without C#."""
    return service().inspect_component_filters(
        identifier,
        component,
        version=version,
        include_params=include_params,
        design_id=design_id,
        at_time=at_time,
    )


def compare_designs(ref_id: str) -> dict[str, Any]:
    """Check whether the editable draft has unpublished changes versus the runtime copy."""
    return service().compare_designs(ref_id)


def trace_dynamic_exception(
    text: str, at_time: str | None = None, context_lines: int = 4
) -> dict[str, Any]:
    """Trace a generated GXP C# stack frame to action history, calls and canvas nodes."""
    return service().trace_dynamic_exception(
        text, at_time=at_time, context_lines=context_lines
    )


def diagnose_codex_input(text: str, at_time: str | None = None) -> dict[str, Any]:
    """Accept raw Codex natural-language or stack-trace input and route the diagnosis."""
    return service().diagnose_codex_input(text, at_time=at_time)


def describe_table(table: str) -> dict[str, Any]:
    """Return columns and indexes before querying a business table."""
    return service().describe_table(table)


def get_records(
    table: str,
    filters: list[dict[str, Any]],
    columns: list[str] | None = None,
    order_by: str | None = None,
    descending: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """Read narrowly filtered business records with structured operators and a hard limit."""
    return service().get_records(
        table,
        filters=filters,
        columns=columns,
        order_by=order_by,
        descending=descending,
        limit=limit,
    )


def evaluate_node_predicate(
    ref_id: str,
    group: str,
    node_key: str,
    record: dict[str, Any],
    version: str = "published",
) -> dict[str, Any]:
    """Evaluate literal parts of one canvas node predicate against a supplied record."""
    return service().evaluate_node_predicate(
        ref_id=ref_id,
        group=group,
        node_key=node_key,
        record=record,
        version=version,
    )


def readonly_sql(
    reason: str,
    sql: str,
    params: dict[str, Any] | None = None,
    max_rows: int = 200,
    timeout_ms: int = 5000,
) -> dict[str, Any]:
    """Run one AST-validated read-only SQL statement when structured tools are insufficient."""
    return service().readonly_sql(
        reason=reason,
        sql=sql,
        params=params,
        max_rows=max_rows,
        timeout_ms=timeout_ms,
    )


MCP_TOOLS = (
    connection_status,
    resolve_action,
    search_actions,
    search_pages,
    list_page_actions,
    get_design_versions,
    inspect_action,
    inspect_component_filters,
    compare_designs,
    trace_dynamic_exception,
    diagnose_codex_input,
    describe_table,
    get_records,
    evaluate_node_predicate,
    readonly_sql,
)

LOCAL_CPM_TOOLS = (
    cpm_snapshot_status,
    refresh_cpm_snapshot,
    search_platform_snapshot,
    inspect_page_snapshot,
    get_cpm_knowledge,
)


def create_mcp(*, include_local_cpm: bool = True, **settings: Any) -> FastMCP:
    """Create one transport-specific MCP instance over the shared read-only tools."""
    app = FastMCP(
        "gxp-lowcode-readonly",
        instructions=(
            "Read-only GXP low-code diagnosis. Use structured tools before readonly_sql. "
            "Never request or expose database credentials. Draft and published are two copies "
            "of the same action: draft edits do not affect runtime; only the published copy runs. "
            "Lock the current/expected/no-match business rule before judging correctness. Start "
            "with compact facts; opt in to full params or generated C# only after narrowing."
        ),
        **settings,
    )
    for tool in MCP_TOOLS:
        app.tool()(tool)
    if include_local_cpm:
        for tool in LOCAL_CPM_TOOLS:
            app.tool()(tool)
    return app


# Backward-compatible stdio object used by existing Claude/Codex registrations.
mcp = create_mcp()


if __name__ == "__main__":
    mcp.run(transport="stdio")
