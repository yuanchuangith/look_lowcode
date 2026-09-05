from __future__ import annotations

import re
from typing import Any

from .source_lex import LexedSource, Token, expression_end, split_arguments, string_value


ROUTE = re.compile(r"/(?:api|gxp2)(?:/[^\s'\";]*)?", re.IGNORECASE)
IDENTIFIER = re.compile(r"^[A-Za-z_$][\w$]*$")


def _assigned_name(tokens: list[Token], start: int) -> str | None:
    if start and tokens[start - 1].value == "async":
        start -= 1
    if start > 1 and tokens[start - 1].value in ("=", ":") and IDENTIFIER.fullmatch(tokens[start - 2].value):
        return tokens[start - 2].value
    return None


def function_scopes(lexed: LexedSource) -> list[dict[str, Any]]:
    tokens, pairs = lexed.tokens, lexed.pairs
    scopes = []
    seen = set()
    for index, token in enumerate(tokens):
        name = None
        body = None
        start = index
        if token.value == "function":
            cursor = index + 1
            if cursor < len(tokens) and tokens[cursor].value == "*":
                cursor += 1
            if cursor < len(tokens) and IDENTIFIER.fullmatch(tokens[cursor].value):
                name = tokens[cursor].value
            else:
                name = _assigned_name(tokens, index)
            while cursor < min(len(tokens), index + 30) and tokens[cursor].value != "(":
                cursor += 1
            if cursor in pairs:
                body = pairs[cursor] + 1
                while body < min(len(tokens), pairs[cursor] + 40) and tokens[body].value not in ("{", ";", "=>"):
                    body += 1
        elif token.value == "=>" and index:
            start = pairs.get(index - 1, index - 1) if tokens[index - 1].value == ")" else index - 1
            name = _assigned_name(tokens, start)
            body = index + 1
        elif token.value == "(" and index and index in pairs:
            previous = tokens[index - 1]
            candidate = pairs[index] + 1
            if IDENTIFIER.fullmatch(previous.value) and previous.value not in {"if", "for", "while", "switch", "catch", "with", "function"} and candidate < len(tokens) and tokens[candidate].value == "{":
                name = previous.value
                body = candidate
                start = index - 1
        if body is None or body >= len(tokens) or body in seen:
            continue
        if tokens[body].value == "{":
            if body not in pairs:
                continue
            end = pairs[body] + 1
        elif token.value == "=>":
            end = expression_end(tokens, pairs, body)
        else:
            continue
        seen.add(body)
        scopes.append({"name": name, "start": start, "body": body, "end": end})
    return scopes


def _write_names(tokens: list[Token], pairs: dict[int, int], begin: int, end: int) -> list[str]:
    while begin < end and tokens[begin].value == "(" and pairs.get(begin) == end - 1:
        begin += 1
        end -= 1
    if end == begin + 1 and IDENTIFIER.fullmatch(tokens[begin].value):
        return [tokens[begin].value]
    if begin >= end or tokens[begin].value not in ("[", "{") or pairs.get(begin) != end - 1:
        return []
    return [token.value for index, token in enumerate(tokens[begin + 1:end - 1], begin + 1)
            if token.kind == "code" and IDENTIFIER.fullmatch(token.value)
            and tokens[index - 1].value not in (".", "?.") and tokens[index + 1].value != ":"]


def _url_writes(lexed: LexedSource, scopes, owners, block_paths):
    tokens, pairs = lexed.tokens, lexed.pairs
    declarations = {}
    events = {}

    def declare(name, position, scope_path, owner):
        declaration = {"name": name, "position": position, "path": scope_path, "owner": owner}
        declarations.setdefault(name, []).append(declaration)

    for scope in scopes:
        opening = next((index for index in range(scope["start"], scope["body"]) if tokens[index].value == "(" and index in pairs), None)
        parameter_path = block_paths[scope["body"]] + ((scope["body"],) if tokens[scope["body"]].value == "{" else ())
        if opening is not None:
            for begin, end in split_arguments(tokens, pairs, opening + 1, pairs[opening]):
                while begin < end and tokens[begin].value == ".":
                    begin += 1
                if begin >= end:
                    continue
                if tokens[begin].value in ("[", "{"):
                    names = _write_names(tokens, pairs, begin, pairs.get(begin, begin) + 1)
                else:
                    names = [tokens[begin].value] if IDENTIFIER.fullmatch(tokens[begin].value) else []
                for name in names:
                    declare(name, scope["body"], parameter_path, scope)
        elif tokens[scope["start"]].kind == "code" and IDENTIFIER.fullmatch(tokens[scope["start"]].value):
            declare(tokens[scope["start"]].value, scope["body"], parameter_path, scope)
    for index, token in enumerate(tokens):
        if token.kind != "code" or token.value not in ("let", "const", "var"):
            continue
        cursor = index + 1
        while cursor < len(tokens):
            end = pairs.get(cursor, cursor) + 1 if tokens[cursor].value in ("[", "{") else cursor + 1
            scope_path = block_paths[index]
            owner = owners[index]
            if token.value == "var" and owner:
                scope_path = block_paths[owner["body"]] + (owner["body"],)
            for name in _write_names(tokens, pairs, cursor, end):
                declare(name, cursor, scope_path, owner)
            cursor = end
            while cursor < len(tokens) and tokens[cursor].value not in ("=", ",", ";", "in", "of", ")", "}"):
                cursor += 1
            if cursor < len(tokens) and tokens[cursor].value == "=":
                cursor = expression_end(tokens, pairs, cursor + 1)
            if cursor >= len(tokens) or tokens[cursor].value != ",":
                break
            cursor += 1

    def binding(name, at):
        matches = [item for item in declarations.get(name, []) if block_paths[at][:len(item["path"])] == item["path"]
                   and (item["owner"] is None or item["owner"]["body"] <= at < item["owner"]["end"])]
        if not matches:
            return None
        return max(matches, key=lambda item: (len(item["path"]), item["position"]))

    operators = {"=", "+=", "-=", "*=", "**=", "/=", "%=", "<<=", ">>=", ">>>=", "|=", "&=", "^=", "||=", "&&=", "??=", "++", "--", "in", "of"}
    for index, token in enumerate(tokens):
        if token.kind != "code" or token.value not in operators:
            continue
        begin, end = index - 1, index
        if begin >= 0 and tokens[begin].value in (")", "]", "}"):
            begin = pairs.get(begin, begin)
            if begin and tokens[begin].value == "[" and IDENTIFIER.fullmatch(tokens[begin - 1].value):
                continue
        if token.value in ("++", "--") and (begin < 0 or not IDENTIFIER.fullmatch(tokens[begin].value)):
            begin, end = index + 1, index + 2
        if begin < 0 or end > len(tokens) or begin and tokens[begin - 1].value in (".", "?."):
            continue
        if token.value in ("++", "--") and end < len(tokens) and tokens[end].value in (".", "?.", "["):
            continue
        for name in _write_names(tokens, pairs, begin, end):
            target = binding(name, index)
            if target is not None:
                events.setdefault((target["position"], name), []).append({"at": index, "begin": index + 1, "end": expression_end(tokens, pairs, index + 1), "operator": token.value, "owner": owners[index]})

    def values(name, at):
        target = binding(name, at)
        if target is None or target["position"] > at:
            return []
        return [item for item in events.get((target["position"], name), []) if item["at"] < at or item["owner"] is not target["owner"]]

    return values


def _query_append(lexed: LexedSource, begin: int, end: int, route: str) -> bool:
    tokens, pairs = lexed.tokens, lexed.pairs
    while begin < end and tokens[begin].value == "(" and pairs.get(begin) == end - 1:
        begin += 1
        end -= 1
    if begin >= end or tokens[begin].kind != "string":
        return False
    if begin + 1 < end and tokens[begin + 1].value != "+":
        return False
    prefix = string_value(tokens[begin])
    if not prefix.startswith(("?", "#")) and not (prefix.startswith("&") and "?" in route):
        return False
    cursor = begin + 1
    while cursor < end:
        token = tokens[cursor]
        if token.value in ("(", "[") and cursor in pairs:
            cursor = pairs[cursor] + 1
            continue
        if token.kind != "string" and not IDENTIFIER.fullmatch(token.value) and not token.value.replace(".", "", 1).isdigit() and token.value not in ("+", ".", "?."):
            return False
        cursor += 1
    return True


def scan_requests(lexed: LexedSource, relative: str) -> dict[str, Any]:
    tokens, pairs = lexed.tokens, lexed.pairs
    scopes = function_scopes(lexed)
    owners = [None] * len(tokens)
    for scope in sorted(scopes, key=lambda item: item["end"] - item["body"], reverse=True):
        for index in range(scope["body"], scope["end"]):
            owners[index] = scope
    block_paths = []
    active_blocks = []
    for index, token in enumerate(tokens):
        if token.kind == "code" and token.value == "}" and active_blocks:
            active_blocks.pop()
        block_paths.append(tuple(active_blocks))
        if token.kind == "code" and token.value == "{":
            active_blocks.append(index)
    assigned_values = _url_writes(lexed, scopes, owners, block_paths)

    def resolve(begin: int, end: int, at: int, owner: dict[str, Any] | None, depth: int = 0):
        if depth > 5 or begin >= end:
            return None
        while begin < end and tokens[begin].value == "(" and pairs.get(begin) == end - 1:
            begin += 1
            end -= 1
        if end == begin + 1 and IDENTIFIER.fullmatch(tokens[begin].value):
            values = assigned_values(tokens[begin].value, at)
            if not values or values[0]["operator"] != "=":
                return None
            initial = values[0]
            resolved = resolve(initial["begin"], initial["end"], initial["at"], owner, depth + 1)
            if resolved is None:
                return None
            route, origin, dynamic, query_dynamic = resolved
            for write in values[1:]:
                if write["operator"] != "+=" or not _query_append(lexed, write["begin"], write["end"], route):
                    return None
                dynamic, query_dynamic = True, True
                if "?" not in route:
                    route += "?"
            return route.split("?", 1)[0] if len(values) > 1 else route, origin, dynamic, query_dynamic
        fragments = []
        unknown_after_route = False
        origin = None
        pending_plus = False
        for token in tokens[begin:end]:
            if token.value in ("(", ")"):
                continue
            if token.value == "+":
                pending_plus = True
                continue
            if token.kind == "string":
                value = string_value(token)
                if fragments and not pending_plus:
                    return None
                if origin is None and ROUTE.search(value):
                    origin = token
                fragments.append(value)
                pending_plus = False
            elif IDENTIFIER.fullmatch(token.value) or token.value in (".", "?."):
                if origin is not None:
                    unknown_after_route = True
            else:
                return None
        if origin is None or unknown_after_route:
            return None
        text = "".join(fragments)
        route = ROUTE.search(text)
        if route is None:
            return None
        return route.group(), origin, "$" + "{" in route.group(), "$" + "{" in route.group().partition("?")[2]

    requests = []
    call_edges = []
    symbols = [{"name": scope["name"], "path": relative, "line": lexed.line(tokens[scope["start"]].start), "kind": "function"} for scope in scopes if scope["name"]]
    for index, token in enumerate(tokens):
        if token.value != "request" or index + 3 >= len(tokens):
            continue
        if tokens[index + 1].value not in (".", "?.") or tokens[index + 2].value not in {"get", "post", "put", "delete", "patch"}:
            continue
        opening = index + 3
        if tokens[opening].value != "(" or opening not in pairs:
            continue
        arguments = split_arguments(tokens, pairs, opening + 1, pairs[opening])
        if not arguments:
            continue
        owner = owners[index]
        resolved = resolve(*arguments[0], index, owner)
        if resolved is None:
            continue
        route, origin, dynamic, query_dynamic = resolved
        name = owner["name"] if owner else None
        requests.append({"route": route, "method": tokens[index + 2].value.upper(), "function": name,
                         "path": relative, "line": lexed.line(origin.start), "call_line": lexed.line(token.start),
                         "dynamic": dynamic, "query_dynamic": query_dynamic,
                         "path_confidence": "candidate" if "$" + "{" in route.split("?", 1)[0] else "structural", "wrapper": "@inbiz/utils" if "@inbiz/utils" in lexed.clean else "unresolved",
                         "confidence": "candidate" if dynamic or lexed.errors else "structural"})
        if name:
            call_edges.append({"layer": "frontend", "caller": name, "callee": f"request.{tokens[index + 2].value}", "path": relative, "line": lexed.line(token.start)})
    candidates = [{"route": match.group(), "path": relative, "line": lexed.line(token.start), "confidence": "candidate"}
                  for token in lexed.strings if (match := ROUTE.search(string_value(token))) is not None]
    return {"requests": requests, "symbols": symbols, "call_edges": call_edges, "route_candidates": candidates}


def component_registrations(lexed: LexedSource, relative: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tokens, pairs = lexed.tokens, lexed.pairs
    calls = [(index + 1, pairs[index + 1]) for index, token in enumerate(tokens[:-1])
             if token.value == "createBehavior" and tokens[index + 1].value == "(" and index + 1 in pairs]
    names, selectors = [], []
    for index, token in enumerate(tokens):
        if token.value == "name" and index + 2 < len(tokens) and tokens[index + 1].value == ":" and tokens[index + 2].kind == "string" and any(start < index < end for start, end in calls):
            names.append({"value": string_value(tokens[index + 2]), "path": relative, "line": lexed.line(token.start)})
        if token.kind == "string" and string_value(token) == "x-component":
            for cursor in range(index + 1, min(index + 7, len(tokens) - 1)):
                if tokens[cursor].value in (":", "===", "==") and tokens[cursor + 1].kind == "string":
                    selectors.append({"value": string_value(tokens[cursor + 1]), "path": relative, "line": lexed.line(token.start)})
                    break
    return names, selectors
