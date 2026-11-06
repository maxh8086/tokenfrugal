# Stage 7 Critic Review: concepts_brief.md

* **Scope:** whole file, lines 1 to 246.
* **Standard:** feature-spec-standard.md (design and structure); egm-style REVIEW mode (style).
* **Produced by:** three read-only subagents, relayed as messages. The orchestrator saved their text here.
  * `egm:egm-design` (subagent `a8b36bbb405f64eb3`): 3 blockers, 14 majors, 5 nits. Its verdict says "two blockers" but it lists three (F1, F2, F4). This report uses the list.
  * `egm:egm-structural` (subagent `a48571fe5c19db442`): 1 blocker, 12 majors, 8 nits.
  * `egm:egm-style` (subagent `ae6673015f11ef228`): 4 blockers, 17 majors, 26 nits.
* **Status of findings:** critic output only. No finding has been applied to `concepts_brief.md`. No decision was changed.

## Cross-reviewer themes

Three reviewers found the same problems independently. These are the most important:

1. **The GPU lease is applied to slice 1, which runs on CPU.** Design F1, structural 6, style B2.
2. **The stage lists and run states disagree.** Design F4, structural 7, style M8.
3. **Decision status is stale.** Structural 5, style B3, design F20.
4. **The 1200-word example is about 8 minutes of speech, not one minute.** Design F10, style B1, structural (none). The word cap for slice 1 should be about 60 to 90 words.
5. **Mode A's pinned image and Mode B share one container.** Design F2, F8.
6. **Alternatives are scattered and no section records the rejections.** Structural 1, design F13.
7. **Approval points are unclear.** Style B4, design F16, F17.

## Blockers

* **C-B1 (design F1).** The GPU lease in blocker B1 and task 5 applies to slice 1, which is CPU-only. Calling `acquire()` would unload Ollama models (`router/gpu_lease.py:359`) and require 6 GB free VRAM (`:318-319`). The pid takeover applies only to the kalamanch holder (`:230-231`). The fix is to remove the lease from slice 1.
* **C-B2 (design F2).** D1 puts render and voice in the media-generator image. That image is pinned by digest (`docker-compose.yml:27`). Adding voice dependencies changes the Mode A pin, and the brief says Mode A is unchanged. The brief has not decided between a separate Mode B service with its own digest and a digest change with Mode A regression gates.
* **C-B3 (design F4 / structural 7 / style M8).** The run states (`queued`, `waiting_gpu`, `running:<stage>`, `done`, `failed:<stage>`) do not match the stage list. They have no approval state, so the run cannot wait for a user decision. The stage order differs between line 94 and section 12.
* **C-B4 (style B1).** The example "1200 words for a one-minute target" is about 8 minutes of speech at roughly 150 words per minute. A 20 to 30 s film is about 50 to 75 words.
* **C-B5 (style B2).** The file contradicts itself on whether voice runs on GPU. Line 20 and D1 say CPU. Lines 63, 122 and 140 refer to a GPU voice step.
* **C-B6 (style B3).** Decision status is unclear. Line 3 and the heading at line 152 do not say which decisions are still open. Lines 76 to 78 still present D3 as options.
* **C-B7 (style B4).** D5 requires script approval, but the stage table has no user approval at stage 1. Only stage 4b has one.

## Majors

* **Structural (12):**
  * S-M1. The "Alternatives considered" section is missing.
  * S-M2. The problem statement is missing. Section 1 says what Mode B does, not why it is needed.
  * S-M3. Security is not covered under risks.
  * S-M4. The summary says "about one minute". Slice 1 is 20 to 30 s (D6).
  * S-M5. The status line and the open-decisions list are stale.
  * S-M6. The GPU lease requirement contradicts the CPU voice decision.
  * S-M7. The stage lists disagree.
  * S-M8. The narration format is one WAV in one place and one WAV per line in another.
  * S-M9. The script approval gate is missing from the stage gates.
  * S-M10. The role name is inconsistent: the title says "media-generator", section 4 says "media-motion", D3 says "film role".
  * S-M11. The naming note says "keep video-editor names", but the paths already use the new names.
  * S-M12. Host or container wording is still conditional after D1.
  * S-M13. Several blockers are stale after the decisions. B6 is superseded by D6.
  * S-M14. Open items are spread across sections.
  * S-M15. Cross-references point to the wrong task (section 10, task 3).
  * S-M16. Section 12 sits after the closing risks section.
  * S-M17. Several items are repeated with diverging status.
* **Style (17):**
  * Y-M1. The summary states the one-minute target as current (line 11).
  * Y-M2. "one-minute run" appears in risk and measurement lines.
  * Y-M3. "anchored decisions" is undefined.
  * Y-M4. "holder list is closed" and "holder" are undefined.
  * Y-M5. "deterministic-enough" cannot be measured.
  * Y-M6. Mood-picker wording conflicts with the music field in slice 1.
  * Y-M7. The mode toggle has no slice-1 status.
  * Y-M8. Stage lists disagree (same as structural S-M7).
  * Y-M9. "Each stage writes one output file" is contradicted by the table.
  * Y-M10. "within a stated tolerance" states no tolerance.
  * Y-M11. Scene-gate fragment: font size, guard rules and tweens are undefined.
  * Y-M12. "loudness at the agreed target" has no value.
  * Y-M13. The narration duration check compares a file to itself.
  * Y-M14. The preview capture reference points to a task that does not cover it.
  * Y-M15. "what the user approves is what gets rendered" is absolute, but the next sentence limits it.
  * Y-M16. "Reproducibility depends on pinned inputs only" contradicts line 146.
  * Y-M17. The reproducibility claim has two readings.
  * Y-M18. The role name is not settled (same as structural S-M10).
  * Y-M19. "Option A" is not defined for D1.
  * Y-M20. The 8 GB VRAM claim is unmeasured and stated as certain.
  * Y-M21. "pid-based takeover" is undefined.
  * Y-M22. Lines 65 and 116 describe decisions that are already made.
  * Y-M23. "unverified", "unchecked" and "not verified online" are three terms for one state.
  * Y-M24. "the brief says" is ambiguous between this file and an earlier one.
  * Y-M25. Many terms and acronyms are undefined. A glossary is needed.
  * Y-M26. `_check()` has no file path.
  * Y-M27. "Dockerfile:57" is ambiguous.
  * Y-M28. "Reuse it" refers to a record that is not described.
* **Design (14):**
  * D-F3. The acceptance command for task 4 uses a Windows host venv path, which contradicts D1. The image's apt list does not include espeak-ng.
  * D-F5. The poll cadence and step budget for the async pattern are not defined. The role has a max of 8 steps.
  * D-F6. Network is open during render, and the whole media folder is mounted read-write. Scene HTML could read or send local files. Chromium runs with `--no-sandbox`.
  * D-F7. Fonts, images and model files can be fetched at run time and are not hashed. The shared `make_score.py` and `compose_intro.py` come from a working tree, not a pinned source.
  * D-F8. The media-generator service sets no memory, CPU or process limits. It runs Chromium and Kokoro alongside Mode A.
  * D-F9. There is no storage plan. The default workspace is under OneDrive, so every run's files would sync to the cloud. Nothing sets a retention rule.
  * D-F10. The 1200-word max is wrong for a 20 to 30 s film (same as C-B4).
  * D-F12. The Studio run record is not built, and it has fewer states than Mode B needs. It is not listed as a dependency.
  * D-F13. "Alternatives" are split across the document. D1 names only Option A. Remotion, CosyVoice and OpenVoice V2 are not compared.
  * D-F14. The brief marks Kokoro licence as open. `docs/designs/video-pipeline-use-cases.md:108` already records Apache-2.0 for the weights, checked on 2026-11-02. The brief does not cite it.
  * D-F15. No licence review covers the music bed, voice output or fonts for commercial use. The product is promotional, so distribution is the purpose.
  * D-F16. The schema has no mode field. The toggle has no contract, and D5 makes approval mandatory either way.
  * D-F17. The stage-2 transcript gate depends on a local ASR model that is not chosen.
  * D-F18. The frame-count check needs an fps that the brief never sets. The lease tests cover code slice 1 does not use. The compose check tests syntax only.

## Nits

* **Structural (8):** S-N1 to S-N8 cover the repetition in the summary, the review log in section 5, the bold labels instead of headings, the overlap between deferred items and non-goals, and the undefined term "anchored decisions". Full text: structural hand-back.
* **Style (26):** Y-N1 to Y-N32 cover internal reviewer IDs, jargon ("faceless", "signature", "pydantic"), vague phrases ("reliably", "real", "weak"), undefined placeholders (`<venv>`), and the "one-minute" history sentence in D6. Full text: style hand-back.
* **Design (5):**
  * D-F11. Tolerance is ±1.0 s at line 87 but "set from measurement" at line 240.
  * D-F19. "colour tween" and the font-size rule are not defined.
  * D-F20. Section 3 still lists host as an option after D1. The two-HyperFrames paragraph describes a choice that no longer exists. The role name varies.
  * D-F21. The "BusinessNext skill exists" row in section 5 should also name the other files that mention it.
  * D-F22. "The reviewers agree" and similar claims have no attached output.

## What the reviewers confirmed as correct

* The compose media-generator service has no network setting. `disableNetwork` appears only on the filesystem sidecar (`docker-compose.yml:22-33`, `profiles/media-generator.yaml:23`).
* The image includes HyperFrames 0.8.223, Chromium and ffmpeg (`docker/media-generator/Dockerfile:10, 15, 26`).
* The lease holder list is closed (`router/gpu_lease.py:38, 336-337`).
* kalamanch takes and releases the lease (`kalamanch/run.py:37, 54`).
* `mgen` needs a Raw clip and diffs Render (`router/media_generator_mcp.py:63, 79-80`).
* The role timeout is 900 s (`router/tf-roles.yaml:43`).
* The exact tool-set test is at `tests/test_preflight.py:135`.
* `LAYOUT` is at `router/media_workspace.py:15`.
* `/tmp/mgen` is at `docker/media-generator/pipeline.py:157`.
* The tool caps (6 recommended, 12 maximum) are at `router/preflight.py:63-64`.
* The heartbeat and stale sweep are at `router/store.py`.
* The 8 GB GPU figure is at `docs/designs/comfyui-gpu-lease.md:11`.
* pyproject requires Python 3.11 or later (`pyproject.toml:5`).
* The Voicebox and host-render text in `docs/designs/video-pipeline-use-cases.md:10, 24` is stale.

## Priority order for the author

Design reviewer's order: C-B1 (lease), C-B2 (image pin), C-B3 (state and stage lists), then D-F3, D-F5, D-F6, D-F8, D-F9, D-F10, D-F12, D-F13, D-F14, D-F15, D-F16, D-F17, D-F18, then the nits.

## Limits

* No review was able to measure anything. VRAM, RAM and render-time figures in the brief are estimates.
* Licence status was checked only against `docs/designs/video-pipeline-use-cases.md`, not against upstream sources.
* The businessnext skill is not in this repo. Its method is unverified.
