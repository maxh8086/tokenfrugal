<#
Start the MCP backends for one or more compose profiles (research, security, design, plan) and wait until healthy.
Backend secrets are Docker secret files in ~/.docker/mcp/secrets (python -m router.secrets_store). Missing random
secrets (CRAWL4AI_API_TOKEN, SEARXNG_SECRET, NEO4J_AUTH) are created on first run; SONARQUBE_TOKEN, TF_DB_PASSWORD and
TF_DB_MSSQL_PASSWORD are set by you: "value" | python -m router.secrets_store set NAME. Values are never printed.
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
    if ($created) { Write-Host "Created in secrets directory: $($created -join ', ')" }
    # the only variable compose needs: the directory of the secret files (no values enter the environment)
    foreach ($line in (& $py -m router.secrets_store export-paths)) {
        $k, $v = $line -split '=', 2
        Set-Item -Path "Env:$k" -Value $v
    }
    $dir = $env:TF_SECRETS_DIR
    $manual = @("SONARQUBE_TOKEN", "TF_DB_PASSWORD", "TF_DB_MSSQL_PASSWORD") | Where-Object { -not (Test-Path (Join-Path $dir $_)) }
    if ($manual) { Write-Host "Not set yet (write each with: python -m router.secrets_store set NAME): $($manual -join ', ')" }
} finally {
    Pop-Location
}
if (-not $Profiles) { $Profiles = @("research", "security", "design", "plan") }
$args = @("compose", "-p", "tokenfrugal", "-f", $compose)
foreach ($p in $Profiles) { $args += @("--profile", $p) }
# backends only (wrappers are started per task by the gateway)
$svc = @{ research = @("crawl4ai", "searxng"); security = "sonarqube"; design = "penpot-mcp"; plan = "neo4j" }
docker @args up -d --wait ($Profiles | ForEach-Object { $svc[$_] })
