# TokenFrugal

**Stop burning your Claude Code / Codex token quota on boilerplate. TokenFrugal hands routine coding, tests, docs, reviews and research to a free local LLM (Ollama or any OpenAI-compatible API) through one small MCP server, and keeps your paid cloud model for architecture and hard decisions.**

Keywords: MCP server, Model Context Protocol, local LLM, Ollama, token saving, reduce Claude Code usage, Codex, LM Studio, vLLM, agent personas, Docker MCP gateway, offline coding assistant.

## The problem it solves

Corporate or entry-level AI subscriptions hit their limits fast. Most of those tokens go to routine work: boilerplate, tests, docstrings, lint fixes, summaries, log reading. A laptop with a GPU (or an Apple Silicon Mac) can do that work for free, but wiring a local model, tools and agents together is tedious.

TokenFrugal does the wiring:

- Your cloud agent calls one tool, `dispatch_task(agent, task)`, and gets back a 150-300 token summary instead of pages of output.
- A local model does the work with a small allowlisted toolset (4-6 tools per role) so small models stay on track.
- 282 [agency-agents](https://github.com/msitarzewski/agency-agents) personas are mapped to 11 roles (builder, analyzer, reviewer, security, docs, designer, browser, research, data, debugger, tracker).
- Failures return a short error and a `task_id` (`resume_task`). No silent cloud fallback, so no surprise spend.

Good fit: side projects, college projects, corporate seats with tight quotas, laptops with a GPU or Apple Silicon.

## Requirements

| Need | Notes |
| --- | --- |
| Python 3.11+ and git | |
| Docker (Desktop, Engine, Colima, Rancher Desktop or Podman with a `docker` shim) | Runs the tool backends. Docker Desktop is free only for personal/education/small-business use; check its licence for your company. |
| Ollama **or any OpenAI-compatible LLM API** | Host and port set in `.env` (`TOKENFRUGAL_LLM_URL`). Default `http://localhost:11434/v1`. |
| Two local models | `ollama pull qwen2.5-coder:3b` and `ollama pull llama3.2:3b` (tags are set in `gateway/personas.yaml`). |
| An MCP-capable agent | Claude Code, Codex, Cursor or any MCP client. |

Check everything at once: `python scripts/doctor.py` (installs nothing; prints exact fix commands).

## Install (Windows, macOS, Linux)

```bash
git clone https://github.com/maxh8086/tokenfrugal.git
cd tokenfrugal
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set TOKENFRUGAL_LLM_URL (host:port) for your LLM
python scripts/doctor.py
```

Start backends once (creates secrets in `~/.docker/mcp/mcp.env`, outside the repo): `scripts/mcp_up.sh` (macOS/Linux) or `scripts/mcp_up.ps1` (Windows). Helper images that wrap upstream tools are built from the Dockerfiles in `docker/` on first use and reused afterwards.

Register with your agent (stdio):

```json
{ "mcpServers": { "tokenfrugal": { "type": "stdio", "command": "python", "args": ["-m", "gateway.server"], "cwd": "<path-to>/tokenfrugal" } } }
```

For Codex use the equivalent `[mcp_servers.tokenfrugal]` table in `~/.codex/config.toml`.

## Use

Ask your agent: "use tokenfrugal to write unit tests for `utils.py`". Tools: `dispatch_task`, `ask_followup`, `get_detail`, `resume_task`, `list_roles`, plus plan tools (`plan_add`, `plan_overview`, ...) backed by Neo4j with automatic retention (`PLAN_RETENTION_DAYS`). `server.py` is a simpler two-tool server if you only want `query_local_llm`.

## FAQ

**Does it send my code to the cloud?** Local models run on your machine; only the short summaries return to your cloud agent.
**Can the small models really code?** For scoped, well-specified tasks yes; that is why tool allowlists and step limits exist. Keep architecture in the cloud model.
**Windows/macOS/Linux?** All three; only git, Docker and Python are called.

## Credits and licence

Apache-2.0 (see [LICENSE](LICENSE), [NOTICE](NOTICE)). Inspired by and built on the work of many authors; see [CREDITS.md](CREDITS.md). Third-party backends run as their own unmodified containers under their own licences.

Developed by Vaibhav Pavtekar with AI assistance (Claude Code).
