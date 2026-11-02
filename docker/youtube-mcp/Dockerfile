# youtube-mcp: YouTube Data API v3 + transcript tools (MCP over stdio).
# Source: https://github.com/kirbah/mcp-youtube at the exact commit below (MIT).
# See SOURCE.md for the review notes, quota table, pins and run instructions.

# ---- build stage: fetch pinned source, install from lockfile, compile ----
FROM node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS build

ARG YT_MCP_REPO=https://github.com/kirbah/mcp-youtube.git
ARG YT_MCP_COMMIT=0ba98f673cf4f2ebdd21edb0ac9d3337c77f4531

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git init -q . \
 && git remote add origin "$YT_MCP_REPO" \
 && git fetch -q --depth 1 origin "$YT_MCP_COMMIT" \
 && git -c advice.detachedHead=false checkout -q FETCH_HEAD \
 && test "$(git rev-parse HEAD)" = "$YT_MCP_COMMIT"

# package-lock.json is present at the pinned commit; npm ci installs exactly that tree.
# --ignore-scripts: no lifecycle scripts from dependencies run during the build.
RUN npm ci --ignore-scripts --no-audit --no-fund \
 && npm run build \
 && npm prune --omit=dev --ignore-scripts \
 && rm -rf /src/.git

# ---- runtime stage ----
FROM node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS runtime

LABEL org.opencontainers.image.title="youtube-mcp" \
      org.opencontainers.image.source="https://github.com/kirbah/mcp-youtube" \
      org.opencontainers.image.licenses="MIT" \
      io.tokenfrugal.source-commit="0ba98f673cf4f2ebdd21edb0ac9d3337c77f4531"

WORKDIR /app
COPY --from=build /src/package.json ./package.json
COPY --from=build /src/dist ./dist
COPY --from=build /src/node_modules ./node_modules
COPY --chmod=0755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Non-root: the official node image provides the unprivileged "node" user (uid 1000).
USER node

# Optional settings (none are set in the image):
#   YOUTUBE_API_KEY        Data API key (or YOUTUBE_API_KEY_FILE pointing at a file with the key)
#   YOUTUBE_API_KEY_FILE   path to a file holding the key, e.g. /run/secrets/youtube_api_key
#   MDB_MCP_CONNECTION_STRING  leave UNSET: enables MongoDB caching and the analytics tool
#                              (also makes the server call dns.setServers to 8.8.8.8/1.1.1.1)
# stdio transport only; no ports are exposed.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
