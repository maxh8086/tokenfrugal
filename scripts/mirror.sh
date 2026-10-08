#!/usr/bin/env bash
# Maintainer-run: build and push the three Docker-built wrapper images to GHCR as a fallback
# if an upstream npm package/repo disappears. Only images built from repo Dockerfiles are mirrored;
# unmodified third-party images (SearXNG, SonarQube, Neo4j, crawl4ai) are never re-pushed.
# Prereq: docker login ghcr.io  (you do this yourself; this script never handles credentials).
set -euo pipefail
OWNER="${GHCR_OWNER:-maxh8086}"; VER="${1:?usage: mirror.sh <version-tag>}"
SRC="https://github.com/$OWNER/tokenfrugal"
declare -A LIC=([crawl4ai-mcp]="Apache-2.0" [penpot-mcp]="MPL-2.0" [chrome-devtools-mcp]="Apache-2.0")
for n in crawl4ai-mcp penpot-mcp chrome-devtools-mcp; do
  img="ghcr.io/$OWNER/tokenfrugal-$n:$VER"
  docker build -t "$img" -t "tokenfrugal/$n:1" \
    --label "org.opencontainers.image.source=$SRC" \
    --label "org.opencontainers.image.licenses=${LIC[$n]}" \
    --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" "docker/$n"
  docker push "$img"
  docker inspect --format '{{index .RepoDigests 0}}' "$img"
done
echo "Record the printed digests in docs/mirror.md. Third-party licences: see CREDITS.md."
