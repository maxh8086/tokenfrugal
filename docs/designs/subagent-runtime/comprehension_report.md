# Stage 6: Comprehension Test

*   **Target:** `docs/designs/subagent-runtime-design.md`.
    *   FeatureRange: lines 1-663.
    *   DetailedRange: lines 664-883.
*   **Reviewer:** `egm-comprehension` (naive reader), run in a fresh context with no extra Goldfish context.
*   **Standard:** `re-implementation-standard.md`.
*   **Date:** 2026-11-20.
*   **Verdict:** a reader can't re-implement this from the document alone. 1 Blocker, 17 Major, 8 Nit.
*   **Main gaps:** most of them are reply and row contracts a new engineer would have to invent. The rest are project terms that are defined only in the brief or in the code.
*   **Elephant check:** C-1 confirmed. `prompt_sent` appears only in the data-flow diagram (line 169) and in the step rows. The NULL-fallback table exists only in `concepts_brief.md:348-355`.

## Blocker

### C-1. The NULL-fallback table the design refers to is missing

*   **Where:** line 630, Step 6+7 (774, 784).
*   **Gap:** three references point to an "F2 table" in the Technical Plan, but the design has no such table. The fallback values change behaviour:

    | Column | Fallback when NULL |
    | --- | --- |
    | `task_type` | `""` |
    | `prompt_sent` | `prompt` |
    | `accept_json` | re-parse the `Accept:` line |
    | `workspace` | current `WORKSPACE` |
    | `plan_id` | 0 |
    | `kind` | `analyze` |

*   **Fix:** add a Column / Writer / Reader / NULL-fallback table to the Technical Plan. Include `parent_id`, `baseline_json`, `packet_json`, `workspace_key` and `receipt`, and point all three references at it.

## Major

| Id | Where | Gap | Fix |
| --- | --- | --- | --- |
| C-2 | Whole document | No glossary. These terms are used without a definition: builder/thinker; slug vs role (`coding-l2` vs `code-l2`); "first dispatch"; FB-xxx and class A; Haiku/Sonnet/orchestrator; Goldfish; EGM; templates; preread; nudges; trail; `health` event; `sweep_stale`; `kind_hint`; gateway vs native server; `content_pipeline`/`studio`; skills and agent skills; role contract `stop_condition`; "S2 spike"; "the CLAUDE.md exception"; `plan_*`. | Add a glossary after the Overview with file/function anchors. Define "first dispatch" as in D1. |
| C-3 | 196-232 | No Stop → Status/Outcome table. Readers can't tell whether `satisfied` stores `stop=none`, whether `checker` leaves `done` or `failed`, or whether `scope` is always `failed`. | Add a Stop → (Status, Outcome, default Next) table, and say which legacy check failures stay `done`. |
| C-4 | 228, 684 | `attempts` has no source: no column, and no rule on whether the correction run, resume or follow-up counts. The escalation rule also contradicts itself: resume then fallback, so re-scope is never reached. | Define `attempts` and where it lives. Give the Next mapping per attempt number, or reword the justification. |
| C-5 | 390-407, 852 | Receipt fields have no source mapping: `files`, `steps`, `secs`, `error`, the `note` values, the `"+N"` form, accept on env_missing or timeout, accept for analyze. | Add a field table (source, type, when omitted), plus examples for satisfied, env_missing and analyze. |
| C-6 | 165-167, 399, 852 | `task_id` is "always present", but refusals create no row. There is no Stop for an invalid packet. `"outcome":"running"` isn't in `Outcome`. The `task_status` running shape is undefined. | Define the refusal reply (for example `stop=bad_packet`, `task_id=null`). Add `running`. Give the exact `task_status` JSON. |
| C-7 | 259-274, 739 | Unspecified: how an `Accept:`/`Acceptance:` line is matched, how `parse_accept` resolves `argv[0]` with no workspace argument, the `NAME=value` regex, and which `checks: none` reason wins. | Give the line regex and label stripping. Pass the workspace to the parser or move the prose decision. State the env regex. Order the reasons. |
| C-8 | 739, 774, 781 | The `<item>` names in `checks: FAILED (<item>)` aren't listed (one example has a literal `...`). The full fix-prompt template appears only in the brief's F1. | List the item names and their order, the line grammar, and the full fix-prompt template. |
| C-9 | 387, 797 | `render(packet)` has no format, and no rule for turning argv into an `Accept:` line. The `base` arm re-parses it with shlex, so quoting decides whether it runs the right command. | Give the exact template and the argv quoting rule. Add a round-trip test. |
| C-10 | 295-315, 176-182, 760 | Packet mode is unclear: is the first segment capped at `role_timeout`, and is "continued loop" the same `_run`? S3 allows more accept runs than the formula reserves. Nothing says what happens when the deadline runs out before accept or the pre-check. | State the cap for each segment, and the rule for an exhausted deadline. |
| C-11 | 832-834, 625 | The in-loop accept trigger contradicts itself, and as read it becomes per-write accept, which Alternative M rejects. "Forced answer" is undefined, "Otherwise" is ambiguous, and packet behaviour with host accept off is unstated. | Define the trigger as a state machine. Define "forced answer". Spell out packet behaviour for host accept on and off. |
| C-12 | 341-355, 794, 834 | Packet resume is undefined: how it detects a packet task, what it rebuilds from `packet_json`, where `create_claimed(resume_of=...)` is called, and what happens to a stale row. | Add a "Resume of a packet task" paragraph. |
| C-13 | 189, 620, 686, 699-704, 418 | These events have no schema: `accept_run`, `health` (`missing`, unknown-key warning), `frames` on `task_failed`, `error_kind` on usage. | Add an Events table: name, when emitted, fields, stage. |
| C-14 | 409-418, 737 | `TOKENFRUGAL_HOST_ACCEPT`: only `=1` is defined. Does `0` force it off? Which strings count as true? What about wrongly typed TOML values? This is the security opt-in. | State the true/false values, the force-off rule, and the behaviour for wrong types. |
| C-15 | 445-488, 803 | `--router` launch isn't specified (interpreter, entry point for pre-S1a checkouts, transport). The pass rule needs a scope check, but the JSONL has no scope field and `base` has no `must_not_change`. `peak_ctx` is missing in `base`. | Specify the launch per arm. The runner computes `scope_ok` from a git diff. `peak_ctx` is null where unavailable. |
| C-16 | 250-257, 290-293 | Unspecified: which traceback frame `first_error` uses, when `EnvKind.missing` is produced, and what happens with no venv and no system python. | State the frame rule (nearest frame under the workspace), when `missing` is set, and `stop=env_missing`. |
| C-17 | 332, 335 | "The same extraction preread uses" names no function or limit (2, or 3 for packets). | Name `loop.named_paths(task, limit)` and the limit change detection uses. |
| C-18 | 28-30, 64, 675 | "The fallback log" has no path. There are two candidates: `docs/haiku-fallback-log.md` and `docs/designs/fallback-execution-log.md`. | Name the file and the entry pattern the weekly metric counts. |

## Nits

| Id | Where | Gap | Fix |
| --- | --- | --- | --- |
| C-19 | 344-350 | `HEARTBEAT_EVERY` and the heartbeat units aren't stated. | `store.HEARTBEAT_EVERY` = 30 s; epoch seconds. |
| C-20 | 371-376 | The path pattern forbids backslashes (Windows callers must send `/`) and rejects names like `a..b.py`. `lines` has no start ≤ end rule. The meaning of `new: true` is undefined. | One sentence each. |
| C-21 | 832 | "Canonical args" and "hash of the last exception line" are undefined. | For example `json.dumps(args, sort_keys=True)`; name the hashed string. |
| C-22 | 836 vs 871 | The tool cap is used before it's defined. | State "6 tools per role" at first use. |
| C-23 | 461 vs 803 | The runner signature in the Technical Plan omits `--venv`. | Align the two. |
| C-24 | 774 | The stored-messages view has no format. The brief's `show=messages` option was silently dropped. | Describe the format and note the change. |
| C-25 | 300 | `TOKENFRUGAL_TASK_DEADLINE` below `role_timeout`, or not a number, is unhandled. | Add a clamp or validation rule. |
| C-26 | 686 | The resolver for "the resolved Ollama tag" isn't named. | Name the function, and how `TOKENFRUGAL_MODEL_*` overrides apply. |
