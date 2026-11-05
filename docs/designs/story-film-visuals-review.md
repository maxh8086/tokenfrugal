# Review: story-film-visuals.md

**Target:** `docs/designs/story-film-visuals.md`
**Date:** 2026-11-04
**Basis:** six Goldfish lens reports, deduplicated. Facts marked "verified" were checked against the files named. Facts marked "reported" come from a lens and were not re-checked here.
**Verdict:** do not approve as written. One decision rests on a false fact (D3), two decisions contradict open questions (D1, D5), and the design has no determinism or render-cost plan for 3D.

v3 skill path used for checks: `C:\Users\vaibh\.claude\plugins\synced\e5bd016c-...\businessnext-video-v3\skills\businessnext-video-v3\`

## 1. Decisions that must change before approval (most severe first)

1. **D3 is built on a false claim. Rewrite it.** The doc says the synced v3 copy has no `assets/` folder. It does: `templates/project/assets/vendor/` holds `three.bundle.js`, `THREE-LICENSE.txt` and `gsap.min.js` (verified). Copy and pin that bundle and its licence, and record the version and sha256. Do not source Three.js separately unless the bundle's version cannot be identified.
2. **3D has no render-cost or availability plan.** The image is CPU only (Debian chromium). v3 `three-d.md` line 85 says software WebGL costs about 3 s per 1080p frame (verified). That is about 45 min for 30 s of 3D at 30 fps. Before 3D is in scope, add: a measured render time for one shot, a per-film 3D budget in seconds (not shot count), and a fail-fast check that WebGL is available in the container. If the cost is not acceptable, 3D leaves slice 1 (see cut 1).
3. **3D determinism is not designed.** The constraint "no clock, no randomness" is stated, but the design has no mechanism: seeded PRNG in place of `Math.random`, no `performance.now` or `Date`, all animation driven from the master clock, pinned GL flags and a pinned renderer (SwiftShader vs GPU gives different pixels). Add these as rules for any 3D shot, plus a test: render the same shot twice and compare frame hashes. Without that test the "deterministic output" constraint is unverified.
4. **The beat solver's input does not exist.** D5 and section 5 take "measured sentence start and end times from the TTS step". `narrate()` (`story_film.py` 33-44) returns only a WAV, and `word_timings()` (47-63) splits time by character count (verified lines). Whisper.cpp is in the image but is not used for this. Decide the source: either (a) use the existing character-proportional estimate and say so, or (b) add a whisper.cpp alignment step as its own task. Until then the solver has no real data, and "cuts on sentence boundaries" is an estimate.
5. **The beat solver has no contract.** Specify: function signature, input and output types, min and max shot duration, what happens when a shot is longer than its sentence (the doc names the test case but not the behaviour), tie-breaking, and how the 3D cap is enforced. This blocks dispatch.
6. **D1 and D5 conflict with open questions A and C.** D1 commits to vendoring into the repo while question A asks whether to vendor at all. D5 ports `lanes` while question C asks whether to keep it. Resolve A and C first (recommended answers below), then restate D1 and D5 to match.
7. **Camera and transition values are presented as "from v3" but are not.** v3 says only "Camera always drifts" (`three-d.md` line 98, verified). The 1.00 to 1.06 push-in, the 20 to 40 px pan and the 6-frame fade through black do not appear in v3 (reported; the 0.60 s cross-dissolve at `narration.md` line 239 and "the house five" transitions at `three-d.md` line 62 are verified). Either mark these as new choices of this design or adopt v3's cross-dissolve and house transitions. Also state fps and canvas size, give one fixed value per shot type, and scale camera travel by shot duration so a 2 s and a 6 s shot move at the same speed.
8. **D6 (cause first) is deferred, but visuals depend on it.** The doc says the visuals cannot explain the cause while the script opens with the ending, then excludes that fix from slice 1. Move D6 into slice 1 (see cut 8). Also correct the target: `story_film.py` has no "narration writer". The v3 skill has `sub-agents/narration-writer.md` (reported). Name the real place where the rule will live.
9. **Asset provenance and trademark handling are not enforceable as written.** `MANIFEST.json` has no schema, no upstream version or commit, and no vendoring procedure. "MIT wrapper" for lobehub means the brand marks inside are not MIT-licensed. The trademark rule ("do not recolour") is stated but nothing checks it, and the fallback for a missing icon is undefined. Fix: define the manifest fields (path, sha256, vendor, upstream version or commit, licence text path), say that a missing or unlisted icon fails the build, and record per-vendor terms. Note `icons.md` line 61 reportedly allows recolouring only for `generic/*`; the doc should say this explicitly.
10. **The guard check does not exist.** Section 6 relies on a `guard.mjs`-style check. `story_film.py` line 728 reports "guard: not run: no guard config in repo" (verified). A guard exists only in a worktree and in v3 `templates/project/tools/guard.mjs` (reported). Either list "write the manifest checker" as a slice task with a test command, or drop the claim.
11. **Section 6 does not verify most decisions.** Nothing covers D3, D4, D6, determinism, trademark, render time or GL availability. Add one pass criterion per decision. The three-story re-check in section 7 needs a pass criterion (for example: line 1 names the setup, and each act has one cause then one consequence, checked by a named reviewer).
12. **The dispatch plan is missing task detail.** Per the project rules each task needs exact file paths, one acceptance command, what must not change, and a tool-call limit. None are given. Test commands are not named.

## 2. Open questions, with a recommended answer

| # | Question | Recommended answer |
|---|---|---|
| A | Vendor about 60 MB of icons and Three.js into the repo, or fetch a pinned artifact at build time? | The 19 MB and 60 MB figures are unsourced and conflict, so measure first. Recommend: vendor only the subset slice 1 uses (Tabler glyphs actually referenced, plus any cloud marks the film needs), which is small. Revisit a pinned artifact only if the measured set exceeds a size you pick. |
| B | Are four shot types enough for five destinations, or does long-form need more? | Not decidable now. Defer. Ship slice 1 with two shots and decide after one rendered film. |
| C | Keep `lanes`? | Do not port it in slice 1. Remove it from D5 and list it as a later candidate. |
| D (new) | Where do sentence timings come from? | Slice 1 uses the existing estimate. Add whisper.cpp alignment later, only if cuts visibly miss the speech. |
| E (new) | Which Tabler glyphs cover topic 4 (truck, warehouse, closed dock)? | Answer before approval, not in slice 1: list exact icon names, with a named substitute for any that do not exist. This is a lookup, not a build step. |
| F (new) | What is the room palette? | Define light and dark values in the design. Note `CHIP_LIT_BG` is `#2563eb` today (`story_film.py` line 87, verified), so reuse that where it fits. |
| G (new) | Is the "at most three 3D shots" cap a rule? | No. It comes from v3's "typically 1-3 acts" guideline (`three-d.md` line 9, reported). If you want a cap, state it as this design's own limit, tied to the render budget. |

## 3. Cuts recommended by the zoom-out lens

The lens says the design is a platform build and slice 1 should be: Tabler icons only, a GSAP push-in, hand-assigned shots on sentence timings, and a cause-first rule.

| # | Cut | View |
|---|---|---|
| 1 | Three.js and all 3D (including `graph`) from slice 1 | Agree. 3D has no determinism design, no render budget and about 45 min per 30 s on this image. The 2D `stack` and `fibre` shots need no WebGL. Keep D3 as a later decision, with the corrected fact. |
| 2 | `graph` and `lanes` shots | Agree. `graph` needs 3D, and `lanes` is not used in slice 1. |
| 3 | Beat solver | Partly agree. Slice 1 needs shot placement, but a hand-assigned shot list per film is enough. Drop the solver and its "scaling" logic until a second film shows the need. This also removes blocker 5. Keep a small unit test on the placement function. |
| 4 | Pan | Agree. Push-in alone is enough, and pan is unsupported by v3. |
| 5 | Fade through black | Agree. Use hard cuts, or v3's cross-dissolve if one is wanted. This also removes the unsupported "6-frame" claim. |
| 6 | Manifest guard | Disagree in part. Keep a minimal check (sha256 of each vendored file against the manifest), since the project requires pinned checksums. Drop the "no file outside approved vendors" scan until more than one vendor is vendored. |
| 7 | Alias table and trademark machinery | Agree for slice 1 if only Tabler is used. Tabler is generic, so none of this applies. Bring it back when the first cloud mark is needed, together with the fail-closed rule from decision 9. |
| 8 | Move D6 (cause first) into slice 1 | Agree. It is the cheapest change that improves the films, and the visuals depend on it. |
| 9 | Restrict vendors to Tabler | Agree. D2's `ai`, `aws`, `azure`, `gcp` and `microsoft` sets are not needed for topic 4. Tabler MIT licence text and a version pin are enough. |

If all cuts are taken, D1 (narrowed to Tabler), D4 (minus 3D), and a smaller D5 survive, and D2 and D3 become "later".

## 4. Corrected facts

| Doc claim | Correct fact | Status |
|---|---|---|
| D3: the synced v3 copy has no `assets/` folder, so `three.bundle.js` is unavailable | `templates/project/assets/vendor/` contains `three.bundle.js`, `THREE-LICENSE.txt` and `gsap.min.js`. `three-d.md` line 3 cites `assets/vendor/three.bundle.js`. | Verified |
| Section 5: camera values and the 6-frame fade "come from the v3 timeline model" | v3 says only "Camera always drifts" (`three-d.md` 98). Cross-dissolve is 0.60 s (`narration.md` 239). Transitions between acts are "the house five" (`three-d.md` 62). The doc's numbers are new choices. | Verified (lines 62, 98, 239) |
| Section 5: beat solver uses "measured narration" sentence times | `narrate()` returns only a WAV. `word_timings()` is proportional by character count. No measured timings exist. | Verified (lines 33-63) |
| Section 6: `guard.mjs`-style checks | No guard config in the repo (`story_film.py` 728). `guard.mjs` exists in v3 `templates/project/tools/` and a worktree only. Nothing in the repo or image holds `assets/icons`, `assets/vendor` or `MANIFEST.json`. | Verified for line 728; rest reported |
| D5: HyperFrames "captures GSAP timelines, so no new renderer is needed" | True for 2D. For 3D the image is CPU only, and v3 puts software WebGL at about 3 s per 1080p frame. "No new renderer" ignores that cost. | Verified (`three-d.md` 85) |
| D5: "each shot is a GSAP timeline" fits current code | `story_film.py` builds HTML with f-strings (`build_scene_html` line 238, `scene_backdrop_html` line 216) and loads `vendor/gsap.min.js` (line 273), copied from the image (`GSAP_IN_IMAGE`, line 464, gsap 3.15.0). There is no shot abstraction, so one must be written. | Verified (lines) |
| Section 1: "every scene is a blue box" | `CHIP_LIT_BG` is `#2563eb` (line 87), consistent with the claim. No correction needed. | Verified |
| D2: "full library is about 19 MB"; open question A: "about 60 MB" | The two figures conflict and neither is sourced. Measure the actual vendored set. | Reported |
| D2: icon sets sized loosely | `icons.md` line 17: `microsoft` has 23 icons (verified). Line 20: `ai` has about 960 (reported). Line 61: only `generic/*` may be recoloured (reported). | Mixed |
| D6: "the narration writer" | `story_film.py` has none. v3 has `sub-agents/narration-writer.md` (reported). | Reported |
| Section 4: "each film uses at most three 3D shots" as a v3 rule | v3 says "typically 1-3 acts" as a guideline (`three-d.md` 9). Not a rule. | Reported |
| Section 9: "Goldfish review not run" | Now run. Update the status line and remove or resolve the process note. | Stale |

## 5. Smaller edits (not blocking)

* Separate "decided" from "proposed" in the status line and decision table. Today everything reads as decided.
* Define terms on first use: GSAP, HyperFrames, v3, TTS, master clock, contact sheet, dBTP, Tabler, lobehub, fibre, lanes, slice 1, act, EGM, Goldfish. Define "concrete fact" and "cause and consequence" with one example each.
* Add sections for D3 and D4 (they have decisions but no matching section), or fold them into section 4.
* Move process items (section 9 first bullets) out of the design body. Order sections by decision flow: problem, decisions, then detail.
* Define the scene slot and shot-template formats (the `{ icon, label }` and `{ src, label }` shapes are given, but not the module interface a shot implements).
