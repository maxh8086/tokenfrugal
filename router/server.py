"""Claude-facing MCP router. Claude plans and dispatches; local models do the work.

Tools return only capped summaries. Full output stays in the task store (get_detail).
Failure never falls back to cloud: a short capped error summary + task_id goes back for retry/resume.
"""
import asyncio
import atexit
import contextlib
import re
import signal
import sys
import time

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from . import checker, compose, events, plan, reconnect, store, ui_launcher
from .config import WORKSPACE, load_tf_roles, resolve_role
from .preflight import task_error
from .loop import error_kind, failure_reason, leaf, role_timeout, run, take_started, take_usage
from .summarize import hard_trim, saved_tokens, summarize

CFG = load_tf_roles()
DIFF_FENCE = re.compile(r"```diff\r?\n(.*?)```", re.S)
STALE_REASON = "router stopped while task was running (no heartbeat)"
HEALTH_EVERY = 10  # seconds between health events; the dashboard marks a router down after ~3 missed beats
RESUME_HINT = {"connection": "retry", "infra": "retry", "timeout": "retry"}  # other reasons: re-scope instead
RESCOPE = "Re-scope the task smaller and dispatch again; resume_task will repeat the same failure."


def kind_hint(kind: str, started: int) -> str:
    """Short next-step hint for an error_kind; empty for 'error', which keeps the reason-based hint."""
    if kind in ("step_timeout", "request_timeout"):
        if started:
            return f"Timed out after {started} tool calls. Call resume_task once, or split the task."
        return "Timed out before any tool call. Split the task into smaller tasks. Do not resume_task."
    if kind == "no_tool_call":
        return "The model answered without calling a tool. Name the exact tool and path in the task."
    if kind == "max_steps":
        return "Step budget used up. Narrow the scope of the task."
    return ""


def failure_message(tid: str, role: dict, err: str, reason: str, kind: str = "error", started: int = 0) -> str:
    """The short failure reply Haiku reads: reason class, error_kind, and the next step it should take."""
    hint = kind_hint(kind, started)
    if not hint:
        if reason in RESUME_HINT:
            hint = f"Call resume_task('{tid}') to retry."
        elif reason == "unknown":
            hint = f"Call resume_task('{tid}') once, then re-scope."
        else:
            hint = RESCOPE
    return f"[{tid}] FAILED ({role['role']}/{role['model']}) reason={reason} error_kind={kind}: {err}. {hint}"


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
    """The last router to exit stops every tokenfrugal container (also on SIGTERM and interpreter exit)."""
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
    reconnector = asyncio.create_task(reconnect.poll_loop(CFG["mcp_catalog"]))
    beat = asyncio.create_task(_health_loop())
    try:
        yield
    finally:
        beat.cancel()
        events.emit("health", status="down")
        warm.cancel()
        reconnector.cancel()
        sweeper.cancel()
        ui_launcher.stop()
        compose.release()


class _ClientSeen(Middleware):
    """Reports which MCP client (Claude, Codex, ...) opened this router process, for the dashboard."""

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


async def _health_loop() -> None:
    """Publish this router's own health so the dashboard's /health reflects the router, not the dashboard."""
    while True:
        events.emit("health", status="up")
        await asyncio.sleep(HEALTH_EVERY)


async def _sweep_loop() -> None:
    """Fail rows left running by gateways that were killed without a restart of this one."""
    while True:
        await asyncio.sleep(store.HEARTBEAT_EVERY * 2)
        await asyncio.to_thread(store.sweep_stale, STALE_REASON)


class CheckFailed(Exception):
    """The checker still failed after its one correction; the message is the failed checks."""


def accept_cmd(text: str) -> list[str] | None:
    """argv of the task's acceptance command: the last 'Accept:' line, split on spaces. None when the task has none."""
    cmd = None
    for line in text.splitlines():
        if line.strip().lower().startswith("accept:"):
            cmd = line.strip()[len("accept:"):].split() or None
    return cmd


def diff_block(text: str) -> str | None:
    """The first ```diff block of a reply, without its fences. None when the reply has none."""
    m = DIFF_FENCE.search(text or "")
    return m.group(1) if m else None


def _check(role: dict, prompt: str, detail: str, t0: float) -> dict | None:
    """Deterministic checks, run only when the task names an Accept: command or the reply holds a ```diff block.
    The accept command gets what is left of the role's timeout_s after the run, so run and checks share one budget."""
    accept = accept_cmd(prompt)
    diff = diff_block(detail)
    if accept is None and diff is None:
        return None
    left = int(role_timeout(role) - (time.monotonic() - t0))
    return checker.check_deterministic(WORKSPACE, accept, diff, timeout=max(5, left))


def _failed_text(verdict: dict) -> str:
    return "; ".join(f"{i['name']}: {i['detail']}" for i in verdict["items"] if not i["passed"])


def _fix_prompt(verdict: dict) -> str:
    return (f"Checker failed: {_failed_text(verdict)}. Reply with a diff only, in a ```diff block, "
            "that fixes these. Do not explain.")


def _report(verdict: dict | None, role: dict) -> str:
    """Checker line appended to the summary; the judgement items go to the client to decide."""
    if verdict is None:
        return ""
    parts = []
    for i in verdict["items"]:
        state = "ok" if i["passed"] else "FAILED"
        shown = i["name"] == "files_changed" or not i["passed"]
        parts.append(f"{i['name']} {state}" + (f" ({i['detail']})" if shown else ""))
    text = "\nChecks: " + "; ".join(parts) + "."
    contract = (CFG.get("contracts") or {}).get(role["role"], {})
    judge = [c["text"] for c in contract.get("checklist") or [] if c.get("kind") == "judgement"]
    if judge:
        text += "\nJudge (client): " + " / ".join(judge) + "."
    return text


async def _execute(tid: str, agent: str, role: dict, prompt: str, messages=None, plan_id: int = 0) -> str:
    row = store.get(tid)
    store.update(tid, status="running", attempts=(row["attempts"] or 0) + 1)
    events.emit("task_start", id=tid, agent=agent, role=role["role"], model=role["model"],
                max_steps=role["max_steps"], attempt=(row["attempts"] or 0) + 1, prompt=prompt[:300],
                tools=role.get("tools") or [], skills=role.get("skills") or [])
    base = len(messages or [])  # messages from an earlier run were already counted
    t0 = time.monotonic()
    beat = asyncio.create_task(_heartbeat(tid))
    try:
        detail, msgs = await run(agent, role, prompt, messages, tid)
        take_started(tid)
        verdict = await asyncio.to_thread(_check, role, prompt, detail, t0)
        if verdict and not verdict["passed"]:  # one correction, continuing the same message history
            detail, msgs = await run(agent, role, _fix_prompt(verdict), msgs, tid)
            take_started(tid)
            verdict = await asyncio.to_thread(_check, role, prompt, detail, t0)
            if verdict and not verdict["passed"]:
                raise CheckFailed(_failed_text(verdict))
        summary = summarize(role["model"], detail, prompt) + _report(verdict, role)
        events.emit("task_done", id=tid, role=role["role"], model=role["model"], summary=summary[:400], saved=saved_tokens(msgs[base:], summary),
                    task=prompt[:80], agent=agent, e2e=round(time.monotonic() - t0, 2), **take_usage(tid))
        store.update(tid, status="done", summary=summary, detail=detail, messages=msgs, error=None)
        if plan_id:
            await _plan(plan.record_run, plan_id, tid, agent, role["role"], "done", summary)
            ok, msg = await _plan(plan.done, plan_id, tid, "router run", "router")
            if ok:
                await _plan(plan.checkpoint)
            summary += "" if ok else f" (plan: {msg})"
        return f"[{tid}] {summary}"
    except Exception as e:  # noqa: BLE001
        if isinstance(e, CheckFailed):
            full, reason, kind = str(e), "checker", "checker"
        else:
            e = leaf(e)
            full = f"{type(e).__name__}: {e}"
            reason = failure_reason(full)
            kind = error_kind(full)
        started = take_started(tid)
        err = hard_trim(full, 300 if kind == "checker" else 120)
        store.update(tid, status="failed", error=err, error_kind=kind)
        events.emit("task_failed", id=tid, role=role["role"], model=role["model"], error=err, reason=reason, error_kind=kind,
                    saved=saved_tokens((getattr(e, "msgs", None) or [])[base:], err),
                    task=prompt[:80], agent=agent, e2e=round(time.monotonic() - t0, 2), **take_usage(tid))
        if plan_id:
            await _plan(plan.record_run, plan_id, tid, agent, role["role"], "failed", "", err)
            await _plan(plan.set_status, plan_id, "blocked", "router", err)
        return failure_message(tid, role, err, reason, kind, started)
    finally:
        beat.cancel()


@mcp.tool()
async def dispatch_task(agent: str = "", task: str = "", plan_id: int = 0, role: str = "") -> str:
    """Run a task on a local tf-role (agency-agents slug, e.g. 'engineering-code-reviewer').
    `role` is an alias for `agent`; when both are given, `agent` wins.
    Optional plan_id links it to a plan task (claimed first, marked done/blocked after).
    Returns a summary of up to 5000 tokens and a task_id."""
    agent = agent or role
    if not agent:
        return "give agent (or role) and task"
    err = task_error(agent, task, CFG, WORKSPACE)
    if err:
        return err
    role = resolve_role(agent, CFG)
    if plan_id:
        ok, msg = await _plan(plan.claim, plan_id, "router")
        if not ok:
            return f"plan task {plan_id} not started: {msg}"
    prompt = store.with_templates(role["role"], task)  # approved templates go before the task text; the row keeps the task
    return await _execute(store.create(agent, role["role"], task), agent, role, prompt, plan_id=plan_id)


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
    """Re-open task task_id and every task depending on it, after that task changed approach. Call this (not plan_overview) when a plan task changed and must be redone."""
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
    """Retry a failed task by its task_id (e.g. abc123), from its saved conversation. Call this whenever a task failed and the user asks to retry it."""
    t = store.get(task_id)
    if not t:
        return f"unknown task {task_id}"
    role = resolve_role(t["agent"], CFG)
    return await _execute(task_id, t["agent"], role, t["prompt"], t["messages"] or None)


@mcp.tool()
def list_roles() -> str:
    """List roles with model, docker profile, compose backends and tool allowlist, then teams with their lead and orchestrator."""
    rows = [f"{r['role']}: {r['model']} | {r['profile'] or '-'} | {','.join(r['backends']) or '-'} | "
            f"{','.join(r['tools']) or 'all'}" for r in events.roles_rows(CFG)]
    teams = [f"team {n}: lead {t['lead']} | {t['description']} | roles {', '.join(t['roles'])}"
             for n, t in CFG["teams"].items()]
    return "\n".join(["role: model | docker profile | compose backends | tools", *rows,
                      "", f"orchestrator: {CFG['orchestrator']} (reviews each team lead's result)", *teams])


if __name__ == "__main__":
    mcp.run()
