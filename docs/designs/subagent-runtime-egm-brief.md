# tokenfrugal as a subagent runtime: code review and EGM brief

Status: review and brief only. No code here is applied. The sketches show the shape of each change for the EGM design; the design and the tasks come from `egm:egm-brainstorm`.

Reviewed at `main` d675d75, 2026-11-19. Files read: `router/loop.py`, `server.py`, `checker.py`, `summarize.py`, `store.py` (schema), `plan.py` (head), `config.py` (constants), `tf-roles.yaml` (roles, builder contract), `skills/role-builder/SKILL.md`, `sandbox_mcp.py` (tool list), `.codex/`, `AGENTS.md`, `Benchmark/results/team_results.csv`, `docs/haiku-fallback-log.md`. The synaptree index was stale (index sha 40e0ecb, head d675d75) and `index_repository` timed out after 1800 s, so files were read directly.

## 1. What exists today

| Area | In the code now | Where |
| --- | --- | --- |
| Entry point | FastMCP stdio server; `dispatch_task`, `resume_task`, `ask_followup`, `get_detail`, `list_roles`, `plan_*` | `router/server.py` |
| Roles | slug -> role = model + Docker MCP profile + 4-6 allowlisted tools + skills + `max_steps` (6-16) + `timeout_s` (60-450) | `router/tf-roles.yaml`, `config.resolve_role` |
| Loop | max 2 tool calls per step; `tool_choice=required` until the first call; pre-reads up to 2 paths named in the task; wrap-up nudge at 70% of steps; last step forced to answer; slop / first-call / all-failed retries | `loop._run` |
| Tool-call repair | native calls, or text mode with JSON / `<function=...>` parsing, brace repair, type coercion, schema check before the call reaches the server | `parse_text_calls`, `coerce_args`, `arg_error` |
| Verification | after the run: Accept command, Python lint of changed files, `git apply --check` for a diff block; one correction run; lint feedback after each `.py` write | `checker.check_deterministic`, `server._check`, `loop.lint_written` |
| Failure classes | `error_kind` (step_timeout, request_timeout, no_tool_call, max_steps, bad_answer, infra, checker, gpu_busy, ...) plus a next-step hint | `loop.error_kind`, `server.failure_message` |
| State | SQLite `tasks` (prompt, summary, detail, full messages, event trail, error_kind) for resume and follow-up; Neo4j plan graph (deps, runs, status events, commit evidence) | `router/store.py`, `router/plan.py` |
| Reply to the cloud agent | free-text summary up to `SUMMARY_MAX_TOKENS` = 5000, a `files_changed:` line and a `status=` line | `summarize.py`, `server._execute` |
| Codex | MCP registered in `.codex/config.toml`; thin wrapper agent `.codex/agents/tokenfrugal.toml`; client name logged | `.codex/`, `server._ClientSeen` |

Measured quality: on 2026-10-29 the builder model (`Qwen3.5-4B Q6_K`) passed 3/3 on most short role tasks (code-l1..l6, builder, analyzer, reviewer, debugger, db-*), mean 10-50 s warm. It failed 0/3 on security and research. These are scoped single tasks, not 15-20 step loops. `docs/haiku-fallback-log.md` shows the real failure modes: tool calls written as text, wrong sandbox path, a 630 KB file that did not fit the context, a missing dependency branch.

## 2. The six pillars checked against the code

| Pillar | Verdict | Main gap |
| --- | --- | --- |
| 1 Shared state, zero-chat handoffs | Feasible, about 40% built | Replies are prose up to 5000 tokens, not typed receipts. There is no task-packet schema, no file-hash registry and no versioned "what changed since v" read. Plan features turn off silently when Neo4j is down. |
| 1b Prompt-cache preservation | Mostly outside tokenfrugal's control | Claude Code and Codex own the cache. The router can only keep its tool surface stable and its replies small and append-only. Caches are per model, so Sonnet and Haiku never share one. |
| 2 Cost-aware routing | Feasible; the Haiku tier pays off less than expected | Routing exists only as CLAUDE.md prose. The real limit is Haiku's 100K price cliff (verified: $0.10/$0.50 up to 100K, $0.50/$2.50 above) together with Claude Code subagent cold start (about 65K tokens by your own note), which leaves Haiku about 35K before the cliff. |
| 3 Loop governance (20+ iterations) | Feasible; biggest gap | `msgs` grows without limit. `result_text` returns tool output uncapped, so `read_file` of a large file floods a 16-32K window. There is no repeated-call or repeated-error detection. Step budgets are 8-16, and the builder `timeout_s` is 130. |
| 4 Constrained tool calls and skill mounting | Feasible with a spike | There is no grammar or JSON-schema constrained decoding; it relies on repair afterwards. All role skills are added to the system prompt once, and every allowlisted tool is offered at every step. The builder runs Q6_K, not Q4_K_M; Q4_K_M is not benchmarked. |
| 5 Verification and circuit breakers | Feasible, extends `checker.py` | Checks run only after the run. The "only named files changed" contract item is never enforced (`files_changed` is always `passed: True`). A failed run leaves the workspace dirty, and there is no structured escalation packet. |
| 6 Token math | See section 4 | With Sonnet 5.5 caching, Sonnet-only is cheaper than intuition suggests. The win comes from first-pass success rate and small receipts, not from more tiers. |

Smaller findings:
- `CLAUDE.md` (global) says replies are capped at 150-300 tokens; `config.py` sets 150-5000.
- `AGENTS.md` points to `router/agents.yaml`; the file is now `router/tf-roles.yaml`.
- `TASK_TIMEOUT` (540 s) must stay below the MCP client's tool timeout. `.codex/config.toml` sets no `tool_timeout_sec`, and I believe Codex defaults to 60 s, which is less than the builder's 130 s. Check this. Long local loops need a non-blocking dispatch either way.

## 3. Proposed changes, with code sketches

### 3.1 Typed task packet (Sonnet/Haiku -> tokenfrugal)

New `router/packet.py`. `render()` produces the same prompt text the loop already understands, so preread (`named_paths`) and `accept_cmd` keep working.

```python
from dataclasses import dataclass, field

@dataclass
class TaskPacket:
    goal: str                                   # one sentence, <= 200 chars
    role: str                                   # agency-agents slug
    files: list[dict]                           # [{"path": "/workspace/app/x.py", "lines": "40-90"}], <= 3
    accept: str                                 # one command, run without a shell
    must_not_change: list[str] = field(default_factory=list)   # globs, e.g. ["tests/**"]
    context: str = ""                           # signatures and types only, <= 1200 chars
    max_steps: int = 0                          # 0 = role default

def validate(p: TaskPacket, ctx_budget: int) -> str:
    if len(p.goal) > 200: return "goal longer than 200 chars"
    if not p.files or len(p.files) > 3: return "name 1-3 files; split larger work into packets"
    if not p.accept.strip(): return "accept command required"
    if len(p.context) > 1200: return "context over 1200 chars; pass paths, not contents"
    need = sum(file_tokens(f) for f in p.files)        # bytes/4 of the named line ranges
    return f"named ranges need {need} tokens, budget {ctx_budget}" if need > ctx_budget else ""

def render(p: TaskPacket) -> str:
    files = "\n".join(f"- {f['path']}" + (f" lines {f['lines']}" if f.get("lines") else "") for f in p.files)
    keep = f"\nDo not change: {', '.join(p.must_not_change)}" if p.must_not_change else ""
    return f"{p.goal}\nFiles:\n{files}{keep}\n{p.context}\nAccept: {p.accept}"
```

### 3.2 Blackboard and receipts (tokenfrugal -> every tier)

Add to `store._db()`; it is SQLite only, so it works when Neo4j is down.

```python
c.execute("""CREATE TABLE IF NOT EXISTS board(
    v INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, kind TEXT, body TEXT, at REAL)""")  # kind: packet|receipt|escalation
c.execute("""CREATE TABLE IF NOT EXISTS file_hashes(path TEXT PRIMARY KEY, sha TEXT, task_id TEXT, at REAL)""")

def err_hash(line: str) -> str:
    """Same error, different line numbers or addresses -> same hash."""
    norm = re.sub(r"0x[0-9a-f]+|\b\d+\b", "N", (line or "").strip().lower())
    return hashlib.sha1(norm.encode()).hexdigest()[:8] if norm else ""

def receipt(tid, role, status, changed, verdict, kind="", err="", phase="", nxt="") -> dict:
    """About 80-150 tokens. This, not the summary, is what Sonnet and Haiku read."""
    return {"task_id": tid, "status": status, "role": role, "phase": phase,
            "files": [{"path": p, "sha": file_sha(WORKSPACE, p)} for p in changed][:10],
            "checks": {i["name"]: i["passed"] for i in (verdict or {}).get("items", [])},
            "error_kind": kind, "error_hash": err_hash(err), "error": err[:160], "next": nxt}

def post(tid, kind, body) -> int:        # sort_keys + compact separators: byte-stable output
    with _db() as c:
        return c.execute("INSERT INTO board(task_id,kind,body,at) VALUES(?,?,?,?)",
                         (tid, kind, json.dumps(body, sort_keys=True, separators=(",", ":")), time.time())).lastrowid
```

New MCP tool: `board_since(v)` returns only the receipts and escalations posted after version `v`. A tier that last saw v=41 reads three small JSON rows, not logs. `get_detail` stays as the escape hatch.

### 3.3 Context window for the local loop (`loop.py`)

Prune the view sent to the model, not the stored `msgs`, so `resume_task` and `get_detail` keep everything. Prune in batches so llama.cpp/Ollama can reuse the KV prefix between prunes.

```python
TOOL_RESULT_TOKENS = int(os.getenv("TOKENFRUGAL_TOOL_RESULT_TOKENS", "1500"))
KEEP_FULL = 3        # newest tool results kept whole
PRUNE_EVERY = 4      # stub older results only every 4 steps: the prefix stays stable in between

def cap_result(name: str, out: str) -> str:
    lim = TOOL_RESULT_TOKENS * 4
    if len(out) <= lim:
        return out
    return (out[: lim * 2 // 3] + f"\n[{len(out) // 4 - TOOL_RESULT_TOKENS} tokens cut: call {name} "
            "with a narrower range]\n" + out[-lim // 3:])

def model_view(msgs: list, step: int) -> list:
    cut = (step // PRUNE_EVERY) * PRUNE_EVERY
    tools = [i for i, m in enumerate(msgs) if m.get("role") == "tool"]
    old = set(tools[:-KEEP_FULL]) if cut else set()
    return [{**m, "content": f"[stub] {len(m['content']) // 4} tokens; first line: "
             f"{(m['content'].strip().splitlines() or ['empty'])[0][:120]}"} if i in old else m
            for i, m in enumerate(msgs)]
# in _run: out = cap_result(c.function.name, result_text(res)); kw["messages"] = model_view(msgs, step)
```

Also keep a harness-written state note (files read with sha, edits applied, last error line, phase) as the newest user message, so the model never needs the old turns.

### 3.4 Loop guard (repeated call / repeated error)

```python
class LoopGuard:
    def __init__(self, same_call: int = 3, same_error: int = 3):
        self.calls, self.errors = collections.Counter(), collections.Counter()
        self.same_call, self.same_error = same_call, same_error

    def call(self, name: str, args: dict) -> str:
        k = hashlib.sha1(f"{name}{json.dumps(args, sort_keys=True)}".encode()).hexdigest()[:10]
        self.calls[k] += 1
        if self.calls[k] >= self.same_call:
            raise LoopError(f"loop: {name} called {self.calls[k]} times with the same arguments")
        return "You made this exact call already; its result is above. Do something different." if self.calls[k] == 2 else ""

    def failed(self, err_line: str) -> None:
        h = err_hash(err_line)
        self.errors[h] += 1
        if self.errors[h] >= self.same_error:
            raise LoopError(f"stuck: error {h} repeated {self.errors[h]} times: {err_line[:120]}")
# error_kind(): map "loop:" -> "loop", "stuck:" -> "stuck"; both mean re-scope, never resume_task.
```

### 3.5 Phase-scoped tools and harness-run verify

Offer only the tools of the current phase. After every successful edit, the harness runs the Accept command itself, which saves one model step per iteration.

```python
PHASES = {"locate": {"search_graph", "get_code_snippet", "read_file", "search_files"},
          "edit":   {"edit_file", "write_file", "read_file"}}

def next_phase(phase: str, tool: str, ok: bool) -> str:
    if phase == "locate" and ok and tool in ("read_file", "get_code_snippet"): return "edit"
    return phase
# after a successful edit_file/write_file in _run:
#   ok, tail = checker.run_accept(accept_argv, WORKSPACE, timeout=60)
#   if ok: force the final answer
#   else: guard.failed(first_error_line(tail)); append "ACCEPT FAILED:\n" + tail; stay in "edit"
step_tools = [t for t in tools if t["function"]["name"] in PHASES[phase]] or tools
```

### 3.6 Constrained decoding (text mode first)

One schema that accepts exactly one valid call to a tool of the current phase, or a final answer. Ollama's OpenAI-compatible endpoint takes `response_format` with `json_schema`; llama.cpp server takes `json_schema` too. Spike this first: `anyOf` + `const` support in the grammar converter, and how it interacts with the thinking output of Qwen3.5.

```python
def step_schema(step_tools: list) -> dict:
    calls = [{"type": "object", "additionalProperties": False, "required": ["name", "arguments"],
              "properties": {"name": {"const": t["function"]["name"]}, "arguments": t["function"]["parameters"]}}
             for t in step_tools]
    final = {"type": "object", "additionalProperties": False, "required": ["final"],
             "properties": {"final": {"type": "string"}}}
    return {"anyOf": calls + [final]}
# text mode: kw["response_format"] = {"type": "json_schema", "json_schema": {"name": "step", "schema": step_schema(step_tools)}}
```

This makes calls syntactically valid. It does not make them the right call, so the loop guard and verify stay.

### 3.7 Scope enforcement, revert, escalation packet (`checker.py`, `server.py`)

```python
def scope_check(new_changes: list[str], allowed: list[str], forbidden: list[str]) -> dict:
    outside = [p for p in new_changes if allowed and not any(fnmatch(p, g) for g in allowed)]
    banned = [p for p in new_changes if any(fnmatch(p, g) for g in forbidden)]
    bad = outside + banned
    return {"name": "scope", "tag": "deterministic", "passed": not bad, "detail": ", ".join(bad) or "ok"}

def escalation(tid, kind, phase, attempts, err, changed, tried) -> dict:
    return {"task_id": tid, "escalate_to": "sonnet", "kind": kind, "phase": phase, "attempts": attempts,
            "error_hash": err_hash(err), "error": err[:160], "files": changed[:10],
            "tried": tried[-3:], "ask": "re-scope | take over | drop"}
```

Revert on failure (opt-in): save `git diff -- <files changed by this run>` to the board, then restore only files that were clean before the run (`after - before` from `_changed_set`). Never touch files that were already dirty.

### 3.8 Non-blocking dispatch (Codex timeout, long loops)

```python
@mcp.tool()
async def dispatch_task(agent="", task="", task_type="", plan_id=0, role="", accept="",
                        packet: dict | None = None, wait: bool = True) -> str:
    ...
    if not wait:
        asyncio.create_task(_execute(tid, agent, role, prompt, plan_id=plan_id, accept_override=accept_argv))
        return json.dumps({"task_id": tid, "status": "running", "poll": "task_status"})

@mcp.tool()
def task_status(task_id: str) -> str:
    """Receipt JSON for one task (running, done, failed, escalated). About 100 tokens."""
```

Changing tool signatures and docstrings changes delegation behaviour and every client's cached prefix. Ship the new tool surface once, then freeze it.

### 3.9 Routing estimate (Sonnet's direct-vs-Haiku decision)

```python
def route(p: TaskPacket, pass_rate: float, ctx_budget: int) -> tuple[str, str]:
    """pass_rate = done / runs for this role over the last 20 tasks in tasks.db, else the benchmark row."""
    need = sum(file_tokens(f) for f in p.files) + len(p.context) // 4
    if not p.accept:            return "cloud", "no acceptance command: local output cannot be checked"
    if need > ctx_budget // 2:  return "cloud", f"needs {need} tokens; local budget {ctx_budget}"
    if len(p.files) > 3:        return "split", "more than 3 files: Haiku splits into packets"
    if pass_rate < 0.55:        return "haiku", f"role pass rate {pass_rate:.0%} is below break-even (55%)"
    return "local", f"pass rate {pass_rate:.0%}; context {need} tokens"
```

## 4. Token and cost math, 15-step coding task

Prices checked against the current model table: Sonnet 5.5 $2 in / $10 out / $0.10 cache read (cache write taken as 1.25x = $2.50). Haiku 5.5 $0.10 / $0.50 up to 100K, $0.50 / $2.50 above (cache read taken as $0.01, as in your brief). Assumptions: 25K cached client prefix; each step adds about 2.5K tokens of tool results; about 600 output tokens plus about 1K thinking per cloud step; Sonnet plans and reviews in 3 turns.

| Setup | Sonnet | Haiku | Local | Total | Notes |
| --- | --- | --- | --- | --- | --- |
| A Sonnet only | 675K input (612K cache read, 62.5K write), 24K output: **$0.46** | - | - | **$0.46** | Output and cache writes dominate, not reads. |
| B Sonnet + Haiku executes | 3 turns: **$0.09** | 15 steps, peak 62.5K: **$0.03** | - | **$0.12** | With a 65K subagent cold start the peak reaches about 100K and hits the 5x cliff. |
| C Sonnet + Haiku + tokenfrugal, receipts | 3 turns reading receipts: **$0.09** | packet + 2 receipts: **$0.003** | 15 steps, $0, about 1-3 min | **$0.09** if it passes | Each failure adds about $0.056 (Haiku fallback plus one Sonnet review). |
| D Sonnet -> tokenfrugal direct | 2 turns: **$0.065** | - | as C | **$0.065** if it passes | Best when Sonnet can write a complete packet. |

Break-even: C beats B when the local first-pass rate is above about 52%, and D beats B above about 45%. Measured short-task pass rates are 100% for most coding roles, but the 15-step loop is not benchmarked. Two conclusions: (1) Sonnet's planning and review turns are most of the bill in B, C and D, so cut Sonnet turns and output, and pass receipts rather than summaries; (2) Haiku adds value when work must be split into packets, not as a relay for single packets.

## 5. Phased roadmap

1. **P0 spikes (no router change):** benchmark Qwen3.5-4B Q4_K_M against Q6_K on the realworld set; test Ollama `json_schema` with `anyOf`/`const` plus thinking; check Codex's MCP tool timeout; write a 15-step benchmark case (edit -> test -> fix).
2. **P1 receipts and packets:** `packet.py`, board tables, `receipt()`, `board_since`, `task_status`, compact JSON reply. Keep the old prose path behind a flag for one release.
3. **P2 loop governance:** `cap_result`, `model_view`, state note, `LoopGuard`, new `error_kind`s.
4. **P3 phase tools and harness verify:** `PHASES`, auto-Accept after each edit, larger step budget only for packet tasks.
5. **P4 constrained decoding:** text mode first, native mode only if the spike shows a gain.
6. **P5 scope, revert, escalation:** `scope_check`, opt-in revert, escalation packet on the board.
7. **P6 routing and non-blocking dispatch:** `route()` from live pass rates, `wait=False`, Codex `tool_timeout_sec`, docs (`CLAUDE.md`, `AGENTS.md`, `examples/`).

Each phase: offline tests (`PYTHONPATH=. python -m unittest discover -s tests -t . -q`), `scripts/smoke.py`, and the realworld benchmark before and after, comparing pass rate, tool calls and wall time.

## 6. EGM brainstorm prompt

Paste this into `egm:egm-brainstorm`:

```text
Feature: make tokenfrugal a dependable local subagent for Claude Code and Codex, using typed
task packets, a shared blackboard of receipts, and a governed local loop.

Repo: C:\Users\vaibh\Downloads\Projects\tokenfrugal (main, d675d75). Write the design to
docs/designs/subagent-runtime-design.md. Read docs/designs/subagent-runtime-egm-brief.md first;
it has the code review, the gap list, code sketches and the cost math. Treat the sketches as
input to challenge, not as decisions.

Current state (verified in code):
- router/server.py: dispatch_task returns a prose summary up to 5000 tokens plus files_changed
  and status lines. resume_task/ask_followup replay the full stored conversation.
- router/loop.py: <=2 tool calls/step, 8-16 steps, preread of named paths, 70% wrap-up, forced
  final step, text-mode JSON repair. No context pruning, tool results uncapped, no repeat
  detection, all role tools offered every step, skills added once to the system prompt.
- router/checker.py: Accept command, Python lint, diff --check, after the run only; one
  correction run; the "only named files changed" contract item is not enforced; no revert.
- router/store.py (SQLite) and router/plan.py (Neo4j) hold tasks, trails, plan graph.
- Codex: .codex/config.toml and .codex/agents/tokenfrugal.toml; no tool_timeout_sec set.
- Builder model hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K passes 3/3 on short role tasks (2026-10-29);
  no benchmark exists for 15-20 step loops or for Q4_K_M.

Goals:
1. Typed TaskPacket in (goal, role, 1-3 files with line ranges, accept, must_not_change,
   context <=1200 chars) and a JSON receipt out (<=150 tokens). Prose stays behind a flag.
2. SQLite blackboard: packets, receipts, escalations, file hashes, versioned; board_since(v)
   and task_status(id) tools. Must work when Neo4j is down.
3. Local loop that survives 20+ iterations in a 16-32K window: capped tool results, pruned
   model view (stored history unchanged), harness state note, repeat-call and repeat-error
   circuit breakers, phase-scoped tools, harness-run Accept after each edit.
4. Constrained decoding for tool calls (JSON schema via Ollama/llama.cpp), gated by a spike.
5. Scope check, opt-in revert of this run's own changes, structured escalation packet.
6. Deterministic routing estimate (local / haiku / split / cloud) from live per-role pass
   rates and context need; non-blocking dispatch for long loops and Codex's tool timeout.

Constraints:
- Local models: only the builder and thinker in router/tf-roles.yaml, <8B. Whether to move the
  builder from Q6_K to Q4_K_M is the user's decision after the P0 benchmark.
- No raw transcripts between tiers: cloud tiers read receipts and board deltas only;
  get_detail stays as the explicit escape hatch.
- Haiku 5.5 must stay under 100K tokens per subagent (price rises 5x above). Account for
  Claude Code subagent cold start (about 65K by the user's measurement).
- Tool docstrings and signatures change delegation behaviour and every client's cached prefix:
  change the tool surface once, keep it byte-stable, sorted JSON in replies.
- Client-neutral: everything over MCP; the design must work for Codex, which has no Haiku tier.
- Portability: no hardcoded paths, pinned requirements, setup steps for other machines.
- Max 6 tools per role (12 hard cap); skills under 1200 chars.
- Do not break: resume_task, ask_followup, get_detail, plan_* tools, studio_*, existing
  benchmark cases, docker compose project rules, GPU lease.

Questions the design must answer:
- Where does the blackboard live (tasks.db vs new file), retention, and concurrency with
  several router processes?
- Exact receipt and escalation JSON schemas, and which fields each tier reads.
- Pruning policy that keeps the llama.cpp/Ollama KV prefix reusable.
- When the harness runs Accept itself vs the model calling run_tests.
- How routing gets pass rates (tasks.db window vs Benchmark csv) and the break-even threshold.
- Whether the Haiku tier is required, optional, or only for splitting work into packets.
- Migration: flag names, default on/off, how old prose replies keep working for one release.

Out of scope: new local models beyond the two roles, cloud fallback inside the router,
media/studio pipelines, UI changes beyond showing receipts.

Acceptance for the design: each goal maps to named files and functions; each phase has one
acceptance command; a 15-step benchmark case is defined with target pass rate, tool calls,
wall time and Haiku/Sonnet token counts; the cost table is recomputed with the final design.
Rule applied: feature-sized (several modules, new interfaces and schema), so EGM brainstorm,
six-lens review plus synthesizer, user approval before any task is dispatched. In this repo,
execution goes to Haiku subagents, not the tokenfrugal MCP.
```
