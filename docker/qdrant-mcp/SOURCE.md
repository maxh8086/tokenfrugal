# qdrant-mcp (tokenfrugal/qdrant-mcp:1)

| Field | Value |
| --- | --- |
| Upstream repo | https://github.com/qdrant/mcp-server-qdrant |
| License | Apache-2.0 (LICENSE in repo root, verified) |
| Pinned commit | `c56ae5adf62bb78d852bf7bbcbc5d7b75e2bbe41` (commit date 2026-08-11, "feat: Add support to use the MCP server as a Kiro Power (#175)") |
| Package version | mcp-server-qdrant 0.8.1 (from pyproject.toml at the pinned commit) |
| Date pinned | 2026-10-31 |
| Base image | `python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159` (pulled 2026-10-31) |
| Image | `tokenfrugal/qdrant-mcp:1`, id `sha256:b239e5f43d8c7e8d4efc5c88c5255ba80e125cd66093fe50b9eee88dbc71cd33`, 813 MB (`docker images`) |
| Dependency lock | upstream `uv.lock` (revision 3), installed with `uv sync --frozen --no-dev`; uv pinned to 0.12.19 |

## How the source is fetched

The Dockerfile clones `https://github.com/qdrant/mcp-server-qdrant` and runs `git checkout --detach c56ae5ad...`.
The build fails unless `git rev-parse HEAD` equals that SHA. No branch, tag or `latest` is used.
Only the upstream `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE` and `src/` are used; nothing is vendored into this folder.

## Tools (as found, `tools/list` at the pinned commit)

- `qdrant-find`: search memories by semantic query in a collection.
- `qdrant-store`: store text (and optional JSON metadata) in a collection.

Both tools accept `collection_name` unless `COLLECTION_NAME` is set. `QDRANT_READ_ONLY=true` removes `qdrant-store`.

## Environment variables

| Name | Required | Secret | Notes |
| --- | --- | --- | --- |
| `QDRANT_URL` | yes, for real use | no | Qdrant server URL, e.g. `http://host.docker.internal:6333`. Not contacted at startup. |
| `QDRANT_API_KEY` | only for secured Qdrant | **yes** | Pass at run time. Never bake into the image. |
| `COLLECTION_NAME` | no | no | Default collection. |
| `EMBEDDING_MODEL` | no | no | Default `sentence-transformers/all-MiniLM-L6-v2` (pre-fetched in the image). Other models are not in the image and fail at startup (see below). |
| `EMBEDDING_PROVIDER` | no | no | Only `fastembed`. Baked as default. |
| `QDRANT_SEARCH_LIMIT` | no | no | Default 10. |
| `QDRANT_READ_ONLY` | no | no | `true` disables `qdrant-store`. |
| `QDRANT_LOCAL_PATH` | no | no | Local on-disk Qdrant. Mutually exclusive with `QDRANT_URL`. Not useful in this container. |
| `TOOL_STORE_DESCRIPTION`, `TOOL_FIND_DESCRIPTION` | no | no | Tool description overrides. |

Qdrant itself is not part of this image. Run it as a separate service and point `QDRANT_URL` at it.

## Embedding model (fastembed)

- At build time the default model is downloaded into `FASTEMBED_CACHE_PATH=/opt/fastembed-cache` (87 MB, in the image).
- `run_offline.py` is the entry wrapper. It defaults fastembed's `local_files_only=True`, then runs the unmodified `mcp_server_qdrant.main`. Without this, the pinned code tries HuggingFace and GCS on every start.
- `HF_HUB_OFFLINE=1` is set at runtime.
- Verified: the smoke test runs with `--network none` and succeeds.
- To use another model, it must be pre-fetched into the cache, which means changing the Dockerfile build step. Otherwise startup fails with an error and never reaches the network.

## Run over stdio

The image has no EXPOSE and publishes no ports. The transport is stdio only (`CMD ["--transport","stdio"]`).

```
docker run --rm -i \
  -e QDRANT_URL=http://host.docker.internal:6333 \
  -e COLLECTION_NAME=my-collection \
  tokenfrugal/qdrant-mcp:1
```

For `QDRANT_API_KEY`, pass the name only (`-e QDRANT_API_KEY`) with the value in the host environment, or mount it from a secret file as in `docker/crawl4ai-mcp/README.txt`. Do not put it in the command line.

The container runs as uid/gid `10001` (`mcp`), not root.

## Build and smoke

```
docker build -t tokenfrugal/qdrant-mcp:1 docker/qdrant-mcp
python docker/qdrant-mcp/smoke.py tokenfrugal/qdrant-mcp:1
```

`smoke.py` runs `docker run --rm -i --network none`, sends initialize and tools/list over stdin, and prints the tool names. Last result: PASS, tools `qdrant-find` and `qdrant-store`.

Notes on what was verified:
- Startup and tools/list succeed with the network disabled and without `QDRANT_URL`.
- `serverInfo.version` reports the mcp SDK version (1.23.0), not the package version.
- Not verified: `qdrant-store` and `qdrant-find` against a live Qdrant server. That needs a separate Qdrant service.
