import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

from scripts.youtube_trends import discover


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_opener(payload):
    def opener(url, timeout=None):
        return FakeResponse(json.dumps(payload).encode("utf-8"))
    return opener


SAMPLE_PAYLOAD = {
    "items": [
        {
            "id": "vid1",
            "snippet": {
                "title": "First",
                "channelId": "ch1",
                "channelTitle": "Chan One",
                "publishedAt": "2026-01-01T00:00:00Z",
                "categoryId": "10",
                "tags": ["a", "b"],
            },
            "statistics": {"viewCount": "1234", "likeCount": "56"},
        },
        {
            "id": "vid2",
            "snippet": {
                "title": "Second",
                "channelId": "ch2",
                "channelTitle": "Chan Two",
                "publishedAt": "2026-01-02T00:00:00Z",
                "categoryId": "20",
            },
            "statistics": {"viewCount": "7", "likeCount": "8"},
        },
    ]
}


class YoutubeDiscoverTests(unittest.TestCase):
    def test_build_url_contains_chart_and_region_and_clamps_max(self):
        url = discover.build_url("KEY123", "US", 500)
        self.assertTrue(url.startswith(discover.API_URL + "?"))
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["chart"], ["mostPopular"])
        self.assertEqual(query["regionCode"], ["US"])
        self.assertEqual(query["maxResults"], ["50"])
        self.assertEqual(query["part"], ["snippet,statistics"])

    def test_parse_items_maps_fields(self):
        items = discover.parse_items(SAMPLE_PAYLOAD)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first["video_id"], "vid1")
        self.assertEqual(first["title"], "First")
        self.assertEqual(first["channel_id"], "ch1")
        self.assertEqual(first["channel_title"], "Chan One")
        self.assertEqual(first["published_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(first["category_id"], "10")
        self.assertEqual(first["tags"], ["a", "b"])
        self.assertEqual(first["views"], 1234)
        self.assertEqual(first["likes"], 56)

    def test_parse_items_tolerates_missing_statistics(self):
        payload = {"items": [{"id": "vid3", "snippet": {"title": "No stats"}}]}
        items = discover.parse_items(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["video_id"], "vid3")
        self.assertEqual(items[0]["views"], 0)
        self.assertEqual(items[0]["likes"], 0)
        self.assertEqual(items[0]["tags"], [])

    def test_fetch_raises_on_http_error_without_key(self):
        fake_key = "FAKESECRETKEY987"

        def opener(url, timeout=None):
            raise urllib.error.HTTPError(
                url, 403, "Forbidden", {},
                FakeResponse(b'{"error": "quota exceeded for ' + fake_key.encode() + b'"}'),
            )

        with self.assertRaises(RuntimeError) as ctx:
            discover.fetch_most_popular(fake_key, "US", 10, opener=opener)
        self.assertNotIn(fake_key, str(ctx.exception))
        self.assertIn("403", str(ctx.exception))

    def test_write_jsonl_one_object_per_line(self):
        items = discover.parse_items(SAMPLE_PAYLOAD)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.jsonl"
            discover.write_jsonl(items, out)
            lines = out.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["video_id"], "vid1")
        self.assertEqual(json.loads(lines[1])["video_id"], "vid2")


if __name__ == "__main__":
    unittest.main()
