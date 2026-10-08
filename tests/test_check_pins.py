import unittest
from unittest import mock

from scripts import check_pins as cp

LS = (
    "aaa\trefs/tags/2.9.0\n"
    "bbb\trefs/tags/2.10.0\n"
    "ccc\trefs/tags/2.10.0^{}\n"
    "ddd\trefs/tags/2.11.0-RC1\n"
)


class CheckPinsTest(unittest.TestCase):
    def test_latest_uses_numeric_order_and_peeled_sha(self):
        with mock.patch.object(cp.subprocess, "run", return_value=mock.Mock(stdout=LS)):
            self.assertEqual(cp.latest("r", r"^(\d+)\.(\d+)\.(\d+)$"), ("2.10.0", "ccc"))

    def test_no_match(self):
        with mock.patch.object(cp.subprocess, "run", return_value=mock.Mock(stdout=LS)):
            self.assertEqual(cp.latest("r", r"^x(\d+)\.(\d+)\.(\d+)$"), (None, None))


if __name__ == "__main__":
    unittest.main()
