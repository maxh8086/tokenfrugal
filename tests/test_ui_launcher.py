import os
import unittest
from unittest import mock

from gateway import ui_launcher


class UiLauncherTests(unittest.TestCase):
    def test_disabled_by_env(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_UI": "0"}):
            self.assertFalse(ui_launcher.enabled())
            self.assertIsNone(ui_launcher.start())

    def test_no_node_is_not_fatal(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_UI": "1"}), \
             mock.patch.object(ui_launcher, "listening", return_value=False), \
             mock.patch.object(ui_launcher.shutil, "which", return_value=None):
            self.assertIsNone(ui_launcher.start())

    def test_reuses_running_server_without_spawning(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_UI": "1", "UI_PORT": "7777"}), \
             mock.patch.object(ui_launcher, "listening", return_value=True), \
             mock.patch.object(ui_launcher.subprocess, "Popen") as popen:
            self.assertEqual(ui_launcher.start(), "http://127.0.0.1:7777")
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
