# Gates G4, G5, G6: voice sample, stills, preview (design)

Status: draft for user approval. No code written. Parent: `media-generator-multiformat-engine.md` (D35, D57, D59, D61, D64; R2).

## 1. What each gate approves

| Gate | Artifact the human sees | Generated from | Approves |
|---|---|---|---|
| G4 | Voice sample: a WAV of the first 60 s of narration, spoken with the G3 voice | Narration script for the job, first 60 s only (D59) | That the voice and delivery are acceptable |
| G5 | Stills: one PNG per scene, taken at the scene's start time (D59) | Scene list and measured audio timing (R2) | The visual content of each scene |
| G6 | Preview: an MP4 at the chosen template's full resolution, rendered from the same 60 s window as G4 (D59) | Same script window and voice as G4, plus the template | That the look and pacing are acceptable before the full render |

Each gate is opened only after the gate before it is approved (D38). A change to the upstream artifact changes its SHA-256, which breaks the approval, so downstream gates must be re-approved.

## 2. Ordering and dependencies

- G3 (voice choice, D55, D61) comes first. It is on PR #94 (`feat/g3-voice-choice`), not merged. G4 cannot start until G3 is on `main` or its branch is the base.
- G4 depends on G3 only.
- G6 depends on G4 (same window, same voice) and on the template for the job.
- G5 depends on R2 (measured audio timing), which is not built. G5 is therefore not in the first build. Until R2 exists, G5 has no timing source and stills cannot be placed at scene start times.

Build order: G4, then G6 (needs the G4 window and voice), then G5 once R2 is built.

## 3. Where the code goes

- Generation: a new module `lib/preview-gates.js` (G4 sample, G6 preview). It calls `lib/dhvani.js` for narration and the existing HyperFrames render path for G6.
- Storage: outputs are written through `lib/project-store.js` (cache entries keyed by step, inputs and parameters), so a re-run with identical inputs reuses the file.
- Approval: each artifact goes through `lib/approvals.js` and `bin/approve.js`, with the same SHA-256 record shape as G1 to G7.
- Gate check: `lib/job-gate.js` `gateJob` is extended so that G4 and G6 must be approved before the full render (G7). G5 is added with R2.

These paths are the planned locations. The implementation step must confirm them against the code before writing.

## 4. Cost and limits

- G4 is 60 s of narration: one dhvani call. Expected to be small.
- G6 is one 60 s render. It uses the same render path as a normal job and is bounded by the existing render budget.
- G5 stills: one HyperFrames still per scene, bounded by the scene limit (10 scenes per part, `PART_MAX_SCENES`).

Disk: each new artifact adds to the job folder. Measure peak disk use for G4 and G6 before setting any new floor (see the open D48 question).

## 5. Decisions (user, 2026-11-07)

1. **G4 voice sample length: 60 s.** Same window as G6 and as D59.
2. **G6 preview resolution: full resolution of the chosen template** (for example YouTube video 1920x1080, YouTube Short or Instagram Reel 1080x1920, LinkedIn video per its preset). No lower-resolution preview, so the approved preview matches the shipped output.
3. **Voice change: G4 is re-approved automatically.** A new G3 voice produces a new voice sample, which is a new artifact with a new SHA-256, so the existing G4 approval no longer matches and G4 is requested again. G6 then depends on the new G4.

## 6. Not in scope

- R2 (measured audio timing) and G5 stills implementation.
- Changing the default of `GATES_ENFORCE`, or the D48 disk floor.
- Merging PR #94.
