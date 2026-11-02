# tokenfrugal/hn-mcp:1 - erithwik/mcp-hn, Hacker News tools over the Algolia HN Search API (read-only, no key).
# Source is fetched by exact commit SHA and verified; deps come from the repo's uv.lock (frozen install).
# One documented patch is applied (see SOURCE.md, finding F1): a stray debug print() in hn.py that writes to
# stdout would corrupt the MCP stdio stream. The patch is verified by grep at build time.
# stdio only; no ports; runs as uid 10001.
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS src
ARG SRC_REPO=https://github.com/erithwik/mcp-hn.git
ARG SRC_SHA=a454f624e6b1171e0e3dbe0c9eafd2830565190f
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
# F1: remove the debug print(url) in search_stories (stdout is the MCP channel). Fail if the line is not as expected.
RUN grep -c '^    print(url)$' /src/src/mcp_hn/hn.py | grep -qx 1 \
 && sed -i '/^    print(url)$/d' /src/src/mcp_hn/hn.py \
 && test "$(grep -c 'print(' /src/src/mcp_hn/hn.py)" = 0

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
 && chmod -R a+rX /app
USER 10001:10001
ENTRYPOINT ["/app/.venv/bin/mcp-hn"]
