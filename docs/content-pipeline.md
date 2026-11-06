# Content pipeline

`scripts/content_pipeline.py` runs the seven content stages in order for one slug, in-process through the router. The roles write the files under `content/<slug>/` in the media workspace; the script writes nothing itself.

## Stages

| # | Stage | Slug | Role | File written |
| --- | --- | --- | --- | --- |
| 1 | outline (research and claims) | `content-outline` | content-research | `01-research.md` |
| 2 | factcheck | `content-factcheck` | content-editor | `02-facts.md` |
| 3 | draft | `content-draft` | content-writer | `03-draft.md` |
| 4 | critic | `content-critic` | content-editor | `04-critique.md` |
| 5 | humanize | `content-humanize` | content-writer | `05-human.md` |
| 6 | antislop | `content-antislop` | content-editor | `06-antislop.md` |
| 7 | executive | `content-executive` | content-writer | `07-final.md` |

Factcheck runs before draft because draft reads `02-facts.md`. There is no separate research slug: stage 1 does the web research.

Models (per slug, set in `router/tf-roles.yaml` under `tf_roles_models`): `ts-qwen3-8b-40960:latest` for stages 1 and 7, `ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536:latest` for stages 3 and 5, `ts-llama3-1-8b-65536:latest` for stages 2, 4 and 6. All three are already installed locally (customised builds, Q4_K_M, tool-capable); no pull is needed. See `models/README.md`.

## Slug convention

Lowercase letters, digits and hyphens, for example `ai-banking-2026`. The slug is the folder name under `content/`.

## Usage

    python scripts/content_pipeline.py ai-banking-2026 --topic "AI in banking"            # dry plan, calls no model
    python scripts/content_pipeline.py ai-banking-2026 --topic "AI in banking" --confirm  # runs the stages

The dry plan prints each stage with its role, model, time limit and what a run would do.

## Resume

The router's task store keeps the last task for each stage slug, and only tasks of runs for the same slug count. A stage whose last task failed or stopped is resumed from its saved messages. A stage whose last task is done is skipped. A different slug never reuses another slug's stages. The run stops at the first stage that does not finish, so running the same command again continues from there.

## Runs and Studio

Each pipeline run has a row in the `runs` table with one of these states: `queued`, `waiting_gpu`, `running`, `cancelling`, `cancelled`, `done`, `failed`. A run or task whose heartbeat is older than 120 s belongs to a dead router; the router marks it `failed` at startup and at each sweep, so the next run for that slug resumes the failed stage.

The Studio tools queue work through a request folder (`STUDIO_DIR/requests`, one JSON file per request):

- `studio_run(action="pipeline", slug, topic)` queues the seven stages for one slug.
- `studio_run(action="collect", sources="reddit-hn,rss,youtube")` queues the three collector roles.
- `studio_run(action="save_feed", feed_url=...)` adds an RSS feed to the saved list. Only http and https; loopback, private, link-local and reserved addresses are refused, and so are URLs over `RSS_MAX_URL` characters.
- `studio_run(action="cancel")` stops the active run at its next stage boundary.
- `studio_run(action="store")` queues one run that writes today's collector files (`content/trends/raw/<date>-*.json`) to Neo4j, one node per item (`docs/designs/studio-write-path.md`). It needs `fastembed` for the embeddings; a missing install ends the run as failed before any write.
- `studio_status()` shows the active run, the last five runs, waiting requests, the estimated YouTube quota for the Pacific day and any missing secret names. It never shows a secret value or a file path.

One run is active at a time. A start is refused while a run is active or a request is already waiting. A request nobody claims within `STUDIO_CLAIM_TIMEOUT` seconds expires. The YouTube quota is an estimate: `searchVideos` counts 100 units and `getVideoDetails` 1 unit per successful call, reset at Pacific midnight.

## Not verified

- A live run has not been done. On the machine where this was written, the three stage tags were not installed (only `ts-*` variants), so `scripts/doctor.py` reports them.
- The factcheck stage uses the content-editor role, which has no web tools. It checks claims only against sources already listed in `01-research.md`. The `content-factcheck` role (web tools) is the alternative if web verification is needed.
- Thinking on the qwen3 stages and their time limits: see "Known gaps" in `docs/content-analyst.md`.
