# Review: settled decisions (D1-D9) and bug-fix specification (F1-F7)

**Target:** `docs/designs/subagent-runtime/concepts_brief.md`. The review covers "Decisions (settled 2026-11-19)", "Bug fixes: production specification (S1 and S2)" and the updated class A finding in Analysis section 2.
**Mode:** brainstorm, round 2. Six Goldfish lenses ran as fresh subagents. All were read-only, and none edited a file.
**Lens key:** DES = design, CB = codebase details, ZO = zoom-out, COMP = comprehension, IR = implementation readiness, STR = structural.
**Severity:** Blocker means the fix is wrong or breaks existing callers as written. Major means the spec has to change before implementation. Nit means a clarity fix or a small correction.

All file references are relative to the repo root, `C:\Users\vaibh\Downloads\Projects\tokenfrugal`.

## Summary

| Severity | Count |
| --- | --- |
| Blocker | 5 |
| Major | 30 |
| Nit | 10 |

Five issues block implementation as written:

1. F4's timeout budget is wrong on its own numbers.
2. F3 would run prose `Acceptance:` lines as commands.
3. F3's `expect` check reads stdout only, so the logged "prints OK" form always fails.
4. F5's legacy "edit task" rule fails non-edit tasks that pass today.
5. D5 misstates the trust boundary for running model-written code on the host.

The proposed order also has a hidden dependency: F2 needs F5's baseline. Five of the six lenses want F6 moved to the front.

---

## F4: outer deadline and accept timeout

### F4-1 The budget rule fails on the gating role, and `TASK_TIMEOUT` already means something else. Blocker
- **Raised by:** DES, CB, ZO, COMP, IR, STR (all six).
- **Evidence:** brief:282 requires `TASK_TIMEOUT` (default 540, `router/config.py:116`) to be greater than role×2 + accept×2.
  - code-l2 (`router/tf-roles.yaml:32`, 225 s): 225×2 + 60×2 = 570, which is already over 540.
  - With `accept_timeout_s=120`: 690, which is over F6's Codex `tool_timeout_sec = 600` (brief:308).
  - code-l4 to code-l6 (450 s) need more than 1000 s.
  - A global 540 s `wait_for` would also kill db-* roles (600 s, `tf-roles.yaml:60-77`) and media roles (900 s, `:51-52`) that work today.
- **Name clash:** `TASK_TIMEOUT` is already the default role timeout for roles with no `timeout_s` (`router/loop.py:240-242`). For those roles the inner and outer limits would be equal, so the correction run could never happen.
- **Tests:** `scripts/bench.py:273-274` patches `loop.TASK_TIMEOUT`.
- **Change:**
  - Add a new variable, for example `TOKENFRUGAL_TASK_DEADLINE`.
  - Compute it per role as `2*timeout_s + 2*accept + lock wait + margin`.
  - Keep `TASK_TIMEOUT` only as the default role timeout.
  - Have F6 or `scripts/doctor.py` derive or check the client tool timeout from the largest per-role deadline.
  - Add a test that checks the rule for every role in `tf-roles.yaml`.
- **Alternative (ZO):** keep one outer deadline. The correction run gets only the time left and is skipped below a floor. The accept timeout is the smaller of its own limit and the time left.

### F4-2 Cancelling with `wait_for` leaves rows marked `running` and accept processes alive. Major
- **Raised by:** CB (as Blocker), DES, IR.
- **Evidence:**
  - Cancelling `_execute` raises `CancelledError`, which `except Exception` at `router/server.py:275` does not catch.
  - So no failed row and no `task_failed` event are written. The row waits for `sweep_stale` to mark it "router stopped" (`router/store.py:84`).
  - Accept runs under `asyncio.to_thread`, so the subprocess keeps running after the cancel.
- **Change:**
  - Enforce the deadline inside `_execute`, with an explicit timeout branch.
  - Have the runner own its deadline: keep the `Popen` handle and kill the process tree on cancel.

### F4-3 `accept_timeout_s` and `slow_accept` have no evidence, and section 5 changed without notice. Nit
- **Raised by:** ZO, STR.
- **Evidence:**
  - None of the 14 logged attempts was an accept timeout.
  - Section 5 (brief:71) said "refuse accept over 20 s". F4 quietly turns that into a `slow_accept` warning.
- **Change:** defer the new field, or record the change of intent in D6.

---

## F3: accept parsing and the runner

### F3-1 Matching `Acceptance:` turns prose into commands. Blocker
- **Raised by:** COMP (as Blocker), IR (as Blocker), DES, CB, ZO.
- **Evidence:**
  - Real specs contain prose such as `Acceptance: loader test passes.` and `Acceptance: one scene renders with no overlap` (`docs/designs/media-generator-visuals.md:82-86`).
  - Under F3, `argv[0]="loader"` and the task fails with `fix_env`. Today the same task finishes (done, unverified).
  - The class A form wraps the command in backticks (`docs/designs/fallback-execution-log.md:19`). The parser does not strip them, so `` `PYTHONPATH=. `` is never seen as a `NAME=` token.
- **Change:**
  - Treat an `Acceptance:` line as a command only when it holds a backtick span (use the first span), or when its first token resolves to an executable.
  - Otherwise report no accept and emit `checks: none (acceptance line is prose)`.
  - Test both cases, and add the FB-001 line verbatim as a test case.

### F3-2 `expect` checks stdout only, so the motivating "prints OK" case always fails. Blocker
- **Raised by:** ZO (as Blocker), DES, CB, STR.
- **Evidence:** unittest writes `OK` to stderr, and FB-001 ends with `prints OK.` (`fallback-execution-log.md:19`).
- **Change:**
  - Match `expect` against stdout and stderr together.
  - Alternatively (ZO), drop `expect` for unittest and pytest, because exit code 0 already means OK.

### D5/F3-3 The trust boundary for host accept is misstated. Blocker
- **Raised by:** DES (as Blocker). CB, ZO and IR raised related points.
- **Evidence:**
  - `router/sandbox_mcp.py:40-42` runs model code with `--network none`, a read-only filesystem, a pids limit and `no-new-privileges`. D5 (brief:202) moves the same code to the host, with network access.
  - "The caller writes the command, never the model" is not a real control. The model writes the code that the command runs: tests, `conftest.py`, `sitecustomize.py`, `*.pth`, and even `.venv/`.
  - Running accept after each write lets the model iterate against the host. Text the model reads in files (prompt injection) becomes host execution.
  - Stripping environment variables does not protect `~/.ssh`, `~/.aws`, git or gh credential stores, or `~/.docker/mcp/secrets` (`router/secrets_store.py:14`).
- **Change:**
  - Make host accept an explicit per-workspace opt-in, off by default for other installers.
  - In packet mode, refuse model writes to `.venv/`, `.git/`, `conftest.py`, `sitecustomize.py` and `*.pth` unless the packet lists them.
  - Document the remaining risk in D5. Do not describe the environment filter as a security boundary.
  - Long term: run accept in a per-workspace container built from the repo's lockfile.

### F3-4 Accept is read from the prompt after templates are added. Major
- **Raised by:** COMP, ZO.
- **Evidence:** `_check` parses the composed prompt (`router/server.py:181`, `router/store.py:265-271`), and the last matching line wins. Templates come from earlier tasks (`source_task_id`), so an approved template's `Accept:` line can run on the host. That contradicts D5's claim that the caller writes the command.
- **Change:** parse accept only from the caller's own task text (or the `accept=` argument), never from template bodies.

### F3-5 The secret-stripping regex is the wrong abstraction. Major
- **Raised by:** DES, CB, ZO, COMP, IR, STR (all six).
- **Evidence:** brief:260.
- **It strips too much:**
  - `TOKEN` matches every `TOKENFRUGAL_*` variable.
  - `AUTH` matches `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` (which breaks git-based tests), `SSH_AUTH_SOCK` and `XAUTHORITY`.
  - `KEY` matches `KEYRING_*`.
- **It keeps real secrets:** `DATABASE_URL` with a password, `*_DSN`, `*_PAT`, `*_PASS`/`*_PWD`/`PASSWD`, `*PRIVATE*`, `*COOKIE*`, and proxy URLs with credentials.
- **Case:** the brief does not say whether the match ignores case. Windows environment names are case-insensitive.
- **Change:**
  - Use an allowlist: `PATH`, `SYSTEMROOT`, `WINDIR`, `COMSPEC`, `PATHEXT`, `TEMP`/`TMP`, `HOME`/`USERPROFILE`, `APPDATA`/`LOCALAPPDATA`, `LANG`/`LC_*`, `TERM` and `VIRTUAL_ENV`.
  - Add the packet's `env` and a user-configurable extra list.
  - Compare names case-insensitively on Windows.
  - Never log packet `env` values in the `accept_run` event.

### F3-6 `shlex` behaves differently on each OS, and the `prints X` rule is ambiguous. Major
- **Raised by:** DES, CB, ZO, COMP.
- **Evidence:** brief:250-254.
  - With `posix=False` on Windows and `posix=True` elsewhere, one string can give a different argv on each OS. A Linux CI run then proves nothing about Windows.
  - `posix=False` has no escape handling, so `python -c "print(\"x\")"` splits wrongly.
  - `prints X` is matched on raw text, so a `-c` body that contains "prints" is misread.
  - The brief does not say whether X keeps its quotes, or how `prints 3.14.` is read.
- **Change:**
  - Packet `accept` takes an argv list only, with no parsing. That is the portable form.
  - Legacy strings go through one parser on every OS. DES proposes `shlex.shlex(s, posix=True)` with `whitespace_split=True` and `escape=''`.
  - Parse `prints X` only from the trailing tokens after splitting.
  - Give an exact regex and a table of example inputs and outputs, and run the parser tests on all three OSes.

### F3-7 Interpreter resolution is wrong outside this machine. Major
- **Raised by:** DES, CB, ZO, COMP, IR, STR (all six).
- **Evidence:**
  - FB-009 used `.venv\Scripts\python.exe` (`docs/designs/fallback-attempts.jsonl:20-22`), which is not in {python, python3, py}.
  - `shutil.which` on a path that contains a separator resolves against the router's working folder, not the workspace. On POSIX the Windows form never resolves.
  - Rewriting `py` to the venv interpreter leaves `-3.12` as a stray argument.
  - Only `argv[0]` is rewritten, so `pytest`, `uv` and `npm` still resolve against the router's PATH.
  - Falling back to the router's `sys.executable` runs the project's tests with tokenfrugal's dependencies.
- **Change:**
  - Treat any `argv[0]` whose basename matches `python3?(\.exe)?` as the interpreter alias.
  - Resolve other relative paths against the workspace.
  - Drop `-X.Y` flags after `py`.
  - Put the workspace venv's `bin` or `Scripts` folder first on PATH, and set `VIRTUAL_ENV`.
  - If there is no venv, fall back to the PATH `python` and report `env: system-python`. Never use the router's interpreter.

### F3-8 Process control can hang on Windows, and other edge cases are missing. Major
- **Raised by:** DES, CB, IR.
- **Evidence:**
  - `taskkill /T` misses grandchildren whose parent has already exited.
  - Orphans that still hold the stdout or stderr pipe make `communicate()` hang after the kill.
  - The child inherits the MCP stdio pipe unless stdin is redirected.
- **Change:**
  - Use a Job Object with `KILL_ON_JOB_CLOSE` (via ctypes), or send output to temp files instead of pipes.
  - Set `stdin=DEVNULL`.
  - Reject `&&`, `|`, `;` and `>` with a clear message.
  - Map `No module named` to `fix_env` instead of a correction run (FB-006).

### F3-9 / D8 The runner and parser signatures are undefined, and existing tests depend on them. Major
- **Raised by:** CB, IR, STR, ZO (as Nit).
- **Evidence:**
  - `checker.run_accept(cmd, repo, timeout) -> (bool, str)` already exists (`router/checker.py:63`).
  - It is tested at `tests/test_checker.py:73-83`, which asserts the exact text "timed out after 1s".
  - `server.accept_cmd` is asserted to return a list (`tests/test_checker_stage.py:25-31`, `tests/test_router_bc.py:73-76`).
  - D8's "thin parser that calls the runner" mixes up the two jobs.
  - The `accept_run` event needs a task id, which the checker does not have.
- **Change:**
  - Define `parse_accept(text) -> AcceptSpec(argv, env, expect)` and `AcceptResult(ok, exit, secs, first_error, out)`.
  - Extend `run_accept` rather than replacing it.
  - Have the server emit the `accept_run` event.
  - List every test each fix rewrites.

---

## F5 / D2 / D7: change detection, edit-task rule and workspace lock

### F5-1 The legacy "edit task" rule fails non-edit tasks that pass today. Blocker
- **Raised by:** IR (as Blocker), DES, CB, COMP, STR.
- **Evidence:**
  - Legacy tasks count as edit tasks when the role has write tools (brief:294).
  - Roles with `write_file` include builder, content-writer, content-research, content-analyst-*, the curator, the collectors, devops and ui-* (`router/tf-roles.yaml:21,38-47`).
  - Under the new rule, "explain code", review work, studio stages (`router/studio.py:269`) and `scripts/content_pipeline.py:77` would end `no_change_unverified`.
  - Today `_check` returns None when there is no accept and no diff (`router/server.py:183-184`), and `check_deterministic` never fails on `files_changed` (`router/checker.py:85`).
  - In a workspace that is not a git repo, `_changed_set` returns an empty set (`router/server.py:198-203`), so every legacy edit task would fail.
  - This contradicts D4's "byte for byte" promise.
- **Change:**
  - Legacy tasks stay `done` and gain the `checks: none` line.
  - Decide edit or not only from the packet's `kind`, or from a fixed set of `task_type` values.
  - Exempt follow-ups.
  - Without git, hash the packet files and report `git: unavailable`.

### F5-2 Lint is not scoped to the task. Major
- **Raised by:** DES, ZO, IR, STR.
- **Evidence:** `lint_python` runs over every git-changed file (`router/checker.py:78-79`), so a dirty file from another session fails the task.
- **Change:** lint only the paths whose hash changed against the baseline.

### F5-3 Baseline cost and method. Major
- **Raised by:** DES, CB, ZO, IR.
- **Evidence:** hashing every untracked file with `--untracked-files=all` can mean gigabytes in repos with media renders.
- **Change, two options:**
  - ZO: let git do it. Build the baseline as one tree id (`GIT_INDEX_FILE=<tmp> git add -A && git write-tree`), and get the changed files with `git diff --name-only <base> <now>`. This respects `.gitignore` and uses git's stat cache.
  - Others: reuse `checker.files_changed`, compare size and mtime before hashing, and cap file size and count.
- **Also:** match packet paths case-insensitively on Windows and macOS.

### F5-4 Legacy "any path" does not fix A3. Major
- **Raised by:** STR.
- **Evidence:** brief:45 and brief:291. For legacy tasks, any changed path is still credited to the task, including another session's edit, which is the A3 problem.
- **Change:** for legacy tasks, use the prompt's named paths as the task's files.

### F5-5 / D7 The workspace lock cannot reuse `gpu_lease.py` and is underspecified. Major
- **Raised by:** DES, CB, ZO, COMP, IR, STR (all six).
- **Evidence:**
  - `router/gpu_lease.py` is hard-wired to one resource: `gpu.json`/`gpu.lock`, `HOLDERS=("comfyui","kalamanch")`, and container or pid takeover (`router/gpu_lease.py:4,38-40,228-235`).
  - Its docstring says only that module touches the lease file.
  - `compose.lease_release` deletes `<service>.*` files in `leases/` (`router/compose.py:155-163`).
  - A 30 s wait inside an async handler blocks the event loop.
  - `scripts/bench.py:263-264` runs builder tasks concurrently, so the lock would change benchmark results.
- **Not specified:**
  - how the key is built from the workspace path (normalisation, case);
  - whether resume, follow-up and `content_pipeline` take the lock;
  - what legacy callers see for `retry_later`;
  - whether a refused call creates a task row.
- **Change, two options:**
  - Extract a generic keyed lease, `router/lease.py`, that gpu_lease also uses. Use a `ws.` prefix and exclude it in compose. Key it on `normcase(realpath(ws))`. Wait via `to_thread`.
  - ZO: use the tasks table instead. In `BEGIN IMMEDIATE`, refuse a new edit task while a running edit row exists for the same workspace, and return `retry_later` at once. The table already has heartbeat and stale handling (`router/store.py:51-86`).
- **Either way:** record as a decision whether legacy tasks take the lock.

### D2-1 Can `satisfied` be reached in packet mode? Major
- **Raised by:** COMP, ZO (as Nit).
- **Evidence:** `satisfied` needs accept to have run. In packet mode accept runs only after a write (brief:201), and goal 4 removes the post-run correction.
- **Change:**
  - State that a final accept always runs.
  - ZO suggests also running accept once before any model work. If it already passes, return `satisfied` without spending model time (as in FB-002 and FB-003), or flag that the accept command cannot tell a fix from no fix.

---

## F2: resume, follow-up and stored state

### F2-1 `ask_followup` would open to failed tasks and rerun accept. Major (one lens rated it Blocker)
- **Raised by:** IR (as Blocker), DES, CB, COMP.
- **Evidence:**
  - The only guard is `not t["messages"]` (`router/server.py:378`). The brief's "only works on finished tasks" (brief:246) is not enforced.
  - Once failed runs store messages, follow-ups would replay conversations that end in unanswered tool calls.
  - Reading `accept_json` back means a follow-up question reruns accept (up to 60 s) and possibly a correction run that edits files.
  - It also goes through F5's no-change rule and can overwrite a done row as failed (`router/server.py:266,288`).
- **Change:**
  - Check `status == 'done'` explicitly.
  - Run follow-ups with no checks and no correction.
  - Write follow-ups to a child row, or never let them overwrite the parent's status.
  - Refuse resume on running tasks. Note that `scripts/bench.py:287` resumes a done task, so a done-task guard on resume would break it.

### F2-2 Stored state is incomplete or ambiguous. Major
- **Raised by:** CB, ZO, COMP, IR, STR.
- **Missing pieces:**
  - **Old rows:** the new columns are NULL on existing `router/tasks.db` rows, and no fallback is given.
  - **Templates:** calling `with_templates` again bumps `uses` and can pick different templates (`router/store.py:259-262`). Store the composed prompt (`prompt_sent`).
  - **Workspace:** a `workspace` column is missing. `WORKSPACE` is set per router process (`router/config.py:66`), so a resume from another repo's session would check the wrong tree.
  - **Plan link:** a `plan_id` column is missing, so a resumed plan task stays blocked.
  - **Encoding:** `store.update` JSON-encodes only `messages` (`router/store.py:58`). The new `*_json` columns need encoding too.
  - **get_detail:** `get_detail` (`router/server.py:386-393`) never reads `messages`, so "for get_detail only" needs code there.
  - **Sources:** `client`, `model_tag` and `parent_id` have no source. `_ClientSeen` only emits an event (`router/server.py:117-121`), and `role["model"]` is the logical name, not the tag. `parent_id` means nothing while resume reuses the same task id (`router/server.py:419`).
  - **Column count (ZO):** ten columns are added at once, and most have no writer until later stages. Add each column in the commit that writes it, using the migration loop at `router/store.py:35`.
- **Change:** a per-column table giving the writer, the reader and the NULL fallback.

### F2-3 Docstring and failure hints conflict with "S1 changes no docstring". Major
- **Raised by:** CB, ZO, COMP, IR, STR.
- **Evidence:**
  - The `resume_task` docstring says "from its saved conversation" (`router/server.py:414`, also `tests/test_haiku_toolcalls.py:39`).
  - The failure hint "resume_task will repeat the same failure" (`tests/test_diagnostics.py:61-64`) becomes wrong once resume starts fresh.
- **Change:** allow these specific edits in S1, or defer the resume behaviour change to S4.

### F2-4 The `bench_resume` metric becomes meaningless. Nit
- **Raised by:** CB, IR, DES.
- **Evidence:** `scripts/bench.py:270-293` measures how saved messages grow across resumes.
- **Change:** update or retire it.

---

## F1: correction-run prompt

### F1-1 Landing F1 before F2 double-appends the prompt, and two callers are missed. Major
- **Raised by:** CB, ZO, IR, DES, STR.
- **Evidence:**
  - `resume_task` (`router/server.py:419`) and `scripts/content_pipeline.py:73` pass both `prompt` and `messages`. Under F1's rule both would add the original prompt again.
  - `tests/test_checker_stage.py:99` asserts `"Checker failed: accept:"`, and `:103` relies on the fake `run` appending the prompt itself.
- **Change:**
  - ZO: fix the call site instead of `run()`: `run(agent, role, "", msgs + [fix_msg], tid)` at `router/server.py:257`. This is one line and leaves `run()` and `ask_followup` alone.
  - Or ship F1 and F2 in one commit, and build the fresh-resume logic inside `_execute` so every caller gets it.
  - Write the test against `loop._client`.

### F1-2 Roles without write tools still get a false `done`. Major
- **Raised by:** DES, ZO, IR, COMP (as Nit), STR (as Nit).
- **Evidence:** the correction asks for a diff that nothing applies; `diff_applies` only checks it (`router/checker.py:39-47`). So the second check passes, and the task reports done with nothing written.
- **Change:**
  - Skip the correction for roles with no write tool.
  - Report the diff as "proposed, not applied".
  - Say which failed item supplies `<first error line>`.

### F1-3 Replayed history contains contradictory nudges. Major
- **Raised by:** DES.
- **Evidence:** "Stop calling tools..." and "Do not call any more tools" (`router/loop.py:413,417`) stay in the history and contradict the fix prompt.
- **Change:** strip the synthetic nudges before appending the fix prompt.

---

## F6: Codex config and installer

### F6-1 The generated config pins one workspace and only works inside this repo. Major
- **Raised by:** DES, CB, ZO, COMP, IR, STR (all six).
- **Evidence:**
  - Setting `CC_WORKSPACE` overrides git-root detection (`router/config.py:66-69`), so every Codex project would use that one repo.
  - A project-level `.codex/config.toml` inside tokenfrugal does nothing for users working in their own repos.
  - `-m router.server` from another working folder needs `cwd` or `PYTHONPATH`.
  - `.mcp.json` has the same hardcoded `.venv/Scripts/python.exe` path, and F6 only fixes Codex.
  - `.codex/config.toml` is committed today, and `.gitignore` has no entry for it.
- **Change:**
  - Do not set `CC_WORKSPACE` unless the user opts in.
  - Write the user-level `~/.codex/config.toml`.
  - ZO: add dependencies and a `[project.scripts] tokenfrugal-router` entry to `pyproject.toml`, so both clients use `command = "tokenfrugal-router"` with no generator script.
  - Add a `git rm --cached` step and a note for existing users.

### F6-2 The "required arguments" test has nothing to inspect. Major
- **Raised by:** DES, CB, IR, ZO.
- **Evidence:** every `dispatch_task` parameter has a default (`router/server.py:303-304`), and `task_type` is checked at runtime (`:314`).
- **Change:**
  - Export a `REQUIRED_ARGS` constant that both the server and the test use.
  - Or (ZO) make `task_type` optional, since `with_templates` already handles an empty value. That removes the "wrapper missed a required argument" failure for every client.

### F6-3 The wrapper is told to read `next`, which exists only in S4. Nit
- **Raised by:** COMP.
- **Evidence:** goal 5 (brief:147) already places the wrapper rewrite in S4.
- **Change:** drop the `next` instruction from F6, or move it to S4.

---

## F7 / A2: class A diagnostics

### F7-1 The test injects the error where it can never reach `_execute`. Major (one lens rated it Blocker)
- **Raised by:** CB (as Blocker), DES, COMP, IR, STR (as Nit).
- **Evidence:** tool-call exceptions are caught at `router/loop.py:516-519` and returned to the model as `tool error: ...`. Class A escaped the loop, so it came from `open_role`/`backends` (stdio launch, anyio ExceptionGroup), `list_tools`, the chat call (`router/loop.py:450`) or `guard_ollama` (`:420`).
- **Change:** inject the error at `open_role`, `backends` or `list_tools`.

### F7-2 "Last 3 frames" will not name the failing call. Major
- **Raised by:** DES, CB.
- **Evidence:**
  - `leaf()` keeps only `exceptions[0]` (`router/loop.py:82-86`).
  - For a launch failure, the last frames are stdlib `subprocess`/`_winapi` frames.
  - `WinError 2` has `filename=None`.
- **Change:**
  - Record the innermost frame, plus the last frames under `router/`, from the whole exception group.
  - Wrap the Popen and stdio launches to log `argv[0]` on `OSError`.
  - Add a branch in `_trail_line` (`router/server.py:409`) to print the frames.
  - Reuse `shutil.which("docker")` from `router/compose.py:184`.

### A2-1 The class A wording overclaims, and stale records remain. Nit
- **Raised by:** COMP, STR, CB. ZO separately confirmed the core analysis against `router/server.py:166` and `router/loop.py:518`.
- **Points:**
  - "Neither suspected cause" ignores `hyperframes` (`fallback-execution-log.md:140`). Add it and `npx` to F7's start-up check.
  - `fallback-attempts.jsonl:4,6` and the root-cause table still say `A_builder_path`.
  - "resume_task drops the accept command" is only half true. An inline `Accept:` line survives in `t["prompt"]` (`router/server.py:341`); only the `accept=` argument and the templates are lost.

---

## D4: legacy reply text

### D4-1 "Byte for byte" is broken, and the `checks:` line has no owner. Major
- **Raised by:** CB, IR, COMP, STR.
- **Evidence:**
  - D4's new line `checks: none (no accept command)` is not assigned to any F or stage.
  - `scripts/bench_checks.py:167` (`_TRAILER`) strips only `status=` and `files_changed:` lines, so the new words could let a benchmark check pass.
  - The new line is easy to confuse with the existing `Checks:` line (`router/server.py:215`).
  - After F5, the `files_changed` line and the checks items also change.
- **Change:**
  - Assign the line to F3.
  - Add `checks:` to `_TRAILER` and place it before `status=`.
  - Show the legacy prose for each new outcome.

### D4-2 The stop and failure vocabulary is fragmented. Major
- **Raised by:** COMP, STR, CB, IR (as Nit).
- **Evidence:**
  - D2 says `no_change_unverified` (brief:185), while F5 says `no_change` (brief:293).
  - `fix_env` is used as both a `stop` value and a `next` value.
  - `retry_later` is a `next` value, but legacy callers have no `next` field.
  - Receipt v1 (brief:194) has no field for `slow_accept`, `env:`, `outside_scope` or `satisfied`.
  - `fix_env` is missing from `error_kind`/`kind_hint` (`router/server.py:34-50`).
- **Change:**
  - Add an F0, or extend F7, to create one enum module before F3.
  - Use one name in D2 and F5.
  - Add the new values to `tests/test_error_kind` and `tests/test_diagnostics`.

---

## D5 / D6: in-loop accept

### D5-1 In-loop accept fires too early, and skills still name `run_tests`. Major
- **Raised by:** DES, CB, ZO (as Nit).
- **Evidence:**
  - Running accept after every write fails on part-edited multi-file tasks, and costs up to 60 s per write against the largest failure class (time, 7 of 14 attempts).
  - `skills/code-l2/SKILL.md:10-11` and the contract `stop_condition` at `router/tf-roles.yaml:431` both name `run_tests`, which packet mode removes.
- **Change:**
  - Run accept once every packet file has been written, or at the final answer.
  - Add a packet-mode skill variant.
  - Hook in next to `lint_written` at `router/loop.py:514-515`, via `to_thread`.

### D6-1 In-loop accept time counts against the role timeout. Major
- **Raised by:** COMP, DES.
- **Evidence:** in-loop accept runs inside `asyncio.wait_for(_run, role timeout)` (`router/loop.py:363`), contradicting brief:208.
- **Change:** say how accept time is excluded, or drop the claim.

---

## Staging and the packet

### S-1 S1-S3 fixes use a packet that ships only in S4. Major
- **Raised by:** COMP, STR, CB.
- **Evidence:**
  - F2-F5 use packet fields: `packet_json`, `kind`, `must_not_change`, `new`, `expect`, `accept_timeout_s` and the files list (brief:166,242,250,280,294-297).
  - S1 "changes no tool signature" (brief:233).
  - D1's corpus is made of `packet.json` files.
  - No single packet schema exists.
- **Change:**
  - Add an internal packet path in S1 (a `packet.py` that renders to the prompt and is not exposed as a tool), and have the corpus use it.
  - Or move every packet-only clause out of F1-F5.
  - Publish one packet schema.

### S-2 A1 and goal 6 have no D or F. Major
- **Raised by:** STR.
- **Evidence:** usage events still drop `error_kind` and peak context, and the per-task fields only arrive with F2, so S1's effect cannot be measured. The Q4_K_M spike has no decision.
- **Change:**
  - Move field recording into F7, or into an S0 fix that runs first.
  - Add a D for Q4_K_M.

### D1-1 The corpus statistics and settings differ from production. Major
- **Raised by:** ZO (as Major), CB, DES, COMP (as Nit).
- **Evidence:**
  - 20 tasks × 3 runs is still about 20 independent units, so the repeats do not narrow the interval the brief uses to reject live tasks.
  - The corpus uses temperature 0.1, while production uses 0.0 (`router/config.py:49`).
- **Change:**
  - State that the gate is a paired comparison (same tasks in both arms; McNemar or sign test).
  - Measure at the production temperature, or change the default.

---

## Order of fixes (F7, F3, F4, F1, F2, F6, then F5)

### O-1 The order has a hidden dependency, and F6 is too late. Major
- **Raised by:** DES, CB, ZO, COMP, IR, STR (all six).
- **Problems:**
  - **F2 needs F5:** F2's test needs "the first attempt's baseline" (brief:247), and its note lists changed files. The baseline only exists in F5 (S2), so S1 does not fix the class D attempts (FB-002, FB-003).
  - **F1 alone is unsafe:** F1 landing before F2 makes resume append the original prompt again.
  - **F6 comes too late:** F6 has no dependencies, carries little risk, and targets the Codex gap (only 24 of 133 Codex sessions used tokenfrugal).
- **Suggested order (consensus):**
  1. F7 and F6 (config half) together.
  2. F3, owning D4's `checks:` line, and the enum.
  3. F4 with a per-role deadline.
  4. F1 and F2 in one commit. F2 covers only the contract: task_type, accept, the composed prompt and fresh resume.
  5. F5 in S2, including the baseline reused on resume, scoped lint and the lock.
- **Alternatives:**
  - DES moves a path-set baseline into F2 and lets F5 upgrade it to hashes.
  - ZO puts a minimal F4 after F2.

---

## Over-built

- The secret regex and the per-OS `posix` branch should be replaced (allowlist; argv list plus one parser), not extended. (DES, ZO)
- Content-hashing every untracked file in Python duplicates what `git write-tree` does. (ZO)
- F2's ten columns, most with no writer in S1. (ZO)
- `accept_timeout_s` and `slow_accept` have no supporting evidence. (ZO)
- A generator script for the Codex config, where a packaged entry point is enough. (ZO)

## Missing

- A write denylist for packet tasks (`.venv/`, `.git/`, `conftest.py`, `sitecustomize.py`, `*.pth`), and host accept as an opt-in. (DES)
- An outer deadline computed per role, plus a doctor check against client timeouts. (all)
- Follow-up isolation: status guard, no checks, no overwrite. (DES, CB, IR)
- One enum for stop and next values, and one packet schema. (STR, COMP)
- Handling of workspaces that are not git repos. (DES, IR)
- A list of the existing tests each fix rewrites: `tests/test_router_bc.py:54-76`, `tests/test_checker.py:73-106`, `tests/test_checker_stage.py:25-31,99,103`, `tests/test_diagnostics.py:61-64`, `tests/test_haiku_toolcalls.py:39`. (STR, IR, CB)

## Nits (structure and clarity)

- Add a glossary for packet, receipt, accept, baseline, satisfied, class A-D, S0-S4, FB-xxx, slug versus role, and Haiku fallback. (COMP)
- D3 and D5-D9 lack the "Rejected:" line promised at brief:173. (STR)
- brief:99 says "Decision F3", but F3 is a fix. Parsing `-c` and `VAR=` forms is a decision with no D number. (STR)
- The estimates at brief:163 ("30-50 lines") and brief:169 ("7-9 of 14") predate F1-F7 and the class A reclassification. (STR)
- D3 refers to the author's own `~/.claude/CLAUDE.md`. Move that to install documentation. (COMP)
- D8: say "extend `checker.run_accept`", not "one runner". (ZO)
