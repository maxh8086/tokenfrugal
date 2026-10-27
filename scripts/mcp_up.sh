#!/usr/bin/env bash
# Start MCP backends for compose profiles (research security design plan; default all) and wait until healthy.
# Backend secrets are Docker secret files in ~/.docker/mcp/secrets (python -m router.secrets_store). Random secrets
# (CRAWL4AI_API_TOKEN, SEARXNG_SECRET, NEO4J_AUTH) are created on first run; set SONARQUBE_TOKEN, TF_DB_PASSWORD and
# TF_DB_MSSQL_PASSWORD yourself, with the value on stdin:
#   printf '%s' "$VALUE" | python -m router.secrets_store set NAME
# Usage: scripts/mcp_up.sh [research] [security] [design] [plan]      (ROTATE=1 regenerates the crawl4ai token)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
compose="$root/docker-compose.yml"
py="$root/.venv/bin/python"
[ -x "$py" ] || py="$root/.venv/Scripts/python.exe"
[ -x "$py" ] || py=python3
cd "$root"
if [ "${ROTATE:-}" = 1 ]; then "$py" -m router.secrets_store delete CRAWL4AI_API_TOKEN >/dev/null || true; fi
created="$("$py" -m router.secrets_store ensure-generated)"
if [ -n "$created" ]; then echo "Created in secrets directory: $(echo "$created" | tr '\n' ' ')"; fi
# the only variable compose needs: the directory of the secret files. No secret value enters the environment.
while IFS= read -r line; do export "$line"; done < <("$py" -m router.secrets_store export-paths)
for n in SONARQUBE_TOKEN TF_DB_PASSWORD TF_DB_MSSQL_PASSWORD; do
  [ -f "$TF_SECRETS_DIR/$n" ] || echo "Not set yet (write with: printf '%s' VALUE | $py -m router.secrets_store set $n): $n"
done
[ $# -gt 0 ] && profiles=("$@") || profiles=(research security design plan)
args=(); svcs=()
for p in "${profiles[@]}"; do
  args+=(--profile "$p")
  case $p in research) svcs+=(crawl4ai searxng);; security) svcs+=(sonarqube);; design) svcs+=(penpot-mcp);; plan) svcs+=(neo4j);; esac
done
docker compose -p tokenfrugal -f "$compose" "${args[@]}" up -d --wait "${svcs[@]}"
