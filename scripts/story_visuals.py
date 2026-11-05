"""Shot types, shot splitting, glyph choice and shot layout for the story film visuals.

See docs/designs/media-generator-visuals.md, sections 1 to 3.

Layout (1920 x 1080 frame, all coordinates absolute to the frame):
  heading zone   x120-1800, y80-270   (heading 72px, subline 28px)
  graphic zone   x120-1800, y300-720  (rounded panel; everything inside .shot-stage)
  divider        y740                 (drawn by the scene, not by the shot)
  caption zone   y760-1000            (narration caption, drawn by the scene)
A shot is rendered into a slot 1920 x 740 at the top of the frame, so no shot element sits at y >= 740.
"""

from __future__ import annotations

import html
import json
import math
import re
import string

try:
    from scripts.glyphs import glyph
except ModuleNotFoundError:
    from glyphs import glyph

CONNECTING_WORDS = ("to", "into", "from", "routes", "connects", "links", "sends", "feeds")
NUMBER_WORDS = (
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen", "twenty", "hundred", "thousand", "million", "percent",
)
_SCALE_FACTORS = {"hundred": 100, "thousand": 1000, "million": 1000000}
_SCALE_WORDS = ("hundred", "thousand", "million", "percent")
# "one" is never a figure, so it is not in the head list.
_HEAD_WORDS = tuple(w for w in NUMBER_WORDS if w not in _SCALE_WORDS)
_WORD_VALUES = {word: i + 2 for i, word in enumerate(_HEAD_WORDS)}  # two=2 ... twenty=20

_DATA_RE = re.compile(r"\d|\b(?:" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)
_DIAGRAM_RE = re.compile(r"\b(?:" + "|".join(CONNECTING_WORDS) + r")\b", re.IGNORECASE)

MIN_SHOT_S = 4.0
MAX_SHOT_S = 6.0

# (keywords, glyph). A keyword matches at the start of any word in the sentence.
GLYPH_RULES = (
    (("database", "data", "record"), "database"),
    (("gateway", "api"), "gateway"),
    (("secure", "security", "shield"), "shield"),
    (("user", "customer", "people"), "user"),
    (("cpu", "compute", "model"), "cpu"),
    (("chart", "metric", "percent"), "chart"),
    (("alert", "error", "fail"), "alert"),
    (("network", "connect"), "network"),
    (("server", "system"), "server"),
    (("cloud",), "cloud"),
    (("route", "path"), "route"),
    (("drone", "flight", "truck"), "truck"),
    (("sensor",), "sensor"),
    (("depot", "door"), "door"),
    (("loader", "dispatcher", "pilot", "captain"), "user"),
    (("box", "cargo", "seal", "suppl", "part"), "stack"),
)
DEFAULT_GLYPH = "document"

# Words that never name a data row or a big-number noun.
_STOP_WORDS = frozenset(
    "a an the of in on at by to for and or but over than from with as is was were are be been "
    "that which who it its their our his her this these those into after before during since "
    "until while across per about so not then all each both many more most some only also "
    "nearly almost just up down out off has have had will would could should can may might one".split()
)


def choose_shot_type(sentence: str) -> str:
    """Return "data", "diagram" or "statement" (first matching rule wins)."""
    if _DATA_RE.search(sentence):
        return "data"
    if _DIAGRAM_RE.search(sentence):
        return "diagram"
    return "statement"


def _shot_count(duration_s: float, n_sentences: int) -> int:
    """2 shots below 12 s, otherwise 3; more when 4 to 6 s per shot needs it."""
    base = 2 if duration_s < 12.0 else 3
    needed = math.ceil(duration_s / MAX_SHOT_S)
    return max(1, min(max(base, needed), n_sentences))


def glyph_set(sentences: list[str]) -> list[str]:
    """Ordered, de-duplicated glyph names matched by any sentence (default glyph excluded)."""
    names: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        for keywords, name in GLYPH_RULES:
            if name in names:
                continue
            if any(re.search(r"\b" + re.escape(kw), lowered) for kw in keywords):
                names.append(name)
    return [name for name in names if name != DEFAULT_GLYPH]


def _clean(token: str) -> str:
    return token.strip(string.punctuation + "“”‘’")


def _is_noun_like(token: str) -> bool:
    word = token.lower()
    return (
        word.isalpha()
        and len(word) >= 2
        and word not in _STOP_WORDS
        and word not in _HEAD_WORDS
        and word not in _SCALE_WORDS
    )


def _sentence_figures(sentence: str) -> list[dict]:
    """Figures in one sentence: digit runs or number words (not "one"), with scale words folded in.

    Each figure is {"text", "value", "label"}. The label is the noun after the figure, or the
    word before it when there is no noun after. A figure with neither is dropped.
    """
    tokens = [_clean(t) for t in sentence.split()]
    found: list[dict] = []
    i = 0
    while i < len(tokens):
        word = tokens[i].lower()
        is_digit = bool(re.fullmatch(r"\d[\d,]*(?:\.\d+)?", word))
        if not (is_digit or word in _WORD_VALUES):
            i += 1
            continue
        value = float(word.replace(",", "")) if is_digit else float(_WORD_VALUES[word])
        parts = [tokens[i]]
        j = i + 1
        while j < len(tokens) and tokens[j].lower() in _SCALE_WORDS:
            scale = tokens[j].lower()
            if scale in _SCALE_FACTORS:
                value *= _SCALE_FACTORS[scale]
            parts.append(tokens[j])
            j += 1
        label = None
        if j < len(tokens) and _is_noun_like(tokens[j]):
            label = tokens[j]
        elif i > 0 and _is_noun_like(tokens[i - 1]):
            label = tokens[i - 1]
        if label is not None:
            found.append({"text": " ".join(parts).lower(), "value": value, "label": label.lower()})
        i = j
    return found


def _group_figures(sentences: list[str]) -> list[dict]:
    """Figures across a shot, one per label (first occurrence wins)."""
    seen: set[str] = set()
    figures: list[dict] = []
    for sentence in sentences:
        for fig in _sentence_figures(sentence):
            if fig["label"] in seen:
                continue
            seen.add(fig["label"])
            figures.append(fig)
    return figures


def choose_group_type(sentences: list[str], prev_type: str | None) -> str:
    """Return "data", "diagram" or "statement" for a whole shot group.

    "data" needs at least one real figure (see _sentence_figures) and a previous shot that was
    not data, so two data shots never sit next to each other. "diagram" needs a connecting word
    or two or more glyphs. Anything else is a statement with a graphic.
    """
    if prev_type != "data" and _group_figures(sentences):
        return "data"
    if any(_DIAGRAM_RE.search(s) for s in sentences) or len(glyph_set(sentences)) >= 2:
        return "diagram"
    return "statement"


def split_scene(sentences: list[str], duration_s: float) -> list[dict]:
    """Split a scene into shots that cover 0.0 to duration_s with no gaps.

    Sentence durations are assumed equal (duration_s / len(sentences) each), so
    shot boundaries fall at sentence ends. Each shot is one or more whole sentences.
    """
    if duration_s <= 0:
        raise ValueError("duration_s must be greater than 0")
    if not sentences:
        raise ValueError("sentences must not be empty")

    m = len(sentences)
    n = _shot_count(duration_s, m)

    # cuts[k-1] = number of sentences before the k-th boundary.
    cuts: list[int] = []
    prev = 0
    for k in range(1, n):
        ideal = round(k * m / n)
        lo = prev + 1
        hi = m - (n - k)  # leave at least one sentence for each later shot
        j = min(max(ideal, lo), hi)
        cuts.append(j)
        prev = j

    bounds = [0] + cuts + [m]
    shots: list[dict] = []
    prev_type: str | None = None
    for i in range(n):
        first, last = bounds[i], bounds[i + 1]
        start_s = 0.0 if i == 0 else round(duration_s * first / m, 6)
        end_s = duration_s if i == n - 1 else round(duration_s * last / m, 6)
        group = list(sentences[first:last])
        kind = choose_group_type(group, prev_type)
        prev_type = kind
        shots.append({
            "start_s": start_s,
            "end_s": end_s,
            "type": kind,
            "sentences": group,
        })
    return shots


def glyph_for(sentence: str) -> str:
    """Return a glyph name from scripts/glyphs for the sentence."""
    lowered = sentence.lower()
    for keywords, glyph_name in GLYPH_RULES:
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw), lowered):
                return glyph_name
    return DEFAULT_GLYPH


# ---------------------------------------------------------------- layout constants (1920 x 1080 frame)

FRAME_W = 1920
SHOT_ZONE_H = 740          # shots end above the divider at y740
HEAD_X = 120
HEAD_TOP = 80
SUB_TOP = 190
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 120, 300, 1680, 420
DIAG_TILE_TOP = 410
DIAG_TILE_PX = 200
DIAG_LABEL_TOP = 630
DIAG_EDGE_Y = 510
DIAG_SPAN_LEFT, DIAG_SPAN_WIDTH = 200, 1320
MAX_DIAG_TILES = 4
ROW_TOPS = (360, 450, 540)
MAX_ROWS = 3
MIN_BAR_FRACTION = 0.15
BIG_NUMBER_PX = 160
BIG_NUMBER_TOP = 370       # 160px line centred on y450
NOUN_TOP = 620
STMT_TILE_LEFT, STMT_TILE_TOP, STMT_TILE_PX = 820, 380, 280
STMT_RING_LEFT, STMT_RING_TOP, STMT_RING_PX = 790, 350, 340
ACCENT = "#2f81f7"
_FALLBACK_GLYPHS = ("document", "server", "cloud", "network")
_XML_DECL_RE = re.compile(r"<\?xml[^>]*\?>\s*")
_TYPE_HEADINGS = {"diagram": "Flow", "data": "Figures", "statement": "Point"}
# GSAP ease for the shot reveals. bnSpring is defined in the index script (story_film.write_index_html).
SPRING_EASE_JS = "function(p){return bnSpring(p);}"

# Only opacity, transform and stroke-dashoffset animate, driven by GSAP (see shot_tween_js).
# No CSS keyframes or animations: they run on wall-clock time, not the seeked timeline.
_COMMON_CSS = """
.shot{box-sizing:border-box;margin:0;overflow:hidden;color:#e6edf3;background:#0d1117;font-family:monospace;}
.shot .sh-stage{transform-origin:50% 50%;}
"""
_DIAGRAM_CSS = """
.shot-diagram .sh-node svg{width:120px;height:120px;display:block;}
"""
_STATEMENT_CSS = """
.shot-statement .sh-node svg{width:180px;height:180px;display:block;}
"""


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _title_case(words: list[str]) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in words)


def _glyph_title(name: str) -> str:
    return _title_case(name.replace("_", " ").split())


def _diagram_glyphs(sentences: list[str]) -> list[str]:
    """Up to MAX_DIAG_TILES glyph names from glyph_set, padded to at least 2 with fallback glyphs."""
    names = glyph_set(sentences)[:MAX_DIAG_TILES]
    for name in _FALLBACK_GLYPHS:
        if len(names) >= 2:
            break
        if name not in names:
            names.append(name)
    return names


def _shot_glyphs(sentences: list[str]) -> list[str]:
    names = glyph_set(sentences)
    return names or [glyph_for(sentences[0])] if sentences else [DEFAULT_GLYPH]


def _data_figures(sentences: list[str]) -> list[dict]:
    return _group_figures(sentences)[:MAX_ROWS]


def shot_count(shot: dict) -> int:
    """Number of tiles (diagram), rows (data, 2 or more figures) or 1 (big number, statement)."""
    kind = shot["type"]
    sentences = list(shot.get("sentences", []))
    if kind == "diagram":
        return len(_diagram_glyphs(sentences))
    if kind == "data":
        return max(1, len(_data_figures(sentences)))
    return 1


def _heading_and_subline(sentences: list[str], kind: str, caption: str) -> tuple[str, str]:
    """Subject heading and glyph subline for a shot.

    Heading: the first glyph keyword with a number word or "the" before it, title-cased, max 4 words.
    It falls back to the glyph name, then to a type word, and skips any candidate that appears in
    the caption text, so the heading never repeats the caption.
    """
    phrase: list[str] = []
    for sentence in sentences:
        words = [_clean(w) for w in sentence.split()]
        for i, word in enumerate(words):
            lowered = word.lower()
            if any(lowered.startswith(kw) for kws, _n in GLYPH_RULES for kw in kws):
                before = words[i - 1].lower() if i > 0 else ""
                lead = []
                if before and (before in _WORD_VALUES or before.isdigit() or before == "the"):
                    lead = [words[i - 1]]
                phrase = (lead + [word])[:4]
                break
        if phrase:
            break

    names = _shot_glyphs(sentences) if kind != "diagram" else _diagram_glyphs(sentences)
    candidates = []
    if phrase:
        candidates.append(_title_case(phrase))
        candidates.append(_title_case(phrase[-1:]))
    candidates.append(_glyph_title(names[0]))
    candidates.append(_TYPE_HEADINGS[kind])
    caption_lower = caption.lower()
    heading = next(
        (c for c in candidates if c.lower() not in caption_lower), candidates[-1]
    )
    subline = " / ".join(names[:12])
    return heading, subline


def _shot_length(shot: dict) -> float:
    if "length" in shot:
        return float(shot["length"])
    return float(shot["end_s"]) - float(shot["start_s"])


def _glyph_svg(name: str) -> str:
    return _XML_DECL_RE.sub("", glyph(name)).strip()


def _heading_html(heading: str, subline: str) -> str:
    return (
        f'<p class="sh-title" style="position:absolute;left:{HEAD_X}px;top:{HEAD_TOP}px;width:1680px;'
        f"margin:0;font-family:monospace;font-size:72px;font-weight:700;line-height:1.2;color:#e6edf3;"
        f'white-space:nowrap;overflow:hidden;opacity:0;">{_esc(heading)}</p>'
        f'<p class="sh-sub" style="position:absolute;left:{HEAD_X}px;top:{SUB_TOP}px;width:1680px;'
        f"margin:0;font-family:monospace;font-size:28px;font-weight:400;line-height:1.3;color:#8b949e;"
        f'white-space:nowrap;overflow:hidden;opacity:0;">{_esc(subline)}</p>'
    )


def _panel_html() -> str:
    # .bn-glow is an accent ring over the panel border. Its opacity is driven by the audio envelope
    # (BN_ENV) in the index; it stays at opacity 0 when no envelope exists.
    return (
        f'<div class="sh-panel" style="position:absolute;left:{PANEL_X}px;top:{PANEL_Y}px;'
        f"width:{PANEL_W}px;height:{PANEL_H}px;box-sizing:border-box;border-radius:32px;"
        f'background:#161b22;border:2px solid #30363d;opacity:0;">'
        f'<div class="bn-glow" style="position:absolute;left:-2px;top:-2px;width:{PANEL_W}px;'
        f"height:{PANEL_H}px;box-sizing:border-box;border-radius:32px;border:2px solid {ACCENT};"
        f'opacity:0;"></div></div>'
    )


def _diagram_body(sentences: list[str]) -> str:
    names = _diagram_glyphs(sentences)
    n = len(names)
    lefts = [round(DIAG_SPAN_LEFT + i * DIAG_SPAN_WIDTH / (n - 1)) for i in range(n)]
    edges = []
    for i in range(n - 1):
        x1 = lefts[i] + DIAG_TILE_PX
        x2 = lefts[i + 1]
        edges.append(
            f'<line class="sh-edge sh-edge-{i}" x1="{x1}" y1="{DIAG_EDGE_Y}" x2="{x2}" y2="{DIAG_EDGE_Y}" '
            f'stroke="{ACCENT}" stroke-width="4" pathLength="1" stroke-dasharray="1" '
            'stroke-dashoffset="1" stroke-linecap="butt"/>'
        )
    svg = (
        f'<svg class="sh-edges" viewBox="0 0 {FRAME_W} {SHOT_ZONE_H}" width="{FRAME_W}" height="{SHOT_ZONE_H}" '
        'style="position:absolute;left:0;top:0;overflow:visible;">' + "".join(edges) + "</svg>"
    )
    tiles = []
    for i, name in enumerate(names):
        tiles.append(
            f'<div class="sh-node sh-node-{i}" style="position:absolute;left:{lefts[i]}px;top:{DIAG_TILE_TOP}px;'
            f"width:{DIAG_TILE_PX}px;height:{DIAG_TILE_PX}px;box-sizing:border-box;border-radius:32px;"
            "background:#0d1117;border:2px solid #30363d;color:#ffffff;display:flex;align-items:center;"
            f'justify-content:center;opacity:0;">{_glyph_svg(name)}</div>'
            f'<div class="sh-label sh-label-{i}" style="position:absolute;left:{lefts[i]}px;top:{DIAG_LABEL_TOP}px;'
            f"width:{DIAG_TILE_PX}px;text-align:center;font-size:28px;font-weight:700;line-height:1.2;"
            f'color:#e6edf3;white-space:nowrap;opacity:0;">{_esc(name.upper())}</div>'
        )
    return svg + "".join(tiles)


def _data_body(sentences: list[str]) -> str:
    figures = _data_figures(sentences)
    if not figures:  # split_scene never makes a figure-less data shot; render nothing rather than guess
        return ""
    if len(figures) == 1:
        fig = figures[0]
        text = fig["text"][:1].upper() + fig["text"][1:]
        return (
            f'<div class="sh-big" style="position:absolute;left:0;top:{BIG_NUMBER_TOP}px;width:{FRAME_W}px;'
            f"height:{BIG_NUMBER_PX}px;line-height:{BIG_NUMBER_PX}px;text-align:center;font-size:{BIG_NUMBER_PX}px;"
            f'font-weight:700;color:{ACCENT};white-space:nowrap;opacity:0;">{_esc(text)}</div>'
            f'<div class="sh-noun" style="position:absolute;left:0;top:{NOUN_TOP}px;width:{FRAME_W}px;'
            'text-align:center;font-size:32px;font-weight:400;line-height:1.2;color:#e6edf3;'
            f'white-space:nowrap;">{_esc(fig["label"])}</div>'
        )
    top_value = max(f["value"] for f in figures) or 1.0
    rows = []
    for i, fig in enumerate(figures):
        pct = max(MIN_BAR_FRACTION, fig["value"] / top_value) * 100
        rows.append(
            f'<div class="sh-row sh-row-{i}" style="position:absolute;left:0;top:{ROW_TOPS[i]}px;'
            f'width:{FRAME_W}px;height:40px;opacity:0.35;">'
            f'<span style="position:absolute;left:200px;top:0;width:360px;height:40px;line-height:40px;'
            "font-size:28px;font-weight:700;color:#e6edf3;white-space:nowrap;overflow:hidden;"
            f'">{_esc(fig["label"])}</span>'
            f'<span style="position:absolute;left:600px;top:0;width:960px;height:40px;box-sizing:border-box;'
            'border:2px solid #8b949e;">'
            f'<span class="sh-fill" style="position:absolute;left:0;top:0;height:100%;width:{pct:.2f}%;'
            f'background:{ACCENT};transform-origin:left center;transform:scaleX(0);"></span></span>'
            f'<span class="sh-value" style="position:absolute;left:1580px;top:0;height:40px;line-height:40px;'
            f'font-size:28px;font-weight:700;color:#e6edf3;white-space:nowrap;opacity:0;">{_esc(fig["text"])}</span>'
            "</div>"
        )
    return "".join(rows)


def _statement_body(sentences: list[str]) -> str:
    name = glyph_for(sentences[0]) if sentences else DEFAULT_GLYPH
    return (
        f'<div class="sh-ring" style="position:absolute;left:{STMT_RING_LEFT}px;top:{STMT_RING_TOP}px;'
        f"width:{STMT_RING_PX}px;height:{STMT_RING_PX}px;box-sizing:border-box;border-radius:50%;"
        f'border:2px solid {ACCENT};"></div>'
        f'<div class="sh-node sh-node-0" style="position:absolute;left:{STMT_TILE_LEFT}px;top:{STMT_TILE_TOP}px;'
        f"width:{STMT_TILE_PX}px;height:{STMT_TILE_PX}px;box-sizing:border-box;border-radius:32px;"
        "background:#0d1117;border:2px solid #30363d;color:#ffffff;display:flex;align-items:center;"
        f'justify-content:center;opacity:0;">{_glyph_svg(name)}</div>'
    )


def shot_tween_js(scene_sel: str, k: int, shot: dict, abs_start: float) -> str:
    """Return GSAP lines that animate the shot in slot k of one scene.

    scene_sel is a selector such as "#scene-0". abs_start is the time, on the timeline the lines
    are added to, at which the shot starts. shot needs "type", a length ("length", or end_s minus
    start_s) and "count" (see shot_count). Only opacity, transform and strokeDashoffset tween.
    """
    slot = f"{scene_sel} .shot-slot-{k}"
    kind = shot["type"]
    length = _shot_length(shot)
    count = int(shot.get("count", 1))
    s = abs_start
    spring = f"ease: {SPRING_EASE_JS}"
    lines = [
        f'tl.fromTo({json.dumps(slot + " .sh-title")}, {{opacity: 0, y: 24}}, '
        f"{{opacity: 1, y: 0, duration: 0.5, {spring}}}, {s + 0.1:.3f});",
        f'tl.fromTo({json.dumps(slot + " .sh-sub")}, {{opacity: 0, y: 24}}, '
        f"{{opacity: 1, y: 0, duration: 0.5, {spring}}}, {s + 0.3:.3f});",
        f'tl.fromTo({json.dumps(slot + " .sh-panel")}, {{opacity: 0}}, '
        f"{{opacity: 1, duration: 0.4, {spring}}}, {s + 0.1:.3f});",
        f'tl.fromTo({json.dumps(slot + " .shot-stage")}, {{scale: 1}}, '
        f'{{scale: 1.04, duration: {length:.3f}, ease: "none"}}, {s:.3f});',
    ]
    if kind == "diagram":
        for i in range(count):
            tile_start = s + 0.5 + 0.6 * i
            lines.append(
                f'tl.fromTo({json.dumps(f"{slot} .sh-node-{i}")}, {{scale: 0.6, opacity: 0}}, '
                f'{{scale: 1, opacity: 1, duration: 0.5, {spring}}}, {tile_start:.3f});'
            )
            lines.append(
                f'tl.fromTo({json.dumps(f"{slot} .sh-label-{i}")}, {{opacity: 0}}, '
                f"{{opacity: 1, duration: 0.3}}, {tile_start + 0.3:.3f});"
            )
            if i < count - 1:
                lines.append(
                    f'tl.fromTo({json.dumps(f"{slot} .sh-edge-{i}")}, {{strokeDashoffset: 1}}, '
                    f"{{strokeDashoffset: 0, duration: 0.5}}, {tile_start + 0.4:.3f});"
                )
    elif kind == "data":
        if count == 1:
            lines.append(
                f'tl.fromTo({json.dumps(slot + " .sh-big")}, {{scale: 0.8, opacity: 0}}, '
                f"{{scale: 1, opacity: 1, duration: 0.6, {spring}}}, {s + 0.4:.3f});"
            )
        else:
            for i in range(count):
                row_start = s + 0.5 + 0.5 * i
                row = json.dumps(f"{slot} .sh-row-{i}")
                lines.append(
                    f'tl.fromTo({json.dumps(f"{slot} .sh-row-{i} .sh-fill")}, {{scaleX: 0}}, '
                    f"{{scaleX: 1, duration: 0.8}}, {row_start:.3f});"
                )
                lines.append(
                    f'tl.fromTo({json.dumps(f"{slot} .sh-row-{i} .sh-value")}, {{opacity: 0}}, '
                    f"{{opacity: 1, duration: 0.3}}, {row_start + 0.5:.3f});"
                )
                lines.append(
                    f"tl.fromTo({row}, {{opacity: 0.35}}, {{opacity: 1, duration: 0.2}}, {row_start:.3f});"
                )
                if i < count - 1:
                    lines.append(
                        f"tl.to({row}, {{opacity: 0.35, duration: 0.2}}, {row_start + 0.5:.3f});"
                    )
    elif kind == "statement":
        lines.append(
            f'tl.fromTo({json.dumps(slot + " .sh-node-0")}, {{scale: 0.8, opacity: 0}}, '
            f"{{scale: 1, opacity: 1, duration: 0.6, {spring}}}, {s + 0.4:.3f});"
        )
        lines.append(
            f'tl.fromTo({json.dumps(slot + " .sh-ring")}, {{scale: 0.9}}, '
            f"{{scale: 1, duration: 0.6}}, {s + 0.6:.3f});"
        )
    else:
        raise ValueError(f"unknown shot type: {kind!r}")
    return "\n".join(lines)


def shot_html(shot: dict, width: int = FRAME_W, height: int = SHOT_ZONE_H, caption: str | None = None) -> str:
    """Return one <div class="shot shot-<type>"> fragment for a split_scene shot.

    shot is one entry from split_scene. caption is the scene's narration text (defaults to the
    shot's own sentences); the heading never repeats it. Inline <style> rules are scoped to the
    shot class. Animated elements carry .sh-* classes and start hidden inline; shot_tween_js
    reveals them on the scene timeline. No CSS keyframes. All user text is HTML-escaped.
    """
    kind = shot["type"]
    sentences = list(shot["sentences"])
    caption_text = " ".join(sentences) if caption is None else caption
    heading, subline = _heading_and_subline(sentences, kind, caption_text)
    if kind == "diagram":
        css, body = _DIAGRAM_CSS, _diagram_body(sentences)
    elif kind == "data":
        css, body = "", _data_body(sentences)
    elif kind == "statement":
        css, body = _STATEMENT_CSS, _statement_body(sentences)
    else:
        raise ValueError(f"unknown shot type: {kind!r}")
    style = f"position:relative;width:{width}px;height:{height}px;"
    stage = (
        '<div class="sh-stage shot-stage" style="position:absolute;left:0;top:0;'
        f'width:{FRAME_W}px;height:{SHOT_ZONE_H}px;">'
        f"{_panel_html()}{body}</div>"
    )
    return (
        f'<div class="shot shot-{kind}" style="{style}">'
        f"<style>{_COMMON_CSS}{css}</style>{_heading_html(heading, subline)}{stage}</div>"
    )
