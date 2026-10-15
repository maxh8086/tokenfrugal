import unittest
from unittest import mock

from router import summarize


class ShortAnswers(unittest.TestCase):
    def test_short_text_is_returned_untouched(self):
        with mock.patch.object(summarize._client.chat.completions, "create", side_effect=AssertionError("model called")):
            self.assertEqual(summarize.summarize("m", "router/config.py, line 166", "find"), "router/config.py, line 166")


if __name__ == "__main__":
    unittest.main()
