# tokenfrugal/reddit-mcp:1 - ekatiyar/simple-reddit-mcp, read-only Reddit tools over the Arctic Shift archive.
# Source is fetched by exact commit SHA and verified; deps come from the repo's uv.lock (frozen install).
# See SOURCE.md for the review record. stdio only; no ports; runs as uid 10001.
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS src
ARG SRC_REPO=https://github.com/ekatiyar/simple-reddit-mcp.git
ARG SRC_SHA=6011105882d447847265dc040823261dbd14d011
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN git init -q /src \
 && cd /src \
 && git remote add origin "$SRC_REPO" \
 && git fetch -q --depth 1 origin "$SRC_SHA" \
 && git checkout -q --detach FETCH_HEAD \
 && test "$(git rev-parse HEAD)" = "$SRC_SHA" \
 && rm -rf /src/.git

FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
ARG UV_VERSION=0.12.19
RUN pip install --no-cache-dir "uv==${UV_VERSION}" \
 && useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY --from=src /src /app
RUN uv sync --frozen --no-dev --no-editable \
 && chown -R root:root /app \
 && chmod -R a+rX /app
USER 10001:10001
ENTRYPOINT ["/app/.venv/bin/simple-reddit-mcp"]
