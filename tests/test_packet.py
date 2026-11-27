import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pydantic import ValidationError

from router.checker import parse_accept
from router.packet import Packet, render, task_files


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs/designs/subagent-runtime/packet.schema.json"


class PacketTests(unittest.TestCase):
    def packet(self, **changes):
        fields = dict(v=1, goal="Fix parser", kind="edit", files=[{"path": "parser.py"}])
        return Packet.model_validate(fields | changes)

    def test_minimal(self):
        packet = self.packet()
        self.assertEqual(render(packet), "Goal: Fix parser\nFiles:\n- parser.py")
        self.assertEqual(task_files(packet), ["parser.py"])

    def test_all_fields_and_accept_round_trip(self):
        argv = ["python", "check script.py", "it's ready", ""]
        packet = self.packet(
            kind="analyze", requirements=["Keep order", "Check input"],
            files=[{"path": "a..b.py", "new": True, "lines": [2, 4]},
                   {"path": "src/main.py", "lines": [1, 1]}],
            accept=argv, env={"MODE": "test"}, must_not_change=["other.py"],
            context="Parser regression",
        )
        expected = (
            "Goal: Fix parser\nRequirements:\n- Keep order\n- Check input\nFiles:\n"
            "- a..b.py (new) lines 2-4\n- src/main.py lines 1-1\nContext: Parser regression\n"
            "Accept: `python 'check script.py' 'it'\"'\"'s ready' ''`"
        )
        prompt = render(packet)
        self.assertEqual(prompt, expected)
        self.assertEqual(task_files(packet), ["a..b.py", "src/main.py"])
        parsed = parse_accept(prompt.splitlines()[-1], "task_line", None)
        self.assertEqual(parsed.spec.argv, tuple(argv))

    def test_invalid_paths(self):
        for path in ("", "../outside", "src/../outside", "/abs", r"src\file", "C:file"):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                self.packet(files=[{"path": path}])

    def test_invalid_fields(self):
        for changes in (
            {"files": [{"path": "file"}] * 4}, {"files": []},
            {"files": [{"path": "file", "lines": [4, 2]}]},
            {"files": [{"path": "file", "lines": [0, 1]}]},
            {"files": [{"path": "file", "unknown": 1}]},
            {"unknown": 1}, {"v": 2}, {"kind": "other"}, {"goal": ""},
            {"goal": "g" * 401}, {"requirements": ["r"] * 6},
            {"requirements": ["r" * 201]}, {"accept": []},
            {"must_not_change": ["file"] * 11}, {"context": "c" * 1501},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.packet(**changes)

    def test_committed_schema(self):
        self.assertEqual(json.loads(SCHEMA.read_text(encoding="utf-8")), Packet.model_json_schema())

    def test_schema_cli_out_and_stdout(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        command = [sys.executable, "-m", "router.packet", "--schema"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "schema.json"
            subprocess.run(command + ["--out", str(out)], cwd=ROOT, env=env,
                           check=True, capture_output=True, timeout=120)
            data = out.read_bytes()
        self.assertNotIn(b"\r", data)
        text = data.decode("utf-8")
        self.assertEqual(json.loads(text), Packet.model_json_schema())
        printed = subprocess.run(command, cwd=ROOT, env=env, check=True,
                                 capture_output=True, timeout=120).stdout
        # Windows text-mode stdout turns "\n" into "\r\n"; normalise before comparing.
        self.assertEqual(printed.replace(b"\r\n", b"\n").decode("utf-8"), text)
