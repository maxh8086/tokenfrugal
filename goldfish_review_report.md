# Goldfish Resolution Report: concepts_brief.md (Stages 5 to 9)

* **Target:** `concepts_brief.md` (unchanged in this pass).
* **Inputs:** `zoom_out_report.md` (Stage 5), `comprehension_report.md` (Stage 6), `critic_report.md` (Stage 7), `intermediate_zoom_out_report.md` (Stage 8), `implementation_readiness_report.md` (Stage 9).
* **Rule:** each finding is marked PROPOSE FIX (agent drafts the edit; applied only after your approval), OWNER DECISION (a product or design choice the agent cannot make), CONTEST (two reports disagree and a check is needed), or UNVERIFIED (claimed, not checked).
* **Status:** no edit has been applied. Approve the group you want applied.

## Summary

| Class | Count | Meaning |
|---|---|---|
| PROPOSE FIX | 11 | Mechanical or evidence-backed. Edit drafted in section A. |
| OWNER DECISION | 9 | Needs your choice before a slice-1 task file can be written. |
| CONTEST | 2 | Reports disagree. Needs a check. |
| UNVERIFIED | 1 | Claimed in a report, not checked by reading. |

## A. PROPOSE FIX (apply on approval)

1. **Remove stage 4b and `mode_b_revise`; keep D5 only.** Sources: Stage 5 M5, Stage 8 M-4. The per-scene preview loop is the most expensive scope item. One contact sheet with no gate replaces it.
2. **One canonical stage list.** Sources: Stage 6 B1, Stage 7 C-B3, Stage 9 M1. Section 12 is the canonical list. Delete the seven-stage list in section 4.
3. **Remove the GPU lease from slice 1.** Sources: Stage 5 M2, Stage 7 C-B1, Stage 8 M-10, Stage 9 B2. This is conditional on voice running on CPU (see OWNER DECISION 1). Delete lines 63, 122, 168 and 189, and the B1 lease wording.
4. **Remove the `/tmp` collision claim.** Sources: Stage 5 M8, Stage 8 M-8. Each mgen call starts a new container (`router/media_generator_mcp.py:67-68`), so `/tmp` cannot collide.
5. **Synchronous single call; drop the async state draft.** Sources: Stage 5 M3, Stage 8 M-2, Stage 9 B9. Delete the `mode_motion_runs` table and the poll and heartbeat numbers at lines 94 to 96. Async is reconsidered only if the spike measures more than about 600 s.
6. **Word cap of 90, with the basis stated.** Sources: Stage 5 M1, Stage 7 C-B4, Stage 8 M-1. 30 s x 2.5 words per second = 75, plus margin. Delete the 1200-word example.
7. **Remove the stage timeouts that sum to 1080 s.** Sources: Stage 8 M-3. Keep one budget, to be set from the spike. Remove the 1800 s cap.
8. **Reduce the schema to four fields.** Sources: Stage 5 M6, Stage 8 M-5. Fields: `text`, `length_target_s`, `music` (boolean), `out_name`. Engine, voice, language, style and seed become constants recorded in the manifest.
9. **Fix the Kokoro licence citation.** Sources: Stage 8 M-11, Stage 7 D-F14. Weights are Apache-2.0 per `docs/designs/video-pipeline-use-cases.md:108`. Only the espeak-ng licence (GPL-3.0) stays open.
10. **Remove the "reuse Studio" wording.** Sources: Stage 5 M7, Stage 9 M4. Studio's runs table is design-only (`docs/designs/studio-and-collector-roles.md`). Replace with "Mode B owns its own status file" or list Studio Piece 2 as a dependency.
11. **Tolerance stated as a ±1.0 s placeholder.** Sources: Stage 5 N6, Stage 9 M11. Delete the "set from measurement" conflict at line 240.

## B. OWNER DECISION (you must choose before a slice-1 task file)

1. **Voice location: container or host.** Blocks: Stage 9 B1, Stage 5 B1, Stage 7 C-B2. Container means a Dockerfile change and a digest change. Host means no image change.
2. **Image: separate Mode B image or the same image as Mode A.** Blocks: Stage 7 C-B2, Stage 8 M-9. A separate image keeps the Mode A digest unchanged.
3. **Music: keep the dramatic `make_score.py` bed, write a neutral bed, or drop music in slice 1.** Blocks: Stage 8 M-12, Stage 9 M5. The current bed is a dark drone with riser and pulse, which conflicts with the neutral style.
4. **Phonemiser: accept espeak-ng (GPL-3.0) or replace it.** Blocks: Stage 8 M-11, Stage 9 M8.
5. **Template: aspect ratio, resolution, fps, palette, font and scene list.** Blocks: Stage 9 B8, Stage 9 M11.
6. **Approval points: script approval before voice (D5), and whether stills approval is in slice 1.** Blocks: Stage 9 M2.
7. **Tool and role contract: tool name, role name, sync or async, error strings, and the Mode B command entry point.** Blocks: Stage 9 B9, B10. Stage 5 M7 and Stage 6 B4 remain open.
8. **Run folder path, and whether Mode B output appears in `list_renders`.** Blocks: see CONTEST 1.
9. **Determinism bar (D8), and gate constants (loudness, fps, transcript tolerance).** Blocks: Stage 9 M12, M11.

## C. CONTEST (a check is needed)

1. **Does a run folder under Render break a test?** Stage 8 M-7 says no LAYOUT change is needed, because the mgen diff counts files only. Stage 9 M6 says `list_renders` lists every file and breaks `tests/test_media_workspace.py:63`. Run the test with a folder present to settle it. Do not edit until settled.
2. **Scope of the lease call.** Stage 9 B2 says the lease may not be needed. Stage 7 C-B1 says remove it. These agree on removal but disagree on whether CPU voice is confirmed. Settled by OWNER DECISION 1.

## D. UNVERIFIED (claimed, not checked)

1. **Container cannot reach the lease file.** Stage 9 B3. The reviewer cited `router/gpu_lease.py:118-125, :305-310` and `docker-compose.yml:31-32`, but did not re-read them. Moot if the lease is removed from slice 1 (A3).

## Not in this pass

The Stage 9 instruction to amend section 10 (task list) is held until owner decisions 1 to 7 are answered. The Stage 8 recommendation is to move exact values to a slice-1 task file written after sign-off, so that file is not drafted here.
