"""Restart and reconnect MCP servers on request from the dashboard, without restarting the gateway.

Connections are opened per task (mcp_client.open_role), so "reconnect" means: recreate the server's compose
backends, then open a fresh connection through the normal client path and list its tools to prove it works.
The dashboard (ui/server.js) drops a request file next to events.jsonl; each gateway polls for it, claims it
with an atomic rename, and writes the outcome to a result file the dashboard reads. Secrets are never logged.
"""
import asyncio
import contextlib
import json
import os

from . import compose
from .events import EVENTS_PATH
from .mcp_client import open_native, open_profile

REQUEST = EVENTS_PATH.with_name("reconnect_request.json")
RESULT = EVENTS_PATH.with_name("reconnect_result.json")
PROBE_TIMEOUT = 90  # seconds to open a connection and list its tools


def _short(e: BaseException) -> str:
    return f"{type(e).__name__}: {str(e)[:150]}"


async def _probe(m: dict) -> int:
    """Open each profile/native the MCP uses through the normal client path; return the tool count."""
    n = 0
    for p in ([m["profile"]] if m.get("profile") else []):
        async with open_profile(p) as s:
            n += len((await s.list_tools()).tools)
    if m.get("native"):
        async with open_native(m["native"]) as s:
            n += len((await s.list_tools()).tools)
    return n


async def restart_one(name: str, catalog: dict) -> dict:
    """Recreate one MCP's backends and reconnect. Returns {name, ok, message}."""
    m = catalog.get(name)
    if m is None:
        return {"name": name, "ok": False, "message": "unknown MCP server"}
    busy = [s for s in m.get("compose", []) if compose._users.get(s)]
    if busy:
        return {"name": name, "ok": False, "message": f"in use by a running task ({', '.join(busy)}); try again when idle"}
    try:
        await compose.recreate(m.get("compose", []))
        n = await asyncio.wait_for(_probe(m), PROBE_TIMEOUT)
    except asyncio.TimeoutError:
        return {"name": name, "ok": False, "message": f"reconnect timed out after {PROBE_TIMEOUT}s"}
    except Exception as e:  # noqa: BLE001
        return {"name": name, "ok": False, "message": _short(leaf(e))}
    return {"name": name, "ok": True, "message": f"reconnected, {n} tools"}


def leaf(e: BaseException) -> BaseException:
    """Innermost cause of an ExceptionGroup (anyio task groups wrap errors)."""
    while getattr(e, "exceptions", None):
        e = e.exceptions[0]
    return e


async def restart(target: str, catalog: dict) -> dict:
    """target is one MCP name or 'all'. Servers restart one at a time."""
    names = list(catalog) if target == "all" else [target]
    results = [await restart_one(n, catalog) for n in names]
    bad = [r for r in results if not r["ok"]]
    msg = "; ".join(f"{r['name']}: {r['message']}" for r in (bad or results)[:6])
    return {"target": target, "ok": not bad, "message": msg, "results": results}


def _write_result(out: dict) -> None:
    tmp = RESULT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out), encoding="utf-8")
    os.replace(tmp, RESULT)


async def poll_once(catalog: dict) -> bool:
    """Handle one pending dashboard request, if any. Returns True when one was handled."""
    claim = REQUEST.with_suffix(f".{os.getpid()}")
    try:
        os.replace(REQUEST, claim)  # atomic: only one gateway process wins the request
    except OSError:
        return False
    try:
        req = json.loads(claim.read_text(encoding="utf-8"))
        target = req["target"]
        if not isinstance(target, str):
            raise ValueError("bad target")
        out = await restart(target, catalog)
    except Exception as e:  # noqa: BLE001
        req, out = {}, {"ok": False, "message": _short(e), "results": []}
    finally:
        with contextlib.suppress(OSError):
            claim.unlink()
    _write_result({**out, "id": req.get("id")})
    return True


async def poll_loop(catalog: dict) -> None:
    while True:
        await asyncio.sleep(1)
        with contextlib.suppress(Exception):
            await poll_once(catalog)
