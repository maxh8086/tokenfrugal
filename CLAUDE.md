# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

TokenFrugal is an MCP gateway (`gateway/`, FastMCP, stdio) that lets a cloud agent hand routine work to local LLMs (Ollama or any OpenAI-compatible endpoint) and get back a 150-300 token summary. Python 3.11+ (3.10.0 breaks pydantic). The root `server.py` is the legacy single-file server (`query_local_llm*`); the gateway supersedes it.

## Commands

```bash
python -m venv .venv && pip install -r requirements.txt
cp .env.example .env                      # set TOKENFRUGAL_LLM_URL; CC_WORKSPACE = folder the file tools may write
python scripts/doctor.py                  # checks Python, Docker, LLM endpoint, models; prints fix commands
PYTHONPATH=. python -m unittest discover -s tests -t . -q     # offline tests
scripts/mcp_up.sh | scripts/mcp_up.ps1   # start ts-mcp backends (compose project `ts-mcp`)
python scripts/install_profiles.py       # import Docker MCP profiles (--workspace PATH to override CC_WORKSPACE)
python scripts/smoke.py                  # live role smoke tests; `smoke.py security` needs SONARQUBE_TOKEN
python -m scripts.smoke_plan             # live Neo4j plan-store smoke (prune, checkpoint, evidence rules)
python -m gateway.server                 # run the gateway (normally launched by the MCP client)
```

## Delegation rules

You are the lead architect. Keep cloud tokens for design, cross-module reasoning and decisions. Hand routine work to the local models through the `tokenfrugal` MCP server.

| Work | Call |
| --- | --- |
| Code, tests, fixtures, schemas, docstrings, regex, lint fixes | `dispatch_task(agent="engineering-...", task="...")` (builder role) |
| Debugging, code review, analysis, summaries, research notes | `dispatch_task(agent="...", task="...")` (thinker roles) |
| Multi-step work | `plan_add` first, then `dispatch_task(..., plan_id=N)` per task |

Use `list_roles` to see agent slugs. Replies are capped summaries; call `get_detail(task_id)` only when you need the full output. On failure call `resume_task(task_id)` once, then re-scope the task smaller. There is no cloud fallback.

## Context budget

Local models run 16k-32k context. Point them at file paths in the workspace instead of pasting files. Pass only signatures and the types they need.

## Verification

- Run the project's test command after every delegated change; never accept delegated code unrun.
- Mark plan tasks `done` only with evidence (a real git sha or a finished task id).

## Never

- Paste secrets into tasks or chat. Secrets live in `~/.docker/mcp/mcp.env`.
- Add Co-Authored-By trailers or "generated with" footers to commits and PRs, unless you want them.

Register in an MCP client: `{"mcpServers": {"tokenfrugal": {"type": "stdio", "command": "python", "args": ["-m", "gateway.server"], "cwd": "<path>/tokenfrugal"}}}`. Use the venv's python on Windows.

## Architecture

- Tools exposed to the agent: `dispatch_task`, `ask_followup`, `get_detail`, `resume_task`, `list_roles`, plus `plan_add/plan_overview/plan_revert/plan_update_from`. Changing tool docstrings changes delegation behaviour.
- `gateway/personas.yaml` maps agency-agents slugs (division prefix, longest match, plus overrides) to a role = model + Docker MCP profile + 4-6 allowlisted tools (+ optional `native:` servers). Only two local models: builder `qwen2.5-coder-yarn:3b`, thinker `llama3.2:3b-16k`. No cloud fallback: failures return a short error and a `task_id` for `resume_task`.
- `loop.py` is the tool-calling loop (max 2 calls/step, forced first tool call, slop retry). `mcp_client.py` opens `docker mcp gateway run --profile <p>` and native stdio servers behind one `Router`. `summarize.py` enforces the token cap; `store.py` (SQLite, `gateway/tasks.db`) backs `get_detail`/`resume_task`.
- `compose.py` + `docker-compose.yml` (project `ts-mcp`): roles with `compose: [...]` start their backends (`up -d --wait`) before a run and stop them after (`keep_alive` / `MCP_KEEP_ALIVE=1` skips the stop). The last gateway process to exit stops every `ts-mcp` container. Leave other compose projects alone.
- Plan store (`plan.py`, Neo4j service `neo4j`, host 127.0.0.1:7697): `Task -DEPENDS_ON-> Task`, `Task -HAS_RUN-> Run`, `Task -HAS_EVENT-> Event`, `Task -LINKED_TO-> Commit`. `done` needs evidence (real git sha or finished gateway task id). Finished plans are pruned after `PLAN_RETENTION_DAYS` (default 30). Workers use the stdio server `python -m gateway.plan_mcp`.
- Docker MCP profiles live in `profiles/*.yaml` with a `__WORKSPACE__` placeholder; `scripts/install_profiles.py` fills it in and builds helper images `tokenfrugal/chrome-devtools-mcp:1` and `tokenfrugal/penpot-mcp:1`.
- Secrets (`SONARQUBE_TOKEN`, `NEO4J_AUTH`, ...) live in `~/.docker/mcp/mcp.env`, never in the repo or catalogue YAMLs.
- Writable workspace for `ts-fs-rw` needs `:rw` in the catalogue volume and `CC_WORKSPACE` equal to that exact host path.

## Code intelligence (synaptree-mcp)

Repo: https://github.com/maxh8086/synaptree-mcp (MCP server `synaptree`, local checkout at `SYNAPTREE_DIR`, project name `SYNAPTREE_PROJECT`, default `tokenfrugal`). Query the code graph before grepping or reading whole files.

- Check `index_status(project)` first; if stale or missing, run `index_repository(project, root_path)` with the main checkout path, not a worktree.
- Find code: `search_graph` / `search_code`. Callers, callees, references: `trace_path`. Structure: `get_architecture`. Hierarchy: `query_graph` (Cypher over `INHERITS` / `IMPLEMENTS` edges). Read one symbol: `get_code_snippet`.
- Read files directly only after the symbol is located, or for configs, docs and files the index excludes.
- Delegated roles builder, analyzer, reviewer and debugger get `synaptree` as a native server; the Router injects `project` automatically.
- Re-index after merges.

## Conventions

- Commits have the human author only: no Co-Authored-By trailer, no "generated with" footer.
- Ask before installing Docker or other software; `scripts/doctor.py` only reports.
- Samples for downstream projects: `examples/CLAUDE.md.sample`, `examples/AGENTS.md.sample`.


