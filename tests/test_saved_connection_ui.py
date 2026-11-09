"""Hidden Tk checks for the small saved-connection controls, using a fake backend."""
from __future__ import annotations

import copy
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import tkinter as tk
    from gxp_core.connection_settings_ui import ConnectionSettingsWindow
except ImportError:
    tk = None


class Backend:
    def __init__(self):
        self.revision = "r1"
        self.active = {"host": "current.invalid", "port": 3306, "database": "current-db"}
        self.projects = [{"project_id": "saved", "name": "Saved database", "revision": "p1",
                          "database": {"host": "saved.invalid", "port": 3307, "database": "saved-db"}}]
        self.calls = []

    def settings_status(self):
        return {"ok": True, "configured": True, "revision": self.revision,
                "settings": {**self.active, "look_user": "original-reader", "write_user": "original-writer"},
                "active_edit_sessions": [], "config_path": "synthetic.json"}

    def list_projects(self):
        return {"ok": True, "projects": copy.deepcopy(self.projects)}

    def save_project(self, name, expected_revision, changes=None):
        self.calls.append(("save_project", name, expected_revision, changes))
        self.revision = "r2"
        project = {"project_id": "new", "name": name, "revision": "p2", "database": dict(changes)}
        self.projects.append(project)
        return {"ok": True, "project": project, "revision": self.revision}

    def switch_project(self, project_id, expected_revision):
        self.calls.append(("switch_project", project_id, expected_revision))
        self.active = dict(next(project for project in self.projects if project["project_id"] == project_id)["database"])
        self.revision = "r3"
        return {"ok": True, "revision": self.revision}

    def update_settings(self, changes, expected_revision, **kwargs):
        self.calls.append(("update_settings", changes, expected_revision, kwargs))
        return {"ok": True}

    def open_sessions(self):
        self.calls.append(("open_sessions",))
        return {"ok": True, "opened": True}


@unittest.skipIf(tk is None, "Tk unavailable")
class SavedConnectionUiTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("No network")))
        self.enterContext(patch("keyring.get_password", side_effect=AssertionError("No credentials")))
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as error:
            self.skipTest("Tk display unavailable: " + str(error))
        self.addCleanup(self.root.destroy)
        self.backend = Backend()
        self.window = ConnectionSettingsWindow(self.root, backend=self.backend)
        self.pump()

    def pump(self):
        deadline = time.monotonic() + 2
        while self.window.busy and time.monotonic() < deadline:
            self.window._poll()
            self.root.update_idletasks()
            time.sleep(0.005)
        self.assertFalse(self.window.busy)

    def test_selection_only_loads_address_without_switching_or_replacing_accounts(self):
        self.window.fields["look_password"].set("synthetic-unsaved")
        self.window.project_selector.current(0)
        self.window.load_selected_project()
        self.assertEqual("saved.invalid", self.window.fields["host"].get())
        self.assertEqual("3307", self.window.fields["port"].get())
        self.assertEqual("original-reader", self.window.fields["look_user"].get())
        self.assertEqual("synthetic-unsaved", self.window.fields["look_password"].get())
        self.assertEqual("current.invalid", self.backend.active["host"])
        self.assertIn("当前生效：current.invalid", self.window.current_connection.get())
        self.assertIn("尚未切换", self.window.message.get())
        self.assertEqual([], self.backend.calls)

    def test_save_new_address_does_not_connect_or_switch_and_selected_switch_uses_saved_id(self):
        self.window.fields["host"].set("new.invalid")
        self.window.fields["database"].set("new-db")
        self.window.project_name.set("Another database")
        self.window.fields["look_password"].set("synthetic-unused")
        self.window.save_project_button.invoke()
        self.pump()
        self.assertEqual(("save_project", "Another database", "r1", {"host": "new.invalid", "port": 3306, "database": "new-db"}), self.backend.calls[0])
        self.assertEqual("current.invalid", self.backend.active["host"])
        self.assertEqual("new.invalid", self.window.fields["host"].get())
        self.assertEqual("new", self.window.selected_project_id)
        self.window.switch_project_button.invoke()
        self.pump()
        self.assertEqual(("switch_project", "new", "r2"), self.backend.calls[-1])
        self.assertEqual("new.invalid", self.window.fields["host"].get())
        self.assertIn("当前生效：new.invalid", self.window.current_connection.get())

    def test_original_test_connection_action_is_preserved(self):
        self.window.fields["look_password"].set("synthetic-input")
        self.window.test_button.invoke()
        self.pump()
        call = self.backend.calls[-1]
        self.assertEqual("update_settings", call[0])
        self.assertTrue(call[3]["test_only"])
        self.assertEqual("synthetic-input", call[3]["look_password"])
        self.assertIn("设置尚未保存", self.window.message.get())

    def test_session_button_only_opens_existing_handler_and_keeps_connection_inputs(self):
        self.window.fields["host"].set("unsaved-target.invalid")
        self.window.sessions_button.invoke()
        self.pump()
        self.assertEqual([("open_sessions",)], self.backend.calls)
        self.assertEqual("unsaved-target.invalid", self.window.fields["host"].get())
        self.assertEqual("current.invalid", self.backend.active["host"])
        self.assertIn("请在流程窗口确认处理", self.window.message.get())


class SavedConnectionMirrorTests(unittest.TestCase):
    def test_look_and_write_settings_windows_are_identical(self):
        look = Path(__file__).resolve().parents[1] / "mcp/gxp_core/connection_settings_ui.py"
        write = look.parents[3] / "write/mcp/gxp_editor/connection_settings_ui.py"
        if write.exists():
            self.assertEqual(look.read_bytes(), write.read_bytes())


if __name__ == "__main__":
    unittest.main()
