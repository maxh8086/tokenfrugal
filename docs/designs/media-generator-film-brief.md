# Media-generator: text brief to BusinessNext-style film

* **Status:** brainstorm. Decisions 1 to 12 are answered in section 4a. The design is not approved yet and no task has been dispatched.
* **Reviewed by:** six Goldfish lenses (design, codebase-details, zoom-out, comprehension, implementation-readiness, structural), compiled by `egm-synthesizer`.
* **Date:** 2026-11-03

## 1. Goal

A user gives a text brief. The `media-generator` container returns a finished 1920x1080 film with narration, built from HyperFrames scenes, with no generative video models and no network access at render time.

"BusinessNext-style" means the house rules in the `businessnext-video` skill: brand type and colours, safe area, mono font weight 400 or 700, minimum font sizes, banned-term guard, and a duration check against the intended length. The skill is at `C:\Users\vaibh\.claude\plugins\synced\e5bd016c-d211-464e-a9ce-c7afcfe5c6a6_cc6a4e36-7d99-4300-ad08-7464d03f29a9\businessnext-video\skills\businessnext-video\`.

## 2. Glossary

| Term | Meaning in this doc |
|---|---|
| Container | The `media-generator` Docker image and its compose service. Network-disabled. |
| Host | The Windows machine running the router (`router/`). Holds the tokenfrugal MCP servers. |
| Brief | The user's text: topic, length, voice. |
| FORMAT-CHOICE.md | The skill's record of which film format was picked and why. In slice 1 it is a fixed format. |
| Narration first | The script is written before any scene. Its word count is set by the target length at 2.70 words per second. |
| Measured synthesis | Narration audio is generated, then its real duration is measured. Timing is never estimated. |
| HyperFrames | HTML scenes rendered to video in headless Chromium. |
| Manim | Python library that renders mathematical animation. Needs LaTeX for formulas. |
| Topic gate | A rule that decides HyperFrames or Manim for a scene. Lives on the host. |
| guard | `guard.mjs`: checks banned terms, font weight, and minimum font size before render. |
| Duration check | Compares the encoded output length to `acts.json` within 0.1 s. |
| Slice | One independently testable step of the build. |
| Builder / thinker | The two local models allowed for routed work (Qwen3.5-4B and Bonsai-4B). |
| voice-artist, media-motion | Existing tokenfrugal roles in `router/tf-roles.yaml` (lines 44 and 46). |

## 3. Goals and non-goals

**Goals (slice 1):** one fixed-format film, dry narration, one HyperFrames render, offline, reproducible.

**Non-goals (slice 1):** Manim output, music bed, the eight-axis format ledger, pronunciation gauntlet, visual frame review by eye, multiple formats.

**"Offline" (testable):** `mgen brief` completes under `--network none`. No model weights are downloaded at run time. Every web asset (for example GSAP) is vendored into the image. The HyperFrames spike loaded GSAP from jsdelivr and got a 404 at render time, so this is a real gap.

**"Deterministic" (testable):** the same brief and the same seed give byte-identical mp4, `acts.json` and narration WAV (SHA-256).

## 4. Decisions needed

Each row has a recommendation. None is approved.

| # | Question | Options | Recommendation | Owner |
|---|---|---|---|---|
| 1 | Topic gate input | Topic label / visual need (equation, graph, node network) | Visual need. A topic label sends most AI-product films to Manim. | You |
| 2 | Gate location | Container / host router `media-motion` role | Host. The container is network-disabled and should not classify. | You |
| 3 | Manim in slice 1? | Yes, with texlive / No, Manim deferred | Deferred. Manim needs LaTeX, which the image does not have. Add it after one formula renders. | You |
| 4 | LaTeX | Add pinned texlive (image size cost) / drop the math path | Decide before the Manim slice, not in slice 1. | You |
| 5 | Narration service | Reuse `docker/voice` image / install Kokoro in media-generator | Reuse the voice image's Kokoro venv if its CUDA dependency is removed, so the output is the same on every machine. Its numpy decision is still open (`docker/voice/ui/server.py:127`). | You |
| 6 | "Offline" and frame review | Haiku multimodal (hosted) / local Qwen VL | Local only. Haiku is a hosted model and would break "offline". This needs a rule change to allow Qwen VL in a role; not decided. | You |
| 7 | Seed for variety | User-supplied artifact chosen at plan time / derived from brief hash | User-supplied. The render stays a pure function of that input, and variety is chosen explicitly. | You |
| 8 | Role split | Replace `voice-artist` and `media-motion` with new roles / extend existing | Extend `media-motion`; keep `voice-artist` as a lookup. Migration needs aliases for existing tasks. | You |
| 9 | Scene HTML author | Builder model / Sonnet / templates only | Templates only in slice 1 (three fixed scenes filled with brief text). No generative scene code. | You |
| 10 | Word rate and loudness | 2.70 words/s (skill) vs 3.0 (`media_briefing_mcp.py:19`); loudness target open (-25.6 LUFS measured in spike) | 2.70 words/s, as the skill specifies. Loudness target set in slice 1. | You |
| 11 | Image rollout | Replace image / new tag with current digest kept | New tag. Keep the current digest for rollback. Do not change existing `mgen` commands. | You |

### 4a. Decisions as answered by the user (2026-11-03)

1. **Gate input:** visual need. The gate receives the scene spec from the third model (the story model) after the story is approved, so most calls arrive with the flags already set.
2. **Gate location:** host router. `media-motion` may be migrated into `media-generator` and removed; decide during slice 0.
3. **Manim:** deferred to slice 2, but yes to including it.
4. **LaTeX:** add a pinned texlive layer. Size and pin to be measured before the Manim slice.
5. **Narration:** reuse the `docker/voice` Kokoro venv. Run on CPU by default; enable CUDA only if it is detected and works (auto compatibility). Benchmark CPU first.
6. **Frame review and offline:** local Qwen VL only. Needs the rule change for Qwen VL, to be written as its own step.
7. **Seed:** user-supplied at plan time.
8. **Roles:** migrate `media-motion` into `voice-artist` or `media-generator`, whichever fits each function best.
9. **Scene HTML:** templates only in slice 1.
10. **Speed and loudness:** not fixed. Add a gate that recommends words-per-second from topic, style and pitch; the user accepts or overrides. Baseline remains 2.70 as the skill default.
11. **Image rollout:** new version tag. Push all local images that are not on Docker Hub before any cleanup.
12. **Cleanup:** remove unneeded local images only after the push is confirmed and the old versions are on Docker Hub.

## 5. Topic gate (deferred to the Manim slice)

* **Type:** rule list, not a model call. A 4B model is not deterministic across runtime versions.
* **Input:** a scene spec from the brief, with an `needs_formula` / `needs_graph` flag per scene.
* **Output:** exactly one of `hyperframes` or `manim`, plus a scene spec. Nothing else.
* **Fixture:** about 20 labelled briefs, written before the rules.
* **Mixed topics:** each scene is classified separately. A film can use both engines; the shared output spec below makes that safe.
* **Override:** the user can force an engine per scene.

## 6. Tool inventory and placement

| Tool | Where | Version pin | Notes |
|---|---|---|---|
| Node 22, HyperFrames, Remotion CLI | Container | `HYPERFRAMES_VERSION`, `REMOTION_VERSION` (Dockerfile) | Existing. Chromium override already in place. |
| Chromium, ffmpeg, tesseract | Container | Unpinned apt (Dockerfile:13, 41) | Pin exact versions and the base image digest. |
| whisper-cli | Container | `WHISPER_CPP_TAG` | Existing. |
| Narration TTS (Kokoro) | Voice image, run with network none | Pin model file hashes | Models baked at build time. |
| Measure, guard, retime, sheet | Container | Pinned commit of the skill tools, vendored | Currently in the plugin directory, not in the image. |
| Manim | Container | `MANIM_COMMIT` (Dockerfile:36) | Built, but no LaTeX; math path blocked until texlive. |
| Topic gate | Host router, `media-motion` role | Rule list file | Emits engine name and scene spec only. |
| Frame review | Local Qwen VL (if approved) | Hash-pinned model tag | Not decided (decision 6). |

## 7. Slice plan

**Slice 0 (prerequisites):** commit or revert the uncommitted `docker/media-generator/Dockerfile` change. Pin the base image digest and apt versions. Fix the broken `COPY --from=scripts` build context. Vendor the skill tools at a pinned commit.

**Slice 1 (HyperFrames only, fixed format):**
* Input: brief text, target length, seed.
* Stages: word budget (2.70 words/s) → narration audio with measured duration → one HyperFrames render from three fixed Mode-B scenes → mux → guard → duration check.
* Output: mp4, `acts.json`, narration WAV, under a timestamped folder.
* Extends the existing `media_briefing_mcp.py` Mode-B stub. No parallel server.

**Slice 2 (Manim path):** only after decision 4, and only after one formula renders. Manim scenes must write into `acts.json` with the same 1920x1080 and fps spec.

**Slice 3 (optional):** music bed, format variety beyond the fixed format, visual frame review.

## 8. Slice 1 acceptance test

1. One non-math brief renders to mp4 under `mgen brief --network none`.
2. Two runs with the same brief and seed give identical SHA-256 for mp4, `acts.json` and WAV.
3. `ffprobe`: 1920x1080, one audio stream, duration within 0.1 s of `acts.json`.
4. `guard.mjs` prints GUARD PASSED with a non-empty banned-term list (`guard.config.json` ships empty today).
5. A second machine builds the image from the setup steps alone and produces matching digests.
6. A grep for `C:\` or `/home` in the source returns nothing.

Slice 2 adds: one math brief passes the gate, and fails with a clear message when LaTeX is absent.

## 9. Risks and rollback

* **Timeouts:** `loop.py` wraps each tool call in 60 s and the whole task in 540 s (`router/config.py:110-111`). A multi-minute render will report a timeout while the container keeps running. Needs a background job pattern with a status poll, or a raised limit. Decide before slice 1.
* **Mutable pins:** the Bonsai and Qwen tags are not hash-pinned.
* **Word rate:** `media_briefing_mcp.py:19` uses 3.0 words/s; the skill uses 2.70. Resolved by 4a item 10: 2.70 is the baseline, and a recommendation gate can override it per brief.
* **Rollback:** the new capability ships under a new image tag. The current digest stays in use, so existing `mgen` commands and mode-b templates are unaffected.
* **Lens conflicts:** the structural lens asks for the full document; the zoom-out lens asks for a reduced first slice. This doc follows the zoom-out scope for slice 1 and keeps the full structure for later slices.

## 10. Open questions for you

Section 4a answered decisions 1 to 12. These items are still open:

1. **Timeout (section 9):** the 60 s tool and 540 s task limits in `router/config.py:110-111` will cut off a multi-minute render. Choose a background job with a status poll, or a higher limit for this role.
2. **Qwen VL rule change (decision 6):** the rule that only the builder and thinker may be used must be amended before any frame-review step. Confirm the wording when that step is written.
3. **Texlive size (decision 4):** measured before the Manim slice, not now.
4. **Approval:** approve slice 0 and slice 1 as written in section 7. No task is dispatched until you approve.
