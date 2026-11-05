"""Fetch the YouTube most-popular chart and write it as JSON lines.

Standard library only. The API key is read from the router secrets store
under the name "yt-key" and is never printed.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_URL = "https://www.googleapis.com/youtube/v3/videos"


def build_url(api_key, region, max_results):
    clamped = max(1, min(50, int(max_results)))
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": clamped,
        "key": api_key,
    }
    return API_URL + "?" + urllib.parse.urlencode(params)


def parse_items(payload):
    out = []
    for item in payload.get("items", []) or []:
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        out.append({
            "video_id": item.get("id"),
            "title": snippet.get("title"),
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
            "published_at": snippet.get("publishedAt"),
            "category_id": snippet.get("categoryId"),
            "tags": snippet.get("tags", []),
            "views": int(stats.get("viewCount", 0) or 0),
            "likes": int(stats.get("likeCount", 0) or 0),
        })
    return out


def fetch_most_popular(api_key, region, max_results=50, opener=None):
    if opener is None:
        opener = urllib.request.urlopen
    url = build_url(api_key, region, max_results)
    try:
        with opener(url, timeout=20) as resp:
            raw = resp.read()
        payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            body = ""
        body = body.replace(api_key, "***")
        raise RuntimeError(
            f"YouTube API HTTP {exc.code}: {body}"
        ) from None
    return parse_items(payload)


def write_jsonl(items, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Discover YouTube most-popular videos.")
    parser.add_argument("--region", default="US")
    parser.add_argument("--max", dest="max_n", type=int, default=50)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    from router import secrets_store

    key = secrets_store.get("yt-key")
    if key is None:
        print("yt-key is not set", file=sys.stderr)
        return 2

    items = fetch_most_popular(key, args.region, args.max_n)
    write_jsonl(items, args.out)
    print(f"wrote {len(items)} videos to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
