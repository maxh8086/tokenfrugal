<# Stop the MCP backends (data volumes kept). Usage: powershell -File scripts/mcp_down.ps1 [-Remove] #>
param([switch]$Remove)
$env:MCP_ENV_FILE = if ($env:MCP_ENV_FILE) { $env:MCP_ENV_FILE } else { Join-Path $HOME ".docker\mcp\mcp.env" }
$compose = Join-Path (Split-Path $PSScriptRoot) "docker-compose.yml"
$a = @("compose", "-p", "ts-mcp", "-f", $compose, "--profile", "research", "--profile", "security", "--profile", "design", "--profile", "plan")
if ($Remove) { docker @a down } else { docker @a stop }
