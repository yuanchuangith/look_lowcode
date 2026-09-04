from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from gxp_core.schema_repository import (
    SchemaMetadataRepository,
    columns_compatible,
    generate_candidates,
    unique_keys,
)


def column(name: str, data_type: str = "bigint", **extra):
    return {
        "column_name": name,
        "data_type": data_type,
        "character_set_name": None,
        "collation_name": None,
        **extra,
    }


def table(name: str, columns, unique=("id",), comment=""):
    return {
        "table_name": name,
        "table_comment": comment,
        "columns": list(columns),
        "indexes": [
            {"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": i + 1, "column_name": value}
            for i, value in enumerate(unique)
        ],
        "constraints": [],
        "foreign_keys": [],
        "checks": [],
    }


class ScalarSession:
    def __init__(self, values):
        self.values = list(values)
        self.sql = []

    def scalar(self, sql, params=None):
        self.sql.append(sql)
        return self.values.pop(0)


class ScalarDatabase:
    def __init__(self, values):
        self.config = SimpleNamespace(database="dev")
        self.active = ScalarSession(values)

    @contextmanager
    def session(self, **kwargs):
        yield self.active


class PagingSession:
    def __init__(self):
        self.calls = []

    def query(self, sql, params, *, max_rows):
        self.calls.append(dict(params))
        if params["after"] == 0:
            return [
                {"COLUMN_NAME": f"c{i}", "ORDINAL_POSITION": i, "DATA_TYPE": "varchar"}
                for i in range(1, 501)
            ], True
        return [{"COLUMN_NAME": "c501", "ORDINAL_POSITION": 501, "DATA_TYPE": "varchar"}], False


class PagingDatabase:
    def __init__(self):
        self.config = SimpleNamespace(database="dev")
        self.active = PagingSession()

    @contextmanager
    def session(self, **kwargs):
        yield self.active


class SchemaRepositoryTests(unittest.TestCase):
    def test_generates_only_metadata_candidates_against_unique_targets(self) -> None:
        schema = {
            "tables": [
                table("orders", [column("id"), column("user_id")]),
                table("users", [column("id")]),
                table("logs", [column("id")], unique=()),
            ]
        }
        candidates = generate_candidates(schema)
        self.assertEqual(1, len(candidates))
        self.assertEqual("orders", candidates[0]["source_table"])
        self.assertEqual(["user_id"], candidates[0]["source_columns"])
        self.assertEqual("users", candidates[0]["target_table"])
        self.assertEqual([["id"]], unique_keys(schema["tables"][1]))

    def test_generic_id_with_legacy_underscores_does_not_create_cross_table_candidates(self) -> None:
        schema = {
            "tables": [
                table("history_a", [column("ID_")], unique=("ID_",)),
                table("history_b", [column("ID_")], unique=("ID_",)),
            ]
        }
        self.assertEqual([], generate_candidates(schema))

    def test_type_compatibility_rejects_family_collation_and_narrow_target_mismatch(self) -> None:
        self.assertFalse(columns_compatible(column("x", "bigint"), column("id", "varchar")))
        self.assertFalse(columns_compatible(
            column("x", "varchar", character_set_name="utf8mb4", collation_name="utf8mb4_bin", character_maximum_length=64),
            column("id", "varchar", character_set_name="utf8mb4", collation_name="utf8mb4_general_ci", character_maximum_length=64),
        ))
        self.assertFalse(columns_compatible(
            column("x", "varchar", character_maximum_length=128),
            column("id", "varchar", character_maximum_length=64),
        ))

    def test_full_data_validation_returns_counts_only(self) -> None:
        database = ScalarDatabase([25, 20, 0])
        result = SchemaMetadataRepository(database).validate_relation(
            "orders", ["user_id"], "users", ["id"], min_distinct_values=20
        )
        self.assertTrue(result["passed"])
        self.assertEqual(1.0, result["match_rate"])
        self.assertEqual({
            "non_null_count", "distinct_count", "unmatched_count", "source_unique",
            "match_rate", "passed", "reason",
        }, set(result))
        self.assertTrue(all("SELECT COUNT" in sql for sql in database.active.sql))

    def test_full_data_validation_rejects_orphans_and_small_sets(self) -> None:
        orphaned = SchemaMetadataRepository(ScalarDatabase([30, 25, 1])).validate_relation(
            "orders", ["user_id"], "users", ["id"], min_distinct_values=20
        )
        self.assertFalse(orphaned["passed"])
        self.assertEqual("unmatched_values", orphaned["reason"])
        small = SchemaMetadataRepository(ScalarDatabase([10, 10, 0])).validate_relation(
            "orders", ["user_id"], "users", ["id"], min_distinct_values=20
        )
        self.assertFalse(small["passed"])
        self.assertEqual("insufficient_distinct_values", small["reason"])

    def test_columns_page_beyond_session_cap(self) -> None:
        database = PagingDatabase()
        result = SchemaMetadataRepository(database)._columns("wide_table")
        self.assertEqual(501, len(result))
        self.assertEqual(500, database.active.calls[1]["after"])


if __name__ == "__main__":
    unittest.main()
