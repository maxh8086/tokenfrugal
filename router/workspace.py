"""Workspace identity and host-accept security policy."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import config

@dataclass(frozen=True)
class Workspace:
    root: str
    key: str
    host_accept: bool
    env_passthrough: tuple[str, ...]
    venv: Path | None

ENV_ALLOWLIST = frozenset("PATH PATHEXT SYSTEMROOT WINDIR COMSPEC TEMP TMP TMPDIR HOME USERPROFILE HOMEDRIVE HOMEPATH APPDATA LOCALAPPDATA LANG TERM TZ SHELL USER USERNAME LOGNAME".split())
PROTECTED_ALWAYS = frozenset(os.path.normcase(os.path.realpath(p)) for p in
                             (config.ROOT / ".env", config.ROOT / "router" / "config_overrides.json"))
DENYLIST_DIRS = frozenset({".git", ".venv", "venv", "node_modules/.bin", ".github/workflows"})
DENYLIST_NAMES = frozenset(x.casefold() for x in {"conftest.py", "sitecustomize.py", "usercustomize.py", "setup.py", "setup.cfg", "pyproject.toml", "pytest.ini", "tox.ini", "noxfile.py", "package.json", ".npmrc", "Makefile", ".envrc"})

def _key(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))

def load_workspace(root) -> Workspace:
    root = os.path.abspath(os.fspath(root)); key = _key(root)
    venv = Path(config.ACCEPT_VENV) if config.ACCEPT_VENV else None
    if not venv:
        venv = next((p for p in (Path(root)/".venv", Path(root)/"venv") if p.is_dir()), None)
    elif not venv.is_dir():
        venv = None
    return Workspace(root, key, key in config.HOST_ACCEPT_PATHS, tuple(config.ACCEPT_ENV_PASSTHROUGH), venv)

def accept_env(ws: Workspace, spec_env: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if k.upper() in ENV_ALLOWLIST or k.upper().startswith("LC_")}
    env["PYTHONIOENCODING"] = "utf-8"
    if ws.venv:
        env["VIRTUAL_ENV"] = str(ws.venv)
        bindir = ws.venv / ("Scripts" if os.name == "nt" else "bin")
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    for name in (*ws.env_passthrough, *spec_env):
        if name in os.environ:
            env[name] = os.environ[name]
    env.update(spec_env)
    return env

def denied(rel: str, allowed: set[str], ws: Workspace) -> bool:
    raw = rel.replace("\\", "/")
    path = _key(Path(ws.root) / raw)
    if path in PROTECTED_ALWAYS:
        return True
    if not ws.host_accept or raw.lstrip("/") in allowed:
        return False
    root = os.path.realpath(ws.root)
    try:
        resolved_rel = os.path.relpath(path, root)
    except ValueError:
        resolved_rel = path
    candidates = (raw, resolved_rel.replace("\\", "/"))
    denied_dirs = {tuple(item.split("/")) for item in DENYLIST_DIRS}
    for candidate in candidates:
        parts = [part.casefold() for part in candidate.replace("\\", "/").split("/") if part not in ("", ".")]
        if any(tuple(parts[i:i + len(denied)]) == denied
               for denied in denied_dirs for i in range(len(parts) - len(denied) + 1)):
            return True
        name = parts[-1] if parts else ""
        if name in DENYLIST_NAMES or name.endswith(".pth"):
            return True
    return False

def to_rel(ws: Workspace, tool_path: str) -> str:
    raw = str(tool_path)
    if raw.startswith("/workspace/"):
        return raw[len("/workspace/"):].replace("\\", "/")
    candidate = _key(raw)
    try:
        if os.path.commonpath((candidate, ws.key)) == ws.key:
            return os.path.relpath(candidate, ws.key).replace("\\", "/")
    except ValueError:
        pass
    return raw

def legacy_task_files(ws: Workspace, task_text: str, limit: int = 3) -> tuple[str, ...]:
    from . import loop, config
    found = []
    def add(value):
        rel = to_rel(ws, value)
        suffix = Path(rel).suffix[1:]
        if rel.casefold() in {"e.g", "i.e"} or (suffix and suffix.isdigit()):
            return
        if (suffix or (Path(ws.root) / rel).exists()) and rel not in found:
            found.append(rel)
    for value in loop.named_paths(task_text):
        add(value)
    for match in re.findall(r"(?<![\w./-])([\w./-]+\.[A-Za-z0-9]{1,8})(?![\w-])", task_text):
        add(match)
    for match in config.WORKSPACE_PATH.finditer(task_text):
        add(match.group(1))
    return tuple(found[:limit])
