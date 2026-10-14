<#
Start the MCP backends for one or more compose profiles (research, security, design, plan) and wait until healthy.
Backend secrets live in the OS secret store (python -m router.secrets_store), not in a file. Missing random
secrets (CRAWL4AI_API_TOKEN, SEARXNG_SECRET, NEO4J_AUTH) are created on first run; SONARQUBE_TOKEN and SONARQUBE_ORG
are set by you: python -m router.secrets_store set SONARQUBE_TOKEN. Values are never printed.
Usage: powershell -File scripts/mcp_up.ps1 [research] [security] [design] [plan] [-Rotate]   (no profile = all)
#>
param([switch]$Rotate, [Parameter(ValueFromRemainingArguments)][string[]]$Profiles)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
$compose = Join-Path $root "docker-compose.yml"
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Push-Location $root
try {
    if ($Rotate) { & $py -m router.secrets_store delete CRAWL4AI_API_TOKEN | Out-Null }
    $created = & $py -m router.secrets_store ensure-generated
    if ($LASTEXITCODE -ne 0) { throw "router.secrets_store ensure-generated failed (see message above)" }
    if ($created) { Write-Host "Created in OS secret store: $($created -join ', ')" }
    # NAME=value lines; set them in this process only so docker compose can read them
    foreach ($line in (& $py -m router.secrets_store export-env)) {
        $k, $v = $line -split '=', 2
        Set-Item -Path "Env:$k" -Value $v
    }
} finally {
    Pop-Location
}
if (-not $Profiles) { $Profiles = @("research", "security", "design", "plan") }
$args = @("compose", "-p", "ts-mcp", "-f", $compose)
foreach ($p in $Profiles) { $args += @("--profile", $p) }
# backends only (wrappers are started per task by the gateway)
$svc = @{ research = @("crawl4ai", "searxng"); security = "sonarqube"; design = "penpot-mcp"; plan = "neo4j" }
docker @args up -d --wait ($Profiles | ForEach-Object { $svc[$_] })
