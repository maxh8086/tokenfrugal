#!/usr/bin/env bash
# Start MCP backends for compose profiles (research security design; default all) and wait until healthy.
# First run creates ~/.docker/mcp/mcp.env (outside the repo) with a random CRAWL4AI_API_TOKEN; set SONARQUBE_TOKEN there yourself.
# Usage: scripts/mcp_up.sh [research] [security] [design] [plan]      (ROTATE=1 regenerates the crawl4ai token)
set -euo pipefail
env_file="${MCP_ENV_FILE:-$HOME/.docker/mcp/mcp.env}"
compose="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"
if [ "${ROTATE:-}" = 1 ] || [ ! -f "$env_file" ]; then
  keep=$( [ -f "$env_file" ] && grep -v '^CRAWL4AI_API_TOKEN=' "$env_file" || printf 'SONARQUBE_TOKEN=\nSONARQUBE_ORG=\n' )
  mkdir -p "$(dirname "$env_file")"; umask 077
  { echo "CRAWL4AI_API_TOKEN=$(openssl rand -hex 32)"; echo "$keep"; } > "$env_file"
  echo "Wrote $env_file (set SONARQUBE_TOKEN there yourself)"
fi
grep -q '^SEARXNG_SECRET=' "$env_file" || echo "SEARXNG_SECRET=$(openssl rand -hex 32)" >> "$env_file"
grep -q "^NEO4J_AUTH=" "$env_file" || echo "NEO4J_AUTH=neo4j/$(openssl rand -hex 16)" >> "$env_file"
export MCP_ENV_FILE="$env_file"
export NEO4J_AUTH="$(grep '^NEO4J_AUTH=' "$env_file" | head -1 | cut -d= -f2-)"
[ $# -gt 0 ] && profiles=("$@") || profiles=(research security design plan)
args=(); svcs=()
for p in "${profiles[@]}"; do
  args+=(--profile "$p")
  case $p in research) svcs+=(crawl4ai searxng);; security) svcs+=(sonarqube);; design) svcs+=(penpot-mcp);; plan) svcs+=(neo4j);; esac
done
docker compose -p ts-mcp -f "$compose" "${args[@]}" up -d --wait "${svcs[@]}"
