"""Hidden Tk smoke tests; every configuration, credential and network boundary is fake."""
from __future__ import annotations

import copy
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import tkinter as tk
    from gxp_project_context.window import ProjectSettingsWindow
except ImportError:
    tk = None


@unittest.skipIf(tk is None, "Tk is not installed")
class ProjectWindowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.enterContext(patch.dict(os.environ, {
            "GXP_LOWCODE_SHARED_CONFIG": str(base / "connection.json"),
            "GXP_PROJECT_CONFIG_ROOT": str(base / "configs"),
            "GXP_PROJECT_RUNTIME_ROOT": str(base / "runtime"),
            "GXP_LOWCODE_CONFIG": str(base / "look.json"),
            "GXP_LOWCODE_EDITOR_CONFIG": str(base / "write.json"),
            "GXP_LOWCODE_SCHEMA_CONFIG": str(base / "schema.json"),
            "GXP_LOWCODE_EDITOR_STATE": str(base / "editor.sqlite3"),
            "GXP_FORM_CONFIG_ROOT": str(base / "forms"),
        }))
        self.enterContext(patch("keyring.get_password", side_effect=AssertionError("No real credentials")))
        self.enterContext(patch("keyring.set_password", side_effect=AssertionError("No real credentials")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("No network")))
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest("Tk display is unavailable: " + str(exc))
        self.addCleanup(self.root.destroy)
        self.profiles = [self.profile("a", "Alpha"), self.profile("b", "Beta")]
        self.status = {"ok": True, "revision": "initial", "active_project_name": "Alpha", "active_edit_sessions": [],
                       "projects": self.profiles, "refresh": {"status": "partial", "resources": {
                           "schema": {"status": "ready"}, "cpm": {"status": "partial", "error_code": "MODEL_MISSING", "failures": [{"type": "model", "id": "fixture"}]}}}}
        self.backend = self.enterContext(patch("gxp_project_context.window.settings.settings_status", side_effect=lambda: copy.deepcopy(self.status)))
        self.enterContext(patch("gxp_project_context.window.load_profile", side_effect=lambda project_id, revision: copy.deepcopy(next(p for p in self.profiles if p["project_id"] == project_id))))
        self.window = ProjectSettingsWindow(self.root)
        self.pump()

    def profile(self, key, name):
        return {"project_id": key * 64, "revision": key * 64, "active": key == "a", "name": name, "environment": "development",
                "database": {"host": "fixture.invalid", "port": 3306, "database": name.lower()},
                "accounts": {"look": {"user": "reader", "credential_target": "fake-look"},
                             "write": {"user": "writer", "account_mode": "dedicated", "credential_target": "fake-write"}},
                "platform_binding": {"platform_url": "https://fixture.invalid", "app_id": "app", "site_out_id": "site", "account": "actor", "credential_target": "fake-platform", "form_config": {"contract_path": "fixture.json", "api_prefix": "/gxp2"}},
                "platform_version": {}, "refresh": {"timeout_seconds": 75, "http_concurrency": 2, "database_concurrency": 1}}

    def pump(self):
        deadline = time.monotonic() + 2
        while self.window.busy and time.monotonic() < deadline:
            self.window.poll()
            self.root.update_idletasks()
            time.sleep(0.005)
        self.assertFalse(self.window.busy, "Window background callback did not finish")

    def button(self, label):
        pending = [self.root]
        while pending:
            widget = pending.pop()
            if widget.winfo_class() == "TButton" and widget.cget("text") == label:
                return widget
            pending.extend(widget.winfo_children())
        self.fail("Button missing: " + label)

    def test_hidden_window_selection_new_project_and_progress(self):
        self.assertEqual("withdrawn", self.root.state())
        self.assertEqual("Alpha", self.window.fields["name"].get())
        self.window.selector.current(1)
        self.window.selected()
        self.assertEqual("b" * 64, self.window.project_id)
        self.assertEqual("beta", self.window.fields["database"].get())
        progress = self.window.progress.get("1.0", "end")
        self.assertIn("部分可用", progress)
        self.assertIn("MODEL_MISSING", progress)
        self.button("新增项目").invoke()
        self.assertEqual("", self.window.project_id)
        self.assertEqual("3306", self.window.fields["port"].get())
        self.assertEqual("", self.window.fields["look_password"].get())

    def test_save_callback_clears_passwords_and_switch_button_uses_selected_project(self):
        self.window.fields["look_password"].set("synthetic-only")
        with patch("gxp_project_context.window.settings.save_project", return_value={"ok": True, "project_id": "a" * 64}) as save:
            self.button("保存项目").invoke()
            self.pump()
        args, kwargs = save.call_args
        self.assertEqual("Alpha", args[0]["name"])
        self.assertEqual("initial", args[1])
        self.assertEqual({"look": "synthetic-only"}, kwargs["passwords"])
        self.assertEqual("", self.window.fields["look_password"].get())
        with patch("gxp_project_context.window.settings.switch_project", return_value={"ok": True}) as switch:
            self.button("切换并全量刷新").invoke()
            self.pump()
        switch.assert_called_once_with("a" * 64, "initial")

    def test_refresh_buttons_call_full_and_failed_only_paths(self):
        with patch("gxp_project_context.refresh.refresh_project", return_value={"ok": True}) as refresh:
            self.button("重新全量刷新").invoke()
            self.pump()
            refresh.assert_called_once_with("initial", retry_failed=False)
            refresh.reset_mock()
            self.button("重试未完成资料").invoke()
            self.pump()
            refresh.assert_called_once_with("initial", retry_failed=True)

    def test_copy_keeps_accounts_and_only_needs_new_database_destination(self):
        original_project = self.window.project_id
        self.button("复制当前项目").invoke()
        self.assertEqual("", self.window.project_id)
        self.assertEqual("reader", self.window.fields["look_user"].get())
        self.assertEqual("writer", self.window.fields["write_user"].get())
        self.assertEqual("", self.window.fields["look_password"].get())
        self.assertEqual("", self.window.fields["write_password"].get())
        self.window.fields["host"].set("other.invalid")
        self.window.fields["database"].set("another_db")
        profile = self.window.profile()
        self.assertEqual(original_project, profile["reuse_credentials_from"])
        self.assertEqual("", profile["accounts"]["write"]["expected_grants_sha256"])
        self.assertNotIn("credential_target", profile["platform_binding"]["form_config"])
        with patch("gxp_project_context.window.settings.save_project", return_value={"ok": True, "project_id": "b" * 64}) as save:
            self.button("保存项目").invoke()
            self.pump()
        self.assertEqual({}, save.call_args.kwargs["passwords"])

    def test_legacy_window_prefills_platform_metadata_and_preserves_secret_reference(self):
        self.status["projects"] = []
        self.status["active_project_id"] = "a" * 64
        self.status["settings"] = {"host": "db.invalid", "port": 3306, "database": "legacy",
                                   "look_user": "reader", "write_user": "writer", "account_mode": "shared_unrestricted"}
        self.status["platform_defaults"] = {"platform_binding": self.profile("a", "Alpha")["platform_binding"], "platform_version": {}}
        self.window.project_id = ""
        self.window.run("load", self.window.backend.settings_status) if hasattr(self.window, "backend") else self.window.run("load", lambda: self.status)
        self.pump()
        for key, expected in (("platform_url", "https://fixture.invalid"), ("app_id", "app"), ("site_out_id", "site"), ("account", "actor"), ("api_prefix", "/gxp2")):
            self.assertEqual(expected, self.window.fields[key].get())
        self.assertEqual("", self.window.fields["platform_password"].get())
        self.assertEqual("fake-platform", self.window.profile()["platform_binding"]["credential_target"])
        self.assertIn("不用重新填写", self.window.platform_summary.get())

    def pump_background(self):
        deadline = time.monotonic() + 2
        while self.window.background_busy and time.monotonic() < deadline:
            self.window.poll()
            self.root.update_idletasks()
            time.sleep(0.005)
        self.assertFalse(self.window.background_busy)

    def test_connection_failure_stays_visible_after_background_status_update(self):
        failure = "目标数据库连接测试失败，原项目保留。"
        self.window.run("switch", lambda: {"ok": False, "error": failure})
        self.pump()
        self.assertEqual(failure, self.window.message.get())
        self.status["revision"] = "background-must-not-change-form-revision"
        self.window.run("progress", lambda: copy.deepcopy(self.status))
        self.assertFalse(self.window.busy)
        self.assertEqual("readonly", str(self.window.selector.cget("state")))
        self.pump_background()
        self.assertEqual(failure, self.window.message.get())
        self.assertEqual("initial", self.window.revision)

    def test_idle_window_does_not_keep_querying_progress(self):
        self.window._status_snapshot = {"refresh": None, "active_edit_sessions": []}
        self.backend.reset_mock()
        self.window.refresh_progress()
        self.backend.assert_not_called()
        self.assertFalse(self.window.background_busy)

    def test_saved_project_selector_shows_actual_host_and_port(self):
        labels = self.window.selector.cget("values")
        self.assertIn("fixture.invalid:3306/alpha", labels[0])

    def test_save_current_connection_does_not_save_the_selected_target_form(self):
        self.window.selector.current(1)
        self.window.selected()
        self.window.fields["host"].set("typed-but-not-current.invalid")
        with patch("gxp_project_context.window.settings.save_current_project", return_value={"ok": True, "project_id": "a" * 64}) as save_current, \
             patch("gxp_project_context.window.settings.save_project", side_effect=AssertionError("Do not save the target form")):
            self.button("保存当前连接").invoke()
            self.pump()
        save_current.assert_called_once_with("initial")
        self.assertEqual("a" * 64, self.window.project_id)

    def test_unchanged_status_does_not_clear_or_redraw_progress_text(self):
        self.window.render_progress(copy.deepcopy(self.status))
        with patch.object(self.window.progress, "delete") as clear, patch.object(self.window.progress, "insert") as insert:
            self.window.render_progress(copy.deepcopy(self.status))
        clear.assert_not_called()
        insert.assert_not_called()

    def test_stale_background_result_cannot_unlock_foreground_or_replace_message(self):
        old_epoch = self.window._view_epoch
        self.window.background_busy = True
        self.window.selector.current(1)
        self.window.selected()
        self.window.busy = True
        self.window.selector.configure(state="disabled")
        self.window.message.set("正在测试连接并切换项目…")
        self.window.results.put(("progress", copy.deepcopy(self.status), old_epoch))
        self.window.poll()
        self.assertTrue(self.window.busy)
        self.assertEqual("disabled", str(self.window.selector.cget("state")))
        self.assertEqual("正在测试连接并切换项目…", self.window.message.get())
        self.assertEqual("b" * 64, self.window.project_id)
        self.window.busy = False

    def test_polling_stops_after_refresh_finishes(self):
        self.window._status_snapshot = {"refresh": {"status": "fetching"}, "active_edit_sessions": []}
        self.status["refresh"]["status"] = "ready"
        self.backend.reset_mock()
        self.window.refresh_progress()
        self.pump_background()
        self.assertEqual(1, self.backend.call_count)
        self.window.refresh_progress()
        self.assertEqual(1, self.backend.call_count)


if __name__ == "__main__":
    unittest.main()
