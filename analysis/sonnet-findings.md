# Sonnet findings (Q1-Q9)

Sources: analysis/evidence.md, Benchmark/results/raw/*.json (31 files), router/roles.json, router/config_overrides.json, router/agents.yaml, router/config.py (lines 70-76), router/loop.py, scripts/bench_real.py (cases, lines 85-125). Read-only; nothing was run against Docker or the benchmark.
Labels: VERIFIED (cited) or HYPOTHESIS. Stored notes in the JSONs are truncated to about 110 characters.

## Q1 Connection closed on cases 1-7 and 9 (confidence: medium-high that the synaptree stack being down is the cause)

Failing cases and their roles (VERIFIED, bench_real.py + roles.json): 1-5 builder, 6 reviewer, 7 debugger, 9 analyzer. All four roles list the native `synaptree` server (roles.json; agents.yaml native: [synaptree]). Roles without it: data (filesystem), docs (filesystem, git-history, fetch), security (filesystem, ast-grep, sonarqube), designer (code-interpreter, penpot), browser (chrome-devtools), tracker (plan), research (web-search: web_search, crawl_markdown, crawl_links). Cases 10-16 use exactly these no-synaptree roles. (m) VERIFIED.

Mechanism (VERIFIED, router/config.py 70-76): NATIVE_SERVERS["synaptree"] is `docker exec -i synaptree-synaptree-1 node src/cli.js --stdio` (unless SYNAPTREE_HOST_NODE=1). If that container is not running, docker exec exits immediately and the stdio MCP client reports "Connection closed". evidence.md docker ps -a: synaptree-synaptree-1 Exited (137), synaptree-neo4j-1 Exited (0). So the mechanism need not be a Neo4j boot crash; a stopped container is sufficient (this refines the question's wording of (f)).

Per candidate:
- (f) stack down: FOR: exact case/role match; seven affected runs all start inside the outage window 07:35:47-09:56:10 IST (Mistral-Nemo started 07:35:41); durations are role-dependent and model-independent (about 2.5-3 s builder, 6-7 s reviewer/analyzer, 16-17 s debugger, consistent with deterministic start-up work of each role's gateway before the failing native server). AGAINST: none found. Best explanation.
- (p) VERIFIED as timestamps (evidence.md). Causal link is inferred.
- (a) harness started before prior containers shut down: AGAINST: it would hit all roles, not only synaptree roles; non-synaptree roles ran in the same runs.
- (b) gateway dropping after tool timeout: AGAINST: 0 output tokens at 2.5 s, no tool call had happened.
- (c) ts-fs-rw failing: AGAINST: data/docs/security (filesystem) passed in the same runs (Mistral-Nemo data 2/2, docs 2/2, security 2/2).
- (d) role/profile start-up failure: AGAINST: the same roles ran before 07:35:47 for earlier models (e.g. llama3.1-8b, ministral, Qwythos cases 1-7, 9 ran normally).
- (e) Docker/compose faults: PARTLY. Compose errors do exist (Qwythos cases 12,13,15,16 "ComposeError: compose up failed: unable to get im..."; Coder-32B case 8), but these hit non-synaptree roles at different times, so they are a separate, intermittent fault, not this pattern.
- (g) plugin stop-on-last-client: HYPOTHESIS, plausible for the stop at 07:35:47 (see Q9); not verifiable from the data.
- (h) second session sharing stack/tasks.db: HYPOTHESIS, supported by "EXC OperationalError: database is locked" (Qwythos designer, VERIFIED in notes) and the unrelated container glossary-workbook-changes-78e56f-ui-1 in docker ps; this explains the compose/lock faults, and may be the actor in Q9.
- (i) other: none needed.

Boot error in stored strings: no. Notes end at "MCPError: Connection closed. Call resume_task('...')" with no stderr. VERIFIED. Full text may exist in router/tasks.db (not examined).
Same pattern at the start of other runs: no. Runs before 07:35 (haiku through Qwythos) have no Connection closed on cases 1-7/9; Qwythos has CC only on browser (case 14, about 85 s), a different server. Affected runs: Mistral-Nemo (from case 1 run 2), Coder-32B, Qwen3.5-9B, Qwable, Qwen3.8, glm4, gemma3-12b (all VERIFIED in the JSONs). Whether each of the last three was run entirely inside the window is inferred from identical case pattern, not timestamps.

## Q2 150 s timeouts: slow inference vs hangs (confidence: medium)

VERIFIED: Qwen3.5-4B Q6_K ran 100% GPU (processor_split 343 of 345 samples "100% GPU", max_cpu_share 26%) and had no timeouts; 30/32; its slowest cases were summarize (about 43 s mean) and security (about 55 s). The same cases time out in CPU-offloaded 9B runs (Qwythos 30%/70% CPU/GPU: summarize timed out at 162 s; Qwen3.5-9B, Qwable, Qwen3.8 summarize TO; Coder-32B security/browser TO).
HYPOTHESIS: timeouts are slow inference (offload plus long generation or thinking), not tool hangs. Support: the same role/tool servers complete fast with the faster model; non-timeout cases in the same slow runs finish at 89-162 s, near the limit, which suggests a continuum of speed rather than a stuck server. Against/unresolved: a tool-timeout (60 s) retried by the model would also look slow; per-case hardware samples cannot be aligned to cases, and the task_timeout error does not record which step stalled. Separating evidence needed: per-step timings in tasks.db for a timed-out task (tool call durations vs generation durations).

## Q3 summarize_readme (confidence: medium)

Classification of every 0/2 (from the per-case table; (b) truncated/no final answer):
- (a) no tool call ("answered without calling any tool"): Mistral-Nemo-Instruct, glm4-9b, DeepSeek-R1-Distill-7B, granite3.3-2b.
- (b) no final answer: gemma4-e4b (NF). Also "wrote a tool call as text": qwen2.5-coder-7b, q5_K_M, llama3.1-8b, llama3.2-1b (TXT, closest to (a)/(d)). Filler/placeholder: qwen2.5-7b, phi4-mini (FIL, (d)). Timeouts (150 s, slow inference, see Q2): Qwythos, Qwen3.5-9B, Qwable, Qwen3.8, granite3.3-8b.
- (e) API error: gemma3-4b, starcoder2-7b, gemma3-12b (HTTP 400, no tool support); ministral-3-8b (HTTP 500, see Q4).
- (f) infra: Coder-32B (ComposeError).
- (c)/(d) answered but failed checker: llama3.2:3b-16k, granite4-micro, qwen2.5-1.5b, qwen2.5-coder-yarn-3b. I did not read their answer text, so (c) vs (d) is undetermined for these.

Research role file tools (VERIFIED, roles.json): research = web-search with web_search, crawl_markdown, crawl_links only; no read_file. The task says "Read /workspace/.../README.md", so a faithful model cannot read it. Qwen3.5-4B's stored answer begins "I was unable to read /workspace/tokenfrugal/RE..." yet it scored 1/2, which means the checker also passes answers that say it could not read the file (VERIFIED partial text, notes field). Haiku passed 2/2 (about 44 s, 2197 output tokens); how it obtained content (web crawl, hallucination from the repo name, or a file tool) is NOT checked; this needs the tool-call rows from a copy of tasks.db.
Does the case measure its label? VERIFIED mismatch: bench_csv labels it "Fetch MCP server (mcp/fetch)" but the role used is research (no fetch, no local file reader; fetch is in docs). It measures nothing reliable about fetching or summarising.
Checker: substring "mcp" or "local" is satisfiable by refusals or generic text ("local" appears in "unable to read the local file"). HYPOTHESIS for a rubric: require at least two of README-specific facts (e.g. "router", "dispatch_task", "Ollama", "FastMCP"), require a tool call to a file or fetch tool in the trace, reject refusal phrases ("unable", "cannot access"), and reject known-wrong terms ("OpenAI API", "GitHub platform"). Fix the role (use docs, or give research a file reader) or serve the README by URL.

## Q4 ministral-3-8b HTTP 500 (confidence: medium)

VERIFIED note: "FAILED (research/ministral-3:8b): InternalServerError: Error code: 500 - {'error': {'message': \"tool 'read_fil..." (truncated). It is the OpenAI-client InternalServerError, i.e. returned by the LLM endpoint (Ollama's /v1), not by MCP or Docker. The message names a tool read_file, which the research role did not offer (VERIFIED roles.json). HYPOTHESIS: the model emitted a tool call to an unregistered tool and Ollama's tool-call parsing/validation rejected it with 500. The full message is not stored; check tasks.db or the Ollama log.

## Q5 Rankable vs re-run (confidence: medium)

Rankable (all 16 cases valid, no infra rows): haiku, llama3.2-1b, qwen2.5-1.5b, granite3.3-2b, qwen2.5-coder-yarn-3b, llama3.2-3b-16k, granite4-micro, phi4-mini, Qwen3.5-4B Q6_K, gemma4-e4b, qwen2.5-7b, qwen2.5-coder-7b (both quants), DeepSeek-R1-Distill-7B, llama3.1-8b, granite3.3-8b, ministral-3-8b. Caveats: summarize_readme is invalid as a measure (Q3), so rank on 15 cases or fix it; ministral's 500 is a model/endpoint behaviour, scored as a fail.
Partially valid (re-run the invalid cases, do not rank on full score): Qwythos-9B (12 valid; cases 12,13,15,16 compose/lock, 14 CC), Mistral-Nemo-Instruct (9 valid), Qwen2.5-Coder-32B, Qwen3.5-9B IQ4_XS, Qwable-9B, Qwen3.8-9B, glm4-9b (8 valid each: cases 1-7 and 9 are infra).
Re-run fully: gemma3-12b (0 valid; 400 on 8, infra on 8; the 400s are legit tool-unsupported but the other 8 are unknown).
No data (3600 s section watchdog): qwen3:4b, qwen3:8b, deepseek-r1:8b, Mistral-NeMo-Minitron-8B. Re-run with a larger watchdog or fewer cases.
Do not rank gemma3:4b and starcoder2:7b; they are unsupported for tools (valid result: "not usable", not "scored 0").

## Q6 Your goal (confidence: low-medium)

Valid data, builder tool-calling: Haiku 32/32 is the ceiling. Best local: Qwen3.5-4B Q6_K 30/32 at 22.8 s (100% GPU), gemma4-e4b 28/32, llama3.2-3b-16k 24/32 (14 s), ministral-3-8b 24/32, qwen2.5-coder-7b 24/32. Qwen2.5-coder-yarn-3b (the configured builder) only 17/32. These are builder-role scores partly; note builder cases 1-7 are the cases lost for the 9B+ models, so no valid builder score exists for Coder-32B, Qwen3.5-9B, Qwable, Qwen3.8, glm4, Mistral-Nemo (beyond case 1).
Thinker/summariser: not measured. summarize_readme is broken (Q3) and no case tests long-document summarising or reasoning quality. Not yet measured: valid builder results for the post-outage 9B-32B models, summarisation quality with a rubric, long-context behaviour, thinking-model results (the four watchdog models), the Haiku tool trace for summarize.

## Q7 Weak/zero rows (confidence: high for 400, medium otherwise)

- gemma3:4b, starcoder2:7b: tool-support error (HTTP 400, all 16 cases, about 9.5 s each). VERIFIED.
- phi4-mini (2/32): model failed to call tools (NT on most cases), plus FIL on summarize, TO on tracker; designer 2/2.
- granite3.3-2b (7/32): model failed to call tools (almost all NT).
- granite3.3-8b (0/32, 97.9 s mean): mixture of NT and timeouts (TO on cases 2,3,4,7,8,13).
- DeepSeek-R1-Distill-7B (0/32, 65.7 s): model failed to call tools (NT everywhere), TO on fix_bug and research.
- qwen3:4b, qwen3:8b, deepseek-r1:8b, Minitron-8B: timeout of the whole section (results.realworld.error "no result after 3600.0s (section watchdog)", VERIFIED). No per-case data. GPU util averaged 35-99% over 1690-1719 samples, so the models were busy. HYPOTHESIS: thinking models or heavy offload exceeding the budget; Minitron (cpu avg 14.6%, GPU 99.2%) looks GPU-bound and slow rather than CPU-offloaded, so its cause is unclear.

## Q8 Valid-case means (excludes Connection closed, ComposeError, database locked, HTTP 400 cases; computed by script over the raw JSONs; case mean of per-case means)

Model: valid cases, score, mean s per valid case
- haiku-baseline: 16, 32/32, 18.4
- llama3.2-1b: 16, 8/32, 20.2
- qwen2.5-1.5b: 16, 11/32, 12.0
- granite3.3-2b: 16, 7/32, 15.2
- qwen2.5-coder-yarn-3b: 16, 17/32, 18.0
- llama3.2-3b-16k: 16, 24/32, 14.2
- granite4-micro: 16, 21/32, 14.4
- phi4-mini: 16, 2/32, 23.2
- Qwen3.5-4B Q6_K: 16, 30/32, 22.8
- gemma4-e4b: 16, 28/32, 19.5
- qwen2.5-7b: 16, 22/32, 16.4
- qwen2.5-coder-7b: 16, 24/32, 18.2
- qwen2.5-coder-7b q5_K_M: 16, 23/32, 17.3
- DeepSeek-R1-Distill-7B: 16, 0/32, 65.7
- llama3.1-8b: 16, 18/32, 41.8
- granite3.3-8b: 16, 0/32, 97.9
- ministral-3-8b: 16, 24/32, 40.0
- Qwythos-9B: 12, 17/24, 76.1 (raw 86.4 over 16)
- Mistral-Nemo-Instruct: 9, 12/18, 37.0 (raw 23.3)
- Qwen2.5-Coder-32B: 8, 10/16, 70.7 (raw 38.0)
- Qwen3.5-9B: 8, 12/16, 99.9 (raw 52.6)
- Qwable-9B: 8, 10/16, 105.4 (raw 55.6)
- Qwen3.8-9B: 8, 12/16, 101.8 (raw 53.6)
- glm4-9b: 8, 0/16, 35.4 (raw 20.4)
- gemma3-4b, starcoder2-7b, gemma3-12b: 0 valid (400 or infra); no mean.
- qwen3:4b, qwen3:8b, deepseek-r1:8b, Minitron-8B: no data.
Notes: the partial runs cover different case subsets (non-synaptree roles only), so their scores and times are not comparable to the full-16 rows; summarize_readme remains in every valid count.

## Q9 Who stopped (07:35:47 IST) and started (09:56:10 IST) the stack (confidence: low)

Evidence permits: synaptree container Exited (137) at 02:05:47Z, neo4j Exited (0) at 02:05:54Z (so an ordered shutdown starting 7 s later for neo4j; 137 = SIGKILL, typical of docker stop/kill after grace or OOM), restart 09:56:10/09:56:23 IST, and the first failing run starting 6 s earlier (07:35:41). It does not identify the actor: the plugin's stop-on-last-client logic (g), a second Claude Code window closing, a manual compose command, or Docker Desktop. Closing or opening a window leaves no transcript. The benchmark itself does not manage this stack (HYPOTHESIS: its compose handling is for ts-mcp, not the plugin project).
Cheapest check (propose only, not run): `docker events --since <07:30 IST> --until <07:40 IST> --filter container=synaptree-synaptree-1` if retained, or `docker inspect -f '{{.State.FinishedAt}} {{.State.StartedAt}} {{.State.ExitCode}} {{.State.OOMKilled}}'` on both containers; then the plugin's own log and the compose project label (`docker inspect` Config.Labels com.docker.compose.*) to see who ran compose, and the Claude Code session list for windows closed at 07:35.
