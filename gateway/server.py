"""Claude-facing MCP gateway. Claude plans and dispatches; local models do the work.

Tools return only capped summaries. Full output stays in the task store (get_detail).
Failure never falls back to cloud: a short capped error summary + task_id goes back for retry/resume.
"""
import asyncio
import atexit
import contextlib
import signal
import sys

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from . import compose, events, plan, store, ui_launcher
from .config import load_personas, resolve_role
from .loop import leaf, run, take_usage
from .summarize import hard_trim, saved_tokens, summarize

CFG = load_personas()
STALE_REASON = "gateway stopped while task was running (no heartbeat)"


async def _warm_up():
    """Start neo4j and create its schema in the background; failures only disable plan features."""
    try:
        await compose.ensure(["neo4j"])
        await asyncio.to_thread(plan.wait_ready)
        await asyncio.to_thread(plan.init)
        await asyncio.to_thread(plan.prune)
    except Exception:  # noqa: BLE001
        pass


@contextlib.asynccontextmanager
async def _lifespan(_server):
    """The last gateway to exit stops every ts-mcp container (also on SIGTERM and interpreter exit)."""
    events.write_roles(CFG)
    store.sweep_stale(STALE_REASON)
    sweeper = asyncio.create_task(_sweep_loop())
    await asyncio.to_thread(ui_launcher.start)
    atexit.register(ui_launcher.stop)
    compose.register()
    atexit.register(compose.release)
    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            with contextlib.suppress(ValueError, OSError):
                signal.signal(getattr(signal, name), lambda *_: sys.exit(0))
    warm = asyncio.create_task(_warm_up())
    try:
        yield
    finally:
        warm.cancel()
        sweeper.cancel()
        ui_launcher.stop()
        compose.release()


class _ClientSeen(Middleware):
    """Reports which MCP client (Claude, Codex, ...) opened this gateway process, for the dashboard."""

    async def on_initialize(self, context, call_next):
        # pydantic exposes the MCP field as snake_case `client_info`, not `clientInfo`
        info = getattr(getattr(context.message, "params", None), "client_info", None)
        if info is not None:
            events.emit("client", name=info.name)
        return await call_next(context)


mcp = FastMCP("tokenfrugal", lifespan=_lifespan, middleware=[_ClientSeen()])


async def _plan(fn, *a, **kw):
    """Plan store call that never breaks a dispatch: returns (ok, text)."""
    try:
        await compose.ensure(["neo4j"])
        return True, await asyncio.to_thread(fn, *a, **kw)
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:150]}"


async def _heartbeat(tid: str) -> None:
    """Keep this task's row fresh so other gateways' sweeps leave it alone."""
    while True:
        await asyncio.sleep(store.HEARTBEAT_EVERY)
        await asyncio.to_thread(store.beat, tid)


async def _sweep_loop() -> None:
    """Fail rows left running by gateways that were killed without a restart of this one."""
    while True:
        await asyncio.sleep(store.HEARTBEAT_EVERY * 2)
        await asyncio.to_thread(store.sweep_stale, STALE_REASON)


async def _execute(tid: str, agent: str, role: dict, prompt: str, messages=None, plan_id: int = 0) -> str:
    row = store.get(tid)
    store.update(tid, status="running", attempts=(row["attempts"] or 0) + 1)
    events.emit("task_start", id=tid, agent=agent, role=role["role"], model=role["model"],
                max_steps=role["max_steps"], attempt=(row["attempts"] or 0) + 1, prompt=prompt[:300])
    base = len(messages or [])  # messages from an earlier run were already counted
    beat = asyncio.create_task(_heartbeat(tid))
    try:
        detail, msgs = await run(agent, role, prompt, messages, tid)
        summary = summarize(role["model"], detail, prompt)
        events.emit("task_done", id=tid, role=role["role"], model=role["model"], summary=summary[:400], saved=saved_tokens(msgs[base:], summary),
                    task=prompt[:80], agent=agent, **take_usage(tid))
        store.update(tid, status="done", summary=summary, detail=detail, messages=msgs, error=None)
        if plan_id:
            await _plan(plan.record_run, plan_id, tid, agent, role["role"], "done", summary)
            ok, msg = await _plan(plan.done, plan_id, tid, "gateway run", "gateway")
            if ok:
                await _plan(plan.checkpoint)
            summary += "" if ok else f" (plan: {msg})"
        return f"[{tid}] {summary}"
    except Exception as e:  # noqa: BLE001
        e = leaf(e)
        err = hard_trim(f"{type(e).__name__}: {e}", 120)
        store.update(tid, status="failed", error=err)
        events.emit("task_failed", id=tid, role=role["role"], model=role["model"], error=err, saved=saved_tokens((getattr(e, "msgs", None) or [])[base:], err),
                    task=prompt[:80], agent=agent, **take_usage(tid))
        if plan_id:
            await _plan(plan.record_run, plan_id, tid, agent, role["role"], "failed", "", err)
            await _plan(plan.set_status, plan_id, "blocked", "gateway", err)
        return f"[{tid}] FAILED ({role['role']}/{role['model']}): {err}. Call resume_task('{tid}') to retry."
    finally:
        beat.cancel()


@mcp.tool()
async def dispatch_task(agent: str, task: str, plan_id: int = 0) -> str:
    """Run a task on a local agent (agency-agents slug, e.g. 'engineering-code-reviewer').
    Optional plan_id links it to a plan task (claimed first, marked done/blocked after).
    Returns a 150-300 token summary and a task_id."""
    role = resolve_role(agent, CFG)
    if plan_id:
        ok, msg = await _plan(plan.claim, plan_id, "gateway")
        if not ok:
            return f"plan task {plan_id} not started: {msg}"
    return await _execute(store.create(agent, role["role"], task), agent, role, task, plan_id=plan_id)


@mcp.tool()
async def plan_add(title: str, depends: list[int] | None = None, priority: int = 0, detail: str = "",
                   tag: str = "") -> str:
    """Add a task to the plan graph. depends = ids of existing tasks it needs first."""
    return (await _plan(plan.add, title, depends, priority, detail, tag))[1]


@mcp.tool()
async def plan_overview(tag: str = "") -> str:
    """Compact plan state: counts per status and every unfinished task."""
    return (await _plan(plan.overview, tag))[1]


@mcp.tool()
async def plan_revert(task_id: int = 0, since: str = "") -> str:
    """Undo status changes: one task's latest change (task_id), or all changes after an ISO time (since)."""
    if task_id:
        return (await _plan(plan.revert, task_id))[1]
    if since:
        return (await _plan(plan.rollback, since))[1]
    return "give task_id or since"


@mcp.tool()
async def plan_update_from(task_id: int) -> str:
    """Re-open a task and everything depending on it (use after changing its approach)."""
    return (await _plan(plan.update_from, task_id))[1]


@mcp.tool()
async def ask_followup(task_id: str, question: str) -> str:
    """Ask the same agent a follow-up about a finished task; context is preserved."""
    t = store.get(task_id)
    if not t or not t["messages"]:
        return f"unknown or empty task {task_id}"
    role = resolve_role(t["agent"], CFG)
    msgs = t["messages"] + [{"role": "user", "content": question}]
    return await _execute(task_id, t["agent"], role, question, msgs)


@mcp.tool()
def get_detail(task_id: str, max_chars: int = 4000) -> str:
    """Fetch the full stored output of a task (use sparingly; costs Claude tokens)."""
    t = store.get(task_id)
    if not t:
        return f"unknown task {task_id}"
    head = (t["detail"] or t["error"] or "no output")[:max_chars]
    trail = [_trail_line(e) for e in t["trail"]]
    return head + ("\n\nevent trail:\n" + "\n".join(trail) if trail else "")


def _trail_line(e: dict) -> str:
    """One line per event: step number, tool name and args, model thought, retry reason, or failure."""
    kind = e.get("kind", "?")
    if kind == "step":
        return f"step {e.get('n')}"
    if kind == "tool":
        return f"tool {e.get('name')} {e.get('args', '')}"
    if kind == "say":
        return f"say {e.get('text', '')[:160]}"
    if kind == "retry":
        return f"retry {e.get('reason', '')[:160]}"
    if kind == "tool_error":
        return f"tool_error {e.get('name')}: {e.get('error', '')[:200]}"
    return f"{kind} {e.get('error') or e.get('summary') or ''}"[:200]


@mcp.tool()
async def resume_task(task_id: str) -> str:
    """Retry a failed task from its saved conversation."""
    t = store.get(task_id)
    if not t:
        return f"unknown task {task_id}"
    role = resolve_role(t["agent"], CFG)
    return await _execute(task_id, t["agent"], role, t["prompt"], t["messages"] or None)


@mcp.tool()
def list_roles() -> str:
    """List roles with model, docker profile, compose backends and tool allowlist."""
    rows = [f"{r['role']}: {r['model']} | {r['profile'] or '-'} | {','.join(r['backends']) or '-'} | "
            f"{','.join(r['tools']) or 'all'}" for r in events.roles_rows(CFG)]
    return "\n".join(["role: model | docker profile | compose backends | tools", *rows])


if __name__ == "__main__":
    mcp.run()
