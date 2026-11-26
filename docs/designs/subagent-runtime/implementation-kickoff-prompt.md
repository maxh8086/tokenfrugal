# Implementation kickoff prompt

This document starts and runs the implementation of [`subagent-runtime-design.md`](../subagent-runtime-design.md). You open one Sonnet session and paste the prompt below. Sonnet then runs a loop with a tick every 15 minutes until every execution slice is done. On each tick it checks progress and moves the current step to its next stage:

1. GPT-6 Luna (Codex) reads its task from [`session-handoff.md`](session-handoff.md), writes the step's tests and then its code and configuration, and writes its feedback back into that file.
2. Haiku completes the tests and runs them.
3. Sonnet confirms the result.
4. Haiku opens a PR, merges it and deletes the branch.

When a step fails, Sonnet writes a fix plan and gives it to Luna. Opus is consulted when the same step fails twice.

## How to run it

### 1. Check the machine first

Run these in the repo folder. Each one should succeed before you start.

```powershell
git switch main; git pull --ff-only tokenfrugal main
```

```powershell
.venv\Scripts\python.exe scripts\doctor.py
```

```powershell
$env:PYTHONPATH = "."; .venv\Scripts\python.exe -m unittest discover -s tests -t . -q
```

```powershell
gh auth status
```

```powershell
codex login status
```

```powershell
codex mcp list
```

`codex mcp list` must show `synaptree` as `enabled`. Steps 8h and 9 (the replay benchmark) also need Docker and Ollama running, with the two local models in `router/tf-roles.yaml` pulled. Sonnet pauses and asks you if they are missing.

### 2. Open the session

1. In the Claude desktop app (Code tab), start a new session in `C:\Users\vaibh\Downloads\Projects\tokenfrugal`.
2. Pick **Sonnet 5.5** in the model picker.
3. Pick a permission mode in which git, gh, codex and Python commands run without a prompt each time, such as auto mode. Otherwise every tick stops at a permission prompt until you answer it. The prompt's own stop rules (installs, pulls, files outside the repo, secrets) still apply in any mode.
4. Keep the computer awake and the app open for the whole run: turn on keep-awake in the Code tab settings. The loop runs only while the session is running.

### 3. Paste the prompt

Copy everything inside the `text` block under [The prompt](#the-prompt) and send it as the first message. Sonnet then:

1. reads this file and the plan, and creates the plan_add tasks and `progress.md`;
2. re-indexes synaptree from the main checkout and checks that Codex can call it;
3. writes the Step 0 spec, gives it to Luna, and starts the 15-minute loop.

If Sonnet does not start the loop on its own, type this in the same session:

```text
/loop 15m Run one tick of the LOOP section of docs/designs/subagent-runtime/implementation-kickoff-prompt.md, following every rule in that prompt.
```

### 4. What you see while it runs

- **Every 15 minutes:** a three-line status in the session (done, running, next).
- **`docs/designs/subagent-runtime/progress.md`:** one row per step: stage, executor, attempts, fix plans, Opus consults, PR link, merge sha, test results, next action.
- **`docs/designs/subagent-runtime/session-handoff.md`:** the task Codex is working on now, its feedback, and the history of earlier assignments.
- **`docs/designs/fallback-execution-log.md`:** every execution, every fix plan and every Opus consult.
- **GitHub:** one merged PR per step.

### 5. When it stops for you

The loop pauses and asks in the session when it needs:

- an install, a model pull, or a change to a file outside the repo (such as `~/.codex/config.toml`);
- a secret;
- your decision, because a step still failed after an Opus re-scope;
- a design change, because S3 also failed the gate;
- your help, because the synaptree check for Codex failed.

Answer in the session. Then say "continue the loop", or start it again with the `/loop` line above.

### 6. Stop, restart, finish

- **Stop:** say "stop the loop" in the session. Sonnet deletes the scheduled job. Any work in progress stays on its step branch.
- **Restart** (after an app restart, or after a pause): open the same session and send the `/loop` line above. Sonnet reads `progress.md` and continues from the stage where the current step stopped.
- **Finish:** when all five GOAL items are true, Sonnet writes the final report, deletes the loop job, and stops on its own.

## The prompt

```text
From now on you run in a loop with a tick every 15 minutes. On each tick you verify progress and assign the next task in sequence to GPT-6 Luna (Codex) or Haiku. Your goal is to complete every execution slice of docs/designs/subagent-runtime-design.md (S1a, S1b, S1c, S2, S3 if Step 9 says build, and S4), Step 0 to Step 11, until it is done.

Read first:
- docs/designs/subagent-runtime/implementation-kickoff-prompt.md: this file, with the run instructions and this prompt;
- docs/designs/subagent-runtime/session-handoff.md: where every Codex task is assigned and where Codex writes its feedback;
- in docs/designs/subagent-runtime-design.md, "## Detailed Implementation Plan", in particular "How the work is executed";
- the review closure tables in docs/designs/subagent-runtime/opus_plan_review.md and astra_plan_review.md.
This prompt replaces the plan's executor and owner rules; every other rule in the plan stays.

GOAL (the loop ends when all of these are true)
1. Every step from 0 to 11 is merged into main through its own PR, with its acceptance command and the full offline suite passing, and its branch is deleted on the remote and locally. Step 10 is merged only if Step 9's "S3 decision:" line says build; otherwise it is recorded as skipped.
2. Step 9 recorded `GATE: PASS` for s2 (or for s3 when S3 was built), and `python -m scripts.replay_report --verify-record Benchmark/replay/RESULTS.md --base <base> --candidate <arm>` exits 0. The base is `base` for s2 and `s2` for s3.
3. CI (.github/workflows/tests.yml) passes on windows-latest, macos-latest and ubuntu-latest for the last step's PR and for main after that merge.
4. Step 11's post-commit checks have run and are recorded in RESULTS.md: the s4 replay against the previous arm, and `python scripts/smoke.py`.
5. docs/designs/subagent-runtime/progress.md lists every step with its PR link, merge commit sha and deleted branch.

ROLES
- Sonnet (you) orchestrates, verifies and decides. You write no code and no tests. You:
  - write each step's specs: the build spec for Luna, then the test spec and the close spec for Haiku;
  - make every decision the plan leaves to the owner or to Sonnet, and write it into the spec: the Step 0 corpus rules, the Step 8h corpus and its substitutions, the Step 9 thinking level and timeout, and the S3 build or skip. Make the corpus decisions before you write or read any S2 result, so the result cannot shape them;
  - review every diff, read Haiku's test output, and run the full suite once yourself before any merge;
  - write the fix plan when a step fails;
  - keep the plan_add tasks and progress.md current.
- GPT-6 Luna (Codex) does the code and configuration of every step, and every fix plan. It writes tests before code: first the step's tests from the plan's test rows, run to show they fail; then the code and configuration until they pass. For a step with no code (Step 0 and Step 8h corpus files, Step 3 pins, the Step 9 replay run), it writes the files or runs the commands the spec gives.
  Every Codex task goes through docs/designs/subagent-runtime/session-handoff.md. You write the build spec or fix plan under "Current assignment" (Status `assigned`), and Codex fills in the Feedback block. Before each new assignment, move the finished one, with its feedback, to the top of History. Run Codex in the background through Bash, with stdin closed:
  codex exec --approve-for-me -C <repo path> "Read docs/designs/subagent-runtime/session-handoff.md. Set Status to 'in progress', do the task under 'Current assignment', then fill in its Feedback block and set Status to done, blocked or failed. Edit nothing else in that file." < /dev/null
  `--approve-for-me` runs in the workspace-write sandbox and approves tool calls by automatic review. Without it every synaptree call fails with "requires approval, but approval policy is never". It cannot be combined with `--sandbox`. Use the model set in ~/.codex/config.toml (gpt-6-luna). If codex is missing or out of tokens, have Haiku do the same assignment from session-handoff.md and fill in its Feedback, note it in progress.md, and go back to Luna for the next step.
- Haiku (Agent with model "haiku", run in the background) completes the tests and closes each step, after Luna:
  - Test: it checks Luna's tests against the plan's test rows, adds any case that is missing, and runs the acceptance command and the full suite. It changes only files under tests/. If a test fails because the code is wrong, it does not change the code; it reports the full failing output.
  - Close: after you confirm, it commits, pushes, opens the PR, waits for CI from Step 4 on, merges, and deletes the branch (see SEQUENCE).
- Opus (Agent with model "opus", fresh context, read-only) is the consultant. Send it:
  - a step that failed twice;
  - a fix that would depart from the plan text;
  - a gate FAIL;
  - a conflict between the plan and the code.
  Each consult gets the step's plan rows, the diff, the failing output and one question. Opus answers with a diagnosis and a concrete fix, not code. You decide whether to use it, record the decision and its reason in progress.md, and turn it into the next fix plan for Luna. If the fix changes the plan, the fix plan also edits the design document, and the commit body says so.

SEQUENCE (every step, in order)
1. You create `impl/step-<id>` (for example `impl/step-6-7`) from the latest main.
2. You write the build spec into session-handoff.md, and Luna builds: tests first, then code and configuration. It reports in the Feedback block.
3. You read the Feedback block, then check `git status` and `git diff`. Status `blocked` or `failed` goes to FAILURE, or, for a question you can answer, to a new assignment with the answer. A "done" with no change, or a change outside the allowed files (session-handoff.md is always allowed), is a failure.
4. Haiku tests: it completes the tests, runs the acceptance command and the full suite, and reports the output.
5. You read Haiku's output and run the full suite once:
   $env:PYTHONPATH = "."; python -m unittest discover -s tests -t . -q
   If both pass with no failure, go to stage 6. Otherwise go to FAILURE.
6. Haiku closes the step, in this order:
   a. Commit on the step branch, session-handoff.md included: human author only, no Co-Authored-By trailer, no "generated with" footer.
   b. Push the branch to the `tokenfrugal` remote and open a PR to main with the step's summary, acceptance result and suite result.
   c. From Step 4 on, wait for CI on the PR. A CI failure stops the close and goes to FAILURE.
   d. Merge with `gh pr merge <n> --merge --delete-branch`, then confirm with `gh pr view <n> --json state,mergeCommit` that it says MERGED, because the merge command can print nothing.
   e. Run `git switch main`, `git pull --ff-only tokenfrugal main` and `git branch -d impl/step-<id>`, plus `git push tokenfrugal --delete impl/step-<id>` if the remote branch is still there.
7. You confirm the merge and that the branch is gone, re-index synaptree from the main checkout, mark the plan_add task done with the merge commit sha, and start the next step at stage 1.

FAILURE
- First failure: write a fix plan with the failing output, the cause, the files to change and what must not change. Assign it to Luna through session-handoff.md (Kind `fix 1`) on the same branch, then repeat stages 3 to 5.
- Second failure of the same step: consult Opus, and give Luna the fix plan you write from its answer.
- Third failure: ask Opus for a re-scope that splits the step smaller, and run each piece through the SEQUENCE.
- A failure after the re-scope: pause the loop and report to me.
- Record every execution in docs/designs/fallback-execution-log.md: executor, stage, attempts, tool calls, elapsed time, result, fix plan and any Opus consult. Add one line per dispatch_task or resume_task call to docs/designs/fallback-attempts.jsonl.

SYNAPTREE (code search for both executors)
- Codex reaches synaptree through the `synaptree` server in ~/.codex/config.toml, and Haiku through the synaptree plugin tools. The project name is `tokenfrugal`.
- Before the first dispatch, run `index_repository` for `tokenfrugal` from the main checkout (never a worktree), then check Codex with:
  codex exec --approve-for-me --ephemeral -C <repo path> "Call the synaptree MCP tool index_status for project 'tokenfrugal'. Do not run shell commands or edit files. Reply in one line: 'SYNAPTREE OK: <status>' or 'SYNAPTREE FAIL: <error>'." < /dev/null
  If it prints SYNAPTREE FAIL, pause the loop and report to me.
- Re-index after every merge, so the next step searches the merged code.

SPECS
- Build spec (Luna):
  - the plan rows for the step, in full;
  - the files it may touch and the files it must not change;
  - the acceptance command;
  - "Write the tests from the plan's test rows first and run them to show they fail; then write the code and configuration until they pass.";
  - "Find code with synaptree (project tokenfrugal): index_status first, then search_graph or search_code, trace_path for callers and callees, get_code_snippet for one symbol. Read a whole file only after synaptree has located the symbol, or for configs and docs.";
  - a tool-call limit of 25, or 35 for steps marked large;
  - "Do not commit, push or install anything; report the files you changed and the test output.";
  - file paths, never whole files.
- Test spec (Haiku): the plan's test rows, the files Luna changed, the acceptance command and the suite command. "Change only files under tests/. Do not change code; report the full output of any failure." Limit 20 tool calls.
- Close spec (Haiku): the step id, the PR title and body, the six close actions with exact commands, and "never force push, never push to main". Limit 15 tool calls.

LOOP (every 15 minutes)
Start it with `/loop 15m` on the tick below. Each tick:
1. Read progress.md, so a restarted loop continues from the stage where the current step stopped.
2. Check the running executor: has it finished, is it still working, or has it stalled (no new file change or output for two ticks)? For Codex, the Status line and Feedback block in session-handoff.md show whether it finished. Stop a stalled job and treat it as a failure.
3. Move the current step to its next SEQUENCE stage, or to FAILURE.
4. When a step is merged, assign the next one whose order rule allows it:
   - any step only after the previous step's PR is merged and its branch deleted;
   - Step 1 only after `git merge-base --is-ancestor <step-0-sha> HEAD` exits 0;
   - Step 5 only after the Step 4 PR passed CI and is merged;
   - Step 9 only after Step 8h;
   - Step 10 only if Step 9 says build;
   - Step 11 after S2 (or S3) passes the gate.
   Run one executor at a time, because steps share files.
5. On a gate FAIL: when S3 is not built yet, build S3 (Step 10) and re-run the gate with `--base s2 --candidate s3`. When S3 already failed the gate, consult Opus, record the diagnosis, and pause the loop for me: the goal cannot be met without a design change.
6. Update progress.md with one row per step: stage, executor, attempts, fix plans, Opus consults, PR link, merge commit sha, acceptance result, suite result, next action. Then post a three-line status here: done, running, next.
7. When every GOAL item is true, write the final report, stop the loop (delete its scheduled job so no further tick fires), and end.

PERMISSIONS GIVEN IN ADVANCE
- For each step: create its branch, push it to the `tokenfrugal` remote, open its PR to main, merge that PR with `gh pr merge --merge --delete-branch` after your suite run passes (and CI, from Step 4 on), and delete the branch locally and on the remote. Never force push, and never push to main directly: main changes only through a step's PR.
- Everything else still needs me: installing software, pulling models, changing ~/.codex/config.toml or any file outside the repo, and secrets. If a step needs one of these, pause the loop and ask.

FIXED RULES
- Step 1 starts by creating tests/test_tool_surface.py and running `python -m tests.test_tool_surface --write` before any router/ edit. S1-S3 change no MCP tool signature or docstring; the tool surface changes once, in Step 11.
- Step 3 uses the pins in Appendix A. If pip freeze in .venv differs, consult Opus and record the decision; do not change a pin silently.
- Step 4's tests.yml runs on `pull_request` to main and on `push` to main, so each step's PR gets CI before its merge.
- Windows, macOS and Linux, with no hardcoded paths; at most 6 tools per role; skills under 1,200 characters; only the two local models in router/tf-roles.yaml.
- Never paste secrets into a spec or the chat.
- Leave my untracked files alone: docs/haiku-fallback-log.md, .agents/ and scratchpad-pr66.txt. Step 3 replaces .codex/config.toml and .codex/agents/tokenfrugal.toml, as the plan says.

Final report: per step, Luna's attempts, the fix plans, Haiku's test result, your suite result, the PR link and merge commit sha; totals per executor; every Opus consult and the decision taken; the GATE and S3 decision lines as printed; and the CI result.
```

## Notes

- **Tests before code:** Luna writes each step's tests from the plan's test rows and runs them to show they fail before it writes the code. Haiku then fills in any missing case and runs everything. Haiku never changes code, so a code fault always goes back to Luna through a fix plan.
- **Corpus independence:** the design makes Steps 0 and 8h the owner's, so the corpus rules are fixed apart from the agent being measured. In this prompt Sonnet makes those decisions, before it sees any S2 result, and Luna only writes the files. If the benchmark must be fully independent, make the Step 0 decisions yourself.
- **Codex command:** tested on 2026-11-26. With `--sandbox read-only`, `codex exec` lists synaptree but every call fails, because a non-interactive run cannot answer the approval. `--approve-for-me` fixes this without changing ~/.codex/config.toml; `index_status` then returned "stale; 44,813 files". `codex exec` also waits on stdin unless it is closed (`< /dev/null`).
- **Handoff file:** Codex gets its tasks only through `session-handoff.md`, not through a long command-line prompt. The file is committed with each step, so the step's PR shows the assignment and Codex's feedback, and a restarted loop can see where Codex stopped.
- **One PR per step:** every step gets its own PR, because the next step branches from main and needs the previous step's commit.
