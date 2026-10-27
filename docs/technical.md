# TokenFrugal technical guide

This page covers how TokenFrugal works and how to set it up. For the short overview, see the [README](../README.md).

- [How a task flows](#how-a-task-flows)
- [Roles](#roles)
- [Setup](#setup)
- [Configuration](#configuration)
- [Choosing a model per agent](#choosing-a-model-per-agent)
- [Tool profiles and MCP servers](#tool-profiles-and-mcp-servers)
- [Plan store](#plan-store)
- [Dashboard](#dashboard)
- [Requirements and limits](#requirements-and-limits)

Design diagrams: [high-level design](hld.svg), [module design](lld-modules.svg), [dispatch sequence](lld-sequence.svg), and the [architecture write-up](architecture.md).

## How a task flows

```
Cloud agent (plans, decides)
     | dispatch_task(agent, task)
     v
TokenFrugal router --> ONE local model (builder or thinker)
     |                    |
     |<-- short summary --+   (up to 5000 tokens)
     |<-- task_id -------- on failure: resume_task / get_detail
```

- The router maps the agent slug (an [agency-agents](https://github.com/msitarzewski/agency-agents) persona) to a **role**. A role sets the model, the Docker MCP profile, the tool allowlist and a step limit.
- Each task runs on one model. The builder and thinker models never run together.
- Only the summary, the `task_id` and any `ask_followup` answer return to the cloud agent. The full output stays in the local store (`router/tasks.db`, SQLite) and is readable with `get_detail(task_id)`.
- Failures return a capped error and a `task_id`. The cloud agent calls `resume_task(task_id)` once, or re-scopes the task smaller.

## Roles

Roles are defined in `router/tf-roles.yaml`. Each role runs on the local model set for it: the `builder` model for code and file edits, or the `thinker` model for reading and analysis. An agent can be overridden to a different model (see [Choosing a model per agent](#choosing-a-model-per-agent)).

| Role | Model | Docker profile | Typical work |
| --- | --- | --- | --- |
| builder | builder | build | Write and edit code, files, tests |
| data | builder | build-data | Read data files (no SQL tool wired yet) |
| analyzer | thinker | analyze | Analyse code, trace callers, read diffs |
| reviewer | thinker | analyze | Review a diff against the code graph |
| debugger | thinker | debug | Trace a failure, run small snippets |
| security | thinker | security | SonarQube issues and hotspots (needs a token) |
| docs | thinker | docs | Read the repo and write documentation |
| designer | thinker | design | Penpot design inspection (helper container) |
| browser | thinker | browser | Navigate, snapshot, screenshot, Lighthouse audit |
| tracker | thinker | (native plan server) | Plan status and task claims in Neo4j |
| github-read | thinker | github | Read-only pull requests, issues and files |
| github-actions-read | thinker | github | Read-only Actions runs and logs |
| devops | builder | build, analyze, debug | Edit files and run commands for ops tasks |
| finance / research | thinker | docs / none | Web search and page crawling (crawl4ai, SearXNG) |

Each role exposes only its allowlisted tools (4-6 for most roles). Small models do better with few tools. The router writes the live list to `router/roles.json`.

## Setup

### 1. Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # set TOKENFRUGAL_LLM_URL (default http://localhost:11434/v1)
python scripts/doctor.py
```

`doctor.py` installs nothing. It checks Python, Docker, the LLM endpoint and the models, and prints the exact commands to fix each gap.

### 2. Pull and create the two local models

Choose a builder model and a thinker model that suit your hardware (the [benchmark report](https://maxh8086.github.io/tokenfrugal/Benchmark/) compares them per role). Pull the base models, then create the tags that `router/tf-roles.yaml` expects, using the Modelfiles in `models/`:

```bash
ollama pull <builder-base-model>
ollama pull <thinker-base-model>
ollama create <builder-tag> -f models/builder.Modelfile
ollama create <thinker-tag> -f models/thinker.Modelfile
```

Replace the placeholders with the base models and tags you chose. `doctor.py` reports which tags are missing.

### 3. Start backends and install tool profiles

1. `scripts/mcp_up.sh` (macOS/Linux) or `scripts/mcp_up.ps1` (Windows) starts the backends and creates the missing random secrets as files in `~/.docker/mcp/secrets`, outside the repo. Helper images from `docker/` are built on first use.
2. `python scripts/install_profiles.py` imports the profiles in `profiles/*.yaml` into Docker's MCP Toolkit. It mounts `CC_WORKSPACE` from `.env`, or this repo by default. Use `--workspace PATH` to override. Set `CC_WORKSPACE` in `.env` to the same absolute path, and re-run the script after changes.

The committed `.mcp.json` pins no workspace, so the router mounts the git root of the folder the client starts it from. To mount a different folder, set `CC_WORKSPACE` as a real environment variable (on Windows: `setx CC_WORKSPACE C:/path/to/Projects`, then restart the client). A real environment variable overrides `.env`.

### 4. SonarQube (security role only)

Open http://localhost:9100, log in as `admin` / `admin`, set a new password, then go to *My Account -> Security -> Generate Token* (type: User). Save the token as the secret file `SONARQUBE_TOKEN`: `printf '%s' '<token>' | python -m router.secrets_store set SONARQUBE_TOKEN`. Leave `SONARQUBE_ORG` empty for the local server. Check with `python scripts/smoke.py security`.

### 5. Smoke tests

- `python scripts/smoke.py` runs one small task per role. It needs Ollama and the steps above.
- `python -m scripts.smoke_plan` exercises the Neo4j plan store with throwaway data.

### 6. Register with your agent

Install steps for Windows, macOS and Linux, with a ready-to-paste prompt for Claude Code and for Codex, are in the [README](../README.md#install-windows-macos-linux). Claude Code uses `claude mcp add`. Codex uses the `[mcp_servers.tokenfrugal]` table in `~/.codex/config.toml`. Other stdio clients use the JSON shown there.

Tools exposed to the agent: `dispatch_task`, `ask_followup`, `get_detail`, `resume_task`, `list_roles`, and the plan tools `plan_add`, `plan_overview`, `plan_revert` and `plan_update_from`. `server.py` is a simpler two-tool legacy server (`query_local_llm`) if you only want that.

## Configuration

| Setting | Where | Default / effect |
| --- | --- | --- |
| `TOKENFRUGAL_LLM_URL` | `.env` | `http://localhost:11434/v1`. Any OpenAI-compatible endpoint works |
| `CC_WORKSPACE` | `.env` or real env var | Folder the file tools may write to |
| `TF_SECRETS_DIR` | set by the launcher | Directory of the Docker secret files (default `~/.docker/mcp/secrets`) |
| `PLAN_RETENTION_DAYS` | `.env` | 30. Finished plans are pruned after this |
| `TOKENFRUGAL_TF_ROLES_MODELS` | env | `0` turns off per-agent model mapping |
| `TOKENFRUGAL_MODEL_*` | env | Any value pins every agent to the role models |
| `TOKENFRUGAL_TF_ROLES_MODELS_FILE` | env | Location of the per-agent mapping file |
| `TOKENFRUGAL_UI` / `TOKENFRUGAL_UI_OPEN` | env | `0` disables the dashboard / skips the browser pop-up |
| `UI_PORT` | env | Dashboard port (default 7777, or `port:` in `router/ui.yaml`) |
| `GATEWAY_EVENTS` | env | Path of the event log (default `router/events.jsonl`) |

Restart the MCP client after changing settings.

## Choosing a model per agent

`tf_roles_models` in `router/tf-roles.yaml` maps an agent slug to a local model. A value is `builder`, `thinker` or any Ollama tag. Agents not listed use their role's model.

Edit the mapping in a browser instead of the YAML:

```bash
python -m scripts.tf_roles_ui            # http://127.0.0.1:7878
```

Changes are saved to `router/tf-roles_models.json` (git-ignored), which overrides the YAML. Restart the MCP client to apply.

To compare models, use the [benchmark report](https://maxh8086.github.io/tokenfrugal/Benchmark/) and the [model selection guide](https://maxh8086.github.io/tokenfrugal/Benchmark/model-selection-guide.html). Results change as models and code change, so they are not listed in this guide.

## Tool profiles and MCP servers

Most tools come from the Docker MCP Toolkit catalogue as maintained, sandboxed containers. Each role runs through `docker mcp gateway run --profile <name>`.

The easiest way to make these changes is to give your agent a prompt. Paste one of the prompts below into Claude Code or Codex from inside the `tokenfrugal` folder. The agent edits the files and runs the scripts, then reports back. The manual commands are listed after each prompt if you prefer to run them yourself.

### Prompt: add a catalogue MCP server

> In this repo, add the Docker MCP catalogue server `<server-name>` to the `<role>` role.
> 1. Add it to the matching profile in `profiles/*.yaml`. Follow the format of the existing profiles. Create a new profile file only if no existing profile fits.
> 2. In `router/tf-roles.yaml`, allowlist 4-6 of the server's tools for `<role>`. If the server exposes more than 6 tools, list them and ask me which to keep.
> 3. Run `python scripts/install_profiles.py`, then `python scripts/smoke.py` and report the result for `<role>`.
> 4. If the server needs a token, name the variable and say where it goes (`~/.docker/mcp/secrets/NAME`, written with `python -m router.secrets_store set NAME`). Never write a secret into a repo file or into chat.
> Show me the diff. Then tell me to restart the MCP client.

Manual steps: edit `profiles/*.yaml` and `router/tf-roles.yaml`, then run `python scripts/install_profiles.py` and restart the router.

### Prompt: add a helper server outside the catalogue

> In this repo, add a containerised helper for `<upstream repo URL>`, pinned to the full commit SHA `<40-char-sha>`. Use the tag `<tag>` only as a label; the SHA is what builds.
> 1. Read `docker/pins.yaml` and one existing helper directory under `docker/` (for example `docker/penpot-mcp/`). Follow their layout.
> 2. Add an entry to `docker/pins.yaml` with `repo`, `sha` (the full 40 characters, never a branch name), `image`, and `dockerfile`. Add a `tag_regex` if the upstream uses release tags.
> 3. Create the Dockerfile at the path you set in `dockerfile`. It builds from the cloned repo as its context.
> 4. Add the service to `docker-compose.yml` (project `tokenfrugal`). Add the server to a profile in `profiles/*.yaml`. Add the helper to the role's `compose:` list in `router/tf-roles.yaml`, and allowlist 4-6 of its tools.
> 5. Run `python scripts/pinned_build.py <name>`, then `python scripts/install_profiles.py`.
> Report the image tag and the SHA. Do not change other pins or roles. Show me the diff.

Manual steps: add the pin and Dockerfile, wire the service into `docker-compose.yml`, `profiles/*.yaml` and `router/tf-roles.yaml`, then run `python scripts/pinned_build.py <name>` and `python scripts/install_profiles.py`.

### Prompt: build helper images from their pinned commits

> In this repo, rebuild the helper images from the commits pinned in `docker/pins.yaml`.
> 1. Run `python scripts/check_pins.py` and list which pins have a newer upstream tag. Do not change any pin. Do not pass `--write` unless I say so.
> 2. Run `python scripts/pinned_build.py` for all pins, or `python scripts/pinned_build.py <name>` if I name one.
> 3. If a build fails, show me the last 30 lines of the error and stop. Do not edit a Dockerfile to work around it without asking me.
> 4. When the builds finish, list the images (`docker images`) and report each tag and its SHA.

Manual commands:

```bash
python scripts/check_pins.py                        # shows newer upstream tags; --write updates pins
python scripts/pinned_build.py                      # all pins
python scripts/pinned_build.py chrome-devtools-mcp  # one pin; --keep leaves the clone
```

`check_pins.py` only reports unless you add `--write`. Nothing is rebuilt until you run `pinned_build.py`.

## Plan store

Multi-step work can use the plan tools. Plans are stored in Neo4j (`neo4j` service, 127.0.0.1:7697) as `Task`, `Run`, `Event` and `Commit` nodes linked by `DEPENDS_ON`, `HAS_RUN`, `HAS_EVENT` and `LINKED_TO`.

- A task is `done` only with evidence: a real git SHA or a finished router task id.
- Dependencies are enforced, so a task cannot start before the tasks it depends on are done.
- Finished plans are pruned after `PLAN_RETENTION_DAYS`.

## Dashboard

The router starts a dashboard at http://127.0.0.1:7777 and opens it in your browser.

- **Status:** router state, the connected client (Claude, Codex or both), Ollama, the current model and agent, Docker, and the MCP servers of the selected role.
- **Tasks and log:** running tasks and a log of events. Each MCP call is recorded as it happens (tool, arguments, step).
- **Tokens saved:** a running total of tokens the local model handled, minus the summary returned to your cloud agent. Tokens are estimated at 4 characters each. Failed tasks count too, because the local work still ran.
- **synaptree-mcp:** the fourth box links to the code graph UI (http://127.0.0.1:8787/ui/) when it is running.

Dashboard text comes from `router/ui.yaml`. Roles, models and tools come from `router/roles.json`. The dashboard needs Node.js and no npm packages. Without Node, the router runs without it. Run `node ui/server.js` to start it by hand.

## Requirements and limits

| Need | Notes |
| --- | --- |
| Python 3.11+ | 3.10 breaks pydantic |
| git | |
| Docker | Desktop, Engine, Colima, Rancher Desktop or Podman with a `docker` shim. Docker Desktop is free only for personal, education and small-business use |
| Ollama or an OpenAI-compatible API | Set in `.env` |
| Two local models | Builder and thinker, as above |
| MCP client | Claude Code, Codex, Cursor or any stdio MCP client |

Limits:

- Built for scoped, well-specified tasks. Architecture and cross-module decisions stay with the cloud model.
- Tool allowlists and step limits (`max_steps`) keep small models on track, and bound how long a task can run.
- Benchmarks cover short cases on the Ollama setup. They do not test long contexts.
- The `data` role has no SQL tool yet.
