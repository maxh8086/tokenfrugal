# reddit-mcp (tokenfrugal/reddit-mcp:1)

Read-only MCP server exposing the Arctic Shift Reddit archive over stdio.

## Source

- Repo: https://github.com/ekatiyar/simple-reddit-mcp
- License: MIT (LICENSE in repo, "Copyright (c) 2026 ekatiyar")
- Pinned commit: `6011105882d447847265dc040823261dbd14d011` (commit date 2026-08-13, subject "Use ekatiyar username instead of first name, drop email")
- Pinned on: 2026-10-31
- Fetched by exact SHA (`git fetch --depth 1 origin <sha>`). The build fails unless `git rev-parse HEAD` equals the SHA.
- Dependencies: the repo's `uv.lock`, installed with `uv sync --frozen --no-dev`. The lock resolves `zeromcp==1.6.0` (sha256 in the lock).

## Base image

- `python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337`
- The build stage also installs `git` from Debian bookworm apt. That package floats; the commit check is what pins the source.
- The runtime stage installs `uv==0.12.19` via pip.

## Tools (as found, `server.py`, all `read_only=True`)

- `get_thread` (url_or_id, comment_limit, parent_id, sort_top, max_chars, raw)
- `get_posts` (ids, fields, max_chars, raw)
- `get_comments` (ids, fields, max_chars, raw)
- `search_posts` (subreddit, author, query, title, selftext, url, after, before, limit, sort, fields, max_chars, raw)
- `search_comments` (subreddit, author, body, link_id, parent_id, after, before, limit, sort, fields, max_chars, raw)
- `search_subreddits` (subreddit, subreddit_prefix, min/max_subscribers, over18, after, before, limit, sort, sort_type, fields, max_chars, raw)

## Env vars

None required. None read. The app does not read the environment.

## Run over stdio

    docker run --rm -i tokenfrugal/reddit-mcp:1

No ports, no volumes, no secrets. Runs as uid 10001.

Smoke test: `python docker/reddit-mcp/smoke.py tokenfrugal/reddit-mcp:1`

Smoke result on build day: initialize OK (protocol 2024-11-05, server `reddit` 0.0.1). tools/list returned the 6 tools above.

## Review findings (source read at the pinned commit)

- Network: the only outbound host is `https://arctic-shift.photon-reddit.com` (`api.py`), and every call is a GET. The status-page URL appears only in an error message string, not as a request. Reddit URLs in output are plain strings.
- No telemetry or analytics code. No credential handling. No environment reads. No subprocess, eval, exec or pickle.
- No write or post actions. Every tool is read-only.
- Input handling: user URLs are parsed by regex (`urls.py`). Non-reddit hosts are rejected. Share links (`/r/<sub>/s/<code>`) are resolved with one more GET to `/api/short_links`.
- `zeromcp` 1.6.0 (a dependency, not the repo) was read from the installed wheel inside the image. Its `stdio()` path does no network I/O and writes only JSON-RPC to stdout. Its HTTP `serve()` code is present but this server never calls it (`main()` calls `mcp.stdio()` only). The zeromcp GitHub repo itself was not separately audited.
- Build hygiene: `pyproject.toml` declares the build backend `uv_build>=0.9,<0.12`, which is not locked. uv warns that 0.12.19 is outside that range. The build succeeded, but the build backend is not frozen.

## Data caveats (important for users)

- Arctic Shift is an archive, not live Reddit. Posts appear with a lag. The server's own docstrings say `score` and `num_comments` are placeholders for posts under about 36 hours old.
- Deleted or removed content may never appear. Removed bodies show as `[removed]` in the archive.
- Arctic Shift has no uptime guarantee and rate-limits bursts. The client paces requests at 0.4 s and retries once on 422/5xx. A 429 is returned as a tool error.
- Keyword comment search is slow. Keyword search can time out without a subreddit, author, or date range.

## Known limits

- Output is capped (default 40000 characters per tool call).
- Live check on build day (2026-10-31): `search_subreddits`, `search_posts` (date-bounded) and `get_posts` returned data from the container, so it can reach the archive.
- Not tested against private or deleted content, or at scale.

## Breakage

None found.
