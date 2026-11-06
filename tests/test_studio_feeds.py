"""Studio RSS feed list: scheme and address checks, saved list limits, and the secret warning (names only)."""
import socket
from unittest import mock

from router import config, secrets_store, studio
from tests.studio_support import StudioEnv

PUBLIC = "93.184.216.34"
DNS = {
    "news.example": [PUBLIC],
    "internal.example": ["10.1.2.3"],
    "mixed.example": [PUBLIC, "192.168.0.9"],
}


def fake_dns(host, port, *args, **kwargs):
    if host not in DNS:
        raise socket.gaierror("no such host")
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in DNS[host]]


class FeedCheckTests(StudioEnv):
    def setUp(self):
        super().setUp()
        self.swap(studio.socket, "getaddrinfo", mock.MagicMock(side_effect=fake_dns))

    def refused(self, url):
        with self.assertRaises(studio.FeedRefused):
            studio.check_feed_url(url)

    def test_refuses_non_http_schemes(self):
        for url in ("ftp://news.example/feed", "file:///etc/passwd", "gopher://news.example/x"):
            self.refused(url)

    def test_refuses_loopback_private_and_link_local_addresses(self):
        for url in ("http://localhost/rss", "http://app.localhost/rss", "http://127.0.0.1/feed",
                    "http://[::1]/feed", "http://10.0.0.5/rss", "http://169.254.169.254/latest",
                    "https://internal.example/rss", "https://mixed.example/rss"):
            self.refused(url)

    def test_refuses_overlong_urls(self):
        self.refused("https://news.example/" + "a" * config.RSS_MAX_URL)

    def test_accepts_a_public_https_feed_and_saves_it(self):
        self.assertEqual(studio.check_feed_url("https://news.example/feed.xml"), "https://news.example/feed.xml")
        self.assertIn("feed saved", studio.save_feed("https://news.example/feed.xml"))
        self.assertEqual(studio.load_feeds(), ["https://news.example/feed.xml"])
        self.assertIn("already saved", studio.save_feed("https://news.example/feed.xml"))

    def test_saved_list_has_a_limit(self):
        self.swap(studio, "RSS_MAX_FEEDS", 1)
        studio.save_feed("https://news.example/feed.xml")
        with self.assertRaises(studio.FeedRefused):
            studio.save_feed("https://news.example/other.xml")

    def test_start_save_feed_reports_a_refusal(self):
        self.assertTrue(studio.start("save_feed", feed_url="file:///etc/passwd").startswith("feed refused"))


class SecretWarningTests(StudioEnv):
    def test_warning_names_the_missing_secret_and_nothing_else(self):
        self.swap(secrets_store, "names", lambda: ["SOMETHING_ELSE"])
        missing = studio.secret_report(["youtube"])
        self.assertEqual(missing, ["YOUTUBE_API_KEY"])
        for name in missing:
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)

    def test_no_warning_for_sources_without_secrets(self):
        self.swap(secrets_store, "names", lambda: [])
        self.assertEqual(studio.secret_report(["reddit-hn", "rss"]), [])


if __name__ == "__main__":
    import unittest
    unittest.main()
