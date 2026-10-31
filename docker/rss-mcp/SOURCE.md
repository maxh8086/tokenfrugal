# rss-mcp (tokenfrugal/rss-mcp:1)

## Source

| Field | Value |
| --- | --- |
| Repository | https://github.com/veithly/rss-mcp |
| License | Apache-2.0 (`LICENSE` at the pinned commit; `package.json` says the same) |
| Pinned commit | `f0713aaeebef6129f277f2f4d524361751606011` |
| Commit date | 2025-12-12 (author: Rick) |
| Package version | `rss-mcp` 1.0.1 (`package.json`); MCP server name reported as `rss` 1.0.0 |
| Fetch method | Dockerfile runs `git init` + `git fetch --depth 1 origin <sha>` + `git checkout FETCH_HEAD`, then asserts `git rev-parse HEAD` equals the pinned SHA. No branch, tag or `latest`. |
| Build date | 2026-10-31 |
| Base image | `node:22-slim` (Node 22.23.4, Debian 12 bookworm), digest `sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da`. Used for both build and runtime stages. |
| Dependency pinning | `package-lock.json` (lockfileVersion 3) from the pinned commit, installed with `npm ci --ignore-scripts`. Dev dependencies pruned in the runtime stage. |

## Image

- Tag: `tokenfrugal/rss-mcp:1`
- Image ID: `sha256:3a97d777b9ee05bb3f2572eb051539d928be259fdf57c61d85cfedec313023fe`
- Size: 409 MB on disk (`docker images`), 88 MB uncompressed content (`docker image inspect`)
- User: `node` (uid 1000), non-root
- Ports: none published. Transport: stdio only.
- Entrypoint: `node /app/dist/index.js`

## Tools (as found in source)

Only one tool is registered, `src/index.ts`:

- `get_feed`: "Get RSS feed from any URL, including RSSHub feeds."
  - `url` (string, required): an RSS/Atom URL, or `rsshub://<route>` (example `rsshub://bilibili/user/dynamic/208259`). A URL without `://` is treated as `rsshub://<value>`.
  - `count` (number, optional): items to return, default 1, `0` for all items.
  - Returns JSON `{title, link, description, items[]}`; each item has `title, description, link, guid, pubDate, author, category`.

Smoke result: `tools/list` returns `get_feed` only.

## Environment variables and secrets

- None are required. The image does not contain or need any secret.
- `PRIORITY_RSSHUB_INSTANCE` (optional): RSSHub base URL placed first in the instance list. Set with `-e` only if you run your own RSSHub.
- `dotenv/config` is loaded at startup. It reads `/app/.env` if present; the image has none.

## RSSHub is optional and NOT included

RSSHub is a separate service. This image does not contain RSSHub and does not start one. Without it, the `rsshub://` form and RSSHub routes still work, but only through the public instances listed in `src/index.ts`. Plain RSS/Atom URLs work with no RSSHub at all.

## How to run over stdio

```
docker run --rm -i tokenfrugal/rss-mcp:1
```

Keep stdin open for the session. Smoke test: `python docker/rss-mcp/smoke.py` (prints `get_feed` and `SMOKE OK`).

Example MCP client entry (stdio):

```json
{"command": "docker", "args": ["run", "--rm", "-i", "tokenfrugal/rss-mcp:1"]}
```

## API quota and rate notes

- No API key and no paid API. Quota is not applicable.
- `get_feed` fetches the feed directly from the target URL, or for `rsshub://` routes from the public RSSHub instances in order (each attempt 15 s timeout, up to 16 instances, default list includes a `localhost:1200` entry). Those public instances rate-limit or go offline; the server falls back to the next one on failure.

## Source review (done before build, at the pinned commit)

Read: `src/index.ts` (293 lines, the only source file besides a 32-line `src/test.ts`), `package.json`, `package-lock.json`, `README.md`.

Network calls found:
1. `axios.get` to the URL the caller passes, or to each RSSHub instance in `RSSHUB_INSTANCES`. The instance list is hard-coded: `rsshub.app`, `rsshub.rssforever.com`, `rsshub.feeded.xyz`, `hub.slarker.me`, `rsshub.liumingye.cn`, `rsshub-instance.zeabur.app`, `rss.fatpandac.com`, `rsshub.pseudoyu.com`, `rsshub.friesport.ac.cn`, `rsshub.atgw.io`, `rsshub.rss.tips`, `rsshub.mubibai.com`, `rsshub.ktachibana.party`, `rsshub.woodland.cafe`, `rsshub.aierliz.xyz`, `localhost:1200`.
2. No other network I/O. No telemetry, analytics, crash-reporting or update-check code was found (grep for fetch/axios/http/telemetry/analytics/track/process.env in `src/`).
3. `console.error` only for logs; stdout is reserved for the MCP JSON-RPC stream.

Findings for the operator:
- Privacy: the feed path a caller requests (for example a user ID in a bilibili route) is sent to third-party public RSSHub operators. Use your own RSSHub via `PRIORITY_RSSHUB_INSTANCE` if that matters.
- No URL allow-list: `get_feed` fetches any `http(s)` URL the model supplies, including addresses reachable from the container network (server-side request forgery risk when the prompt is untrusted). Restrict egress at the Docker network level if this matters. Not changed here, because the source is pinned as-is.
- `zod` is imported in `src/index.ts` but is not listed in `package.json`. It resolves as a transitive dependency of `@modelcontextprotocol/sdk` (zod 3.25.63 in the lockfile). Works today; fragile if the SDK changes.
- Dependency audit (`npm audit --omit=dev` on the pinned lockfile): 12 advisories, 2 critical, 7 high, 3 moderate. Affected: `@modelcontextprotocol/sdk` (<=1.31.0; locked 1.13.2), `axios` (1.0.0 to 1.19.0; locked 1.10.0), `zod` (<4.6.6; locked 3.25.63), `zod-to-json-schema`, `body-parser`, `path-to-regexp`, `form-data`, `proxy-addr`, `undici`, `qs`, `follow-redirects`, `ajv`. Upgrading means changing the lockfile, which would no longer be the pinned source; not done. Treat the container as not hardened for untrusted input.
- Minor: the default `count` is 1; `count: 0` returns all items (can be large).

## Build and verification

- `docker build -t tokenfrugal/rss-mcp:1 docker/rss-mcp`: builds, `npm ci` from lockfile, `tsc` compiles cleanly.
- Smoke: `python docker/rss-mcp/smoke.py` returns `get_feed`, `SMOKE OK`.
- The smoke test makes no feed request. Only initialize and tools/list are sent.
