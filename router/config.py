"""Router configuration (env-overridable)."""
import json
import os
import re
import sys
from datetime import date
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
# Sampling temperature for every tokenfrugal model call (loop, summaries, benchmarks). 0.0 unless LOCAL_LLM_TEMPERATURE says otherwise.
LLM_TEMPERATURE = float(os.getenv("LOCAL_LLM_TEMPERATURE", "0.0"))


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
NATIVE_SERVERS["sandbox"] = {"command": sys.executable, "args": ["-m", "router.sandbox_mcp"]}  # run_tests / run_python in a network-less container
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


# The pre-rename agent_* and persona_* names (env vars, override files, yaml keys) are read as a fallback until this date.
# tests/test_legacy_agent_config.py and tests/test_legacy_persona_config.py fail after it, which is the reminder to delete
# the fallbacks; CHANGELOG.md records it.
LEGACY_REMOVE_AFTER = date(2027, 3, 31)
_LEGACY_SEEN: set[str] = set()
_LEGACY_MODEL_ENVS = ("TOKENFRUGAL_AGENT_MODELS", "TOKENFRUGAL_PERSONA_MODELS")
_LEGACY_MODELS_FILES = (("TOKENFRUGAL_AGENT_MODELS_FILE", "agent_models.json"),
                        ("TOKENFRUGAL_PERSONA_MODELS_FILE", "persona_models.json"))
_LEGACY_MCPS_FILES = (("TOKENFRUGAL_AGENT_MCPS_FILE", "agent_mcps.json"),
                      ("TOKENFRUGAL_PERSONA_MCPS_FILE", "persona_mcps.json"))


def _legacy_notice(name: str) -> None:
    """Warn on stderr once per process when a deprecated agent_* or persona_* name is actually used."""
    if name in _LEGACY_SEEN:
        return
    _LEGACY_SEEN.add(name)
    kind = "agent_*" if "agent" in name.lower() else "persona_*"
    print(f"tokenfrugal: '{name}' is deprecated; rename to tf-roles ({kind} name). "
          f"(fallback removed after {LEGACY_REMOVE_AFTER.isoformat()})", file=sys.stderr)


def _tf_roles_file(env_name: str, name: str, legacy: tuple[tuple[str, str], ...]) -> Path:
    """Override file path. The tf-roles env var and filename win. legacy = ((env, filename), ...) in precedence order:
    the agent_* and persona_* names are a fallback until LEGACY_REMOVE_AFTER, and a deprecation warning is printed once."""
    here = Path(__file__).parent
    if os.getenv(env_name):
        return Path(os.environ[env_name])
    for lenv, _ in legacy:
        if os.getenv(lenv):
            _legacy_notice(lenv)
            return Path(os.environ[lenv])
    new = here / name
    if new.exists():
        return new
    for _, lname in legacy:
        if (here / lname).exists():
            _legacy_notice(lname)
            return here / lname
    return new


TF_ROLES_MODELS_FILE = _tf_roles_file("TOKENFRUGAL_TF_ROLES_MODELS_FILE", "tf-roles_models.json", _LEGACY_MODELS_FILES)


TF_ROLES_MCPS_FILE = _tf_roles_file("TOKENFRUGAL_TF_ROLES_MCPS_FILE", "tf-roles_mcps.json", _LEGACY_MCPS_FILES)


def load_catalog() -> dict:
    cat = yaml.safe_load((Path(__file__).parent / "mcp_catalog.yaml").read_text(encoding="utf-8"))
    imported = claude_import.load()  # MCPs added from Claude `mcpServers` JSON; built-in names win
    cat["mcps"] = {**imported["mcps"], **cat["mcps"]}
    return cat


def default_mcps(role: dict, catalog: dict) -> list[str]:
    """MCPs whose tools the role already allows (the benchmarked default toolkit)."""
    return [n for n, m in catalog["mcps"].items() if set(m["tools"]) & set(role["tools"])]


def _yaml_section(cfg: dict, name: str, legacy: tuple[str, ...]) -> dict:
    """Section `name` of tf-roles.yaml. Pre-rename keys are a fallback until LEGACY_REMOVE_AFTER."""
    if cfg.get(name):
        return cfg[name]
    for old in legacy:
        if cfg.get(old):
            _legacy_notice(old)
            return cfg[old]
    return {}


def load_tf_roles() -> dict:
    cfg = yaml.safe_load((Path(__file__).parent / "tf-roles.yaml").read_text(encoding="utf-8"))
    pm = dict(_yaml_section(cfg, "tf_roles_models", ("agent_models", "persona_models")))
    try:  # user overrides (written by scripts/tf_roles_ui.py) win over the yaml defaults
        pm.update(json.loads(TF_ROLES_MODELS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    # Benchmarks pin one model for every role with TOKENFRUGAL_MODEL_*; TOKENFRUGAL_TF_ROLES_MODELS=0 disables the mapping.
    # The TOKENFRUGAL_AGENT_MODELS and TOKENFRUGAL_PERSONA_MODELS names are still honoured until LEGACY_REMOVE_AFTER.
    if not os.getenv("TOKENFRUGAL_TF_ROLES_MODELS"):
        for old in _LEGACY_MODEL_ENVS:
            if os.getenv(old):
                _legacy_notice(old)
    switch = (os.getenv("TOKENFRUGAL_TF_ROLES_MODELS") or os.getenv("TOKENFRUGAL_AGENT_MODELS")
              or os.getenv("TOKENFRUGAL_PERSONA_MODELS"))
    disabled = switch == "0" or any(os.getenv(f"TOKENFRUGAL_MODEL_{k.upper()}") for k in cfg["models"])
    cfg["known_agents"] = sorted(set(pm) | set(cfg.get("known_agents") or []))  # slugs stay valid when the model mapping is off
    if disabled:
        pm = {}
    cfg["agent_models"] = {k: v for k, v in pm.items() if isinstance(v, str) and v.strip()}
    cfg["mcp_catalog"] = load_catalog()["mcps"]
    try:  # user MCP selection per agent (written by scripts/tf_roles_ui.py); off whenever the model mapping is off
        mc = json.loads(TF_ROLES_MCPS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mc = {}
    cfg["agent_mcps"] = {} if disabled else {k: v for k, v in mc.items() if isinstance(v, list)}
    for k in cfg["models"]:  # TOKENFRUGAL_MODEL_BUILDER / _THINKER swap a model without editing the yaml (benchmarks)
        cfg["models"][k] = os.getenv(f"TOKENFRUGAL_MODEL_{k.upper()}") or cfg["models"][k]
    cfg["agent_skills"] = dict(_yaml_section(cfg, "tf_roles_skills", ("agent_skills", "persona_skills")))
    # Role -> model tag from the dashboard Configuration tab; wins over the logical model in tf-roles.yaml.
    cfg["role_models"] = {k: v for k, v in (_overrides.get("role_models") or {}).items() if isinstance(v, str) and v.strip()}
    # Role -> MCP names from the dashboard Configuration tab; an agent_mcps entry for one agent still wins.
    cfg["role_mcps"] = {k: [n for n in v if isinstance(n, str)] for k, v in (_overrides.get("role_mcps") or {}).items() if isinstance(v, list)}
    return cfg


load_agents = load_tf_roles  # pre-rename name, kept for callers


def resolve_role(agent: str, cfg: dict) -> dict:
    """Map an agency-agents slug (e.g. 'engineering-sre') to its role config."""
    div = max((d for d in cfg["divisions"] if agent.startswith(d + "-") or agent == d), key=len, default=None)
    div = next((d for d, slugs in cfg.get("members", {}).items() if agent in slugs), div)
    role = cfg["overrides"].get(agent) or (cfg["divisions"][div] if div else "builder")
    r = dict(cfg["roles"][role])
    r["role"] = role
    r["model"] = cfg.get("role_models", {}).get(role) or cfg["models"][r["model"]]
    own = list(r.get("skills") or [])
    r["skills"] = own + [s for s in cfg.get("agent_skills", {}).get(agent, []) if s not in own]
    chosen = cfg.get("agent_mcps", {}).get(agent) or cfg.get("role_mcps", {}).get(role) or []
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
    pm = cfg.get("agent_models", {}).get(agent)
    if pm:  # a logical name (builder/thinker) or a concrete model tag
        r["model"] = cfg["models"].get(pm, pm)
    return r


def check_agent(slug: str, cfg: dict) -> str:
    """Return '' when slug is a known agent, else a short error."""
    known = set(cfg.get("overrides") or {}) | set(cfg.get("agent_models") or {}) | set(cfg.get("known_agents") or []) | set(cfg.get("agent_skills") or {})
    for slugs in (cfg.get("members") or {}).values():
        known |= set(slugs)
    if slug in known:
        return ""
    return f"unknown agent '{slug}'; call list_roles for valid slugs"
