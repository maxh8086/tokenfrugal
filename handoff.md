# Handoff: tokenfrugal

Last updated: 2026-10-17

This file holds the working handoff notes. Closed items are removed once verified.

---
## Concurrent docker runs: DONE (2026-10-15)

Backend stops are decided by per-backend lease files in `router/leases/` (`<service>.<pid>.<uuid>`), so a router stops a backend only when no other live router still uses it; stale leases of dead pids are pruned. `MCP_KEEP_ALIVE=1` / `keep_alive` still skips the stop. Docker-backed tests may now run concurrently.

---
## Workspace auto-sync: DONE (2026-10-15)

`CC_WORKSPACE` resolves as real env var, then cwd git root, then `.env`, then repo root (`router/profile_sync.py`). The router re-imports Docker MCP profiles on startup only when the workspace changed (marker `router/profiles_workspace.json`, gitignored).

---
## Haiku tool-call verification: DONE (2026-10-15)

Haiku (claude-haiku-5-5) calls all 9 router tools and all 83 role tools behind the Docker gateway (`tests/test_haiku_toolcalls.py --roles`: 83 pass, 0 fail). Offline suite: 183 tests OK. Live smoke: all roles pass; security is occasionally flaky because the 3B model writes a tool call as text (rerun passes).

Gotchas:
- A shell-level `CC_WORKSPACE` overrides `.env`; unset it or it hides the writable fs tools. `.env` must equal the installed profile's mount path.
- `ANTHROPIC_API_KEY` must be in the process env; in Git Bash export it from the user env var.

---
## Current plan (2026-10-12)

Status at this point:

1. Benchmark (open): finish the priority run for list 1 only, classify the 4B `slug`/`AssertionError` failures (model output vs mount), then Qwythos, then `scripts/bench_append.py` without `--dry-run`. List 2 (about 60 models) waits for explicit confirmation in chat.
2. Housekeeping (open): plan task 51 still needs closing by hand (no delete tool). Checked 2026-10-17: task `0cf6dd6716` made no changes. Its `edit_file` calls failed (no exact match, ENOENT), and `git status` is clean. Plan task 50 is not in plan `main`; `plan_overview` lists only task 52.
3. Commit: done for the working-tree reorganisation (4f9c35c). Future commits: no Co-Authored-By trailer, per the project and memory rules.

Delegation: builder tasks go through `tokenfrugal.dispatch_task` in small pieces. Haiku fallback is used only after failures and is disclosed in the report.

---
## MCP configuration UI and secret store move (open, 2026-10-17)

**Gate: no code changes until stage 1 finishes and the offline suite passes.** Design agreed in chat; implementation not started.

Goal: a configuration-tab UI that adds MCP servers built locally as Docker images and mapped to tokenfrugal. The form for each MCP is generated from its catalogue schema (`secrets`, `config`, `env`, `volumes`).

Decisions:
- Input tiers: secrets go to the Docker MCP secret store (`docker mcp secret set`). Paths are per-machine placeholders filled from the form. Plain config (URLs, usernames, regions) goes to YAML or the agent config.
- Docker secret store is write-only: `docker mcp secret` supports only `ls`, `rm` and `set` (checked 2026-10-17). The router cannot read values back from it.
- Move all secrets from the OS keyring to the Docker store. Backend secrets that compose needs (`CRAWL4AI_API_TOKEN`, `SEARXNG_SECRET`, `SONARQUBE_TOKEN`, `SONARQUBE_ORG`, `NEO4J_AUTH`) are held in a gitignored launcher file, since compose reads them from the process environment.
- Catalogue research: top 25 entries that take user input, with their schema fields, is in the session scratchpad (`top25.txt`). Puppeteer needs no input. Slack, GitHub, Google Maps and Puppeteer are archived upstream and should be flagged in the UI.

Code touchpoints to change (confirmed by grep, 2026-10-17):
- `router/secrets_store.py`: backend moves from `keyring` to Docker. `resolve`, `resolve_env`, `export_env`, `ensure_generated` need a new source for values.
- `router/docker_mcp.py`: stops pushing from keyring; secret refs become Docker store names.
- `router/mcp_client.py` (lines 58–59), `router/config.py` (lines 45, 92, 104), `router/claude_import.py`: `keyring:NAME` references change.
- `scripts/mcp_up.ps1`, `scripts/mcp_up.sh`: read the launcher file instead of `export-env`.
- `docker-compose.yml` (line 6), `docs/mcp-standards.md` (lines 75–76, 147): rewrite the keyring text.
- `router/secret_names.json` and the `keyring` line in `requirements.txt`: remove once nothing uses them.
- Existing values in Windows Credential Manager: re-enter into the Docker store. Nothing migrates automatically.

Two ways to add an MCP from the configuration tab:
1. **From the Docker MCP catalogue.** Pick an entry; the form is generated from its `secrets`, `config`, `env` and `volumes` schema. Values go to the stores described above, and the entry is mapped to a tokenfrugal profile.
2. **From a GitHub repo path.** The user gives a repo URL and optional ref. The router clones it into a new empty directory under the scratchpad or a managed cache, reads its Dockerfile or build instructions, builds a local image tagged `tokenfrugal/<name>:<ref>`, then maps it to a tokenfrugal profile. Its required inputs are read from the repo's own README or manifest, with a plain form as fallback.
   - Cloned repos are untrusted data. Before any build, show the user the Dockerfile and the file list, and ask for explicit approval. Build with `-I`-style isolation: no host mounts except the workspace paths the user approves.
   - Build failures return a short error and stop; nothing is mapped until the image builds and the MCP lists its tools.

Decisions from the user (2026-10-17):
- Repos without a Dockerfile are not refused. Catalogue MCPs ship no Dockerfile either, so the router generates a build recipe per MCP from the repo's language and entry point. The generated Dockerfile is shown to the user before the first build, like any repo file.
- The clone cache is pruned. Retention and size limit to be set when implemented.
- Once an image is built it runs locally with no network. Builds need the network only the first time, for the clone and base image pull.
- Built images are pushed to the user's own Docker Hub account. A push publishes the image, so each push needs explicit approval in chat, and the Docker Hub token is held in the Docker secret store. Visibility (private or public repo) is the user's choice per push.

Open:
- Name and location of the gitignored launcher file for backend secrets.
- Whether `ensure-generated` keeps creating random values, and where they are written.
- Default Docker Hub repo visibility for pushed MCP images. Recommend private.
- Cache retention period and size cap for pruning.

---
## Benchmark at temperature 0.0 (open, 2026-10-17)

`LOCAL_LLM_TEMPERATURE` now defaults to `0.0` in `router/config.py`, and `router/summarize.py` and `router/loop.py` pass it through. The earlier gemma4 run (`bg05d1pw8`, tag `gemma4-e4b-n3`) was at 0.1 and was stopped. Rerun in progress: `gemma4:e4b --tag gemma4-e4b-n3 --n 3`, then `hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K --tag qwen35-4b-q6k`. Logs are in the session scratchpad. When both finish: run `python Benchmark/script/build_report.py`, check the new CSV rows, and do not edit other rows. Code and docs committed; the benchmark rows are not yet in results/.

---
## Inference engine plan (open, 2026-10-17)

**Gate: no code changes until the full test run finishes.** That means stage 1 completes, `build_report.py` runs, and the offline suite (`PYTHONPATH=. python -m unittest discover -s tests -t . -q`) passes. Research and planning notes only until then.

Goal: support larger models and tools while the router runs the same way on every engine. Behavior should differ between models only where a model or engine limitation requires it.

Decisions so far:
- Keep the OpenAI-compatible `/v1/chat/completions` endpoint as the single interface for `router/loop.py` and `router/summarize.py`. Engine choice is config only.
- Model size and RAM spillover are engine settings (llama-server `-ngl` / `-fit`, Ollama automatic offload), not router code.
- Decode t/s needs native timing (`eval_count`, `eval_duration`) from `/api/chat` on Ollama. llama-server and Docker Model Runner timing is unconfirmed, so wall-clock t/s is the fallback there.

Steps:
1. Add `LLM_ENGINE` plus endpoint config with capability flags for `tool_choice` and native timing. Default preserves current behavior.
2. In `router/loop.py`, make the forced first tool call depend on the `tool_choice` flag. Without it, fall back to a prompt-level instruction. This is the only expected behavior difference, and it is an engine limitation.
3. Run the same tool-calling cases on llama-server and Docker Model Runner with one model that Ollama already runs well. Check parity.
4. Only after step 3, decide whether llama-server or Docker Model Runner is worth adding for larger models.

Open questions:
- Confirm whether Docker Model Runner's Ollama-compatible API serves `/api/chat` with timing fields. The official overview page does not say.
- Confirm `tool_choice` support on llama-server (not documented on the fetched page).
- Unverified: which engine gives RAM spillover on this Windows machine (NVIDIA driver 576.57+ needed for Docker Model Runner GPU).
