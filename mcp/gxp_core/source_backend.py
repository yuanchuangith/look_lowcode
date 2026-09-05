from __future__ import annotations

import bisect
import re
from pathlib import Path
from typing import Any

from .source_lex import LexedSource, expression_end, split_arguments


TYPE = re.compile(r"\b(class|interface|struct)\s+(\w+)(?:\s*<[^>{}]+>)?\s*(?::\s*([^{}]+))?\s*\{")
NAMESPACE = re.compile(r"\bnamespace\s+([\w.]+)\s*[{;]")
USING = re.compile(r"\busing\s+(?!var\b|static\b)([\w.]+)\s*;")
MEMBER = re.compile(r"(?:^|[;{}])\s*(?:(?:public|protected|private|internal|static|virtual|override|abstract|async|sealed|new|partial|extern|readonly)\s+)*(?P<return>[\w.]+(?:\s*<[^;{}()]+>)?(?:\[\])?\??)\s+(?P<name>\w+)(?:<[^;{}()]+>)?\s*\(", re.MULTILINE)
FIELD = re.compile(r"\b(?:public|protected|private|internal)\s+(?:(?:static|readonly|volatile|new)\s+)*(?P<type>[\w.]+(?:<[^;{}()]+>)?(?:\[\])?\??)\s+(?P<name>\w+)\s*(?:[;=]|\{\s*get\b)")
LOCAL = re.compile(r"\b(?P<type>[\w.]+(?:<[^;{}()]+>)?(?:\[\])?\??)\s+(?P<name>\w+)\s*=")
CALL = re.compile(r"(?P<receiver>(?:this\.)?\b\w+)\s*(?:\?\.|\.)\s*(?P<name>\w+)(?:\s*<[^;{}()]+>)?\s*\(")
ASSIGNMENT = re.compile(r"(?<![\w.])(?P<name>\w+)\s*=(?!=)")
BARE_CALL = re.compile(r"(?<![\w.])(?P<name>\w+)\s*\(")
ROUTE_ATTRIBUTE = re.compile(r'\bRoute\s*\(\s*"([^"\r\n]*)"\s*\)')
HTTP_ATTRIBUTE = re.compile(r'\bHttp(Get|Post|Put|Delete|Patch|Head|Options)(?:\s*\(\s*"([^"\r\n]*)"\s*\))?')
PRIMITIVES = {"string", "bool", "int", "long", "short", "byte", "decimal", "double", "float", "object", "void", "char"}


def plain_type(value: str) -> str:
    return re.sub(r"<.*>|\[\]|\?", "", value).strip()


def _parameters(lexed: LexedSource, opening: int, closing: int) -> list[dict[str, Any]]:
    result = []
    for begin, end in split_arguments(lexed.tokens, lexed.pairs, opening + 1, closing):
        if begin >= end:
            continue
        text = lexed.clean[lexed.tokens[begin].start:lexed.tokens[end - 1].end]
        text = re.sub(r"\[[^\]]*\]", "", text).strip()
        matched = re.match(r"(?:(?:ref|out|in|params|this)\s+)*([\w.]+(?:\s*<[^=]+>)?(?:\[\])?\??)\s+(\w+)\s*(=.*)?$", text, re.DOTALL)
        if matched:
            result.append({"name": matched.group(2), "type": re.sub(r"\s+", "", matched.group(1)), "optional": matched.group(3) is not None})
    return result


def parse_backend_file(text: str, relative: str) -> tuple[dict[str, Any], LexedSource]:
    lexed = LexedSource(text, language="csharp")
    positions = None
    braces = {}
    stack = []
    for brace in re.finditer(r"[{}]", lexed.code):
        if brace.group() == "{":
            stack.append(brace.start())
        elif stack:
            braces[stack.pop()] = brace.start()
        else:
            lexed.errors.append("unbalanced_brace")
    if stack:
        lexed.errors.append("unclosed_brace")
    namespaces = list(NAMESPACE.finditer(lexed.code))
    imports = USING.findall(lexed.code)
    types = []
    methods = []
    routes = []
    dtos = []
    for declaration in TYPE.finditer(lexed.code):
        opening = declaration.end() - 1
        if opening not in braces:
            continue
        closing = braces[opening]
        offset = declaration.start()
        namespace = next((item.group(1) for item in reversed(namespaces) if item.start() < offset), "")
        type_name = declaration.group(2)
        type_id = f"{namespace}.{type_name}".strip(".")
        outer = next((item for item in reversed(types) if item["body_start"] < offset < item["body_end"]), None)
        if outer:
            type_id = outer["symbol_id"] + "." + type_name
        type_item = {"kind": declaration.group(1), "name": type_name, "symbol_id": type_id, "namespace": namespace,
                     "imports": imports, "path": relative, "line": lexed.line(offset), "bases": [item.strip() for item in (declaration.group(3) or "").split(",")],
                     "body_start": opening + 1, "body_end": closing, "fields": {}}
        types.append(type_item)
        class_prefix_start = max(lexed.code.rfind("}", 0, offset), lexed.code.rfind(";", 0, offset)) + 1
        class_attributes = lexed.clean[class_prefix_start:offset]
        class_route_match = ROUTE_ATTRIBUTE.search(class_attributes)
        class_route = class_route_match.group(1) if class_route_match else ""
        region_start, region_end = type_item["body_start"], type_item["body_end"]
        body = lexed.code[region_start:region_end]
        for member in MEMBER.finditer("{" + body):
            if positions is None:
                tokens, pairs = lexed.tokens, lexed.pairs
                positions = {token.start: index for index, token in enumerate(tokens)}
            name_offset = region_start + member.start("name") - 1
            return_type = re.sub(r"\s+", "", member.group("return"))
            if return_type in {"return", "new", "throw", "await"}:
                continue
            if any(item["body_start"] <= name_offset < item["body_end"] for item in methods):
                continue
            parameter_offset = region_start + member.end() - 2
            parameter_open = positions.get(parameter_offset)
            if parameter_open not in pairs:
                continue
            parameter_close = pairs[parameter_open]
            cursor = parameter_close + 1
            while cursor < len(tokens) and tokens[cursor].value not in ("{", ";", "=>", "}") and cursor < parameter_close + 60:
                cursor += 1
            if cursor >= len(tokens) or tokens[cursor].value == "}":
                continue
            body_start = tokens[cursor].start
            if tokens[cursor].value == "{":
                if cursor not in pairs:
                    continue
                body_end = tokens[pairs[cursor]].end
            elif tokens[cursor].value == "=>":
                ending = expression_end(tokens, pairs, cursor + 1)
                body_end = tokens[ending].start if ending < len(tokens) else len(text)
            else:
                body_end = body_start
            parameters = _parameters(lexed, parameter_open, parameter_close)
            method_name = member.group("name")
            symbol_id = f"{type_id}.{method_name}({','.join(item['type'] for item in parameters)})"
            method = {"kind": "method", "name": f"{type_name}.{method_name}", "symbol_id": symbol_id, "type_id": type_id,
                      "namespace": namespace, "imports": imports, "member": method_name, "return_type": return_type,
                      "parameters": parameters, "path": relative, "line": lexed.line(name_offset),
                      "body_start": body_start, "body_end": body_end, "end_line": lexed.line(body_end)}
            methods.append(method)
            previous_boundary = max(lexed.code.rfind("}", region_start, name_offset), lexed.code.rfind(";", region_start, name_offset), region_start - 1) + 1
            attributes = lexed.clean[previous_boundary:name_offset]
            http_matches = list(HTTP_ATTRIBUTE.finditer(attributes))
            if http_matches and type_name.endswith("Controller"):
                controller = type_name[:-10]
                method_route_match = ROUTE_ATTRIBUTE.search(attributes)
                for http in http_matches:
                    method_route = http.group(2) or (method_route_match.group(1) if method_route_match else "")
                    route = method_route.removeprefix("~") if method_route.startswith(("/", "~/")) else "/" + "/".join(item.strip("/") for item in (class_route, method_route) if item)
                    route = route.replace("[controller]", controller).replace("{controller}", controller)
                    routes.append({"route": route, "method": http.group(1).upper(), "controller": type_name, "action": method_name,
                                   "symbol_id": symbol_id, "parameter_types": [item["type"] for item in parameters],
                                   "dto_types": [item["type"] for item in parameters if plain_type(item["type"]).endswith("Dto")],
                                   "path": relative, "line": lexed.line(previous_boundary + http.start()), "action_line": lexed.line(name_offset)})
        for field in FIELD.finditer(body):
            field_offset = region_start + field.start()
            if not any(item["body_start"] <= field_offset < item["body_end"] for item in methods):
                type_item["fields"][field.group("name")] = re.sub(r"\s+", "", field.group("type"))
        if "/Dto/" in "/" + relative and type_item["kind"] == "class":
            properties = []
            for property_match in re.finditer(r"\bpublic\s+([\w.]+(?:\s*<[^;{}]+>)?(?:\[\])?\??)\s+(\w+)\s*\{\s*get\s*;", body):
                properties.append({"name": property_match.group(2), "type": re.sub(r"\s+", "", property_match.group(1)), "line": lexed.line(region_start + property_match.start())})
            dtos.append({"name": type_name, "symbol_id": type_id, "path": relative, "line": type_item["line"], "bases": type_item["bases"], "properties": properties})
    return {"types": types, "methods": methods, "routes": routes, "dtos": dtos}, lexed


def resolve_type(name: str, owner: dict[str, Any], types: dict[str, dict[str, Any]]) -> str | None:
    name = plain_type(name)
    if name in PRIMITIVES:
        return name
    if name in types:
        return name
    names = [f"{owner.get('namespace', '')}.{name}".strip("."), *(f"{namespace}.{name}" for namespace in owner.get("imports", []))]
    found = list(dict.fromkeys(candidate for candidate in names if candidate in types))
    return found[0] if len(found) == 1 else None


def inherited_types(type_id: str, types: dict[str, dict[str, Any]]) -> list[str]:
    result, queue = [], [type_id]
    while queue and len(result) < 30:
        current = queue.pop(0)
        if current in result:
            continue
        result.append(current)
        owner = types.get(current, {})
        queue.extend(resolved for base in owner.get("bases", []) if (resolved := resolve_type(base, owner, types)))
    return result


def bind_backend(parsed_files: list[tuple[dict[str, Any], LexedSource]], file_count: int) -> dict[str, Any]:
    type_rows = [item for data, _ in parsed_files for item in data["types"]]
    types = {}
    for item in type_rows:
        if item["symbol_id"] in types:
            types[item["symbol_id"]]["fields"].update(item["fields"])
        else:
            types[item["symbol_id"]] = dict(item)
    methods = [item for data, _ in parsed_files for item in data["methods"]]
    by_member = {}
    for method in methods:
        by_member.setdefault(method["member"], []).append(method)
    bindings = []
    for owner in types.values():
        for base in owner.get("bases", []):
            interface_id = resolve_type(base, owner, types)
            if interface_id and types[interface_id]["kind"] == "interface" and owner["kind"] == "class":
                bindings.append({"interface": types[interface_id]["name"], "implementation": owner["name"], "interface_id": interface_id,
                                 "implementation_id": owner["symbol_id"], "path": owner["path"], "line": owner["line"], "confidence": "structural"})
    for data, _ in parsed_files:
        method_map = {item["symbol_id"]: item for item in data["methods"]}
        for route in data["routes"]:
            owner = method_map[route["symbol_id"]]
            route["dto_symbol_ids"] = [resolved for name in route["dto_types"] if (resolved := resolve_type(name, owner, types))]
    edges = []
    for data, lexed in parsed_files:
        if not data["methods"]:
            continue
        tokens, pairs = lexed.tokens, lexed.pairs
        positions = {token.start: index for index, token in enumerate(tokens)}
        for method in data["methods"]:
            lineage = inherited_types(method["type_id"], types)
            receiver_types = {"this": method["type_id"]}
            for type_id in reversed(lineage):
                receiver_types.update(types.get(type_id, {}).get("fields", {}))
            receiver_types.update({item["name"]: item["type"] for item in method["parameters"]})
            body_start, body_end = method["body_start"], method["body_end"]
            body = lexed.code[body_start:body_end]
            declarations = list(LOCAL.finditer(body))
            mutations = {}
            for assignment in ASSIGNMENT.finditer(body):
                mutations.setdefault(assignment.group("name"), []).append(assignment.start())
            call_matches = list(CALL.finditer(body))
            receiver_evidence = {}
            receiver_declared_at = {}
            declaration_index = 0
            for call in call_matches:
                call_offset = body_start + call.start()
                while declaration_index < len(declarations) and declarations[declaration_index].start() < call.start():
                    declaration = declarations[declaration_index]
                    declaration_index += 1
                    variable = declaration.group("name")
                    declared = re.sub(r"\s+", "", declaration.group("type"))
                    if declared in {"return", "throw"}:
                        continue
                    if declared == "var":
                        expression = body[declaration.end():]
                        constructed = re.match(r"\s*new\s+([\w.]+)", expression)
                        factory = re.match(r"\s*(?:this\.)?(\w+)\s*\(", expression)
                        if constructed:
                            declared = constructed.group(1)
                        elif factory:
                            factory_open = positions.get(body_start + declaration.end() + factory.end() - 1)
                            count = len(split_arguments(tokens, pairs, factory_open + 1, pairs[factory_open])) if factory_open in pairs else -1
                            candidates = [item for item in by_member.get(factory.group(1), []) if item["type_id"] in lineage and sum(not parameter["optional"] for parameter in item["parameters"]) <= count <= len(item["parameters"])]
                            returns = {item["return_type"] for item in candidates}
                            declared = next(iter(returns)) if len(returns) == 1 else ""
                            if declared:
                                receiver_evidence[variable] = {"factory": candidates[0]["symbol_id"], "path": candidates[0]["path"], "line": candidates[0]["line"]}
                        else:
                            declared = ""
                    receiver_types[variable] = declared
                    receiver_declared_at[variable] = declaration.end()
                receiver = call.group("receiver").removeprefix("this.")
                mutation_positions = mutations.get(receiver, [])
                first_mutation = bisect.bisect_left(mutation_positions, receiver_declared_at.get(receiver, 0))
                if first_mutation < len(mutation_positions) and mutation_positions[first_mutation] < call.start():
                    receiver_types[receiver] = ""
                    receiver_evidence.pop(receiver, None)
                raw_type = receiver_types.get(receiver)
                resolved_type = resolve_type(raw_type or receiver, method, types)
                opening = positions.get(body_start + call.end() - 1)
                arguments = split_arguments(tokens, pairs, opening + 1, pairs[opening]) if opening in pairs else []
                count = len(arguments)
                allowed_types = inherited_types(resolved_type, types) if resolved_type in types else []
                implementations = [item["implementation_id"] for item in bindings if item["interface_id"] in allowed_types]
                target_types = implementations or allowed_types
                targets = [item for item in by_member.get(call.group("name"), []) if item["type_id"] in target_types and sum(not parameter["optional"] for parameter in item["parameters"]) <= count <= len(item["parameters"])]
                if len(targets) > 1:
                    argument_types = []
                    for begin, end in arguments:
                        token = tokens[begin] if begin < end else None
                        inferred = "string" if token and token.kind == "string" else "int" if token and token.value.isdigit() else receiver_types.get(token.value, "") if token else ""
                        argument_types.append(inferred)
                    targets = [item for item in targets if all(not inferred or plain_type(parameter["type"]) == plain_type(inferred) for inferred, parameter in zip(argument_types, item["parameters"]))]
                data_access = None
                external_type = plain_type(raw_type or "")
                if resolved_type not in types and external_type in {"ZeroDbContext", "IFreeSql"} and (receiver in receiver_evidence or raw_type in {"ZeroDbContext", "IFreeSql"}):
                    if call.group("name").lower() in {"insert", "update", "delete", "select"}:
                        data_access = call.group("name").lower()
                infrastructure = receiver in {"string", "String", "Guid", "Math", "Convert", "JsonConvert"} or external_type in {"List", "Dictionary", "HashSet", "IEnumerable", "IList"}
                category = "data_access" if data_access else "infrastructure" if infrastructure else "business" if targets else "unresolved"
                edges.append({"layer": "backend", "caller": method["name"], "caller_id": method["symbol_id"], "receiver": receiver,
                              "receiver_type": resolved_type or raw_type, "receiver_evidence": receiver_evidence.get(receiver), "callee_member": call.group("name"),
                              "target_ids": [item["symbol_id"] for item in targets], "targets": [item["name"] for item in targets], "argument_count": count,
                              "path": method["path"], "line": lexed.line(call_offset), "data_access": data_access, "category": category,
                              "confidence": "structural" if len(targets) == 1 or data_access else "candidate"})
    symbols = [{key: value for key, value in item.items() if key not in {"body_start", "body_end", "fields", "imports"}} for item in [*type_rows, *methods]]
    return {"symbols": symbols, "routes": [item for data, _ in parsed_files for item in data["routes"]],
            "dto_contracts": [item for data, _ in parsed_files for item in data["dtos"]], "service_bindings": bindings, "call_edges": edges, "file_count": file_count}
