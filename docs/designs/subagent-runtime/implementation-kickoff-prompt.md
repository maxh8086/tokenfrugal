# Implementation kickoff prompt

This document starts and runs the implementation of [`subagent-runtime-design.md`](../subagent-runtime-design.md). You open one Sonnet session and paste the prompt below. Sonnet then runs a loop with a tick every 15 minutes until the goal is met. On each tick it checks progress, verifies finished work, and assigns the next step to GPT-6 Luna (Codex) or Haiku. Each step is merged to main through its own PR before the next one starts. Opus is consulted when a step fails.

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

1. creates the plan_add tasks and `progress.md`;
2. re-indexes synaptree from the main checkout and checks that Codex can call it;
3. does Step 0 itself, on branch `impl/step-0`, and merges it through its PR;
4. starts the 15-minute loop.

If Sonnet does not start the loop on its own, type this in the same session:

```text
/loop 15m Run one tick of the LOOP section of docs/designs/subagent-runtime/implementation-kickoff-prompt.md, following every rule in that prompt.
```

### 4. What you see while it runs

- **Every 15 minutes:** a three-line status in the session (done, running, next).
- **`docs/designs/subagent-runtime/progress.md`:** one row per step: executor, state, attempts, Opus consults, PR link, merge sha, test results, next action.
- **`docs/designs/fallback-execution-log.md`:** every execution and every Opus consult.
- **GitHub:** one merged PR per step, titled by step.

### 5. When it stops for you

The loop pauses and asks in the session when it needs:

- an install, a model pull, or a change to a file outside the repo (such as `~/.codex/config.toml`);
- a secret;
- your decision after a step failed on both executors and after an Opus re-scope;
- a design change, because S3 also failed the gate;
- your help because the synaptree check for Codex failed.

Answer in the session. Then say "continue the loop", or start it again with the `/loop` line above.

### 6. Stop, restart, finish

- **Stop:** say "stop the loop" in the session. Sonnet deletes the scheduled job. Any work in progress stays on its step branch.
- **Restart** (after an app restart, or after a pause): open the same session and send the `/loop` line above. Sonnet reads `progress.md` and continues from the first step that is not merged.
- **Finish:** when all five GOAL items are true, Sonnet writes the final report, deletes the loop job, and stops on its own.

## The prompt

```text
Implement docs/designs/subagent-runtime-design.md from Step 0 to the end, one step at a time. Each step gets its own branch from the latest main, `impl/step-<id>` (for example `impl/step-6-7`), and is merged back through its own PR before the next step starts. Read "## Detailed Implementation Plan" first, in particular "How the work is executed". The review closure tables are in docs/designs/subagent-runtime/opus_plan_review.md and astra_plan_review.md. This prompt replaces the plan's executor and owner rules with the ones below; every other rule in the plan stays.

GOAL (the loop ends when all of these are true)
1. Every step from 0 to 11 is merged into main through its own PR, with its acceptance command and the full offline suite passing, and its branch is deleted on the remote and locally. Step 10 is merged only if Step 9's "S3 decision:" line says build; otherwise it is recorded as skipped.
2. Step 9 recorded `GATE: PASS` for s2 (or for s3 when S3 was built), and `python -m scripts.replay_report --verify-record Benchmark/replay/RESULTS.md --base <base> --candidate <arm>` exits 0. The base is `base` for s2 and `s2` for s3.
3. CI (.github/workflows/tests.yml) passes on windows-latest, macos-latest and ubuntu-latest for the last step's PR and for main after that merge.
4. Step 11's post-commit checks have run and are recorded in RESULTS.md: the s4 replay against the previous arm, and `python scripts/smoke.py`.
5. docs/designs/subagent-runtime/progress.md lists every step with its PR link, merge commit sha and deleted branch.

ROLES
- Sonnet (you) orchestrates and decides. Sonnet:
  - writes no step code;
  - writes each step's spec and assigns it to an executor;
  - reviews every diff, runs every acceptance command and the suite, and commits;
  - makes every decision the plan leaves to the owner or to Sonnet: the Step 0 corpus rules, the Step 8h corpus build and its substitutions, the Step 9 thinking level and timeout, and the S3 build or skip;
  - keeps the plan_add tasks and the progress file current.
  Steps 0 and 8h are corpus work, not code: Sonnet does them itself, and does them before it writes or reads any S2 result, so its choices cannot be shaped by the result.
- GPT-6 Luna (Codex) is the first executor for the steps that change router code: 1, 2, 4, 5, 6+7 (task 6, then task 7), 8a, 8c, 8d, 8e and 11, plus 10 if S3 is built. Run it in the background through Bash, with stdin closed:
  codex exec --approve-for-me -C <repo path> "<step spec>" < /dev/null
  `--approve-for-me` runs in the workspace-write sandbox and approves tool calls by automatic review. Without it every synaptree call fails with "requires approval, but approval policy is never". It cannot be combined with `--sandbox`. Use the model set in ~/.codex/config.toml (gpt-6-luna). If codex is missing or out of tokens, give that step to Haiku and note it in the progress file.
- Haiku (Agent with model "haiku", run in the background) is the first executor for steps 3, 8b, 8f and 8g, and the fallback for any Luna step. Luna is likewise the fallback for a Haiku step.
- Opus (Agent with model "opus", fresh context, read-only) is the consultant. Sonnet sends it:
  - any step that failed verification twice;
  - any fix that would depart from the plan text;
  - a gate FAIL;
  - any conflict between the plan and the code.
  Each consult gets the step's plan rows, the diff, the failing output, and one question. Opus answers with a diagnosis and a concrete fix, not code. Sonnet decides whether to apply it, records the decision and its reason in the progress file, then hands the fix to an executor. If the fix changes the plan, Sonnet also edits the design document in the same commit and says so in the commit body.

SYNAPTREE (code search for both executors)
- Codex reaches synaptree through the `synaptree` server in ~/.codex/config.toml, and Haiku through the synaptree plugin tools. The project name is `tokenfrugal`.
- Before the first dispatch, Sonnet runs `index_repository` for `tokenfrugal` from the main checkout (never a worktree), then checks Codex with:
  codex exec --approve-for-me --ephemeral -C <repo path> "Call the synaptree MCP tool index_status for project 'tokenfrugal'. Do not run shell commands or edit files. Reply in one line: 'SYNAPTREE OK: <status>' or 'SYNAPTREE FAIL: <error>'." < /dev/null
  If it prints SYNAPTREE FAIL, pause the loop and report to me.
- After each merge, Sonnet re-indexes from the main checkout, so the next step searches the merged code.

STEP SPEC (the same for both executors)
- The plan rows for the step, copied in full.
- The files it may touch and the files it must not change.
- The one acceptance command.
- The tool-call limit: 25, or 35 for steps marked large.
- "Do not commit, push or install anything; report the files you changed."
- Pass file paths, never whole files.
- "Find code with synaptree (project tokenfrugal): index_status first, then search_graph or search_code, trace_path for callers and callees, get_code_snippet for one symbol. Read a whole file only after synaptree has located the symbol, or for configs and docs."

VERIFY (Sonnet, after each executor report)
- Check `git status` and `git diff`. A "done" report with no change counts as a failure.
- Run the step's acceptance command, then the full suite:
  $env:PYTHONPATH = "."; python -m unittest discover -s tests -t . -q
- If both pass, close the step in this order:
  1. Commit on the step branch (human author only, no Co-Authored-By trailer, no "generated with" footer).
  2. Push the branch to the `tokenfrugal` remote and open a PR to main with the step's summary, acceptance result and suite result.
  3. From Step 4 on, wait for CI on the PR. A CI failure goes back to the executor as a correction on the same branch, counted like a local failure.
  4. Merge with `gh pr merge <n> --merge --delete-branch`, then confirm with `gh pr view <n> --json state,mergeCommit` that it says MERGED, because the merge command can print nothing.
  5. Run `git switch main`, `git pull --ff-only tokenfrugal main` and `git branch -d impl/step-<id>`, plus `git push tokenfrugal --delete impl/step-<id>` if the remote branch is still there.
  6. Re-index synaptree from the main checkout, and mark the plan_add task done with the merge commit sha.
  The next step, for either executor, is assigned only after all six.
- If either fails, send the same executor a correction with the failing output and only what must change. After a second failure, consult Opus, then give the step to the other executor with the fix. After a failure on both executors with an Opus fix, consult Opus once more for a re-scope (split the step smaller). That is the last automatic attempt; after it, pause the loop and report to me.
- Record every execution in docs/designs/fallback-execution-log.md: executor, attempts, tool calls, elapsed time, result, and any Opus consult. Add one line per dispatch_task or resume_task call to docs/designs/fallback-attempts.jsonl.

LOOP (every 15 minutes)
Start it with `/loop 15m` on the tick below. Each tick first reads docs/designs/subagent-runtime/progress.md, so a restarted loop continues from the first step that is not merged. Each tick:
1. Check the running executor: has it finished, is it still working, or has it stalled (no new file change or output for two ticks)? Stop a stalled job and treat it as a failure.
2. Verify a finished step as above, and decide its outcome.
3. Assign the next step whose order rule allows it:
   - any step only after the previous step's PR is merged and its branch deleted;
   - Step 1 only after `git merge-base --is-ancestor <step-0-sha> HEAD` exits 0;
   - Step 5 only after the Step 4 PR passed CI and is merged;
   - Step 9 only after Step 8h;
   - Step 10 only if Step 9 says build;
   - Step 11 after S2 (or S3) passes the gate.
   Run one writing executor at a time, because steps share files.
4. On a gate FAIL: when S3 is not built yet, build S3 (Step 10) and re-run the gate with `--base s2 --candidate s3`. When S3 already failed the gate, consult Opus, record the diagnosis, and pause the loop for me: the goal cannot be met without a design change.
5. Update docs/designs/subagent-runtime/progress.md with one row per step: executor, state, attempts, Opus consults, PR link, merge commit sha, acceptance result, suite result, next action. Then post a three-line status here: done, running, next.
6. When every GOAL item is true, write the final report, stop the loop (delete its scheduled job so no further tick fires), and end.

PERMISSIONS GIVEN IN ADVANCE
- For each step: create its branch, push it to the `tokenfrugal` remote, open its PR to main, merge that PR with `gh pr merge --merge --delete-branch` once the step is verified (and CI has passed, from Step 4 on), and delete the branch locally and on the remote. Never force push, and never push to main directly: main changes only through a step's PR.
- Everything else still needs me: installing software, pulling models, changing ~/.codex/config.toml or any file outside the repo, and secrets. If a step needs one of these, pause the loop and ask.

FIXED RULES
- Step 1 starts by creating tests/test_tool_surface.py and running `python -m tests.test_tool_surface --write` before any router/ edit. S1-S3 change no MCP tool signature or docstring; the tool surface changes once, in Step 11.
- Step 3 uses the pins in Appendix A. If pip freeze in .venv differs, consult Opus and record the decision; do not change a pin silently.
- Windows, macOS and Linux, with no hardcoded paths; at most 6 tools per role; skills under 1,200 characters; only the two local models in router/tf-roles.yaml.
- Step 4's tests.yml runs on `pull_request` to main and on `push` to main, so each step's PR gets CI before its merge.
- Never paste secrets into a spec or the chat.
- Leave my untracked files alone: docs/haiku-fallback-log.md, .agents/ and scratchpad-pr66.txt. Step 3 replaces .codex/config.toml and .codex/agents/tokenfrugal.toml, as the plan says.

Final report: per step, the executor, commit sha, acceptance result and suite result; totals per executor; every Opus consult and the decision taken; the GATE and S3 decision lines as printed; the CI result; and every PR link with its merge commit sha.
```

## Notes

- **Corpus independence:** the design makes Steps 0 and 8h the owner's, so the corpus rules are fixed apart from the agent being measured. This prompt gives both steps to Sonnet, and requires Sonnet to finish them before it sees any S2 result. If the benchmark must be fully independent, keep Step 0 for the owner.
- **Codex command:** tested on 2026-11-26. With `--sandbox read-only`, `codex exec` lists synaptree but every call fails, because a non-interactive run cannot answer the approval. `--approve-for-me` fixes this without changing ~/.codex/config.toml; `index_status` then returned "stale; 44,813 files". `codex exec` also waits on stdin unless it is closed (`< /dev/null`).
- **One PR per step:** every step, Haiku's included, gets its own PR, because the next step branches from main and needs the previous step's commit.
