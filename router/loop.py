"""Tool-calling agent loop: <=2 tool calls per step, anti-slop checks, bounded steps."""
import asyncio
import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace

from openai import OpenAI

from . import events, mcp_reap
from .config import (LLM_API_KEY, LLM_TEMPERATURE, LLM_TIMEOUT, OLLAMA_URL, SYNAPTREE_PROJECT, TASK_TIMEOUT, THINK_LEVEL,
                     TOOL_TIMEOUT, TOOLS_PER_STEP, TOOL_MODE, WORKSPACE)
from .compose import backends
from .lint import check_python
from .mcp_client import open_role, result_text, to_openai_tools

_NO_TEMP: set[str] = set()  # models whose endpoint refuses `temperature`
_NO_THINK: set[str] = set()  # models that have no thinking and refuse the `think` field
_LOCAL = any(h in OLLAMA_URL for h in ("localhost", "127.0.0.1", "[::1]", "host.docker.internal"))
# hosted endpoints rate-limit (429/529): let the SDK back off and honour retry-after; local stays at 0
_client = OpenAI(base_url=OLLAMA_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT, max_retries=0 if _LOCAL else 4)
DONE: dict[str, dict] = {}  # last taken totals per task id, read by the benchmark
USAGE: dict[str, dict] = {}  # per task id: model calls and tokens, taken by the router when the task ends


def _count(tid: str, r, msgs: list, m, secs: float) -> None:
    """Add one model call to the task's totals. Uses the backend's usage when sent, else chars / 4. secs is the call's wall time."""
    u = getattr(r, "usage", None)
    inp = getattr(u, "prompt_tokens", None)
    out = getattr(u, "completion_tokens", None)
    if inp is None:
        inp = sum(len(str(x.get("content") or "")) for x in msgs) // 4
    if out is None:
        out = len(m.content or "") // 4
    a = USAGE.setdefault(tid, {"calls": 0, "input": 0, "output": 0, "secs": 0.0})
    a["calls"] += 1
    a["input"] += int(inp)
    a["peak"] = max(a.get("peak", 0), int(inp))
    a["output"] += int(out)
    a["secs"] += secs


def take_usage(tid: str) -> dict:
    """Totals for one task id; cleared so a resumed run starts its own count."""
    u = USAGE.pop(tid, {"calls": 0, "input": 0, "output": 0, "secs": 0.0, "peak": 0})
    DONE[tid] = u
    return u


STARTED: dict[str, int] = {}  # per task id: tool calls sent to an MCP server in the current run; reset by run()


def take_started(tid: str) -> int:
    """Tool calls the current run actually sent to an MCP server; cleared when the task ends."""
    return STARTED.pop(tid, 0)
SYSTEM = ("You are a focused {role} agent ({agent}). Use at most {n} tool calls per step. "
          "Work only inside the workspace, which is mounted at /workspace: always use absolute paths like /workspace/README.md. Be terse. When done, reply with the final result "
          "(findings, files changed, verdict) and no tool call. Never invent file contents or paths: you MUST call a tool to read real data before answering, and say 'not found' if a tool returns nothing.")
GRAPH_RULE = (" Code graph: search_graph returns repo-relative file_path values. The file on disk is "
              "/workspace/{project}/<file_path>; use that path with read_file, or get_code_snippet for one symbol. "
              "Never run search_files on /workspace itself; it walks every repo and times out. "
              "Call search_graph with only `query` (a symbol name); do not set `label` or other filters unless you know the value.")
BROWSER_RULE = (" Browser: call navigate_page with `url` first. take_snapshot and take_screenshot return their result inline; "
                "never pass `filePath` (writes outside the allowed roots are denied). The first page has pageId 1 (a number). "
                "Only call the listed tools.")
TEXT_TOOLS = (chr(10) * 2 + "Tools are NOT available through an API. To use one, reply with ONLY one JSON object per call, "
              'for example {{"name": "read_file", "arguments": {{"path": "/workspace/README.md"}}}}, and nothing else. '
              'One-shot example of write_file (escape newlines in content as \\n, never put a raw line break inside the JSON string): '
              '{{"name": "write_file", "arguments": {{"path": "/workspace/app/util.py", "content": "def add(a, b):\\n    return a + b\\n"}}}}. '
              "Write the real code in content, never a placeholder such as '...' or 'rest of file'. "
              "To change an existing file, prefer edit_file over rewriting it with write_file. "
              "Results come back in the next message. Available tools:" + chr(10) + "{tools}")
SLOP = re.compile(r"(as an ai|i.m sorry, but i.m not able|i can.t assist|i cannot access|lorem ipsum|TODO: implement|placeholder|\.\.\. ?rest of)", re.I)


class LoopError(Exception):
    pass


def leaf(e: BaseException) -> BaseException:
    """Unwrap (nested) ExceptionGroups from anyio task groups to the first real error."""
    while getattr(e, "exceptions", None):
        e = e.exceptions[0]
    return e


def slop_check(text: str) -> str | None:
    if not text.strip():
        return "empty answer"
    if re.match(r'''\s*\{\s*["']name["']\s*:''', re.sub(r"</?tool_call>|```(?:json)?", "", text).lstrip()):
        return "you wrote a tool call as text; use the tool-calling interface or give the final answer"
    if SLOP.search(text):
        return "answer contains filler/placeholder text; redo with concrete content"
    return None


def coerce_args(args: dict, schema: dict) -> dict:
    """Small models send numbers/booleans as strings; convert to the types the tool schema declares."""
    props = (schema or {}).get("properties", {})
    out = dict(args)
    for k, v in args.items():
        t = (props.get(k) or {}).get("type")
        if not isinstance(v, str):
            continue
        try:
            if t == "integer":
                out[k] = int(v)
            elif t == "number":
                out[k] = float(v)
            elif t == "boolean" and v.lower() in ("true", "false"):
                out[k] = v.lower() == "true"
            elif t == "array":  # live failure: fields='["number", ...]' sent as text; the server wants a list
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    out[k] = parsed
        except ValueError:  # json.JSONDecodeError is a ValueError
            pass
    return out


JSON_TYPES = {  # schema type -> Python check; bool is excluded from number/integer below
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def arg_error(args: dict, schema: dict) -> str:
    """Reject calls the schema cannot accept before they reach the MCP server: unknown, missing or mistyped arguments."""
    props = (schema or {}).get("properties")
    if props is None:
        return ""
    unknown = sorted(k for k in args if k not in props)
    missing = sorted(k for k in (schema or {}).get("required", []) if k not in args)
    # top-level "type" only; anyOf/oneOf/$ref and unknown type names are not checked
    mistyped = sorted(
        f"{k} must be {props[k]['type']}, got {type(v).__name__}"
        for k, v in args.items()
        if k in props and isinstance(props[k], dict) and props[k].get("type") in JSON_TYPES
        and not JSON_TYPES[props[k]["type"]](v)
    )
    if not unknown and not missing and not mistyped:
        return ""
    parts = []
    if unknown:
        parts.append(f"unknown argument(s) {', '.join(unknown)}")
    if missing:
        parts.append(f"missing required argument(s) {', '.join(missing)}")
    if mistyped:
        parts.append(f"wrong type: {'; '.join(mistyped)}")
    return f"tool error: {'; '.join(parts)}. Valid arguments: {', '.join(sorted(props)) or 'none'}. Call again with only those."


def lint_written(path: str) -> str:
    """Feedback line for a just-written .py file so the model fixes missing imports/syntax itself."""
    if not path.endswith(".py") or not path.startswith("/workspace/"):
        return ""
    try:
        src = (Path(WORKSPACE) / path[len("/workspace/"):]).read_text(encoding="utf-8")
    except OSError:
        return ""
    problem = check_python(src)
    return f"\nLINT: {problem}. Fix it with edit_file or write_file." if problem else ""


def _repair(t: str, i: int, dec) -> tuple:
    """Small models often drop the last closing brace/bracket of a tool call; try adding up to 3."""
    for tail in ("}", "}}", "]}", "}]}", "}}}"):
        try:
            return dec.raw_decode(t[i:] + tail)[0], len(t)
        except ValueError:
            continue
    return None, i


FN_BLOCK = re.compile(r"<function=([\w.-]+)>(.*?)</function>", re.S)  # <function=NAME> ... </function>
PARAM = re.compile(r"<parameter=([\w.-]+)>(.*?)</parameter>", re.S)
PATH = re.compile(r"/workspace/[\w.\-/]+|(?<![\w.])/[\w.\-]+(?:/[\w.\-]+)*\.\w+")  # absolute paths in a task


def parse_text_calls(text: str, names: set) -> list:
    """Recover tool calls a small model wrote as text: <function=NAME><parameter=KEY>VALUE</parameter> blocks,
    or JSON, both optionally inside <tool_call>/code fences."""
    body = text or ""
    calls = []
    for fn, inner in FN_BLOCK.findall(body):
        if fn in names:
            args = {k: v.strip() for k, v in PARAM.findall(inner)}
            calls.append(SimpleNamespace(id=f"txt_{len(calls)}", function=SimpleNamespace(name=fn, arguments=json.dumps(args))))
    t = re.sub(r"</?tool_call>|```(?:json)?", "", FN_BLOCK.sub("", body)).strip()
    dec = json.JSONDecoder(strict=False)  # small models emit raw newlines inside "content" strings
    i = 0
    while (i := t.find("{", i)) != -1:
        try:
            o, j = dec.raw_decode(t, i)
        except ValueError:
            o, j = _repair(t, i, dec)
            if o is None:
                i += 1
                continue
        i = j
        if isinstance(o, dict) and o.get("name") in names:
            a = o.get("arguments", o.get("parameters", {}))
            calls.append(SimpleNamespace(id=f"txt_{len(calls)}", function=SimpleNamespace(
                name=o["name"], arguments=a if isinstance(a, str) else json.dumps(a))))
    return calls


NL = chr(10)


def text_tool_prompt(tools: list) -> str:
    lines = []
    for t in tools:
        f = t["function"]
        props = ", ".join(f"{k}: {(v or {}).get('type', 'any')}" for k, v in (f["parameters"].get("properties") or {}).items())
        lines.append(f"- {f['name']}({props}): {f.get('description') or ''}")
    return TEXT_TOOLS.format(tools=NL.join(lines))


def text_view(msgs: list) -> list:
    """Messages for a model without native tool calling: tool calls become JSON text, tool results become user turns."""
    out = []
    for x in msgs:
        if x.get("role") == "tool":
            out.append({"role": "user", "content": f"TOOL RESULT:{NL}{x['content']}"})
        elif x.get("tool_calls"):
            out.append({"role": "assistant", "content": NL.join(json.dumps(
                {"name": c["function"]["name"], "arguments": json.loads(c["function"]["arguments"] or "{}")}) for c in x["tool_calls"])})
        else:
            out.append(x)
    return out


def role_timeout(role: dict) -> float:
    """Whole-task limit in seconds: the role's frozen timeout_s when set, else the global TASK_TIMEOUT."""
    return float(role.get("timeout_s") or TASK_TIMEOUT)


def first_call_hint(task: str, names: set, required: str = "") -> str | None:
    """Corrective message for a model that answered without reading anything: name the role's required tool (else read_file), and the task's path if it has one."""
    m = PATH.search(task or "")
    path = m.group(0).rstrip(".,;:)'\"") if m else ""
    if required and required in names:
        return f"You have not called {required} yet. Call {required}" + (f" with path={path}" if path else "") + " now, then answer from its result."
    if "read_file" not in names:
        return None
    if path:
        return f"You have not read anything yet. Call read_file with path={path} now, then answer from its result."
    return "You have not read anything yet. Call read_file on the file you need now, then answer from its result."


def named_paths(task: str | None, limit: int = 2) -> list[str]:
    """Absolute paths the task names, in order, without repeats, capped at limit: the router reads them before the model starts."""
    seen: list[str] = []
    for m in PATH.finditer(task or ""):
        p = m.group(0).rstrip(".,;:)'\"")
        if p and p not in seen:
            seen.append(p)
            if len(seen) >= limit:
                break
    return seen


def preread_messages(path: str, content: str, idx: int) -> list[dict]:
    """A synthetic read_file call and its result, shaped like a call the model made itself."""
    cid = f"preread-{idx}"
    return [
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": cid, "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"path": path})}}]},
        {"role": "tool", "tool_call_id": cid, "content": content},
    ]


def wrapup_due(step: int, max_steps: int, n_ok_results: int) -> bool:
    """True from 70% of the step budget (ceil) until the last step, once some tool call has succeeded."""
    return n_ok_results > 0 and step >= (7 * max_steps + 9) // 10 and step < max_steps  # (7m+9)//10 == ceil(0.7m)


def infra_error(exc: BaseException) -> bool:
    """Backend/runner failures worth one retry (HTTP 500, runner crashed), as opposed to request errors."""
    s = str(exc).lower()
    return bool(re.search(r"\b500\b", s) or "internalservererror" in s or "llama runner" in s
                or ("runner" in s and ("terminated" in s or "stopped" in s)))


def failure_reason(text: str) -> str:
    """Coarse class of a task failure, so the orchestrator knows whether to resume or re-scope."""
    s = (text or "").lower()
    if s.startswith("infra:") or re.search(r"\b500\b", s) or any(
            m in s for m in ("internalservererror", "llama runner", "runner terminated", "runner stopped")):
        return "infra"
    if re.search(r"connection closed|is not running|broken ?pipe", s):
        return "connection"
    if "timed out" in s or "timeouterror" in s or "apitimeouterror" in s:
        return "timeout"
    if "without calling any tool" in s or re.search(r"you have not (called|read)", s):
        return "no-tool-call"
    if "tool call" in s and ("malformed" in s or "could not be run" in s or "wrote a tool call" in s):
        return "malformed-tool-call"
    if "no final answer" in s:
        return "out-of-steps"
    if "empty answer" in s or "filler/placeholder" in s:
        return "bad-answer"
    return "unknown"


def error_kind(text: str) -> str:
    """Failure kind stored as error_kind: step_timeout (role time limit hit), request_timeout (one model request timed out),
    no_tool_call, max_steps, bad_answer (empty or placeholder reply), infra (backend or runner failure), or error for
    everything else (connection, ...). Built on failure_reason."""
    reason = failure_reason(text)
    if reason == "infra":
        return "infra"
    if reason == "timeout":
        return "step_timeout" if "task timed out" in (text or "").lower() else "request_timeout"
    if reason == "no-tool-call":
        return "no_tool_call"
    if reason == "out-of-steps":
        return "max_steps"
    if reason == "bad-answer":
        return "bad_answer"
    return "error"


def think_extra(role: dict) -> dict:
    """Send the thinking level (TOKENFRUGAL_THINK) to models that accept it; empty when off or refused."""
    if THINK_LEVEL in ("", "off") or role["model"] in _NO_THINK:
        return {}
    return {"extra_body": {"think": THINK_LEVEL}}


async def run(agent: str, role: dict, prompt: str, messages: list | None = None,
              tid: str = "") -> tuple[str, list]:
    system = SYSTEM.format(role=role["role"], agent=agent, n=TOOLS_PER_STEP)
    if "synaptree" in (role.get("native") or []):
        system += GRAPH_RULE.format(project=SYNAPTREE_PROJECT)
    if role["role"] == "browser":
        system += BROWSER_RULE
    for name in [] if os.environ.get("TOKENFRUGAL_NO_SKILLS") == "1" else role.get("skills") or []:
        path = Path(__file__).parent / "skills" / name / "SKILL.md"
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8").split("---", 2)[-1].strip()
        system += f"\n\nSkill {name}:\n{body}"
    msgs = messages or [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    STARTED[tid] = 0
    limit = role_timeout(role)
    try:
        return await asyncio.wait_for(_run(agent, role, msgs, tid), limit or None)
    except asyncio.TimeoutError:
        e = LoopError(f"task timed out after {limit:g}s")
        e.msgs = msgs
        raise e
    except BaseException as e:
        leaf(e).msgs = msgs  # failed runs still did local work; the router counts it as saved
        raise


async def _run(agent: str, role: dict, msgs: list, tid: str) -> tuple[str, list]:
    async with backends(role.get("compose", []), role.get("keep_alive", False)), \
            open_role(role.get("profile"), role.get("native"), role.get("params")) as sess:
        tools = to_openai_tools((await sess.list_tools()).tools, role["tools"])
        if role["tools"] and not tools:  # the MCP server did not start: a harness fault, not a model answer
            raise LoopError(f"infra: no tools listed for {agent} (profile {role.get('profile')} failed to start)")
        names = {t["function"]["name"] for t in tools}
        text_mode = bool(tools) and (role.get("tool_mode") or TOOL_MODE) == "text"
        if text_mode and msgs and msgs[0].get("role") == "system" and "Tools are NOT available" not in msgs[0]["content"]:
            msgs[0]["content"] += text_tool_prompt(tools)
        schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
        ok_calls = sum(1 for x in msgs if x.get("role") == "tool" and not str(x.get("content", "")).startswith("tool error"))
        fail_retries = 0
        slop_retries = 0
        used_tools = any(m.get("role") == "tool" for m in msgs)
        task_text = next((x.get("content") or "" for x in msgs if x.get("role") == "user"), "")
        # 2B: read the paths the task names before the model starts, so a small model never has to find the first read itself
        if "read_file" in names and not used_tools and not text_mode and role["role"] != "browser" \
                and os.environ.get("TOKENFRUGAL_NO_PREREAD") != "1":
            for i, p in enumerate(named_paths(task_text), 1):
                try:
                    STARTED[tid] = STARTED.get(tid, 0) + 1
                    res = await asyncio.wait_for(sess.call_tool("read_file", {"path": p}), TOOL_TIMEOUT or None)
                    out = result_text(res)
                except Exception:  # unreadable here: skip it silently, the model can still read it itself
                    continue
                if (hasattr(res, "is_error") and res.is_error) or (not hasattr(res, "is_error") and getattr(res, "isError", False)) \
                        or not out.strip() or out.startswith(("Error:", "tool error", "Input validation error")):
                    continue
                events.emit("tool", id=tid, name="read_file", args="preread " + p[:150])
                msgs += preread_messages(p, out, i)
                ok_calls += 1
                used_tools = True
        hinted = False  # the first "answered without reading" retry names read_file (2A)
        hint_retries = 0  # first-call hint retries: their own budget of 2, separate from slop_retries
        wrapped = False  # the wrap-up nudge is sent once
        for step in range(1, role["max_steps"] + 1):
            events.emit("step", id=tid, n=step)
            if not wrapped and wrapup_due(step, role["max_steps"], ok_calls):
                wrapped = True
                msgs.append({"role": "user", "content": "Stop calling tools. Give the final answer now."})
            # the last step is reserved for the answer once real results exist: no tools, so the model cannot run out of steps
            force_answer = bool(ok_calls) and step == role["max_steps"]
            if force_answer:
                msgs.append({"role": "user", "content": "Step limit reached. Do not call any more tools. "
                                                        "Answer now using only the tool results above."})
            use_tools = bool(tools) and not text_mode and not force_answer
            t0 = time.monotonic()
            kw = {"model": role["model"], "messages": text_view(msgs) if text_mode else msgs, **think_extra(role)}
            if use_tools and tools:
                kw["tools"] = tools
                if not used_tools:
                    kw["tool_choice"] = "required"
            if role["model"] not in _NO_TEMP:
                kw["temperature"] = LLM_TEMPERATURE
            infra_retried = False  # one retry after a 3s pause for runner/HTTP 500 failures
            for _attempt in range(3):
                try:
                    r = await asyncio.to_thread(_client.chat.completions.create, **kw)  # off the event loop
                    break
                except Exception as e:
                    s = str(e)
                    if "temperature" in kw and "temperature" in s:
                        _NO_TEMP.add(role["model"])  # endpoint rejects sampling params for this model
                        del kw["temperature"]
                    elif "tool_choice" in kw and "tool_choice" in s:
                        del kw["tool_choice"]  # model/endpoint cannot force a tool call
                    elif "extra_body" in kw and "think" in s.lower() and "400" in s:
                        _NO_THINK.add(role["model"])  # model has no thinking: send it without the flag from now on
                        del kw["extra_body"]
                    elif infra_error(e):
                        if infra_retried:
                            raise LoopError(f"infra: {s[:300]}") from e
                        infra_retried = True
                        await asyncio.sleep(3)
                    else:
                        raise
            m = r.choices[0].message
            _count(tid, r, msgs, m, time.monotonic() - t0)
            thought = (getattr(m, "reasoning_content", None) or getattr(m, "reasoning", None) or m.content or "").strip()
            if thought:
                events.emit("say", id=tid, text=thought[:1000])
            calls = (m.tool_calls or parse_text_calls(m.content, names))[:TOOLS_PER_STEP]
            if not calls:
                bad = slop_check(m.content or "")
                if bad and bad.startswith("you wrote a tool call"):
                    if text_mode:
                        bad = ("that tool call could not be run: it is malformed JSON or names an unknown tool. Reply with ONLY "
                               'one valid JSON object like {"name": "<tool>", "arguments": {...}}. Valid tool names: '
                               + ", ".join(sorted(names)))
                    else:
                        bad += ". Unknown tool name? Valid tool names: " + ", ".join(sorted(names))
                hint_turn = False  # a first-call nudge: counted in hint_retries, not slop_retries
                if not bad and tools and not used_tools:
                    bad = (first_call_hint(task_text, names, role.get("required_tool") or "") if not hinted else None) or \
                        "you answered without calling any tool; call a tool to read real data first"
                    hinted = True
                    hint_turn = True
                failed = not bad and used_tools and not ok_calls and fail_retries < 2
                if failed:
                    fail_retries += 1
                    bad = "every tool call failed; fix the arguments and call the tool again before answering"
                if bad and (failed or (hint_turn and hint_retries < 2) or (not hint_turn and slop_retries < 2)):
                    if hint_turn:
                        hint_retries += 1
                    elif not failed:
                        slop_retries += 1
                    events.emit("retry", id=tid, n=slop_retries, reason=bad[:200])
                    msgs += [{"role": "assistant", "content": m.content or ""}, {"role": "user", "content": bad}]
                    continue
                if bad:
                    raise LoopError(bad)
                msgs.append({"role": "assistant", "content": m.content})
                return m.content, msgs
            msgs.append({"role": "assistant", "content": "" if not m.tool_calls else (m.content or ""), "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in calls]})
            used_tools = True
            for c in calls:
                events.emit("tool", id=tid, name=c.function.name, args=(c.function.arguments or "")[:160])
                bad_args = ""
                try:
                    a = coerce_args(json.loads(c.function.arguments or "{}"), schemas.get(c.function.name, {}))
                    if role["role"] == "browser":
                        a.pop("filePath", None)  # snapshots return inline; file output is outside the sandbox roots
                    bad_args = arg_error(a, schemas.get(c.function.name, {}))
                    if bad_args:  # never sent to the server; the model must fix the call
                        out = bad_args
                    else:
                        STARTED[tid] = STARTED.get(tid, 0) + 1
                        res = await asyncio.wait_for(sess.call_tool(c.function.name, a), TOOL_TIMEOUT or None)
                        out = result_text(res)
                        if (hasattr(res, "is_error") and res.is_error) or (not hasattr(res, "is_error") and getattr(res, "isError", False)) or out.startswith(("Input validation error", "Error:")):
                            out = f"tool error: {out}"
                        else:
                            ok_calls += 1
                            if not out.strip():  # empty result: say so, so the model does not invent data
                                out = "tool returned no results (empty). Report that no matching data was found; do not invent any."
                            elif c.function.name in ("write_file", "edit_file"):
                                out += lint_written(a.get("path", ""))
                except asyncio.TimeoutError:
                    out = f"tool error: {c.function.name} timed out after {TOOL_TIMEOUT:g}s; try a narrower path or query"
                except Exception as e:  # tool errors go back to the model, not up
                    out = f"tool error: {e}"
                if role["role"] != "browser":  # browser sessions keep state in their container
                    await asyncio.to_thread(mcp_reap.sweep)  # idle per-call stdio containers do not pile up mid-run
                if out.startswith("tool error") or bad_args:  # the trail keeps the error text, so get_detail shows why a call failed
                    events.emit("tool_error", id=tid, name=c.function.name, error=out[:300])
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": out})
        raise LoopError(f"no final answer in {role['max_steps']} steps")
