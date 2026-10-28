"""Checks that run before every task, benchmark case and skill-gate variant, not once per run.

Each check returns a short error string, or '' when the check passes. Callers refuse the work on any error, so a
wrong mount, an unknown agent or a missing skill file costs no model time.
"""
import re
from pathlib import Path

from .config import ROOT, check_agent, missing_workspace_folder


def task_error(agent: str, task: str, cfg: dict, workspace: str) -> str:
    """Refuse a dispatch whose agent is unknown, whose role has a static config problem (tool registry included), or
    whose task names a /workspace folder that does not exist."""
    err = check_agent(agent, cfg)
    if not err and "roles" in cfg:
        err = role_error(agent, cfg, ROOT)
    return err or missing_workspace_folder(task, workspace)


def role_error(agent: str, cfg: dict, root: Path) -> str:
    """Static role check for the role an agent resolves to, so a broken role is refused at dispatch."""
    from .config import resolve_role

    name = resolve_role(agent, cfg)["role"]
    return "; ".join(role_errors({name: cfg["roles"][name]}, root).get(name, []))


def mount_error(folder: Path, ws_path: str) -> str:
    """Refuse when the sandbox would not resolve ws_path (a /workspace path) to the host folder `folder`."""
    from . import sandbox_mcp  # imported here: only the sandbox-backed checks need the MCP module

    folder.mkdir(parents=True, exist_ok=True)
    got = sandbox_mcp._resolve(ws_path)
    if got != folder.resolve():
        return f"{ws_path} resolves to {got}, but the cases seed {folder.resolve()}"
    return ""


def skill_error(skill_file: Path, expected_text: str) -> str:
    """Refuse when the live skill file is missing or no longer holds the text the gate expects to restore."""
    if not skill_file.exists():
        return f"skill file {skill_file} is missing"
    live = skill_file.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if live != expected_text:
        return f"skill file {skill_file} differs from the expected baseline; restore it before running the gate"
    return ""


def heal_skill(skill_file: Path, expected_text: str) -> str:
    """Self-heal for the skill file: rewrite it to the baseline text the gate expects, then re-check. Returns the
    action taken ('' when nothing was needed). Only the one file is touched, and only to the text already on record."""
    if not skill_error(skill_file, expected_text):
        return ""
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_bytes(expected_text.encode("utf-8"))
    remaining = skill_error(skill_file, expected_text)
    if remaining:
        return f"heal failed: {remaining}"
    return f"restored {skill_file} to the baseline text"


MAX_TOOLS = 6  # the same cap the role tests enforce
MODELS = {"builder", "thinker"}  # the two local models; the role's `model` key names one of them
NATIVE = {"synaptree", "sandbox", "plan", "sonarqube", "crawl4ai"}  # native servers a role may use

# In-repo native servers: their tool names are read from the @mcp.tool() definitions, so no model or Docker is needed.
# synaptree and sonarqube run elsewhere, so their tools cannot be read offline and stay "unverified".
NATIVE_SOURCES = {
    "sandbox": "router/sandbox_mcp.py",
    "plan": "router/plan_mcp.py",
    "crawl4ai": "docker/crawl4ai-mcp/server.py",
}
_TOOL_DEF = re.compile(r"@mcp\.tool\([^)]*\)\s*\n(?:async\s+)?def\s+(\w+)")


def _as_list(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


def _native_tools(root: Path, name: str):
    """Tool names a native server defines, or None when they cannot be read offline."""
    src = NATIVE_SOURCES.get(name)
    if src is None or not (root / src).exists():
        return None
    return set(_TOOL_DEF.findall((root / src).read_text(encoding="utf-8")))


def _profile_tools(root: Path, profile: str):
    """Tool names a Docker MCP profile serves, or None when the profile does not name them (an unfiltered server
    with no snapshot list). A missing profile file also gives None: the file error is reported on its own."""
    import yaml

    path = root / "profiles" / f"{profile}.yaml"
    if not path.exists():
        return None
    names = set()
    for srv in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("servers") or []:
        if srv.get("tools"):  # the gateway filter is the allowlist the role gets
            names |= {t if isinstance(t, str) else t.get("name") for t in srv["tools"]}
            continue
        snap = ((srv.get("snapshot") or {}).get("server") or {}).get("tools")
        if snap is None:
            return None
        names |= {t["name"] for t in snap}
    return names


def tool_sources(role: dict, root: Path) -> dict:
    """{source label: set of tool names, or None when the source cannot be read offline} for one role."""
    out = {}
    for p in _as_list(role.get("profile")):
        out[f"profile {p}"] = _profile_tools(root, p)
    for n in _as_list(role.get("native")):
        out[f"native {n}"] = _native_tools(root, n)
    return out


def tool_gaps(role: dict, root: Path):
    """(missing, unverified). `missing` lists role tools that no readable source provides; `unverified` lists the
    sources that could not be read offline. A tool is only reported missing when every source is readable."""
    sources = tool_sources(role, root)
    unverified = [label for label, names in sources.items() if names is None]
    provided = set().union(*(names for names in sources.values() if names is not None))
    if unverified:
        return [], unverified
    missing = [t for t in _as_list(role.get("tools")) if t not in provided]
    return missing, []


def role_errors(roles: dict, root: Path) -> dict:
    """Static check of every role in tf-roles.yaml, no model call. Returns {role: [problem, ...]} for roles with
    problems. Checks: model name, tool count, profile file, skill file, compose services, native server names, and
    tools that no readable profile or native server provides."""
    import yaml

    compose = set((yaml.safe_load((root / "docker-compose.yml").read_text(encoding="utf-8")) or {}).get("services") or {})
    out = {}
    for name, role in roles.items():
        probs = []
        if role.get("model") not in MODELS:
            probs.append(f"model '{role.get('model')}' is not builder or thinker")
        tools = _as_list(role.get("tools"))
        if len(tools) > MAX_TOOLS:
            probs.append(f"{len(tools)} tools, cap is {MAX_TOOLS}")
        for p in _as_list(role.get("profile")):
            if not (root / "profiles" / f"{p}.yaml").exists():
                probs.append(f"profile file profiles/{p}.yaml is missing")
        for s in _as_list(role.get("skills")):
            if not (root / "router" / "skills" / s / "SKILL.md").exists():
                probs.append(f"skill router/skills/{s}/SKILL.md is missing")
        for c in _as_list(role.get("compose")):
            if c not in compose:
                probs.append(f"compose service '{c}' is not in docker-compose.yml")
        for n in _as_list(role.get("native")):
            if n not in NATIVE:
                probs.append(f"native server '{n}' is not a known native server")
        req = role.get("required_tool")
        if req and tools and req not in tools:
            probs.append(f"required_tool '{req}' is not in the role's tools")
        missing, _ = tool_gaps(role, root)
        for t in missing:
            probs.append(f"tool '{t}' is not provided by any of its profiles or native servers")
        if probs:
            out[name] = probs
    return out


def unverified_roles(roles: dict, root: Path) -> dict:
    """{role: [source, ...]} for roles whose tools could not be checked offline (unfiltered profile, synaptree, ...)."""
    out = {}
    for name, role in roles.items():
        _, unverified = tool_gaps(role, root)
        if unverified:
            out[name] = unverified
    return out


CONTRACT_FIELDS = ("purpose", "inputs", "output_format", "stop_condition", "checklist")
CHECK_KINDS = ("deterministic", "judgement")


def contract_errors(roles: dict, contracts: dict) -> dict:
    """{role: [problem, ...]} for an active role whose contract is missing or incomplete, and for contracts naming no role.
    A contract needs every field, and a checklist of 3+ items, each with text and a kind of deterministic or judgement."""
    out = {}
    for name in roles:
        c = contracts.get(name)
        if not isinstance(c, dict):
            out[name] = ["no contract"]
            continue
        probs = [f"missing {f}" for f in CONTRACT_FIELDS if not c.get(f)]
        items = c.get("checklist")
        if items and not isinstance(items, list):
            probs.append("checklist must be a list")
        elif isinstance(items, list):
            if len(items) < 3:
                probs.append("checklist needs 3 or more items")
            for item in items:
                if not isinstance(item, dict) or not str(item.get("text") or "").strip() or item.get("kind") not in CHECK_KINDS:
                    probs.append(f"checklist item needs text and a kind of {' or '.join(CHECK_KINDS)}: {item!r}")
        if probs:
            out[name] = probs
    for name in contracts:
        if name not in roles:
            out[name] = ["contract has no active role"]
    return out


if __name__ == "__main__":
    import sys
    from .config import ROOT, load_tf_roles

    roles = load_tf_roles().get("roles") or {}
    bad = role_errors(roles, ROOT)
    for name, probs in sorted(bad.items()):
        print(f"{name}: " + "; ".join(probs))
    unv = unverified_roles(roles, ROOT)
    for name, srcs in sorted(unv.items()):
        print(f"{name}: unverified (cannot read tools offline from {', '.join(srcs)})")
    print(f"{len(roles)} roles checked, {len(bad)} need fixing, {len(unv)} unverified")
    sys.exit(1 if bad else 0)
