import os
import shlex
import tempfile
import unittest
from pathlib import Path

from router.checker import AcceptSpec, accept_from_task, parse_accept
from router.workspace import load_workspace

FALLBACK_ACCEPTS = [
    ("python -m unittest discover -s tests -t . -q", ("python", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"), ""),
    ("python -m unittest discover -s tests -t . -q", ("python", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"), ""),
    ('python -c "import scripts.story_film ..."', ("python", "-c", "import scripts.story_film ..."), ""),
    ("python -m unittest discover -s tests -t . -q", ("python", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"), ""),
    ('python -c "import ast; ast.parse(...)"', ("python", "-c", "import ast; ast.parse(...)"), ""),
    ('python -c "import ast; ast.parse(...)"', ("python", "-c", "import ast; ast.parse(...)"), ""),
    ("python -m unittest discover -s tests -t . -q", ("python", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"), ""),
    ("python -m unittest discover -s tests -t . -q", ("python", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"), ""),
    ("docker ebur128 measure on re-muxed film", None, "prose"),
    ("python -m unittest discover -s tests -t . -q + docker ebur128 on re-muxed scratch copy",
     ("python", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q", "+", "docker", "ebur128", "on", "re-muxed", "scratch", "copy"), ""),
    (r".venv\Scripts\python.exe -m unittest tests.test_youtube_discover -q",
     (r".venv\Scripts\python.exe", "-m", "unittest", "tests.test_youtube_discover", "-q"), ""),
    (r".venv\Scripts\python.exe -m py_compile scripts\youtube_trends\discover.py",
     (r".venv\Scripts\python.exe", "-m", "py_compile", r"scripts\youtube_trends\discover.py"), ""),
    (r".venv\Scripts\python.exe -m unittest tests.test_youtube_discover -q",
     (r".venv\Scripts\python.exe", "-m", "unittest", "tests.test_youtube_discover", "-q"), ""),
]


class AcceptParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = load_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_commands_prose_operators_and_labels(self):
        cases = [
            ("python -m unittest", ("python", "-m", "unittest"), ""),
            ("python -c 'print(\"ok\")'", ("python", "-c", 'print("ok")'), ""),
            ("make sure loader works", None, "prose"),
            ("pytest -q", None, "prose"),
            ("`pytest -q`", ("pytest", "-q"), ""),
            ("python x.py|tee", None, "refused: accept must be one command; put several steps in a script"),
            ("python x.py --tag=#1", ("python", "x.py", "--tag=#1"), ""),
            ('python -c "print(|)"', ("python", "-c", "print(|)"), ""),
            ('python "unterminated', None, "refused: unclosed quote"),
        ]
        for text, argv, note in cases:
            with self.subTest(text=text):
                result = parse_accept(text, "task_line", self.ws)
                self.assertEqual(result.note, note)
                self.assertEqual(result.spec.argv if result.spec else None, argv)

    def test_task_uses_last_acceptance_label(self):
        result = accept_from_task("Accept: python old.py\n  acceptance: python new.py", "", self.ws)
        self.assertEqual(result.spec.argv, ("python", "new.py"))

    def test_shlex_round_trip(self):
        argv = ["python", "-c", "it's fine | safe"]
        result = parse_accept(shlex.join(argv), "argument", self.ws)
        self.assertEqual(result.spec.argv, tuple(argv))

    def test_operator_refusal_table_and_unquoted_attached_operators(self):
        for operator in ("&&", "||", "|", ";", ">", ">>", "<"):
            with self.subTest(operator=operator):
                self.assertTrue(parse_accept("python x.py" + operator + "other", "argument", self.ws).note.startswith("refused:"))
        for command in ("python x.py|tee", "python a.py>out"):
            self.assertTrue(parse_accept(command, "argument", self.ws).note.startswith("refused:"))
        self.assertEqual(parse_accept('python -c "print(|)"', "argument", self.ws).spec.argv[-1], "print(|)")

    def test_acceptance_case_indentation_last_line_and_empty(self):
        result = accept_from_task(" Acceptance: python first.py\nacceptance: python last.py", "", self.ws)
        self.assertEqual(result.spec.argv, ("python", "last.py"))
        self.assertEqual(parse_accept("", "task_line", self.ws).note, "no accept")

    def test_fallback_attempt_accept_strings(self):
        for text, argv, note in FALLBACK_ACCEPTS:
            with self.subTest(text=text):
                result = parse_accept(text, "task_line", self.ws)
                self.assertEqual(result.note, note)
                self.assertEqual(result.spec.argv if result.spec else None, argv)


if __name__ == "__main__":
    unittest.main()
