<#
Start the MCP backends for one or more compose profiles (research, security, design, plan) and wait until healthy.
First run creates ~/.docker/mcp/mcp.env (outside the repo) with a random CRAWL4AI_API_TOKEN and an empty
SONARQUBE_TOKEN line; set the SonarQube token there yourself. Token values are never printed.
Usage: powershell -File scripts/mcp_up.ps1 [research] [security] [design] [plan] [-Rotate]   (no profile = all)
#>
param([switch]$Rotate, [Parameter(ValueFromRemainingArguments)][string[]]$Profiles)
$ErrorActionPreference = "Stop"
$envFile = if ($env:MCP_ENV_FILE) { $env:MCP_ENV_FILE } else { Join-Path $HOME ".docker\mcp\mcp.env" }
$compose = Join-Path (Split-Path $PSScriptRoot) "docker-compose.yml"
if ($Rotate -or -not (Test-Path $envFile)) {
    $old = if (Test-Path $envFile) { Get-Content $envFile | Where-Object { $_ -notmatch '^CRAWL4AI_API_TOKEN=' } } else { @("SONARQUBE_TOKEN=", "SONARQUBE_ORG=") }
    $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    New-Item -ItemType Directory -Force (Split-Path $envFile) | Out-Null
    (@("CRAWL4AI_API_TOKEN=" + ([BitConverter]::ToString($b) -replace '-', '').ToLower()) + $old) | Set-Content $envFile -Encoding ascii
    Write-Host "Wrote $envFile (see README step 3 for SONARQUBE_TOKEN)"
}
if (-not (Select-String -Path $envFile -Pattern '^SEARXNG_SECRET=' -Quiet)) {
    $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    Add-Content $envFile ("SEARXNG_SECRET=" + ([BitConverter]::ToString($b) -replace '-', '').ToLower()) -Encoding ascii
}
if (-not (Select-String -Path $envFile -Pattern '^NEO4J_AUTH=' -Quiet)) {
    $b = New-Object byte[] 16; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    Add-Content $envFile ("NEO4J_AUTH=neo4j/" + ([BitConverter]::ToString($b) -replace '-', '').ToLower()) -Encoding ascii
}
$env:MCP_ENV_FILE = $envFile
$env:NEO4J_AUTH = ((Select-String -Path $envFile -Pattern '^NEO4J_AUTH=' | Select-Object -First 1).Line -replace '^NEO4J_AUTH=', '')
if (-not $Profiles) { $Profiles = @("research", "security", "design", "plan") }
$args = @("compose", "-p", "ts-mcp", "-f", $compose)
foreach ($p in $Profiles) { $args += @("--profile", $p) }
# backends only (wrappers are started per task by the gateway)
$svc = @{ research = @("crawl4ai", "searxng"); security = "sonarqube"; design = "penpot-mcp"; plan = "neo4j" }
docker @args up -d --wait ($Profiles | ForEach-Object { $svc[$_] })
