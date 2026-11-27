"""Replay task fb-009: youtube_trends.discover helpers and main() (offline; network and secrets mocked)."""
import contextlib
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
from unittest import mock

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

API_KEY = "fake-key-4471"
API_URL = "https://www.googleapis.com/youtube/v3/videos"
PAYLOAD = {"items": [{"id": "abc123", "snippet": {
    "title": "Hello", "channelId": "UC1", "channelTitle": "Chan",
    "publishedAt": "2026-01-02T03:04:05Z", "categoryId": "28", "tags": ["a", "b"]},
    "statistics": {"viewCount": "1234", "likeCount": "56"}}]}
EXPECTED_ITEM = {"video_id": "abc123", "title": "Hello", "channel_id": "UC1", "channel_title": "Chan",
                 "published_at": "2026-01-02T03:04:05Z", "category_id": "28", "tags": ["a", "b"],
                 "views": 1234, "likes": 56}


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def fail(message):
    print("FAIL:", message)
    return 1


def query_of(url):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def check_build_url(d):
    url = d.build_url(API_KEY, "IN", 500)
    if d.API_URL != API_URL:
        return "API_URL is %r" % (d.API_URL,)
    if not url.startswith(API_URL + "?"):
        return "build_url does not start with API_URL and a query"
    query = query_of(url)
    wanted = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": "IN",
              "maxResults": "50", "key": API_KEY}
    for name, value in wanted.items():
        if query.get(name) != [value]:
            return "query %s is %r, expected %r" % (name, query.get(name), value)
    for raw, want in ((500, "50"), (0, "1"), (-3, "1"), (20, "20")):
        got = query_of(d.build_url(API_KEY, "US", raw)).get("maxResults")
        if got != [want]:
            return "max_results %r gave maxResults %r, expected %r" % (raw, got, want)
    return None


def check_parse_items(d):
    parsed = d.parse_items(PAYLOAD)
    if parsed != [EXPECTED_ITEM]:
        return "parse_items returned %r" % (parsed,)
    if d.parse_items({}) != []:
        return "parse_items({}) is not []"
    sparse = d.parse_items({"items": [{"id": "x1", "snippet": {"title": "T"}}]})
    if len(sparse) != 1:
        return "item with missing fields was not kept"
    item = sparse[0]
    if item.get("video_id") != "x1":
        return "video_id is %r" % (item.get("video_id"),)
    if item.get("views") != 0 or item.get("likes") != 0:
        return "missing statistics gave views %r and likes %r" % (item.get("views"), item.get("likes"))
    if item.get("tags") != []:
        return "missing tags is not []"
    return None


def check_fetch(d):
    calls = []

    def opener(url, timeout=None):
        calls.append((url, timeout))
        return FakeResponse(json.dumps(PAYLOAD).encode("utf-8"))

    items = d.fetch_most_popular(API_KEY, "US", 10, opener=opener)
    if items != [EXPECTED_ITEM]:
        return "fetch_most_popular returned %r" % (items,)
    if len(calls) != 1:
        return "opener called %d times" % len(calls)
    url, timeout = calls[0]
    if timeout != 20:
        return "opener timeout is %r, expected 20" % (timeout,)
    if query_of(url).get("maxResults") != ["10"]:
        return "fetch URL maxResults is wrong"

    def failing(url, timeout=None):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {},
                                     io.BytesIO(b"{\"error\": {\"message\": \"quota exceeded\"}}"))

    message = None
    try:
        d.fetch_most_popular(API_KEY, "US", 10, opener=failing)
    except RuntimeError as exc:
        message = str(exc)
    except Exception as exc:
        return "HTTP error raised %r, expected RuntimeError" % (exc,)
    if message is None:
        return "HTTP error did not raise RuntimeError"
    if API_KEY in message:
        return "API key appears in the error message"
    if "403" not in message:
        return "status code missing from the error message"
    if "quota exceeded" not in message:
        return "body text missing from the error message"
    return None


def check_write_jsonl(d, tmp):
    items = [{"video_id": "a", "title": "Café"}, {"video_id": "b", "views": 3}]
    path = os.path.join(tmp, "out.jsonl")
    d.write_jsonl(items, path)
    with open(path, "rb") as handle:
        raw = handle.read()
    lines = raw.decode("utf-8").splitlines()
    if len(lines) != 2:
        return "expected 2 lines, got %d" % len(lines)
    if [json.loads(line) for line in lines] != items:
        return "lines do not round-trip to the items"
    if "Café".encode("utf-8") not in raw:
        return "non-ASCII text was escaped"
    return None


def check_main(d, tmp):
    out = os.path.join(tmp, "videos.jsonl")
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch("router.secrets_store.get", return_value=None) as get:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = d.main(["--out", out])
    if code != 2:
        return "missing key returned %r, expected 2" % (code,)
    if "yt-key is not set" not in stderr.getvalue():
        return "missing-key message not on stderr"
    if "yt-key" not in str(get.call_args):
        return "secrets_store.get was not asked for yt-key"
    if os.path.exists(out):
        return "file written without a key"

    fetched = [EXPECTED_ITEM, dict(EXPECTED_ITEM, video_id="zz9")]
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch("router.secrets_store.get", return_value=API_KEY), \
            mock.patch.object(d, "fetch_most_popular", return_value=fetched) as fetch, \
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")), \
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = d.main(["--region", "US", "--max", "5", "--out", out])
    if code != 0:
        return "main returned %r on success" % (code,)
    if API_KEY in stdout.getvalue() + stderr.getvalue():
        return "API key was printed"
    if "wrote 2 videos to" not in stdout.getvalue():
        return "success message missing"
    args = list(fetch.call_args.args) + list(fetch.call_args.kwargs.values())
    if "US" not in args or 5 not in args:
        return "region or max was not passed to fetch_most_popular"
    with open(out, "rb") as handle:
        lines = handle.read().decode("utf-8").splitlines()
    if [json.loads(line) for line in lines] != fetched:
        return "written file does not hold the fetched items"
    return None


def main():
    try:
        from scripts.youtube_trends import discover as d
    except Exception as exc:
        return fail("cannot import scripts.youtube_trends.discover: %r" % (exc,))
    with tempfile.TemporaryDirectory() as tmp:
        checks = [
            ("build_url", lambda: check_build_url(d)),
            ("parse_items", lambda: check_parse_items(d)),
            ("fetch_most_popular", lambda: check_fetch(d)),
            ("write_jsonl", lambda: check_write_jsonl(d, tmp)),
            ("main", lambda: check_main(d, tmp)),
        ]
        for name, run in checks:
            try:
                problem = run()
            except Exception as exc:
                problem = "raised %r" % (exc,)
            if problem:
                return fail("%s: %s" % (name, problem))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
