#!/usr/bin/env bash
# Stop the MCP backends (volumes kept). Pass --remove to also remove containers.
export MCP_ENV_FILE="${MCP_ENV_FILE:-$HOME/.docker/mcp/mcp.env}"
compose="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"
a=(compose -p ts-mcp -f "$compose" --profile research --profile security --profile design --profile plan)
if [ "${1:-}" = --remove ]; then docker "${a[@]}" down; else docker "${a[@]}" stop; fi
