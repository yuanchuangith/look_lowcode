from __future__ import annotations

import unittest

from gxp_core.sql_guard import SqlRejected, validate_readonly_sql


class SqlGuardTests(unittest.TestCase):
    def test_allows_supported_read_statements(self) -> None:
        for sql in (
            "SELECT id FROM cpm_bizflows WHERE id=%(id)s LIMIT 1",
            "WITH x AS (SELECT 1 AS value) SELECT value FROM x",
            "SHOW TABLES",
            "DESCRIBE cpm_bizflows",
            "EXPLAIN SELECT * FROM cpm_bizflows WHERE id='x'",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(validate_readonly_sql(sql, "testdb").sql_hash)

    def test_rejects_mutation_and_multi_statement(self) -> None:
        for sql in (
            "UPDATE cpm_bizflows SET code='x'",
            "DELETE FROM cpm_bizflows",
            "SELECT 1; SELECT 2",
            "SET @x=1",
            "SELECT SLEEP(1)",
            "SELECT * FROM cpm_bizflows FOR UPDATE",
            "SELECT * FROM another_database.some_table",
            "SHOW TABLES FROM mysql",
            "SHOW DATABASES",
            "SELECT LOAD_FILE('x')",
        ):
            with self.subTest(sql=sql), self.assertRaises(SqlRejected):
                validate_readonly_sql(sql, "testdb")


if __name__ == "__main__":
    unittest.main()
