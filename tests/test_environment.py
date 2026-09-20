from __future__ import annotations

import unittest
from unittest.mock import Mock

from gxp_core.canvas import CanvasInspector
from gxp_core.config import DatabaseConfig, ConfigurationError
from gxp_core.diagnostics import DiagnosticEngine
from gxp_core.environment import diagnosis_environment


class EnvironmentTests(unittest.TestCase):
    def decide(self, text, previous=None, configured="development"):
        return diagnosis_environment(text, {"environment": previous} if previous else None, configured)

    def test_legacy_and_new_connections_default_to_development(self):
        config = DatabaseConfig.from_dict({"host": "fixture", "port": 3306, "database": "fixture", "user": "fixture"})
        self.assertEqual("development", config.environment)
        self.assertEqual("development", self.decide("排查动作异常")["database_environment"])
        with self.assertRaises(ConfigurationError):
            DatabaseConfig.from_dict({**config.public_dict(), "environment": "invalid"})

    def test_target_does_not_relabel_connection(self):
        for text in ("排查生产环境", "正式环境异常", "线上环境报错", "排查prod", "production"):
            with self.subTest(text=text):
                result = self.decide(text)
                self.assertEqual("production", result["target_environment"])
                self.assertEqual("development", result["database_environment"])
                self.assertEqual("blocked", result["status"])

    def test_explicit_connection_declaration_overrides_default(self):
        for text in ("当前配置的数据库是生产环境，排查生产异常", "我配置的是正式环境", "这个连接就是测试库"):
            result = self.decide(text)
            self.assertEqual("matched", result["status"], result)
            self.assertEqual("user_declared", result["database_basis"])
            self.assertNotEqual("development", result["database_environment"])

    def test_declaration_and_target_can_still_differ(self):
        result = self.decide("当前配置的数据库是测试环境，排查生产环境")
        self.assertEqual("test", result["database_environment"])
        self.assertEqual("production", result["target_environment"])
        self.assertEqual("blocked", result["status"])

    def test_followup_retains_explicit_source_and_target(self):
        first = self.decide("当前连接是生产环境，排查生产环境")
        for text in ("继续查", "我改好了", "发布了再看看"):
            result = self.decide(text, first["record"])
            self.assertEqual(first["record"], result["record"])
        blocked = self.decide("排查生产环境")
        self.assertEqual("blocked", self.decide("继续查", blocked["record"])["status"])

    def test_business_words_negation_and_logs_do_not_relabel_database(self):
        self.assertEqual("test", self.decide("生产订单在测试环境报错")["target_environment"])
        self.assertEqual("test", self.decide("不是生产，是测试")["target_environment"])
        self.assertEqual("development", self.decide("生产订单未完成")["target_environment"])
        result = self.decide("排查开发环境\n```\n当前连接是生产环境")
        self.assertEqual("development", result["database_environment"])

    def test_reference_is_explicit_and_preserves_production_target(self):
        result = self.decide("生产环境报错，先参考开发配置")
        self.assertEqual("reference_only", result["status"])
        self.assertEqual("production", result["target_environment"])
        self.assertEqual("development", result["database_environment"])
        self.assertEqual("blocked", self.decide("生产环境报错，不要参考开发配置")["status"])

    def test_configured_environment_is_used_without_user_override(self):
        result = self.decide("排查测试环境", configured="test")
        self.assertEqual("matched", result["status"])
        self.assertEqual("configuration", result["database_basis"])

    def test_diagnosis_blocks_before_any_repository_read(self):
        repository = Mock()
        repository.database = None
        engine = DiagnosticEngine(repository, CanvasInspector())
        result = engine.diagnose_codex_input("生产环境异常\nat GTEoZQNMJ.GTEoZQNMJ.main() in :line 213")
        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["database_queried"])
        self.assertEqual([], repository.mock_calls)
        followup = engine.diagnose_codex_input("继续查", context=result["conversation_context"]["record"])
        self.assertEqual("blocked", followup["status"])
        self.assertEqual([], repository.mock_calls)

    def test_default_development_diagnosis_remains_compatible(self):
        repository = Mock()
        repository.database = None
        repository.resolve_actions.return_value = []
        repository.search_actions.return_value = []
        repository.search_design_text.return_value = []
        result = DiagnosticEngine(repository, CanvasInspector()).diagnose_codex_input("check ACTION01")
        self.assertEqual("matched", result["environment"]["status"])
        self.assertTrue(repository.resolve_actions.called)


if __name__ == "__main__":
    unittest.main()
