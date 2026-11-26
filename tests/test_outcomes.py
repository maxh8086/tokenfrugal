import unittest
from router.outcomes import (LEGACY_ERROR_KINDS, LEGACY_FAILURE_REASONS, NEXT, Next, Stop,
                              stop_from_legacy)

class OutcomeVocabulary(unittest.TestCase):
    def test_every_legacy_value_maps_and_stop_values_are_idempotent(self):
        for value in LEGACY_ERROR_KINDS:
            self.assertIsInstance(stop_from_legacy(None, value), Stop)
        for value in LEGACY_FAILURE_REASONS:
            self.assertIsInstance(stop_from_legacy(value, None), Stop)
        for value in Stop:
            self.assertEqual(stop_from_legacy(None, value.value), value)

    def test_error_kind_precedence_and_failure_reason_fallback(self):
        self.assertEqual(stop_from_legacy("connection", "error"), Stop.CONNECTION)
        self.assertEqual(NEXT[stop_from_legacy("connection", "error")], Next.RETRY_LATER)
        self.assertEqual(stop_from_legacy("no-tools", "step_timeout"), Stop.OUT_OF_TIME)
        self.assertEqual(stop_from_legacy("unknown", None), Stop.ERROR)
        self.assertEqual(stop_from_legacy("nonsense", "nonsense"), Stop.ERROR)

    def test_every_stop_has_next_and_serializes_as_plain_string(self):
        self.assertEqual(set(NEXT), set(Stop))
        for value in Stop:
            self.assertIsInstance(value.value, str)
            self.assertEqual(__import__("json").dumps(value), __import__("json").dumps(value.value))

if __name__ == "__main__":
    unittest.main()
