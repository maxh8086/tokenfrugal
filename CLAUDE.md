# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single-file FastMCP stdio server ([server.py](server.py)) that exposes a local OpenAI-compatible LLM (LM Studio, Ollama, etc.) as MCP tools so Claude Code can offload small tasks. There is no build step, test suite, or linter configured.

## Commands

```bash
pip install -r requirements.txt   # fastmcp, openai, python-dotenv
cp .env.example .env              # then edit for your local LLM
python server.py                  # runs the MCP server over stdio (normally launched by Claude Code)
```

Register it in `~/.claude.json` under `mcpServers` as a `stdio` server running `python <path>/server.py` (see README.md).

## Architecture

- Config is read once at import time from `.env` via `load_dotenv()`: `OPENAI_API_KEY`, `OPENAI_BASE_URL` (default `http://localhost:1234/v1`), `LOCAL_MODEL_NAME`, `LOCAL_LLM_TEMPERATURE`, `LOCAL_LLM_MAX_TOKENS` (`-1` = unlimited). A single module-level `OpenAI` client is shared by all tools.
- Two `@mcp.tool()` functions, both calling `client.chat.completions.create` with a system + user message:
  - `query_local_llm` — prompt only; per-call `temperature`/`max_tokens` overrides.
  - `query_local_llm_with_context` — wraps input as `Context:\n...\n\nTask:\n...`, picks a system message from `task_type` (`code_review`, `documentation`, `refactor`, `general`); no per-call overrides, and the model is always the env-configured `MODEL_NAME`.
- Tool docstrings are the prompts Claude Code sees when deciding whether to delegate; changing their wording changes delegation behavior. Errors are returned as `"Error querying local LLM..."` strings rather than raised.

## Gateway (`gateway/`)

`gateway/server.py` is the Claude-facing FastMCP server `tokenfrugal` (`dispatch_task`, `ask_followup`, `get_detail`, `resume_task`, `list_roles`). Run: `python -m gateway.server`.

- `personas.yaml` maps agency-agents slugs (by division prefix, longest match, plus overrides) to a role; a role = model + Docker MCP profile + 4-6 allowlisted tools (+ optional `native:` servers such as `codebase`). Only two local models: `qwen2.5-coder-yarn:3b` (builder) and `llama3.2:3b-16k` (thinker). No cloud fallback.
- `loop.py` runs the tool-calling loop (max 2 calls/step, forced first tool call, slop retry). `mcp_client.py` opens `docker mcp gateway run --profile <p>` plus native stdio servers behind one `Router`; for the native `codebase` server it injects `project` automatically (`config.CODEBASE_PROJECT`, derived from the checkout path; reindex with `index_repository` after adding files).
- `compose.py` + `docker-compose.yml` (project `ts-mcp`): roles with `compose: [...]` in `personas.yaml` get their backends (crawl4ai, searxng, sonarqube, penpot-mcp) started with `up -d --wait` before the run and stopped after (`keep_alive` / `MCP_KEEP_ALIVE=1` skips the stop). The stdio wrappers `mcp-crawl4ai` / `mcp-sonarqube` run as native gateway servers. Secrets live in `~/.docker/mcp/mcp.env` (created by `scripts/mcp_up.*`; set `SONARQUBE_TOKEN` there yourself), never in catalogue YAMLs.
- Plan store (`plan.py`): Neo4j (`neo4j` service, profile `plan`, always on from gateway start; the gateway lifespan runs `compose.ensure(["neo4j"])`, and the last gateway process to exit stops every `ts-mcp` container; finished plans are pruned after `PLAN_RETENTION_DAYS`). Graph: `Task -DEPENDS_ON-> Task`, `Task -HAS_RUN-> Run` (links `gateway_task_id` to the SQLite store), `Task -HAS_EVENT-> Event` (status history used by revert), `Task -LINKED_TO-> Commit`. `done` needs evidence (real git sha or a finished gateway task id). `dispatch_task(..., plan_id=N)` claims the task, records the run, then marks done (or blocked). Claude sees only `plan_add/plan_overview/plan_revert/plan_update_from`; workers (tracker role, `.claude/agents/plan-worker.md`) get `plan_next/claim/status/blockers/done/note` from the stdio server `python -m gateway.plan_mcp`. `NEO4J_AUTH` is generated into `~/.docker/mcp/mcp.env`.
- `summarize.py` enforces the 150-300 token cap; `store.py` keeps tasks (SQLite) for `get_detail`/`resume_task`.
- Writable workspace for `ts-fs-rw` needs `:rw` in the catalogue volume and `CC_WORKSPACE` equal to that exact host path.

`delegate_to_local_llm` from the global CLAUDE.md is the legacy tool; `server.py` (root) only has `query_local_llm*`.

> NOTE: local-model routing is defined in ~/.claude/CLAUDE.md (two models via the TokenFrugal gateway). Ignore older model tiers above.
