"""Router configuration (env-overridable)."""
import json
import os
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from . import claude_import, profile_sync, secrets_store

ROOT = Path(__file__).resolve().parent.parent
_REAL_ENV = set(os.environ)  # set before .env is read: these beat both .env and the dashboard overrides
load_dotenv(ROOT / ".env")  # LLM endpoint etc.; real environment variables win

# Settings saved from the dashboard Configuration tab (ui/server.js POST /api/config). They override .env;
# real environment variables still win.
_OVERRIDE_ENV = {
    "workspace": "CC_WORKSPACE",
    "bind_writable": "MCP_GATEWAY_DOCKER_BIND_ALLOW_WRITABLE_PATHS",
    "bind_readonly": "MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS",
    "llm_url": "OPENAI_BASE_URL",
    "temperature": "LOCAL_LLM_TEMPERATURE",
    "max_tokens": "LOCAL_LLM_MAX_TOKENS",
}
try:
    _overrides = json.loads((Path(__file__).parent / "config_overrides.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    _overrides = {}
for _k, _env in _OVERRIDE_ENV.items():
    if _k in _overrides and _env not in _REAL_ENV:
        os.environ[_env] = str(_overrides[_k])

# Any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, a hosted API). Host and port live in .env.
OLLAMA_URL = os.getenv("TOKENFRUGAL_LLM_URL") or os.getenv("OLLAMA_URL", "http://localhost:11434/v1")


def _llm_api_key() -> str:
    """TOKENFRUGAL_LLM_API_KEY wins; otherwise the OS secret store entry `llm-api-key`; otherwise the local default."""
    if os.getenv("TOKENFRUGAL_LLM_API_KEY"):
        return os.environ["TOKENFRUGAL_LLM_API_KEY"]
    try:
        return secrets_store.get("llm-api-key") or "ollama"
    except secrets_store.SecretStoreError:  # no usable OS store here: keep the local default
        return "ollama"


LLM_API_KEY = _llm_api_key()


def _git_root(start: str):
    """Nearest ancestor of `start` that holds a .git entry, as a posix path; None if there is none."""
    here = Path(start).resolve()
    for p in [here, *here.parents]:
        if (p / ".git").exists():
            return p.as_posix()
    return None


# Exact host path the Docker router may bind writable (defaults to the checkout; see docker catalogue volume).
# Priority: real env var, then the git repo the client launched us from, then .env / dashboard value, then this checkout.
WORKSPACE = profile_sync.resolve_workspace(
    os.environ.get("CC_WORKSPACE") if "CC_WORKSPACE" in _REAL_ENV else None,
    _git_root(os.getcwd()), os.getenv("CC_WORKSPACE"), ROOT.as_posix())
os.environ["CC_WORKSPACE"] = WORKSPACE  # plan.py and child processes read the same value
# Non-Docker MCP servers a role may use directly (name -> stdio command).
SYNAPTREE_DIR = os.getenv("SYNAPTREE_DIR") or str(Path(__file__).resolve().parent.parent.parent / "synaptree-mcp")
NATIVE_SERVERS = {
    # synaptree-mcp: code graph over stdio (default: inside the synaptree Docker container; SYNAPTREE_HOST_NODE=1 for host node)
    "synaptree": (
        {"command": "node", "args": [str(Path(SYNAPTREE_DIR) / "src" / "cli.js"), "--stdio"]}
        if os.getenv("SYNAPTREE_HOST_NODE") == "1"
        else {"command": "docker", "args": ["exec", "-i", os.getenv("SYNAPTREE_CONTAINER", "synaptree-synaptree-1"),
                                            "node", "src/cli.js", "--stdio"]}
    ),
}
# Compose-managed backends (docker-compose.yml). Secrets come from an env file outside the repo.
COMPOSE_FILE = Path(os.getenv("MCP_COMPOSE_FILE", Path(__file__).resolve().parent.parent / "docker-compose.yml"))
COMPOSE_PROJECT = "ts-mcp"
MCP_ENV_FILE = os.getenv("MCP_ENV_FILE", str(Path.home() / ".docker" / "mcp" / "mcp.env"))
os.environ["MCP_ENV_FILE"] = MCP_ENV_FILE


def _load_backend_env() -> None:
    """Export the backend secrets from the OS store (compose reads them from the environment).
    Values already in the environment win. Nothing is written to disk; values are never printed or logged."""
    try:
        for name, value in secrets_store.export_env().items():
            os.environ.setdefault(name, value)
    except secrets_store.SecretStoreError:
        pass  # no usable store here; compose then fails with a message naming the missing variable


_load_backend_env()
KEEP_ALIVE = os.getenv("MCP_KEEP_ALIVE", "") == "1"  # leave backends running after a task
for _n, _svc in (("crawl4ai", "mcp-crawl4ai"), ("sonarqube", "mcp-sonarqube")):
    NATIVE_SERVERS[_n] = {"command": "docker", "args": ["compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE),
                                                         "run", "--rm", "-T", _svc]}
# keyring: refs are resolved from the OS store by mcp_client.open_native and passed to compose as ${SONARQUBE_TOKEN}
NATIVE_SERVERS["sonarqube"]["env"] = {"SONARQUBE_TOKEN": "keyring:SONARQUBE_TOKEN"}
NATIVE_SERVERS["plan"] = {"command": sys.executable, "args": ["-m", "router.plan_mcp"]}
# synaptree-mcp project = checkout folder name; SYNAPTREE_PROJECT overrides it
for _n, _spec in claude_import.load()["servers"].items():  # Claude-JSON imports (python -m router.claude_import)
    NATIVE_SERVERS.setdefault(_n, _spec)
SYNAPTREE_PROJECT = os.getenv("SYNAPTREE_PROJECT") or Path(__file__).resolve().parent.parent.name
DB_PATH = Path(os.getenv("GATEWAY_DB", Path(__file__).parent / "tasks.db"))
SUMMARY_MIN_TOKENS, SUMMARY_MAX_TOKENS = 150, 300
TOOLS_PER_STEP = 2
TOOL_MODE = os.getenv("TOKENFRUGAL_TOOL_MODE", "native")  # "text": tools described in the prompt, calls parsed from JSON text (models without a tool template)
# CPUs / memory per Docker MCP tool container (docker mcp gateway defaults: 1 CPU, 2Gb).
MCP_CPUS = os.getenv("TOKENFRUGAL_MCP_CPUS", "4")
MCP_MEMORY = os.getenv("TOKENFRUGAL_MCP_MEMORY", "2Gb")
# Timeouts (seconds), all overridable via env. 0 disables the task/tool limit.
LLM_TIMEOUT = float(os.getenv("TOKENFRUGAL_LLM_TIMEOUT", "180"))    # one chat completion
TOOL_TIMEOUT = float(os.getenv("TOKENFRUGAL_TOOL_TIMEOUT", "60"))   # one MCP tool call
TASK_TIMEOUT = float(os.getenv("TOKENFRUGAL_TASK_TIMEOUT", "540"))  # whole task; keep below the MCP client's tool timeout


PERSONA_MODELS_FILE = Path(os.getenv("TOKENFRUGAL_PERSONA_MODELS_FILE", Path(__file__).parent / "persona_models.json"))


PERSONA_MCPS_FILE = Path(os.getenv("TOKENFRUGAL_PERSONA_MCPS_FILE", Path(__file__).parent / "persona_mcps.json"))


def load_catalog() -> dict:
    cat = yaml.safe_load((Path(__file__).parent / "mcp_catalog.yaml").read_text(encoding="utf-8"))
    imported = claude_import.load()  # MCPs added from Claude `mcpServers` JSON; built-in names win
    cat["mcps"] = {**imported["mcps"], **cat["mcps"]}
    return cat


def default_mcps(role: dict, catalog: dict) -> list[str]:
    """MCPs whose tools the role already allows (the benchmarked default toolkit)."""
    return [n for n, m in catalog["mcps"].items() if set(m["tools"]) & set(role["tools"])]


def load_personas() -> dict:
    cfg = yaml.safe_load((Path(__file__).parent / "agents.yaml").read_text(encoding="utf-8"))
    pm = dict(cfg.get("persona_models") or {})
    try:  # user overrides (written by scripts/persona_ui.py) win over the yaml defaults
        pm.update(json.loads(PERSONA_MODELS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    # Benchmarks pin one model for every persona with TOKENFRUGAL_MODEL_*; TOKENFRUGAL_PERSONA_MODELS=0 disables the mapping.
    disabled = os.getenv("TOKENFRUGAL_PERSONA_MODELS") == "0" or any(os.getenv(f"TOKENFRUGAL_MODEL_{k.upper()}") for k in cfg["models"])
    cfg["known_agents"] = sorted(pm)  # slugs stay valid when the model mapping is off
    if disabled:
        pm = {}
    cfg["persona_models"] = {k: v for k, v in pm.items() if isinstance(v, str) and v.strip()}
    cfg["mcp_catalog"] = load_catalog()["mcps"]
    try:  # user MCP selection per persona (written by scripts/persona_ui.py); off whenever the model mapping is off
        mc = json.loads(PERSONA_MCPS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mc = {}
    cfg["persona_mcps"] = {} if disabled else {k: v for k, v in mc.items() if isinstance(v, list)}
    for k in cfg["models"]:  # TOKENFRUGAL_MODEL_BUILDER / _THINKER swap a model without editing the yaml (benchmarks)
        cfg["models"][k] = os.getenv(f"TOKENFRUGAL_MODEL_{k.upper()}") or cfg["models"][k]
    cfg["persona_skills"] = dict(cfg.get("persona_skills") or {})
    # Role -> model tag from the dashboard Configuration tab; wins over the logical model in agents.yaml.
    cfg["role_models"] = {k: v for k, v in (_overrides.get("role_models") or {}).items() if isinstance(v, str) and v.strip()}
    # Role -> MCP names from the dashboard Configuration tab; a persona_mcps entry for one agent still wins.
    cfg["role_mcps"] = {k: [n for n in v if isinstance(n, str)] for k, v in (_overrides.get("role_mcps") or {}).items() if isinstance(v, list)}
    return cfg


def resolve_role(agent: str, cfg: dict) -> dict:
    """Map an agency-agents slug (e.g. 'engineering-sre') to its role config."""
    div = max((d for d in cfg["divisions"] if agent.startswith(d + "-") or agent == d), key=len, default=None)
    div = next((d for d, slugs in cfg.get("members", {}).items() if agent in slugs), div)
    role = cfg["overrides"].get(agent) or (cfg["divisions"][div] if div else "builder")
    r = dict(cfg["roles"][role])
    r["role"] = role
    r["model"] = cfg.get("role_models", {}).get(role) or cfg["models"][r["model"]]
    own = list(r.get("skills") or [])
    r["skills"] = own + [s for s in cfg.get("persona_skills", {}).get(agent, []) if s not in own]
    chosen = cfg.get("persona_mcps", {}).get(agent) or cfg.get("role_mcps", {}).get(role) or []
    sel = [n for n in chosen if n in cfg.get("mcp_catalog", {})]
    if sel:  # user-chosen toolkit: open the distinct profiles/natives/backends and allow the union of tools
        ms = [cfg["mcp_catalog"][n] for n in sel]
        uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))
        r["profile"] = uniq(m.get("profile") for m in ms) or None
        r["native"] = uniq(m.get("native") for m in ms)
        r["compose"] = uniq(c for m in ms for c in m.get("compose", []))
        r["tools"] = uniq(t for m in ms for t in m["tools"])
        r["params"] = {m["profile"]: m["params"] for m in ms if m.get("profile") and m.get("params")}
        r["mcps"] = sel
    pm = cfg.get("persona_models", {}).get(agent)
    if pm:  # a logical name (builder/thinker) or a concrete model tag
        r["model"] = cfg["models"].get(pm, pm)
    return r


def check_agent(slug: str, cfg: dict) -> str:
    """Return '' when slug is a known agent, else a short error."""
    known = set(cfg.get("overrides") or {}) | set(cfg.get("persona_models") or {}) | set(cfg.get("known_agents") or []) | set(cfg.get("persona_skills") or {})
    for slugs in (cfg.get("members") or {}).values():
        known |= set(slugs)
    if slug in known:
        return ""
    return f"unknown agent '{slug}'; call list_roles for valid slugs"
