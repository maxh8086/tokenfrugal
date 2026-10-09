# Credits

TokenFrugal stands on other people's work. Thank you to every author below.
Entries read "inspired from `repo`; owner: name". TokenFrugal bundles none of this source:
upstreams are pulled or built at install time under their own licences.

| Inspired from / used | Owner | Licence | How it is used |
| --- | --- | --- | --- |
| [cc_token_saver_mcp](https://github.com/csabakecskemeti/cc_token_saver_mcp) | Csaba Kecskemeti | none stated | Original idea: Claude Code offloading small tasks to a local LLM via MCP. TokenFrugal's `server.py` is a clean-room rewrite; no code copied. |
| [agency-agents](https://github.com/msitarzewski/agency-agents) | msitarzewski | MIT | The 282 persona slugs mapped to roles in `gateway/personas.yaml`. |
| [synaptree-mcp](https://github.com/maxh8086/synaptree-mcp) | maxh8086 | see repo | Code-graph MCP server used by builder/analyzer/reviewer/debugger roles (installed separately). |
| [mcp-gateway](https://github.com/docker/mcp-gateway) | Docker | MIT | `docker mcp gateway` hosts the allowlisted tool profiles. |
| [crawl4ai](https://github.com/unclecode/crawl4ai) | unclecode | Apache-2.0 | Web crawling backend (pulled image, unchanged). |
| [SearXNG](https://github.com/searxng/searxng) | SearXNG contributors | AGPL-3.0 | Search backend (pulled image, unchanged; only a `settings.yml` is shipped). |
| [SonarQube](https://github.com/SonarSource/sonarqube) | SonarSource | LGPL-3.0 | Security-scan backend (pulled image, unchanged). |
| [Neo4j](https://github.com/neo4j/neo4j) | Neo4j, Inc. | GPL-3.0 (Community) | Plan store (pulled image, unchanged). |
| [Penpot](https://github.com/penpot/penpot) | Kaleidos / Penpot | MPL-2.0 | Design MCP (`@penpot/mcp`), built locally from its npm package. |
| [chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Chrome DevTools team (Google) | Apache-2.0 | Browser role, built locally from its npm package. |
| [FastMCP](https://github.com/PrefectHQ/fastmcp) | PrefectHQ | Apache-2.0 | MCP server framework. |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Model Context Protocol | MIT | MCP client/server plumbing. |
| [Ollama](https://github.com/ollama/ollama) | Ollama | MIT | Default local model runtime. |
| [claude-task-master](https://github.com/eyaltoledano/claude-task-master) | eyaltoledano | MIT with Commons Clause | Idea only (task-graph planning); no code used. |

If you are an author listed here and want a change, please open an issue.
