# Stage 7: Critic Review

*   **Target:** `docs/designs/subagent-runtime-design.md`, FeatureRange lines 1-663.
*   **Reviewers:** `egm-design` and `egm-structural` (standard: `feature-spec-standard.md`), plus `egm-style` (persona audit vectors). Each ran in a fresh context with no extra Goldfish context.
*   **Date:** 2026-11-20.
*   **Raw counts:**

    | Reviewer | Blocker | Major | Nit |
    | --- | --- | --- | --- |
    | Design | 2 | 15 | 7 |
    | Structural | 0 | 4 | 7 |
    | Style | 0 | 6 | 10 |

*   **After deduplication:** 2 Blocker, 19 Major, 21 Nit. The traceability matrix is at the end.
*   **Verdict:** fails the feature-spec standard until CR-1, CR-2, the Risks section (CR-12) and the top-level alternatives (CR-13) are addressed.

## Blockers

### CR-1. The host-accept opt-in can be granted by the repo or by the model (D-1)

*   **Where:** lines 409-418, 420-443.
*   **Problem:**
    *   **The repo can opt itself in.** `<workspace>/.tokenfrugal.toml` lives inside the untrusted workspace. A cloned repo can commit `host_accept = true`, plus `accept_env_passthrough = ["AWS_SECRET_ACCESS_KEY", ...]`.
    *   **The model can opt itself in.** It can write `.tokenfrugal.toml`: the file isn't on the denylist, and the denylist only applies once host accept is already on. A prompt-injected model can switch host accept on for the next task.
    *   **The env override is too broad.** `TOKENFRUGAL_HOST_ACCEPT=1` is process-wide, so one shell-profile line opts every repo in.
*   **Why it matters:** the design calls the opt-in "the control that matters", and both the repo content and the model can bypass it.
*   **Suggested change:**
    *   Keep trust in a store the user owns, for example `~/.config/tokenfrugal/trusted.toml`, keyed by realpath and set with `doctor.py --trust <path>`.
    *   An in-repo file may only narrow settings, never widen them.
    *   Put `.tokenfrugal.toml` on a write denylist that applies whatever the host-accept state.
    *   Make the env override a list of paths, and have `doctor.py` warn when it is set.

### CR-2. `ModuleNotFoundError` is classified as `env_missing`, which breaks "new module plus test" tasks (D-2)

*   **Where:** line 293, CUJ 2 (96-103), data flow line 174.
*   **Problem:**
    *   **New-module tasks fail as environment errors.** A test that imports a module the task is about to create, or a misspelled import, gives `stop=env_missing`. The run then stops at once with `next: fix_env` and no correction run.
    *   **The failing pre-check is unspecified.** The design only covers a pre-check that passes. If a failing one takes the env_missing path, every new-module task fails before the model even runs.
*   **Why it matters:** this is one of the three task shapes in the Problem section. It would sink the 16/20 gate.
*   **Suggested change:**
    *   A failing pre-check always continues to the model run.
    *   Use `env_missing` only when the missing top-level module is neither a packet file nor a path inside the workspace; otherwise it is `accept_failed`.
    *   Add a CUJ and a corpus task for "new module plus test".

## Major

### Security and correctness

| Id | Where | Problem | Suggested change | Source |
| --- | --- | --- | --- | --- |
| CR-3 | 274, CUJ 4 | A line without backticks runs whenever `argv[0]` resolves, so prose executes on the host: `Accept: make sure the loader works` runs `make`. `find`, `git`, `npm` and `test` resolve on most systems. | Require backticks for legacy lines (report `prose` otherwise), or allow only an interpreter allowlist plus a word stoplist. | D-3 |
| CR-4 | 426-429 vs 178 | The denylist's scope contradicts itself: "packet only" in the data flow, "whenever host accept is on" in Security. `execute_code` tools aren't covered. The list misses `pytest.ini`, `tox.ini`, `setup.cfg`, `noxfile.py`, `.envrc`, `.tokenfrugal.toml` and `.github/workflows/`. | One rule: every builder task with host accept on. List the tool names covered, and extend the file list. | D-4 |
| CR-5 | 321-322, 559-563, 624 | A fresh temporary index has no stat cache, so `git add -A` hashes every file and writes loose objects on every dispatch. The rejection of Alternative I and the "well under a second" claim aren't measured. | Seed the temporary index from `.git/index`. Measure this repo and one large repo. State the cost of object growth. | D-5, W-5 |
| CR-6 | 322-329, Goal 58 | In hash mode (above 200 MB, or no git) only task files are hashed, so a `must_not_change` violation goes unseen and the task can report `done`. | Also hash files matched by the `must_not_change` globs (capped). Otherwise add the note `scope unchecked` and never report `satisfied`. | D-6 |
| CR-7 | 341-355, 34 | The claim can't see human or legacy edits, so concurrent edits get credited to the task. A claim goes stale after 60 s, but `sweep_stale` waits 120 s. Routers with a different `DB_PATH` don't share claims. | State the claim's scope (routers sharing one `GATEWAY_DB`). Use `STALE_AFTER`. Hash packet files at baseline and before accept. Add a Risks row. | D-7 |
| CR-8 | CUJ 3, 174, 336-338 | The pre-check gives `satisfied` whenever a weak accept already passes, which is a new false-success path. | Skip the pre-check for `new: true` or missing files. Make it opt-in, or give `satisfied` the `next: verify`. Add a corpus task where accept passes before any change. | D-8 |
| CR-9 | 654, 19-20, 77 | `task_status`, `wait=False` and fresh resume exist only in a release-note row, and `poll` isn't in `Next`. There are no rules for background task lifetime, for delivering results to a later session, or for the fresh-resume note. The S4 surface can't be revised after it ships. | Add an "S4 surface" section: signatures, docstrings, `Next.poll`, lifetime rules, resume prompt contract. Or defer these, per Stage 5 Z-3/Z-4. | D-9 |
| CR-10 | 295-315, 625, 59 | The deadline reserves 2 accept runs, but S3 allows more. `min(ACCEPT_TIMEOUT, left)` can bring back seconds-long accepts. Client-timeout advice covers builder roles only: db roles reach 1,050 s and media roles 1,500 s. The Claude Code timeout isn't named. | Cap accept runs, or reserve time for all of them. Set a minimum accept slot of 15 s, below which the stop is `out_of_time`. Compute the advice over every role. Name the Claude Code setting. | D-10, W-14 |
| CR-11 | 57, 82, 445-488 | The gate trains and tests on the same data: FB tasks were the design targets. Tasks 10-20 are hand-picked after S1. Arm selection uses the gate tasks. Statistical power is low: 13→16 passes with zero regressions gives p = 0.125, which fails. | Freeze the selection rules and pick tasks before S1 merges. Keep a held-out split. State the minimum detectable effect. Justify 3 runs at temperature 0. Express the q4 rule in tasks. | D-11 |
| CR-12 | Missing section | There is no Risks & Mitigations section, and the standard requires one. Missing rows: gate miss at S2; small corpus; S1b turning verification off by default; misclassification; git object growth; concurrent attribution; replay pollution; a shared DB used by old checkouts; the partial-hash limits; claim serialisation. | Add a Risks & Mitigations table (risk, category, likelihood/impact, mitigation, stage), linking to the Security model. | S-1, D-15 |
| CR-13 | 490-615 | All 16 alternatives are component-level. There is no top-level alternative: the status quo with cloud re-verification; an existing harness (Aider, OpenHands, Codex local-model mode); dropping the builder for edits. | Add 2-3 top-level alternatives with reasons covering cost, maintenance and fit. | D-16 |

### Operations and measurement

| Id | Where | Problem | Suggested change | Source |
| --- | --- | --- | --- | --- |
| CR-14 | 459-468 | **No venv:** a new worktree has none, so accept falls back to system Python (the FB-006 class). **Pollution:** `--router` writes to that checkout's `tasks.db`, polluting production metrics. **No budget:** 420 runs, up to 57 GPU-hours, with GPU-lease contention. | Provision a venv per repo. Give each run its own `GATEWAY_DB`/events and no UI or studio. Add an idle-GPU check. State the compute budget. | D-12, Z-16 |
| CR-15 | 62, CUJ 5, 602-609, 645 | `pip install -e .` doesn't put `tokenfrugal-router` on the client's PATH. A project-scoped `.codex/config.toml` doesn't help other projects. Codex's MCP cwd behaviour is unverified. | Use `pipx`/`uv tool install`, or have `doctor.py` print a full user-level block with an absolute path. Verify Codex's cwd. | D-13 |
| CR-16 | 11-13, 55-64 | No goal measures cloud tokens, the stated aim. The fallback goal has no threshold or normalisation. Packet authoring cost isn't estimated. | Add cloud tokens per delegated edit, with a target and source. Normalise fallback entries per 100 dispatches and set a threshold. | D-14, W-4 |
| CR-17 | 156, 169, 346, 630 | There is no data-model table: types, NULL meaning, indexes. The claim needs an index on `(workspace_key, status)`. | Add a data-model table. This is the same fix as Stage 6 C-1 and Stage 5 Z-6. | D-17 |

### Document structure and clarity

| Id | Where | Problem | Suggested change | Source |
| --- | --- | --- | --- | --- |
| CR-18 | 629 vs 651-654 | Compatibility lists `resume_task` and `ask_followup` as "Unchanged", but the release notes change both. | Split into "Signature unchanged until S4" and "Behaviour changes" (linked). | W-3, S-4, D-19 |
| CR-19 | Whole document | D1-D10, F0-F7, FB-nnn, class A, Goldfish, arm, preread and spike are undefined. "F2 table" points to a list in another document. The brief path is a code span, not a link. | Add a Terms and Decision index after the Overview, with a D9 entry-criteria table. Link the brief. | W-2, S-3, S-7, D-17 |
| CR-20 | 13, 15, 94, 496, 499 | One actor has five names: cloud agent, orchestrator, caller, main agent, Sonnet. "builder" means both a model and a role. `coding-l2` vs `code-l2` is never explained. | Define "caller" once and use it everywhere. Say "builder model" for the model. Note that `coding-l2` is an alias of the role `code-l2`. | W-1, S-7 |
| CR-21 | 617-660 | Release notes and Future Improvements sit as H3s under NFR, while the NFR subsections are bold labels. | Make the NFR labels H3s. Put release notes under Rollout or in their own H2. Promote Future Improvements to an H2. | S-2 |

## Nits

| Id | Where | Finding | Source |
| --- | --- | --- | --- |
| CR-22 | 17, 41 | "Most of the logged failures" and "mostly in the harness" are never quantified. | W-6 |
| CR-23 | 229-232 | The legacy mapping doesn't match the code literals (`out-of-steps`, `malformed-tool-call`, `connection`, `checker`, ...). Give the full table. | D-18 |
| CR-24 | 579 | The "570 s worst case" in Alternative K is about 460 s by `server.py:185-186`. Correct it; the rejection still holds. | D-20 |
| CR-25 | 407 | `len//4` undercounts JSON. Use a character cap with margin, or a real tokenizer in the test. | D-21, Z-17 |
| CR-26 | 152 vs 180-182 | `loop_policy` is called "pure, no I/O", but runs accept. Say accept runs via `asyncio.to_thread`, who sets `cancel`, and add a `cancelled` stop. | D-22 |
| CR-27 | 92 | "Without `run_tests`" isn't specified in the Technical Plan. Give the packet-mode tool list for host accept on and off. | D-23 |
| CR-28 | 374, 332, 653 | `(?!.*\.\.)` rejects `a..b.py`; reject `..` only as a whole segment. The legacy `named_paths` limit makes unnamed legacy edits show as `outside_scope`. | D-24 |
| CR-29 | 24, 55/66, 141 | Section names differ from the standard: Problem Statement, Proposed Architecture, Goals & Non-Goals. | S-5 |
| CR-30 | 79-83 | Open Questions come before the sections that define their terms. Move them, or add forward links. | S-6 |
| CR-31 | 145-157 | The "five existing modules" count is wrong (six). Scripts and config files are missing from the table. | S-8, W-11 |
| CR-32 | 196-266, 161-194 | Formatting: make Stop a Markdown table, fence code as `python`, use an ASCII-only diagram, and give H3 titles one pattern. | S-9 |
| CR-33 | 268, 459, 597 | Add blank lines before lists and fences. Alternative N's shape doesn't match A-P. | S-10 |
| CR-34 | 649 vs 271 | The release notes list 4 of the 7 refused operators. | S-11 |
| CR-35 | 35, 39, 44 | Colloquial headings ("barely use it", "breaks easily"). | W-7 |
| CR-36 | 18, 31, 53 | "Honest" and "trustworthy" applied to a status value. State the mechanism instead. | W-8 |
| CR-37 | 28-30 | A failure heading gives a pass rate. "14 attempts" is ambiguous. "A 4B model should handle" is unsupported. | W-9 |
| CR-38 | 62 | "No extra steps beyond" two steps. | W-10 |
| CR-39 | 443, 534, 600 | Second person, and value judgments ("the control that matters", "the right long-term form"). | W-12 |
| CR-40 | 542, 557 | Absolute claims ("always lags", "never blocks"); `BEGIN IMMEDIATE` can wait on the busy timeout. | W-13 |
| CR-41 | 639 | "The columns stay, since DROP COLUMN is not needed" reverses cause and effect. | W-15 |
| CR-42 | 18, 31, 58, 103, 228, 82/452 | Inconsistent formatting: "done", `done` and plain done; re-scope vs `rescope`; FB-001 vs fb-001. | W-16 |

## Traceability matrix

| Raw finding | Consolidated |
| --- | --- |
| D-1 | CR-1 |
| D-2 | CR-2 |
| D-3 | CR-3 |
| D-4 | CR-4 |
| D-5, W-5 | CR-5 |
| D-6 | CR-6 |
| D-7 | CR-7 |
| D-8 | CR-8 |
| D-9 | CR-9 |
| D-10, W-14 | CR-10 |
| D-11 | CR-11 |
| D-12 | CR-14 |
| D-13 | CR-15 |
| D-14, W-4 | CR-16 |
| D-15, S-1 | CR-12 |
| D-16 | CR-13 |
| D-17 | CR-17, CR-19 |
| D-18 | CR-23 |
| D-19, W-3, S-4 | CR-18 |
| D-20 | CR-24 |
| D-21 | CR-25 |
| D-22 | CR-26 |
| D-23 | CR-27 |
| D-24 | CR-28 |
| S-2 | CR-21 |
| S-3, S-7, W-2 | CR-19 |
| S-5 | CR-29 |
| S-6 | CR-30 |
| S-8, W-11 | CR-31 |
| S-9 | CR-32 |
| S-10 | CR-33 |
| S-11 | CR-34 |
| W-1 | CR-20 |
| W-6 | CR-22 |
| W-7 | CR-35 |
| W-8 | CR-36 |
| W-9 | CR-37 |
| W-10 | CR-38 |
| W-12 | CR-39 |
| W-13 | CR-40 |
| W-15 | CR-41 |
| W-16 | CR-42 |

## Cross-stage overlap

*   **Data-model table:** Stage 5 Z-6, Stage 6 C-1 and CR-17 ask for the same table. One table answers all three.
*   **Undefined terms:** Stage 6 C-2 and CR-19 ask for the same terms index.
*   **The S4 surface:** CR-9 and Stage 6 C-6 depend on Stage 5 Z-3 and Z-4. Deferring `wait=False`, `task_status` and fresh resume removes most of CR-9.
