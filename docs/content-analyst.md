# Content and Trend Intelligence Analyst

This is the design for the content analyst, split into four live roles and three held roles (docs/designs/studio-and-collector-roles.md, Piece 1). The analyst is separate from the script pipeline (`content-research` to `content-editor`).

| Role | Kind | Profile | Skill | Status |
| --- | --- | --- | --- | --- |
| `content-analyst-reddit-hn` | collector (Reddit, Hacker News) | `content-analyst-reddit-hn` | `role-content-analyst-reddit-hn` | live |
| `content-analyst-rss` | collector (RSS feeds) | `content-analyst-rss` | `role-content-analyst-rss` | live |
| `content-analyst-youtube` | collector (YouTube Data API) | `content-analyst-youtube` | `role-content-analyst-youtube` | live |
| `content-analyst-curator` | analyst (merge, score, brief) | `content-analyst-curator` | `role-content-analyst-curator` | live |
| `content-analyst-linkedin` | collector | none | none | held |
| `content-analyst-meta` | collector (Instagram, Facebook) | none | none | held |
| `content-analyst-x` | collector | none | none | held |

Collectors write raw JSON to `content/trends/raw/<YYYY-MM-DD>-<source>.json` in the shared media folder. The curator reads those files, scores the topics and writes the daily brief. Collectors never score.

The old slug `content-analyst` still resolves to the curator, with a logged warning, until 2026-12-31 (`ROLE_ALIASES` in `router/config.py`). After that date the alias is removed and the slug is unknown.

## Held roles

A held role has a `held` reason in `router/tf-roles.yaml`. `dispatch_task` refuses it before any task row is created, and the refusal names the reason. No tools, profile or model call are involved.

| Role | Reason |
| --- | --- |
| `content-analyst-linkedin` | No free collector; terms unresolved. The owner decides on servers, terms and API cost. |
| `content-analyst-meta` | Instagram and Facebook need a Meta app review and API cost. |
| `content-analyst-x` | X has no free API tier for search. |

## Mission

1. Identify trending topics.
2. Detect emerging themes early.
3. Summarize high-performing content.
4. Analyze audience sentiment.
5. Generate content opportunities.
6. Recommend content calendars.
7. Predict trend momentum.

## Tools per role

Every live role is at or under the recommended ceiling of 6 tools (`RECOMMENDED_TOOLS`). The old 12-tool exception is gone.

| Role | Native servers | Tools |
| --- | --- | --- |
| reddit-hn | reddit, hn | search_posts, search_stories, read_file, write_file |
| rss | rss | get_feed, read_file, write_file |
| youtube | youtube | searchVideos, getVideoDetails, read_file, write_file |
| curator | sandbox, qdrant, postgres | run_python, qdrant-find, execute_sql, read_file, write_file |

Server notes:
- **reddit**: Arctic Shift archive; has ingestion lag and rate limits.
- **hn**: Algolia search API. `mcp-hn` has no HTTP timeout (see Known gaps).
- **rss**: any RSS or Atom URL, read from the saved feed list only.
- **youtube**: YouTube Data API v3 (key needed).
- **qdrant**: read-only. The image starts with `QDRANT_READ_ONLY=true`, so qdrant-store is absent. Runs as a compose service (`qdrant`, `127.0.0.1:6333`), started by the curator.
- **postgres**: restricted mode, read-only DB role required.
- **profiles**: each live role mounts the shared media folder read-write through its own filesystem profile.

Left out on purpose: qdrant-store, getChannelTopVideos, getChannelStatistics, getTrendingVideos, getVideoComments, getVideoCategories, getTranscripts, and the postgres schema and index tools.

## Agent flow

| Step | Role | What happens | Tool |
| --- | --- | --- | --- |
| 1 | reddit-hn, rss, youtube | Collect up to 5 items per source: platform, title, URL, engagement, date. Write the raw file. | search_posts, search_stories, get_feed, searchVideos, write_file |
| 2 | curator | Read the raw files for the date. A source with no file is marked not collected. | read_file |
| 3 | curator | Group items into the topic clusters below. Label each topic positive, neutral or negative, with one quoted line and its URL. Summarize each high-performing item in one line with its URL. | model reasoning |
| 4 | curator | Per topic: one LinkedIn post idea, one YouTube idea, one X thread idea, one 5-day calendar entry. | model reasoning |
| 5 | curator | Score each topic with run_python only. Past items for comparison come from qdrant-find and execute_sql. | run_python, qdrant-find, execute_sql |
| 6 | curator | Write the daily brief as `content/trends/<YYYY-MM-DD>.md`. This file is the dashboard. | write_file |

## Topic clusters

- AI Agents
- Cybersecurity
- Prompt Engineering
- Productivity
- Automation
- Startups

## Scoring

Each input is scaled to 0-100 against earlier days in `content/trends/`.

    score = 0.30 * growth + 0.25 * engagement + 0.25 * mentions + 0.20 * cross_platform

| Input | Meaning |
| --- | --- |
| growth | Change in mentions or engagement against the previous files |
| engagement | Upvotes, points, views, as collected |
| mentions | Count of items in the topic that day |
| cross_platform | Number of platforms that mention the topic |

The score is computed by run_python, never by hand.

## Daily output

The brief lists the top 5 topics per day, each with its score, a summary, and the content ideas and calendar entry. Every figure carries a source URL. The curator reports the file path, then the top 3 topics with scores.

## Source table

| Source | How collected | Status |
| --- | --- | --- |
| YouTube | youtube role: searchVideos, getVideoDetails | collected; quota-limited (see below) |
| X / Twitter | held role `content-analyst-x` | not collected; no free collector |
| LinkedIn | held role `content-analyst-linkedin` | not collected; no free collector |
| Instagram and Facebook | held role `content-analyst-meta` | not collected; Meta app review and API cost |
| News and blogs (Reuters, TechCrunch, VentureBeat, Microsoft, OpenAI, Google) | rss role, only feeds on the saved list | collected only when the feed is on the list. The old web_search and crawl_markdown path was removed from the split roles, so unlisted sites are not collected. |
| Reddit (r/artificial, r/MachineLearning, r/OpenAI, r/technology, r/startups) | reddit-hn role: search_posts | collected; archive lag |
| Hacker News | reddit-hn role: search_stories | collected |
| RSS (OpenAI, Anthropic, Microsoft AI, Google DeepMind, AWS ML, NVIDIA) | rss role: get_feed | collected |
| PostgreSQL (past trends and metrics) | curator role: execute_sql | collected when the DB has data |
| Qdrant (embeddings, semantic search of past items) | curator role: qdrant-find | collected when the collection has data |

### YouTube quota

The default Data API quota is 10,000 units per day, reset at midnight Pacific Time.

| Tool | Units per call |
| --- | --- |
| searchVideos | 100 per page (about 1% of the daily quota) |
| getVideoDetails | 1 |

The youtube role makes one searchVideos call per run. getTranscripts is not in the role: it scrapes YouTube web pages through an unofficial method that can break and may not match YouTube's terms, so it is best-effort and excluded.

## Secrets and setup

Secrets are Docker secret files in `~/.docker/mcp/secrets`, outside the repo. Set them with:

    python -m router.secrets_store set YOUTUBE_API_KEY
    python -m router.secrets_store set DATABASE_URI

- **YOUTUBE_API_KEY**: a YouTube Data API v3 key, needed by the youtube role only. The image reads it from `YOUTUBE_API_KEY_FILE`. The key is not in the environment.
- **DATABASE_URI**: a PostgreSQL connection URL, for example `postgresql://reader:...@host:5432/db`, needed by the curator only. The wrapper exports it inside the container, then starts `postgres-mcp --access-mode=restricted`.
  - **The role in the URI must be read-only.** Restricted mode blocks writes in the server, but the database must enforce it too. Create a role with `SELECT` only on the tables the analyst needs.
  - Restricted mode is not tested against a live database. The read-only claim comes from upstream documentation.

A missing secret file makes only the role that needs it fail to open, because compose cannot mount it. Set the secret before running that role, or remove the matching entry from `native` in `router/tf-roles.yaml`.

The curator's `qdrant` service (`127.0.0.1:6333`, named volume `qdrant_data`) is started by its `compose` list. Its contents are not verified against a live Qdrant in this repo.

## Known gaps

- **Hacker News timeouts**: `mcp-hn` makes HTTP requests with no timeout. The upstream code cannot be given one by env or config, and the source is not patched. The only limit is the role's `timeout_s`.
- **RSS network reach**: `get_feed` fetches any http(s) URL the model supplies, with no allow-list. The `mcp-rss` container runs on its own network (`rss_egress`), so it cannot reach the other compose services, but it can still reach addresses on the LAN. Blocking that needs a host firewall rule (for example DOCKER-USER) that this repo does not apply. The upstream npm audit reports 12 advisories, so treat the container as not hardened for untrusted input.
- **Reddit and HN privacy**: queries are sent to Arctic Shift and Algolia.
- **Digest pinning**: the images are pinned by git commit (`docker/pins.yaml`) and the base images by digest in each SOURCE.md. The qdrant service is pinned by tag and digest. No image digest is recorded for the locally built `tokenfrugal/*-mcp:1` images.
- **Tool names are not read offline**: the reddit, hn, rss, youtube, qdrant and postgres servers have no in-repo source for `router/preflight.py`, so their tools show as unverified.
- **Qwen3 thinking and time limits**: `router/loop.py` sends `think` (TOKENFRUGAL_THINK, default `medium`) to every model, and there is no per-model or per-slug switch. The ts-qwen3-8b-40960 stages (outline, executive) therefore think. Their time limit comes from the role (content-research 150 s, content-writer 120 s), not the slug, and content-writer is shared by draft, humanize and executive, so it cannot be raised for qwen3 alone. Not measured against a live model yet. TOKENFRUGAL_THINK=off turns thinking off for all models.

## Note on MCP servers

The Docker MCP catalog has no YouTube, Reddit, Hacker News, RSS or Qdrant server. The servers used here are local builds, not catalog entries. X and LinkedIn have no collector. Apify actors need a paid token and are not used.
