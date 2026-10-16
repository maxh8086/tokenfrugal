# Benchmark failure analysis (Opus, independent)

Sources:
- `analysis/evidence.md` (cited as ev:LINE).
- Raw JSONs in `Benchmark/results/raw/`.
- Repo files: `router/config.py`, `router/roles.json`, `router/agents.yaml`, `router/config_overrides.json`, `scripts/bench_real.py`, `scripts/bench.py`, `router/server.py`.
- A read-only copy of `router/tasks.db`, made in the scratchpad, 3488 rows. It has no model or timestamp column; `heartbeat` is set on 2052 rows.

Labels: VERIFIED means checked against the cited file or field. HYPOTHESIS means inferred and not checked.

---

## Q1. Why did cases 1-7 and 9 fail with "MCPError: Connection closed"?

**Confidence: high** on the mechanism (synaptree native server unavailable). **Medium** on the exact failure point inside the start-up sequence, because no boot error was stored.

### Server lists per role

All VERIFIED: `router/roles.json`, `router/agents.yaml` lines 25-38, `router/config_overrides.json` role_mcps.

| Case(s) | Role | Profile servers (role_mcps) | native |
|---|---|---|---|
| 1-5 write_function, fix_bug, write_tests, rename_across_files, find_symbol | builder | filesystem, synaptree | **synaptree** |
| 6 review_sqli | reviewer | filesystem, synaptree, ast-grep, git | **synaptree** |
| 7 debug_trace (engineering-sre) | debugger | filesystem, synaptree, git-history, sequentialthinking, code-interpreter, penpot | **synaptree** |
| 9 role_analyzer | analyzer | filesystem, synaptree, ast-grep, git | **synaptree** |
| 8 summarize_readme, role_research | research | (profile "") | crawl4ai |
| role_data | data | filesystem | none |
| role_docs | docs | filesystem, git-history, fetch | none |
| role_security | security | filesystem, ast-grep, sonarqube | sonarqube |
| role_designer | designer | code-interpreter, penpot | none |
| role_browser | browser | chrome-devtools | none |
| role_tracker | tracker | plan | plan |

- **Only synaptree roles fail.** Every failing case runs a role with `native: [synaptree]`. No case 10-16 role has it. VERIFIED.
- **How the native synaptree server starts.** `router/config.py` lines 67-76 define `NATIVE_SERVERS["synaptree"]` as `docker exec -i synaptree-synaptree-1 node src/cli.js --stdio`. The only alternative is host node, which requires `SYNAPTREE_HOST_NODE=1`, and that variable is set nowhere: `.env` sets only `SYNAPTREE_DIR` and `SYNAPTREE_PROJECT`. VERIFIED.
- **What happens when the container is stopped.** `docker exec` into a stopped container exits at once with "container ... is not running". The stdio pipe closes and the MCP client raises "Connection closed". The docker behaviour is HYPOTHESIS, not observed; it is the standard behaviour.
- **This is not (f)'s mechanism.** The process never reaches `cli.js` boot, so (f)'s mechanism ("cli.js crashes at boot when Neo4j is unreachable") is not what happens. The cause is that the whole synaptree compose project, including the `synaptree-synaptree-1` container, is stopped. HYPOTHESIS, strongly supported by (p).

### Candidates

| | Candidate | For | Against | Verdict |
|---|---|---|---|---|
| (a) | Harness started before the previous model's containers stopped or the new model loaded | Mistral-Nemo started 07:35:41 and its model loaded 07:35:58 (ev:833). | The failures persist for about 2.5 h across 7 models with identical per-case durations (cases 1-5 about 2.5-2.9 s, 6 about 6.4 s, 7 about 16.7 s, 9 about 6.5 s). Cases 10-16 in the same runs reach the model. A load race would hit the first case only. | Refuted (VERIFIED from durations and notes) |
| (b) | Gateway dropping after a tool timeout | none | 0 output tokens and 2.5-17 s duration, so it fails before any model turn. No tool was ever called. | Refuted (VERIFIED: tokens and s fields) |
| (c) | ts-fs-rw failing | Cases 1-5 use filesystem. | role_data and role_docs use filesystem too and run in the same models (Qwen3.5-9B, Qwable and others have non-infra results there). | Refuted (VERIFIED) |
| (d) | Role or profile-level start-up failure | Yes, but it is the native server, not the Docker profile. The fixed per-role durations equal the profile gateway start time, which grows with profile size (build < analyze < debug), before the native open fails. | none | Confirmed as the symptom class. The duration explanation is HYPOTHESIS. |
| (e) | Docker or compose faults | The Qwythos tail (role_security, role_designer, role_browser, role_tracker, role_research) and 32B summarize_readme carry ComposeError. Full strings in tasks.db read "unable to get image '...': request returned 500 Internal Server Error for API route ... dockerDesktopLinuxEngine" (VERIFIED, tasks.db `error`). | These are separate from the MCPError cases. Different roles, a different error class and an earlier time. | A separate fault: a Docker Desktop engine API 500 that affects compose roles. Not the cause of Q1. |
| (f) | Synaptree stack down / cli.js crash on Neo4j | Timing matches (p). All failing roles list synaptree. | No stored boot message. The more likely mechanism is that `docker exec` targets a stopped container. | Confirmed with the correction above (stack stopped, not only Neo4j unreachable). |
| (g) | Plugin stop-on-last-client stopped the stack | Exit 137 (SIGKILL after stop timeout, or kill) is consistent with an orchestrated stop or down. | No log ties the stop to the plugin. | Unverified (see Q9). |
| (h) | Second session or process sharing the stack or tasks.db | "database is locked" in Qwythos role_designer (ev:623) shows another writer on tasks.db at about 07:2x. | One occurrence. It does not explain MCPError. | Weak evidence of concurrency. Not the Q1 cause. |
| (i) | Something else | none | none | No further cause needed. |
| (m) | Failing cases are synaptree roles | | | VERIFIED (table above) |
| (p) | Stack stopped 07:35:47, down until 09:56 | Mistral-Nemo case 1 ran 1/2. Its first dispatch at about 07:35:41-07:35:58 overlaps the 07:35:47 kill, and every later synaptree-role case fails until the end of the gemma-3-12b run (09:51:56, ev:782), before the 09:56:10 restart. | none | Consistent (VERIFIED from timestamps). Why run 1 of case 1 survived is HYPOTHESIS: the session was opened before the kill. |
| (q) | Plugin owns that lifecycle | Not in this repo. | none | Cannot be verified from repo evidence. |

### Stored error strings and earlier runs

- **No stored string carries a boot error.** `router/server.py` stores `hard_trim(f"{type(e).__name__}: {e}", 120)`. Every MCPError in the raw JSONs and in tasks.db reads only "MCPError: Connection closed. Call resume_task(...)". The gateway and docker-exec stderr are not persisted. VERIFIED.
- **The pattern does not appear in earlier runs.** No model run before 07:35:41 has MCPError on cases 1-7 or 9 (VERIFIED: the Q8 script finds no infra notes for any model before Qwythos, and Qwythos's infra cases are all compose roles). The pattern is present from Mistral-Nemo onward, including Qwen3.8-9B, glm4:9b and gemma-3-12b. VERIFIED.

---

## Q2. Are the 150 s timeouts slow inference or tool/server hangs?

**Confidence: medium.**

- **Timeouts follow CPU offload.**
  - Models at 100% GPU rarely time out: Qwen3.5-4B Q6_K, gemma4:e4b and the qwen2.5 family (ev:282, 332-407).
  - Qwen3.5-4B Q6_K (100% GPU, ev:282) passes role_security in 55.4 s, scores 30/32 overall and gets summarize_readme 1/2.
  - The same cases time out in runs with 30-72% CPU share: granite3.3:8b 46% (ev:532), the 9B group 23-30%, the 32B at 72% (ev:657).
  - VERIFIED from processor_split and per-case s/notes. That offload is the cause is HYPOTHESIS, though strong.
- **summarize_readme timeouts are tool-loop churn.**
  - In tasks.db, research-role README tasks show repeated `crawl_markdown`/`crawl_links` calls returning `400 Bad Request` from `http://crawl4ai:11235/crawl` (81 + 8 occurrences), then `web_search` loops. VERIFIED, tasks.db `messages`.
  - Each loop step costs a full model turn, so on offloaded models the 8-step research budget (roles.json max_steps 8) exceeds 150 s.
  - The tools answered every time; nothing hung.
  - This is churn plus slow inference, not a server hang. VERIFIED that tools answered. The timing split is HYPOTHESIS.
- **What separates the two.**
  - **Inference-bound:** tasks.db `messages` for a timed-out task shows tool results returned promptly and many assistant turns; output tokens are greater than 0; processor_split shows a CPU share.
  - **Server hang:** the last message is an assistant tool call with no tool result, and output tokens are near 0.
  - **What is missing:** per-call timestamps. tasks.db has no per-message time, and the JSON keeps no per-run data, only stats and up to 3 notes (`scripts/bench_real.py` run()). VERIFIED.
  - **Cheapest fix:** log per-tool-call latency in `loop.py`.
- **role_browser and role_security** need container backends (chrome-devtools, sonarqube). Their compose `up --wait` time counts against the 150 s, so a cold compose start can also produce a "timeout". HYPOTHESIS. Checking needs per-phase timing that is not recorded.

---

## Q3. summarize_readme: classification, tools, Haiku, checker

**Confidence: high** that the case is invalid as built.

### Tools available to the research role

The research role has `profile ""`, `native [crawl4ai]` and `tools [web_search, crawl_markdown, crawl_links]` (VERIFIED: `router/roles.json`, `router/agents.yaml`).
- It has **no read_file and no fetch.**
- The crawl4ai service runs in its own container (`config.py` lines 96-99: `docker compose -p ts-mcp ... run --rm -T mcp-crawl4ai`) and cannot see `/workspace`.
- Every local-path attempt (`/workspace/...`, `file:///...`, `http://localhost/...`) returns 400 (VERIFIED, tasks.db).

**The case cannot be passed honestly.** Its label, "Fetch MCP server", is also wrong: `support-docs-writer` routes to the research role, not to docs (which has fetch and filesystem).

### How Haiku "passed"

VERIFIED from the tasks.db copy:
- The Haiku run started 20:15:42 IST (raw filename `20261015-201542-haiku-baseline`).
- Its research tasks are 5bd06707a8 (heartbeat 20:19:21) and aa52fe7aee (20:19:58).
- Both made four crawl calls on local-path variants (all 400), then one `web_search`.
- Both final summaries refused correctly. They start "I could not read `/workspace/tokenfrugal/README.md` ..." and contain "**Local reads (4 attempts):**" or "**Local file reads failed.**".

The checker `_has("mcp","local")` (`scripts/bench_real.py` line 24: lowercase substring) matched "local" in the refusal. **Haiku's 2/2 is a false pass on an honest failure report.**

### Classification of the zeros

From evidence.md notes and tasks.db; VERIFIED where a note or row exists.

| Category | Models |
|---|---|
| (e) tool/API error | ministral-3-8b (Ollama 500 "tool 'read_file' not found", see Q4). Every run that tried crawl4ai also had 400 tool errors, but those runs ended in another category. |
| (a) no tool call, or tool call written as text | Mistral-Nemo (LoopError, answered without tool); qwen2.5-coder variants and llama3.1-8b (JSON tool call emitted as text); phi4-mini, granite3.3-2b, DeepSeek-R1-Distill, glm4:9b (no tool call); gemma3:4b, starcoder2:7b, gemma-3-12b (HTTP 400, tools unsupported) |
| (b) truncated or no final answer | gemma4:e4b (loop ended with no final answer) |
| (c) or (d) honest "could not read" answer that missed the substring | qwen2.5 1.5B / 3B-class runs. Their answers are the correct behaviour given the tools, which is the opposite of the checker's intent. |
| (f) infra or timeout | 32B (ComposeError, engine API 500); Qwen3.5-9B, Qwable, Qwen3.8-9B, granite3.3-8b (150 s timeout during the crawl/search loop); the four watchdog models (no result) |

**No zero is a "reasonable summary rejected by the checker".** No model could read the file. Any pass came either from web-search text about unrelated "token-frugal"/FrugalGPT projects that contained "mcp" or "local", or from refusals containing "local". The Qwen3.5-4B 1/2 belongs in one of these two groups. Which one is HYPOTHESIS, because tasks.db cannot map rows to that model by time without heartbeat.

**Is the case measuring what it claims?** No. It measures how the agent handles a crawler failure, and the checker scores refusals and hallucinations alike.

### Fix

- **Routing.** Route the task to a role that has `read_file`: use the docs role (`engineering-technical-writer`), or add `filesystem` to research. Alternatively, rename the case and keep it as a "can't read: does the model admit it?" test with an inverted checker.
- **Rubric.** Require at least 2 README-specific facts, for example:
  - "router" or "dispatch_task"
  - "Ollama", "local LLM" or "OpenAI-compatible"
  - "150-300 token" or "summary"
  - "MCP"
- **Failing terms.** Any of these should fail the answer: "OpenAI API", "GitHub platform", "FrugalGPT", "could not read", "unable to read".
- **Trail evidence.** Require a successful `read_file` tool result in the task trail.

---

## Q4. ministral-3-8b summarize_readme HTTP 500

**Confidence: high.**

- **Full stored error (VERIFIED, tasks.db `error`; tasks 900de9d7c2, 6177cd78ca):** `InternalServerError: Error code: 500 - {'error': {'message': "tool 'read_file' not found", 'type': 'api_error', ...}}`.
- **The model's mistake.** ministral called `read_file`, which the research role does not offer (VERIFIED, roles.json tools list).
- **Who returned the 500.** The LLM endpoint `http://localhost:11434/v1` (Ollama, VERIFIED: roles.json llm_url). Ollama's tool-call parser rejected a call to a tool missing from the request's `tools` array and returned 500 instead of passing it through.
- **Not the router and not an MCP server.** No MCP call was made.
- **The same Ollama error appears elsewhere.** It shows up for `write_file` and `edit_file` on other roles and models (VERIFIED, tasks.db), so it is a model-side hallucinated tool name surfaced by Ollama as a 500.

---

## Q5. Trustworthy results and re-runs

**Confidence: medium-high.**

### Trustworthy for ranking (no infra notes; VERIFIED by the Q8 script)

- All 22 completed runs from llama3.2-1b through ministral-3-8b (20:15-06:43). Haiku is included, but its summarize_readme pass is false.
- Exclude summarize_readme from every model (invalid, Q3).
- Treat role_tracker and role_designer passes with caution (lax checks, noted in evidence.md).

### Must re-run

1. Mistral-Nemo, Qwen2.5-Coder-32B, Qwen3.5-9B, Qwable-9B, Qwen3.8-9B, glm4:9b and gemma-3-12b: cases 1-7 and 9, with the synaptree stack verified up (`docker ps` shows `synaptree-synaptree-1`).
2. Qwythos-9B: role_security, role_designer, role_browser, role_tracker and role_research (ComposeError or DB lock).
3. Qwen2.5-Coder-32B: summarize_readme (ComposeError). Only after the case is fixed.
4. qwen3:4b, qwen3:8b, deepseek-r1:8b and Minitron: whole run (watchdog, no results). Use a smaller num_ctx or think off, free RAM first (qwen3:4b RAM max 99.3%), and keep per-case results so the watchdog does not erase partial data.
5. summarize_readme for every model, after the Q3 fix.

Valid but low-signal (do not re-run): gemma3:4b, starcoder2:7b, phi4-mini, granite3.3-2b and DeepSeek-R1-Distill. These are real capability failures (Q7).

---

## Q6. Goal: thinking and summarising model plus a reliable tool-calling builder

**Confidence: medium** for the builder. **Low** for the thinker/summariser, because it is not measured.

### What the valid results say

Scores are valid cases excluding summarize_readme (out of 30); VERIFIED, Q8 script.

| Model | Score | Mean time |
|---|---|---|
| Qwen3.5-4B Q6_K | 29/30 | 21.4 s |
| gemma4:e4b | 28/30 | 18.8 s |
| llama3.2:3b-16k (current thinker) | 24/30 | 14.3 s |
| qwen2.5-coder:7b | 24/30 | 18.6 s |
| ministral-3-8b | 24/30 | 40.3 s, 49% CPU |
| qwen2.5-coder:7b-q5_K_M | 23/30 | |
| qwen2.5:7b | 22/30 | |
| granite4:micro | 21/30 | |
| qwen2.5-coder-yarn:3b (current builder) | 17/30 | |

- **Builder.** The 100%-GPU leaders, Qwen3.5-4B Q6_K and gemma4:e4b, are the best-supported builder candidates. The current builder scores lowest of the 7B-class and Qwen3.5 options. VERIFIED (scores). That a swap would help is HYPOTHESIS until it is re-run with n greater than 2.
- **Sample size.** With n=2 per case, differences of 1-2 points are within noise. HYPOTHESIS, a statistical judgement.
- **9B / 32B models.** Partial valid results (10-12/14) cannot be compared yet (Q5).

### Not yet measured

- Document summarisation quality: the only summary case is invalid (Q3).
- Long-document or long-context handling: num_ctx is not recorded in the JSON (ev:57 et seq.).
- Reasoning or "thinking" quality: no case scores reasoning; think mode is not recorded (ev:581).
- The thinking-model family itself (qwen3, deepseek-r1): no results at all.
- Variance: n=2.
- Faithfulness and hallucination rate in summaries.

---

## Q7. Weak or zero rows

**Confidence: medium-high.** Based on evidence.md notes per case, VERIFIED unless marked.

| Model | Class | Evidence |
|---|---|---|
| gemma3:4b | Tool-support error (HTTP 400) | 0/32, mean 9.5 s; notes: 400 "does not support tools" |
| starcoder2:7b | Tool-support error (HTTP 400) | 0/32, mean 9.6 s; same note |
| phi4-mini | Model failed to call tools (LoopError "answered without calling any tool"), with a few passes | 2/32; 25% CPU (ev:207) |
| granite3.3-2b | Model failed to call tools | 7/32 |
| granite3.3-8b | Mostly timeout (150 s), plus no-tool LoopErrors | 0/32, mean 97.9 s, 46% CPU (ev:532, 548) |
| DeepSeek-R1-Distill-Qwen-7B | Model failed to call tools (reasoning text, no tool call); slow | 0/32, mean 65.7 s, 12% CPU (ev:432) |
| qwen3:4b | Timeout or infra, no results (section watchdog 3600 s) | 26% CPU, RAM max 99.3%. Cause unverified. HYPOTHESIS: thinking-mode token volume plus offload and memory pressure |
| qwen3:8b | Timeout or infra, no results (watchdog) | 29% CPU (ev:482). Same HYPOTHESIS |
| deepseek-r1:8b | Timeout or infra, no results (watchdog) | 42% CPU (ev:507). Same HYPOTHESIS |
| Mistral-NeMo-Minitron-8B | Timeout or infra, no results (watchdog) | **100% GPU** for the whole hour (ev:557), so offload does not explain it. Cause unknown. HYPOTHESIS: a generation loop with no stop token, or a stuck tool loop |

Related cases:
- glm4:9b (0/16 valid) is a no-tool LoopError on its valid cases, plus Q1 infra.
- gemma-3-12b (0/16 valid) is HTTP 400 tool support, plus Q1 infra.

The watchdog rows are an infra or harness gap as well. One hung case wipes the whole section's results.

---

## Q8. Valid-case means

**Confidence: high** for the arithmetic, which is VERIFIED from the raw JSON `verified`, `s.mean` and `notes` fields.

**Method.**
- A case is excluded if any of its notes contain MCPError, ComposeError, "compose up failed" or "database is locked".
- Score is the sum of verified passes over valid cases. Time is the mean of per-case `s.mean` over valid cases.
- **Limitation:** cases partly hit by infra (for example Mistral-Nemo write_function, ran 1/2) are excluded whole, because the JSON keeps no per-run data.

| Model | Valid cases | Score (valid) | Mean s (valid) | Score excl. readme | Mean s excl. readme | Raw mean s (all) |
|---|---|---|---|---|---|---|
| haiku-baseline | 16 | 32/32 | 18.4 | 30/30 | 16.7 | 18.4 |
| llama3.2-1b | 16 | 8/32 | 20.2 | 8/30 | 19.2 | 20.2 |
| qwen2.5-1.5b | 16 | 11/32 | 12.0 | 11/30 | 12.1 | 12.0 |
| granite3.3-2b | 16 | 7/32 | 15.2 | 7/30 | 15.4 | 15.2 |
| qwen2.5-coder-yarn-3b | 16 | 17/32 | 18.0 | 17/30 | 18.5 | 18.0 |
| llama3.2-3b-16k | 16 | 24/32 | 14.2 | 24/30 | 14.3 | 14.2 |
| granite4-micro | 16 | 21/32 | 14.4 | 21/30 | 14.5 | 14.4 |
| phi4-mini | 16 | 2/32 | 23.2 | 2/30 | 23.9 | 23.2 |
| gemma3-4b | 16 | 0/32 | 9.5 | 0/30 | 9.5 | 9.5 |
| qwen3-4b | 0 | no results (watchdog) | - | - | - | - |
| Qwen3.5-4B Q6_K | 16 | 30/32 | 22.8 | 29/30 | 21.4 | 22.8 |
| starcoder2-7b | 16 | 0/32 | 9.6 | 0/30 | 9.6 | 9.6 |
| gemma4-e4b | 16 | 28/32 | 19.5 | 28/30 | 18.8 | 19.5 |
| qwen2.5-7b | 16 | 22/32 | 16.4 | 22/30 | 15.8 | 16.4 |
| qwen2.5-coder-7b | 16 | 24/32 | 18.2 | 24/30 | 18.6 | 18.2 |
| qwen2.5-coder-7b-q5_K_M | 16 | 23/32 | 17.3 | 23/30 | 17.7 | 17.3 |
| DeepSeek-R1-Distill-Qwen-7B | 16 | 0/32 | 65.7 | 0/30 | 67.2 | 65.7 |
| llama3.1-8b | 16 | 18/32 | 41.8 | 18/30 | 42.3 | 41.8 |
| qwen3-8b | 0 | no results (watchdog) | - | - | - | - |
| deepseek-r1-8b | 0 | no results (watchdog) | - | - | - | - |
| granite3.3-8b | 16 | 0/32 | 97.9 | 0/30 | 94.3 | 97.9 |
| Minitron-8B | 0 | no results (watchdog) | - | - | - | - |
| ministral-3-8b | 16 | 24/32 | 40.0 | 24/30 | 40.3 | 40.0 |
| Qwythos-9B | 11 | 17/22 | 65.1 | 17/20 | 55.5 | 86.4 |
| Mistral-Nemo-12B | 8 | 12/16 | 37.8 | 12/14 | 39.6 | 23.3 |
| Qwen2.5-Coder-32B | 7 | 10/14 | 70.0 | 10/14 | 70.0 | 38.0 |
| Qwen3.5-9B | 8 | 12/16 | 99.9 | 12/14 | 91.7 | 52.6 |
| Qwable-9B | 8 | 10/16 | 105.4 | 10/14 | 98.0 | 55.6 |
| Qwen3.8-9B | 8 | 12/16 | 101.8 | 12/14 | 94.4 | 53.6 |
| glm4-9b | 8 | 0/16 | 35.4 | 0/14 | 32.9 | 20.4 |
| gemma-3-12b | 8 | 0/16 | 11.0 | 0/14 | 11.1 | 8.2 |

**Effect of the correction.** The raw means for the 7 post-07:35 models are understated by roughly 2x, because of the near-instant MCPError cases. Their valid cases are the slower role cases only, so their means are still not comparable with full-suite models. Compare per case instead. HYPOTHESIS on comparability.

---

## Q9. Who stopped the synaptree stack at 07:35:47 and started it at 09:56:10?

**Confidence: low.** The evidence does not identify the actor.

### What the evidence permits

- **Event times (VERIFIED, ev):** synaptree exited 137 at 07:35:47 IST and neo4j stopped at 07:35:54. The stack came back at 09:56:10/09:56:23.
- **Exit 137 means SIGKILL.** That fits `docker stop` or `compose stop/down` exceeding the stop grace period on the node process, or a direct `docker kill`. It does not fit a crash on its own (a crash usually exits 1). HYPOTHESIS.
- **Ordered shutdown.** The synaptree container stopped before neo4j, 7 s apart, which matches a compose stop that removes dependents first. HYPOTHESIS.
- **The benchmark did not do it.** The stop came 6 s after a benchmark section began (07:35:41). The router's compose logic only touches project `ts-mcp` (CLAUDE.md, `compose.py`), and synaptree is a different compose project. VERIFIED that it is a different project name in config.py (`synaptree-synaptree-1` versus `-p ts-mcp`).

### What it does not permit

- Nothing in the repo, the JSONs or tasks.db records who issued the stop or start.
- Closing or opening a Claude Code window or session leaves no transcript entry that marks the moment of a plugin's stop-on-last-client hook.
- (g)/(q), the plugin lifecycle, remains a plausible candidate: a Claude Code session using the synaptree plugin closing at about 07:35 and one opening at about 09:56. A manual stop, or a Docker Desktop resource action, is equally unexcluded.

### Cheapest checks (in order)

1. **Session times.** List the mtimes and first and last record timestamps of `~/.claude/projects/*/*.jsonl` (and subagent jsonl files) around 07:30-07:40 and 09:50-10:00. A session whose last write is about 07:35:4x, and another whose first write is about 09:56, points to the plugin. Read-only, seconds.
2. **Synaptree plugin log.** Read its own log or hook output, if it writes one (check the plugin directory under `~/.claude/plugins/`). Look for a "last client, stopping" line.
3. **Docker Desktop logs.** Read the daemon and backend logs (`%LOCALAPPDATA%\Docker\log\vm\dockerd.log`, `host\com.docker.backend.log`) for the window. They show the API call (`POST /containers/.../stop` versus `kill`, or a compose label) and the client user-agent (compose CLI version or docker CLI).
4. **Going forward.** Run `docker events --filter label=com.docker.compose.project=synaptree` in the background during benchmarks. Add a pre-case health check in `bench_real.py` that aborts on a missing `synaptree-synaptree-1` instead of recording MCPError.
