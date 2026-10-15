import unittest
from unittest import mock

from router import loop


class TokenCapture(unittest.TestCase):
    def test_peak_tracks_largest_prompt_and_take_usage_keeps_done(self):
        loop.USAGE.pop("tp", None)
        usage = lambda i: mock.Mock(prompt_tokens=i, completion_tokens=1)  # noqa: E731
        for n in (100, 900, 300):
            loop._count("tp", mock.Mock(usage=usage(n)), [], mock.Mock(content=""), 0.1)
        u = loop.take_usage("tp")
        self.assertEqual(u["peak"], 900)
        self.assertIs(loop.DONE["tp"], u)


if __name__ == "__main__":
    unittest.main()
