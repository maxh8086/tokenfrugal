"""Studio YouTube quota: Pacific day boundary, unit weights, and the estimated label."""
from datetime import datetime, timezone
from unittest import mock

from router import secrets_store, store, studio
from tests.studio_support import StudioEnv


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class PacificDayTests(StudioEnv):
    def test_pacific_day_follows_pdt_and_pst(self):
        self.assertEqual(studio.pacific_day(utc(2026, 7, 1, 6, 30)), "2026-06-30")  # 23:30 PDT
        self.assertEqual(studio.pacific_day(utc(2026, 7, 2, 7, 1)), "2026-07-02")  # 00:01 PDT
        self.assertEqual(studio.pacific_day(utc(2026, 1, 15, 7, 30)), "2026-01-14")  # 23:30 PST

    def test_pacific_day_rolls_over_at_the_march_dst_change(self):
        # DST starts 2026-03-08 at 10:00 UTC (02:00 PST)
        self.assertEqual(studio.pacific_day(utc(2026, 3, 8, 7, 30)), "2026-03-07")  # 23:30 PST
        self.assertEqual(studio.pacific_day(utc(2026, 3, 8, 9, 30)), "2026-03-08")  # 01:30 PST


class QuotaCountTests(StudioEnv):
    def test_search_costs_100_and_detail_costs_1(self):
        now = utc(2026, 7, 1, 20, 0)  # 13:00 PDT on 2026-07-01
        studio.record_quota_call("searchVideos", now=now)
        for _ in range(3):
            studio.record_quota_call("getVideoDetails", now=now)
        rows = {r["tool"]: r for r in store.quota_day("2026-07-01")}
        self.assertEqual((rows["searchVideos"]["calls"], rows["searchVideos"]["units"]), (1, 100))
        self.assertEqual((rows["getVideoDetails"]["calls"], rows["getVideoDetails"]["units"]), (3, 3))

    def test_counts_move_to_the_next_pacific_day(self):
        studio.record_quota_call("searchVideos", now=utc(2026, 7, 1, 20, 0))  # July 1 in Pacific
        studio.record_quota_call("searchVideos", now=utc(2026, 7, 2, 7, 30))  # July 2 in Pacific (00:30 PDT)
        self.assertEqual(store.quota_day("2026-07-01")[0]["units"], 100)
        self.assertEqual(store.quota_day("2026-07-02")[0]["units"], 100)

    def test_status_labels_the_quota_as_estimated(self):
        self.swap(secrets_store, "names", lambda: [])
        st = studio.status()
        self.assertIn("estimated", st["quota"]["note"])
        self.assertIn("(estimated)", studio.format_status(st))


if __name__ == "__main__":
    import unittest
    unittest.main()
