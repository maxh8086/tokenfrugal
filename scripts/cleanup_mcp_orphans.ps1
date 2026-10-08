# Remove orphaned Docker MCP containers left behind by killed `docker mcp gateway run` processes.
# Each gateway session starts its own stdio container per server (e.g. mongodb); on Windows a hard-killed
# gateway never stops them, so they pile up.
# - No gateway alive: remove every labelled container.
# - Gateways alive: per server name keep the newest <gateway count> containers, remove older extras
#   that are also at least -MinAgeMinutes old (so a just-started session is never touched).
param([int]$MinAgeMinutes = 10)
$gw = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'mcp gateway run' })
$ids = @(docker ps -aq --filter label=docker-mcp=true)
if (-not $ids) { Write-Host "None."; exit 0 }
if ($gw.Count -eq 0) {
    docker rm -f $ids | Out-Null
    Write-Host "Removed $($ids.Count) orphan MCP container(s)."
    exit 0
}
$rows = docker inspect $ids | ConvertFrom-Json | ForEach-Object {
    [pscustomobject]@{
        Id      = $_.Id
        Name    = $_.Config.Labels.'docker-mcp-name'
        Started = [datetime]$_.Created
    }
}
$cut = (Get-Date).AddMinutes(-$MinAgeMinutes)
$stale = $rows | Group-Object Name | ForEach-Object {
    $_.Group | Sort-Object Started -Descending | Select-Object -Skip $gw.Count | Where-Object { $_.Started -lt $cut }
}
if ($stale) {
    docker rm -f @($stale.Id) | Out-Null
    Write-Host "Removed $(@($stale).Count) surplus MCP container(s) (kept $($gw.Count) per server)."
} else { Write-Host "No surplus containers." }
