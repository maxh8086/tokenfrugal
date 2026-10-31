# qdrant-mcp: https://github.com/qdrant/mcp-server-qdrant (Apache-2.0)
# Source is fetched from git at an exact commit and verified before use.
# Dependencies come from the repo's uv.lock (frozen install).
# Qdrant itself is NOT in this image. See SOURCE.md.

ARG BASE=python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ARG QDRANT_MCP_SHA=c56ae5adf62bb78d852bf7bbcbc5d7b75e2bbe41
ARG UV_VERSION=0.12.19

# ---- fetch and verify source at the pinned commit ----
FROM ${BASE} AS source
ARG QDRANT_MCP_SHA
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --no-checkout https://github.com/qdrant/mcp-server-qdrant /src \
 && git -C /src checkout --detach "${QDRANT_MCP_SHA}" \
 && test "$(git -C /src rev-parse HEAD)" = "${QDRANT_MCP_SHA}"

# ---- install locked dependencies and pre-fetch the default embedding model ----
FROM ${BASE} AS builder
ARG UV_VERSION
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    FASTEMBED_CACHE_PATH=/opt/fastembed-cache
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
WORKDIR /app
COPY --from=source /src/pyproject.toml /src/uv.lock /src/README.md /src/LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY --from=source /src/src ./src
RUN uv sync --frozen --no-dev
# Default model from settings.py. Baked in so the container runs with the network disabled.
RUN /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')" \
 && test -d /opt/fastembed-cache

# ---- runtime ----
FROM ${BASE} AS runtime
RUN groupadd --system --gid 10001 mcp \
 && useradd --system --uid 10001 --gid mcp --home-dir /app --shell /usr/sbin/nologin mcp
COPY --from=builder /app /app
COPY --from=builder /opt/fastembed-cache /opt/fastembed-cache
COPY run_offline.py /opt/qdrant-mcp/run_offline.py
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed-cache \
    HF_HUB_OFFLINE=1 \
    EMBEDDING_PROVIDER=fastembed \
    EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
WORKDIR /app
USER mcp
# stdio only: no EXPOSE, no port published. QDRANT_URL / QDRANT_API_KEY / COLLECTION_NAME are supplied at run time.
ENTRYPOINT ["/app/.venv/bin/python", "/opt/qdrant-mcp/run_offline.py"]
CMD ["--transport", "stdio"]
