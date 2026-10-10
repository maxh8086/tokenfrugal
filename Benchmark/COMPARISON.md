# Local models vs Haiku (cloud fallback)

Same 16 real-world cases as `iter4` (`scripts/bench_real.py`), same pass/fail checks (`scripts/haiku_cmp.py`).
Local = TokenFrugal gateway, n=3 per case (`bench/20261009-192407-iter4.json`). Haiku = one run per case as a
subagent with plain file tools. Haiku was run once, so treat its column as "can do it", not a rate.

| Case | Model | Local pass | Local p50 | Haiku | Haiku wall | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| write_function | builder | 3/3 | 13.0s | pass | 12s | local equal, 0 cloud tokens |
| fix_bug | builder | 3/3 | 10.1s | pass | 7s | local equal |
| write_tests | builder | **1/3** | 9.7s | pass | 9s | **local fails 2 of 3** |
| rename_across_files | builder | **0/3** | 15.5s | pass | 9s | **local fails** |
| find_symbol | builder | 3/3 | 7.4s | pass | 6s | local equal |
| review_sqli | thinker | 3/3 | 10.9s | pass | 7s | local equal |
| debug_trace | thinker | 3/3 | 10.9s | pass | 6s | local equal |
| summarize_readme | thinker | **0/3** | 16.2s | pass | 7s | **local fails** (hallucinates) |
| role_data | data | 3/3 | 5.2s | pass | 6s | local equal |
| role_docs | docs | 3/3 | 7.0s | pass | 7s | local equal |
| role_security | security | 3/3 | 43.9s | pass | 7s | local equal, slower |
| role_browser | browser | **1/3** | 8.1s | pass | 10s | **local fails 2 of 3** |
| role_analyzer, designer, tracker, research | tool-backed | 3/3 each | 4-22s | not run | | Haiku has no equivalent tool (plan store, Penpot, crawl) here |

## Where local does as well as Haiku (8 cases, zero cloud tokens)
Single-file write and fix, symbol lookup through synaptree, review and debug of small files, and the
tool-backed roles (data, docs, security). Haiku also passed all of them, so local wins only on cost:
each Haiku run used roughly 60k tokens (mostly harness context); local used none.

## Where local fails (4 cases)
| Task | Local | Why |
| --- | --- | --- |
| rename_across_files | 0/3 | 3B model renames the definition and import but leaves the `old_name(1)` call. A prompt nudge did not fix it. |
| summarize_readme | 0/3 | Invents project details instead of reading the README summary faithfully. |
| write_tests | 1/3 | Tests often fail or are fewer than 3. |
| role_browser | 1/3 | Tool-call arguments for the browser MCP are often wrong. |

Use Haiku for these four kinds of work. Everything else is safe to keep local.

## Where local beats Haiku
Not on quality: Haiku passed every case it was given. Local is better only on cloud-token cost and, for
tool-backed roles, availability of tools Haiku does not have. Haiku was faster in wall time on most cases
(especially role_security, 7s vs 44s).

## Caveats
- Haiku n=1, run in parallel on a shared scratch folder; file cases were re-verified on disk afterwards.
- Answer-text cases (find_symbol, review_sqli, etc.) are checked by keyword only, for both local and Haiku, so a pass means the right term appeared, not that the whole answer is correct.
- Haiku used its own file tools, not the gateway roles.
