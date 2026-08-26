from __future__ import annotations

import json
import re
from typing import Any, Iterable


MAX_HINT_BYTES = 4 * 1024
MAX_EXACT_TERMS = 8
MAX_PAIRED_TERMS = 4
MAX_ANCHOR_VALUES = 8
MAX_VALUE_LENGTH = 160

BACKEND_STACK_FRAME = re.compile(
    r"\bat\s+(?P<type>GxP2(?:\.[A-Za-z_]\w*)+)\.(?P<method>[A-Za-z_]\w*)\s*\(",
    re.IGNORECASE,
)
FRONTEND_STACK_FILE = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?[^\s()]+?\.(?:tsx?|jsx?|vue))(?::\d+){1,2}",
    re.IGNORECASE,
)
API_ROUTE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<route>/(?:api|gxp2)(?:/[A-Za-z0-9_.{}:-]+)+)",
    re.IGNORECASE,
)
SERVICE_SYMBOL = re.compile(
    r"\b(?P<symbol>(?:GxP2\.)?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*"
    r"(?:Controller|Service|ServiceBase)(?:\.[A-Za-z_]\w*)?)\b"
)


def _clean(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:MAX_VALUE_LENGTH]


def _unique(values: Iterable[Any], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _source_searchable(value: Any) -> str:
    cleaned = _clean(value)
    if len(cleaned) < 2 or len(cleaned) > 100:
        return ""
    compact = cleaned.replace("-", "")
    if len(compact) >= 24 and re.fullmatch(r"[0-9a-fA-F]+", compact):
        return ""
    return cleaned


def _symbol_source_terms(symbols: Iterable[str]) -> list[str]:
    terms: list[str] = []
    for symbol in symbols:
        parts = [part for part in re.split(r"[.:]", symbol) if part]
        for index, part in enumerate(parts):
            if re.search(r"(?:Controller|Service|ServiceBase)$", part):
                terms.append(part)
                if index + 1 < len(parts):
                    terms.append(parts[index + 1])
                break
    return terms


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _values_for_keys(value: Any, keys: set[str]) -> list[str]:
    result: list[str] = []
    for key, item in _walk(value):
        if key.lower() not in keys:
            continue
        if isinstance(item, list):
            result.extend(_clean(part) for part in item)
        elif isinstance(item, dict):
            for nested_key in ("code", "value", "name", "label"):
                if item.get(nested_key) not in (None, ""):
                    result.append(_clean(item[nested_key]))
                    break
        else:
            result.append(_clean(item))
    return result


def _structured_pairs(value: Any) -> list[list[str]]:
    pairs: list[list[str]] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(first: Any, second: Any) -> None:
        left = _source_searchable(first)
        right = _source_searchable(second)
        if not left or not right or left.casefold() == right.casefold():
            return
        key = tuple(sorted((left.casefold(), right.casefold())))
        if key in seen or len(pairs) >= MAX_PAIRED_TERMS:
            return
        seen.add(key)
        pairs.append([left, right])

    def visit(item: Any) -> None:
        if len(pairs) >= MAX_PAIRED_TERMS:
            return
        if isinstance(item, dict):
            filters = item.get("filters")
            if isinstance(filters, list):
                group_fields: list[str] = []
                for filter_item in filters:
                    if not isinstance(filter_item, dict):
                        continue
                    field = _source_searchable(filter_item.get("field"))
                    expression = _source_searchable(filter_item.get("expression"))
                    if field:
                        group_fields.append(field)
                    add_pair(field, expression)
                group_fields = _unique(group_fields, limit=8)
                for index, first in enumerate(group_fields):
                    for second in group_fields[index + 1 :]:
                        add_pair(first, second)
                        if len(pairs) >= MAX_PAIRED_TERMS:
                            return
            for collection_key in ("field_mappings", "call_parameters"):
                collection = item.get(collection_key)
                if not isinstance(collection, list):
                    continue
                for row in collection:
                    if not isinstance(row, dict):
                        continue
                    left = row.get("field") or row.get("name")
                    add_pair(left, row.get("expression"))
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return pairs


def _component_from_nodes(nodes: list[dict[str, Any]]) -> dict[str, str]:
    for node in nodes:
        component = (node.get("facts") or {}).get("component")
        if isinstance(component, dict) and any(component.values()):
            return {
                key: _clean(component.get(key))
                for key in ("component_key", "component_type", "model_key", "label")
                if _clean(component.get(key))
            }
    return {}


def _base_anchors(
    action: dict[str, Any] | None,
    design: dict[str, Any] | None,
) -> dict[str, Any]:
    anchors: dict[str, Any] = {}
    action = action or {}
    design = design or {}
    for target, source in (
        ("action_code", "action_code"),
        ("ref_id", "ref_id"),
        ("action_name", "action_name"),
    ):
        value = _clean(action.get(source))
        if value:
            anchors[target] = value
    for target, source in (("design_id", "design_id"), ("version", "version")):
        value = _clean(design.get(source))
        if value:
            anchors[target] = value
    return anchors


def _bounded_hints(hints: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(hints, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) <= MAX_HINT_BYTES:
        return hints

    hints["truncated"] = True
    for key in ("paired_terms", "exact_terms"):
        values = hints.get(key) or []
        while values and len(
            json.dumps(hints, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ) > MAX_HINT_BYTES:
            values.pop()
    anchors = hints.get("anchors") or {}
    for key in ("service_symbols", "api_routes", "called_actions", "fields", "tables"):
        anchors.pop(key, None)
        if len(
            json.dumps(hints, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ) <= MAX_HINT_BYTES:
            break
    return hints


def build_source_hints(
    *,
    action: dict[str, Any] | None = None,
    design: dict[str, Any] | None = None,
    nodes: list[dict[str, Any]] | None = None,
    component_filters: dict[str, Any] | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    nodes = nodes or []
    component_filters = component_filters or {}
    text = text or ""
    anchors = _base_anchors(action, design)
    candidate_layers: list[str] = []
    reason_codes: list[str] = []
    exact_terms: list[str] = []

    component = component_filters.get("component") or _component_from_nodes(nodes)
    if isinstance(component, dict) and any(component.values()):
        for key in ("component_key", "component_type", "model_key", "label"):
            value = _clean(component.get(key))
            if value:
                anchors[key] = value
        candidate_layers.append("frontend")
        reason_codes.append("component_identity")
        exact_terms.extend(
            _source_searchable(component.get(key))
            for key in ("component_type", "component_key", "model_key")
        )

    combined: list[Any] = [node.get("facts") or {} for node in nodes]
    combined.append(component_filters)
    api_routes = _unique(
        [
            *_values_for_keys(combined, {"api_routes", "api_route", "route", "endpoint", "url"}),
            *(match.group("route") for match in API_ROUTE.finditer(text)),
        ],
        limit=MAX_ANCHOR_VALUES,
    )
    service_symbols = _unique(
        [
            *_values_for_keys(
                combined,
                {"service_symbols", "service_symbol", "service", "controller", "class_name", "method_name"},
            ),
            *(match.group("symbol") for match in SERVICE_SYMBOL.finditer(text)),
        ],
        limit=MAX_ANCHOR_VALUES,
    )

    backend_frames = []
    for match in BACKEND_STACK_FRAME.finditer(text):
        symbol = f"{match.group('type')}.{match.group('method')}"
        backend_frames.append(symbol)
    backend_frames = _unique(backend_frames, limit=MAX_ANCHOR_VALUES)
    if backend_frames:
        candidate_layers.append("backend")
        reason_codes.append("backend_stack_frame")
        service_symbols = _unique([*backend_frames, *service_symbols], limit=MAX_ANCHOR_VALUES)
    if api_routes:
        candidate_layers.append("backend")
        reason_codes.append("api_route")
        exact_terms.extend(api_routes)
    if service_symbols:
        candidate_layers.append("backend")
        reason_codes.append("backend_service_symbol")
        exact_terms.extend(_symbol_source_terms(service_symbols))

    frontend_files = _unique(
        (match.group("path").replace("\\", "/") for match in FRONTEND_STACK_FILE.finditer(text)),
        limit=MAX_ANCHOR_VALUES,
    )
    if frontend_files:
        candidate_layers.append("frontend")
        reason_codes.append("frontend_stack_frame")
        exact_terms.extend(path.rsplit("/", 1)[-1] for path in frontend_files)

    fields = _unique(
        _values_for_keys(combined, {"field", "fields", "attribute", "target_field"}),
        limit=MAX_ANCHOR_VALUES,
    )
    tables = _unique(
        _values_for_keys(combined, {"model_or_table", "table", "tables"}),
        limit=MAX_ANCHOR_VALUES,
    )
    called_actions = []
    for value in _values_for_keys(combined, {"called_action"}):
        called_actions.append(value)
    for node in nodes:
        called = (node.get("facts") or {}).get("called_action") or {}
        if isinstance(called, dict):
            called_actions.extend(called.get(key) for key in ("code", "id", "name"))
    called_actions = _unique(called_actions, limit=MAX_ANCHOR_VALUES)

    for key, values in (
        ("fields", fields),
        ("tables", tables),
        ("called_actions", called_actions),
        ("api_routes", api_routes),
        ("service_symbols", service_symbols),
        ("frontend_files", frontend_files),
    ):
        if values:
            anchors[key] = values

    candidate_layers = _unique(candidate_layers, limit=2)
    if len(candidate_layers) == 2:
        reason_codes.append("request_contract_cross_layer")
    hints = {
        "candidate_layers": candidate_layers,
        "reason_codes": _unique(reason_codes, limit=8),
        "anchors": anchors,
        "exact_terms": _unique(exact_terms, limit=MAX_EXACT_TERMS),
        "paired_terms": _structured_pairs(combined),
        "confidence": (
            "high"
            if backend_frames or api_routes or _clean(component.get("component_type"))
            else "medium"
            if candidate_layers
            else "low"
        ),
    }
    return _bounded_hints(hints)
