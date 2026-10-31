# hn-mcp (tokenfrugal/hn-mcp:1)

Read-only MCP server for Hacker News, backed by the Algolia HN Search API, over stdio.

## Source

- Repo: https://github.com/erithwik/mcp-hn
- License: MIT (LICENSE in repo, "Copyright (c) 2024")
- Pinned commit: `a454f624e6b1171e0e3dbe0c9eafd2830565190f` (commit date 2025-07-13, "Merge pull request #2 from punkpeye/patch-1"; last push 2025-07)
- Pinned on: 2026-10-31
- Fetched by exact SHA. The build fails unless `git rev-parse HEAD` equals the SHA.
- Dependencies: the repo's `uv.lock`, installed with `uv sync --frozen --no-dev`. The lock resolves `mcp==1.1.2`, `requests==2.32.3`, `httpx==0.28.1`, `pydantic==2.10.4`, `hatchling==1.27.0` and others.

## Base image

- `python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337`
- The build stage also installs `git` from Debian bookworm apt. The commit check is what pins the source.
- The runtime stage installs `uv==0.12.19` via pip.

## Patch applied on top of the pinned commit (one line)

- Finding F1 (below): `src/mcp_hn/hn.py` has `print(url)` at the top of `search_stories`. Stdout is the MCP channel, so this line corrupts the JSON-RPC stream.
- The Dockerfile deletes exactly that line with sed. It first checks with grep that the line occurs once, and fails the build if not. It then checks that no `print(` calls remain.
- No other source change.

## Tools (as found, `server.py`)

- `get_stories` (story_type: top|new|ask_hn|show_hn, num_stories)
- `get_user_info` (user_name, num_stories)
- `search_stories` (query, search_by_date, num_results)
- `get_story_info` (story_id)

## Env vars

None required. None read.

## Run over stdio

    docker run --rm -i tokenfrugal/hn-mcp:1

No ports, no volumes, no secrets. Runs as uid 10001.

Smoke test: `python docker/hn-mcp/smoke.py tokenfrugal/hn-mcp:1`

Smoke result on build day: initialize OK (protocol 2024-11-05, server `hn` 0.1.0). tools/list returned the 4 tools above.

Live calls on build day, all returned clean JSON with isError=false: `get_stories top`, `search_stories rust`, `get_story_info 1`, `get_user_info pg`.

## Review findings (source read at the pinned commit)

- Network: the only outbound host is the Algolia HN Search API, `http://hn.algolia.com/api/v1` (`hn.py`). Every call is a GET via requests.
- No telemetry or analytics code. No credentials. No environment reads. No subprocess, eval, exec or pickle. No write or post actions.
- F1 (fixed in the image, see above): `print(url)` in `search_stories` writes to stdout. The MCP stdio transport shares stdout, so each search would inject a non-JSON line. Found by reading the code. I did not reproduce it against the unpatched image.
- F2 (not patched): the base URL uses plain `http://`, not `https://`. Responses are unencrypted and can be altered in transit. The data is public and no credentials are sent, so this is a hygiene issue. The source is not changed, per the rule to build at the pinned commit. I did not check whether the endpoint redirects to https.
- F3 (not patched): `query` and `user_name` are formatted into URLs without URL-encoding. A value containing `&` or `#` can add or change query parameters on the Algolia request. The effect is limited to read-only search parameters.
- F4 (not patched): every `requests.get` has no timeout. A stalled upstream can hang a tool call indefinitely.
- F5 (stale): the lock pins `mcp==1.1.2` (a late-2024 SDK). The repo has no commit after 2025-07 and no tests. Expect old-SDK behaviour and no security fixes.
- F6 (minor): `handle_call_tool` assumes `arguments` is a dict. A call with no arguments raises AttributeError, which the SDK turns into a tool error.
- F7 (minor): `pyproject.toml` pins `hatchling==1.26.3` as the build backend, but the lock resolves `hatchling==1.27.0`. The build works, but the two versions differ.
- The repo's own Dockerfile (Smithery) and smithery.yaml are not used. The image uses the house-style Dockerfile instead.

## Data caveats

- Algolia search can return empty results for very targeted queries. The repo's own tool text recommends short queries (fewer than 5 words).
- Results come from the Algolia index, not a live HN feed.

## Known limits

- Live checks ran once on build day. No load test.
- The repo has no tests.

## Breakage

None observed in the live calls above. The stdout issue (F1) is patched in the image.
