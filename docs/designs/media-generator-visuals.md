# Media-generator story film: visuals upgrade

Status: approved by the user (visuals first; narration, voice, loudness and music unchanged).

## Goal

Raise the picture of `scripts/story_film.py` to the level of the BN v3 film and the reference
videos: diagram, data and statement shots with motion, a shot change every 4 to 6 seconds, and
a logo end card. Narration, timing, loudness and the music bed stay as they are.

## Locked (must not change)

- `narrate()` (Kokoro `am_michael`, speed 1.0) and `word_timings()`.
- `LOUDNESS_FILTER` (`loudnorm=I=-16:TP=-1.5:LRA=11`), `make_music_bed()`, `mix_narration()` (music gain 0.15).
- `check_duration()` and `write_job_json()` output fields.
- Baseline to match after the change (from `Benchmark/video-test/media-generator-linkedin-topic-2/`):
  integrated loudness -16.4 LUFS, narration about 2.2 words per second in span, 6 scenes, 59.9 s.

## Current state (what we replace)

- `scene_backdrop_html()` draws keyword chips from `_key_terms()`.
- `build_scene_html()` holds one composition per scene (about 10 s) and drives chips with `_chip_tween_js`.
- `end_card_html()` shows text only (`END_CARD_FOOTER`, `END_CARD_CLOSING`).

## Design

### 1. Shot types (new module `scripts/story_visuals.py`)

Each scene is split into 2 or 3 shots. Each shot is one of three types, chosen from the scene's
sentences (deterministic: first matching rule wins).

| Type | Use when | Content |
|---|---|---|
| `diagram` | sentence names two or more things that connect (words like "to", "into", "from", "routes") | 2 to 4 glyph nodes joined by lines that draw in (`stroke-dashoffset`) |
| `data` | sentence has a number or a count | a panel whose rows fill (bars grow with `scaleX`) |
| `statement` | any other sentence | one large line of type, revealed word by word |

Rules: no colour tweens (opacity cross-fades only); mono type weight 400 or 700; text at least 20 px.

### 2. Glyph set (new folder `scripts/glyphs/`)

- Own SVG glyphs, 24x24 viewBox, stroke-only, under the repository licence. About 30 generic
  glyphs (document, database, gateway, shield, user, cpu, chart, alert, door, truck, sensor,
  stack, route). No vendor logos and no third-party icon library, so the film stays portable.
- Chosen per shot by keyword table in `story_visuals.py`. A missing keyword falls back to `document`.

### 3. Shot cadence

- Each scene is split into shots of 4 to 6 seconds. Shot boundaries snap to sentence ends from
  the narration timings, so the picture changes on a phrase boundary.
- Each shot gets a slow push-in (scale 1.00 to 1.04 over its length).
- Target: 12 to 15 shots in a 60-second film.

### 4. End card

- Logo wordmark (text, since no logo file is vendored) plus `END_CARD_CLOSING`, with one
  diagram glyph. Duration unchanged (`END_CARD_S`).

### 5. Finish

- 1920x1080, 30 fps. Safe margin 120 px. Font sizes at least 20 px.

## Verification

1. `PYTHONPATH=. python -m unittest tests.test_story_film tests.test_sandbox tests.test_model_sync -q`.
2. New tests in `tests/test_story_visuals.py`: shot type rules, glyph fallback, shot length 4 to 6 s,
   shot boundaries on sentence ends, no colour tweens in output.
3. Re-render the film. Check duration (59.9 s +/- 0.05). Contact sheet every 2nd frame.
4. Re-measure audio with `audio_measure.py` against the baseline above. Loudness and narration
   rate must stay within 0.3 LU and 0.1 words per second.

## Decisions

- Glyphs: own set (portable) rather than the BN v3 icon library (higher coverage, but needs
  vendoring and trademark rules).
- 12 to 15 shots per 60 s. No 3D acts (needs a GPU; breaks portability).
- Scope: `scripts/story_film.py` plus the new `story_visuals.py`, glyphs folder and tests. No
  change to the router or `media_generator_mcp.py`.

## Task split (for `plan_add` and the local builder)

1. Glyph set: 30 SVG files and a loader. Acceptance: loader test passes.
2. `story_visuals.py`: shot type choice and shot split. Acceptance: `tests/test_story_visuals.py`.
3. Diagram, data and statement builders in HTML/CSS. Acceptance: one scene renders with no overlap.
4. Wire shots into `build_scene_html()`. Acceptance: existing `tests/test_story_film.py` passes.
5. End card with logo and glyph. Acceptance: end card test passes.
6. Full verification and re-render (Sonnet runs it, records the git sha).
