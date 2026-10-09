# AGENTS.md (sample for projects that use TokenFrugal)

Guidance for Codex, Cursor and other MCP-capable agents. Requires the `tokenfrugal` MCP server to be registered in your client.

- Delegate routine work (code, tests, docstrings, lint fixes, summaries, log reading) with `dispatch_task(agent, task)`. Keep architecture and hard decisions for yourself.
- Pick an `agent` slug from `list_roles`. Results are 150-300 token summaries; use `get_detail(task_id)` sparingly.
- On failure call `resume_task(task_id)` once, then split the task. There is no cloud fallback.
- For multi-step work use `plan_add`, then pass `plan_id` to `dispatch_task`. A task is `done` only with evidence (git sha or finished task id).
- Use the `synaptree` MCP server (https://github.com/maxh8086/synaptree-mcp) to find code before reading files: `index_status`, then `search_graph` / `search_code`, `trace_path` for callers and callees, `get_code_snippet` for one symbol. Re-index after merges.
- Pass file paths, not file contents. Local models have 16k-32k context.
- Run the project's tests after every delegated change.
- Never print or commit secrets (`~/.docker/mcp/mcp.env` holds them).
