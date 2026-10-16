import json
import os
import tempfile
import unittest
from pathlib import Path

from router import config


class AgentMcps(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self._old = config.AGENT_MCPS_FILE, config.AGENT_MODELS_FILE
        config.AGENT_MODELS_FILE = tmp / "m.json"
        config.AGENT_MCPS_FILE = tmp / "c.json"

    def tearDown(self):
        config.AGENT_MCPS_FILE, config.AGENT_MODELS_FILE = self._old

    def test_catalog_default_agent_listed(self):
        cat = config.load_catalog()
        for t in cat["profile_types"].values():
            self.assertIn(t["default"], t["agents"])
        for m in cat["mcps"].values():
            self.assertTrue(m.get("profile") or m.get("native"))

    def test_selection_builds_union_toolkit(self):
        config.AGENT_MCPS_FILE.write_text(json.dumps({"finance-analyst": ["fetch", "web-search", "filesystem"]}))
        r = config.resolve_role("finance-analyst", config.load_agents())
        self.assertEqual(r["profile"], ["docs", "build"])
        self.assertIn("web_search", r["tools"])
        self.assertEqual(r["native"], ["crawl4ai"])
        self.assertEqual(r["compose"], ["crawl4ai", "searxng"])

    def test_no_selection_keeps_role(self):
        r = config.resolve_role("finance-analyst", config.load_agents())
        self.assertEqual(r["profile"], ["build", "docs"])

    def test_disabled_by_env(self):
        config.AGENT_MCPS_FILE.write_text(json.dumps({"finance-analyst": ["fetch"]}))
        os.environ["TOKENFRUGAL_AGENT_MODELS"] = "0"
        try:
            r = config.resolve_role("finance-analyst", config.load_agents())
            self.assertEqual(r["profile"], ["build", "docs"])
        finally:
            del os.environ["TOKENFRUGAL_AGENT_MODELS"]

    def test_default_mcps_from_role(self):
        cfg = config.load_agents()
        names = config.default_mcps(config.resolve_role("engineering-backend-architect", cfg), config.load_catalog())
        self.assertIn("synaptree", names)
        self.assertIn("filesystem", names)

    def test_finance_has_web_search_by_default(self):
        cfg = config.load_agents()
        r = config.resolve_role("finance-analyst", cfg)
        self.assertEqual(r["role"], "finance")
        self.assertIn("web-search", config.default_mcps(r, config.load_catalog()))

    def test_designer_and_data_tools_are_real(self):
        cfg = config.load_agents()
        self.assertIn("execute_code", config.resolve_role("design-ui-designer", cfg)["tools"])
        self.assertNotIn("query", config.resolve_role("engineering-data-engineer", cfg)["tools"])


if __name__ == "__main__":
    unittest.main()
