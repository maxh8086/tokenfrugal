Q1. Why did cases 1-7 and 9 fail with "MCPError: Connection closed" (0 output tokens, 2.5-17 s each) in the
    Mistral-Nemo-Instruct (from its second run of case 1), Qwen2.5-Coder-32B, Qwen3.5-9B and Qwable-9B runs
    (and Qwen3.8-9B, glm4:9b and gemma-3-12b as they finish), while cases 10-16 mostly ran? Candidates to
    confirm or refute; none is assumed:
    (a) harness started before the previous model's containers shut down or the new model loaded;
    (b) gateway dropping after a tool timeout;
    (c) ts-fs-rw failing;
    (d) a role/profile-level start-up failure;
    (e) Docker/compose faults;
    (f) the synaptree compose stack (Neo4j on 127.0.0.1:17687) being down, because the native
        `synaptree cli.js --stdio` crashes at boot when Neo4j is unreachable;
    (g) the plugin's stop-on-last-client logic stopping that stack;
    (h) a second session or process sharing the stack or tasks.db;
    (i) something else.
    Also: (m) cases 1-7 and 9 use synaptree-listing roles (builder, analyzer, reviewer, debugger); (p) the synaptree
    compose project was stopped (synaptree exit 137 at 02:05:47Z = 07:35:47 IST, neo4j stopped 02:05:54Z) seconds after the
    Mistral-Nemo run started (07:35:41 IST) and stayed down until 09:56:10/09:56:23 IST; (q) the plugin owns that lifecycle
    (start on connect, stop on last client exit).
    For each candidate, give evidence for and against. State which servers each role's server list contains
    (router/config_overrides.json, router/roles.json, scripts/bench.py, router/config.py) for the failing
    cases versus cases 10-16. State whether any stored error string carries a boot error. State whether the
    same pattern appears at the start of the other models' runs.
Q2. Are the 150 s timeouts (summarize_readme, role_security, role_browser and others) slow inference
    (CPU offload, thinking) or tool/server hangs? Compare the same cases in the Qwen3.5-4B Q6_K run
    (100% GPU). What evidence separates the two?
Q3. Across all models, classify every summarize_readme 0/2 as: (a) no tool call, (b) truncated or no final
    answer, (c) reasonable answer rejected by the checker, (d) genuinely poor, (e) tool/API error,
    (f) infra fault. The case is labelled "Fetch MCP server" (fetches URLs) but the task reads the local
    path /workspace/tokenfrugal/README.md: which tools does the research role have for reading a local
    file, and how did Haiku pass (tool calls from a COPY of router/tasks.db)? Is the case measuring what it
    claims? Does the checker (substring "mcp" or "local") need a rubric, and what should it contain so that
    "OpenAI API" or "GitHub platform" answers fail?
Q4. What is the ministral-3-8b summarize_readme HTTP 500, and which component returned it?
Q5. Which results are trustworthy enough to rank, and which must be re-run?
Q6. For my goal (a local model that thinks well and summarises documents, plus a separate builder that
    calls tools reliably), what do the valid results say, and what is not yet measured?
Q7. Classify each weak or zero row as: tool-support error (HTTP 400), model failed to call tools
    (LoopError "answered without calling any tool"), timeout, or infra fault. Cover gemma3:4b,
    starcoder2:7b, phi4-mini, granite3.3-2b, granite3.3-8b, DeepSeek-R1-Distill-7B and the four
    timed-out models (qwen3:4b, qwen3:8b, deepseek-r1:8b, Mistral-NeMo-Minitron-8B).
Q8. mean_s_per_case includes near-instant infra failures. Recompute per-model mean time and score over
    valid cases only, and state each model's valid-case count.
Q9. Who stopped the synaptree stack at 07:35:47 IST and who started it at 09:56:10 IST? State what the
    evidence permits and what it does not (for example, closing or opening a Claude Code window writes no
    transcript). Propose the cheapest check that would identify the actor.
