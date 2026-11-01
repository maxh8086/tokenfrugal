# Intermediate Zoom Out Report (Stage 8): docs/designs/comfyui-gpu-lease.md

Reviewer: egm-zoom-out, against `zoom-out-standard.md`. Compared with `zoom_out_report.md` (Stage 5) and `critic_report.md`. Owner decisions not reopened: Docker, tab in `ui/server.js`, Windows mount, release on empty queue, kalamanch takes the lease, embedded editor, LTX 0.9.8 distilled, no egress, 180 s debounce.

Context sufficiency passes. The edits made the design clearer and more testable. They also made it larger (about 330 lines). Most of the growth documents the cost of release-on-empty-queue (heartbeat, TTL, `generation`, lock file, takeover checks, bridge). The scope has not moved toward the root problem (do not load two models into 8 GB).

## What the edits did

- **Reduced:** the "Correction to the Technical Plan" section is gone; voice and headings fixed; `ollama` holder and `releasing` marked reserved; fail-open replaced by a 30 s refusal window; no-egress closes the security gap.
- **Grew:** timing table, expiry table, failure-mode table, 13-row risk table, 7-row open-questions table, deferred live-check section, alternatives from 12 to 17, eight Goals.

## Major

1. **Scope.** Pieces 3 (tab, bridge, ETA, proxy) and 5 (PSNR/SSIM harness, Tier A/B tuning, sign-off) are fully specified before the 2b go/stop gate. "Quality before speed" is a Goal unrelated to the root problem. Stage 5 #1 unaddressed. Direction: move piece 5 and the ETA method to a follow-up design written after 2b passes.
2. **ETA estimator unchanged.** Moving average, `comfy_history.json` and a "loading models" state remain. Alternative 12 rejects a simple ETA then builds a complex one. Stage 5 #2 unaddressed. Direction: ship "running, step n/m, elapsed"; add an ETA after real use.
3. **Bridge process and data flow unchanged** (Stage 5 #3). It now also owns heartbeat, `docker inspect` crash detection, history, parent-exit watching and release on exit, and its death creates the accepted known gap. Direction: justify it against a short `python -m router.gpu_lease` CLI called by Node plus `GET /queue` polling.
4. **Lease record heavier than the problem.** Reserved `ollama` and `releasing` values are still in the schema table; `generation`, lock file with stale-lock logic, ten fields, three rule tables. Direction: move reserved values to the deferred section; check whether `generation` plus the lock file is needed with one bridge and short `run.py` runs.
5. **Deferred live-check is YAGNI kept in the document.** Own section, open question, risk row, and a piece 1 test. Direction: one line in Non-Goals or Open Questions; drop the piece 1 test; reuse `nvidia-smi` shell-outs in `scripts/bench.py` and `Benchmark/script/hardware.py` for the spike and doctor.
6. **Router and acquire disagree on an expired lease.** After 30 s the router lets Ollama through; acquire refuses an expired lease while ComfyUI is live. The root problem returns after about 60 s. "Unreadable" has no timestamp, so the 30 s window has no start. Direction: one failure policy, for example the router also does the cheap `GET /queue` or label check before letting a task through, or state the gap and why.
7. **Layering and reuse** (Stage 5 #6, #7). `gpu_lease.py` mixes lease state, Ollama unload HTTP, VRAM probe, heartbeat and router wrapper. Existing `/api/ps` code in `router/preflight.py` and `Benchmark/script/modelinfo.py` not named for reuse. The `router/compose.py` edit remains although `stop_all_sync` already filters by project label; keep the test, drop the edit unless shown needed. No recorded search for an existing lock helper.
8. **Pins-schema extension** (Stage 5 #9). Still edits `docker/pins.yaml`, `scripts/pinned_build.py`, `scripts/check_pins.py` and two tests for a `nodes:` list. The `context: folder` pattern (qdrant-mcp, postgres-mcp) is not discussed in Alternatives. Direction: use it or reject it in writing.
9. **`kalamanch/run.py` coupling** (Stage 5 #8). The bypass is now a Non-Goal, but `kalamanch` importing `router/gpu_lease.py` creates a dependency on `router` with no stated package boundary. Direction: state it or put the lease module somewhere neutral.
10. **Egress mechanism is an unresolved conflict.** An internal-only network cannot publish a port. Open Question 6 offers a firewall rule or a forwarder container; a forwarder is another container to build, pin and supervise. It is a hard requirement, so name a fallback and what happens if neither works.

## Nit

11. **Altitude.** Timings table, 6 GB placeholder, `nvidia-smi` command line, websocket event list, `POST /free` parameters, `.gitignore` and docs entries belong in an implementation plan. File inventory is about 40 items; seven open questions are carried into it.
12. **Alternatives count.** 17, of which 13, 15 and 16 all concern lease storage. Merge into one entry.
13. **Goal wording.** "No stuck lease" gives a 60 s bound that the Risks table and Stop section contradict (UI restart, bridge death with a live render). Qualify with "except the known gap". "A usable tab" mixes five conditions that belong in the tab section.
14. **Stage 5 items now fixed:** #7 text conflict, #11 security, #14 structure and voice, #16 manifest naming, #10 partly.

## Stage 5 items still unaddressed

Items 1, 2, 3, 5 (partly), 6, 7, 8, 9, 12, 13, 15. Item 4 is an owner decision and is closed.

## Verdict

Simplify. The document is consistent and testable but larger than the Stage 5 version. Before the next stage: (1) move the ETA and piece 5 to a follow-up gated on the 2b spike; (2) justify or remove the bridge; (3) drop reserved schema values and the deferred live-check detail; (4) resolve the router versus acquire inconsistency; (5) use the folder-context pin pattern or explain why not; (6) name a fallback for the egress and published-port conflict.

## Resolution (2026-11-01, owner decisions)

- #1 Piece 5: keep in this design.
- #2 ETA: keep.
- #3 Bridge: detached bridge (Stage 9 E2).
- #4 Lease record: keep all.
- #5 Live check: keep as is.
- #6 Expiry: router also checks ComfyUI `GET /queue` after the refusal window (2 s timeout; a timeout lets the task through). Design, failure-mode, risk and alternative text updated.
- #7 Layering: reuse list and private-function split added to Piece 1; `compose.py` change limited to import, guard comment and test.
- #8 Pins: names and `context: folder` pattern in Piece 2a (Stage 9 E3).
- #9 `run.py` boundary: stdlib-only module, `sys.path` stated (Stage 9 item 8).
- #10 Egress: forwarder container, Start refuses if its healthcheck fails (Stage 9 E4).
- #12 Alternatives 13, 15, 16 merged. #13 "No stuck lease" goal qualified. #11 altitude: left as is.
