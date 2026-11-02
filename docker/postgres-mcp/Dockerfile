# postgres-mcp: https://github.com/crystaldba/postgres-mcp (MIT)
# Source is fetched from git at an exact commit and verified before use.
# Dependencies come from the repo's uv.lock (frozen install).
# Default is --access-mode=restricted (read-only). DATABASE_URI is supplied at run time, never baked. See SOURCE.md.

ARG BASE=python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ARG PG_MCP_SHA=15c8e33353546148acc2d8bd784551cf3905d1e2
ARG UV_VERSION=0.12.19

# ---- fetch and verify source at the pinned commit ----
FROM ${BASE} AS source
ARG PG_MCP_SHA
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --no-checkout https://github.com/crystaldba/postgres-mcp /src \
 && git -C /src checkout --detach "${PG_MCP_SHA}" \
 && test "$(git -C /src rev-parse HEAD)" = "${PG_MCP_SHA}"

# ---- install locked dependencies ----
FROM ${BASE} AS builder
ARG UV_VERSION
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
WORKDIR /app
COPY --from=source /src/pyproject.toml /src/uv.lock /src/README.md /src/LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY --from=source /src/src ./src
RUN uv sync --frozen --no-dev

# ---- runtime ----
FROM ${BASE} AS runtime
RUN groupadd --system --gid 10001 mcp \
 && useradd --system --uid 10001 --gid mcp --home-dir /app --shell /usr/sbin/nologin mcp
COPY --from=builder /app /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER mcp
# stdio only: no EXPOSE, no port published.
# Read-only is the default. To run unrestricted, pass --access-mode=unrestricted explicitly
# (this replaces the whole CMD, so also pass --transport=stdio if you override it).
ENTRYPOINT ["/app/.venv/bin/postgres-mcp"]
CMD ["--access-mode=restricted", "--transport=stdio"]
