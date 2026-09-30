from __future__ import annotations

import time
from collections import deque

from .business_graph_model import DATA_KINDS
from .business_logic_graph import GraphValidationError, _digest


def project(edges: list[dict], projection: str) -> list[dict]:
    if projection not in {"business", "data"}:
        raise GraphValidationError("GRAPH_INVALID_PROJECTION")
    if projection == "business":
        return edges
    return [edge for edge in edges if edge["kind"] in DATA_KINDS
            or edge["kind"] == "calls" and edge.get("data_binding", False)]


def adjacency(nodes: list[dict], edges: list[dict], reverse: bool = False, undirected: bool = False) -> dict:
    result = {node["id"]: [] for node in nodes}
    for edge in edges:
        source, target = (edge["target"], edge["source"]) if reverse else (edge["source"], edge["target"])
        if source in result and target in result:
            result[source].append((target, edge["id"]))
            if undirected:
                result[target].append((source, edge["id"]))
    for neighbors in result.values():
        neighbors.sort()
    return result


def neighborhood(nodes: list[dict], edges: list[dict], seeds: list[str], depth: int,
                 max_nodes: int = 200, max_edges: int = 400, edge_cursor: str | None = None) -> tuple[list, list, list, bool]:
    if type(depth) is not int or not 0 <= depth <= 5:
        raise GraphValidationError("GRAPH_INVALID_DEPTH")
    known = {node["id"]: node for node in nodes}
    links = adjacency(nodes, edges, undirected=True)
    selected, frontier = set(), set()
    queue = deque((seed, 0) for seed in sorted(set(seeds)) if seed in known)
    while queue:
        current, distance = queue.popleft()
        if current in selected:
            continue
        if len(selected) >= max_nodes:
            frontier.add(current)
            continue
        selected.add(current)
        neighbors = links[current]
        if distance < depth:
            queue.extend((neighbor, distance + 1) for neighbor, _ in neighbors if neighbor not in selected)
        else:
            frontier.update(neighbor for neighbor, _ in neighbors if neighbor not in selected)
    selected_edges = [edge for edge in edges if edge["source"] in selected and edge["target"] in selected
                      and (edge_cursor is None or edge["id"] > edge_cursor)]
    limited = len(selected_edges) > max_edges
    edge_frontier = set()
    if limited:
        edge_frontier.update(edge[key] for edge in selected_edges[max_edges:] for key in ("source", "target"))
    return ([known[key] for key in sorted(selected)], selected_edges[:max_edges], sorted((frontier - selected) | edge_frontier),
            limited or bool(frontier - selected))


def components(nodes: list[dict], edges: list[dict]) -> list[list[str]]:
    links = adjacency(nodes, edges, undirected=True)
    remaining, result = set(links), []
    while remaining:
        root = min(remaining)
        pending, found = [root], set()
        while pending:
            current = pending.pop()
            if current in found:
                continue
            found.add(current)
            pending.extend(neighbor for neighbor, _ in links[current] if neighbor not in found)
        remaining.difference_update(found)
        result.append(sorted(found))
    return result


def strongly_connected(nodes: list[dict], edges: list[dict]) -> list[list[str]]:
    links = adjacency(nodes, edges)
    reverse = adjacency(nodes, edges, reverse=True)
    seen, order = set(), []
    for root in sorted(links):
        if root in seen:
            continue
        pending = [(root, False)]
        while pending:
            current, finished = pending.pop()
            if finished:
                order.append(current)
                continue
            if current in seen:
                continue
            seen.add(current)
            pending.append((current, True))
            pending.extend((neighbor, False) for neighbor, _ in reversed(links[current]) if neighbor not in seen)
    seen, result = set(), []
    for root in reversed(order):
        if root in seen:
            continue
        pending, found = [root], []
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            found.append(current)
            pending.extend(neighbor for neighbor, _ in reverse[current] if neighbor not in seen)
        result.append(sorted(found))
    return sorted(result)


def condensation(groups: list[list[str]], edges: list[dict]) -> dict:
    membership = {entity_id: index for index, group in enumerate(groups) for entity_id in group}
    pairs = sorted({(membership[edge["source"]], membership[edge["target"]]) for edge in edges
                    if membership[edge["source"]] != membership[edge["target"]]})
    identifiers = {index: _digest(["scc", group]) for index, group in enumerate(groups)}
    return {"nodes": [{"id": identifiers[index], "members": group,
                       "label": f"SCC {index} ({len(group)})"} for index, group in enumerate(groups)],
            "edges": [{"id": _digest([identifiers[source], identifiers[target]]),
                       "source": identifiers[source], "target": identifiers[target], "label": "flows_to"}
                      for source, target in pairs]}


def paths(nodes: list[dict], edges: list[dict], start: str, target: str | None = None,
          direction: str = "downstream", max_depth: int = 8, max_paths: int = 5) -> dict:
    if (direction not in {"upstream", "downstream"} or type(max_depth) is not int
            or not 1 <= max_depth <= 20 or type(max_paths) is not int or not 1 <= max_paths <= 5):
        raise GraphValidationError("GRAPH_INVALID_PATH_QUERY")
    known = {node["id"] for node in nodes}
    if start not in known or target is not None and target not in known:
        return {"paths": [], "frontier": [], "truncated": False, "status": "not_found"}
    links = adjacency(nodes, edges, reverse=direction == "upstream")
    queue = deque([([start], [])])
    result, frontier = [], set()
    visits, deadline = 0, time.monotonic() + 5
    while queue and len(result) < max_paths and visits < 5000 and time.monotonic() < deadline:
        entity_path, edge_path = queue.popleft()
        visits += 1
        current = entity_path[-1]
        if target == current:
            result.append({"entities": entity_path, "edges": edge_path, "cycle": False})
            continue
        neighbors = links[current]
        if not neighbors:
            if target is None:
                result.append({"entities": entity_path, "edges": edge_path, "cycle": False})
            continue
        if len(edge_path) >= max_depth:
            frontier.add(current)
            continue
        for neighbor, edge_id in neighbors:
            if neighbor in entity_path:
                if target is None and len(result) < max_paths:
                    result.append({"entities": entity_path + [neighbor], "edges": edge_path + [edge_id], "cycle": True})
                continue
            queue.append((entity_path + [neighbor], edge_path + [edge_id]))
    frontier.update(item[0][-1] for item in queue)
    return {"paths": result, "frontier": sorted(frontier), "truncated": bool(frontier),
            "status": "ok", "path_semantics": "static_possible_not_runtime_execution"}
