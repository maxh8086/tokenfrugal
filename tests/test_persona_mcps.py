import json
import os
import tempfile
import unittest
from pathlib import Path

from gateway import config


class PersonaMcps(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self._old = config.PERSONA_MCPS_FILE, config.PERSONA_MODELS_FILE
        config.PERSONA_MODELS_FILE = tmp / "m.json"
        config.PERSONA_MCPS_FILE = tmp / "c.json"

    def tearDown(self):
        config.PERSONA_MCPS_FILE, config.PERSONA_MODELS_FILE = self._old

    def test_catalog_default_persona_listed(self):
        cat = config.load_catalog()
        for t in cat["profile_types"].values():
            self.assertIn(t["default"], t["personas"])
        for m in cat["mcps"].values():
            self.assertTrue(m.get("profile") or m.get("native"))

    def test_selection_builds_union_toolkit(self):
        config.PERSONA_MCPS_FILE.write_text(json.dumps({"finance-analyst": ["fetch", "web-search", "filesystem"]}))
        r = config.resolve_role("finance-analyst", config.load_personas())
        self.assertEqual(r["profile"], ["docs", "build"])
        self.assertIn("web_search", r["tools"])
        self.assertEqual(r["native"], ["crawl4ai"])
        self.assertEqual(r["compose"], ["crawl4ai", "searxng"])

    def test_no_selection_keeps_role(self):
        r = config.resolve_role("finance-analyst", config.load_personas())
        self.assertEqual(r["profile"], "docs")

    def test_disabled_by_env(self):
        config.PERSONA_MCPS_FILE.write_text(json.dumps({"finance-analyst": ["fetch"]}))
        os.environ["TOKENFRUGAL_PERSONA_MODELS"] = "0"
        try:
            r = config.resolve_role("finance-analyst", config.load_personas())
            self.assertEqual(r["profile"], "docs")
        finally:
            del os.environ["TOKENFRUGAL_PERSONA_MODELS"]

    def test_default_mcps_from_role(self):
        cfg = config.load_personas()
        names = config.default_mcps(config.resolve_role("engineering-backend-architect", cfg), config.load_catalog())
        self.assertIn("synaptree", names)
        self.assertIn("filesystem", names)

    def test_finance_has_web_search_by_default(self):
        cfg = config.load_personas()
        r = config.resolve_role("finance-analyst", cfg)
        self.assertEqual(r["role"], "finance")
        self.assertIn("web-search", config.default_mcps(r, config.load_catalog()))

    def test_designer_and_data_tools_are_real(self):
        cfg = config.load_personas()
        self.assertIn("execute_code", config.resolve_role("design-ui-designer", cfg)["tools"])
        self.assertNotIn("query", config.resolve_role("engineering-data-engineer", cfg)["tools"])


if __name__ == "__main__":
    unittest.main()
