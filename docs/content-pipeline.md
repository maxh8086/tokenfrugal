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

The router's task store keeps the last task for each stage slug. A stage whose last task failed or stopped is resumed from its saved messages. A stage whose last task is done is skipped. The run stops at the first stage that does not finish, so running the same command again continues from there.

## Not verified

- A live run has not been done. On the machine where this was written, the three stage tags were not installed (only `ts-*` variants), so `scripts/doctor.py` reports them.
- The factcheck stage uses the content-editor role, which has no web tools. It checks claims only against sources already listed in `01-research.md`. The `content-factcheck` role (web tools) is the alternative if web verification is needed.
- Thinking on the qwen3 stages and their time limits: see "Known gaps" in `docs/content-analyst.md`.
