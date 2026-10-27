"""Query-only synthetic ActionDesign database; never opens a connection."""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canvas(count=24):
    nodes = [{"key": f"writer-{index}", "title": "过滤器", "elementKey": "DataFilter", "paramsValue": {"inputParams": {
        "name": {"value": "picker", "componentType": "EformDynamicList"},
        "whereConditions": {"Logic": "And", "Filters": [{"Field": "table.id", "Operator": "Any", "ParamInput": {"code": f"values{index}"}}]}}}}
        for index in range(count)]
    return {"actionData": [{"key": "main", "title": "主动作", "data": nodes}]}


class FixtureDatabase:
    columns = ("id", "ref_Id", "is_publish", "isDeleted", "lastModificationTime", "creationTime", "data", "csharp_code")

    def __init__(self, count=24, history=3):
        self.config = SimpleNamespace(host="synthetic.invalid", port=3306, database="fixture", user="reader", credential_target="fixture-only")
        self.actions = [{"action_type": "public", "ref_id": "root", "action_code": "ACTION01", "action_name": "根动作", "page_id": None}]
        text = json.dumps(canvas(count), ensure_ascii=False)
        self.versions = [{"design_id": f"published-{index:03}", "ref_id": "root", "is_publish": 1,
            "is_deleted": int(index != history - 1), "modified_time": f"2026-10-26 10:{index:02}:00",
            "created_time": f"2026-10-26 10:{index:02}:00", "data": text,
            "csharp_code": 'class ACTION01 { void Run() {\nCallPublicAction("MISSING01");\n} }'} for index in range(history)]
        self.versions.append({**self.versions[-1], "design_id": "draft", "is_publish": 0})
        self.queries, self.body_reads, self.denied, self.truncated = [], 0, False, False

    @contextmanager
    def session(self, **kwargs):
        yield self

    def query(self, sql, params=None, *, max_rows=200):
        self.queries.append((sql, deepcopy(params), max_rows))
        if self.denied:
            raise PermissionError("synthetic SELECT denied")
        if sql.startswith("DESCRIBE"):
            return [{"Field": name} for name in self.columns], False
        if "FROM cpm_public_flows" in sql:
            if isinstance(params, list):
                rows = [row for row in self.actions if row["ref_id"] in params or row["action_code"] in params]
            else:
                rows = [row for row in self.actions if params["query"] in (row["ref_id"], row["action_code"]) or params["query"] in row["action_name"]]
            return deepcopy(sorted(rows, key=lambda row: (row["action_type"], row["ref_id"]))), self.truncated
        if "FROM `cpm_bizflows_design`" not in sql:
            raise AssertionError("Unhandled synthetic query: " + sql)
        rows = list(self.versions)
        if "LIKE %(needle)s" in sql:
            rows = [row for row in rows if params["needle"].strip("%") in row["csharp_code"]]
            rows.sort(key=lambda row: (row["is_deleted"], -row["is_publish"], row["design_id"]))
            result = [{key: row[key] for key in ("design_id", "ref_id", "is_publish", "is_deleted", "modified_time")}
                      | {"csharp_length": len(row["csharp_code"].encode("utf-8"))} for row in rows]
            return deepcopy(result[:max_rows]), self.truncated or len(result) > max_rows
        rows = [row for row in rows if row["ref_id"] == params["ref_id"]]
        if "design_id" in params:
            rows = [row for row in rows if row["design_id"] == params["design_id"]]
        if "AND `isDeleted`=0" in sql:
            rows = [row for row in rows if not row["is_deleted"]]
        rows.sort(key=lambda row: row["design_id"])
        rows.sort(key=lambda row: row["is_deleted"])
        rows.sort(key=lambda row: row["created_time"], reverse=True)
        rows.sort(key=lambda row: row["modified_time"], reverse=True)
        result = []
        for row in rows:
            item = {key: row[key] for key in ("design_id", "ref_id", "is_publish", "is_deleted", "modified_time", "created_time")}
            for source, alias in (("data", "data"), ("csharp_code", "csharp_code")):
                if f"AS `{alias}`" in sql:
                    proof = f"SHA2(CONVERT(IFNULL(`{source}`" in sql
                    item[alias] = sha(row[source]) if proof else row[source]
                    self.body_reads += int(not proof)
            for alias, source in (("data_length", "data"), ("csharp_length", "csharp_code")):
                if f"AS `{alias}`" in sql:
                    item[alias] = len(row[source].encode("utf-8"))
            for alias, source in (("data_sha256", "data"), ("csharp_sha256", "csharp_code")):
                if f"AS `{alias}`" in sql:
                    item[alias] = sha(row[source])
            result.append(item)
        return deepcopy(result[:max_rows]), self.truncated or len(result) > max_rows


STACK = 'System.Exception: synthetic failure\n at Generated.ACTION01.Run() in generated.cs:line 2'
