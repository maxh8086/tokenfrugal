"""Gateway configuration (env-overridable)."""
import json
import os
import re
import secrets
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # LLM endpoint etc.; real environment variables win

# Any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, a hosted API). Host and port live in .env.
OLLAMA_URL = os.getenv("TOKENFRUGAL_LLM_URL") or os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("TOKENFRUGAL_LLM_API_KEY", "ollama")
# Exact host path the Docker gateway may bind writable (defaults to the checkout; see docker catalogue volume).
WORKSPACE = os.getenv("CC_WORKSPACE", ROOT.as_posix())
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


def _load_neo4j_env() -> None:
    """Make NEO4J_AUTH (user/password) available to this process and compose; created once if missing.
    The value lives only in the secrets env file; it is never printed or logged."""
    f = Path(MCP_ENV_FILE)
    try:
        if f.exists() and "NEO4J_AUTH=" not in f.read_text(encoding="utf-8"):
            with f.open("a", encoding="ascii") as fh:
                fh.write(f"{chr(10)}NEO4J_AUTH=neo4j/{secrets.token_hex(16)}{chr(10)}")
        for line in f.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "NEO4J_AUTH" and v.strip():
                os.environ.setdefault("NEO4J_AUTH", v.strip())
    except OSError:
        pass


_load_neo4j_env()
KEEP_ALIVE = os.getenv("MCP_KEEP_ALIVE", "") == "1"  # leave backends running after a task
for _n, _svc in (("crawl4ai", "mcp-crawl4ai"), ("sonarqube", "mcp-sonarqube")):
    NATIVE_SERVERS[_n] = {"command": "docker", "args": ["compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE),
                                                         "run", "--rm", "-T", _svc]}
NATIVE_SERVERS["plan"] = {"command": sys.executable, "args": ["-m", "gateway.plan_mcp"]}
# synaptree-mcp project = checkout folder name; SYNAPTREE_PROJECT overrides it
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
    return yaml.safe_load((Path(__file__).parent / "mcp_catalog.yaml").read_text(encoding="utf-8"))


def default_mcps(role: dict, catalog: dict) -> list[str]:
    """MCPs whose tools the role already allows (the benchmarked default toolkit)."""
    return [n for n, m in catalog["mcps"].items() if set(m["tools"]) & set(role["tools"])]


def load_personas() -> dict:
    cfg = yaml.safe_load((Path(__file__).parent / "personas.yaml").read_text(encoding="utf-8"))
    pm = dict(cfg.get("persona_models") or {})
    try:  # user overrides (written by scripts/persona_ui.py) win over the yaml defaults
        pm.update(json.loads(PERSONA_MODELS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    # Benchmarks pin one model for every persona with TOKENFRUGAL_MODEL_*; TOKENFRUGAL_PERSONA_MODELS=0 disables the mapping.
    disabled = os.getenv("TOKENFRUGAL_PERSONA_MODELS") == "0" or any(os.getenv(f"TOKENFRUGAL_MODEL_{k.upper()}") for k in cfg["models"])
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
    return cfg


def resolve_role(agent: str, cfg: dict) -> dict:
    """Map an agency-agents slug (e.g. 'engineering-sre') to its role config."""
    div = max((d for d in cfg["divisions"] if agent.startswith(d + "-") or agent == d), key=len, default=None)
    div = next((d for d, slugs in cfg.get("members", {}).items() if agent in slugs), div)
    role = cfg["overrides"].get(agent) or (cfg["divisions"][div] if div else "builder")
    r = dict(cfg["roles"][role])
    r["role"] = role
    r["model"] = cfg["models"][r["model"]]
    own = list(r.get("skills") or [])
    r["skills"] = own + [s for s in cfg.get("persona_skills", {}).get(agent, []) if s not in own]
    sel = [n for n in cfg.get("persona_mcps", {}).get(agent, []) if n in cfg.get("mcp_catalog", {})]
    if sel:  # user-chosen toolkit: open the distinct profiles/natives/backends and allow the union of tools
        ms = [cfg["mcp_catalog"][n] for n in sel]
        uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))
        r["profile"] = uniq(m.get("profile") for m in ms) or None
        r["native"] = uniq(m.get("native") for m in ms)
        r["compose"] = uniq(c for m in ms for c in m.get("compose", []))
        r["tools"] = uniq(t for m in ms for t in m["tools"])
        r["mcps"] = sel
    pm = cfg.get("persona_models", {}).get(agent)
    if pm:  # a logical name (builder/thinker) or a concrete model tag
        r["model"] = cfg["models"].get(pm, pm)
    return r
