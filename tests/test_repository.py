from __future__ import annotations

import unittest
from contextlib import contextmanager

from gxp_core.repository import GxpRepository, _page_similarity


class FormattingSession:
    """Approximate PyMySQL's mapping interpolation for a query-only unit test."""

    def __init__(self) -> None:
        self.sql = ""
        self.params: dict[str, object] = {}
        self.rendered_sql = ""

    def query(self, sql, params, *, max_rows):
        self.sql = sql
        self.params = dict(params)
        escaped = {key: repr(value) for key, value in self.params.items()}
        self.rendered_sql = sql % escaped
        return [{"form_name": "培训矩阵申请流程"}], False


class QueueDatabase:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    @contextmanager
    def session(self, **kwargs):
        database = self

        class Session:
            def query(self, sql, params, *, max_rows):
                database.calls.append((sql, params, max_rows))
                return database.responses.pop(0), False

        yield Session()


class RepositoryTests(unittest.TestCase):
    def test_form_name_query_parameterizes_multilingual_like_pattern(self) -> None:
        repository = object.__new__(GxpRepository)
        session = FormattingSession()

        form_name = repository._load_form_name("peixunjuzhenshenqingliucheng", session)

        self.assertEqual("培训矩阵申请流程", form_name)
        self.assertEqual(
            "{multilingual}global.%",
            session.params["multilingual_name_pattern"],
        )
        self.assertEqual(
            "peixunjuzhenshenqingliucheng",
            session.params["page_id"],
        )
        self.assertIn("LIKE '{multilingual}global.%'", session.rendered_sql)

    def test_page_result_distinguishes_identifier_name_and_contains(self) -> None:
        row = {
            "page_id": "page-id",
            "route": "gangweipeixunshenqingliucheng",
            "out_id": "page-out-id",
            "application_id": "app-1",
            "raw_name": "raw-name",
            "display_name": "岗位培训申请流程",
        }

        by_route = GxpRepository._page_result(row, "gangweipeixunshenqingliucheng")
        by_id = GxpRepository._page_result(row, "page-id")
        by_out_id = GxpRepository._page_result(row, "page-out-id")
        by_name = GxpRepository._page_result(row, "岗位培训申请流程")
        by_contains = GxpRepository._page_result(row, "岗位培训申请")

        self.assertEqual("exact_identifier", by_route["matched_by"])
        self.assertEqual("exact_identifier", by_id["matched_by"])
        self.assertEqual("exact_identifier", by_out_id["matched_by"])
        self.assertEqual("exact_display_name", by_name["matched_by"])
        self.assertEqual("display_name_contains", by_contains["matched_by"])

    def test_fuzzy_page_search_ranks_three_golden_queries_first(self) -> None:
        pages = [
            {
                "page_id": "apply",
                "route": "peixunjuzhenshenqingliucheng",
                "out_id": "out-apply",
                "application_id": "app-1",
                "raw_name": "raw-apply",
                "display_name": "培训矩阵申请流程",
            },
            {
                "page_id": "revise",
                "route": "peixunjuzhenbiangengliucheng",
                "out_id": "out-revise",
                "application_id": "app-1",
                "raw_name": "raw-revise",
                "display_name": "培训矩阵修订流程",
            },
            {
                "page_id": "training",
                "route": "gangweipeixunshenqingliucheng",
                "out_id": "out-training",
                "application_id": "app-1",
                "raw_name": "raw-training",
                "display_name": "岗位培训申请流程",
            },
        ]
        expected = {
            "岗位矩阵申请": "peixunjuzhenshenqingliucheng",
            "岗位矩阵修订": "peixunjuzhenbiangengliucheng",
        }
        for query, route in expected.items():
            database = QueueDatabase([[], pages])
            repository = GxpRepository(database)
            result = repository.search_pages(query)
            self.assertEqual(route, result[0]["route"])
            self.assertEqual("chinese_bigram_similarity", result[0]["matched_by"])

        direct_database = QueueDatabase([[pages[2]]])
        direct = GxpRepository(direct_database).search_pages("岗位培训申请")
        self.assertEqual("gangweipeixunshenqingliucheng", direct[0]["route"])
        self.assertEqual("display_name_contains", direct[0]["matched_by"])

    def test_page_similarity_prefers_matching_business_operation(self) -> None:
        self.assertGreater(
            _page_similarity("岗位矩阵申请", "培训矩阵申请流程"),
            _page_similarity("岗位矩阵申请", "培训矩阵修订流程"),
        )
        self.assertGreater(
            _page_similarity("采购订单审批", "采购订单审批流程"),
            _page_similarity("采购订单审批", "采购订单编辑页面"),
        )

    def test_lists_active_page_actions_with_bounded_query(self) -> None:
        database = QueueDatabase(
            [[{"ref_id": "ref-1", "action_code": "PQDL0QlL", "action_name": "培训主题", "page_id": "route-1", "application_id": "app-1", "action_order": 1}]]
        )
        repository = GxpRepository(database)
        actions = repository.list_page_actions(
            {"route": "route-1", "page_id": "page-1", "out_id": "out-1"}
        )

        self.assertEqual("PQDL0QlL", actions[0]["action_code"])
        self.assertEqual("form", actions[0]["action_type"])
        sql, params, max_rows = database.calls[0]
        self.assertIn("isDeleted=0", sql)
        self.assertEqual(["route-1", "page-1", "out-1"], params)
        self.assertEqual(50, max_rows)

    def test_load_design_at_time_honors_requested_version_and_publish_time(self) -> None:
        repository = object.__new__(GxpRepository)
        repository.action_metadata = lambda ref_id: {"ref_id": ref_id}
        repository.get_design_versions = lambda ref_id, **kwargs: [
            {
                "design_id": "future-published",
                "version": "published",
                "is_deleted": False,
                "created_time": "2026-02-01 00:00:00",
                "modified_time": "2025-01-01 00:00:00",
                "data": "{}",
            },
            {
                "design_id": "past-published",
                "version": "published",
                "is_deleted": True,
                "created_time": "2026-01-01 00:00:00",
                "modified_time": "2026-03-01 00:00:00",
                "data": "{}",
            },
            {
                "design_id": "past-draft",
                "version": "draft",
                "is_deleted": True,
                "created_time": "2025-01-01 00:00:00",
                "modified_time": "2026-01-10 00:00:00",
                "data": "{}",
            },
        ]

        published = repository.load_design(
            "ref-1", version="published", at_time="2026-01-15 00:00:00"
        )
        draft = repository.load_design(
            "ref-1", version="draft", at_time="2026-01-15 00:00:00"
        )

        self.assertEqual("past-published", published["design_id"])
        self.assertEqual("past-draft", draft["design_id"])


if __name__ == "__main__":
    unittest.main()
