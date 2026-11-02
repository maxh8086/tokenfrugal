# Critic Report (Stage 7): docs/designs/comfyui-gpu-lease.md, lines 1-179

Reviewers: egm-design, egm-structural, egm-style (run in parallel, deduplicated below). Standard: `feature-spec-standard.md`.

## Blockers

1. **The core design depends on the "optional" live GPU check (lines 95, 107-113, 171).** Acquire step 4 makes the live check a required step. Line 109 says it is optional and not part of piece 1. Alternative 6 justifies fail-open by citing it as the second opinion. Line 107 says the lease file alone solves the root problem. A reader cannot tell what is specified. *(style B1/B2, design M1, structural M2)*
   - Direction: split the required free-VRAM check (step 4) from the optional process-name check. Rename the section at line 100 to "Router check" and give the optional check its own subsection ("Deferred: live GPU check, post-spike"). Replace line 107 with a bounded claim (the lease stops the router loading Ollama models while held; other Ollama clients are not blocked). Reword Alternative 6 so it does not depend on the deferred check. Define "piece 1" or drop the term.
2. **The `ollama` holder and `releasing` state are defined but never specified (lines 76-77, 92, 98, 109).** Neither is used in the core flow. *(style B3, design 2)*
   - Direction: remove both from the core schema, or mark them "reserved, used only if the live check is adopted". Reword line 92 to "if a valid lease is held by `comfyui` or `kalamanch`, refuse with `GpuBusy`".

## Major

3. **Fail-open is unproven (lines 105, 171, 113).** If the file is unreadable or the lease expires while the container still holds VRAM (laptop sleep), the router loads Ollama onto a busy GPU, which is the failure the design exists to prevent. *(design 1, 2)*
   - Direction: state what protects the user in piece 1. Make the `nvidia-smi` visibility test a go/no-go criterion in the spike, and say what fail-open degrades to if it fails (a `/api/ps` or `docker inspect` probe, or a short fail-closed window).
4. **Expiry and takeover are described twice with different outcomes (lines 77, 92, 105).** Define where `docker inspect` runs: `check_for_ollama` is read-only and fails open; acquire takes over only after `docker inspect` (or the pid check for kalamanch). Cover expired lease with live container, expired with dead container, and a `pending` that never completed. *(design 2, style M4)*
5. **Holder and heartbeat failure modes are missing (lines 29, 83, 98).** If the bridge dies during a render, the container keeps rendering while the lease expires after 30 s. `releasing` has no timeout. Sleep and resume make the clocks inconsistent. *(design 3)*
   - Direction: add a failure-mode table (bridge crash mid-render, node crash, sleep/resume, stuck `pending`/`releasing`) with the lease outcome and a mitigation, such as checking the ComfyUI `/queue` before treating an expired lease as free. Tie `ttl_s` to the heartbeat as a multiple, and run the heartbeat on its own thread.
6. **No Risks & Mitigations section (lines 111-114, 122, 148-160).** Risks are spread over four places and several have no mitigation or owner (spill, 8 GB feasibility with no fallback, two processes breaking a stale lock). *(design 4, structural 1)*
   - Direction: add one `## Risks & Mitigations` table (risk, impact, mitigation, owner/test) and a spike go/no-go criterion (fit in 8 GB, `nvidia-smi` visibility, mount load time). Put 8 GB feasibility first.
7. **Security posture has gaps (lines 120, 122, 136-137).** The container has outbound network access. An embedded editor with CORS or a proxy on localhost exposes an unauthenticated ComfyUI to any local web page (DNS rebinding, cross-origin). A same-origin proxy would forward arbitrary ComfyUI API calls. *(design 5)*
   - Direction: evaluate an internal-only Docker network plus a single proxied port, or an egress block. Add Host and Origin validation and state the dashboard's own authentication stance.
8. **Supervision across Node and Python is unspecified (lines 29, 67, 126, 128).** No policy for a Node restart mid-render, a Stop during a render (it kills the job), or Force release while ComfyUI still holds models (breaks the invariant at line 27). *(design 6)*
   - Direction: Force release must also free or stop the container, or warn clearly. Specify bridge restart or adoption of an existing lease, and what Stop does to a running job.
9. **Open decisions are scattered (lines 86, 109, 132, 134-137).** Add an `## Open Questions` section with an owner and a resolution gate for each (debounce, embedding mechanism, live-check policy, spike-tuned timings). *(structural 3, design 9)*
10. **Goals are not testable (lines 13, 27, 29-33).** "A usable tab", "quality before speed" with no metric, "measured against `generate_ltx.py`" with no quantities, "cannot leave GPU busy forever" with no maximum stale time, an undefined retry hint. *(style M1, M2)*
    - Direction: list the tab features with an acceptance condition; name PSNR/SSIM as the metric or defer thresholds to the spike; name the compared quantities (wall time, peak VRAM); state maximum stale lease time (TTL plus check interval); define the retry hint.
11. **Timing values are inconsistent (lines 71, 83, 86, 94).** 10 s stale lock vs "a couple of seconds" wait; "every few seconds" heartbeat vs `ttl_s` 30; 60 s unload wait. Give a number for each. *(style M5, design 7)*
12. **`generation` rejection is not described (lines 84, 98).** Say writers pass their generation on heartbeat and release, and what a rejected writer does. *(style M6)*
13. **Unquantified performance claims (lines 19, 151).** "Slows to a crawl", "several times slower": cite a measurement or write "to be measured in the spike". *(style M3)*
14. **Unload and release races (lines 94, 98, 132).** Another Ollama client can reload a model between "empty" and `held`; the debounce is undecided. Re-check after writing `pending`, define rollback on timeout, and set a default debounce (for example 60-120 s, configurable). *(design 8)*
15. **kalamanch scripts run directly bypass the lease (lines 34, 62-64).** Add to Non-Goals or the weak points, as done for direct Ollama clients (line 41). *(design 10)*
16. **The stress-test paragraph is a dense block (lines 109-114) in second person.** Convert to a short list: purpose, decision pending, open questions. *(style M7)*

## Nits

- Headings: "The Problem" and "Technical Plan (Architecture)" vs the standard's "Problem Statement" and "Proposed Architecture". Rename "Weak points to review" (line 155) or fold it into Risks. Make "Stress-test of the live check" (line 111) and the "Reuse:" paragraph (line 88) proper subheadings.
- Voice: "you", "your", "settled by you" at lines 109, 164, 166, 170, 175, 176. Use "the author" or the passive voice.
- Alternatives labelling: "(fixed)", "(fixed against)", "(fixed: ...)" are cryptic and vary (lines 164, 170, 174-176). Use one tag, for example "[Pre-decided]", with an objective reason. List item 10 has different marker spacing (line 175).
- Missing alternatives: querying ComfyUI or Docker as the source of truth instead of a heartbeat file; OS file lock or small localhost service; SQLite or named mutex; a no-egress container network.
- Define terms once: "lease" before line 13, "kalamanch" and `kalamanch/run.py` at line 11. Goals bullets 31-34 use inconsistent bold lead-ins.
- Wording: line 67 "Node does not rewrite its logic" to "does not reimplement the lease logic"; line 11 "That is too small"; line 22 heading "Unreviewed code risk" to "Unpinned third-party code" and name the mechanism (runtime `pip install`); line 39 first Non-Goal is a fragment; line 136 "mishandles" to "does not forward"; line 168 "UI-side owner" is vague.
- Line 20 and 151: the WDDM spill claim is unbacked; label it an observation to confirm in the spike.
- Line 118-119 acceptance tests are scattered; add one short acceptance list (shutdown path, competing writers, sleep, bridge crash).
- Cross-references at lines 40 and 176 name no subsection; link to anchors. Add a language tag to the diagram fence at line 50.

## Verdict

No findings on the problem statement, goals or architecture shape. The root issue is that the core flow and the optional live check are mixed, so fail-open safety is claimed but not delivered in piece 1. Fix blockers 1 and 2 and major 3-6 first.
