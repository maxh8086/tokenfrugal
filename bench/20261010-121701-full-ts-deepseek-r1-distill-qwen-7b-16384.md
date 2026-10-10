# Benchmark full-ts-deepseek-r1-distill-qwen-7b-16384 20261010-121701

n=2, task timeout 150s

## Roles

Section failed: AssertionError: bench does not cover roles: ['devops', 'finance']

## Real-world tasks (verified by running code or checking files)

| task | verified | ran | p50 s | max s | failure notes |
|---|---|---|---|---|---|
| write_function | 0/2 | 0/2 | 57.8 | 71.2 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call  |
| fix_bug | 0/2 | 0/2 | 35.2 | 35.2 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call  |
| write_tests | 0/2 | 0/2 | 52.1 | 56.8 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call  |
| rename_across_files | 0/2 | 0/2 | 37.3 | 43.0 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call  |
| find_symbol | 0/2 | 0/2 | 24.8 | 34.3 | FAILED (builder/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call  |
| review_sqli | 0/2 | 0/2 | 36.3 | 49.4 | FAILED (reviewer/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call |
| debug_trace | 0/2 | 0/2 | 40.9 | 48.2 | FAILED (debugger/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call |
| summarize_readme | 0/2 | 0/2 | 32.2 | 46.7 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call |
| role_analyzer | 0/2 | 0/2 | 22.8 | 24.4 | FAILED (analyzer/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call |
| role_data | 0/2 | 0/2 | 22.0 | 26.8 | FAILED (data/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call a t |
| role_docs | 0/2 | 0/2 | 35.2 | 36.9 | FAILED (docs/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: answer contains filler/placeholder text; redo w / FAILED (docs/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call a t |
| role_security | 0/2 | 0/2 | 79.0 | 95.6 | FAILED (security/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: answer contains filler/placeholder text; re / FAILED (security/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call |
| role_designer | 0/2 | 0/2 | 35.1 | 41.1 | FAILED (designer/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call |
| role_browser | 0/2 | 0/2 | 35.2 | 35.3 | FAILED (browser/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call  |
| role_tracker | 0/2 | 0/2 | 29.7 | 54.6 | FAILED (tracker/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call  |
| role_research | 0/2 | 0/2 | 31.5 | 45.9 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; call |

## Context ramp (docs role, prompt tokens)

| tokens | success | recall | p50 s | failures |
|---|---|---|---|---|
| 2000 | 0/1 | 0/1 | 29.4 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; c |
| 4000 | 0/1 | 0/1 | 37.9 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; c |
| 8000 | 0/1 | 0/1 | 37.4 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; c |
| 12000 | 0/1 | 0/1 | 35.7 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; c |
| 16000 | 0/1 | 0/1 | 38.7 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): LoopError: you answered without calling any tool; c |
| 24000 | 0/1 | 0/1 | 11.2 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): BadRequestError: Error code: 400 - {'error': {'mess |
| 32000 | 0/1 | 0/1 | 11.2 | FAILED (research/ts-deepseek-r1-distill-qwen-7b-16384): BadRequestError: Error code: 400 - {'error': {'mess |

## Output length (direct)

| model | max_tokens | tok/s | p50 s | fails |
|---|---|---|---|---|
| builder | 128 | 43.8 | 2.9 | 0 |
| builder | 512 | 50.1 | 10.2 | 0 |
| builder | 1024 | 49.9 | 16.7 | 0 |
| builder | 2048 | 50.0 | 8.9 | 0 |
| builder | 4096 | None | - | 1 |
| thinker | 128 | 5.7 | 22.5 | 0 |
| thinker | 512 | 5.8 | 89.0 | 0 |
| thinker | 1024 | 5.8 | 162.4 | 0 |
| thinker | 2048 | 5.8 | 84.7 | 0 |
| thinker | 4096 | 5.8 | 109.6 | 0 |

## Concurrency

| parallel | wall s | per-task p50 | success | per min |
|---|---|---|---|---|
| 1 | 152.4 | 152.4 | 0/1 | 0.4 |
| 2 | 152.3 | 150.9 | 0/2 | 0.8 |
| 4 | 153.3 | 151.3 | 0/4 | 1.6 |
| 8 | 153.4 | 151.7 | 0/8 | 3.1 |

Mixed builder/thinker x4: {'s': [154.0, 150.8, 154.0, 152.7], 'success': '0/4'}

## Resume

```json
[
 {
  "round": 0,
  "s": 2.8,
  "ok": false,
  "msgs": 0
 },
 {
  "round": 1,
  "s": 2.7,
  "ok": false,
  "msgs": 0,
  "attempts": 2
 },
 {
  "round": 2,
  "s": 2.6,
  "ok": false,
  "msgs": 0,
  "attempts": 3
 },
 {
  "round": 3,
  "s": 2.6,
  "ok": false,
  "msgs": 0,
  "attempts": 4
 },
 {
  "round": 4,
  "s": 2.6,
  "ok": false,
  "msgs": 0,
  "attempts": 5
 },
 {
  "round": 5,
  "s": 2.6,
  "ok": false,
  "msgs": 0,
  "attempts": 6
 },
 {
  "round": "final",
  "s": 154.0,
  "ok": false,
  "msgs": 0
 }
]
```

## Plan

```json
{
 "plan_add": {
  "s": 2.0,
  "out": "task 27 added"
 },
 "plan_overview": {
  "s": 1.2,
  "out": "plan 'bench': pending=3\n13 [pending] bench task\n18 [pending] bench task\n27 [pending] bench task"
 },
 "smoke_plan": {
  "rc": 0,
  "tail": [
   "PASS A done with real commit ",
   "PASS checkpoint keeps open tasks ",
   "PASS prune spares done task that an open task depends on ",
   "PASS checkpoint prunes finished tag ",
   "PASS prune leaves no new orphaned events ",
   "smoke_plan: OK"
  ]
 }
}
```

## Resources

```json
{
 "gpu_before": "5395 MiB, 8188 MiB, 100 %",
 "docker_before": "synaptree-synaptree-1 0.00% 7.52GiB / 15.26GiB\nsynaptree-neo4j-1 0.79% 968.1MiB / 15.26GiB\nts-mcp-neo4j-1 0.89% 645.5MiB / 1GiB\nglossary-workbook-changes-78e56f-ui-1 0.21% 28.51MiB / 15.26GiB\nmarket-scanner-collector-1 0.00% 19.67MiB / 15.26GiB",
 "gpu_after": "5395 MiB, 8188 MiB, 0 %",
 "run_s": 157.7,
 "ok": false,
 "docker_samples": [
  "synaptree-synaptree-1 0.00% 7.551GiB / 15.26GiB\nsynaptree-neo4j-1 0.67% 968.3MiB / 15.26GiB\nts-mcp-neo4j-1 0.78% 645.8MiB / 1GiB\nglossary-workbook-changes-78e56f-ui-1 0.19% 28.52MiB / 15.26GiB\nmarket-scanner-collector-1 0.00% 19.67MiB / 15.26GiB",
  "synaptree-synaptree-1 0.00% 7.551GiB / 15.26GiB\nsynaptree-neo4j-1 0.74% 968MiB / 15.26GiB\nts-mcp-neo4j-1 0.70% 645.6MiB / 1GiB\nglossary-workbook-changes-78e56f-ui-1 0.23% 28.52MiB / 15.26GiB\nmarket-scanner-collector-1 0.00% 19.67MiB / 15.26GiB",
  "synaptree-synaptree-1 0.00% 7.551GiB / 15.26GiB\nsynaptree-neo4j-1 0.78% 968.8MiB / 15.26GiB\nts-mcp-neo4j-1 0.73% 645.7MiB / 1GiB\nglossary-workbook-changes-78e56f-ui-1 0.19% 28.52MiB / 15.26GiB\nmarket-scanner-collector-1 0.00% 19.67MiB / 15.26GiB",
  "synaptree-synaptree-1 0.00% 7.551GiB / 15.26GiB\nsynaptree-neo4j-1 0.78% 968.1MiB / 15.26GiB\nts-mcp-neo4j-1 3.23% 646.3MiB / 1GiB\nglossary-workbook-changes-78e56f-ui-1 0.19% 28.51MiB / 15.26GiB\nmarket-scanner-collector-1 0.00% 19.67MiB / 15.26GiB",
  "synaptree-synaptree-1 0.00% 7.551GiB / 15.26GiB\nsynaptree-neo4j-1 0.70% 968.1MiB / 15.26GiB\nts-mcp-neo4j-1 0.80% 645.7MiB / 1GiB\nglossary-workbook-changes-78e56f-ui-1 0.19% 28.51MiB / 15.26GiB\nmarket-scanner-collector-1 0.00% 19.67MiB / 15.26GiB"
 ],
 "ollama_ps": "NAME                                           ID              SIZE      PROCESSOR    CONTEXT    UNTIL               \nts-deepseek-r1-distill-qwen-7b-16384:latest    36c4d36b43b9    5.5 GB    100% GPU     16384      29 minutes from now",
 "leftover_containers": "synaptree-synaptree-1\nsynaptree-neo4j-1\nts-mcp-neo4j-1\nglossary-workbook-changes-78e56f-ui-1\nmarket-scanner-collector-1"
}
```
