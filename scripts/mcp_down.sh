#!/usr/bin/env bash
# Stop the MCP backends (volumes kept). Pass --remove to also remove containers.
# compose parses the secrets: block even for stop, so the secrets directory must be set (no values are read)
export TF_SECRETS_DIR="${TF_SECRETS_DIR:-$HOME/.docker/mcp/secrets}"
compose="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"
a=(compose -p tokenfrugal -f "$compose" --profile research --profile security --profile design --profile plan)
if [ "${1:-}" = --remove ]; then docker "${a[@]}" down; else docker "${a[@]}" stop; fi
