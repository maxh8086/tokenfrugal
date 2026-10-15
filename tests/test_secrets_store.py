import json
import tempfile
import unittest
from pathlib import Path

import keyring
from keyring.backend import KeyringBackend
from keyring.backends import fail
from keyring.errors import PasswordDeleteError

from router import secrets_store


class FakeKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.store:
            raise PasswordDeleteError("not found")
        del self.store[(service, username)]


class SecretsStoreTest(unittest.TestCase):
    def setUp(self):
        self._orig_backend = keyring.get_keyring()
        self.backend = FakeKeyring()
        keyring.set_keyring(self.backend)
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_index = secrets_store.INDEX_FILE
        secrets_store.INDEX_FILE = Path(self._tmp.name) / "secret_names.json"

    def tearDown(self):
        keyring.set_keyring(self._orig_backend)
        secrets_store.INDEX_FILE = self._orig_index
        self._tmp.cleanup()

    def test_put_get_roundtrip_and_index(self):
        secrets_store.put("llm-api-key", "abc123")
        self.assertEqual(secrets_store.get("llm-api-key"), "abc123")
        self.assertEqual(secrets_store.names(), ["llm-api-key"])
        self.assertEqual(json.loads(secrets_store.INDEX_FILE.read_text(encoding="utf-8")), ["llm-api-key"])

    def test_index_holds_names_only(self):
        secrets_store.put("github-token", "ghp_secretvalue")
        self.assertNotIn("ghp_secretvalue", secrets_store.INDEX_FILE.read_text(encoding="utf-8"))

    def test_get_unknown_returns_none(self):
        self.assertIsNone(secrets_store.get("missing"))

    def test_put_empty_value_rejected(self):
        with self.assertRaises(secrets_store.SecretStoreError):
            secrets_store.put("x", "")

    def test_delete(self):
        secrets_store.put("x", "1")
        self.assertTrue(secrets_store.delete("x"))
        self.assertIsNone(secrets_store.get("x"))
        self.assertEqual(secrets_store.names(), [])
        self.assertFalse(secrets_store.delete("x"))

    def test_resolve_keyring_ref(self):
        secrets_store.put("github-token", "tok")
        self.assertEqual(secrets_store.resolve("keyring:github-token"), "tok")

    def test_resolve_passes_plain_values_through(self):
        self.assertEqual(secrets_store.resolve("plain"), "plain")
        self.assertEqual(secrets_store.resolve(""), "")

    def test_resolve_missing_secret_fails_loudly(self):
        with self.assertRaises(secrets_store.SecretStoreError) as cm:
            secrets_store.resolve("keyring:nope")
        self.assertIn("nope", str(cm.exception))

    def test_resolve_env_mixes_refs_and_literals(self):
        secrets_store.put("tok", "v")
        self.assertEqual(
            secrets_store.resolve_env({"A": "keyring:tok", "B": "lit"}),
            {"A": "v", "B": "lit"},
        )

    def test_no_usable_backend_is_an_error_not_a_plaintext_fallback(self):
        keyring.set_keyring(fail.Keyring())
        with self.assertRaises(secrets_store.SecretStoreError):
            secrets_store.put("x", "1")
        with self.assertRaises(secrets_store.SecretStoreError):
            secrets_store.get("x")
        self.assertFalse(secrets_store.INDEX_FILE.exists())

    def test_ensure_generated_creates_missing_only(self):
        secrets_store.put("SEARXNG_SECRET", "kept")
        created = secrets_store.ensure_generated()
        self.assertEqual(sorted(created), ["CRAWL4AI_API_TOKEN", "NEO4J_AUTH"])
        self.assertEqual(secrets_store.get("SEARXNG_SECRET"), "kept")
        self.assertTrue(secrets_store.get("NEO4J_AUTH").startswith("neo4j/"))
        self.assertEqual(secrets_store.ensure_generated(), [])

    def test_export_env_returns_only_stored_backend_names(self):
        secrets_store.put("SONARQUBE_TOKEN", "sq")
        secrets_store.put("unrelated", "x")
        self.assertEqual(secrets_store.export_env(), {"SONARQUBE_TOKEN": "sq"})


if __name__ == "__main__":
    unittest.main()
