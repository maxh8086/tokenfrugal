# Model comparison (realworld suite, all cases)

| Model / run tag | Params | Verified | Ran | Mean s/case | write_function<br>Filesystem MCP server (mcp/filesystem)<br>persona: engineering-backend-architect | fix_bug<br>Filesystem MCP server (mcp/filesystem)<br>persona: engineering-backend-architect | write_tests<br>Filesystem MCP server (mcp/filesystem)<br>persona: engineering-backend-architect | rename_across_files<br>Filesystem MCP server (mcp/filesystem)<br>persona: engineering-backend-architect | find_symbol<br>synaptree-mcp (maxh8086/synaptree-mcp)<br>persona: engineering-backend-architect | review_sqli<br>Filesystem MCP server (mcp/filesystem)<br>persona: testing-code-reviewer | debug_trace<br>Filesystem MCP server (mcp/filesystem)<br>persona: engineering-sre | summarize_readme<br>Fetch MCP server (mcp/fetch)<br>persona: support-docs-writer | code_graph_search<br>synaptree-mcp (maxh8086/synaptree-mcp)<br>persona: finance-analyst | list_project_files<br>Filesystem MCP server (mcp/filesystem)<br>persona: gis-analyst | read_docs_file<br>Filesystem MCP server (mcp/filesystem)<br>persona: engineering-technical-writer | security_file_read<br>Filesystem MCP server (mcp/filesystem)<br>persona: security-auditor | design_overview<br>Penpot MCP (penpot/penpot, mcp package)<br>persona: design-ui-designer | browser_navigate_snapshot<br>Chrome DevTools MCP (ChromeDevTools/chrome-devtools-mcp)<br>persona: testing-evidence-collector | plan_status<br>TokenFrugal plan MCP server (this repo, Neo4j backed)<br>persona: project-management-project-shepherd | web_crawl<br>Crawl4AI MCP server (unclecode/crawl4ai)<br>persona: support-docs-writer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| full-ts-qwen3-8b-16384 | 8B | 28/32 | 28/32 | 72.7 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 1/2 | 2/2 | 2/2 |
| full-ts-gemma4-e4b-16384 | 4B eff. (8B raw) | 27/32 | 30/32 | 21.5 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 0/2 | 2/2 | 2/2 |
| confirmB | 7B + 3B | 25/32 | 31/32 | 15.2 | 2/2 | 0/2 | 1/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 |
| full-ts-qwen25c-7b-builder-granite-thinker | 7B + 3B | 24/32 | 30/32 | 16.0 | 2/2 | 1/2 | 1/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 | 2/2 |
| confirmA | 3B + 3B | 24/32 | 32/32 | 14.5 | 2/2 | 1/2 | 0/2 | 0/2 | 1/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 |
| full-ts-qwen25c-7b-16384 | 7B | 23/32 | 30/32 | 13.9 | 2/2 | 1/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 0/2 |
| confirmC | ? | 23/32 | 32/32 | 14.7 | 0/2 | 2/2 | 0/2 | 0/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 |
| full-defaults-yarn3b-llama32 | 3B + 3B | 22/32 | 31/32 | 21.4 | 1/2 | 2/2 | 0/2 | 1/2 | 1/2 | 2/2 | 2/2 | 0/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 1/2 |
| full-ts-qwen2-5-7b-16384 | 7B | 21/32 | 32/32 | 16.6 | 0/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 1/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 0/2 |
| full-ts-ministral-3-8b-16384 | 8B | 21/32 | 30/32 | 26.9 | 0/2 | 0/2 | 1/2 | 0/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 |
| full-ts-qwen3-4b-16384 | 4B | 20/32 | 24/32 | 76.8 | 1/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 0/2 | 1/2 | 0/2 |
| full-ts-michelrosselli-bonsai-27b-16384 | 27B | 20/32 | 23/32 | 57.3 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 1/2 | 0/2 | 2/2 | 0/2 | 0/2 | 1/2 |
| full-llama3-2-3b-16k | 3B | 20/32 | 29/32 | 15.2 | 0/2 | 0/2 | 0/2 | 0/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 |
| full-yarn3b-solo | ? | 15/32 | 27/32 | 20.7 | 1/2 | 1/2 | 0/2 | 0/2 | 1/2 | 1/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 | 1/2 | 0/2 |
| full-ts-llama3-1-8b-16384 | 8B | 15/32 | 21/32 | 28.7 | 0/2 | 0/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 0/2 | 1/2 | 2/2 | 2/2 | 0/2 | 2/2 | 0/2 | 0/2 | 0/2 |
| full-ts-phi4-mini-16384 | 3.8B | 2/32 | 5/32 | 14.0 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 2/2 | 0/2 | 0/2 | 0/2 |
| full-ts-starcoder2-7b-16384 | 7B | 0/32 | 0/32 | 8.0 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| full-ts-qwen2-5vl-7b-16384 | 7B | 0/32 | 0/32 | 7.9 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| full-ts-granite3-3-8b-16384 | 8B | 0/32 | 0/32 | 41.9 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| full-ts-gemma3-4b-16384 | 4B | 0/32 | 0/32 | 7.9 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| full-ts-deepseek-r1-8b-16384 | 8B | 0/32 | 0/32 | 137.1 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
