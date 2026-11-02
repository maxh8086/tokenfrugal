"""Offline tests for the --only section parsing in scripts/bench.py. No model, router or container is contacted."""
import argparse
import contextlib
import io
import unittest

from scripts import bench


def _parser():
    return argparse.ArgumentParser()


class ParseOnlyTest(unittest.TestCase):
    def test_unknown_name_exits_nonzero_and_names_it(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            bench.parse_only(_parser(), "nosuchsection")
        self.assertNotEqual(cm.exception.code, 0)
        msg = err.getvalue()
        self.assertIn("nosuchsection", msg)
        self.assertIn("valid sections", msg)
        self.assertIn(", ".join(bench.SECTIONS), msg)

    def test_one_unknown_name_in_a_list_fails(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            bench.parse_only(_parser(), "roles,nosuchsection")

    def test_known_names_pass_through(self):
        self.assertEqual(bench.parse_only(_parser(), "roles,output"), ["roles", "output"])
        self.assertEqual(bench.parse_only(_parser(), ",".join(bench.SECTIONS)), bench.SECTIONS)


if __name__ == "__main__":
    unittest.main()
