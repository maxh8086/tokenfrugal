# CLAUDE.md (sample for projects that use TokenFrugal)

Copy to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md`) and adjust. Requires the `tokenfrugal` MCP server to be registered.

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

## Code intelligence (synaptree-mcp)

Repo: https://github.com/maxh8086/synaptree-mcp (MCP server `synaptree`). Query the code graph before grepping or reading whole files.

- Check `index_status(project)` first; if stale or missing, run `index_repository(project, root_path)` with the main checkout path, not a worktree.
- Find code: `search_graph` / `search_code`. Callers, callees, references: `trace_path`. Structure: `get_architecture`. Hierarchy: `query_graph` (Cypher over `INHERITS` / `IMPLEMENTS` edges). Read one symbol: `get_code_snippet`.
- Read files directly only after the symbol is located, or for configs and docs the index excludes.
- Re-index after merges.

## Verification

- Run the project's test command after every delegated change; never accept delegated code unrun.
- Mark plan tasks `done` only with evidence (a real git sha or a finished task id).

## Never

- Paste secrets into tasks or chat. Secrets live in `~/.docker/mcp/mcp.env`.
- Add Co-Authored-By trailers or "generated with" footers to commits and PRs, unless you want them.
