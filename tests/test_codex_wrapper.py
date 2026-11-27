import json
import re
import shlex
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL_OPERATORS = ("&&", "||", "|", ";", ">", "<", "&")
PATH_SEPARATORS = "/" + chr(92)


class CodexWrapperTest(unittest.TestCase):
    def example_line(self):
        wrapper = tomllib.loads((ROOT / ".codex/agents/tokenfrugal.toml").read_text(encoding="utf-8"))
        lines = [line for line in wrapper["developer_instructions"].splitlines() if "dispatch_task(agent=" in line]
        self.assertEqual(len(lines), 1)
        return lines[0]

    def test_example_call_names_every_required_dispatch_argument(self):
        from router.server import REQUIRED_ARGS

        names = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", self.example_line()))
        self.assertTrue(set(REQUIRED_ARGS).issubset(names))

    def test_example_call_names_accept_as_one_command_without_shell_operators(self):
        match = re.search(r'accept="([^"]*)"', self.example_line())
        self.assertIsNotNone(match)
        command = match.group(1)
        for operator in SHELL_OPERATORS:
            self.assertNotIn(operator, command)
        self.assertTrue(shlex.split(command))

    def test_client_commands_have_no_path_separator_and_no_args(self):
        config = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
        mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        codex = config["mcp_servers"]["tokenfrugal"]
        client = mcp["mcpServers"]["tokenfrugal"]
        for server in (codex, client):
            self.assertFalse(set(server["command"]) & set(PATH_SEPARATORS))
            self.assertEqual(server["command"], "tokenfrugal-router")
            self.assertEqual(server["args"], [])
        self.assertEqual(client["cwd"], ".")

    def test_codex_config_sets_no_workspace_env_and_points_to_doctor(self):
        text = (ROOT / ".codex/config.toml").read_text(encoding="utf-8")
        config = tomllib.loads(text)
        self.assertNotIn("env", config["mcp_servers"]["tokenfrugal"])
        self.assertNotIn("CC_WORKSPACE", text)
        self.assertIn("scripts/doctor.py", text)


if __name__ == "__main__":
    unittest.main()
