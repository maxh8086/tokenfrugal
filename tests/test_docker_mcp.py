import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import claude_import, docker_mcp, secrets_store

PROFILE = "name: build\nservers:\n  - fs\nvolume: __WORKSPACE__:/w\n"


class GatewayArgvTests(unittest.TestCase):
    def test_argv_for_profile(self):
        self.assertEqual(docker_mcp.gateway_argv("build", "2", "4Gb", docker="D"),
                         ["D", "mcp", "gateway", "run", "--profile", "build", "--cpus", "2", "--memory", "4Gb"])

    def test_missing_docker_binary_is_clear_error(self):
        with mock.patch("router.docker_mcp.shutil.which", return_value=None):
            with self.assertRaises(docker_mcp.DockerMcpError) as c:
                docker_mcp.gateway_argv("build")
        self.assertIn("docker was not found", str(c.exception))


class ProfileTests(unittest.TestCase):
    def _write(self, text):
        d = Path(tempfile.mkdtemp())
        p = d / "p.yaml"
        p.write_text(text, encoding="utf-8")
        return p

    def test_workspace_substitution(self):
        self.assertIn("C:/ws:/w", docker_mcp.profile_text(self._write(PROFILE), "C:/ws"))
        self.assertNotIn("__WORKSPACE__", docker_mcp.profile_text(self._write(PROFILE), "C:/ws"))

    def test_load_profile(self):
        self.assertEqual(docker_mcp.load_profile(self._write(PROFILE), "X")["servers"], ["fs"])

    def test_load_profile_rejects_non_profile(self):
        with self.assertRaises(docker_mcp.DockerMcpError):
            docker_mcp.load_profile(self._write("a: 1\n"), "X")

    def test_repo_profiles_load(self):
        for p in sorted(Path("profiles").glob("*.yaml")):
            self.assertIn("servers", docker_mcp.load_profile(p, "C:/ws"), p.name)


class ParamTests(unittest.TestCase):
    def test_no_params_no_commands(self):
        self.assertEqual(docker_mcp.param_commands("p", None, docker="D"), [])

    def test_config_and_secret_commands(self):
        params = {"config": {"srv.key": "v1", "srv.tok": "keyring:T"}, "secrets": {"NAME": "keyring:NAME"}}
        with mock.patch("router.docker_mcp.secrets_store.resolve", side_effect=lambda v: "R:" + v):
            cmds = docker_mcp.param_commands("p", params, docker="D")
        self.assertEqual(cmds[0], (["D", "mcp", "profile", "config", "p", "--set", "srv.key=R:v1", "--set", "srv.tok=R:keyring:T"], None))
        self.assertEqual(cmds[1], (["D", "mcp", "secret", "set", "NAME"], "R:keyring:NAME"))

    def test_secret_never_in_argv(self):
        with mock.patch("router.docker_mcp.secrets_store.resolve", return_value="s3cret"):
            cmds = docker_mcp.param_commands("p", {"secrets": {"N": "keyring:N"}}, docker="D")
        self.assertNotIn("s3cret", " ".join(cmds[0][0]))
        self.assertEqual(cmds[0][1], "s3cret")

    def test_literal_secret_rejected(self):
        with self.assertRaises(docker_mcp.DockerMcpError):
            docker_mcp.param_commands("p", {"secrets": {"N": "plain"}}, docker="D")

    def test_apply_runs_commands(self):
        with mock.patch("router.docker_mcp.docker_bin", return_value="D"), \
             mock.patch("router.docker_mcp.secrets_store.resolve", side_effect=lambda v: v), \
             mock.patch("router.docker_mcp.subprocess.run", return_value=mock.Mock(returncode=0)) as run:
            docker_mcp.apply_params("p", {"config": {"a.b": "c"}})
        self.assertEqual(run.call_args.args[0][:5], ["D", "mcp", "profile", "config", "p"])

    def test_apply_failure_raises(self):
        with mock.patch("router.docker_mcp.docker_bin", return_value="D"), \
             mock.patch("router.docker_mcp.subprocess.run", return_value=mock.Mock(returncode=1, stderr="boom", stdout="")):
            with self.assertRaises(docker_mcp.DockerMcpError):
                docker_mcp.apply_params("p", {"config": {"a.b": "c"}})

    def test_apply_missing_docker(self):
        with mock.patch("router.docker_mcp.docker_bin", return_value="D"), \
             mock.patch("router.docker_mcp.subprocess.run", side_effect=FileNotFoundError("x")):
            with self.assertRaises(docker_mcp.DockerMcpError):
                docker_mcp.apply_params("p", {"config": {"a.b": "c"}})


class ClaudeImportTests(unittest.TestCase):
    DOC = {"mcpServers": {"memory": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"],
                                     "env": {"TOKEN": "keyring:TOKEN"}}}}

    def test_convert(self):
        out = claude_import.convert(self.DOC)
        self.assertEqual(out["servers"]["memory"], {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"],
                                                    "env": {"TOKEN": "keyring:TOKEN"}})
        self.assertEqual(out["mcps"]["memory"]["native"], "memory")

    def test_rejects_url_servers_and_bad_names(self):
        with self.assertRaises(ValueError):
            claude_import.convert({"mcpServers": {"x": {"url": "http://h"}}})
        with self.assertRaises(ValueError):
            claude_import.convert({"mcpServers": {"Bad Name": {"command": "c"}}})
        with self.assertRaises(ValueError):
            claude_import.convert({})

    def test_install_roundtrip(self):
        p = Path(tempfile.mkdtemp()) / "i.json"
        self.assertEqual(claude_import.install(self.DOC, p), ["memory"])
        self.assertIn("memory", claude_import.load(p)["servers"])
        json.loads(p.read_text(encoding="utf-8"))

    def test_load_missing_file(self):
        self.assertEqual(claude_import.load(Path("nope.json")), {"servers": {}, "mcps": {}})


class ResolveRefTests(unittest.TestCase):
    def test_resolve_passthrough_for_plain(self):
        self.assertEqual(secrets_store.resolve("plain"), "plain")


if __name__ == "__main__":
    unittest.main()
