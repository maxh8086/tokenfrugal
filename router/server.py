"""Claude-facing MCP router. Claude plans and dispatches; local models do the work.

Tools return only capped summaries. Full output stays in the task store (get_detail).
Failure never falls back to cloud: a short capped error summary + task_id goes back for retry/resume.
"""
import asyncio
import atexit
import contextlib
import os
import re
import signal
import sys
import threading
import time

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from . import checker, compose, config, events, gpu_lease, kalamanch_cleanup, loop, ollama_launcher, plan, reconnect, store, studio, ui_launcher, workspace
from .outcomes import Stop, stop_from_legacy
from .config import NATIVE_BACKENDS, OLLAMA_URL, WORKSPACE, load_tf_roles, resolve_role, team_of
from .mcp_client import backend_state
from .model_sync import ensure_models
from .preflight import missing_programs, task_error
from .loop import error_kind, failure_reason, frames_of, leaf, program_missing, role_timeout, run, take_started, take_usage
from .summarize import hard_trim, saved_tokens, summarize

CFG = load_tf_roles()
DIFF_FENCE = re.compile(r"```diff\r?\n(.*?)```", re.S)
STALE_REASON = "router stopped while task was running (no heartbeat)"
HEALTH_EVERY = 10  # seconds between health events; the dashboard marks a router down after ~3 missed beats
RESUME_HINT = {"connection": "retry", "infra": "retry", "timeout": "retry"}  # other reasons: re-scope instead
RESCOPE = "Re-scope the task smaller and dispatch again; resume_task will repeat the same failure."
REQUIRED_ARGS = ("agent", "task", "task_type")
_CLIENT_NAME: str | None = None
_models_ready = False  # set once ensure_models() has succeeded in this process (mediahouse tasks)


def kind_hint(kind: str, started: int, required_tool: str = "") -> str:
    """Short next-step hint for an error_kind; empty for 'error', which keeps the reason-based hint."""
    if kind == "out_of_time":
        if started:
            return f"Timed out after {started} tool calls. Call resume_task once, or split the task."
        return "Timed out before any tool call. Split the task into smaller tasks. Do not resume_task."
    if kind == "no_tool_call":
        if required_tool:
            return f"The model answered without calling a tool. Call {required_tool} with the exact path in the task."
        return "The model answered without calling a tool. Name the exact tool and path in the task."
    if kind == "max_steps":
        return "Step budget used up. Narrow the scope of the task."
    if kind == "infra":
        return "The backend containers did not start. Do not resume_task; check Docker, then dispatch again."
    if kind == "bad_answer":
        return "The answer was empty or placeholder text. Re-scope the task smaller and dispatch again."
    if kind == "env_missing":
        return "A program or module the task needs is missing. Install it or fix the accept command, then dispatch again. Do not resume_task."
    if kind == "workspace_busy":
        return "Another edit task is running in this workspace. Wait for it to finish, then dispatch again."
    return ""


def failure_message(tid: str, role: dict, err: str, reason: str, kind: str = "error", started: int = 0,
                    required_tool: str = "", hint_text: str = "") -> str:
    """The short failure reply Haiku reads: reason class, error_kind, and the next step it should take."""
    hint = hint_text or kind_hint(kind, started, required_tool)
    if not hint:
        if reason in RESUME_HINT:
            hint = f"Call resume_task('{tid}') to retry."
        elif reason == "unknown":
            hint = f"Call resume_task('{tid}') once, then re-scope."
        else:
            hint = RESCOPE
    return f"[{tid}] FAILED ({role['role']}/{role['model']}) reason={reason} error_kind={kind}: {err}. {hint}"


def status_line(status: str, role: str, model: str, calls: int, elapsed: float) -> str:
    """Last line of every dispatch reply: outcome, role, model, tool calls sent and wall time in seconds."""
    return f"status={status} role={role} model={model} calls={calls} elapsed={round(elapsed, 1)}s"


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
    # background: a cold Ollama start can take ~30 s and must not delay the MCP handshake
    ollama_start = asyncio.create_task(asyncio.to_thread(ollama_launcher.ensure))
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
    studio_poller = asyncio.create_task(studio.poll_loop())
    beat = asyncio.create_task(_health_loop())
    try:
        yield
    finally:
        beat.cancel()
        ollama_start.cancel()
        events.emit("health", status="down")
        warm.cancel()
        reconnector.cancel()
        studio_poller.cancel()
        sweeper.cancel()
        ui_launcher.stop()
        compose.release()


class _ClientSeen(Middleware):
    """Reports which MCP client (Claude, Codex, ...) opened this router process, for the dashboard."""

    async def on_initialize(self, context, call_next):
        global _CLIENT_NAME
        # pydantic exposes the MCP field as snake_case `client_info`, not `clientInfo`
        info = getattr(getattr(context.message, "params", None), "client_info", None)
        if info is not None:
            _CLIENT_NAME = info.name
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
    first = True
    while True:
        if first:
            events.emit("health", status="up", missing=missing_programs(), config_warnings=checker.config.CONFIG_WARNINGS)
            first = False
        else:
            events.emit("health", status="up")
        await asyncio.sleep(HEALTH_EVERY)


async def _sweep_loop() -> None:
    """Fail rows left running by gateways that were killed without a restart of this one."""
    while True:
        await asyncio.sleep(store.HEARTBEAT_EVERY * 2)
        await asyncio.to_thread(store.sweep_stale, STALE_REASON)


class CheckFailed(Exception):
    """The checker still failed after its one correction; the message is the failed checks."""

    def __init__(self, message, stop=Stop.CHECKER):
        super().__init__(message)
        self.stop = stop


def diff_block(text: str) -> str | None:
    """The first ```diff block of a reply, without its fences. None when the reply has none."""
    m = DIFF_FENCE.search(text or "")
    return m.group(1) if m else None


def _check(role: dict, task_text: str, detail: str, t0: float, accept=None, ws=None, deadline_at=None, cancel=None) -> dict | None:
    ws = ws or workspace.load_workspace(WORKSPACE)
    parsed = accept if accept is not None else checker.accept_from_task(task_text, "", ws)
    diff = diff_block(detail)
    if parsed.note == "no accept" and diff is None:
        return None
    left = deadline_at - time.monotonic() if deadline_at is not None else role_timeout(role) - (time.monotonic() - t0)
    if not ws.host_accept and parsed.spec:
        parsed = checker.AcceptParse(None, "host accept off")
    skipped = bool(parsed.spec and left < config.MIN_ACCEPT_S)
    if skipped:
        parsed = checker.AcceptParse(None, "out of time")
    verdict = checker.check_deterministic(ws, parsed, diff, timeout=min(config.ACCEPT_TIMEOUT, left), cancel=cancel,
                                          task_files=workspace.legacy_task_files(ws, task_text, limit=3))
    if skipped:
        verdict["passed"] = False
        verdict["stop"] = Stop.OUT_OF_TIME
    return verdict


def _failed_text(verdict: dict) -> str:
    return "; ".join(f"{i['name']}: {i['detail']}" for i in verdict["items"] if not i["passed"])


def _failed_stop(verdict: dict):
    stop = verdict.get("stop")
    if stop in (Stop.OUT_OF_TIME, Stop.ENV_MISSING):
        return stop
    failed = next((item for item in verdict.get("items", []) if not item["passed"]), None)
    return Stop.ACCEPT_FAILED if failed and failed["name"] == "accept" else Stop.CHECKER


def strip_nudges(msgs: list) -> list:
    return [m for m in msgs if not (m.get("role") == "user" and
            m.get("content") in (loop.NUDGE_WRAP, loop.NUDGE_FINAL))]


def _can_write(role: dict) -> bool:
    return bool({"write_file", "edit_file"} & set(role.get("tools") or []))


def _fix_prompt(verdict: dict, role: dict) -> str:
    first = next(i for i in verdict["items"] if not i["passed"])
    return (f"Checks failed: {first['name']}: {first['detail']}. "
            "Fix it with edit_file or write_file. The checks run again after your reply.")


def _changed_set() -> set[str]:
    """Files git reports as changed in the workspace. Empty when git fails, so a broken git never fails a task."""
    try:
        return set(checker.files_changed(WORKSPACE))
    except Exception:  # noqa: BLE001
        return set()


def _report(verdict: dict | None, role: dict) -> str:
    """Checker line appended to the summary; the judgement items go to the client to decide."""
    if verdict is None:
        text = "\nchecks: none (no accept command)"
    else:
        note = verdict.get("accept_note", "")
        note = {"prose": "acceptance line is prose", "no accept": "no accept command"}.get(note, note)
        changed = next((i["detail"] for i in verdict["items"] if i["name"] == "files_changed"), "")
        ran = [i["name"] for i in verdict["items"] if i["name"] != "files_changed"]
        lint_ran = any(x.endswith(".py") for x in changed.split(", "))
        effective = [name for name in ran if name != "lint" or lint_ran]
        if note and not effective:
            state = f"none ({note})"
        else:
            failed = [i for i in verdict["items"] if not i["passed"]]
            state = ("FAILED (" + "; ".join(f"{i['name']}: {i['detail'][:100]}" for i in failed) + ")") if failed else "ok (" + ", ".join(ran) + ")"
            if note:
                state = state[:-1] + f"; accept none: {note})"
        text = ("\ndiff: proposed, not applied" if verdict.get("diff_proposed") else "") + "\nchecks: " + state
    contract = (CFG.get("contracts") or {}).get(role["role"], {})
    judge = [c["text"] for c in contract.get("checklist") or [] if c.get("kind") == "judgement"]
    if judge:
        text += "\nJudge (client): " + " / ".join(judge) + "."
    return text


async def _infra_failed(tid: str, agent: str, role: dict, prompt: str, plan_id: int, name: str, t0: float, reason: str) -> str:
    """B3: a native server's containers were not running or healthy, so the task fails before any model run."""
    missing = reason.startswith("program not found:")
    err = reason if missing else f"infra: backend for {name}: {reason}"
    stop = Stop.ENV_MISSING if missing else Stop.INFRA
    usage = take_usage(tid)
    store.update(tid, status="failed", error=err, error_kind=stop, outcome="failed", model_tag=role["model"], peak_ctx=usage.get("peak"))
    events.emit("task_failed", id=tid, role=role["role"], model=role["model"], error=err, reason="env_missing" if missing else "infra", error_kind=stop,
                saved=0, task=prompt[:80], agent=agent, e2e=round(time.monotonic() - t0, 2), **usage)
    if plan_id:
        await _plan(plan.record_run, plan_id, tid, agent, role["role"], "failed", "", err)
        await _plan(plan.set_status, plan_id, "blocked", "router", err)
    return (failure_message(tid, role, err, "env_missing" if missing else "infra", stop, 0, role.get("required_tool") or "") + "\n"
            + "checks: none (not run)\n"
            + status_line("failed", role["role"], role["model"], 0, time.monotonic() - t0))


async def _execute(tid: str, agent: str, role: dict, prompt: str, messages=None, plan_id: int = 0,
                   accept=None, task_text: str | None = None, checks: bool = True, correction: bool = True) -> str:
    t0 = time.monotonic()
    ws = workspace.load_workspace(WORKSPACE)
    task_text = task_text if task_text is not None else (store.get(tid).get("prompt") or prompt)
    allowed = set()
    for name in role.get("native") or []:  # B3: a native server's containers must be up before any model call
        if name in NATIVE_BACKENDS:
            backend_reason = await backend_state(name)
            if backend_reason:
                return await _infra_failed(tid, agent, role, prompt, plan_id, name, t0, backend_reason)
    row = store.get(tid)
    store.update(tid, status="running", attempts=(row["attempts"] or 0) + 1)
    events.emit("task_start", id=tid, agent=agent, role=role["role"], model=role["model"],
                max_steps=role["max_steps"], attempt=(row["attempts"] or 0) + 1, prompt=prompt[:300],
                tools=role.get("tools") or [], skills=role.get("skills") or [])
    base = len(messages or [])  # messages from an earlier run were already counted
    before = await asyncio.to_thread(_changed_set)  # C2: the workspace's changed files before the run
    beat = asyncio.create_task(_heartbeat(tid))
    calls = 0  # tool calls sent over every run of this task (a checker correction is a second run)
    last_msgs = messages
    rt = role_timeout(role)
    deadline_s = config.deadline(role, rt)
    accept_cancel = threading.Event()
    cm = None
    try:
        async with asyncio.timeout(deadline_s) as cm:
            try:
                gpu_lease.guard_ollama(OLLAMA_URL)  # a held GPU lease refuses the task before any model or backend work
                guard = lambda p: workspace.denied(workspace.to_rel(ws, p), allowed, ws)
                budget = loop.Budget(rt)
                detail, msgs = await run(agent, role, prompt, messages, tid, guard=guard, budget=budget)
                last_msgs = msgs
                calls += take_started(tid)
                task_accept = accept if accept is not None else checker.accept_from_task(task_text, "", ws)
                if checks and not ws.host_accept and task_accept.spec:
                    events.emit("checks_skipped", id=tid, reason="host accept off")
                verdict = None
                if checks:
                    with budget.pause():
                        verdict = await asyncio.to_thread(_check, role, task_text, detail, t0, accept, ws, deadline_at=t0 + deadline_s, cancel=accept_cancel)
                if verdict is not None:
                    verdict["diff_proposed"] = bool(diff_block(detail) is not None and not _can_write(role))
                if correction and verdict and not verdict["passed"]:  # one correction, continuing the same message history
                    if verdict.get("accept_note") == "out of time":
                        failed = _failed_text(verdict)
                        err = f"{failed}; accept: out of time" if failed else "accept: out of time"
                        raise CheckFailed(err, Stop.OUT_OF_TIME)
                    if verdict.get("stop") == Stop.ENV_MISSING:
                        raise CheckFailed(_failed_text(verdict), verdict["stop"])
                    if not _can_write(role):
                        raise CheckFailed(_failed_text(verdict), _failed_stop(verdict))
                    left = config.model_budget(role, rt) - budget.spent()
                    if left < config.CORRECTION_FLOOR_S:
                        raise CheckFailed(_failed_text(verdict) + "; no time for a correction run", Stop.OUT_OF_TIME)
                    correction_budget = loop.Budget(left)
                    fix = _fix_prompt(verdict, role)
                    detail, msgs = await run(agent, role, "", strip_nudges(msgs) + [{"role": "user", "content": fix}], tid, guard=guard, budget=correction_budget)
                    last_msgs = msgs
                    budget = correction_budget
                    calls += take_started(tid)
                    with budget.pause():
                        verdict = await asyncio.to_thread(_check, role, task_text, detail, t0, accept, ws, deadline_at=t0 + deadline_s, cancel=accept_cancel)
                    if verdict is not None:
                        verdict["diff_proposed"] = bool(diff_block(detail) is not None and not _can_write(role))
                    if verdict and not verdict["passed"]:
                        if verdict.get("accept_note") == "out of time":
                            failed = _failed_text(verdict)
                            err = f"{failed}; accept: out of time" if failed else "accept: out of time"
                            raise CheckFailed(err, Stop.OUT_OF_TIME)
                        if verdict.get("stop") in (Stop.ENV_MISSING, Stop.OUT_OF_TIME):
                            raise CheckFailed(_failed_text(verdict), verdict["stop"])
                        raise CheckFailed(_failed_text(verdict), _failed_stop(verdict))
                after = await asyncio.to_thread(_changed_set)
                base_summary = summarize(role["model"], detail, prompt)
                report = _report(verdict, role)
                summary = base_summary + report
                usage = take_usage(tid)
                store.update(tid, status="done", summary=summary, detail=detail, messages=msgs, error=None, error_kind=None, model_tag=role["model"], peak_ctx=usage.get("peak"), outcome="done")
                events.emit("task_done", id=tid, role=role["role"], model=role["model"], summary=summary[:400], saved=saved_tokens(msgs[base:], summary),
                            task=prompt[:80], agent=agent, e2e=round(time.monotonic() - t0, 2), error_kind=None, **usage)
            except asyncio.CancelledError as exc:
                accept_cancel.set()
                err = f"task timed out after {deadline_s:g}s" if cm.expired() else "task cancelled"
                usage = take_usage(tid)
                store.update(tid, status="failed", error=err, error_kind=Stop.OUT_OF_TIME,
                             messages=getattr(leaf(exc), "msgs", None) or last_msgs,
                             outcome="failed", model_tag=role["model"], peak_ctx=usage.get("peak"))
                events.emit("task_failed", id=tid, role=role["role"], model=role["model"], error=err,
                            reason="timeout", error_kind=Stop.OUT_OF_TIME, saved=0, task=prompt[:80],
                            agent=agent, e2e=round(time.monotonic() - t0, 2), **usage)
                raise
        if plan_id:
            await _plan(plan.record_run, plan_id, tid, agent, role["role"], "done", summary)
            ok, msg = await _plan(plan.done, plan_id, tid, "router run", "router")
            if ok:
                await _plan(plan.checkpoint)
            summary += "" if ok else f" (plan: {msg})"
        return (f"[{tid}] {base_summary}\n{checker.manifest(before, after)}{report}\n"
                + status_line("done", role["role"], role["model"], calls, time.monotonic() - t0))
    except Exception as e:  # noqa: BLE001
        if isinstance(e, TimeoutError) and cm is not None and cm.expired():
            started = calls + take_started(tid)
            err = f"task timed out after {deadline_s:g}s"
            if plan_id:
                await _plan(plan.record_run, plan_id, tid, agent, role["role"], "failed", "", err)
                await _plan(plan.set_status, plan_id, "blocked", "router", err)
            return (failure_message(tid, role, err, "timeout", Stop.OUT_OF_TIME, started,
                                    role.get("required_tool") or "") + "\n"
                    + "checks: none (out of time)"
                    + "\n" + status_line("failed", role["role"], role["model"], started, time.monotonic() - t0))
        orig = e
        frames = frames_of(orig) if not isinstance(e, CheckFailed) else []
        if isinstance(e, CheckFailed):
            full = str(e)
            reason = "env_missing" if e.stop == Stop.ENV_MISSING else ("timeout" if e.stop == Stop.OUT_OF_TIME else "checker")
            kind = e.stop
        else:
            e = leaf(e)
            full = program_missing(orig) or f"{type(e).__name__}: {e}"
            reason = failure_reason(full)
            kind = error_kind(full)
        started = calls + take_started(tid)
        gpu = isinstance(e, gpu_lease.GpuBusy)  # its message is short and carries the holder: not trimmed
        if gpu:
            reason = "gpu-busy"
        kind = stop_from_legacy(reason, kind)
        usage = take_usage(tid)
        err = full if gpu else hard_trim(full, 300 if isinstance(e, CheckFailed) else 120)
        failure_msgs = getattr(e, "msgs", None) or getattr(orig, "msgs", None) or last_msgs
        store.update(tid, status="failed", error=err, error_kind=kind, messages=failure_msgs,
                     outcome="failed", model_tag=role["model"], peak_ctx=usage.get("peak"))
        extra = {"frames": frames} if kind in (Stop.ERROR, Stop.ENV_MISSING) else {}
        events.emit("task_failed", id=tid, role=role["role"], model=role["model"], error=err, reason=reason, error_kind=kind, **extra,
                    saved=saved_tokens((getattr(e, "msgs", None) or [])[base:], err),
                    task=prompt[:80], agent=agent, e2e=round(time.monotonic() - t0, 2), **usage)
        if plan_id:
            await _plan(plan.record_run, plan_id, tid, agent, role["role"], "failed", "", err)
            await _plan(plan.set_status, plan_id, "blocked", "router", err)
        return (failure_message(tid, role, err, reason, kind, started, role.get("required_tool") or "",
                               hint_text=e.hint if gpu else "") + "\n"
                + (_report(verdict, role).lstrip("\n") if isinstance(e, CheckFailed) else "checks: none (not run)")
                + "\n" + status_line("failed", role["role"], role["model"], started, time.monotonic() - t0))
    finally:
        beat.cancel()


@mcp.tool()
async def dispatch_task(agent: str = "", task: str = "", task_type: str = "", plan_id: int = 0, role: str = "",
                        accept: str = "") -> str:
    """Run a task on a local tf-role (agency-agents slug, e.g. 'engineering-code-reviewer').
    `role` is an alias for `agent`; when both are given, `agent` wins.
    `task_type` is required: the kind of task (e.g. 'add test', 'fix bug', 'explain code'). It picks which approved templates apply.
    `accept`, when given, is a command (e.g. 'python -m unittest') that replaces the task's Accept: line; it runs without a shell.
    Optional plan_id links it to a plan task (claimed first, marked done/blocked after).
    Returns a summary of up to 5000 tokens and a task_id."""
    agent = agent or role
    required = dict(zip(REQUIRED_ARGS, (agent, task, task_type)))
    if not required["agent"]:
        return "give agent (or role) and task"
    if not required["task"].strip():
        return "task is empty: send the task text"
    if not required["task_type"].strip():
        return "give task_type: the kind of task, e.g. 'add test' or 'explain code' (see list_roles for templates)"
    parsed_accept = checker.parse_accept(accept, "argument", workspace.load_workspace(WORKSPACE)) if accept else None
    if parsed_accept and parsed_accept.note.startswith("refused:"):
        return parsed_accept.note
    err = task_error(agent, task, CFG, WORKSPACE)
    if err:
        events.emit("task_refused", agent=agent, reason=err)  # refusal before any model time; logged to events.jsonl
        return err
    role = resolve_role(agent, CFG)
    if role.get("held"):  # held roles are listed for the owner but never run; refused before any task row exists
        events.emit("task_refused", agent=agent, reason="held")
        return f"role '{role['role']}' is held: {role['held']}"
    global _models_ready
    if not _models_ready and team_of(role["role"], CFG) == "mediahouse":
        err = await asyncio.to_thread(ensure_models)  # a first pull can take hours; keep the event loop free
        if err:
            return err
        _models_ready = True
    if plan_id:
        ok, msg = await _plan(plan.claim, plan_id, "router")
        if not ok:
            return f"plan task {plan_id} not started: {msg}"
    kalamanch_cleanup.maybe_run()  # at most once a day, in a background thread; never blocks or fails the dispatch
    task_type = task_type.strip()
    prompt = store.with_templates(role["role"], task, task_type)  # approved templates go before the task text; the row keeps the task
    kind = "edit" if task_type.lower() in {"add test", "fix bug", "add feature", "refactor", "edit", "write"} else "analyze"
    effective_accept = parsed_accept if accept else checker.accept_from_task(task, "", workspace.load_workspace(WORKSPACE))
    contract = {"accept": effective_accept.spec.to_json() if effective_accept and effective_accept.spec else None, "packet": None}
    tid = store.create(agent, role["role"], task, client=_CLIENT_NAME, task_type=task_type, prompt_sent=prompt,
                       contract_json=contract, workspace=os.path.normcase(os.path.realpath(WORKSPACE)),
                       plan_id=plan_id or 0, kind=kind)
    return await _execute(tid, agent, role, prompt, plan_id=plan_id,
                          accept=parsed_accept, task_text=task)


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
    if not t:
        return f"unknown task {task_id}"
    if t["status"] != "done":
        return f"task {task_id} must be done before asking a follow-up (status: {t['status']})"
    if not t["messages"]:
        return f"empty task {task_id}"
    role = resolve_role(t["agent"], CFG)
    msgs = t["messages"] + [{"role": "user", "content": question}]
    child_id = store.create(t["agent"], t["role"], question, client=t.get("client"), task_type=t.get("task_type"),
                            workspace=t.get("workspace"), kind="analyze", parent_id=task_id)
    return await _execute(child_id, t["agent"], role, question, msgs, task_text=question, checks=False, correction=False)


@mcp.tool()
def get_detail(task_id: str, max_chars: int = 4000) -> str:
    """Fetch the full stored output of a task (use sparingly; costs Claude tokens)."""
    t = store.get(task_id)
    if not t:
        return f"unknown task {task_id}"
    if t["detail"]:
        head = t["detail"]
    elif t["messages"]:
        lines = ([t["error"]] if t["error"] else []) + [f"{m.get('role', '')}: {m.get('content') or ''}" for m in t["messages"]]
        head = "\n".join(lines)
    else:
        head = t["error"] or "no output"
    head = head[:max_chars]
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
    if e.get("frames"):
        return f"{kind} {e.get('error') or e.get('summary') or ''} frames: {'; '.join(e['frames'])}"[:400]
    return f"{kind} {e.get('error') or e.get('summary') or ''}"[:200]


@mcp.tool()
async def resume_task(task_id: str) -> str:
    """Retry a failed task by its task_id (e.g. abc123), from its saved conversation. Call this whenever a task failed and the user asks to retry it."""
    t = store.get(task_id)
    if not t:
        return f"unknown task {task_id}"
    if t["status"] == "running":
        return f"task {task_id} is already running"
    current_workspace = os.path.normcase(os.path.realpath(WORKSPACE))
    stored_workspace = t.get("workspace") or current_workspace
    if stored_workspace != current_workspace:
        return f"task workspace mismatch: stored {stored_workspace}; current {current_workspace}"
    role = resolve_role(t["agent"], CFG)
    prompt = t.get("prompt_sent") or t["prompt"]
    contract = t.get("contract_json")
    if contract is None:
        accept = checker.accept_from_task(t["prompt"], "", workspace.load_workspace(WORKSPACE))
    else:
        accept_json = contract.get("accept")
        if accept_json:
            accept = checker.AcceptParse(checker.AcceptSpec.from_json(accept_json))
        else:
            parsed = checker.accept_from_task(t["prompt"], "", workspace.load_workspace(WORKSPACE))
            accept = checker.AcceptParse(None, parsed.note if not parsed.spec else "no accept")
    options = {"checks": False, "correction": False} if t.get("parent_id") else {}
    return await _execute(task_id, t["agent"], role, prompt, t["messages"] or None,
                          plan_id=t.get("plan_id") or 0, accept=accept, task_text=t["prompt"], **options)


@mcp.tool()
async def studio_run(action: str = "", slug: str = "", topic: str = "", sources: str = "", feed_url: str = "") -> str:
    """Studio run backend. action: 'collect' (sources: comma list of reddit-hn, rss, youtube; default all three),
    'pipeline' (slug + topic: the seven content stages), 'save_feed' (feed_url: adds an RSS feed to the saved list, no run),
    'store' (writes today's collector files to Neo4j once each), 'cancel' (stops the active run at its next stage boundary). One run at a time: a start is refused while one is active.
    Returns a one-line message; use studio_status for state."""
    return await asyncio.to_thread(studio.start, action, slug, topic, sources, feed_url)


@mcp.tool()
def studio_status() -> str:
    """State of the Studio run backend: active run and stage, recent runs with their end state, waiting requests,
    estimated YouTube quota used today (Pacific date), and any missing secret names (never values)."""
    return studio.format_status(studio.status())


@mcp.tool()
def list_roles() -> str:
    """List roles with model, docker profile, compose backends and tool allowlist, then teams with their lead and orchestrator."""
    rows = [f"{r['role']}: {r['model']} | {r['profile'] or '-'} | {','.join(r['backends']) or '-'} | "
            f"{','.join(r['tools']) or 'all'}" for r in events.roles_rows(CFG)]
    teams = [f"team {n}: lead {t['lead']} | {t['description']} | roles {', '.join(t['roles'])}"
             for n, t in CFG["teams"].items()]
    tpl = [f"  #{t['id']} {t['role']}: {t['title']} | task_type {t['task_type'] or '-'} | uses {t['uses']}"
           for t in store.list_templates()]
    return "\n".join(["role: model | docker profile | compose backends | tools", *rows,
                      "", f"orchestrator: {CFG['orchestrator']} (reviews each team lead's result)", *teams,
                      "", "approved templates (applied only when a dispatch_task task_type and wording match):",
                      *(tpl or ["  none"])])


def main():
    mcp.run()


if __name__ == "__main__":
    main()
