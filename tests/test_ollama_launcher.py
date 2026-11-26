import os
import unittest
from unittest import mock

from router import ollama_launcher


class OllamaLauncherTests(unittest.TestCase):
    def test_disabled_by_env(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_OLLAMA_AUTOSTART": "0"}), \
             mock.patch.object(ollama_launcher, "reachable", return_value=False), \
             mock.patch.object(ollama_launcher.subprocess, "Popen") as popen:
            self.assertFalse(ollama_launcher.ensure("http://localhost:11434/v1"))
            popen.assert_not_called()

    def test_remote_endpoint_is_never_started(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_OLLAMA_AUTOSTART": "1"}), \
             mock.patch.object(ollama_launcher, "reachable", return_value=False), \
             mock.patch.object(ollama_launcher.subprocess, "Popen") as popen:
            self.assertFalse(ollama_launcher.ensure("http://10.0.0.5:11434/v1"))
            popen.assert_not_called()

    def test_running_server_is_not_spawned_again(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_OLLAMA_AUTOSTART": "1"}), \
             mock.patch.object(ollama_launcher, "reachable", return_value=True), \
             mock.patch.object(ollama_launcher.subprocess, "Popen") as popen:
            self.assertTrue(ollama_launcher.ensure("http://localhost:11434/v1"))
            popen.assert_not_called()

    def test_missing_binary_is_not_fatal(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_OLLAMA_AUTOSTART": "1"}), \
             mock.patch.object(ollama_launcher, "reachable", return_value=False), \
             mock.patch.object(ollama_launcher, "binary", return_value=None), \
             mock.patch.object(ollama_launcher.subprocess, "Popen") as popen:
            self.assertFalse(ollama_launcher.ensure("http://localhost:11434/v1"))
            popen.assert_not_called()

    def test_starts_serve_and_waits_until_reachable(self):
        with mock.patch.dict(os.environ, {"TOKENFRUGAL_OLLAMA_AUTOSTART": "1"}), \
             mock.patch.object(ollama_launcher, "reachable", side_effect=[False, False, True]), \
             mock.patch.object(ollama_launcher, "binary", return_value="ollama"), \
             mock.patch.object(ollama_launcher.time, "sleep"), \
             mock.patch.object(ollama_launcher.subprocess, "Popen") as popen:
            self.assertTrue(ollama_launcher.ensure("http://localhost:11434/v1"))
            self.assertEqual(popen.call_args.args[0], ["ollama", "serve"])


if __name__ == "__main__":
    unittest.main()
