"""Tool-calling agent loop: <=2 tool calls per step, anti-slop checks, bounded steps."""
import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace

from openai import OpenAI

from . import events
from .config import (LLM_API_KEY, LLM_TIMEOUT, OLLAMA_URL, SYNAPTREE_PROJECT, TASK_TIMEOUT, TOOL_TIMEOUT,
                     TOOLS_PER_STEP, TOOL_MODE, WORKSPACE)
from .compose import backends
from .lint import check_python
from .mcp_client import open_role, result_text, to_openai_tools

_client = OpenAI(base_url=OLLAMA_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT, max_retries=0)
USAGE: dict[str, dict] = {}  # per task id: model calls and tokens, taken by the gateway when the task ends


def _count(tid: str, r, msgs: list, m) -> None:
    """Add one model call to the task's totals. Uses the backend's usage when sent, else chars / 4."""
    u = getattr(r, "usage", None)
    inp = getattr(u, "prompt_tokens", None)
    out = getattr(u, "completion_tokens", None)
    if inp is None:
        inp = sum(len(str(x.get("content") or "")) for x in msgs) // 4
    if out is None:
        out = len(m.content or "") // 4
    a = USAGE.setdefault(tid, {"calls": 0, "input": 0, "output": 0})
    a["calls"] += 1
    a["input"] += int(inp)
    a["output"] += int(out)


def take_usage(tid: str) -> dict:
    """Totals for one task id; cleared so a resumed run starts its own count."""
    return USAGE.pop(tid, {"calls": 0, "input": 0, "output": 0})
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
              "Results come back in the next message. Available tools:" + chr(10) + "{tools}")
SLOP = re.compile(r"(as an ai|i.m sorry, but i.m not able|i can.t assist|i cannot access|lorem ipsum|TODO: implement|placeholder|\.\.\. ?rest of)", re.I)
TOOL_CAP = 8000  # chars of tool output fed back to the model


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
        except ValueError:
            pass
    return out


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


def parse_text_calls(text: str, names: set) -> list:
    """Recover tool calls a small model wrote as JSON text (optionally in <tool_call>/code fences)."""
    t = re.sub(r"</?tool_call>|```(?:json)?", "", text or "").strip()
    calls = []
    dec = json.JSONDecoder()
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
        lines.append(f"- {f['name']}({props}): {(f.get('description') or '')[:160]}")
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


async def run(agent: str, role: dict, prompt: str, messages: list | None = None,
              tid: str = "") -> tuple[str, list]:
    system = SYSTEM.format(role=role["role"], agent=agent, n=TOOLS_PER_STEP)
    if "synaptree" in (role.get("native") or []):
        system += GRAPH_RULE.format(project=SYNAPTREE_PROJECT)
    if role["role"] == "browser":
        system += BROWSER_RULE
    msgs = messages or [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    try:
        return await asyncio.wait_for(_run(agent, role, msgs, tid), TASK_TIMEOUT or None)
    except asyncio.TimeoutError:
        e = LoopError(f"task timed out after {TASK_TIMEOUT:g}s")
        e.msgs = msgs
        raise e
    except BaseException as e:
        leaf(e).msgs = msgs  # failed runs still did local work; the gateway counts it as saved
        raise


async def _run(agent: str, role: dict, msgs: list, tid: str) -> tuple[str, list]:
    async with backends(role.get("compose", []), role.get("keep_alive", False)), \
            open_role(role.get("profile"), role.get("native")) as sess:
        tools = to_openai_tools((await sess.list_tools()).tools, role["tools"])
        names = {t["function"]["name"] for t in tools}
        text_mode = bool(tools) and (role.get("tool_mode") or TOOL_MODE) == "text"
        if text_mode and msgs and msgs[0].get("role") == "system" and "Tools are NOT available" not in msgs[0]["content"]:
            msgs[0]["content"] += text_tool_prompt(tools)
        schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
        ok_calls = sum(1 for x in msgs if x.get("role") == "tool" and not str(x.get("content", "")).startswith("tool error"))
        fail_retries = 0
        slop_retries = 0
        used_tools = any(m.get("role") == "tool" for m in msgs)
        for step in range(1, role["max_steps"] + 1):
            events.emit("step", id=tid, n=step)
            r = await asyncio.to_thread(  # off the event loop so keepalives and other tasks keep running
                _client.chat.completions.create, model=role["model"], messages=text_view(msgs) if text_mode else msgs,
                temperature=0.1, max_tokens=2048, tools=None if text_mode else (tools or None),
                **({} if used_tools or not tools or text_mode else {"tool_choice": "required"}))
            m = r.choices[0].message
            _count(tid, r, msgs, m)
            thought = (getattr(m, "reasoning_content", None) or getattr(m, "reasoning", None) or m.content or "").strip()
            if thought:
                events.emit("say", id=tid, text=thought[:1000])
            calls = (m.tool_calls or parse_text_calls(m.content, names))[:TOOLS_PER_STEP]
            if not calls:
                bad = slop_check(m.content or "")
                if bad and bad.startswith("you wrote a tool call") and text_mode:
                    bad = ("that tool call could not be run: it is malformed JSON or names an unknown tool. Reply with ONLY "
                           'one valid JSON object like {"name": "<tool>", "arguments": {...}}. Valid tool names: '
                           + ", ".join(sorted(names)))
                if not bad and tools and not used_tools:
                    bad = "you answered without calling any tool; call a tool to read real data first"
                failed = not bad and used_tools and not ok_calls and fail_retries < 2
                if failed:
                    fail_retries += 1
                    bad = "every tool call failed; fix the arguments and call the tool again before answering"
                if bad and (failed or slop_retries < 2):
                    slop_retries += 0 if failed else 1
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
                try:
                    a = coerce_args(json.loads(c.function.arguments or "{}"), schemas.get(c.function.name, {}))
                    if role["role"] == "browser":
                        a.pop("filePath", None)  # snapshots return inline; file output is outside the sandbox roots
                    res = await asyncio.wait_for(sess.call_tool(c.function.name, a), TOOL_TIMEOUT or None)
                    out = result_text(res)
                    if getattr(res, "isError", False) or out.startswith(("Input validation error", "Error:")):
                        out = f"tool error: {out}"
                    else:
                        ok_calls += 1
                        if c.function.name in ("write_file", "edit_file"):
                            out += lint_written(a.get("path", ""))
                except asyncio.TimeoutError:
                    out = f"tool error: {c.function.name} timed out after {TOOL_TIMEOUT:g}s; try a narrower path or query"
                except Exception as e:  # tool errors go back to the model, not up
                    out = f"tool error: {e}"
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": out[:TOOL_CAP]})
        raise LoopError(f"no final answer in {role['max_steps']} steps")
