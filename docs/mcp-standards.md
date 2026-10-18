# MCP standards for tokenfrugal

How MCP servers are managed in this repo, and how a new one is added. It is based on how the Docker MCP Toolkit (`docker mcp`) manages its own servers, so tokenfrugal and Docker agree on the layers.

## 1. How Docker manages MCPs

| Layer | Docker object | Where it lives | Command |
| --- | --- | --- | --- |
| Catalogue | Server entry (image, config schema, tools) | OCI catalogue `mcp/docker-mcp-catalog`, cached in `~/.docker/mcp/catalogs/` | `docker mcp catalog show`, `docker mcp catalog list` |
| Profile | Named bundle of servers | `docker mcp profile` (its DB, `~/.docker/mcp/mcp-toolkit.db`) | `profile list / show / server add / server remove` |
| Profile config | Per-server non-secret values (for example `filesystem.paths`) | Profile | `profile config <profile> --set / --get-all` |
| Secrets | Tokens and keys | OS keychain (provider `docker-desktop-store`) | `docker mcp secret set / ls / rm` |
| OAuth | Browser-authorised apps | Docker's store | `docker mcp oauth ls / authorize / revoke` |
| Tool allowlist | Which tools a profile exposes | Profile | `profile tools <profile> --enable / --disable / --enable-all / --disable-all` |
| Tool inspection | Flat list of exposed tools | Gateway | `docker mcp tools ls / inspect / call / count` |
| Clients | Which AI clients the gateway is wired into | Client config | `docker mcp client ls / connect / disconnect` |
| Features | Experimental switches | Gateway config | `docker mcp feature ls / enable / disable` |
| Templates | Starter profiles | Built in | `docker mcp template list / use` |

Current gateway features on this machine: `dynamic-tools` is enabled, which exposes `mcp-find`, `mcp-add`, `mcp-remove`, `mcp-config-set`, `mcp-create-profile`, `mcp-exec` and `mcp-activate-profile` to the model at runtime. `oauth-interceptor` is disabled.

Config schema: each catalogue server declares a `config` block with typed properties and `required` fields. The `command` and `volumes` are templates filled from those values, for example `{{filesystem.paths|volume}}`. The Desktop UI builds its forms from this schema.

## 2. tokenfrugal's layers

tokenfrugal maps Docker's layers onto three files and one set of scripts:

| tokenfrugal file | Role | Docker equivalent |
| --- | --- | --- |
| `profiles/*.yaml` | Profile definitions (image, volumes, secrets, snapshot) | Profile + catalogue entry |
| `router/mcp_catalog.yaml` | MCP catalogue: label, profile or native server, compose backends, tool names | Catalogue entry |
| `router/tf-roles.yaml` | Roles: model, profile, tool allowlist (6 or fewer for 3B models) | Client-side tool choice |
| `scripts/install_profiles.py` | Imports profiles, fills `__WORKSPACE__` | `docker mcp profile import` |

Key rule: Docker decides what a profile can expose. tokenfrugal decides what a role may call. Both layers must allow a tool before an agent can use it.

## 3. Standard for adding a new MCP

Work through this in order and stop at the first step that answers the question.

### Step 1: Is it already in the Docker catalogue?

- Search with `docker mcp catalog show` or the `mcp-find` tool. Prefer an existing `mcp/...` image.
- Pin the image by `@sha256:` digest, never `latest`.
- Record the server in the profile that matches its job. Do not create a profile per server.

### Step 2: Pick the profile by job, not by server

Existing profiles: `build` (writable workspace), `build-data`, `analyze` (read-only analysis), `debug`, `docs` (fetch and read), `security`, `design`, `browser`, `github`. A new MCP joins an existing profile unless it needs a different mount, network or secret set.

Create a new profile only when one of these is true:
- it needs a different writable mount or different secrets;
- its network policy differs (`disableNetwork` on, or an `allowHosts` list);
- it is a distinct role that a persona would use alone.

Do not add to `default`, `profile_test` or `claude`. They are for experiments and personal use.

### Step 3: Declare the server in the profile YAML

- `secrets: default` and the `secrets:` block at the bottom of the profile.
- Mounts are read-only by default (`:ro`). Only `build` may mount the workspace read-write.
- `disableNetwork: true` unless the server needs the network. If it does, list every host in `allowHosts`.
- Use `__WORKSPACE__` for the workspace path. Never hard-code a user path.
- Name the instance with the `ts-` prefix (`ts-fs-rw`, `ts-git`), so it is clear which server is ours.

### Step 4: Non-secret config

- Path and option values go through the profile config: `docker mcp profile config <profile> --set key=value`.
- Values that are paths must be inside `CC_WORKSPACE` or the repo. Validate before saving.
- Document the config key in the catalogue entry, as the Docker schema does.

### Step 5: Secrets

- Docker-managed MCPs: store with `docker mcp secret set NAME` (value on stdin). Reference from the profile with `env:`.
- tokenfrugal-managed secrets (native servers, LLM key, backend services): store in the OS secret store with `python -m router.secrets_store set NAME` (value typed at a hidden prompt). Reference it from config as `keyring:NAME` in a native server's `env` block, or by its known name (`llm-api-key`).
- `python -m router.secrets_store list` shows names only; `get-status NAME` shows set/not set; neither prints a value.
- Backend secrets used by `docker-compose.yml` are `CRAWL4AI_API_TOKEN`, `SEARXNG_SECRET`, `NEO4J_AUTH` (generated on first run by `ensure-generated`) and `SONARQUBE_TOKEN` / `SONARQUBE_ORG` (set by you). `scripts/mcp_up.*` read them with `export-env` and pass them to compose through the process environment. Each compose service receives only its own variables; there is no env file.
- Never put a secret in a repo file, a catalogue YAML, a task payload, a log or a chat message.
- Do not add keys to `~/.docker/mcp/mcp.env`. Its keys move to the OS store per section 6; the file is removed after a verified restart.

### Dashboard "Add plugin" standard

Adding an MCP from the dashboard follows the Claude-style import flow: **Add plugin → Select MCP → import JSON**. The JSON uses the same shape Claude uses for `mcpServers` entries (server name, command or image, args, env). Env values are `keyring:NAME` refs or non-secret literals, never raw secrets. The dashboard shows the parsed plan first (profile, server, config keys, secret names); nothing is written until the user approves. Only then does it run `docker mcp profile server add` and `docker mcp profile config <profile> --set key=value`. No `profile server add` or `profile config --set` runs without that approval.

### Step 6: OAuth servers

- Mark the catalogue entry `auth: oauth`.
- Check with `docker mcp oauth ls`. Authorise with `docker mcp oauth authorize <app>`. Revoke with `docker mcp oauth revoke <app>`.
- tokenfrugal never receives or stores OAuth tokens.

### Step 7: Tool allowlists (two layers)

1. **Profile level** (Docker): enable only the tools the role needs with `docker mcp profile tools <profile> --enable <server>.<tool>`. Do not use `--enable-all` for a new server.
2. **Role level** (tokenfrugal): add the tool names to `router/tf-roles.yaml` under the role, at most 6 per role. Do not add a tool at role level that the profile does not enable.

Confirm with `docker mcp tools ls` that the tool is exposed, and `docker mcp tools inspect <tool>` for its schema.

### Step 8: Register in tokenfrugal

- Add an entry to `router/mcp_catalog.yaml` with `label`, one of `profile:` or `native:`, `compose:` if it needs backends, and `tools:`.
- Add the MCP to the relevant role in `tf-roles.yaml`.
- For a native stdio server (not a Docker image), set `native:` and add the server to `router/config.py`. A compose backend goes in `docker-compose.yml` under project `ts-mcp`. Leave other compose projects alone.

### Step 9: Verify

Run in this order:

```
python scripts/doctor.py
python scripts/install_profiles.py
docker mcp profile show <profile>
docker mcp tools ls
PYTHONPATH=. python -m unittest discover -s tests -t . -q
python scripts/smoke.py
```

- Check the bind mount points where you expect after a gateway restart (`ts-fs-rw`, `ts-fs-ro`, `ast-grep`).
- Re-run `write_roles(cfg)` so the dashboard's `roles.json` shows the new tools.
- Mark the plan task `done` only with evidence (a git sha or a finished task id).

### Step 10: Remove an MCP

Remove it in reverse order: `tf-roles.yaml` roles, then `mcp_catalog.yaml`, then `docker mcp profile server remove`, then the profile YAML, then `docker mcp secret rm` for keys nothing else uses, then `docker mcp oauth revoke` if it was OAuth.

## 4. Standards that apply to every MCP

- **Pin:** digest images only.
- **Least privilege:** read-only mounts, network off by default, the fewest tools enabled.
- **One writable root:** only `build` writes to the workspace.
- **No secrets in files:** keychain or OAuth only.
- **Two-layer allowlist:** profile enables, role allows, and both are small.
- **Dynamic tools off for tokenfrugal roles:** the `dynamic-tools` gateway feature lets the model add servers at runtime, which bypasses the allowlists. Recommend disabling it for the tokenfrugal gateway. Not yet changed.
- **Naming:** `ts-` prefix for our instances; tool names unprefixed, matching the catalogue.
- **Limits:** keep a role at 6 or fewer tools, because the local models are 3B.

## 5. Current gaps against this standard

- `profile_test`, `default` and `claude` profiles hold servers that are not used by any role.
- `build` mounts the whole `Projects` folder (`C:/Users/vaibh/Downloads/Projects`), not the tokenfrugal repo. This is wider than the standard requires; a narrower root is recommended.
- The chrome-devtools server is named three ways: catalogue key `chrome-devtools` (`router/mcp_catalog.yaml`), instance title `tokenfrugal-chrome-devtools` (`profiles/browser.yaml`), and image `maxh8086/chrome-devtools-mcp:1` (`profiles/browser.yaml`, `docker/pins.yaml`). The `ts-` prefix from section 3 is not applied to it yet.
- Secrets still reference `mcp.env` in `CLAUDE.md`. The OS secret store is the standard for tokenfrugal secrets; update `CLAUDE.md` once the `mcp.env` removal is verified.
- `mcp.env` still holds the five backend keys until the restart is verified (section 6).
- `dynamic-tools` is enabled.

## 6. Decisions pending

1. Move secrets from `~/.docker/mcp/mcp.env` to the OS secret store (`router/secrets_store.py`, via `keyring`; Windows Credential Manager here). Implemented: native-server env refs, `llm-api-key`, compose reads backend secrets from the environment, and the launchers use the store. Remaining: remove the five `mcp.env` keys (`CRAWL4AI_API_TOKEN`, `SONARQUBE_TOKEN`, `SONARQUBE_ORG`, `SEARXNG_SECRET`, `NEO4J_AUTH`) and restart the backends, only after explicit user approval. Then update `CLAUDE.md`.
2. Narrow the `build` workspace mount to the repo.
3. Disable `dynamic-tools` for the tokenfrugal gateway.
4. Confirm the exact `profile config --set` key format on a throwaway profile before the dashboard relies on it.
