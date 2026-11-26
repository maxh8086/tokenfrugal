# tokenfrugal builder as a dependable local subagent

*   **Author:** Vaibhav Pavtekar
*   **Status:** Draft
*   **Date:** 2026-11-19

--------------------------------------------------------------------------------

## Overview

tokenfrugal is an MCP router that lets Claude Code and Codex hand routine coding work to a local 4B model (`hf.co/unsloth/Qwen3.5-4B-GGUF:Q6_K`, the "builder") and get back a short summary. The aim is to spend fewer cloud tokens on routine edits.

That only saves tokens if the cloud agent can trust the answer. Today it cannot. About a third of builder tasks fail. Some tasks report "done" when nothing was written or nothing was checked. After every fallback, the orchestrator re-runs the tests itself. A failed local attempt therefore costs the local run, the cloud agent's re-check, and a Haiku fallback of up to 120K tokens.

This design makes the builder's result something the caller can act on without re-checking:

1. **S1a-S1c:** fix the defects in existing code that cause most of the logged failures. This changes no tool signature.
2. **S2:** make "done" mean a file actually changed, or the work was already done, and measure the result on a fixed set of real tasks.
3. **S3:** add a small amount of loop control for structured tasks.
4. **S4:** change the tool surface once, adding a structured task packet in and a short JSON receipt out.

The design source is `docs/designs/subagent-runtime/concepts_brief.md`. Decisions D1-D10 and fixes F0-F7 there are settled; this document turns them into a buildable plan.

## The Problem

**What the caller sees today:**

*   **Failures are common.** 63% of builder-role tasks in `router/tasks.db` finish (2,120 of 3,381). The fallback log shows the failures that cost the most:
    *   9 real tasks needed 14 attempts before a Haiku subagent took over.
    *   Most of those tasks were a parser plus tests, one pipeline function, or one new module with its test file. These are tasks a 4B model should handle.
*   **"Done" is not trustworthy.**
    *   **Resume reports done with nothing written.** Twice in the log, a resume reported "done" with no file changed (FB-002, FB-003).
    *   **Some tasks are never checked.** A task whose prompt says `Acceptance:` instead of `Accept:` runs no checks at all, and the reply does not say so.
    *   **The change list can be wrong.** It compares sets of git paths, so it misses edits to files that were already modified and can credit another session's edits to the task.
*   **Codex can barely use it.**
    *   Its wrapper calls `dispatch_task` without the required `task_type`, so the server refuses the call.
    *   Its default tool timeout is shorter than the 88 s median run.
    *   Only 24 of 133 Codex sessions used tokenfrugal at all.
*   **It does not install cleanly elsewhere.** `.mcp.json` and `.codex/config.toml` hardcode a Windows venv path.

**Why it happens.** The causes are mostly in the harness, not the model. Each was checked against the code:

*   **The correction run never sees its instruction.** `loop.py:359` drops the fix prompt whenever earlier messages are passed, so the run replays the old conversation unchanged.
*   **The accept command breaks easily.**
    *   It is split on spaces (`server.py:167,318`), so `python -c "..."` and `PYTHONPATH=.` both break.
    *   It runs with the router's Python, not the project's. That is FB-006's missing `yaml`.
    *   After a long run it can get as little as 5 s to finish.
*   **Resume and follow-up lose the task's contract.** They drop the accept command and the templates, and take a new baseline on each attempt, so the first attempt's edits become invisible.
*   **The model tests in the wrong environment.** It tests in a container without the repo's dependencies, while the harness tests on the host. The two disagree, and the model chases errors that do not exist on the host.
*   **Time runs out.** Timeouts are the largest failure class (658 coding failures). Each model step takes 45-110 s.
*   **One failure class has no known cause.** It is `WinError 2` (class A). The traceback was never stored, so it cannot be diagnosed from the data.

**What changes.** The fixes come first, as plain bug fixes, each with a unit test. Then "done" is made honest with a per-task baseline taken from git. Last, structured tasks get a typed packet and a JSON receipt. That last step is the only change the cloud agent's tool list sees.

## Goals

*   **First-dispatch pass rate of at least 80% on the replay corpus:** 16 of 20 frozen real tasks, on role `code-l2`, at temperature 0.0. A paired sign test against today's `main` must show the improvement is not noise (D1).
*   **Zero false successes on the corpus.** No task reports `done` or `satisfied` when its hidden check fails or a `must_not_change` file changed.
*   **Zero failures caused by the checker's own environment.** Examples are a wrong interpreter, broken quoting, a missing program reported as a bare `WinError 2`, or a 5 s accept timeout. A missing program is named, and the reply says what to fix.
*   **Every reply states what was verified.** A legacy reply carries a `checks:` line, and a packet reply carries the `accept` field. A caller can tell a checked done from an unchecked one without calling `get_detail`.
*   **Packet replies of at most 150 tokens** (receipt v1), and legacy replies unchanged apart from the one `checks:` line.
*   **Codex works with no extra steps** beyond `pip install -e .` and the one `tool_timeout_sec` line that `doctor.py` prints. The same `tokenfrugal-router` command works on Windows, macOS and Linux.
*   **Every failure can be diagnosed from the stored row.** It has a stop reason from one vocabulary, a next step, and for unknown errors the frame that raised.
*   **Fewer new fallback-log entries per week** after S2, compared with the four weeks before S1a.

## Non-Goals

*   **New or larger local models.** The builder and thinker in `router/tf-roles.yaml` stay. Q4_K_M is measured as a corpus arm and may be recommended by `doctor.py` through the existing `TOKENFRUGAL_MODEL_*` override. It is never added as a third model in `tf-roles.yaml` (D10).
*   **Any cloud fallback inside the router.** Haiku stays a fallback the caller runs, with the packet and receipt only, never the transcript (D3).
*   **Haiku as packet writer or per-step relay** (D3).
*   **A shared blackboard table, `board_since`, a file-hash registry, or a `route()` cost estimator.**
*   **Escalation packets, automatic revert, phase-scoped tools, constrained decoding, a pruned model view, or a harness state note.** Each has its own entry criterion in D9 and comes back only if the corpus shows the failure it fixes.
*   **Running accept in a container built from the repo's lockfile.** This is listed in D9; host accept stays opt-in until then.
*   **Blocking network access for host accept.** There is no portable way to do this without elevated privileges.
*   **Prompt-cache work** beyond keeping the tool surface stable.
*   **Changes to studio and media pipelines, the GPU lease, compose project rules or the `plan_*` tools.** They must keep working unchanged.
*   **More than one tool-surface change.** All signature and docstring changes ship together in S4.

## Open Questions

*   **Class A cause.** The process launch that raised `WinError 2` is unknown until F7 records it. If F7 shows a cause that S1 does not fix, a follow-up fix is added to S1b. Until then the design does not guess.
*   **Corpus tasks 10-20.** The 11 tasks beyond FB-001..FB-009 are not yet chosen. They must come from Claude Code transcripts, touch at most 3 files, and have a check script that can be written without the model's output. They are chosen in S2, before the first gate run.
*   **Thinking level.** The S2 spike picks medium, low or off, and the unified `code-l2` timeout follows from it. Until then `timeout_s` stays at 225 s.

## Critical User Journeys (CUJs)

### CUJ 1: Claude Code sends a one-module edit and acts on the receipt

*   **Given:** a workspace with `host_accept = true` in `.tokenfrugal.toml`, a venv at `.venv`, and S4 shipped.
*   **When:** Claude Code calls `dispatch_task(agent="coding-l2", task_type="add feature", packet={goal, files:[{path:"scripts/story_film.py"}], accept:["python","-m","unittest","tests.test_story_film"], kind:"edit"})`.
*   **Then:**
    *   The router takes a git-tree baseline, runs the builder without `run_tests`, and runs accept with the workspace venv once the packet files are written.
    *   It returns a receipt of at most 150 tokens: `outcome: done`, `files: ["scripts/story_film.py"]`, `accept: pass`, `next: none`.
    *   Claude Code does not re-run the tests. `get_detail` is not needed.

### CUJ 2: The task fails, and the caller knows what to do next

*   **Given:** the same setup, and the packet's accept command imports a package the venv does not have.
*   **When:** accept runs.
*   **Then:**
    *   The run stops at once with `stop: env_missing` and `next: fix_env`. `error` names the missing module.
    *   No correction run is spent.
    *   The caller installs the package or re-scopes. It does not call `resume_task`, and it does not start a Haiku fallback.

### CUJ 3: The work was already done

*   **Given:** a new packet edit task whose function already exists in the file (an earlier session wrote it), so its accept already passes.
*   **When:** the task is dispatched.
*   **Then:**
    *   Accept runs once before the model starts and passes. The receipt says `outcome: satisfied`, with the note "accept passed before any change", and no model time is spent.
    *   `tasks.status` is `done`, so the dashboard and `sweep_stale` are unaffected.
    *   On a **resume** of a task whose first attempt already changed files against the baseline, the same early pass reports `outcome: done` with those files, not `satisfied`. The work is credited to the task.

### CUJ 4: A legacy caller sees an unverified done

*   **Given:** a legacy call (no packet) whose task text says `Acceptance: loader test passes.` and a workspace without the host-accept opt-in.
*   **When:** the builder finishes.
*   **Then:**
    *   The reply is today's prose plus `checks: none (host accept off)` before `status=`.
    *   Nothing is run on the host.
    *   The task stays `done`. The caller knows it must check the work itself.

### CUJ 5: Codex dispatches on a fresh machine

*   **Given:** a new macOS or Linux machine.
*   **When:** the user runs `pip install -e .` in the tokenfrugal venv, then `python scripts/doctor.py`.
*   **Then:**
    *   `doctor.py` prints the `tool_timeout_sec` line for `~/.codex/config.toml`.
    *   `.codex/config.toml` already points at `tokenfrugal-router`.
    *   Codex's `dispatch_task` call includes `task_type`, and the router finds the git root of the project Codex runs in. No path is configured.

### CUJ 6: A failure with an unknown cause can be diagnosed

*   **Given:** a native server whose command cannot be launched.
*   **When:** a task needing that server starts.
*   **Then:**
    *   The task fails with `stop: env_missing`, and the error names the program.
    *   `get_detail` shows the innermost frame and the last frames under `router/`.
    *   The router's health event and `doctor.py` list the missing program at startup, before any task runs.

## Technical Plan (Architecture)

### Components

The design adds four small modules and changes five existing ones. Nothing new runs as its own process or service.

| Module | New / changed | Job |
| --- | --- | --- |
| `router/outcomes.py` | new (S1a) | The one vocabulary for status, outcome, stop, next and env kind, plus the mapping from today's failure strings. |
| `router/workspace.py` | new (S1b) | Reads `.tokenfrugal.toml`, finds the workspace venv, builds the accept environment, holds the write denylist. |
| `router/packet.py` | new (S2) | Validates a task packet and renders it to prompt text. Used from Python in S2-S3 and exposed as a tool argument in S4. |
| `router/loop_policy.py` | new (S3) | The packet-mode rules for the loop, as pure hooks with no I/O of their own. |
| `router/checker.py` | changed | Accept parsing and the runner (S1b); git-tree baseline, scoped manifest and lint (S2). |
| `router/server.py` | changed | Per-role deadline, correction call, stored task contract, follow-up isolation, `checks:` line, lock, receipt (S4). |
| `router/loop.py` | changed | Calls the policy hooks when a packet is present (S3); a `Budget` object replaces the bare `wait_for`. |
| `router/store.py` | changed | New columns, added in the commit that writes each one; the workspace claim. |
| `router/mcp_client.py`, `router/compose.py` | changed | Process launches name the missing program (S1a). |

### Data flow of one dispatch (after S4)

```text
caller (Claude Code / Codex)
   |  dispatch_task(agent, task_type, task | packet, accept?)
   v
server.dispatch_task ── validate args (REQUIRED_ARGS), packet.validate ── refuse ─> reply, no row
   |
   |  packet edit task: store.create_claimed ── busy ──> workspace_busy / retry_later, no row
   |  other tasks:      store.create
   |                    row: task_type, prompt_sent, accept_json, workspace, plan_id, kind, client
   |  checker.baseline(workspace)  ──> baseline_json (git tree id, or file hashes)
   v
server._execute(deadline = deadline(role))
   |
   |  [packet + host accept on]  accept pre-check ── pass ──> satisfied (or done on resume)
   |
   |  loop.run(budget = 1.5 x timeout_s)
   |     each step: model call -> tool calls
   |        policy.before_call: denylist, repeat guard      (packet only)
   |        tool call via Docker MCP gateway / native server
   |        policy.after_tool: cap output; once all packet files written -> run accept,
   |                           append "accept: PASS|FAIL <first_error>"  (budget paused)
   |     final answer -> policy.on_final: final accept; FAIL and budget left -> continue loop
   |
   |  [legacy]  _check: accept (if host accept on) + lint on changed files
   |            FAIL and model time left >= 45 s -> one correction run (fix prompt at call site)
   |
   |  checker.changes(baseline) -> changed files, outside_scope, no_change / satisfied
   v
store.update (status, outcome, stop, receipt, trail)  ──>  events.emit(task_done | task_failed)
   |
   v
reply:  packet -> receipt v1 JSON (<= 150 tokens)
        legacy -> today's prose + "checks: ..." line before "status="
```

### Outcome vocabulary (`router/outcomes.py`)

Every stored value and every reply value comes from these enums (`enum.StrEnum`, so they serialise as plain strings).

```text
Status   (tasks.status, unchanged values): running | done | failed
Outcome  (tasks.outcome):                  done | satisfied | failed
EnvKind  (receipt env):                    venv | system-python | missing

Stop  (why the run ended)                 default Next
  none                                     none
  accept_failed                            resume
  no_change                                rescope
  scope           (must_not_change hit)    rescope
  out_of_time                              rescope
  max_steps                                rescope
  repeat_guard    (S3)                     rescope
  no_tool_call                             resume
  bad_tool_call                            resume
  bad_answer                               resume
  model_unsupported                        fix_env
  env_missing     (program/module missing) fix_env
  infra           (backend not healthy)    fix_env
  connection                               retry_later
  gpu_busy                                 retry_later
  workspace_busy                           retry_later
  checker         (legacy checks failed)   resume
  error           (unclassified)           fallback

Next: resume | rescope | fallback | fix_env | retry_later | none
```

*   **Escalation:** `next_for(stop, attempts)` returns `fallback` instead of `resume` or `rescope` once a task has had 2 attempts. That matches the existing rule: resume once, then re-scope, then fall back.
*   **Legacy strings:** `stop_from_legacy(failure_reason, error_kind) -> Stop` maps today's strings, so old rows read the same way as new ones.
    *   `timeout` becomes `out_of_time`, and `out of steps` becomes `max_steps`.
    *   `no tool support` becomes `model_unsupported`, and `gpu-busy` becomes `gpu_busy`.
    *   Unknown strings become `error`.

### Accept: parsing and running (`router/checker.py`, `router/workspace.py`)

```text
@dataclass(frozen=True)
AcceptSpec:
    argv:   tuple[str, ...]          # never empty
    env:    dict[str, str]           # from NAME=value tokens or the packet's env
    expect: str | None               # substring of stdout+stderr, from "prints X" or the packet
    source: "packet" | "argument" | "task_line"

@dataclass(frozen=True)
AcceptParse:
    spec: AcceptSpec | None
    note: "" | "no accept" | "prose" | "refused: <reason>"

@dataclass(frozen=True)
AcceptResult:
    ok: bool
    exit: int | None                 # None when it never started or was killed
    secs: float
    first_error: str                 # <= 100 chars, "file:line: message" when a frame is found
    out: str                         # first 400 + last 1200 chars of stdout+stderr
    env_kind: EnvKind
    stop: Stop | None                # env_missing, out_of_time, or None

parse_accept(text: str, source) -> AcceptParse          # one parser, every OS
accept_from_task(task_text: str, accept_arg: str) -> AcceptParse
    # accept_arg wins; else the last Accept:/Acceptance: line of the caller's task text.
    # Template bodies are never parsed.
run_accept_spec(spec, ws: Workspace, timeout: float, cancel: threading.Event) -> AcceptResult
run_accept(cmd: list[str], repo: str, timeout: int = 120) -> tuple[bool, str]
    # kept: wraps run_accept_spec, same return shape and "timed out after Ns" text
```

**Parsing** (legacy strings only; packet `accept` is already an argv list):
1. Take the first backtick span, if any. Otherwise use the whole line.
2. Split with `shlex.shlex(s, posix=True)`, with `whitespace_split=True` and `escape=""`. Quotes group, and backslashes are kept, so `.venv\Scripts\python.exe` survives.
3. Refuse with `refused: accept must be one command; put several steps in a script` if any token outside quotes is `&&`, `||`, `|`, `;`, `>`, `>>` or `<`.
4. Move leading `NAME=value` tokens into `env`.
5. Take trailing `prints <X>` tokens (an optional final `.` is removed) as `expect`, with outer quotes removed.
6. With no backtick span, the line is a command only if `argv[0]` resolves (rules below). Otherwise the note is `prose`, and no accept runs.

**Running:**
*   **Workspace venv:** `TOKENFRUGAL_ACCEPT_VENV`, else `<ws>/.venv`, else `<ws>/venv`.
*   **Interpreter:**
    *   An `argv[0]` whose basename matches `python3?(\.exe)?` or `py(\.exe)?` becomes the venv's interpreter. A `-X.Y` flag after `py` is dropped.
    *   With no venv, the system `python` on PATH is used, and `env_kind` is `system-python`. The router's own interpreter is never used.
*   **Other programs:**
    *   An `argv[0]` containing `/` or `\` resolves against the workspace.
    *   Any other name resolves with `shutil.which` against the accept PATH, with the venv's `Scripts` or `bin` folder first.
    *   If it does not resolve, the result is `stop=env_missing`, naming the program.
*   **Environment:** the allowlist in the Security section, then `VIRTUAL_ENV`, then `PYTHONIOENCODING=utf-8`, then the names in `accept_env_passthrough`, then `spec.env`.
*   **Process:**
    *   `cwd` is the workspace and `stdin` is DEVNULL. stdout and stderr go to temporary files.
    *   On Windows the child is in a Job Object with kill-on-close. On POSIX it gets `start_new_session=True`, and the whole group is killed.
    *   A `finally` kills the tree on timeout, on cancel, or on any exception.
*   **Result:**
    *   Pass means exit code 0, plus `expect` (if set) found in stdout or stderr.
    *   `first_error` is the last line matching `\b\w*(Error|Exception)\b|AssertionError`, else the first `FAIL:` or `FAILED` line.
    *   `ModuleNotFoundError` or `No module named` gives `stop=env_missing`.

### Time budgets

```text
ACCEPT_TIMEOUT     = env TOKENFRUGAL_ACCEPT_TIMEOUT, default 60 s
model_budget(role) = 1.5 x role_timeout(role)          # role_timeout = timeout_s or TASK_TIMEOUT
deadline(role)     = env TOKENFRUGAL_TASK_DEADLINE, else
                     1.5 x role_timeout(role) + 2 x ACCEPT_TIMEOUT + 30
```

*   **First run:** it may use up to `role_timeout`.
*   **Correction run** (legacy) or **continued loop** (packet): it gets `model_budget` minus the time already used. If less than 45 s is left, it does not run, and the stop is `out_of_time`.
*   **Each accept run:** it gets `min(ACCEPT_TIMEOUT, deadline - elapsed)`.
*   **`Budget`** in `loop.py` replaces `asyncio.wait_for(_run, limit)`. It is a monotonic-clock allowance with `pause()` and `resume()`. Accept runs inside a pause, so accept time counts against the deadline, not the model budget.
*   **Enforcement:**
    *   `_execute` checks `deadline` itself. Its timeout branch writes the failed row and the `task_failed` event.
    *   It also catches `CancelledError`, writes the row with `stop=out_of_time`, and re-raises.
*   **Worked numbers:**
    *   code-l2 (225 s): model budget 337 s, deadline 487 s.
    *   builder (130 s): 195 s and 345 s.
    *   code-l4 (450 s): 675 s and 825 s.
*   **Client timeouts:** `doctor.py` reports the largest deadline among builder-model roles plus 60 s as the minimum Codex `tool_timeout_sec`.

### Change detection (`router/checker.py`, S2)

```text
baseline(ws, task_files) -> Baseline
    git workspace:  GIT_INDEX_FILE=<tmp> git add -A ; git write-tree      -> {"kind":"git-tree","tree":<sha>}
                    untracked non-ignored size > 200 MB                    -> hash task_files only, partial=true
    no git:         sha256 of task_files                                   -> {"kind":"hash","files":{path: sha|null}}

changes(ws, baseline, task_files, must_not_change) -> Changes
    changed:        git diff --name-only -z <base_tree> <now_tree>   (or hash compare)
    task_changed:   changed ∩ task_files
    outside_scope:  changed - task_files
    scope_violation: changed ∩ must_not_change (glob, ** aware)
```

*   **Task files:** for a packet, its `files`. For a legacy task, the paths named in the task text, using the same extraction preread uses.
*   **Path comparison:** case-insensitive on Windows and macOS.
*   **Lint:** runs on `changed` only, so another session's dirty file can't fail the task.
*   **Edit vs analyze:** `kind` comes from the packet. For legacy tasks it comes from `task_type` in {add test, fix bug, add feature, refactor, edit, write}. Anything else is `analyze`.
*   **The no-change rule** applies to packet `edit` tasks only:
    *   `task_changed` is empty and accept ran and passed: `satisfied`.
    *   `task_changed` is empty otherwise: `no_change`.
*   **Legacy tasks** are never failed by this rule.

### Workspace claim (`router/store.py`, S2)

```text
create_claimed(row_fields, ws_key: str, resume_of: str | None) -> task_id | None
    BEGIN IMMEDIATE
      SELECT 1 FROM tasks WHERE workspace_key = ? AND kind = 'edit' AND packet_json IS NOT NULL
         AND status = 'running' AND heartbeat > now - 2 * HEARTBEAT_EVERY AND id != coalesce(?, '')
      none found -> INSERT the new row (or UPDATE the resumed row) as running with workspace_key ; COMMIT ; id
      found      -> ROLLBACK ; None
ws_key = os.path.normcase(os.path.realpath(workspace))
```

*   Packet edit tasks, and resumes of them, claim the workspace.
*   Legacy tasks, follow-ups, analyze tasks and `content_pipeline` never claim it.
*   A refused claim creates no row.

### Task packet v1 (`docs/designs/subagent-runtime/packet.schema.json`, validated in `router/packet.py`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "tokenfrugal task packet v1",
  "type": "object",
  "required": ["v", "goal", "kind", "files"],
  "additionalProperties": false,
  "properties": {
    "v":               {"const": 1},
    "goal":            {"type": "string", "minLength": 1, "maxLength": 400},
    "kind":            {"enum": ["edit", "analyze"]},
    "requirements":    {"type": "array", "maxItems": 5, "items": {"type": "string", "maxLength": 200}},
    "files":           {"type": "array", "minItems": 1, "maxItems": 3, "items": {
                          "type": "object", "required": ["path"], "additionalProperties": false,
                          "properties": {
                            "path":  {"type": "string", "pattern": "^(?!/)(?!.*\\.\\.)[^\\\\:]+$"},
                            "new":   {"type": "boolean", "default": false},
                            "lines": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2}}}},
    "accept":          {"type": "array", "minItems": 1, "items": {"type": "string"}},
    "env":             {"type": "object", "additionalProperties": {"type": "string"}},
    "expect":          {"type": "string", "maxLength": 200},
    "must_not_change": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
    "context":         {"type": "string", "maxLength": 1500}
  }
}
```

*   **Validation** is written by hand in `packet.py`, with no new dependency. A test checks that `packet.py` and the schema file accept and reject the same 10 example packets.
*   **`render(packet) -> str`** produces the prompt text the model sees: goal, requirements, the files with `(new)` and line ranges, context, and an `Accept:` line for the legacy path. The replay runner uses the same rendering to send a packet to today's code.
*   **Preread:** packet files go to preread, which is raised from 2 paths to 3 for packet tasks.

### Receipt v1 (S4)

```json
{"v":1,"task_id":"6c4f3ca6d6","outcome":"failed","stop":"accept_failed","next":"resume",
 "files":["scripts/story_film.py"],"accept":"fail",
 "error":"tests/test_story_film.py:41: AssertionError: 'scene-1' not found",
 "env":"venv","steps":7,"secs":212}
```

*   **Always present:** `v`, `task_id`, `outcome`, `stop`, `next`, `accept`.
*   **`accept` values:**
    *   `pass` or `fail`: it ran;
    *   `none`: there is no accept;
    *   `off`: host accept is off;
    *   `prose`: the acceptance line was prose.
*   **Omitted when empty:** `files` (at most 3 entries, then `"+N"`), `outside_scope` (at most 3, then `"+N"`), `error` (at most 100 characters), `env`, `note`.
*   **Always numbers:** `steps` and `secs`.
*   **Size:** a test builds the largest possible receipt, using long real paths from `tasks.db`, and asserts it is at most 150 tokens by the counter in `summarize.py`.

### Workspace configuration (`<workspace>/.tokenfrugal.toml`, read with `tomllib`)

```toml
host_accept = false                 # true lets tokenfrugal run accept commands on this machine
accept_env_passthrough = []         # extra environment names accept may see, e.g. ["DATABASE_URL_TEST"]
```

*   A missing file means both defaults apply.
*   `TOKENFRUGAL_HOST_ACCEPT=1` turns host accept on for the router process and overrides the file. It is meant for CI and for this repo's own checkout.
*   Unknown keys are ignored, with one warning in the health event.

### Security model for host accept

**What it does.** With `host_accept = true`, tokenfrugal runs the caller's accept command on the user's machine, in the workspace, after the local model has edited files. The model does not write the command. It does write the code the command runs.

**Controls:**
*   **Opt-in per workspace, default off.** With it off, no accept command runs on the host, legacy or packet. The reply says `checks: none (host accept off)` or `accept: off`. `doctor.py` shows the state.
*   **Write denylist** (enforced in the loop before a write, edit or move call is sent, whenever host accept is on). Refused paths:
    *   anything under `.git/`, `.venv/`, `venv/` or `node_modules/.bin/`;
    *   any file named `conftest.py`, `sitecustomize.py`, `usercustomize.py`, `*.pth`, `setup.py`, `pyproject.toml`, `package.json`, `.npmrc` or `Makefile`.
    *   A packet that lists one of these paths in `files` allows that one path.
*   **Environment allowlist:**
    *   Allowed names: `PATH`, `PATHEXT`, `SYSTEMROOT`, `WINDIR`, `COMSPEC`, `TEMP`, `TMP`, `TMPDIR`, `HOME`, `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `APPDATA`, `LOCALAPPDATA`, `LANG`, `LC_*`, `TERM`, `TZ`, `SHELL`, `USER`, `USERNAME`, `LOGNAME`.
    *   Plus the passthrough names and the spec's env.
    *   Names are compared case-insensitively on Windows. Values from the spec's env are never logged.
*   **Process-tree kill** on timeout or cancel (Job Object or process group). `stdin` is closed, and output goes to files, so a hung child cannot block the router.
*   **One command only:** shell operators are refused, and there is no shell.

**What it does not protect:**
*   **Network access.** Model-written code can reach the network.
*   **The user's home folder.** Model-written code can read `~/.ssh`, `~/.aws`, git and gh credential stores, and `~/.docker/mcp/secrets`, with the user's permissions.
*   **Files outside the denylist.** A test file the model writes can do anything the user can do. The allowlist only keeps the router's own environment variables out of the child.
*   **Prompt injection.** Text in files the model reads can steer it into writing such code.

The control that matters is the opt-in. Turn it on only for repos whose content you would run yourself. Containerised accept is deferred (D9).

### Measurement plan (S2)

**Corpus layout:**

```text
Benchmark/replay/
  README.md                  how to add a task; rules (<= 3 files, check script independent of model output)
  <id>/                      fb-001 ... fb-009, rw-010 ... rw-020
    task.toml                repo = "<name>", base_commit = "<sha>", agent = "coding-l2", task_type = "..."
    packet.json              packet v1
    check.py                 hidden check; exit 0 = task truly done; never shown to the model
  results/<arm>-<YYYYMMDD>.jsonl   one line per run: id, arm, run, outcome, stop, check_ok, secs, steps, peak_ctx
```

**Runner, `scripts/replay.py`:**
```text
--arm NAME --router PATH --repo NAME=PATH ... [--env K=V ...] [--runs 3]
```
*   **Per task and run:**
    *   it creates a `git worktree` of the repo at `base_commit` in a temporary folder;
    *   it starts the router from `--router` (a checkout) with `CC_WORKSPACE` set to the worktree and `TOKENFRUGAL_HOST_ACCEPT=1`;
    *   it dispatches the packet: as a packet for arms that have `packet.py`, and as `render(packet)` text through `dispatch_task` for older checkouts;
    *   it runs `check.py` with the worktree's venv, records one line, and removes the worktree.
*   **Settings:** temperature is the production value (`LOCAL_LLM_TEMPERATURE` unset, so 0.0), and the Ollama digest of the model is recorded.

**Report, `scripts/replay_report.py`:**
*   **Task result:** a task passes in an arm when at least 2 of its 3 runs end `done` or `satisfied`, with `check_ok` true and no scope violation.
*   **Gate:**
    *   at least 16 of 20 tasks pass in the candidate arm;
    *   and a one-sided exact sign test on the tasks whose result differs between baseline and candidate gives p < 0.05;
    *   and no run in the candidate arm is a false success (`done` or `satisfied` with `check_ok` false).

**Arms:**

| Arm | Router | Settings | When |
| --- | --- | --- | --- |
| `base` | commit before S1a | defaults | S2, once |
| `s2` | S2 head | defaults | S2 gate |
| `think-low`, `think-off` | S2 head | `TOKENFRUGAL_THINK=low` or `off` | S2, before S3 |
| `q4` | S2 head | `TOKENFRUGAL_MODEL_BUILDER=hf.co/unsloth/Qwen3.5-4B-GGUF:Q4_K_M` | S2 |
| `s3`, `s4` | S3 head, S4 head | defaults | after each stage |

*   The thinking arm with the best gate result sets the default, and the unified `code-l2` timeout comes from that arm's 90th-percentile run time.
*   `q4` decides D10: within 5 points of `s2`, with zero false successes, means `doctor.py` recommends it on GPUs with less than 8 GB free.

## Alternatives Considered

Each alternative below was raised in the brainstorm or one of its two Goldfish reviews. Each was rejected for the reason given.

### Alternative A: Haiku writes the packets

*   **Pros:** it keeps the current global rule. Sonnet spends no tokens writing task specs.
*   **Cons:**
    *   A Haiku subagent's cold start costs about 65K tokens, more than the whole local task saves.
    *   Filling in files and line ranges means reading the files again, which the main agent has already done.
    *   Codex has no Haiku tier, so Codex would need a different path.
    *   Two logged Haiku fallbacks (106,481 and 120,842 tokens) already went past the 100K price step.
*   **Reason for rejection:** it costs more than it saves, and it does not exist for one of the two clients (D3).

### Alternative B: one global switch from prose replies to JSON

*   **Pros:** one reply format, and one code path in `server.py`.
*   **Cons:** it breaks every existing reader at once:
    *   `scripts/bench_checks.py` and `tests/test_router_bc.py`;
    *   the error-kind and diagnostics tests;
    *   the Codex wrapper and `plan.record_run`;
    *   any caller that reads `status=` lines.
*   **Reason for rejection:** a call with a packet asks for the new contract and gets JSON. A call without one keeps prose. That lets old and new callers coexist with no flag (D4).

### Alternative C: measure the gate on live tasks

*   **Pros:** it reflects real work, and no corpus has to be built.
*   **Cons:**
    *   At 20-30 tasks the 95% interval is about ±15-18 points, so 63% and 80% cannot be told apart.
    *   Live tasks are not repeatable, so two arms cannot be compared on the same task.
*   **Reason for rejection:** the gate could not separate a real improvement from noise. The corpus gives a paired comparison, and live fallback counts stay as a secondary signal (D1).

### Alternative D: host accept on by default

*   **Pros:** no opt-in step. Legacy `Accept:` lines keep running exactly as today.
*   **Cons:** model-written code then runs on every installer's machine, with network access and the user's home folder. That includes tests, `conftest.py`, `.pth` files and prompt-injected content. Stripping environment variables does not change that.
*   **Reason for rejection:** this is unsafe for other people's machines. The opt-in makes the trust decision explicit, per workspace (D5).

### Alternative E: keep the container `run_tests` as the only test signal

*   **Pros:** model code never runs on the host (`--network none`, read-only, pids limit).
*   **Cons:**
    *   The container has none of the repo's dependencies. FB-002 spent 5 steps on missing `yaml` and `dotenv`.
    *   The model and the harness see different results, so "done" stays unverified.
*   **Reason for rejection:** it gives the model a wrong signal and the caller no verified result. The right long-term form is a per-workspace container built from the repo's lockfile. That is deferred in D9 until host accept proves to be the obstacle.

### Alternative F: strip secret-looking environment variables with a regex

*   **Pros:** it changes the least, because most of the router's environment passes through.
*   **Cons:**
    *   It strips too much: `TOKEN` matches `TOKENFRUGAL_*`, and `AUTH` matches `GIT_AUTHOR_*` and `SSH_AUTH_SOCK`.
    *   It misses real secrets: `DATABASE_URL`, `*_DSN`, `*_PAT`, `*_PWD`, and proxy URLs with credentials.
*   **Reason for rejection:** a denylist always lags new secret names. The allowlist, plus `accept_env_passthrough`, is predictable (F3).

### Alternative G: a different `shlex` mode per OS

*   **Pros:** it matches each OS's own quoting rules.
*   **Cons:** one string gives different argv on Windows and Linux, so a Linux CI run proves nothing about Windows. `posix=False` also mishandles escaped quotes.
*   **Reason for rejection:** one parser behaves the same everywhere. Packets take an argv list and avoid parsing altogether (F3).

### Alternative H: a lease file for the workspace lock, reusing `gpu_lease.py`

*   **Pros:** it reuses the lease code, with heartbeat and stale takeover.
*   **Cons:**
    *   `gpu_lease.py` is hard-wired to one resource (`gpu.json`, `HOLDERS`, container takeover).
    *   `compose.lease_release` deletes files in the same folder.
    *   A blocking wait inside an async handler stalls the router.
*   **Reason for rejection:** the `tasks` table already has heartbeats and stale handling. A claim in one `BEGIN IMMEDIATE` transaction needs no new file and never blocks (D7).

### Alternative I: hash every changed and untracked file in Python

*   **Pros:** no dependence on git internals, and the same method for git and non-git folders.
*   **Cons:** it reads every untracked file, which can be gigabytes in repos with media renders. It also ignores `.gitignore` unless that logic is rebuilt.
*   **Reason for rejection:** `git write-tree` with a temporary index uses git's stat cache and respects `.gitignore`. Python hashing remains only for non-git workspaces, limited to the task files (F5).

### Alternative J: fresh-start resume in S1

*   **Pros:** a 4B model gets a short, true picture of the current state instead of replaying a failed 20K-token trail.
*   **Cons:**
    *   It changes the `resume_task` docstring ("from its saved conversation") and the failure hint.
    *   Two tests assert those texts.
    *   It would break the one-surface-change rule in S1.
*   **Reason for rejection (for S1):** it moves to S4. The resume false successes are fixed by the baseline and the `no_change` rule in S2, not by fresh resume.

### Alternative K: one global outer deadline equal to `TASK_TIMEOUT`

*   **Pros:** one number to reason about.
*   **Cons:**
    *   `TASK_TIMEOUT` already means the default role timeout.
    *   At 540 s it is below code-l2's own worst case (570 s).
    *   It would kill the db roles (600 s) and media roles (900 s) that work today.
*   **Reason for rejection:** the deadline has to scale with the role. `deadline(role)` is computed per role, and `TASK_TIMEOUT` keeps its meaning (F4).

### Alternative L: fix the dropped prompt inside `run()`

*   **Pros:** every caller that passes `prompt` and `messages` gets the prompt appended.
*   **Cons:** `resume_task`, `ask_followup` and `content_pipeline.py:73` already pass both. Each would then send the original prompt a second time.
*   **Reason for rejection:** the fix goes at the one call site that needs it, the correction run, and leaves `run()` alone (F1).

### Alternative M: accept after every write in packet mode

*   **Pros:** the model gets test feedback as early as possible.
*   **Cons:** a multi-file task fails while half-edited. Each run costs up to 60 s against timeouts, the largest failure class.
*   **Reason for rejection:** accept runs once all packet files are written, and again at the final answer (D6).

### Alternative N: loop features from the original sketch

The pruned model view, the state note, phase-scoped tools, constrained decoding, the shared board and `route()`.
*   **Pros:** each addresses a failure seen in other agent systems.
*   **Cons:** none of the logged failures here comes from context overflow (median peak 5.4K tokens). Malformed tool calls are about 2% of failures, and there is one builder role to route to.
*   **Reason for rejection:** none has evidence here. Each has an entry criterion in D9 and comes back only if the corpus shows its failure.

### Alternative O: a script that generates the Codex config

*   **Pros:** it can write this machine's absolute interpreter path and the timeout line.
*   **Cons:**
    *   It is one more script to maintain.
    *   It writes user files.
    *   If it set `CC_WORKSPACE`, every Codex project would be pinned to one repo.
*   **Reason for rejection:** a `tokenfrugal-router` console script from `pyproject.toml` gives every client the same path-free command. `doctor.py` prints the one timeout line for the user to add (F6).

### Alternative P: make `task_type` optional

*   **Pros:** no client can fail by leaving it out, and `with_templates` already handles an empty value.
*   **Cons:** it changes the `dispatch_task` docstring and signature semantics in S1.
*   **Reason for rejection (for S1):** `REQUIRED_ARGS` plus a test of the Codex wrapper catches the failure without touching the surface. It can be reconsidered in S4.

## Non-Functional Requirements

**Security and privacy.** See "Security model for host accept" in the Technical Plan. Also:
*   **Packet `env` is not for secrets.** `accept_json` stores the packet's `env` values so a resume can re-run accept, and the `dispatch_task` call already carried them in plain text. A secret the accept command needs goes in `accept_env_passthrough`. Its value is read from the router's environment at run time and never stored. The `accept_run` event logs names only.
*   Secrets stay as Docker secret files in `~/.docker/mcp/secrets`, as today.

**Performance:**
*   **Baseline:** `git add -A` into a temporary index plus `git write-tree` takes well under a second on this repo. It is capped at 200 MB of untracked, non-ignored files, after which only the task files are hashed.
*   **Accept:** at most two accept runs per packet task in S3 (the pre-check and the final one), plus one each time all packet files have been written again after a failure. Accept time does not count against the model budget.
*   **Reply size:** at most 150 tokens for a receipt. Legacy replies grow by one line.

**Compatibility:**
*   **Unchanged:** `resume_task`, `ask_followup`, `get_detail`, `plan_*`, `studio_*`, `bench.py`, `bench_checks.py`, compose project handling and the GPU lease. Any behaviour change to them is listed in the release notes below.
*   **Old `tasks.db` rows:** they keep working. Every new column has a NULL fallback (F2 table).
*   **Python:** 3.11+ is required, as today (`tomllib`, `enum.StrEnum`).

**Portability:**
*   No paths in committed config.
*   `requirements.txt` gets `mcp` pinned to the installed version. It is unpinned today, which breaks the portability rule.
*   Parser and runner tests run on Windows, macOS and Linux in CI.
*   The Windows Job Object uses `ctypes`, so there is no new dependency.

**Rollout and rollback.** Each fix is one commit with its tests, merged on its own. A rollback reverts that commit. The new columns stay, since SQLite `DROP COLUMN` is not needed. Old code ignores them.

### Release notes (user-visible changes)

| Stage | Change | What the user does |
| --- | --- | --- |
| S1a | `.mcp.json` and `.codex/config.toml` run `tokenfrugal-router` instead of a venv path. | Run `pip install -e .` in the tokenfrugal venv. Existing clients keep working until their config is replaced. |
| S1a | `doctor.py` checks Codex's `tool_timeout_sec`. | Add the printed line to `~/.codex/config.toml`, under `[mcp_servers.tokenfrugal]`. |
| S1a | A missing program is reported by name, never as a bare `WinError 2`. | None. |
| S1b | **Legacy `Accept:`/`Acceptance:` lines stop running on the host unless the workspace opts in.** The reply says `checks: none (host accept off)`. | To keep today's behaviour, add `host_accept = true` to `<workspace>/.tokenfrugal.toml`, or set `TOKENFRUGAL_HOST_ACCEPT=1`. |
| S1b | Accept commands with `&&`, `\|`, `;`, `>` are refused. | Put several steps in a script. |
| S1b | Accept uses the workspace venv, not the router's Python. | None. If there is no venv, the reply says `env: system-python`. |
| S1c | `ask_followup` works only on finished tasks. Its answer is stored as a child task and does not change the original. | Use `resume_task` for failed tasks. |
| S1c | `resume_task` refuses a task that is still running. | Wait, or check `get_detail`. |
| S2 | The `files_changed` line lists only changes since the task's first dispatch. Other changes appear as `outside_scope`. | None. |
| S4 | `dispatch_task` accepts `packet` and returns a receipt; adds `task_status` and `wait=False`; `resume_task` starts from the current files with a short note instead of replaying the failed conversation. | Update the Codex wrapper and agent instructions (shipped in the same release). |

### Future Improvements

*   **Containerised accept:** a per-workspace image built from the repo's lockfile, so accept no longer needs host trust (D9).
*   **Optional `task_type`** in S4 or later (Alternative P).
*   **The D9 items**, each when its entry criterion is met.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### How the work is executed

*   **Executors:** this repo uses Haiku subagents (`Agent`, `model: "haiku"`), not `dispatch_task`, per the CLAUDE.md exception. Each numbered step below is one Haiku task. Its spec carries:
    *   the files it may touch;
    *   the files it must not change;
    *   one acceptance command;
    *   a tool-call limit of 25, or 35 for steps marked *large*.
*   **Review:** Sonnet reviews each diff, runs the full offline suite, and commits. One step is one commit. No step starts until the previous commit passes the full suite: `PYTHONPATH=. python -m unittest discover -s tests -t . -q`.
*   **Plan tracking:** each step is a `plan_add` task. It is marked done with its commit sha.
*   **Fallback log:** every Haiku execution is logged in `docs/designs/fallback-execution-log.md`, with its sequence, tool calls and steps. That is a standing rule for this repo.
*   **Tool surface:** S1-S3 must not change any `@mcp.tool()` signature or docstring. Each step's review checks that a `git diff` on `router/server.py` shows no change to a decorated function's `def` line or docstring.

### Stage S1a

#### Step 1. F0: outcome vocabulary and measurement fields

| File | Change | Rationale |
| --- | --- | --- |
| `router/outcomes.py` | **Create** | `Status`, `Outcome`, `Stop`, `Next` and `EnvKind` StrEnums; `DEFAULT_NEXT: dict[Stop, Next]`; `next_for(stop, attempts) -> Next` (attempts ≥ 2 turns resume/rescope into fallback); `stop_from_legacy(failure_reason, error_kind) -> Stop`. This is the one vocabulary every later step uses. |
| `router/store.py` | Modify | Add `client TEXT`, `model_tag TEXT`, `peak_ctx INTEGER` and `outcome TEXT` to the migration tuple (`store.py:35`). Add them to `update()`'s accepted fields. |
| `router/server.py` | Modify | `_ClientSeen.on_initialize` stores `client_info.name` in a module variable. `store.create` callers pass `client`. `_execute` writes `model_tag` (the resolved Ollama tag from `role["model"]` through `config`), `peak_ctx` and `outcome`. `kind_hint` gains `env_missing` and `workspace_busy`. `peak_ctx` reuses what exists: `loop._count` already keeps `peak` in `USAGE`. Each exit path in `_execute` (`:228`, `:265`, `:291`) calls `take_usage(tid)` once into a local variable. It writes `peak` to the row, then spreads the same dict into the usage event, which already carries `peak`. The three usage events gain `error_kind` (None on success). `router/loop.py` and `router/events.py` are not changed in this step. |
| `tests/test_outcomes.py` | **Create** | Every legacy `failure_reason` and `error_kind` maps to a `Stop`. Every `Stop` has a default `Next`. `next_for` escalates at 2 attempts. Values serialise as plain strings. |
| `tests/test_store_idempotence.py` | Modify | The migration runs twice on an old schema without error, and the new columns are NULL on old rows. |
| `tests/test_error_kind.py`, `tests/test_diagnostics.py` | Modify | Add cases for the new hint kinds only. Existing assertions are unchanged. |

*   **Schema:** four nullable columns. Old rows read NULL, meaning unknown.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_outcomes tests.test_store_idempotence tests.test_error_kind tests.test_diagnostics -q`

#### Step 2. F7: diagnosable failures

| File | Change | Rationale |
| --- | --- | --- |
| `router/loop.py` | Modify | Add `frames_of(exc) -> list[str]`, which walks the whole exception group (not just `leaf()`'s first member). It returns the innermost frame plus the last 3 frames whose file is under `router/`, as `file:line:function`. |
| `router/server.py` | Modify | In the `_execute` except branch, for error kinds `unknown` or `error`: add `frames` to the `task_failed` event, and store them in the trail as a `frames` entry. `_trail_line` gains a `frames` branch, so `get_detail` prints them. The `error` column keeps the short form. |
| `router/mcp_client.py` | Modify | Wrap the stdio server launch (`stdio_client(params)`, `:201-202` and `:215-223`) and the gateway `create_subprocess_exec` (`:42`). An `OSError` re-raises as `FileNotFoundError(f"program not found: {argv0}")`, chained to the original. |
| `router/compose.py` | Modify | The same wrapper around `_compose_once`'s `create_subprocess_exec`. |
| `router/server.py` (startup) | Modify | At start: resolve `docker`, `git`, `npx`, `hyperframes` and every `NATIVE_SERVERS[*]["command"]` with `shutil.which`, and put the missing names in the first `health` event as `missing=[...]`. |
| `router/outcomes.py` | Modify | `stop_from_legacy` maps `program not found` to `env_missing`. |
| `scripts/doctor.py` | Modify | Print the same missing-program list. It reuses the resolver, so the router and doctor agree. |
| `docs/designs/fallback-attempts.jsonl` | Modify | On lines 4 and 6, add a `note: "cause unconfirmed, see F7"` field. Other fields are unchanged. |
| `docs/designs/fallback-execution-log.md` | Modify | Annotate the `A_builder_path` row (`:140`) the same way. |
| `tests/test_diagnostics_frames.py` | **Create** | Inject `FileNotFoundError` at `open_role`, at `compose.backends` and at `list_tools`, using fakes. Each produces a `task_failed` event with frames and a `program not found: <name>` message. A tool-call exception still goes back to the model, as today. |

*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_diagnostics_frames tests.test_diagnostics -q`

#### Step 3. F6: installation and client configuration

| File | Change | Rationale |
| --- | --- | --- |
| `pyproject.toml` | Modify | Add `dependencies` (copied from `requirements.txt`, pinned) and `[project.scripts] tokenfrugal-router = "router.server:main"`. Add `[tool.setuptools] packages = ["router", "router.skills"]` and package data for `tf-roles.yaml`, `skills/**/SKILL.md` and JSON files. |
| `requirements.txt` | Modify | Pin `mcp` to the version installed in `.venv`, which is unpinned today. |
| `router/server.py` | Modify | Add `def main(): mcp.run()`; `if __name__ == "__main__": main()`. Add `REQUIRED_ARGS = ("agent", "task", "task_type")`. `dispatch_task`'s existing runtime checks read from it, with no signature or docstring change. |
| `.mcp.json` | Modify | `"command": "tokenfrugal-router"`, `"args": []`. |
| `.codex/config.toml` | Modify | `command = "tokenfrugal-router"`, `args = []`, and no `CC_WORKSPACE`. A comment points to `doctor.py` for `tool_timeout_sec`. |
| `.codex/agents/tokenfrugal.toml` | Modify | The example call names `agent`, `task_type`, `task` and `accept`. Accept is written as one command that exits non-zero on failure. The rule stays: resume once, then report. There is no `next` instruction yet (S4). |
| `scripts/doctor.py` | Modify | Read `~/.codex/config.toml` with `tomllib`. Compute `max(deadline(role)) + 60` over builder-model roles (F4 provides `deadline`; until F4 lands, use `1.5 x timeout_s + 150`). Print the exact `tool_timeout_sec = N` line when the value is missing or lower. Never write the file. |
| `README.md` | Modify | The install section becomes `pip install -e .` and `python scripts/doctor.py`. The client config examples use `tokenfrugal-router`. |
| `CLAUDE.md` | Modify | The "Register in an MCP client" line uses `tokenfrugal-router`. |
| `tests/test_codex_wrapper.py` | **Create** | Parse `.codex/agents/tokenfrugal.toml`, find the example `dispatch_task(...)` call, and assert every name in `REQUIRED_ARGS` appears. Parse `.codex/config.toml` and `.mcp.json`, and assert neither contains a path separator in `command`. |
| `tests/test_entrypoint.py` | **Create** | `router.server.main` exists and is the `pyproject.toml` script target. Parsing `pyproject.toml` with `tomllib` finds `tokenfrugal-router`. |

*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_codex_wrapper tests.test_entrypoint -q`, plus a manual check: `pip install -e .`, then `tokenfrugal-router` starts and waits on stdin (Ctrl+C to stop).

### Stage S1b

#### Step 4. F3: accept parser and runner (*large*)

| File | Change | Rationale |
| --- | --- | --- |
| `router/workspace.py` | **Create** | `Workspace` dataclass: `root`, `key` (normcase realpath), `host_accept: bool`, `env_passthrough: tuple[str, ...]`, `venv: Path \| None`. `load_workspace(root) -> Workspace` reads `.tokenfrugal.toml` (`tomllib`; missing file means defaults) and `TOKENFRUGAL_HOST_ACCEPT` / `TOKENFRUGAL_ACCEPT_VENV`. `ENV_ALLOWLIST`; `accept_env(ws, spec_env) -> dict`, compared case-insensitively on Windows. `DENYLIST_DIRS`, `DENYLIST_NAMES`, `denied(path, allowed: set[str]) -> bool` (used in S2). |
| `router/checker.py` | Modify | Add `AcceptSpec`, `AcceptParse`, `AcceptResult`, `parse_accept`, `accept_from_task`, `run_accept_spec` and the helpers `_resolve_argv0`, `_first_error` and `_kill_tree`. `_kill_tree` uses a Job Object via `ctypes` on Windows and `os.killpg` on POSIX. `run_accept(cmd, repo, timeout)` becomes a wrapper with the same return shape and timeout text. |
| `router/server.py` | Modify | `accept_cmd(text)` keeps returning `list[str] \| None` (now `accept_from_task(text, "").spec.argv`). `_check` takes the raw task text (`store.get(tid)["prompt"]`), not the composed prompt. It loads the `Workspace`. With host accept off, it skips accept and records the reason. `_report` adds the `checks:` line: `checks: ok`, `checks: FAILED (<item>)` or `checks: none (<reason>)`, where reason is one of `no accept command`, `acceptance line is prose`, `host accept off`, `refused: ...`. It is placed before `status=`. `dispatch_task`'s `accept=` string goes through `parse_accept`; a refusal returns the reason with no row created. `env_missing` from accept skips the correction run. |
| `scripts/bench_checks.py` | Modify | `_TRAILER` (`:167`) also strips `checks:` lines. |
| `tests/test_accept_parse.py` | **Create** | A table of at least 12 cases: plain argv; `python -c "..."` with nested quotes; `PYTHONPATH=. python -m unittest ...`; `.venv\Scripts\python.exe -m pytest`; backtick span inside prose; prose line; `prints True.`; `prints "OK"`; a `-c` body containing the word prints; `&&` refused; `|` inside quotes allowed; empty line. The FB-001, FB-006, FB-009 and class A lines are included verbatim from `fallback-attempts.jsonl`. |
| `tests/test_accept_run.py` | **Create** | Venv interpreter substitution (a fake venv folder with a stub interpreter script). `py -3.12` drops the flag. An unknown program gives `env_missing`. `expect` is found on stderr. A timeout kills a grandchild: a child spawns a sleeping grandchild that writes its pid, and the test asserts the pid is gone. Cancel through the `threading.Event`. Allowlisted names pass and others are dropped (with a sentinel variable). `No module named` gives `env_missing`. Output is cut to 400+1200. |
| `tests/test_workspace.py` | **Create** | `.tokenfrugal.toml` missing, true or false; the env override; unknown key warning; case-insensitive names on Windows (skipped elsewhere). |
| `tests/test_checker.py` | Modify | Keep `:73-83` unchanged (the wrapper). Add wrapper cases for an argv with spaces in quotes. |
| `tests/test_checker_stage.py` | Modify | `:25-31`: `accept_cmd` still returns a list, and an `Acceptance:` line is now matched. Add the `checks:` line assertions. Cases that expect accept to run set `TOKENFRUGAL_HOST_ACCEPT=1` in `setUp`. |
| `tests/test_router_bc.py` | Modify | `:54-76`: as above. The reply text gains the `checks:` line before `status=`. |
| `.github/workflows/tests.yml` | **Create** | Matrix of `windows-latest`, `macos-latest` and `ubuntu-latest` on Python 3.11. Runs `pip install -r requirements.txt`, then the offline suite. This is the CI the parser tests need. There is no workflow today. |
| `.gitignore` | Modify | Nothing to add for `.tokenfrugal.toml`: it is meant to be committed per workspace. Add a comment saying so. |
| `.tokenfrugal.toml` | **Create** | `host_accept = true` for this repo's own checkout, with a comment explaining the trust decision. |

*   **Schema:** none (accept is still parsed from the stored prompt; `accept_json` arrives in Step 7).
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_accept_parse tests.test_accept_run tests.test_workspace tests.test_checker tests.test_checker_stage tests.test_router_bc -q`

#### Step 5. F4: per-role deadline

| File | Change | Rationale |
| --- | --- | --- |
| `router/config.py` | Modify | Add `ACCEPT_TIMEOUT` (`TOKENFRUGAL_ACCEPT_TIMEOUT`, default 60), `TASK_DEADLINE_OVERRIDE` (`TOKENFRUGAL_TASK_DEADLINE`, default unset) and `CORRECTION_FLOOR_S = 45`. `TASK_TIMEOUT` is unchanged. |
| `router/loop.py` | Modify | Add `class Budget(total: float)` with `remaining()`, `pause()` / `resume()` (a context manager) and `spent()`. Add `deadline(role)`. `run()` takes an optional `budget`; when given, `_run` checks `budget.remaining()` before each model call and raises `LoopError("task timed out ...")` with today's text. Without a budget, today's `asyncio.wait_for(_run, role_timeout)` path is unchanged, so `bench.py`'s patching of `loop.TASK_TIMEOUT` still works. |
| `router/server.py` | Modify | `_execute` creates `Budget(1.5 x role_timeout(role))` and a deadline. The first run gets at most `role_timeout`. The correction runs only if `budget.remaining() ≥ CORRECTION_FLOOR_S`; otherwise the stop is `out_of_time`. `_check` passes `min(ACCEPT_TIMEOUT, deadline - elapsed)`, and `max(5, left)` is gone. An explicit `except asyncio.CancelledError` writes the failed row (`outcome=failed`, stop `out_of_time`), emits `task_failed`, sets the accept cancel event, and re-raises. |
| `scripts/doctor.py` | Modify | Replace the Step 3 placeholder formula with `loop.deadline`. |
| `tests/test_deadline.py` | **Create** | For every role in `tf-roles.yaml`, `deadline(role)` is finite and above `role_timeout`. code-l2 gives 487. A fake slow accept after a long fake run still gets its full `ACCEPT_TIMEOUT`. The correction is skipped below the floor with `out_of_time`. A cancelled `_execute` leaves the row `failed`, not `running`, and the fake accept's cancel event set. |
| `tests/test_bench_timeout.py` | Modify | Only if it asserts the old `max(5, ...)`. Otherwise unchanged. |

*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_deadline tests.test_bench_timeout tests.test_checker_stage -q`

### Stage S1c

#### Step 6+7 (one commit). F1 correction prompt and F2 task contract (*large*)

| File | Change | Rationale |
| --- | --- | --- |
| `router/server.py` | Modify | **F1:**<br>• `strip_nudges(msgs)` drops user messages whose content starts with the loop's synthetic nudge texts. Those texts become constants in `loop.py`.<br>• `_fix_prompt(verdict, role)` returns the edit-tool wording for roles with `write_file` or `edit_file`.<br>• The correction call at `:257` becomes `run(agent, role, "", strip_nudges(msgs) + [user(fix)], tid)`.<br>• Roles with no write tool skip the correction. A reply diff is reported as `diff: proposed, not applied`, with `checks: FAILED (diff_applies...)` or `checks: ok`.<br><br>**F2:**<br>• `dispatch_task` writes `task_type`, `prompt_sent`, `accept_json`, `workspace`, `plan_id` and `kind` through `store.create`.<br>• `resume_task` reads them, with the NULL fallbacks from the Technical Plan table. It refuses when `status == 'running'`, and when `workspace` differs from `WORKSPACE` (naming both). It passes the stored `accept_json` to `_execute`.<br>• `ask_followup` refuses unless `status == 'done'`. It creates a child row (`parent_id`), runs with checks off and no correction, returns the child's id, and never updates the parent.<br>• Failed runs store `messages=e.msgs`. `get_detail(task_id, max_chars)` keeps its signature; a stored-messages view is shown only when the row has no `detail`.<br>• Docstrings are unchanged. |
| `router/loop.py` | Modify | Nudge texts move into constants `NUDGE_WRAP` and `NUDGE_FINAL` (`:413,417`), so `strip_nudges` can match them. |
| `router/store.py` | Modify | Add `task_type`, `prompt_sent`, `accept_json`, `workspace`, `plan_id INTEGER`, `kind` and `parent_id` to the migration. `create()` takes them as keyword arguments (defaults keep `content_pipeline` and `studio` callers working). `update()` JSON-encodes `accept_json`. |
| `router/checker.py` | Modify | `AcceptSpec.to_json()` / `from_json()` for `accept_json`. |
| `scripts/bench.py` | Modify | The `bench_resume` growth metric (`:270-293`) reads `peak_ctx` per attempt instead of counting saved messages. Resuming a done task (`:287`) still works. |
| `tests/test_correction_prompt.py` | **Create** | A fake `loop._client` records messages. The correction run's last user message is the fix prompt, exactly once, and no nudge text remains. A no-write role gets no correction and reports `diff: proposed, not applied`. |
| `tests/test_task_contract.py` | **Create** | Resume uses the stored `accept_json` and `prompt_sent` (and `with_templates` is not called again). An old row with NULL columns falls back to `prompt` and the `Accept:` line. Resume refuses `running` and a different workspace. A follow-up on a failed task is refused. A follow-up on a done task creates a child row and leaves the parent's status, outcome and summary unchanged. A failed run stores messages. |
| `tests/test_checker_stage.py` | Modify | `:99` asserts the new fix text (`"Checks failed: accept:"`). `:103` no longer relies on the fake `run` appending the prompt. |
| `tests/test_bench_*` (resume-related) | Modify | Only those that read the old growth metric. |

*   **Schema:** seven nullable columns (table in the Technical Plan, plus `parent_id`, which is NULL for old rows and means no parent).
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_correction_prompt tests.test_task_contract tests.test_checker_stage tests.test_haiku_toolcalls -q`. `test_haiku_toolcalls` is a live test that is known to be flaky (2-3 of 9 fail from the live API). Run it for the docstring assertion at `:39` only, and ignore live-call failures.

### Stage S2

#### Step 8. F5: honest finish (*large*)

| File | Change | Rationale |
| --- | --- | --- |
| `router/checker.py` | Modify | `Baseline` and `Changes` dataclasses. `baseline(ws, task_files) -> Baseline`: a temporary-index `git add -A` plus `git write-tree`, with `GIT_INDEX_FILE` in a temp folder that is removed after. It falls back to a partial file hash above 200 MB of untracked, non-ignored files, and to a hash only without git. `changes(ws, baseline, task_files, must_not_change) -> Changes`. `manifest_from(changes) -> str` keeps today's `files_changed:` line format and adds `outside_scope:` when non-empty. `lint_python` is called on `changes.changed` only. The `files_changed` item in `check_deterministic` gets the rule from the Technical Plan for `kind=edit`, and always passes otherwise. |
| `router/server.py` | Modify | `_execute` takes the baseline at the first attempt (when `baseline_json` is NULL) and reuses it after that. `before`/`after` path sets are replaced by `changes()`. It sets `outcome` to `satisfied` or `failed` with `no_change` for packet edit tasks, and to `scope` on a must-not-change hit. Packet edit tasks are created through `store.create_claimed`. |
| `router/store.py` | Modify | Add the `baseline_json`, `packet_json` and `workspace_key` columns, and `create_claimed(...)` (Technical Plan). |
| `router/loop.py` | Modify | When host accept is on, `denied(path, allowed)` is checked before `write_file`, `edit_file` and `move_file` calls, next to `arg_error`. A refusal goes back to the model as `tool error: path is protected: <path>` and is not sent to the server. |
| `router/packet.py` | **Create** | `validate(obj) -> list[str]` (empty means valid), written by hand to match the schema. `render(packet) -> str`. `task_files(packet) -> list[str]`. |
| `docs/designs/subagent-runtime/packet.schema.json` | **Create** | The schema from the Technical Plan. |
| `router/server.py` (internal) | Modify | `_execute` accepts an optional `packet: dict` from Python callers (no tool change). When given: `kind` and task files come from the packet, accept comes from `packet.accept`, and the prompt is `render(packet)`. Preread takes up to 3 packet files. |
| `router/loop.py` (preread) | Modify | `named_paths` limit: 3 when a packet is present, 2 otherwise. |
| `Benchmark/replay/README.md` | **Create** | Corpus rules: at most 3 files; `check.py` independent of the model's output; how to add a task. |
| `Benchmark/replay/<id>/task.toml`, `packet.json`, `check.py` | **Create** | FB-001..FB-009, rebuilt from `fallback-execution-log.md` at each task's pre-fallback commit, plus rw-010..rw-020, chosen as in Open Questions. `task.toml` gives `repo`, `base_commit`, `agent`, `task_type`. |
| `scripts/replay.py` | **Create** | The runner from the Technical Plan. `--repo NAME=PATH` and `--venv NAME=PATH` (the venv `check.py` and accept use for that repo's worktrees; default `<repo>/.venv`), plus `--arm`, `--router`, `--env K=V`, `--runs`. It writes `Benchmark/replay/results/<arm>-<date>.jsonl`. A router checkout without `router/packet.py` gets `render(packet)` sent as legacy task text. |
| `scripts/replay_report.py` | **Create** | Per-task pass (2 of 3), the 16-of-20 count, a one-sided exact sign test on discordant tasks (binomial, standard library only), false-success count, and per-arm 90th-percentile seconds. It prints PASS or FAIL for the gate. |
| `tests/test_baseline.py` | **Create** | In a temporary git repo:<br>• an edit to an already-dirty file is detected;<br>• an untouched dirty file is not credited;<br>• an untracked new file is detected;<br>• an ignored file is not;<br>• a non-git folder uses hashes;<br>• the 200 MB cap gives a partial result (with a small cap patched in);<br>• a must-not-change glob hit is reported;<br>• case-insensitive matching on Windows and macOS. |
| `tests/test_honest_finish.py` | **Create** | Packet edit task outcomes:<br>• no change with accept passing gives `satisfied`;<br>• no change with no accept gives `no_change`;<br>• legacy tasks are never failed;<br>• resume reuses the first baseline (FB-002 replay with fakes).<br><br>Lint is scoped to changed files. |
| `tests/test_workspace_claim.py` | **Create** | Two concurrent `create_claimed` calls: one wins. A stale heartbeat is taken over. Legacy tasks never claim. A refusal creates no row. |
| `tests/test_packet.py` | **Create** | 10 example packets (6 valid, 4 invalid: 4 files, `..` path, absolute path, unknown key). The results agree with `packet.schema.json` (loaded as JSON; the agreement is checked by the example table, not by a validator library). `render` includes an `Accept:` line. |
| `tests/test_denylist.py` | **Create** | Each denylisted path is refused only when host accept is on. A path listed in the packet is allowed. |
| `tests/test_replay_report.py` | **Create** | The sign test against known values, the 2-of-3 rule, and a false-success count from a fixture `results/*.jsonl`. |
| `tests/test_checker.py`, `tests/test_router_bc.py` | Modify | The manifest cases use `changes()` fixtures. The `files_changed:` line format is unchanged. |

*   **Schema:** `baseline_json`, `packet_json`, `workspace_key`. All are NULL on old rows, meaning no baseline: the task is treated as legacy.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_baseline tests.test_honest_finish tests.test_workspace_claim tests.test_packet tests.test_denylist tests.test_replay_report tests.test_checker tests.test_router_bc -q`

#### Step 9. Gate run (no code; Sonnet runs it)

*   **Run arms** `base`, `s2`, `think-low`, `think-off` and `q4` with `scripts/replay.py`. Then run `python -m scripts.replay_report --base base --candidate s2`.
*   **Record** the results and the chosen thinking level in `Benchmark/replay/RESULTS.md` (create), along with the unified `code-l2` `timeout_s` taken from the chosen arm's 90th percentile.
*   **Apply the outcome:**
    *   Set `timeout_s` for `builder` and `code-l2` in `router/tf-roles.yaml` to that value. `scripts/gen_db_profiles.py` does not generate these lines (checked 2026-11-19), so edit `tf-roles.yaml` directly.
    *   Set the `TOKENFRUGAL_THINK` default in `router/config.py`.
    *   If the D10 rule passes, add the `doctor.py` Q4_K_M recommendation.
*   **Acceptance:** `python -m scripts.replay_report --base base --candidate s2` prints `GATE: PASS`. If it prints `FAIL`, S3 starts with the failing tasks as its first test cases, and the gate is re-run after S3.

### Stage S3

#### Step 10. Packet-gated loop policy, in-loop accept, accept pre-check (*large*)

| File | Change | Rationale |
| --- | --- | --- |
| `router/loop_policy.py` | **Create** | `class PacketPolicy(packet, ws, run_accept_fn, budget)`. The hooks are pure, and accept is injected.<br>• `tools(names) -> names`: drops `run_tests` when host accept is on.<br>• `before_call(name, args) -> str \| None`: the denylist and the repeat guard. The key is `(name, canonical args)`. The count is reset whenever a write or edit succeeds. It trips at the 3rd identical call with no file change in between.<br>• `after_tool(name, args, out) -> str`: caps output at 4000 characters, first 1000 + last 3000, reusing `_tail` from `sandbox_mcp.py`. Once every packet file exists and was written in this run, it runs accept inside `budget.pause()` and appends `accept: PASS` or `accept: FAIL <first_error>`. A repeated identical `first_error` (hash of the last exception line) 3 times trips `repeat_guard`.<br>• `on_final(answer) -> str \| None`: final accept. On FAIL with budget left it returns a continue message; otherwise None.<br>• `stop() -> Stop \| None`.<br><br>Precedence: guard > accept > forced answer. The 70% wrap-up nudge is off in packet mode. |
| `router/loop.py` | Modify | `_run` takes an optional `policy` and calls the four hooks at the points shown in the data-flow diagram. With no policy, the code path is unchanged. |
| `router/server.py` | Modify | For packet tasks with host accept on: before the first model call, run accept once. A pass gives `satisfied` (no changes since baseline) or `done` (changes on a resume), with the note "accept passed before any change". No model call is made. Otherwise it builds `PacketPolicy`, and there is no post-run correction. |
| `router/skills/code-l2-packet/SKILL.md` | **Create** | The packet-mode variant of `code-l2`: no `run_tests`; "after you write the files, the harness runs the check and tells you the result". Under 1200 characters. |
| `router/tf-roles.yaml` | Modify | The `code-l2` contract `stop_condition` (`:431`) gets a packet-mode wording. The `code-l2` role gains `packet_skills: [code-l2-packet]`, which replaces `skills` for packet runs. There is no new role, so the role still has 5 tools and stays within the cap. `scripts/gen_db_profiles.py` does not generate the `code-l2` lines, so edit `tf-roles.yaml` directly. |
| `router/config.py` | Modify | `resolve_role(agent, packet=False)`. When `packet` is true and the role has `packet_skills`, use them instead of the role's own `skills` before the agent skills are appended (`:288`). Callers that don't pass `packet` get exactly today's result. Skills keep one resolution point. `server.py` passes `packet=True` for packet tasks and does not choose skills itself. |
| `tests/test_config_packet_skills.py` | **Create** | `resolve_role("coding-l2", packet=True)` gives `code-l2-packet` plus the agent skills. Without `packet`, the result is unchanged for every role in `tf-roles.yaml`. A role with no `packet_skills` gives the same result either way. |
| `tests/test_loop_policy.py` | **Create** | The repeat guard trips at 3 and resets after a write. The error-hash guard trips on the same `first_error`. Output is capped. Accept runs only once all packet files are written. A partial multi-file edit does not trigger accept. `on_final` continues on FAIL with budget left. Accept time is paused out of the budget. Precedence order is respected. |
| `tests/test_precheck.py` | **Create** | Pre-check pass on a fresh task gives `satisfied` with no model call (the fake client records zero calls). Pre-check pass on a resume with prior changes gives `done`. With host accept off there is no pre-check. |
| `tests/test_preread.py`, `tests/test_loopfix.py` | Modify | Only to pass `policy=None` where they call `_run` directly. Behaviour is unchanged. |

*   **Schema:** none.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_loop_policy tests.test_precheck tests.test_config_packet_skills tests.test_preread tests.test_loopfix -q`, then the corpus run `python -m scripts.replay --arm s3 ...` and `python -m scripts.replay_report --base s2 --candidate s3`.

### Stage S4

#### Step 11. The single tool-surface release (*large*)

| File | Change | Rationale |
| --- | --- | --- |
| `router/server.py` | Modify | **`dispatch_task`** gains `packet: dict \| None = None` and `wait: bool = True`. Its docstring describes the packet, the receipt and `wait`.<br>• With `packet`, it returns receipt v1 JSON from `receipt(row) -> dict` (new). The receipt is also stored in the `receipt` column.<br>• With `wait=False`, it starts `_execute` as a background task and returns `{"v":1,"task_id":..., "outcome":"running","next":"poll"}`. `next` gains the value `poll`, added to `outcomes.py`.<br><br>**`task_status(task_id)`** is a new tool. It returns the receipt, or the running state with elapsed seconds.<br><br>**`resume_task`:**<br>• It starts a fresh conversation: system prompt, `prompt_sent`, and a note of at most 300 characters ("Attempt N stopped: <stop>. Files already changed: <paths>. Last check: <first_error>. Continue from the files as they are now.").<br>• Its docstring is updated to match.<br>• It returns a receipt for packet tasks and prose otherwise.<br><br>The failure hint "resume_task will repeat the same failure" is reworded. |
| `router/store.py` | Modify | Add the `receipt` column. |
| `router/outcomes.py` | Modify | Add `Next.POLL`. |
| `router/plan.py` | Modify | `record_run` stores the receipt's one-line form when present. |
| `.codex/agents/tokenfrugal.toml` | Modify | Send packets for edit tasks. Read `next`: `resume` means resume once; `rescope` or `fallback` means report back; `fix_env` means report the fix; `retry_later` means wait, then retry; `poll` means call `task_status`. Use `wait=False` for tasks the caller expects to exceed the client's tool timeout. |
| `CLAUDE.md`, `AGENTS.md`, `examples/example_claude.md`, `examples/example_agents.md` | Modify | The delegation table shows the packet form and the receipt fields. `AGENTS.md` drops the stale `router/agents.yaml` reference. |
| `docs/subagent.md` | **Create** | The install and usage guide for both clients:<br>• the packet and receipt;<br>• the host-accept trust decision and what it does not protect;<br>• the D3 rule that the caller writes the packet and Haiku is the fallback only;<br>• the release notes. |
| `CHANGELOG.md`, `router/__init__.py`, `pyproject.toml` | Modify | Bump the version (minor) and add the release notes table. |
| `tests/test_receipt.py` | **Create** | The largest receipt is at most 150 tokens by the `summarize.py` counter, using real long paths from a fixture. Empty fields are omitted. `files` and `outside_scope` are cut to 3 plus `"+N"`. Every enum value round-trips. |
| `tests/test_surface_s4.py` | **Create** | `dispatch_task(packet=...)` returns valid receipt JSON. A legacy call returns prose, byte-identical to a recorded fixture except the `checks:` line. `wait=False` then `task_status` reaches the final receipt. Resume sends the fresh-start note and does not replay messages. |
| `tests/test_haiku_toolcalls.py`, `tests/test_diagnostics.py` | Modify | `:39` and `:61-64` assert the new docstring and hint texts. |

*   **Schema:** `receipt TEXT`, NULL on old rows; `task_status` then builds a receipt from the row fields.
*   **Acceptance:** `PYTHONPATH=. python -m unittest tests.test_receipt tests.test_surface_s4 tests.test_diagnostics -q`, then the corpus run for arm `s4` and `python -m scripts.replay_report --base s3 --candidate s4`.

### Verification Plan

*   **Build:** `pip install -e .`, then `tokenfrugal-router` starts (S1a onward).
*   **Unit tests:** after every step, `PYTHONPATH=. python -m unittest discover -s tests -t . -q`. The suite runs on Windows, macOS and Linux in `.github/workflows/tests.yml` (from Step 4).
*   **Static checks:** the repo's existing `router/lint.py` checks on changed Python files. Every new `SKILL.md` must be under 1200 characters. Every role must have at most 6 tools (an existing test or a new assertion in `tests/test_deadline.py`, which already walks every role).
*   **Surface check:** before each S1-S3 commit, the reviewer checks that no `@mcp.tool()` signature or docstring changed in `router/server.py`.
*   **Live checks:**
    *   `python scripts/smoke.py` after S1c and after S4.
    *   `python -m scripts.smoke_plan` after S1c, because `plan_id` is now stored.
    *   The realworld benchmark (`realworld-bench` skill) on the builder tag after S2 and S4, to catch regressions outside the corpus.
*   **Gate:** `python -m scripts.replay_report` prints `GATE: PASS` for `s2` against `base`. It is re-run for `s3` and `s4`. The success measures from `hypothesis.md` are read from `RESULTS.md`:
    *   zero false successes;
    *   zero checker-environment failures;
    *   receipts of at most 150 tokens;
    *   fallback-log entries per week.

*Drafted with EGM*
