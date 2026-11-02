# postgres-mcp (tokenfrugal/postgres-mcp:1)

| Field | Value |
| --- | --- |
| Upstream repo | https://github.com/crystaldba/postgres-mcp |
| License | MIT (LICENSE in repo root, verified: "MIT License, Copyright (c) 2025, Crystal Corp.") |
| Pinned commit | `15c8e33353546148acc2d8bd784551cf3905d1e2` (commit date 2026-08-15, "fix: Pin mcp[cli]<2.0 to prevent breaking import change #187 (#201)") |
| Package version | postgres-mcp 0.3.0 (from pyproject.toml at the pinned commit) |
| Date pinned | 2026-10-31 |
| Base image | `python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159` (pulled 2026-10-31) |
| Image | `tokenfrugal/postgres-mcp:1`, id `sha256:a58514cc2baaf66160ad99ca0352eaaa6409e9643b22b5f767b2f570e434063e`, 408 MB (`docker images`) |
| Dependency lock | upstream `uv.lock` (revision 3), installed with `uv sync --frozen --no-dev`; uv pinned to 0.12.19 |

## How the source is fetched

The Dockerfile clones `https://github.com/crystaldba/postgres-mcp` and runs `git checkout --detach 15c8e333...`.
The build fails unless `git rev-parse HEAD` equals that SHA. No branch, tag or `latest` is used.
Only the upstream `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE` and `src/` are used; nothing is vendored into this folder.
Upstream's own `Dockerfile` and `docker-entrypoint.sh` are not used. The entrypoint is the `postgres-mcp` console script directly.

## Access mode

- Image default: `CMD ["--access-mode=restricted", "--transport=stdio"]`. This is the read-only mode.
- Upstream's own default is unrestricted. This image overrides it.
- Passing any argument to `docker run` replaces the whole CMD. To run unrestricted you must pass `--access-mode=unrestricted --transport=stdio` yourself. Unrestricted is for development only.

### Tools in restricted mode (`tools/list` verified)

All nine tools have `readOnlyHint: true`.

- `list_schemas`: list schemas.
- `list_objects`: list tables, views, sequences, extensions in a schema.
- `get_object_details`: columns, constraints, indexes for an object.
- `explain_query`: execution plan for a SQL statement.
- `execute_sql`: "Execute a read-only SQL query". The restricted-mode driver runs statements inside read-only transactions with an execution-time limit.
- `analyze_workload_indexes`: index recommendations from `pg_stat_statements`. Needs that extension.
- `analyze_query_indexes`: index recommendations for up to 10 given queries. Uses `hypopg` when it is installed in the database.
- `analyze_db_health`: health checks (index, buffer, connection, constraint, sequence, replication, vacuum).
- `get_top_queries`: slowest or most resource-intensive queries from `pg_stat_statements`.

Restricted mode was not checked against a live database. The read-only claim comes from upstream's README and the `execute_sql` description, not from a write test here.

## Environment variables

| Name | Required | Secret | Notes |
| --- | --- | --- | --- |
| `DATABASE_URI` | yes | **yes** | Connection URL, e.g. `postgresql://user:pass@host.docker.internal:5432/db`. Supply at run time. Never baked into the image. The env value wins over a positional argument. |
| `OPENAI_API_KEY` | only for `method="llm"` | **yes** | Read by the OpenAI client in `index/llm_opt.py`. Only the LLM index-advisor path (`analyze_workload_indexes` / `analyze_query_indexes` with `method="llm"`) uses it. Not needed for the default `dta` method or any other tool. Not exercised here. |
| `OPENAI_BASE_URL` | no | no | Standard OpenAI client variable, used only with the LLM path. |
| `POSTGRES_MCP_INCLUDE_LANGFUSE_TRACE` | no | no | Upstream default `true`. Affects index-advisor output only. |

## Run over stdio

The image has no EXPOSE and publishes no ports. Use `-e DATABASE_URI` with the value in the host environment (or from a secret file, as in `docker/crawl4ai-mcp/README.txt`). Do not put the URL on the command line.

```
docker run --rm -i -e DATABASE_URI tokenfrugal/postgres-mcp:1
```

The container runs as uid/gid `10001` (`mcp`), not root.

If the database is unreachable at startup, the server still starts and only warns. Tool calls fail until the connection works.

## Build and smoke

```
docker build -t tokenfrugal/postgres-mcp:1 docker/postgres-mcp
python docker/postgres-mcp/smoke.py tokenfrugal/postgres-mcp:1
```

`smoke.py` runs `docker run --rm -i --network none`. It uses the host `DATABASE_URI` if set, otherwise a placeholder pointing at a closed local port. It sends initialize and tools/list over stdin and prints the tool names. Last result: PASS, 9 tools.
