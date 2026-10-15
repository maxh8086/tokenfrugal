import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import compose, reconnect

CATALOG = {
    "web": {"native": "crawl4ai", "compose": ["crawl4ai", "searxng"], "tools": []},
    "fs": {"profile": "ts-fs", "compose": [], "tools": []},
}


class RestartTests(unittest.TestCase):
    def test_unknown_name(self):
        r = asyncio.run(reconnect.restart_one("nope", CATALOG))
        self.assertFalse(r["ok"])

    def test_success_recreates_and_probes(self):
        with mock.patch.object(compose, "recreate", mock.AsyncMock()) as rec, \
                mock.patch.object(reconnect, "_probe", mock.AsyncMock(return_value=7)):
            r = asyncio.run(reconnect.restart_one("web", CATALOG))
        rec.assert_awaited_once_with(["crawl4ai", "searxng"])
        self.assertTrue(r["ok"])
        self.assertIn("7 tools", r["message"])

    def test_busy_backend_is_skipped(self):
        with mock.patch.dict(compose._users, {"crawl4ai": 1}), \
                mock.patch.object(compose, "recreate", mock.AsyncMock()) as rec:
            r = asyncio.run(reconnect.restart_one("web", CATALOG))
        rec.assert_not_awaited()
        self.assertFalse(r["ok"])
        self.assertIn("in use", r["message"])

    def test_error_is_reported_short(self):
        boom = compose.ComposeError("x" * 500)
        with mock.patch.object(compose, "recreate", mock.AsyncMock(side_effect=boom)):
            r = asyncio.run(reconnect.restart_one("web", CATALOG))
        self.assertFalse(r["ok"])
        self.assertLess(len(r["message"]), 200)

    def test_restart_all_reports_each(self):
        with mock.patch.object(compose, "recreate", mock.AsyncMock()), \
                mock.patch.object(reconnect, "_probe", mock.AsyncMock(side_effect=[3, RuntimeError("down")])):
            out = asyncio.run(reconnect.restart("all", CATALOG))
        self.assertFalse(out["ok"])
        self.assertEqual([r["ok"] for r in out["results"]], [True, False])
        self.assertIn("fs: RuntimeError: down", out["message"])


class PollTests(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        self.req, self.res = d / "reconnect_request.json", d / "reconnect_result.json"
        for n, v in (("REQUEST", self.req), ("RESULT", self.res)):
            p = mock.patch.object(reconnect, n, v)
            p.start()
            self.addCleanup(p.stop)

    def test_no_request(self):
        self.assertFalse(asyncio.run(reconnect.poll_once(CATALOG)))

    def test_request_is_claimed_and_result_written(self):
        self.req.write_text(json.dumps({"id": "a1", "target": "fs"}))
        with mock.patch.object(compose, "recreate", mock.AsyncMock()), \
                mock.patch.object(reconnect, "_probe", mock.AsyncMock(return_value=2)):
            self.assertTrue(asyncio.run(reconnect.poll_once(CATALOG)))
        out = json.loads(self.res.read_text())
        self.assertEqual((out["id"], out["ok"]), ("a1", True))
        self.assertFalse(self.req.exists())
        self.assertEqual(list(self.req.parent.glob("reconnect_request.*")), [])

    def test_bad_request_gives_error_result(self):
        self.req.write_text("not json")
        self.assertTrue(asyncio.run(reconnect.poll_once(CATALOG)))
        self.assertFalse(json.loads(self.res.read_text())["ok"])


if __name__ == "__main__":
    unittest.main()
