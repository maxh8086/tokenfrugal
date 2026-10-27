<# Stop the MCP backends (data volumes kept). Usage: powershell -File scripts/mcp_down.ps1 [-Remove] #>
param([switch]$Remove)
# compose parses the secrets: block even for stop, so the secrets directory must be set (no values are read)
$env:TF_SECRETS_DIR = (& python -m router.secrets_store export-paths) -replace '^TF_SECRETS_DIR=', ''
$compose = Join-Path (Split-Path $PSScriptRoot) "docker-compose.yml"
$a = @("compose", "-p", "tokenfrugal", "-f", $compose, "--profile", "research", "--profile", "security", "--profile", "design", "--profile", "plan")
if ($Remove) { docker @a down } else { docker @a stop }
