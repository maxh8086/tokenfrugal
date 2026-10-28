"""Every native server a role lists is defined, and the synaptree roles really get the synaptree server.

Offline: reads router/tf-roles.yaml and router/config.py only. No container or model is started.
"""
import unittest

from router.config import NATIVE_BACKENDS, NATIVE_SERVERS, load_tf_roles

CFG = load_tf_roles()
ROLES = {**CFG["roles"], **CFG.get("pending_roles", {})}
SYNAPTREE_ROLES = sorted(n for n, r in ROLES.items() if "synaptree" in (r.get("native") or []))


class NativeWiringTest(unittest.TestCase):
    def test_every_listed_native_server_is_defined(self):
        missing = {n: [s for s in (r.get("native") or []) if s not in NATIVE_SERVERS] for n, r in ROLES.items()}
        self.assertEqual({n: m for n, m in missing.items() if m}, {})

    def test_synaptree_roles_are_the_expected_set(self):
        # Changing this list is a deliberate wiring change; update it with the role.
        self.assertEqual(SYNAPTREE_ROLES, ["analyzer", "builder", "code-l6", "debugger", "reviewer",
                                           "ui-a11y-check", "ui-tokens-check"])

    def test_synaptree_roles_allow_at_least_one_synaptree_tool(self):
        graph_tools = {"search_graph", "search_code", "trace_path", "get_code_snippet", "query_graph", "get_architecture"}
        for name in SYNAPTREE_ROLES:
            tools = set(ROLES[name].get("tools") or [])
            self.assertTrue(tools & graph_tools, f"{name} lists synaptree but allows no synaptree tool")

    def test_synaptree_backends_are_declared_for_ensure(self):
        # The container ensure step (mcp_client.ensure_backend) starts these before a synaptree role opens.
        self.assertIn("synaptree", NATIVE_BACKENDS)
        self.assertTrue(NATIVE_BACKENDS["synaptree"])
        self.assertIn("synaptree", NATIVE_SERVERS)


if __name__ == "__main__":
    unittest.main()
