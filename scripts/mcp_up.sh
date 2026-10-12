#!/usr/bin/env bash
# Start MCP backends for compose profiles (research security design plan; default all) and wait until healthy.
# Backend secrets live in the OS secret store (python -m gateway.secrets_store), not in a file. Random secrets
# (CRAWL4AI_API_TOKEN, SEARXNG_SECRET, NEO4J_AUTH) are created on first run; set SONARQUBE_TOKEN yourself:
#   python -m gateway.secrets_store set SONARQUBE_TOKEN
# Usage: scripts/mcp_up.sh [research] [security] [design] [plan]      (ROTATE=1 regenerates the crawl4ai token)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
compose="$root/docker-compose.yml"
py="$root/.venv/bin/python"
[ -x "$py" ] || py="$root/.venv/Scripts/python.exe"
[ -x "$py" ] || py=python3
cd "$root"
if [ "${ROTATE:-}" = 1 ]; then "$py" -m gateway.secrets_store delete CRAWL4AI_API_TOKEN >/dev/null || true; fi
created="$("$py" -m gateway.secrets_store ensure-generated)"
if [ -n "$created" ]; then echo "Created in OS secret store: $(echo "$created" | tr '\n' ' ')"; fi
# NAME=value lines; exported into this shell only so docker compose can read them. Values are never printed.
while IFS= read -r line; do export "$line"; done < <("$py" -m gateway.secrets_store export-env)
[ $# -gt 0 ] && profiles=("$@") || profiles=(research security design plan)
args=(); svcs=()
for p in "${profiles[@]}"; do
  args+=(--profile "$p")
  case $p in research) svcs+=(crawl4ai searxng);; security) svcs+=(sonarqube);; design) svcs+=(penpot-mcp);; plan) svcs+=(neo4j);; esac
done
docker compose -p ts-mcp -f "$compose" "${args[@]}" up -d --wait "${svcs[@]}"
