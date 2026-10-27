import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import secrets_store


class SecretsStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(secrets_store, "SECRETS_DIR", Path(self._tmp.name) / "secrets")
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_put_get_roundtrip_writes_value_only(self):
        secrets_store.put("llm-api-key", "abc123")
        self.assertEqual(secrets_store.get("llm-api-key"), "abc123")
        raw = (secrets_store.SECRETS_DIR / "llm-api-key").read_bytes()
        self.assertEqual(raw, b"abc123")  # no trailing newline, no extra content

    def test_names_lists_files_only(self):
        self.assertEqual(secrets_store.names(), [])
        secrets_store.put("SONARQUBE_TOKEN", "sq")
        secrets_store.put("llm-api-key", "k")
        self.assertEqual(secrets_store.names(), ["SONARQUBE_TOKEN", "llm-api-key"])

    def test_get_unknown_returns_none(self):
        self.assertIsNone(secrets_store.get("missing"))

    def test_put_empty_value_rejected(self):
        with self.assertRaises(secrets_store.SecretStoreError):
            secrets_store.put("x", "")

    def test_invalid_names_cannot_leave_the_directory(self):
        for bad in ("../escape", "a/b", "", "with space", ".hidden"):
            with self.assertRaises(secrets_store.SecretStoreError):
                secrets_store.put(bad, "v")
            with self.assertRaises(secrets_store.SecretStoreError):
                secrets_store.get(bad)

    def test_delete(self):
        secrets_store.put("x", "1")
        self.assertTrue(secrets_store.delete("x"))
        self.assertIsNone(secrets_store.get("x"))
        self.assertEqual(secrets_store.names(), [])
        self.assertFalse(secrets_store.delete("x"))

    def test_resolve_docker_secret_ref(self):
        secrets_store.put("github-token", "tok")
        self.assertEqual(secrets_store.resolve("docker-secret:github-token"), "tok")

    def test_resolve_passes_plain_values_through(self):
        self.assertEqual(secrets_store.resolve("plain"), "plain")
        self.assertEqual(secrets_store.resolve(""), "")

    def test_resolve_missing_secret_fails_loudly(self):
        with self.assertRaises(secrets_store.SecretStoreError) as cm:
            secrets_store.resolve("docker-secret:nope")
        self.assertIn("nope", str(cm.exception))

    def test_resolve_env_mixes_refs_and_literals(self):
        secrets_store.put("tok", "v")
        self.assertEqual(
            secrets_store.resolve_env({"A": "docker-secret:tok", "B": "lit"}),
            {"A": "v", "B": "lit"},
        )

    def test_ensure_generated_creates_missing_only(self):
        secrets_store.put("SEARXNG_SECRET", "kept")
        created = secrets_store.ensure_generated()
        self.assertEqual(sorted(created), ["CRAWL4AI_API_TOKEN", "NEO4J_AUTH"])
        self.assertEqual(secrets_store.get("SEARXNG_SECRET"), "kept")
        self.assertTrue(secrets_store.get("NEO4J_AUTH").startswith("neo4j/"))
        self.assertEqual(secrets_store.ensure_generated(), [])

    def test_owner_only_permissions_where_posix(self):
        if os.name == "nt":
            self.skipTest("POSIX mode bits only")
        secrets_store.put("x", "1")
        self.assertEqual(stat.S_IMODE(os.stat(secrets_store.SECRETS_DIR / "x").st_mode), 0o600)

    def test_cli_export_paths_prints_directory_not_values(self):
        import io
        from contextlib import redirect_stdout
        secrets_store.put("SONARQUBE_TOKEN", "sq-value")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(secrets_store._cli(["export-paths"]), 0)
        self.assertEqual(out.getvalue().strip(), f"TF_SECRETS_DIR={secrets_store.SECRETS_DIR}")
        self.assertNotIn("sq-value", out.getvalue())


if __name__ == "__main__":
    unittest.main()
