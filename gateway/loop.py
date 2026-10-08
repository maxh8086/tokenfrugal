"""Tool-calling agent loop: <=2 tool calls per step, anti-slop checks, bounded steps."""
import json
import re
from types import SimpleNamespace

from openai import OpenAI

from .config import LLM_API_KEY, OLLAMA_URL, TOOLS_PER_STEP
from .compose import backends
from .mcp_client import open_role, result_text, to_openai_tools

_client = OpenAI(base_url=OLLAMA_URL, api_key=LLM_API_KEY)
SYSTEM = ("You are a focused {role} agent ({agent}). Use at most {n} tool calls per step. "
          "Work only inside the workspace, which is mounted at /workspace: always use absolute paths like /workspace/README.md. Be terse. When done, reply with the final result "
          "(findings, files changed, verdict) and no tool call. Never invent file contents or paths: you MUST call a tool to read real data before answering, and say 'not found' if a tool returns nothing.")
SLOP = re.compile(r"(as an ai|i cannot access|lorem ipsum|TODO: implement|placeholder|\.\.\. ?rest of)", re.I)
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
    if re.match(r'''\s*\{\s*["']name["']\s*:''', text):
        return "you wrote a tool call as text; use the tool-calling interface or give the final answer"
    if SLOP.search(text):
        return "answer contains filler/placeholder text; redo with concrete content"
    return None


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
            i += 1
            continue
        i = j
        if isinstance(o, dict) and o.get("name") in names:
            a = o.get("arguments", o.get("parameters", {}))
            calls.append(SimpleNamespace(id=f"txt_{len(calls)}", function=SimpleNamespace(
                name=o["name"], arguments=a if isinstance(a, str) else json.dumps(a))))
    return calls


async def run(agent: str, role: dict, prompt: str, messages: list | None = None) -> tuple[str, list]:
    msgs = messages or [{"role": "system", "content": SYSTEM.format(role=role["role"], agent=agent, n=TOOLS_PER_STEP)},
                        {"role": "user", "content": prompt}]
    async with backends(role.get("compose", []), role.get("keep_alive", False)), \
            open_role(role.get("profile"), role.get("native")) as sess:
        tools = to_openai_tools((await sess.list_tools()).tools, role["tools"])
        names = {t["function"]["name"] for t in tools}
        slop_retries = 0
        used_tools = any(m.get("role") == "tool" for m in msgs)
        for _ in range(role["max_steps"]):
            r = _client.chat.completions.create(model=role["model"], messages=msgs, temperature=0.1,
                                                max_tokens=2048, tools=tools or None,
                                                **({} if used_tools or not tools else {"tool_choice": "required"}))
            m = r.choices[0].message
            calls = (m.tool_calls or parse_text_calls(m.content, names))[:TOOLS_PER_STEP]
            if not calls:
                bad = slop_check(m.content or "")
                if not bad and tools and not used_tools:
                    bad = "you answered without calling any tool; call a tool to read real data first"
                if bad and slop_retries < 2:
                    slop_retries += 1
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
                try:
                    res = await sess.call_tool(c.function.name, json.loads(c.function.arguments or "{}"))
                    out = result_text(res)
                except Exception as e:  # tool errors go back to the model, not up
                    out = f"tool error: {e}"
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": out[:TOOL_CAP]})
        raise LoopError(f"no final answer in {role['max_steps']} steps")
