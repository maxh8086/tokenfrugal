import contextlib
import io
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from scripts import doctor


class DoctorConfig(unittest.TestCase):
    def run_doctor(self, config_text=None, router_path=None):
        home = Path(tempfile.mkdtemp())
        self.home = home
        codex = home / ".codex" / "config.toml"
        if config_text is not None:
            codex.parent.mkdir(parents=True)
            codex.write_text(config_text, encoding="utf-8")
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(Path, "home", return_value=home))
            stack.enter_context(mock.patch.object(doctor.shutil, "which", side_effect=lambda name: router_path if name == "tokenfrugal-router" else name))
            stack.enter_context(mock.patch("router.preflight.missing_programs", return_value=[]))
            stack.enter_context(mock.patch("router.preflight.stage_model_gaps", return_value=[]))
            stack.enter_context(mock.patch.object(doctor, "gpu_container_ok", return_value=True))
            stack.enter_context(mock.patch.object(doctor, "driver_check", lambda report: None))
            stack.enter_context(mock.patch.object(doctor, "wslconfig_check", lambda report: None))
            stack.enter_context(mock.patch.object(doctor, "required_models", return_value=[]))
            stack.enter_context(mock.patch.object(doctor.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="")))
            stack.enter_context(mock.patch.object(doctor.urllib.request, "urlopen", side_effect=OSError("offline")))
            with contextlib.redirect_stdout(output):
                doctor.main()
        return output.getvalue()

    def test_timeout_uses_role_names_and_config_task_default(self):
        out = self.run_doctor()
        self.assertIn("tool_timeout_sec = 548", out)
        self.assertIn("MCP_TOOL_TIMEOUT=548000", out)

    def test_timeout_is_read_from_server_table(self):
        self.assertIn("tool_timeout_sec = 548", self.run_doctor("tool_timeout_sec = 9999\n"))
        self.assertNotIn("Add this under [mcp_servers.tokenfrugal]", self.run_doctor('[mcp_servers.tokenfrugal]\ntool_timeout_sec = 548\n'))
        self.assertIn("tool_timeout_sec = 548", self.run_doctor('[mcp_servers.tokenfrugal]\ntool_timeout_sec = 547\n'))

    def test_broken_toml_is_reported_as_missing_timeout(self):
        self.assertIn("tool_timeout_sec = 548", self.run_doctor("[broken\n"))

    def test_router_command_is_valid_toml_with_spaces_in_path(self):
        router = Path(tempfile.mkdtemp()) / "Token Frugal" / "tokenfrugal-router"
        out = self.run_doctor(router_path=str(router))
        block = "\n".join(out.split("Add this to your Codex config:\n", 1)[1].splitlines()[:3])
        parsed = tomllib.loads(block)
        self.assertEqual(parsed["mcp_servers"]["tokenfrugal"]["command"], router.resolve().as_posix())

    @unittest.skipUnless(os.name == "nt", "backslash path is Windows only")
    def test_router_command_converts_windows_backslash_path(self):
        out = self.run_doctor(router_path=r"C:\Users\Me\Token Frugal\tokenfrugal-router.exe")
        block = "\n".join(out.split("Add this to your Codex config:\n", 1)[1].splitlines()[:3])
        parsed = tomllib.loads(block)
        self.assertEqual(parsed["mcp_servers"]["tokenfrugal"]["command"], "C:/Users/Me/Token Frugal/tokenfrugal-router.exe")

    def test_missing_router_warns_without_failing(self):
        out = self.run_doctor(router_path=None)
        self.assertIn("[warn] tokenfrugal-router is not on PATH", out)
        self.assertIn("pip install -e .", out)

    def test_doctor_writes_no_files(self):
        original = "tool_timeout_sec = 547" + chr(10)
        self.run_doctor(original)
        files = sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob("*") if p.is_file())
        self.assertEqual(files, [".codex/config.toml"])
        self.assertEqual((self.home / ".codex" / "config.toml").read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
