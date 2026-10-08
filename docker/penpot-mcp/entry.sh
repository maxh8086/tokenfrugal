#!/bin/sh
# MODE=service : persistent Penpot MCP server (publish 4400-4402 on the host, load the plugin from :4400).
# MODE=bridge  : (default) stdio <-> streamable HTTP bridge for the Docker MCP gateway.
if [ "$MODE" = "service" ]; then
  cd /usr/local/lib/node_modules/@penpot/mcp && exec pnpm run start
else
  exec mcp-remote "${PENPOT_MCP_URL:-http://host.docker.internal:4401/mcp}" --allow-http
fi
