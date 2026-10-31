# rss-mcp: RSS/Atom + RSSHub feed reader (MCP over stdio).
# Source: https://github.com/veithly/rss-mcp at the exact commit below (Apache-2.0).
# See SOURCE.md for the review notes, pins and run instructions.

# ---- build stage: fetch pinned source, install from lockfile, compile ----
FROM node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS build

ARG RSS_MCP_REPO=https://github.com/veithly/rss-mcp.git
ARG RSS_MCP_COMMIT=f0713aaeebef6129f277f2f4d524361751606011

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git init -q . \
 && git remote add origin "$RSS_MCP_REPO" \
 && git fetch -q --depth 1 origin "$RSS_MCP_COMMIT" \
 && git -c advice.detachedHead=false checkout -q FETCH_HEAD \
 && test "$(git rev-parse HEAD)" = "$RSS_MCP_COMMIT"

# package-lock.json is present at the pinned commit; npm ci installs exactly that tree.
# --ignore-scripts: no lifecycle scripts from dependencies run during the build.
RUN npm ci --ignore-scripts --no-audit --no-fund \
 && npm run build \
 && npm prune --omit=dev --ignore-scripts \
 && rm -rf /src/.git

# ---- runtime stage ----
FROM node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS runtime

LABEL org.opencontainers.image.title="rss-mcp" \
      org.opencontainers.image.source="https://github.com/veithly/rss-mcp" \
      org.opencontainers.image.licenses="Apache-2.0" \
      io.tokenfrugal.source-commit="f0713aaeebef6129f277f2f4d524361751606011"

WORKDIR /app
COPY --from=build /src/package.json ./package.json
COPY --from=build /src/dist ./dist
COPY --from=build /src/node_modules ./node_modules

# Non-root: the official node image provides the unprivileged "node" user (uid 1000).
# App files are root-owned and read-only to that user.
USER node

# stdio transport only; no ports are exposed.
ENTRYPOINT ["node", "/app/dist/index.js"]
