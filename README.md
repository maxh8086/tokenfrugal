<p align="center"><img src="assets/logo.svg" alt="tokenfrugal" width="420"></p>

# TokenFrugal

**Hand routine coding work to a free local LLM, and keep your paid cloud model for planning and hard decisions.**

TokenFrugal is an MCP server. Your cloud agent (Claude Code, Codex, Cursor or any MCP client) calls one tool, `dispatch_task(agent, task)`. A local model does the work and returns a 150-300 token summary, so your cloud quota pays for thinking, not for boilerplate.

## Why TokenFrugal

- **Lower token spend.** Tests, docstrings, lint fixes, file edits and log reading go to a local model. The cloud agent only sees a short summary.
- **Private by default.** Local models run on your machine. Only summaries and a `task_id` return to the cloud agent.
- **No surprise bills.** A failed task returns a short error and a `task_id` you can resume. Nothing falls back silently to the cloud.
- **Small models that stay on track.** Each role gets a tool allowlist of 4-6 tools, and runs one model at a time.
- **Visible and auditable.** A live dashboard shows every tool call, and the task log is stored locally.

## Use cases

1. **Stretching a limited subscription.** Your seat has tight limits. Send unit tests, docstrings and boilerplate to `builder`, and keep the cloud model for design and review.
2. **Triaging logs and test output.** Ask the `analyzer` or `debugger` role to read a long log or failing test run and return the root cause in a few lines.
3. **Reviewing and scanning code before a merge.** The `reviewer` role checks a diff, and the `security` role runs SonarQube rules, all on local models.
4. **Working on confidential code.** For client or internal code that must not leave the machine, the source stays local and only summaries reach the cloud agent.
5. **Documentation, design and browser checks.** Route docs to `docs`, UI mock-ups to `designer`, and page audits to `browser`, each with its own persona and tools.

## Quick start

You need Python 3.11+, git, Docker, and [Ollama](https://ollama.com) (or any OpenAI-compatible LLM API).

```bash
git clone https://github.com/maxh8086/tokenfrugal.git
cd tokenfrugal
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env          # set TOKENFRUGAL_LLM_URL
python scripts/doctor.py      # checks everything and prints the fix commands
```

Then register the router with your agent:

```json
{ "mcpServers": { "tokenfrugal": { "type": "stdio", "command": "python", "args": ["-m", "router.server"], "cwd": "<path-to>/tokenfrugal" } } }
```

The full setup (models, Docker backends, tool profiles, smoke tests) is in the [technical guide](docs/technical.md#setup).

## Learn more

- **[Technical guide](docs/technical.md):** architecture, roles, tools, configuration, dashboard, and how to add an MCP server.
- **[Architecture write-up](docs/architecture.md)** and [interactive routing flowchart](docs/architecture-routing.html).
- **[Benchmark report](https://maxh8086.github.io/tokenfrugal/Benchmark/)** and [model selection guide](https://maxh8086.github.io/tokenfrugal/Benchmark/model-selection-guide.html) for choosing a model per role.

## FAQ

**Does it send my code to the cloud?** No. Local models run on your machine. Only short summaries return to your cloud agent.

**Can small local models really code?** For scoped, well-specified tasks, yes. Keep architecture and cross-module decisions with the cloud model.

**Which platforms?** Windows, macOS and Linux.

## Licence and credits

Apache-2.0 (see [LICENSE](LICENSE) and [NOTICE](NOTICE)). Built on the work of many authors; see [CREDITS.md](CREDITS.md). Third-party backends run as their own unmodified containers under their own licences.

Developed by Vaibhav Pavtekar with AI assistance (Claude Code).
