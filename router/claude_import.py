"""Import Claude-style `mcpServers` JSON into TokenFrugal's MCP catalog.

Input shape (same as Claude Code / Claude Desktop):
    {"mcpServers": {"memory": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"], "env": {}}}}
Each entry becomes a native stdio server (`servers`) plus a catalog entry (`mcps`), stored in
router/imported_mcps.json and merged by config.py. Env values may be `keyring:NAME` references.

Usage: python -m router.claude_import FILE.json [--probe]   (--probe lists the server's tools and records them)
"""
import asyncio
import json
import re
import sys
from pathlib import Path

IMPORT_FILE = Path(__file__).parent / "imported_mcps.json"
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def convert_server(name: str, spec: dict) -> tuple[dict, dict]:
    """One mcpServers entry -> (catalog entry, native server spec). Raises ValueError for unsupported entries."""
    if not _NAME.match(name or ""):
        raise ValueError(f"server name '{name}' must be lowercase letters, digits, '-' or '_'")
    if not isinstance(spec, dict) or not spec.get("command"):
        raise ValueError(f"server '{name}': only stdio servers with a 'command' are supported (remote url servers are not)")
    args = [str(a) for a in spec.get("args") or []]
    env = {str(k): str(v) for k, v in (spec.get("env") or {}).items()}
    server = {"command": str(spec["command"]), "args": args, "env": env}
    entry = {"label": f"{name} (imported from Claude JSON)", "native": name, "tools": list(spec.get("tools") or [])}
    return entry, server


def convert(doc: dict) -> dict:
    """Whole document -> {"servers": {...}, "mcps": {...}}."""
    servers = doc.get("mcpServers") if isinstance(doc, dict) else None
    if not isinstance(servers, dict) or not servers:
        raise ValueError("expected a JSON object with a non-empty 'mcpServers' block")
    out = {"servers": {}, "mcps": {}}
    for name, spec in servers.items():
        out["mcps"][name], out["servers"][name] = convert_server(name, spec)
    return out


def load(path: Path = IMPORT_FILE) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"servers": dict(d.get("servers") or {}), "mcps": dict(d.get("mcps") or {})}


def install(doc: dict, path: Path = IMPORT_FILE) -> list[str]:
    """Merge the converted entries into the import file (replacing same-named ones); return the names."""
    new, cur = convert(doc), load(path)
    cur["servers"].update(new["servers"])
    cur["mcps"].update(new["mcps"])
    Path(path).write_text(json.dumps(cur, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sorted(new["mcps"])


async def probe_tools(name: str) -> list[str]:
    from . import config, mcp_client
    config.NATIVE_SERVERS.update(load()["servers"])
    async with mcp_client.open_native(name) as s:
        return [t.name for t in (await s.list_tools()).tools]


def main(argv: list[str]) -> int:
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2
    names = install(json.loads(Path(files[0]).read_text(encoding="utf-8")))
    if "--probe" in argv:
        cur = load()
        for n in names:
            cur["mcps"][n]["tools"] = asyncio.run(probe_tools(n))
        IMPORT_FILE.write_text(json.dumps(cur, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("installed:", ", ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
