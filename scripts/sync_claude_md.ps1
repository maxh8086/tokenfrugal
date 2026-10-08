# Replace stale local-model routing text in per-project CLAUDE.md files with a pointer to the global rule.
# Usage: .\scripts\sync_claude_md.ps1 -Root C:\Users\you\Projects [-Apply]
param([string]$Root = "$HOME\Downloads\Projects", [switch]$Apply)
Get-ChildItem $Root -Recurse -Filter CLAUDE.md -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '[\/](node_modules|[.]venv)[\/]' } | ForEach-Object {
  if (Select-String -Path $_.FullName -Pattern 'deepseek-r1-prd|qwen2\.5-coder-prd|delegate_to_local_llm' -Quiet) {
    Write-Host "STALE: $($_.FullName)"
    if ($Apply) { Copy-Item $_.FullName "$($_.FullName).bak" -Force
      Add-Content $_.FullName "`n> NOTE: local-model routing is defined in ~/.claude/CLAUDE.md (two models via the TokenFrugal gateway). Ignore older model tiers above." }
  }
}
