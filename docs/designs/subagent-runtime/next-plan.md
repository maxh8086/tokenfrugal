Draft, unreviewed, not approved (2026-11-27)

## Where it stands

PRs 108 through 125 merged. The base arm passed 5 of 20 tasks. S2 passed 4 of 20, with 8 false-success runs. S3 passed 4 of 20, with 3 false-success runs. Both candidates missed the frozen gate of 16 passing tasks and zero false-success runs. The owner ended the run with S3 enabled. S2 and S3 are unreleased. Step 11 has not been built. [Replay results](../../../Benchmark/replay/RESULTS.md) · [Owner decision](progress.md#open-items) · [Assignment](session-handoff.md)

## What is known and not known

- Most real-work tasks lacked an accept command. Others used checks such as `py_compile` or `--help` that can pass even when the requested behaviour is missing. The hidden check exposed failures after the router reported success. Six distinct S2 tasks and three S3 tasks had a false success. [Replay results](../../../Benchmark/replay/RESULTS.md) · [Step 9 and 10 decision notes](progress.md#open-items)
- S2 recorded 11 `out_of_time` stops in 28 runs. S3 recorded 11 in 24. In five S2 diagnostic reruns, model calls and the interrupted final step accounted for most of the time. Setup took 39 to 53 seconds, no tool call exceeded 10 seconds, and 13 to 94 seconds per run fell outside router events. Those five traces do not establish the cause of timeouts across either arm. [Replay results](../../../Benchmark/replay/RESULTS.md) · [Timeout diagnosis, Feedback](session-handoff.md#timeout-diagnosis)
- For rw-017 and fb-001, S3 lost runs to the deadline even though the hidden check passed. Continuing after an in-loop accept pass is one possible explanation. The consult did not inspect those run trails. [Step 10 decision notes](progress.md#open-items)
- On 2026-11-27 Sonnet confirmed that the results files and diagnostic logs were backed up to `<home>/Downloads/Projects/tokenfrugal-replay-backup/2026-11-27`. One post-run `smoke.py tracker` run passed in 37 seconds. [Sonnet’s post-run checks](session-handoff.md)
- The post-run `smoke.py security` check failed with `APITimeoutError` after 228 seconds without a model reply on its first step. Another project's script was using the same Ollama instance. The builder model was loaded with a 32768-token context and GPU utilization was 96 percent. Contention is a likely but unproven cause of this smoke failure. [Sonnet’s post-run checks](session-handoff.md)
- The other project's scratch files date from 22:39, overlapping the end of S3. Earlier GPU use by that project or other containers is unknown. The gate protocol required only that ComfyUI be stopped. Contention may have affected replay timings and `out_of_time` counts. The available records cannot establish whether it did. [Sonnet’s post-run checks](session-handoff.md) · [Measurement plan](../subagent-runtime-design.md#measurement-plan-s2)

## Proposed work, in order

### N0. Establish exclusive GPU use

Update `scripts/replay.py` and the protocol in `Benchmark/replay/README.md`. Before each measurement and throughout each arm, record loaded models, GPU users and Ollama request sources. A second client can request the same builder, so the loaded-model list alone cannot establish exclusivity. Accept a measurement only when its run record covers the full interval and shows that only the intended client and model used the GPU. Mark interference or gaps in observation and repeat the measurement. Then rerun `smoke.py security` on an idle GPU and record the result, elapsed time and first reply or error. Preserve the original results and timeout. Which request and GPU records will the owner accept as evidence?

### N1. Report unverified write tasks

Likely files include `router/checker.py`, `router/outcomes.py`, `router/server.py` and checker tests. For a write task that would otherwise report success, return an unverified result when its accept command is absent or trivial. Check missing, trivial, failing and behaviour-checking commands against the expected outcomes, including a verified success. Preserve existing failure precedence and read-only task behaviour. Which commands count as trivial, and how should clients receive the result? Changing outcome values or MCP docstrings falls under Step 11's single tool-surface release rule. Agree on that contract before exposing it.

### N2. Freeze a second corpus

Add a versioned directory under `Benchmark/replay/` and version selection in `scripts/replay.py` and `scripts/replay_report.py`. Give each write task a visible command that exercises the requested behaviour and an independent hidden check. Validate each command against a known incorrect and a known correct implementation. Freeze the corpus before any calibration or scored run. Use a separate idle-GPU calibration sample to choose the pass bar and time limit, then record both before scoring. Label both as set after the first results. Check the frozen revision, calibration record and thresholds in the report. Preserve the first corpus, its bar, its time limit and its results. Which calibration sample, threshold rule and false-success criterion should govern v2?

### N3. Decide when S3 should stop

Inspect the saved rw-017 and fb-001 trails for the order of accept, subsequent calls and deadline expiry. If the trails are incomplete, record that uncertainty. The owner can choose to end the model loop on in-loop `accept: PASS`, or switch S3 off by default. Likely files include the model loop, `router/checker.py`, role configuration and their tests. For early exit, verify that a passing accept ends further model calls and final scope and verification checks still run. For a default-off switch, verify that the default skips S3 and explicit opt-in restores it. Preserve the recorded S3 arm and its verdict. Which behaviour should become the default?

### N4. Decide whether Step 11 can ship independently

An independent release requires an approved change to the design. Likely files include the Step 11 design section and, if authorized, `router/server.py`, receipt tests, client examples and release notes. Check legacy dispatch and resume, packet dispatch and refusal receipts, the 600-character receipt limit and tool-surface compatibility against Step 11. Keep the existing gate verdict visible in release notes. Should release still require a passing gate, or which independent release checks would the owner require? [Step 11](../subagent-runtime-design.md#stage-s4)

### Small follow-ups

- Under `code-l2-accept`, two 60-second `search_files` calls looked for files the task was about to create. Inspect the role skill and its role bench. Compare search counts, durations and task correctness on the same sandbox task under N0. Preserve the host accept check. May the skill wording change if the searches recur? [Step 8d bench](../../../Benchmark/replay/RESULTS.md)
- Finish the Step 3 live Codex check from another project using the owner's `~/.codex/config.toml`. Record whether Codex discovers the installed router and completes a dispatch. Preserve unrelated settings and keep the personal configuration outside the repository. When can the owner provide the configured client? [Step 3 open item](progress.md#open-items)

## Decisions the owner must take before work starts

1. Approve how N0 will detect competing requests and document exclusive GPU use.
2. Define a trivial accept command and approve how and when clients see an unverified result.
3. Choose the v2 calibration sample, the rule for deriving the bar and deadline, and the false-success criterion.
4. Choose early exit on accept pass or an S3 default-off switch after reviewing the available trails.
5. Decide whether Step 11 remains gated and specify its release checks if it can ship independently.
6. Decide whether the search skill may change and arrange the live Codex check.

A later session will run the EGM brainstorm and review and seek owner approval before implementation.
