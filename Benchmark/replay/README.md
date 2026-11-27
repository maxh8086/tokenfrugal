# Replay corpus

This folder contains the replay corpus for the [S2 measurement plan](../../docs/designs/subagent-runtime-design.md#measurement-plan-s2). In Step 8h, the FB tasks fb-001..fb-009 are rebuilt from `docs/designs/fallback-execution-log.md`.

## Selection rules

1. Each rw task comes from a Claude Code transcript of a session that worked on this repository (tokenfrugal). Transcripts of other projects are not used.
2. The request was made before 2026-11-19.
3. Candidates are taken in ascending date order (oldest first) by the timestamp of the request. The first eligible ones become rw-010, rw-011 and so on.
4. One task is one user request or delegated spec that asked for a change to files in the repository. Questions, reviews and analysis with no file change are not tasks.
5. The change touches at most 3 files.
6. The base commit is the last commit on main before the request. It must be reachable in the repository.
7. `check.py` is written from the request and the repository at the base commit, without the model's output (neither the diff nor the reply from that session). It asserts observable behaviour, never the text of a diff, and exits 0 when the task is done.
8. `check.py` runs with the repository's venv on Windows, macOS and Linux, with no network, Docker, GPU or secret.
9. A candidate that changes the same behaviour in the same file as FB-001..FB-009 is skipped.
10. No transcript text, secret or personal data is copied into the corpus. The goal is restated in the corpus author's own words.
11. Exactly one of rw-010..rw-020 has an accept command that passes before any change. It is the first eligible candidate in date order with that property, and its `check.py` follows rule 7.
12. Every skipped candidate is recorded in this README with the number of the rule that excluded it. A substitute for an FB task is the next eligible candidate in date order and takes the next free rw id (rw-021 onwards).
13. These rules are fixed by the Step 0 commit, before any S2 result exists. Step 8h only adds the corpus table, the skip records and the substitutions; it does not change a rule.

## Corpus tasks

| ID | Repo | Base SHA | Agent | Task type | Goal | Files | What `check.py` asserts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fb-001 | tokenfrugal | b6a9a898b60a | coding-l2 | code | Parse story markdown into sentences and add a unit test. | `scripts/story_film.py`, `tests/test_story_film.py` | The parser drops the stage direction and returns exactly the two spoken sentences in order. |
| fb-002 | tokenfrugal | b6a9a898b60a | coding-l2 | code | Narrate text with Kokoro and save the WAV. | `scripts/story_film.py` | With the container mocked, narrate sends the expected arguments and JSON, saves stdout as WAV, and raises with the last stderr line on failure without writing a file. |
| fb-009 | tokenfrugal | b6a9a898b60a | coding-l2 | code | Fetch popular YouTube videos and save JSON Lines. | `scripts/youtube_trends/__init__.py`, `scripts/youtube_trends/discover.py`, `tests/test_youtube_discover.py` | URL limits, item defaults, mocked fetch errors, UTF-8 JSON Lines and CLI key handling match the fixtures. |
| rw-010 | tokenfrugal | 518f0a40f305 | coding-l2 | code | Open one profile session per name and add a unit test. | `gateway/mcp_client.py`, `tests/test_open_role_profiles.py` | List, string and absent profiles open the expected sessions, native servers coexist, and the profile tests pass. |
| rw-011 | tokenfrugal | 4b1fd67973e0 | coding-l2 | code | Allow raw control characters in text tool calls. | `gateway/loop.py` | One allowed call is recovered with its title and literal newline intact. |
| rw-012 | tokenfrugal | f335f782b2d0 | coding-l2 | code | Run the existing benchmark for one Ollama tag. | `scripts/bench_model.py` | Help succeeds, one child gets the expected arguments and environment, its exit code propagates, and an existing tag skips creation. |
| rw-013 | tokenfrugal | f335f782b2d0 | coding-l2 | code | Record the Ollama environment and task timeout in benchmark reports. | `scripts/bench.py`, `tests/test_bench_env.py` | The helper returns the five specified Ollama keys and timeout, with the expected defaults and environment values. |
| rw-014 | tokenfrugal | f335f782b2d0 | coding-l2 | code | Score keyword persona routing against labelled examples offline. | `scripts/persona_routing_eval.py` | Fixture slugs, routes, label validation, scores, JSON Lines loading and CLI exit codes match expectations. |
| rw-015 | tokenfrugal | f335f782b2d0 | coding-l2 | code | Validate persona slugs in gateway configuration. | `gateway/config.py` | Known slugs return an empty string and unknown slugs return the expected error, including with incomplete configuration. |
| rw-016 | tokenfrugal | f335f782b2d0 | coding-l2 | code | Append a dated CSV result to the model comparison table. | `scripts/bench_append.py`, `Benchmark/model-comparison.md` | Dry run previews escaped notes, append inserts exactly one row at the first table’s end, and a duplicate fails without editing. |
| rw-017 | tokenfrugal | f335f782b2d0 | coding-l2 | code | Load optional environment defaults when importing gateway configuration. | `gateway/config.py` | Valid JSON supplies missing values, preset values survive, and missing or malformed JSON leaves defaults unset. |
| rw-018 | tokenfrugal | d42866186bfb | coding-l2 | code | Collect Ollama model and memory statistics for benchmark rows. | `Benchmark/script/modelinfo.py`, `Benchmark/script/run_benchmark.py`, `tests/test_modelinfo.py` | Mocked responses yield the expected fields and fallback values, and CSV metadata places those fields in order. |
| rw-019 | tokenfrugal | 435818f7d828 | coding-l2 | code | Tighten README summary verification and route the case to the docs agent. | `scripts/bench_real.py` | The docs case uses the README checker, which accepts grounded local MCP summaries and rejects access failures and unsupported claims. |
| rw-020 | tokenfrugal | 435818f7d828 | coding-l2 | code | Correct the README case description and persona in both reports. | `scripts/bench_csv.py`, `scripts/bench_consolidate.py` | The CSV layout has the specified summary row, and both persona maps assign it to engineering-technical-writer and match the full fixture. |
| rw-021 | tokenfrugal | 435818f7d828 | coding-l2 | code | Detect Synaptree outages before a run and guard CSV import during it. | `Benchmark/script/run_benchmark.py` | Failed preflight stops the run, a stopped or restarted container preserves raw results and skips import with a warning, and a stable run imports. |
| rw-022 | tokenfrugal | ab41db0120ce | coding-l2 | code | Strip task IDs, tighten three case checks and exclude infrastructure failures from aggregates. | `scripts/bench_real.py` | Only valid prefixes are stripped, and the security, debugging and generated-test fixtures receive the expected verdicts. |
| rw-023 | tokenfrugal | ab41db0120ce | coding-l2 | code | Use task trails to classify connection errors and verify required tools. | `scripts/bench_real.py`, `tests/test_bench_status.py` | Trail lookup handles missing data, connection errors mark runs as infrastructure failures, and tool evidence controls verification. |
| rw-024 | tokenfrugal | ab41db0120ce | coding-l2 | code | Isolate repeats, verify the Synaptree UI, tighten summaries and bound dispatches. | `scripts/bench_real.py`, `scripts/bench.py`, `tests/test_bench_status.py` | The browser case requires navigation and both reply keywords, summary limits hold, data fixtures reset, and each repeat starts with empty scratch. |
| rw-025 | tokenfrugal | 16203d9e988d | coding-l2 | code | Update the fake API key in the security fixture and checker. | `scripts/bench_real.py` | The fixture uses the new key and original password, and only the tested reply containing both passes. |
| rw-026 | tokenfrugal | cc771571dc20 | coding-l2 | code | Add an opt-in five-case thinker suite and preserve the default suite. | `scripts/bench_real.py`, `scripts/bench.py`, `tests/test_bench_hard.py` | Hard mode selects five cases with fixtures and checks that reject empty replies, while default and unknown modes retain the original case order. |

## Selection and substitutions

N = 20. The selection was decided on 2026-11-27, before any S2 result existed. The first eligible requests in ascending date order became rw-010 through rw-026, counting subagent edits toward each request’s file total. The last selected request was dated 2026-10-18T12:11Z. Later entries need no skip record.

The files for fb-001, fb-002 and fb-009 did not exist at their original base. All three were rebuilt at `b6a9a89` using the delegated request texts for their packets and checks. For FB-003 through FB-008, no commit holds the code they changed as it stood before their work. FB-007 and FB-008 also required Docker.

| Original task | Substitute |
| --- | --- |
| FB-003 | rw-021 |
| FB-004 | rw-022 |
| FB-005 | rw-023 |
| FB-006 | rw-024 |
| FB-007 | rw-025 |
| FB-008 | rw-026 |

Only rw-010 has an accept command that passes before any change. All 97 of its 97 tests passed in a worktree of its base. Most rw tasks have no accept command, so their false-success detection rests on `check.py`. The FB half no longer covers failure classes A, B and D. The transcripts omit edits made through local-model dispatches. Eight subagent edits were attributed by time alone.

Every task’s `check.py` failed on its untouched base and passed on a reference implementation written from its packet. Independent validation found that rw-012, rw-014 and rw-021 each checked something beyond the request. Those three checks were loosened.

## Skip records

Numbers are indices into the candidate list mined from session transcripts. The list is local and uncommitted. For indices the original review did not name, classification used file lists alone. UI-only changes were assigned R8, handoff-only changes R4, and documentation-only changes R7. Dates below are in October 2026, with times in UTC.

How R6, R7 and R8 were applied (a reading of the frozen rules, not a change to them): R6 where the base commit lacks code or inputs the request depends on; R7 where no check of observable behaviour could be written from the request and the base alone, documentation and data-only changes included; R8 where such a check could not run offline with the venv, UI-only changes included. Indices classed from file lists alone are judgement calls that were not examined one by one.

### R4

- Approvals and picks — 7–9, 23, 32, 37, 45, 47, 73, 149, 213–216, 253, 260–261, 267 (twin of 266).
- Questions and reviews — 16–20, 41, 66, 129, 134–135, 145–146.
- Git and run operations — 42, 49, 55, 255, 258–259.
- Handoff and plan notes — 25, 54, 68–69, 72, 75–82, 120, 247–248, 254, 256–257, 268–275.
- Files outside the repository — 12–15, 52, 103, 144, 250.
- Re-dispatches of a chosen spec — 70–71, 84, 87, 102, 137, 140, 148.
- Duplicate sessions — every second copy within 155–299 of a session already counted.
- User requests — Oct 10 18:52, Oct 11 10:50, Oct 15 16:40, Oct 16 05:13, 06:17, 07:11, 07:25 and 14:05, and Oct 18 12:09. Also skipped were the Oct 12 06:50 spec and second-session duplicate specs on Oct 16 17:55 and Oct 18 12:11.

### R5

118, 133, 142, 143, 249. Each exceeded three files when subagent edits were counted.

### R6

93–95, 113–117, 119, 121–128, 130–131, 141, 251. The Oct 11 13:10 and 13:12 specs used gitignored `bench/` outputs. The Oct 12 06:51 spec needed `check_persona`, absent at `f335f78`. The Oct 14 14:51 user request matches 113. The Oct 14 19:21 spec’s acceptance test was absent at `0f356f9`. The Oct 15 04:10 spec needed `profile_sync`, and the Oct 15 05:20 user request needed compose. Both were absent at their respective bases.

### R7

2, 5–6, 21–22, 28, 30, 34–36, 38–40, 43–44, 46, 85, 96–98, 100, 112, 150–158, 209, 252, 278–299. The Oct 16 15:14 user request and 15:17 spec changed documentation. The Oct 16 17:54 user request and 17:55 spec added data rows to a new CSV.

### R8

0–1, 3–4, 10–11, 24, 26–27, 29, 33, 51, 53, 56–65, 74, 89–92, 99, 105–111, 159–208, 210–212, 217–246, 262–265, 276–277. Timestamped entries were the Oct 12 09:10 and 12:32 user requests, the Oct 14 16:36 request and 16:37 spec, and the Oct 14 19:17 request and 19:18 spec.

### R9

None.
