# Content and Trend Intelligence Analyst

This is the design for the `content-analyst` role (profile `content-analyst`, skill `router/skills/role-content-analyst/SKILL.md`). The role is separate from the script pipeline (`content-research` to `content-editor`). It uses web tools plus six native content servers, each a stdio container built from `docker/<name>-mcp` and pinned in `docker/pins.yaml`.

## Mission

1. Identify trending topics.
2. Detect emerging themes early.
3. Summarize high-performing content.
4. Analyze audience sentiment.
5. Generate content opportunities.
6. Recommend content calendars.
7. Predict trend momentum.

## Tools (12, the maximum)

| Server | Tools used by the role | Notes |
| --- | --- | --- |
| web (crawl4ai, searxng) | web_search, crawl_markdown | existing |
| sandbox | run_python | existing |
| profile content-analyst | read_file, write_file | existing Docker MCP profile (mcp/filesystem) |
| reddit | search_posts | Arctic Shift archive; has ingestion lag and rate limits |
| hn | search_stories | Algolia search API |
| rss | get_feed | any RSS/Atom URL |
| youtube | searchVideos, getVideoDetails | YouTube Data API v3 (key needed) |
| qdrant | qdrant-find | read-only: the image is started with `QDRANT_READ_ONLY=true`, so qdrant-store is absent |
| postgres | execute_sql | restricted mode, read-only DB role required |

This is 12 tools. The router's recommended ceiling for 3B models is 6, so this role is above it on purpose; the tool cap (MAX_TOOLS = 12) still holds. Left out on purpose: qdrant-store, getChannelTopVideos, getChannelStatistics, getTrendingVideos, getVideoComments, getVideoCategories, getTranscripts, and the postgres schema and index tools.

## Agent flow

| Step | Stage | What happens | Tool |
| --- | --- | --- | --- |
| 1 | Trend Collector | Collect up to 5 items per source: platform, title, URL, engagement, date. | web_search, get_feed, search_stories, search_posts, searchVideos |
| 2 | Topic Clustering | Group items into the topic clusters below. | model reasoning |
| 3 | Sentiment | Label each topic positive, neutral or negative, with one quoted line and its URL. | model reasoning |
| 4 | Content Summary | Summarize each high-performing item in one line with its URL. | model reasoning |
| 5 | Content Recommendation | Per topic: one LinkedIn post idea, one YouTube idea, one X thread idea, one 5-day calendar entry. | model reasoning |
| 6 | Trend Scoring | Score each topic with run_python only. | run_python |
| 7 | Dashboard | Write the daily brief as `content/trends/<YYYY-MM-DD>.md`. This file is the dashboard. | write_file |

Past items for comparison come from qdrant-find (vector store) and execute_sql (PostgreSQL). Both are read-only.

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

The brief lists the top 5 topics per day, each with its score, a summary, and the content ideas and calendar entry from step 5. Every figure carries a source URL. The role reports the file path, then the top 3 topics with scores.

## Source table

| Source | How collected | Status |
| --- | --- | --- |
| YouTube | youtube server: searchVideos, getVideoDetails | collected; quota-limited (see below) |
| X / Twitter | none | not collected; no free collector |
| LinkedIn | none | not collected; no free collector |
| News and blogs (Reuters, TechCrunch, VentureBeat, Microsoft, OpenAI, Google) | web_search, crawl_markdown | collected |
| Reddit (r/artificial, r/MachineLearning, r/OpenAI, r/technology, r/startups) | reddit server: search_posts | collected; archive lag |
| Hacker News | hn server: search_stories | collected |
| RSS (OpenAI, Anthropic, Microsoft AI, Google DeepMind, AWS ML, NVIDIA) | rss server: get_feed | collected |
| PostgreSQL (past trends and metrics) | postgres server: execute_sql | collected when the DB has data |
| Qdrant (embeddings, semantic search of past items) | qdrant server: qdrant-find | collected when the collection has data |

### YouTube quota

The default Data API quota is 10,000 units per day, reset at midnight Pacific Time.

| Tool | Units per call |
| --- | --- |
| searchVideos | 100 per page (about 1% of the daily quota) |
| getVideoDetails | 1 |

The role makes one searchVideos call per run. getTranscripts is not in the role: it scrapes YouTube web pages through an unofficial method that can break and may not match YouTube's terms, so it is best-effort and excluded.

## Secrets and setup

Both secrets are Docker secret files in `~/.docker/mcp/secrets`, outside the repo. Set them with:

    python -m router.secrets_store set YOUTUBE_API_KEY
    python -m router.secrets_store set DATABASE_URI

- **YOUTUBE_API_KEY**: a YouTube Data API v3 key. The image reads it from `YOUTUBE_API_KEY_FILE`. The key is not in the environment.
- **DATABASE_URI**: a PostgreSQL connection URL, for example `postgresql://reader:...@host:5432/db`. The wrapper exports it inside the container, then starts `postgres-mcp --access-mode=restricted`.
  - **The role in the URI must be read-only.** Restricted mode blocks writes in the server, but the database must enforce it too. Create a role with `SELECT` only on the tables the analyst needs.
  - Restricted mode is not tested against a live database. The read-only claim comes from upstream documentation.

A missing secret file makes the whole `content-analyst` role fail to open, because compose cannot mount it. Set both secrets before running the role, or remove the postgres and youtube entries from `native` in `router/tf-roles.yaml`.

Qdrant runs as a service (`qdrant`, `127.0.0.1:6333`, named volume `qdrant_data`) and is started by the role's `compose` list. Its contents are not verified against a live Qdrant in this repo.

## Known gaps

- **Hacker News timeouts**: `mcp-hn` makes HTTP requests with no timeout. The upstream code cannot be given one by env or config, and the source is not patched. The only limit is the role's `timeout_s`.
- **RSS network reach**: `get_feed` fetches any http(s) URL the model supplies, with no allow-list. The `mcp-rss` container runs on its own network (`rss_egress`), so it cannot reach the other compose services, but it can still reach addresses on the LAN. Blocking that needs a host firewall rule (for example DOCKER-USER) that this repo does not apply. The upstream npm audit reports 12 advisories, so treat the container as not hardened for untrusted input.
- **Reddit and HN privacy**: queries are sent to Arctic Shift and Algolia.
- **Digest pinning**: the images are pinned by git commit (`docker/pins.yaml`) and the base images by digest in each SOURCE.md. The qdrant service is pinned by tag and digest. No image digest is recorded for the locally built `tokenfrugal/*-mcp:1` images.
- **Tool names are not read offline**: the reddit, hn, rss, youtube, qdrant and postgres servers have no in-repo source for `router/preflight.py`, so their tools show as unverified.

- **Qwen3 thinking and time limits**: `router/loop.py` sends `think` (TOKENFRUGAL_THINK, default `medium`) to every model, and there is no per-model or per-slug switch. The ts-qwen3-8b-40960 stages (outline, executive) therefore think. Their time limit comes from the role (content-research 150 s, content-writer 120 s), not the slug, and content-writer is shared by draft, humanize and executive, so it cannot be raised for qwen3 alone. Not measured against a live model yet. TOKENFRUGAL_THINK=off turns thinking off for all models.

## Note on MCP servers

The Docker MCP catalog has no YouTube, Reddit, Hacker News, RSS or Qdrant server. The six servers used here are local builds, not catalog entries. X and LinkedIn have no collector. Apify actors need a paid token and are not used.
