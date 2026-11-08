"""Parse a story markdown file into sentences for narration."""
import os
import re
import json
import subprocess
import html
import string

try:
    from scripts.story_visuals import ACCENT, shot_count, shot_html, shot_tween_js, split_scene
except ModuleNotFoundError:
    from story_visuals import ACCENT, shot_count, shot_html, shot_tween_js, split_scene


def parse_story(path):
    """Return the sentences of the markdown story at path."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    kept = []
    for raw in lines:
        line = raw.strip()
        if re.fullmatch(r"\*{0,2}\[.*\]\*{0,2}", line):
            continue
        line = line.replace("*", "").strip()
        if len(line) >= 2 and line.startswith('"') and line.endswith('"'):
            line = line[1:-1].strip()
        elif line.startswith('"'):
            line = line[1:].strip()
        elif line.endswith('"'):
            line = line[:-1].strip()
        if line:
            kept.append(line)
    text = " ".join(kept)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


# Narration is served by the dhvani service (docker/dhvani/ui/server.py). It listens only on the compose
# network, so the request runs from the media image joined to that network.
DHVANI_NETWORK = os.environ.get("DHVANI_NETWORK", "tokenfrugal_default")
DHVANI_SPEAK_URL = os.environ.get("DHVANI_SPEAK_URL", "http://dhvani:8080/api/kokoro/speak")


def narrate(text, out_wav, voice="am_michael", speed=1.0):
    """Narrate text using dhvani. The WAV bytes are written to out_wav."""
    body = json.dumps({"text": text, "voice": voice, "speed": speed}).encode("utf-8")
    if IN_CONTAINER:
        # Already inside the media image: the request goes out from here directly.
        cmd = ["curl", "-sS", "--fail", "-X", "POST", "-H", "Content-Type: application/json",
               "--data-binary", "@-", DHVANI_SPEAK_URL]
        result = subprocess.run(cmd, input=body, capture_output=True, check=False)
    else:
        cmd = ["docker", "run", "--rm", "-i", "--network", DHVANI_NETWORK, MEDIA_IMAGE,
               "curl", "-sS", "--fail", "-X", "POST", "-H", "Content-Type: application/json",
               "--data-binary", "@-", DHVANI_SPEAK_URL]
        result = subprocess.run(cmd, input=body, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(detail[-1] if detail else f"narration failed (exit {result.returncode})")
    with open(out_wav, "wb") as f:
        f.write(result.stdout)


def word_timings(sentences, span_s):
    """Return a list of (word, start_s, end_s) tuples that cover span_s seconds.

    Each sentence is split on whitespace. Each word gets a share of span_s
    proportional to its character count, and the words keep their order.
    """
    words = [word for sentence in sentences for word in sentence.split()]
    if not words:
        return []
    total_chars = sum(len(word) for word in words)
    timings = []
    cursor = 0.0
    for word in words:
        end = cursor + span_s * len(word) / total_chars
        timings.append((word, cursor, end))
        cursor = end
    return timings


CAPTION_CSS = (
    # Caption zone x120-1800, y760-1000 (240 px). Min-height of 3 lines (3 x 1.25 line-height) so lines do not jump.
    ".caption { position: absolute; left: 120px; width: 1680px; top: 760px; bottom: 80px; box-sizing: border-box; "
    "min-height: 3.75em; margin: 0; padding: 0; line-height: 1.25; font-family: Inter, sans-serif; font-weight: 700; "
    "font-size: 48px; color: #ffffff; text-align: left; }\n"
    ".caption .w { display: inline-block; white-space: nowrap; opacity: 0; }"
)
BACKDROP_CSS = (
    ".chip { position: absolute; box-sizing: border-box; display: flex; align-items: center; justify-content: center; "
    "border-radius: 32px; background: #161b26; color: #e6edf7; font-family: Inter, sans-serif; font-weight: 700; "
    "font-size: 44px; padding: 0 24px; opacity: 0.35; text-align: center; }"
)
END_CARD_CSS = (
    ".endcard { position: absolute; left: 0; top: 0; width: 100%; height: 100%; box-sizing: border-box; padding: 0 5%; "
    "display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: Inter, sans-serif; "
    "color: #ffffff; text-align: center; }\n"
    ".endcard .tagline { margin: 0; font-size: 96px; font-weight: 800; line-height: 1.2; }\n"
    ".endcard .footer { position: absolute; left: 0; right: 0; bottom: 8%; margin: 0; font-size: 36px; "
    "letter-spacing: 0.08em; color: #b8c2d6; text-align: center; }\n"
    ".endcard .endcard-mark svg { width: 160px; height: 160px; display: block; margin: 0 auto 24px auto; }"
)
CHIP_LIMIT = 6
CHIP_DIM_BG = "#161b26"
CHIP_LIT_BG = "#2563eb"
ACCENT_CSS = "\n".join(
    [
        ".accent { position: absolute; border-radius: 24px; background: " + CHIP_LIT_BG + "; "
        "opacity: 0; transform: scale(0.85); }",
        ".progress { position: absolute; bottom: 0; left: 0; height: 10px; width: 100%; background: "
        + CHIP_LIT_BG + "; transform: scaleX(0); transform-origin: left; }",
    ]
)
SCENE_CSS = "\n".join([CAPTION_CSS, BACKDROP_CSS, END_CARD_CSS, ACCENT_CSS])
END_CARD_S = 3.0
END_CARD_FOOTER = "SBI | Business Next"
END_CARD_CLOSING = "Find out more at Business Next"
LOUDNESS_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
_TERM_RE = re.compile(r"[A-Z][A-Za-z]+")
_LOWER_TERM_RE = re.compile(r"[a-z]{7,}")
_FALLBACK_MIN_TERMS = 3
_FALLBACK_STOPWORDS = frozenset(
    "about because before after which through something another between without though "
    "while would could should there their these those where being".split()
)
_CLAUSE_BREAK_RE = re.compile("[,;:—–]")


def _key_terms(sentences):
    """Return up to CHIP_LIMIT (term, sentence_index) pairs for key terms.

    First pass: capitalised words longer than 3 letters that are not the first word of
    their sentence. If that yields fewer than 3 terms, a fallback pass adds lowercase words
    of 7+ letters (not in _FALLBACK_STOPWORDS) until 3 terms are reached. Terms keep
    first-appearance order, listed once.
    """
    seen, terms = set(), []
    for k, sentence in enumerate(sentences):
        for j, raw in enumerate(sentence.split()):
            if j == 0:
                continue
            term = raw.strip(string.punctuation + "“”‘’")
            if len(term) <= 3 or not _TERM_RE.fullmatch(term) or term in seen:
                continue
            seen.add(term)
            terms.append((term, k))
            if len(terms) == CHIP_LIMIT:
                return terms
    if len(terms) >= _FALLBACK_MIN_TERMS:
        return terms
    target = min(_FALLBACK_MIN_TERMS, CHIP_LIMIT)
    for k, sentence in enumerate(sentences):
        for raw in sentence.split():
            term = raw.strip(string.punctuation + "“”‘’")
            if not _LOWER_TERM_RE.fullmatch(term) or term in seen or term in _FALLBACK_STOPWORDS:
                continue
            seen.add(term)
            terms.append((term, k))
            if len(terms) >= target:
                return terms
    return terms


def _chip_light_times(sentences, timings):
    """Return [(chip_no, light_s)]: each chip lights at the start of the first word of its sentence."""
    offsets, total = [], 0
    for sentence in sentences:
        offsets.append(total)
        total += len(sentence.split())
    return [
        (chip_no, round(timings[offsets[k]][1], 3))
        for chip_no, (_term, k) in enumerate(_key_terms(sentences), start=1)
    ]


def _chip_tween_js(scene_index, chip_no, at_s):
    """JS line that lights one chip (background colour change and opacity 1) at at_s."""
    sel = f"#scene-{scene_index} .backdrop > .chip:nth-child({chip_no})"
    return (
        f'tl.fromTo("{sel}", {{backgroundColor: "{CHIP_DIM_BG}", opacity: 0.35}}, '
        f'{{backgroundColor: "{CHIP_LIT_BG}", opacity: 1, duration: 0.3}}, {at_s:.3f});'
    )


def _accent_spans(sentences, timings):
    """Return [(index, accent_start_s, accent_end_s)] per sentence: first word start to last word end."""
    spans, offset = [], 0
    for i, sentence in enumerate(sentences):
        n = len(sentence.split())
        if n:
            spans.append((i, round(timings[offset][1], 3), round(timings[offset + n - 1][2], 3)))
        offset += n
    return spans


def _accent_sel(scene_index, index):
    return f'#scene-{scene_index} .accent[data-index="{index}"]'


def _accent_tween_js(scene_index, index, start_s, end_s):
    """JS lines that fade one accent in at start_s and out at end_s (absolute times)."""
    sel = json.dumps(_accent_sel(scene_index, index))
    return (
        f"tl.fromTo({sel}, {{opacity: 0, scale: 0.85}}, {{opacity: 1, scale: 1, duration: 0.35}}, {start_s:.3f});\n"
        f"tl.to({sel}, {{opacity: 0, duration: 0.25}}, {end_s:.3f});"
    )


def _progress_tween_js(scene_index, at_s, duration_s):
    """JS line that grows the scene progress rule from scaleX 0 to 1 over duration_s, starting at at_s."""
    sel = json.dumps(f"#scene-{scene_index} .progress")
    return f"tl.fromTo({sel}, {{scaleX: 0}}, {{scaleX: 1, duration: {duration_s:.3f}}}, {at_s:.3f});"


def _hold_window(timings, duration_s):
    """Return (from_s, to_s) for the hold rule, relative to scene start.

    Starts when the last word ends and runs to duration_s - 0.6. If that window is empty,
    it starts at 0. The end never goes below the start, and never below 0.
    """
    from_s = timings[-1][2] if timings else 0.0
    to_s = duration_s - 0.6
    if to_s <= from_s:
        from_s = 0.0
        to_s = max(duration_s - 0.6, 0.0)
    to_s = max(to_s, from_s)
    return round(from_s, 3), round(to_s, 3)


def _hold_tween_js(scene_index, from_s, to_s):
    """JS line that grows the hold rule from scaleX 0 to 1 between from_s and to_s."""
    sel = json.dumps(f"#scene-{scene_index} .hold")
    return (
        f"tl.fromTo({sel}, {{scaleX: 0}}, "
        f"{{scaleX: 1, duration: {max(0.1, to_s - from_s):.3f}}}, {from_s:.3f});"
    )


def end_card_tagline(sentence, max_words=12):
    """Return a tagline for the end card that never ends mid-clause.

    Keeps the sentence if it has at most max_words words. Otherwise keeps the first clause
    (text before the first , ; : or dash) when it has 2 to max_words words, adding a period
    if it has no final punctuation. Otherwise returns END_CARD_CLOSING.
    """
    text = sentence.strip()
    if len(text.split()) <= max_words:
        return text
    match = _CLAUSE_BREAK_RE.search(text)
    clause = text[:match.start()].strip() if match else text
    if 2 <= len(clause.split()) <= max_words:
        if clause[-1] not in ".!?":
            clause += "."
        return clause
    return END_CARD_CLOSING


def scene_backdrop_html(sentences, width, height):
    """Return a <div class="backdrop"> holding dark rounded chips for the scene's key terms.

    Chips sit in a 2-column grid in the upper 60% of the frame. Up to CHIP_LIMIT chips.
    """
    back_h = round(height * 0.6)
    cards = []
    for i, (term, _k) in enumerate(_key_terms(sentences)):
        col, row = i % 2, i // 2
        left = 0.05 * width + col * 0.47 * width
        top = 0.03 * height + row * 0.18 * height
        cards.append(
            f'<div class="chip" style="left: {left:.0f}px; top: {top:.0f}px; '
            f'width: {0.43 * width:.0f}px; height: {0.15 * height:.0f}px;">{html.escape(term)}</div>'
        )
    return (
        f'<div class="backdrop" style="position: absolute; left: 0; top: 0; width: {width}px; height: {back_h}px;">'
        + "".join(cards)
        + "</div>"
    )


SHOT_ZONE_FRACTION = 740 / 1080  # shots fill y0-740, above the divider and the caption zone


def _slot_fade_js(sel, start, end):
    """Return the two tweens that fade a shot slot in at start and out so it ends at end."""
    fade = min(0.25, max(0.05, (end - start) / 3))
    return (
        f"tl.fromTo({sel}, {{opacity: 0}}, {{opacity: 1, duration: {fade:.3f}}}, {start:.3f});\n"
        f"tl.to({sel}, {{opacity: 0, duration: {fade:.3f}}}, {max(start, end - fade):.3f});"
    )


def _shot_slots_html(scene_index, sentences, duration_s, width, height):
    """Return (slots_html, tween_js, shots) for the scene's shots, in the top shot zone.

    Each shot from split_scene gets an absolutely positioned slot holding its shot_html fragment,
    slot height round(SHOT_ZONE_FRACTION * height). tween_js holds the scene-relative fades and
    shot_tween_js reveals. shots is a JSON-ready list of [slot_index, start_s, end_s, type].
    """
    if not sentences or duration_s <= 0:
        return "", "", []
    slot_h = round(SHOT_ZONE_FRACTION * height)
    caption = " ".join(sentences)
    parts, js, shots = [], [], []
    for k, shot in enumerate(split_scene(sentences, duration_s)):
        start, end = float(shot["start_s"]), float(shot["end_s"])
        count = shot_count(shot)
        shot = dict(shot, count=count)
        parts.append(
            f'<div class="shot-slot shot-slot-{k}" style="position: absolute; left: 0; top: 0; '
            f'width: {width}px; height: {slot_h}px; opacity: 0;">'
            f"{shot_html(shot, width, slot_h, caption=caption)}</div>"
        )
        sel = json.dumps(f"#scene-{scene_index} .shot-slot-{k}")
        js.append(_slot_fade_js(sel, start, end))
        js.append(shot_tween_js(f"#scene-{scene_index}", k, shot, start))
        shots.append([k, round(start, 3), round(end, 3), shot["type"], count])
    return "".join(parts), "\n".join(js), shots


def build_scene_html(scene_index, sentences, start_s, duration_s, width, height):
    """Build HTML document for a scene: stacked shots, and a lower-third caption with word-by-word motion."""
    reveal_s = duration_s - 0.6
    if reveal_s <= 0:
        reveal_s = 0.1
    timings = word_timings(sentences, reveal_s)
    chip_times = _chip_light_times(sentences, timings)

    start_attr = f"{start_s:.3f}"
    duration_attr = f"{duration_s:.3f}"
    tail_at = f"{duration_s - 0.4:.3f}"
    # Word and chip timings travel with the scene file so write_index_html can rebuild the tweens.
    timings_attr = html.escape(
        json.dumps([[round(s, 3), round(e, 3)] for _, s, e in timings]), quote=True
    )
    chips_attr = html.escape(json.dumps([[c, t] for c, t in chip_times]), quote=True)
    accent_spans = _accent_spans(sentences, timings)
    accents_attr = html.escape(json.dumps([[i, s, e] for i, s, e in accent_spans]), quote=True)
    # No accent blocks: they were unlabelled blue rectangles drawn over the chips and caption.
    # The chip light-up (_chip_tween_js) carries the emphasis. accent_spans still feed data-accents and tweens.
    accent_divs = ""
    word_spans = " ".join(f'<span class="w">{html.escape(w)}</span>' for w, _, _ in timings)
    js_timings = ", ".join(f"{{start: {s:.3f}, end: {e:.3f}}}" for _, s, e in timings)
    shot_slots, shot_js, shot_list = _shot_slots_html(scene_index, sentences, duration_s, width, height)
    shots_attr = html.escape(json.dumps(shot_list), quote=True)
    backdrop = (
        f'<div class="backdrop" style="position: absolute; left: 0; top: 0; '
        f'width: {width}px; height: {height}px;">{shot_slots}</div>'
    )
    divider = (
        f'<div class="divider" style="position: absolute; left: 0; top: 740px; width: {width}px; '
        f'height: 2px; background: #21262d;"></div>'
    )
    chip_js = "\n".join(_chip_tween_js(scene_index, c, t) for c, t in chip_times)
    accent_js = "\n".join(_accent_tween_js(scene_index, i, s, e) for i, s, e in accent_spans)
    progress_js = _progress_tween_js(scene_index, 0.0, duration_s)
    hold_from, hold_to = _hold_window(timings, duration_s)
    hold_js = _hold_tween_js(scene_index, hold_from, hold_to)
    hold_attr = f"{hold_from:.3f},{hold_to:.3f}"
    hold_div = (
        f'<div class="hold" style="position: absolute; left: {0.06 * width:.0f}px; top: {0.955 * height:.0f}px; '
        f'width: {0.40 * width:.0f}px; height: 4px; background: {CHIP_LIT_BG}; '
        f'transform: scaleX(0); transform-origin: left;"></div>'
    )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Scene</title>
<script src="vendor/gsap.min.js"></script>
<style>
{SCENE_CSS}
</style>
</head>
<body style="margin: 0; background: #000;">
<div id="scene-{scene_index}" data-start="{start_attr}" data-duration="{duration_attr}" data-timings="{timings_attr}" data-chips="{chips_attr}" data-accents="{accents_attr}" data-hold="{hold_attr}" data-shots="{shots_attr}" style="width: {width}px; height: {height}px; position: relative; background: #0d1117;">
{backdrop}
{divider}
{accent_divs}
<p class="caption">{word_spans}</p>
<div class="progress"></div>
{hold_div}
</div>
<script>
var tl = gsap.timeline({{paused: true}});
var timings = [{js_timings}];
timings.forEach(function (t, j) {{
  tl.fromTo("#scene-{scene_index} .caption > .w:nth-child(" + (j + 1) + ")", {{opacity: 0}}, {{opacity: 1, duration: 0.25}}, t.start);
}});
{chip_js}
{shot_js}
{accent_js}
{progress_js}
{hold_js}
tl.to("#scene-{scene_index}", {{opacity: 0, duration: 0.4}}, {tail_at});
window.__timelines = window.__timelines || {{}};
window.__timelines["scene-{scene_index}"] = tl;
</script>
</body>
</html>
"""


def scene_motion_spec(scene_index, sentences, start_s, duration_s, width, height):
    """Return the motion timeline of one scene, with the same numbers build_scene_html uses.

    Times are relative to the scene start. Used by check_scene_motion, so no HTML parsing is needed.
    """
    reveal_s = duration_s - 0.6
    if reveal_s <= 0:
        reveal_s = 0.1
    timings = word_timings(sentences, reveal_s)
    chip_times = _chip_light_times(sentences, timings)
    accent_spans = _accent_spans(sentences, timings)
    hold_from, hold_to = _hold_window(timings, duration_s)
    return {
        "index": scene_index,
        "start": start_s,
        "duration": duration_s,
        "timings": [[round(s, 3), round(e, 3)] for _, s, e in timings],
        "chips": [[c, t] for c, t in chip_times],
        "accents": [[i, s, e] for i, s, e in accent_spans],
        "hold": [hold_from, hold_to],
    }


def check_scene_motion(scene_specs):
    """Check that every scene's motion stays inside the scene and ends near its end.

    Motion points are word starts and ends, chip lights, accent starts and ends, and the hold end.
    Raises ValueError for a point outside [0, duration] or a last point more than 2.5 s before the end.
    Returns a list of dicts: index, last_motion_s, duration_s, max_gap_s.
    """
    tol = 0.001
    report = []
    for spec in scene_specs:
        index, duration = spec["index"], float(spec["duration"])
        points = []
        for s, e in spec["timings"]:
            points += [s, e]
        points += [t for _c, t in spec["chips"]]
        for _i, a_start, a_end in spec["accents"]:
            points += [a_start, a_end]
        if spec.get("hold"):
            points.append(spec["hold"][1])
        for p in points:
            if p < -tol or p > duration + tol:
                raise ValueError(
                    f"scene {index}: motion point {p} is outside [0, {duration:.3f}]"
                )
        last = max(points) if points else 0.0
        if duration - last > 2.5:
            raise ValueError(
                f"scene {index}: last motion point {last:.3f} is {duration - last:.3f} s before the end "
                f"({duration:.3f} s); limit 2.5 s"
            )
        ordered = sorted(set(points + [duration]))
        gaps = [b - a for a, b in zip(ordered, ordered[1:])]
        report.append({
            "index": index,
            "last_motion_s": round(last, 3),
            "duration_s": round(duration, 3),
            "max_gap_s": round(max(gaps), 3) if gaps else round(duration, 3),
        })
    return report


def end_card_html(tagline, width, height, scene_index=0, start_s=0.0, duration_s=END_CARD_S, fade_in_s=0.6):
    """Build the closing scene: a route glyph, a wordmark, a centred tagline and a small brand footer that fades in."""
    try:
        from scripts.glyphs import glyph
    except ModuleNotFoundError:
        from glyphs import glyph

    route_svg = glyph("route")
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>End card</title>
<script src="vendor/gsap.min.js"></script>
<style>
{SCENE_CSS}
</style>
</head>
<body style="margin: 0; background: #000;">
<div id="scene-{scene_index}" data-start="{start_s:.3f}" data-duration="{duration_s:.3f}" data-timings="[]" data-chips="[]" data-fade-in="{fade_in_s:.3f}" data-fade-out="0" style="width: {width}px; height: {height}px; position: relative;">
<div class="endcard"><div class="endcard-mark" style="color: currentColor;">{route_svg}</div><p class="endcard-wordmark" style="margin: 0 0 24px 0; font-family: monospace; font-weight: 700; font-size: 56px; color: currentColor;">Business Next</p><p class="tagline">{html.escape(tagline)}</p><p class="footer">{html.escape(END_CARD_FOOTER)}</p></div>
</div>
<script>
var tl = gsap.timeline({{paused: true}});
tl.fromTo("#scene-{scene_index}", {{opacity: 0}}, {{opacity: 1, duration: {fade_in_s:.3f}}}, 0);
tl.fromTo(".endcard-mark", {{opacity: 0}}, {{opacity: 1, duration: {fade_in_s:.3f}}}, 0);
tl.fromTo(".endcard-wordmark", {{opacity: 0}}, {{opacity: 1, duration: {fade_in_s:.3f}}}, 0.2);
window.__timelines = window.__timelines || {{}};
window.__timelines["scene-{scene_index}"] = tl;
</script>
</body>
</html>
"""


def make_music_bed(duration_s, out_wav, sample_rate=44100):
    """Build a quiet music bed with A2 and E3 pads."""
    import numpy as np
    import soundfile as sf
    
    n = int(duration_s * sample_rate)
    t = np.arange(n) / sample_rate
    signal = 0.06 * np.sin(2 * np.pi * 110 * t) + 0.06 * np.sin(2 * np.pi * 164.81 * t)
    
    fade_duration = 2.0
    fade_mask = np.ones(n, dtype=np.float64)
    fade_mask[:int(fade_duration * sample_rate)] = np.linspace(0, 1, int(fade_duration * sample_rate))
    fade_mask[-int(fade_duration * sample_rate):] = np.linspace(1, 0, int(fade_duration * sample_rate))
    signal = signal * fade_mask
    
    sf.write(out_wav, signal, sample_rate, subtype="PCM_16")
    return out_wav


def mix_narration(narration_wav, music_wav, out_wav, music_gain=0.15):
    """Mix narration over the music bed, padding the shorter with silence."""
    import numpy as np
    import soundfile as sf

    narr, sr_n = sf.read(narration_wav, dtype="float64")
    music, sr_m = sf.read(music_wav, dtype="float64")
    if sr_n != sr_m:
        raise ValueError(f"sample rate mismatch: narration {sr_n} vs music {sr_m}")
    if narr.ndim > 1:
        narr = narr.mean(axis=1)
    if music.ndim > 1:
        music = music.mean(axis=1)

    n = max(len(narr), len(music))
    narr = np.pad(narr, (0, n - len(narr)))
    music = np.pad(music, (0, n - len(music)))

    mix = narr + music_gain * music
    peak = np.max(np.abs(mix)) if n else 0.0
    if peak > 0.95:
        mix = mix * (0.95 / peak)

    sf.write(out_wav, mix, sr_n, subtype="PCM_16")
    return out_wav


_SCENE_RE = re.compile(r'<div id="scene-(\d+)"([^>]*)>(.*?)</div>\n<script>', re.S)
_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

DOT_COUNT = 40          # background dots per scene
DOT_MAX_Y = 736         # dot tops stay above the caption zone (caption starts at y760)
ENV_FPS = 10            # audio envelope bins per second (one bin = 0.1 s)
GLOW_MIN_OPACITY = 0.25
GLOW_MAX_OPACITY = 0.6

# Browser-side helpers, kept between markers so tests can run them under node.
BN_HELPERS_JS = """// BN-HELPERS-BEGIN
function bnSpring(t) {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  var k = 100, c = 14, m = 1;
  var w0 = Math.sqrt(k / m), z = c / (2 * Math.sqrt(k * m));
  var wd = w0 * Math.sqrt(1 - z * z);
  var e = Math.exp(-z * w0 * t);
  return 1 - e * (Math.cos(wd * t) + (z * w0 / wd) * Math.sin(wd * t));
}
function bnHash(s) {
  var h = 2166136261;
  for (var i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  h ^= h >>> 16; h = Math.imul(h, 2246822507);
  h ^= h >>> 13; h = Math.imul(h, 3266489909);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}
function bnRand(seed) { return bnHash(String(seed)); }
function bnDotPositions(sceneId, n, width, maxY) {
  var out = [];
  for (var i = 0; i < n; i++) {
    var key = sceneId + ':' + i;
    out.push({ x: bnRand(key) * width, y: bnRand(key + ':y') * maxY, r: 1 + bnRand(key + ':r') });
  }
  return out;
}
// BN-HELPERS-END"""

# Creates the dot field in each scene and gives every dot a GSAP opacity and y drift over the scene.
BN_DOTS_JS = """BN_CFG.scenes.forEach(function (sc) {
  var host = document.getElementById("scene-" + sc.id);
  if (!host) return;
  bnDotPositions(sc.id, BN_CFG.dots, BN_CFG.width, BN_CFG.dotMaxY).forEach(function (p) {
    var d = document.createElement("div");
    d.className = "bn-dot";
    var size = (2 * p.r).toFixed(2);
    d.style.cssText = "position:absolute;left:" + p.x.toFixed(2) + "px;top:" + p.y.toFixed(2) +
      "px;width:" + size + "px;height:" + size + "px;border-radius:50%;background:#30363d;";
    host.insertBefore(d, host.firstChild);
    tl.fromTo(d, {opacity: 0.3, y: 0}, {opacity: 0.8, y: -8, duration: sc.duration, ease: "none"}, sc.start);
  });
});"""


def series_offsets(durations):
    """Start time of each item when the items play back to back.

    Returns the cumulative sum of the durations before each item, rounded to 3 decimals.
    The first item starts at 0.0, so series_offsets([4.0, 2.5]) == [0.0, 4.0].
    """
    offsets, total = [], 0.0
    for d in durations:
        offsets.append(round(total, 3))
        total += float(d)
    return offsets


def amplitude_envelope(wav_path, fps=ENV_FPS):
    """RMS loudness of a WAV per 1/fps second bin, normalised to 0..1 by the loudest bin.

    Reads with soundfile and numpy (as make_music_bed does). Multi-channel audio is averaged to mono.
    An all-silent file gives all zeros. Values are rounded to 3 decimals so the index is deterministic.
    """
    import numpy as np
    import soundfile as sf

    data, rate = sf.read(wav_path, dtype="float64")
    if data.ndim > 1:
        data = data.mean(axis=1)
    hop = max(1, int(round(rate / fps)))
    n_bins = -(-len(data) // hop)
    rms = []
    for i in range(n_bins):
        chunk = data[i * hop:(i + 1) * hop]
        rms.append(float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) else 0.0)
    peak = max(rms) if rms else 0.0
    if peak <= 0.0:
        return [0.0] * n_bins
    return [round(v / peak, 3) for v in rms]


def scene_props(plan):
    """getInputProps-style entry point: the values the composition index needs, as plain data.

    plan keys: width, height, scene_ids (one per scene), scene_durations (seconds, in play order),
    and optionally format, start_s (default 0.0) and shots (one list per scene, each entry
    [shot_no, start, end, kind, count] relative to the scene start, as data-shots holds it).
    Scene starts come from series_offsets, so scenes play back to back from start_s.
    Returns a JSON-serialisable dict. write_index_html reads the scene timing from it and writes
    it to props.json beside index.html, in the same write step.
    """
    durations = [float(d) for d in plan["scene_durations"]]
    ids = [int(i) for i in plan["scene_ids"]]
    if len(ids) != len(durations):
        raise ValueError("scene_ids and scene_durations differ in length")
    shots = plan.get("shots") or [[] for _ in durations]
    if len(shots) != len(durations):
        raise ValueError("shots and scene_durations differ in length")
    origin = float(plan.get("start_s", 0.0))
    starts = [round(origin + offset, 3) for offset in series_offsets(durations)]
    ends = [s + d for s, d in zip(starts, durations)]
    return {
        "format": plan.get("format", ""),
        "width": int(plan["width"]),
        "height": int(plan["height"]),
        "accent": ACCENT,
        "scene_ids": ids,
        "scene_starts": starts,
        "scene_durations": [round(d, 3) for d in durations],
        "total_s": round(max(ends), 3) if ends else 0.0,
        "shots": [[list(shot) for shot in scene] for scene in shots],
    }


def _read_scene(scene_file):
    """Parse one scene file written by build_scene_html or end_card_html."""
    with open(scene_file, encoding="utf-8") as fh:
        src = fh.read()
    m = _SCENE_RE.search(src)
    if not m:
        raise ValueError(f"no scene div found in {scene_file}")
    attrs = dict(_ATTR_RE.findall(m.group(2)))
    return {
        "idx": m.group(1),
        "inner": m.group(3),
        "attrs": attrs,
        "duration": float(attrs["data-duration"]),
        "start": float(attrs["data-start"]),
        "timings": json.loads(html.unescape(attrs["data-timings"])),
        "chips": json.loads(html.unescape(attrs.get("data-chips", "[]"))),
        "accents": json.loads(html.unescape(attrs.get("data-accents", "[]"))),
        "shots": json.loads(html.unescape(attrs.get("data-shots", "[]"))),
        "fade_in": float(attrs.get("data-fade-in", "0")),
        "fade_out": attrs.get("data-fade-out", "1") == "1",
        "hold": attrs.get("data-hold"),
    }


def _glow_js(env):
    """Steps the .bn-glow opacity once per envelope bin. Empty when there is no envelope."""
    if env is None:
        return ""
    step = f"{1.0 / ENV_FPS:.1f}"
    span = f"{GLOW_MAX_OPACITY - GLOW_MIN_OPACITY:.2f}"
    return (
        f"var BN_ENV = {json.dumps(env)};\n"
        "for (var bk = 0; bk < BN_ENV.length; bk++) {\n"
        f"  tl.set(\".bn-glow\", {{opacity: {GLOW_MIN_OPACITY} + {span} * BN_ENV[bk]}}, bk * {step});\n"
        "}"
    )


def write_index_html(out_dir, scene_files, width, height, props=None):
    """Combine scene files into one composition index.html inside out_dir, plus props.json.

    Each scene's caption markup is copied into a timed clip. Scene timing (start and duration)
    comes from props, which scene_props builds from the scene files when props is None. Word
    timings and chips come from each scene's data attributes, so the output is deterministic.
    One root timeline animates every word of every scene, the shots, the dots and the glow.
    If mixed.wav sits in out_dir, its amplitude envelope drives the glow (BN_ENV); otherwise the
    glow is left out and the index stays valid.
    """
    os.makedirs(out_dir, exist_ok=True)
    scenes = [_read_scene(path) for path in scene_files]
    if props is None:
        props = scene_props({
            "width": width,
            "height": height,
            "start_s": scenes[0]["start"] if scenes else 0.0,
            "scene_ids": [s["idx"] for s in scenes],
            "scene_durations": [s["duration"] for s in scenes],
            "shots": [s["shots"] for s in scenes],
        })
    if len(props["scene_starts"]) != len(scenes):
        raise ValueError("props describe a different number of scenes than scene_files")
    clips = []
    tweens = []
    total = 0.0
    cfg_scenes = []
    rows = zip(scenes, props["scene_ids"], props["scene_starts"], props["scene_durations"], props["shots"])
    for scene, scene_id, start, duration, shots in rows:
        idx = scene["idx"]
        if int(idx) != int(scene_id):
            raise ValueError(f"props scene id {scene_id} does not match scene file {idx}")
        inner = scene["inner"]
        fade_in = scene["fade_in"]
        total = max(total, start + duration)
        cfg_scenes.append({"id": int(idx), "start": start, "duration": duration})
        clips.append(
            f'<div class="clip" id="scene-{idx}" data-start="{start:.3f}" '
            f'data-duration="{duration:.3f}" style="position: absolute; left: 0; top: 0; '
            f'width: {width}px; height: {height}px; background: #0d1117;">{inner}</div>'
        )
        for j, (word_start, _word_end) in enumerate(scene["timings"], start=1):
            sel = f"#scene-{idx} .caption > .w:nth-child({j})"
            tweens.append(
                f'tl.fromTo("{sel}", {{opacity: 0}}, {{opacity: 1, duration: 0.25}}, {start + word_start:.3f});'
            )
        for chip_no, light in scene["chips"]:
            tweens.append(_chip_tween_js(idx, chip_no, start + light))
        for acc_no, acc_start, acc_end in scene["accents"]:
            tweens.append(_accent_tween_js(idx, acc_no, start + acc_start, start + acc_end))
        if "data-accents" in scene["attrs"]:
            tweens.append(_progress_tween_js(idx, start, duration))
        if scene["hold"] is not None:
            hold_from, hold_to = (float(v) for v in scene["hold"].split(","))
            tweens.append(_hold_tween_js(idx, start + hold_from, start + hold_to))
        for k, shot_start, shot_end, kind, count in shots:
            sel = json.dumps(f"#scene-{idx} .shot-slot-{k}")
            tweens.append(_slot_fade_js(sel, start + shot_start, start + shot_end))
            shot_info = {"type": kind, "length": shot_end - shot_start, "count": count}
            tweens.append(shot_tween_js(f"#scene-{idx}", k, shot_info, start + shot_start))
        if fade_in > 0 and "endcard-mark" in inner:
            tweens.append(
                f'tl.fromTo("#scene-{idx} .endcard-mark", {{opacity: 0}}, {{opacity: 1, duration: {fade_in:.3f}}}, {start:.3f});'
            )
        if fade_in > 0:
            tweens.append(
                f'tl.fromTo("#scene-{idx}", {{opacity: 0}}, {{opacity: 1, duration: {fade_in:.3f}}}, {start:.3f});'
            )
        if scene["fade_out"]:
            tweens.append(
                f'tl.to("#scene-{idx}", {{opacity: 0, duration: 0.4}}, {start + duration - 0.4:.3f});'
            )

    mixed_path = os.path.join(out_dir, "mixed.wav")
    env = amplitude_envelope(mixed_path, fps=ENV_FPS) if os.path.exists(mixed_path) else None
    cfg = {"width": width, "dots": DOT_COUNT, "dotMaxY": DOT_MAX_Y, "scenes": cfg_scenes}

    body = "\n".join(clips)
    tween_js = "\n".join(tweens)
    cfg_json = json.dumps(cfg, sort_keys=True)
    doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Story film</title>
<script src="vendor/gsap.min.js"></script>
<style>
{SCENE_CSS}
</style>
</head>
<body style="margin: 0; background: #000;">
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{width}" data-height="{height}" style="position: relative; width: {width}px; height: {height}px; overflow: hidden; background: #000;">
{body}
</div>
<script>
window.__timelines = window.__timelines || {{}};
{BN_HELPERS_JS}
var BN_CFG = {cfg_json};
var tl = gsap.timeline({{paused: true}});
{BN_DOTS_JS}
{_glow_js(env)}
{tween_js}
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""
    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    with open(os.path.join(out_dir, "props.json"), "w", encoding="utf-8") as fh:
        json.dump(props, fh, indent=2, sort_keys=True)
    return index_path


MEDIA_IMAGE = "maxh8086/media-generator:latest"
GSAP_IN_IMAGE = "/usr/local/lib/node_modules/hyperframes/dist/vendor/npm/gsap@3.15.0/dist/gsap.min.js"
# True when this script runs inside MEDIA_IMAGE (the host sets STORY_FILM_IN_CONTAINER=1).
IN_CONTAINER = os.environ.get("STORY_FILM_IN_CONTAINER") == "1"


def _host_mount(path):
    """Return a Docker -v host path that works with Windows and Git Bash."""
    return os.path.abspath(path).replace("\\", "/")


def _docker_in_work(work_dir, args):
    """Run args inside the media image with work_dir mounted at /work.

    Inside the container (IN_CONTAINER) the args run directly in work_dir.
    """
    if IN_CONTAINER:
        return subprocess.run(list(args), cwd=work_dir, capture_output=True, text=True, check=False)
    cmd =["docker", "run", "--rm", "-v", f"{_host_mount(work_dir)}:/work", "-w", "/work", MEDIA_IMAGE]
    return subprocess.run(cmd + list(args), capture_output=True, text=True, check=False)


def render_film(out_dir):
    """Lint then render out_dir/index.html to out_dir/video.mp4 in the media image."""
    os.makedirs(out_dir, exist_ok=True)
    # The composition loads vendor/gsap.min.js, so copy GSAP from the image first.
    vendor = _docker_in_work(out_dir, ["sh", "-c", f"mkdir -p /work/vendor && cp {GSAP_IN_IMAGE} /work/vendor/gsap.min.js"])
    if vendor.returncode != 0:
        raise RuntimeError(f"vendor copy failed (exit {vendor.returncode}): {vendor.stderr.strip()[-400:]}")

    lint = _docker_in_work(out_dir, ["hyperframes", "lint"])
    if lint.returncode != 0:
        raise RuntimeError(f"hyperframes lint failed (exit {lint.returncode}): {(lint.stdout + lint.stderr).strip()[-400:]}")

    render = _docker_in_work(out_dir, ["hyperframes", "render", "--output", "video.mp4"])
    if render.returncode != 0:
        raise RuntimeError(f"hyperframes render failed (exit {render.returncode}): {(render.stdout + render.stderr).strip()[-400:]}")

    video_path = os.path.join(out_dir, "video.mp4")
    if not os.path.exists(video_path):
        raise RuntimeError(f"render reported success but {video_path} does not exist")
    return video_path


def mux_film(video_path, mixed_wav, out_mp4):
    """Copy the video stream and encode the mixed audio as AAC, trimmed to the shorter input."""
    work = os.path.dirname(os.path.abspath(out_mp4))
    for src in (video_path, mixed_wav):
        if os.path.dirname(os.path.abspath(src)) != work:
            raise ValueError(f"{src} must be in the same folder as {out_mp4}")
    
    # Pass 1: Run loudnorm and parse JSON output for measured values
    args1 = [
        "ffmpeg", "-y",
        "-i", f"/work/{os.path.basename(video_path)}",
        "-i", f"/work/{os.path.basename(mixed_wav)}",
        "-c:v", "copy",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    result1 = _docker_in_work(work, args1)
    if result1.returncode != 0:
        raise RuntimeError(f"ffmpeg pass 1 failed (exit {result1.returncode}): {result1.stderr.strip()[-400:]}")
    
    # loudnorm prints a flat (non-nested) JSON object to stderr; take the last one that parses
    measured = None
    for match in re.finditer(r"\{[^{}]*\}", result1.stderr):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "input_i" in obj:
            measured = obj
    if measured is None:
        raise RuntimeError("no loudnorm JSON found in ffmpeg pass 1 stderr")
    try:
        input_i = measured["input_i"]
        input_tp = measured["input_tp"]
        input_lra = measured["input_lra"]
        input_thresh = measured["input_thresh"]
        target_offset = measured["target_offset"]
    except KeyError as exc:
        raise RuntimeError(f"loudnorm JSON missing key {exc} in ffmpeg pass 1 output") from exc
    
    # Pass 2: Run loudnorm with measured values
    args2 = [
        "ffmpeg", "-y",
        "-i", f"/work/{os.path.basename(video_path)}",
        "-i", f"/work/{os.path.basename(mixed_wav)}",
        "-c:v", "copy",
        "-af", f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}:linear=true,alimiter=limit=0.80:attack=5:release=50:level=disabled",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        f"/work/{os.path.basename(out_mp4)}",
    ]
    result2 = _docker_in_work(work, args2)
    if result2.returncode != 0:
        raise RuntimeError(f"ffmpeg pass 2 failed (exit {result2.returncode}): {result2.stderr.strip()[-400:]}")
    if not os.path.exists(out_mp4):
        raise RuntimeError(f"ffmpeg reported success but {out_mp4} does not exist")
    return out_mp4


def check_duration(mp4_path, target_s, tolerance=0.05):
    """Probe the container duration in the media image. Returns (ok, seconds)."""
    work = os.path.dirname(os.path.abspath(mp4_path))
    args = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", f"/work/{os.path.basename(mp4_path)}",
    ]
    result = _docker_in_work(work, args)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed (exit {result.returncode}): {result.stderr.strip()[-400:]}")
    seconds = float(result.stdout.strip())
    ok = abs(seconds - target_s) <= target_s * tolerance
    return ok, seconds


def write_job_json(out_dir, info_dict):
    """Write out_dir/job.json with indent 2."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "job.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(info_dict, fh, indent=2)
    return path


WORDS_PER_MINUTE = 162
GAP_S = 0.25


def _select_sentences(sentences, target_words):
    """Keep sentences in order until the running word count reaches target_words."""
    chosen, words = [], 0
    for sentence in sentences:
        if words >= target_words:
            break
        chosen.append(sentence)
        words += len(sentence.split())
    return chosen, words


def _group_scenes(n):
    """Split n sentence indexes into scenes of 2-3 sentences where possible."""
    if n == 0:
        return []
    k = (n + 2) // 3
    base, extra = divmod(n, k)
    groups, i = [], 0
    for j in range(k):
        size = base + (1 if j < extra else 0)
        groups.append(list(range(i, i + size)))
        i += size
    return groups


def _write_failure(out_dir, message, facts):
    lines = ["# RUN_FAILED: video", "", f"Error: {message}", ""]
    lines += [f"- {key}: {value}" for key, value in facts.items()]
    path = os.path.join(out_dir, "RUN_FAILED-video.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def run_cli(args):
    """Narrate the chosen sentences on the host, then assemble the film in the media image.

    The numeric and render work runs in maxh8086/media-generator:latest through assemble_plan.
    Returns the container exit code.
    """
    out = os.path.abspath(args.out)
    tmp = os.path.join(out, "tmp")
    os.makedirs(tmp, exist_ok=True)
    width, height = (1080, 1920) if args.format == "9x16" else (1920, 1080)

    sentences = parse_story(args.story)
    chosen, word_count = _select_sentences(sentences, WORDS_PER_MINUTE * args.minutes)
    if not chosen:
        raise SystemExit("story has no sentences")

    wav_files = []
    for i, sentence in enumerate(chosen):
        rel = f"tmp/s{i}.wav"
        narrate(sentence, os.path.join(out, rel), voice="am_michael")
        wav_files.append(rel)

    plan = {
        "chosen": chosen,
        "last_sentence": sentences[-1],
        "width": width,
        "height": height,
        "minutes": args.minutes,
        "destination": args.destination,
        "format": args.format,
        "story": os.path.abspath(args.story),
        "word_count": word_count,
        "wav_files": wav_files,
    }
    with open(os.path.join(tmp, "plan.json"), "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = [
        "docker", "run", "--rm",
        "-e", "STORY_FILM_IN_CONTAINER=1",
        "-v", f"{_host_mount(out)}:/work",
        "-v", f"{_host_mount(repo_root)}:/app:ro",
        "-w", "/work",
        MEDIA_IMAGE,
        "python3", "/app/scripts/story_film.py", "assemble", "/work/tmp/plan.json",
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        failure = os.path.join(out, "RUN_FAILED-video.md")
        if os.path.exists(failure):
            print(f"RUN_FAILED: {failure}")
        else:
            print(f"RUN_FAILED: container exited {result.returncode} without a report")
        return result.returncode
    print(f"OK: {os.path.join(out, 'film.mp4')}")
    return 0


WORK_DIR = "/work"


def assemble_plan(plan_path):
    """Container entry point: build the film from plan.json inside WORK_DIR. Returns the exit code.

    Reads the narration wavs listed in the plan, then builds scenes, music, mix, render,
    mux and the duration check. On any failure it writes RUN_FAILED-video.md and returns 1.
    """
    out = WORK_DIR
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    width, height = plan["width"], plan["height"]
    chosen = plan["chosen"]
    facts = {
        "destination": plan["destination"],
        "format": plan["format"],
        "word_count": plan["word_count"],
        "sentence_count": len(chosen),
    }
    try:
        import numpy as np
        import soundfile as sf

        tmp = os.path.join(out, "tmp")
        parts, starts, sr, cursor = [], [], None, 0.0
        for i, rel in enumerate(plan["wav_files"]):
            data, rate = sf.read(os.path.join(out, rel), dtype="float64")
            if data.ndim > 1:
                data = data.mean(axis=1)
            if sr is None:
                sr = rate
            elif rate != sr:
                raise RuntimeError(f"sample rate changed from {sr} to {rate} at sentence {i}")
            if i > 0:
                parts.append(np.zeros(int(GAP_S * sr)))
                cursor += GAP_S
            starts.append(cursor)
            parts.append(data)
            cursor += len(data) / sr

        narration_s = cursor
        narration_wav = os.path.join(tmp, "narration.wav")
        sf.write(narration_wav, np.concatenate(parts), sr, subtype="PCM_16")

        groups = _group_scenes(len(chosen))
        scene_files, scene_specs = [], []
        scene_durations, shot_lists = [], []
        for k, group in enumerate(groups):
            start = starts[group[0]]
            end = starts[groups[k + 1][0]] if k + 1 < len(groups) else narration_s
            scene_sentences = [chosen[i] for i in group]
            scene_path = os.path.join(tmp, f"scene_{k}.html")
            with open(scene_path, "w", encoding="utf-8") as fh:
                fh.write(build_scene_html(k, scene_sentences, start, end - start, width, height))
            scene_files.append(scene_path)
            scene_specs.append(scene_motion_spec(k, scene_sentences, start, end - start, width, height))
            scene_durations.append(end - start)
            shot_lists.append(_shot_slots_html(k, scene_sentences, end - start, width, height)[2])

        # Raises ValueError (handled below as RUN_FAILED) if any scene's motion is out of bounds or stalls.
        motion_check = check_scene_motion(scene_specs)
        facts["motion_check"] = motion_check

        # The end card is the final scene: it follows the narration and fades in.
        tagline = end_card_tagline(plan["last_sentence"])
        end_idx = len(groups)
        end_path = os.path.join(tmp, f"scene_{end_idx}.html")
        with open(end_path, "w", encoding="utf-8") as fh:
            fh.write(end_card_html(tagline, width, height, scene_index=end_idx,
                                   start_s=narration_s, duration_s=END_CARD_S))
        scene_files.append(end_path)
        scene_durations.append(END_CARD_S)
        shot_lists.append([])
        total_s = narration_s + END_CARD_S

        facts["scene_count"] = len(groups) + 1
        facts["narration_seconds"] = round(narration_s, 3)
        facts["target_seconds"] = round(total_s, 3)

        props = scene_props({
            "width": width,
            "height": height,
            "format": plan["format"],
            "start_s": 0.0,
            "scene_ids": list(range(len(scene_files))),
            "scene_durations": scene_durations,
            "shots": shot_lists,
        })
        bed = make_music_bed(total_s, os.path.join(tmp, "music.wav"), sample_rate=sr)
        mixed = mix_narration(narration_wav, bed, os.path.join(out, "mixed.wav"))
        # Written after mixed.wav exists so the index can carry the audio-reactive glow envelope.
        write_index_html(out, scene_files, width, height, props=props)

        video = render_film(out)
        film = mux_film(video, mixed, os.path.join(out, "film.mp4"))
        ok, seconds = check_duration(film, total_s)
        if not ok:
            raise RuntimeError(f"duration check failed: film is {seconds:.3f}s, target {total_s:.3f}s")

        job = {
            "destination": plan["destination"],
            "format": plan["format"],
            "minutes": plan["minutes"],
            "story": plan["story"],
            "word_count": plan["word_count"],
            "sentence_count": len(chosen),
            "scene_count": len(groups) + 1,
            "motion_check": motion_check,
            "narration_seconds": round(narration_s, 3),
            "end_card_seconds": END_CARD_S,
            "end_card_tagline": tagline,
            "loudness": {"filter": LOUDNESS_FILTER, "target_lufs": -16, "true_peak_dbtp": -1.5},
            "final_duration_seconds": round(seconds, 3),
            "render_exit_codes": {"vendor_copy": 0, "lint": 0, "render": 0, "mux": 0, "probe": 0},
            "voice": "am_michael",
            "music": "procedural sine pad 110 Hz and 164.81 Hz, 2 s fades, no randomness",
            "sample_rate": sr,
            "gpu": False,
            "ollama": False,
            "guard": "not run: no guard config in repo",
            "output": film,
        }
        write_job_json(out, job)
    except Exception as exc:  # narration read, render, mux, probe or duration check failed
        path = _write_failure(out, str(exc), facts)
        print(f"RUN_FAILED: {path}")
        return 1

    print(f"OK: {film} ({seconds:.3f}s)")
    return 0


SHORTLIST = [
    ("youtube-shorts", "9x16", "ministral-3-8b", "topic-4"),
    ("instagram-reels", "9x16", "qwen3-8-9b-distill", "topic-5"),
    ("facebook-reels", "9x16", "nemotron-3-nano-4b", "topic-1"),
    ("linkedin", "16x9", "ministral-3-8b", "topic-2"),
    ("long-form", "16x9", "ministral-3-8b", "topic-3"),
]


def run_shortlist():
    """Run the five shortlist jobs one after another. Returns 1 if any job fails."""
    import argparse

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    failed = False
    for destination, fmt, model, topic in SHORTLIST:
        out = os.path.join(repo_root, "Benchmark", "video-test", destination, model, topic)
        story = os.path.join(repo_root, "Benchmark", "story-test", "outputs-v3",
                             destination, model, topic, "story.md")
        args = argparse.Namespace(story=story, destination=destination, format=fmt, out=out, minutes=1.0)
        label = f"{destination}/{model}/{topic}"
        error = None
        try:
            code = run_cli(args)
        except (Exception, SystemExit) as exc:
            code, error = 1, exc
        if code == 0:
            with open(os.path.join(out, "job.json"), encoding="utf-8") as fh:
                seconds = json.load(fh)["final_duration_seconds"]
            print(f"{label} PASS {seconds}s")
        else:
            failed = True
            print(f"{label} RUN_FAILED {error or ''}".rstrip())
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="scripts.story_film")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="build one film from a story")
    run_p.add_argument("--story", required=True)
    run_p.add_argument("--destination", required=True)
    run_p.add_argument("--format", required=True, choices=["9x16", "16x9"])
    run_p.add_argument("--out", required=True)
    run_p.add_argument("--minutes", type=float, default=1.0)
    asm_p = sub.add_parser("assemble", help="assemble a film from plan.json (runs in the media image)")
    asm_p.add_argument("plan")
    sub.add_parser("shortlist", help="run the five shortlist jobs")
    parsed = parser.parse_args()
    if parsed.cmd == "assemble":
        sys.exit(assemble_plan(parsed.plan))
    if parsed.cmd == "shortlist":
        sys.exit(run_shortlist())
    sys.exit(run_cli(parsed))
