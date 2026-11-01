# Goldfish Annotated Review Report

**Target:** `docs/designs/comfyui-gpu-lease.md` (`1-179`)
**Source:** `critic_report.md` (Stage 7). Item numbers match that report.
**Status:** resolved

Resolution: 14 PROPOSE FIX entries accepted and applied (items 1, 2, 4, 5, 6, 9-16, nits batch). Contested 0. Escalated 4 (E1-E4), all answered by the owner and applied. Declined 0. Remaining 0. Applied edits are in `docs/designs/comfyui-gpu-lease.md`; line ranges changed, so FeatureRange is now 1-238 and DetailedRange 239-end.

Summary: 4 ESCALATE (need the owner's decision), 13 PROPOSE FIX, 0 CONTEST, nits batched as one PROPOSE FIX. I do not contest anything: each Blocker and Major is a real gap in the text.

## ESCALATE (owner decides; no edit until answered)

### [E1] Critic item 3 - `egm-design` - Severity: High
*   **Affected Scope:** Lines 105, 107, 113, 171 (Router check)
*   **Discrepancy:** Fail-open is the only router policy, and its backstop (live GPU check) is deferred and may be blind on Windows.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** More than one defensible answer. Options: (a) fail open, accept the gap, spike decides; (b) fail open but add a cheap `docker inspect` probe of the labelled container when the file is unreadable or expired; (c) fail closed for a short window (for example 30 s) after an expired or unreadable lease, then open. Failure case for (a): sleep leaves Ollama loading onto a busy GPU. For (b): Docker Desktop slow or down makes every router call wait. For (c): a corrupt file blocks the router for the window.
*   ***Proposed Edit:*** Once chosen, rewrite lines 105-107 and Alternative 6 to state the policy, and add the spike go/no-go test for `nvidia-smi` visibility.

### [E2] Critic item 7 - `egm-design` - Severity: Medium
*   **Affected Scope:** Lines 118-122, 134-137 (container network, embedding)
*   **Discrepancy:** Outbound network access is accepted, and a localhost proxy or CORS path exposes an unauthenticated ComfyUI to local web pages.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** Options: (a) accept outbound access, add Host/Origin validation on the proxy; (b) internal-only Docker network with only the published port, no egress (the editor then cannot fetch anything from the internet, including node-side downloads); (c) egress on during build only, none at run time (same as b at run time, plus a build step that fetches models and nodes). Needs your call because (b) and (c) change whether ComfyUI can ever reach the network at run time.
*   ***Proposed Edit:*** Rewrite the accepted-risk bullet (line 122) and the embedding paragraph (136-137) to match the choice.

### [E3] Critic item 8 - `egm-design` - Severity: Medium
*   **Affected Scope:** Lines 29, 67, 126, 128
*   **Discrepancy:** Stop mid-render kills the job; Force release frees the lease while ComfyUI may still hold models; no policy for a Node restart.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** Product behaviour. Options: Force release (a) deletes the lease only and warns; (b) deletes the lease and calls `POST /free`; (c) deletes the lease and stops the container. Stop (x) refuses while the queue is non-empty; (y) asks for confirmation then interrupts. On Node restart: (p) bridge is re-adopted from the lease file, or (q) the lease expires.
*   ***Proposed Edit:*** Add a short "Stop, Force release and UI restart" subsection with the chosen behaviour.

### [E4] Critic items 11 and 14 (debounce value) - `egm-design` - Severity: Low
*   **Affected Scope:** Lines 86, 98, 132
*   **Discrepancy:** The queue-empty debounce has no value; it decides how long Ollama stays blocked after a job.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** Short means more model reloads between queued jobs; long means longer GPU blocking. A starting value is your tolerance for "GPU busy" after a job ends.
*   ***Proposed Edit:*** Set a default in the Technical Plan. Suggested start: 90 s, configurable, tuned in the spike.

## PROPOSE FIX

### [1] Critic Blocker 1 - Severity: High
*   **Scope:** Lines 95, 100-113, 171
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Step 4 conflates the free-VRAM check with the optional process check.
*   ***Proposed Edit:*** Step 4 becomes "check free VRAM is at least the minimum" only. Rename the heading at line 100 to "Router check". Move the `nvidia-smi` process check into a new subsection "Deferred: live GPU check (after the spike)". Replace line 107 with: "The lease file stops the router loading Ollama models while a lease is held. It does not block other Ollama clients (see Non-Goals)." Define "piece 1" as the first build step (lease module) or remove the term. Reword Alternative 6 once E1 is answered.

### [2] Critic Blocker 2 - Severity: High
*   **Scope:** Lines 76-77, 92, 98
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. `ollama` holder and `releasing` are unused in the core flow.
*   ***Proposed Edit:*** Mark `ollama` and `releasing` "reserved, used only if the live check is adopted". Line 92 becomes: "If a valid lease is held by `comfyui` or `kalamanch`, refuse with `GpuBusy`."

### [4] Critic item 4 - Severity: Medium
*   **Scope:** Lines 77, 92, 105
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Two places describe expiry differently.
*   ***Proposed Edit:*** Add a three-row rule: (1) the router check only reads, never clears, fails open on expired; (2) acquire may take over an expired lease only after `docker inspect` shows the container gone (or the pid is dead, for kalamanch); (3) an expired `pending` is treated as free after the lock is held and the same check passes.

### [5] Critic item 5 - Severity: Medium
*   **Scope:** Lines 29, 83, 98
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. No failure-mode coverage.
*   ***Proposed Edit:*** Add a failure-mode table: bridge crash mid-render, node crash, sleep and resume, stuck `pending`, stuck `releasing`. Each row gives the lease outcome and mitigation. Before treating an expired lease as free, acquire checks ComfyUI `/queue` for a running job. Heartbeat runs on its own thread. Outcomes for bridge restart depend on E3.

### [6] Critic item 6 - Severity: Medium
*   **Scope:** Lines 111-114, 122, 148-160
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The standard requires one risks and mitigations section.
*   ***Proposed Edit:*** Add `## Risks & Mitigations` after the Technical Plan as a table (risk, impact, mitigation, owner or test). Move Windows risks, weak points, the accepted-risk bullet and live-check blindness into it. List 8 GB feasibility first, with a spike go/no-go: fits in 8 GB, `nvidia-smi` sees processes, mount load time acceptable.

### [9] Critic item 9 - Severity: Medium
*   **Scope:** Lines 86, 109, 132, 134-137
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:*** Add `## Open Questions` (owner, resolution gate). Leave one-line pointers in the body.

### [10] Critic item 10 - Severity: Medium
*   **Scope:** Lines 13, 27, 29-33
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Goals are not testable.
*   ***Proposed Edit:*** List tab features with an acceptance condition. State maximum stale-lease time as heartbeat TTL plus the router's read interval. Define the retry hint as the holder's elapsed time plus the ETA when known. Name wall time and peak VRAM as the compared quantities for `generate_ltx.py`. Say image-quality thresholds are set in the spike.

### [11] Critic item 11 - Severity: Medium
*   **Scope:** Lines 71, 83, 86, 94
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Values are vague or inconsistent.
*   ***Proposed Edit:*** One timing table (starting values, spike-tuned): heartbeat 5 s; `ttl_s` 30 (six heartbeats); lock wait 2 s; stale lock 10 s; unload wait 60 s; debounce per E4; minimum free VRAM a placeholder (for example 6 GB) until measured.

### [12] Critic item 12 - Severity: Medium
*   **Scope:** Lines 84, 98
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:* ** Add: "A holder remembers the `generation` it received at acquire and passes it on every heartbeat and release. The write is rejected if the file's generation differs; the old holder then stops work and exits with a logged error."

### [13] Critic item 13 - Severity: Low
*   **Scope:** Lines 19, 151
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Replace "slows to a crawl" and "several times slower" with "slower (factor to be measured in the spike)". Label the WDDM spill as an observation to confirm.

### [14] Critic item 14 - Severity: Medium
*   **Scope:** Lines 94, 98
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** After writing `pending`, re-check `/api/ps` once before `held`. If the unload wait times out, or free VRAM stays below the minimum, delete the `pending` lease and raise a typed error. If the second VRAM check at release fails, keep the lease and warn in the tab.

### [15] Critic item 15 - Severity: Low
*   **Scope:** Lines 34, 41, 62-64
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add a Non-Goal: "kalamanch scripts started directly, not through `kalamanch/run.py`, do not take the lease."

### [16] Critic item 16 - Severity: Low
*   **Scope:** Lines 109-114
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Rewrite as a short list: purpose, decision pending, open questions. Use "the author" instead of "you".

### [N] Nits batch - Severity: Low
*   **Scope:** headings, voice, labels, terms, wording, missing alternatives
*   ***AI Suggestion:*** PROPOSE FIX (batch)
*   ***Proposed Edit:* ** Rename "The Problem" to "Problem Statement", "Technical Plan (Architecture)" to "Proposed Architecture". Replace "you/your" with "the author" at lines 109, 164, 166, 170, 175, 176. Replace the "(fixed ...)" tags with one "[Pre-decided]" tag plus a reason, fix list spacing at line 175. Define "lease" before line 13 and "kalamanch" and `kalamanch/run.py` at line 11. Fix wording at lines 11, 22, 39, 67, 136, 168. Add language tag to the diagram fence at line 50. Add one-line rejected alternatives: ComfyUI/Docker as source of truth, OS lock or localhost service, SQLite or named mutex, no-egress network (depends on E2).
