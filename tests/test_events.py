import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateway import events

CFG = {"models": {"builder": "m1"}, "divisions": {},
       "roles": {"builder": {"model": "builder", "profile": "p", "tools": ["a", "b"], "max_steps": 3}}}


class EventsTest(unittest.TestCase):
    def test_emit_and_roles(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.jsonl"
            with mock.patch.object(events, "EVENTS_PATH", path), mock.patch.object(events, "ROLES_PATH", path.with_name("roles.json")):
                events.emit("step", id="t1", n=2)
                line = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual((line["kind"], line["id"], line["n"]), ("step", "t1", 2))
                events.write_roles(CFG)
                self.assertEqual(json.loads(path.with_name("roles.json").read_text())["roles"][0]["model"], "m1")

    def test_client_event_and_roles_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.jsonl"
            with mock.patch.object(events, "EVENTS_PATH", path), mock.patch.object(events, "ROLES_PATH", path.with_name("roles.json")):
                events.emit("client", name="claude-code")
                self.assertEqual(json.loads(path.read_text(encoding="utf-8").splitlines()[0])["name"], "claude-code")
                events.write_roles(CFG)
                data = json.loads(path.with_name("roles.json").read_text())
                for key in ("roles", "divisions", "ui"):
                    self.assertIn(key, data)

    def test_emit_never_raises(self):
        with mock.patch.object(events, "EVENTS_PATH", Path("/nonexistent-dir/x/events.jsonl")):
            events.emit("step", id="t")


if __name__ == "__main__":
    unittest.main()
