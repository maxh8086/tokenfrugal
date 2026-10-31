# youtube-mcp (tokenfrugal/youtube-mcp:1)

## Source

| Field | Value |
| --- | --- |
| Repository | https://github.com/kirbah/mcp-youtube |
| License | MIT (`LICENSE` at the pinned commit) |
| Pinned commit | `0ba98f673cf4f2ebdd21edb0ac9d3337c77f4531` |
| Commit date | 2026-10-31 09:25 +0100 (author: Kiryl Bahdanau). The commit is from the day of the build, so it has little review history; pinned as requested. |
| Package version | `@kirbah/mcp-youtube` 1.1.15 (MCP server name reported as `YouTube`) |
| Fetch method | Dockerfile runs `git init` + `git fetch --depth 1 origin <sha>` + `git checkout FETCH_HEAD`, then asserts `git rev-parse HEAD` equals the pinned SHA. No branch, tag or `latest`. |
| Build date | 2026-10-31 |
| Base image | `node:22-slim` (Node 22.23.4, Debian 12 bookworm), digest `sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da`. The project requires Node >= 22. |
| Dependency pinning | `package-lock.json` (lockfileVersion 3) from the pinned commit, installed with `npm ci --ignore-scripts`. Dev dependencies pruned in the runtime stage. |

## Image

- Tag: `tokenfrugal/youtube-mcp:1`
- Image ID: `sha256:943cd61a9540400453f90582d51a69e1793bb5c9bdd8890cd984f70d28e9d283`
- Size: 679 MB on disk (`docker images`), 117 MB uncompressed content (`docker image inspect`)
- User: `node` (uid 1000), non-root
- Ports: none published. Transport: stdio only.
- Entrypoint: `/usr/local/bin/docker-entrypoint.sh` (POSIX sh wrapper, then `node /app/dist/index.js`)

## Secrets and configuration

| Variable | Needed | Purpose |
| --- | --- | --- |
| `YOUTUBE_API_KEY` | Yes, for the Data API tools | YouTube Data API v3 key. Read from the environment. |
| `YOUTUBE_API_KEY_FILE` | Alternative to the above | Path to a file that holds only the key (for example a mounted Docker secret). The entrypoint reads it, strips trailing newlines, and exports `YOUTUBE_API_KEY`. The key is never printed. |
| `MDB_MCP_CONNECTION_STRING` | No, leave UNSET | Enables MongoDB caching and the `findConsistentOutlierChannels` tool. Not included in this image. |

- The key is never baked into the image. Do not pass it as a build argument.
- Without a key the server starts but registers only `getTranscripts`.
- Example, Docker secret file (PowerShell or with path conversion disabled in Git Bash):

```
docker run --rm -i -e YOUTUBE_API_KEY_FILE=/run/secrets/youtube_api_key -v C:\path\to\youtube_api_key:/run/secrets/youtube_api_key:ro tokenfrugal/youtube-mcp:1
```

Git Bash on Windows rewrites `/run/...` paths inside `-v`; run with `MSYS_NO_PATHCONV=1` in that case. A mount that was rewritten silently fails with "YOUTUBE_API_KEY_FILE is set but not readable".

## MongoDB (optional) is DISABLED

Leave `MDB_MCP_CONNECTION_STRING` unset. When it is set, the source:
- connects to MongoDB for caching and for the analytics tool (`findConsistentOutlierChannels`), and
- calls `dns.setServers(["8.8.8.8", "1.1.1.1"])` process-wide (`src/services/database.service.ts`), so DNS for the whole container goes to those resolvers.

Without it, `CacheService` keeps no persistent cache and MongoDB is never loaded at runtime.

## Tools (as found in source)

Registered when `YOUTUBE_API_KEY` is set (`src/tools/index.ts`):

| Tool | Data API calls | Approx. quota units per call |
| --- | --- | --- |
| `searchVideos` | `search.list` per page (up to 50 results per page) | 100 per page |
| `getChannelTopVideos` | `search.list` (100) + `videos.list` per batch of 50 | about 101 per page |
| `getChannelStatistics` | `channels.list` (one call per channel, or per 50 IDs in batch) | 1 |
| `getVideoDetails` | `videos.list` | 1 |
| `getTrendingVideos` | `videos.list` (chart) per page | 1 |
| `getVideoComments` | `commentThreads.list` per page, plus `comments.list` per reply thread fetched | 1 per page, plus 1 per reply fetch |
| `getVideoCategories` | `videoCategories.list` | 1 |
| `getTranscripts` | none (no Data API; scrapes YouTube web pages, see below) | 0 Data API units |

Not included: `findConsistentOutlierChannels` (only with the MongoDB connection string). It runs many `search.list` calls, so its cost is high and it is intentionally not in this image.

Without a key, only `getTranscripts` is registered. Quota numbers are from the source's `API_COSTS` table (`src/services/youtube.service.ts`): `search.list` 100, `videos.list`, `channels.list`, `videoCategories.list`, `commentThreads.list`, `comments.list` each 1.

Free quota: the default project quota is 10,000 units per day. It resets at midnight Pacific Time. One `searchVideos` page uses 1% of the day. The server keeps only an in-process counter of units used (`getApiCreditsUsed`), not a real quota view.

Smoke results: without a key, `tools/list` returns `getTranscripts`. With `--dummy-key` (placeholder value), it returns the 8 tools above. No API call is made in either case.

## How to run over stdio

```
docker run --rm -i -e YOUTUBE_API_KEY=... tokenfrugal/youtube-mcp:1
```

Prefer `YOUTUBE_API_KEY_FILE` with a secret file over a plain environment variable (the plain form shows in `docker inspect` and shell history).

Smoke test (no key needed, no API calls):

```
python docker/youtube-mcp/smoke.py
python docker/youtube-mcp/smoke.py --dummy-key
```

## Source review (done before build, at the pinned commit)

Read: `package.json`, `package-lock.json`, `README.md` (headings), `.env.example`, `server.json`, `src/index.ts`, `src/server.ts`, `src/container.ts`, `src/utils/env.ts`, `src/tools/index.ts`, `src/services/youtube.service.ts` (API call sites and cost table), `src/services/transcript.service.ts`, `src/services/database.service.ts`, `src/config/cache.config.ts`. Tests are not part of the image (excluded by `tsconfig.json`).

Network calls found:
1. `googleapis` client to `https://youtube.googleapis.com/` (the official Data API v3). The key is sent as a query parameter, as Google's client does by default.
2. `youtube-transcript-plus` (MIT, v2.0.3) in `getTranscripts`. It is not the Data API. Inside the package it requests `https://www.youtube.com/watch?v=<id>` and `https://www.youtube.com/youtubei/v1/player?key=<key>`. The `<key>` is the `INNERTUBE_API_KEY` scraped from the watch page, not `YOUTUBE_API_KEY`. This is unofficial scraping; it can break or violate YouTube's terms. Document it to users.
3. MongoDB and its DNS change: only when `MDB_MCP_CONNECTION_STRING` is set (see above). Not set in this image.
4. No telemetry, analytics or crash-reporting code was found in `src/`. Logs go to stderr only (`console.error`); stdout is the MCP JSON-RPC stream.

Other findings:
- `index.ts` sets `process.env.NODE_ENV !== "test"` guard and loads `.env` from the working directory if present; the image has none (`/app` has no `.env`).
- Tool annotations are `readOnlyHint: true` for every tool.
- Dependency audit (`npm audit --omit=dev` on the pinned lockfile): 2 moderate advisories, no high or critical: `fast-uri` 3.0.0 to 3.1.8 and `ip-address` <=10.7.3. Not fixed here (would require changing the lockfile).
- Lockfile includes `tsx` as a runtime dependency; it is kept in the image (harmless, adds size).
- The Dockerfile does not run `npm install` scripts (`--ignore-scripts`). The build succeeded without them.

## Build and verification

- `docker build -t tokenfrugal/youtube-mcp:1 docker/youtube-mcp`: `npm ci` from the lockfile, `tsc` build succeeded.
- Smoke without key: `getTranscripts` only, `SMOKE OK`.
- Smoke with `--dummy-key`: 8 tools, `SMOKE OK`.
- Key-file test: `YOUTUBE_API_KEY_FILE` with a placeholder file, run with `--network none`: all 8 tools registered, exit 0, placeholder not printed to stdout or stderr. Shows the file path works and tools/list needs no network.
