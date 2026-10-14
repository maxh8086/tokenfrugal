#!/usr/bin/env python3
"""Render bench/results.json into two hand-written SVG charts (stdlib only).

Outputs:
  bench/persona_scores.svg        per-persona grouped horizontal bars
  bench/params_vs_realworld.svg   parameters vs real-world passes scatter
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = REPO_ROOT / "bench" / "results.json"
PERSONA_SVG = REPO_ROOT / "bench" / "persona_scores.svg"
SCATTER_SVG = REPO_ROOT / "bench" / "params_vs_realworld.svg"

PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
BG = "#ffffff"
TEXT = "#222222"
GREY = "#777777"
GRID = "#dddddd"
THRESH = "#444444"
FONT = 'font-family="Arial, Helvetica, sans-serif"'


def load_results() -> dict:
    with RESULTS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def text(x: float, y: float, s: str, size: int = 12, anchor: str = "start",
         weight: str = "normal", fill: str = TEXT) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}" fill="{fill}">{escape(s)}</text>')


def persona_svg(data: dict) -> str:
    tags = [run["tag"] for run in data["runs"]]
    colors = {tag: PALETTE[i % len(PALETTE)] for i, tag in enumerate(tags)}
    personas = data["personas"]

    max_score = max([3] + [max(p["scores"].values(), default=0) for p in personas.values()])
    left = 330
    px_per = 360.0 / max_score
    row_h = 16
    title_h = 22
    group_pad = 14
    width = int(left + max_score * px_per + 90)

    body: list[str] = []
    y = 40.0
    for name, p in personas.items():
        default = p["default"] or "none"
        body.append(text(12, y + 14, name, 13, weight="bold"))
        body.append(text(left, y + 14, f"best {p['best']}  threshold {p['threshold']:g}  default {default}",
                         11, fill=GREY))
        bars_top = y + title_h
        bars_bottom = bars_top + len(tags) * row_h
        body.append(f'<line x1="{left}" y1="{bars_top:.1f}" x2="{left}" y2="{bars_bottom:.1f}" '
                    f'stroke="{GRID}" stroke-width="1"/>')
        for i, tag in enumerate(tags):
            by = bars_top + i * row_h
            score = p["scores"].get(tag, 0)
            label = f"{tag}*" if tag == p["default"] else tag
            body.append(text(left - 8, by + 11, label, 11, anchor="end"))
            if score:
                body.append(f'<rect x="{left}" y="{by + 2:.1f}" width="{score * px_per:.1f}" '
                            f'height="{row_h - 4}" fill="{colors[tag]}"/>')
            body.append(text(left + score * px_per + 4, by + 11, str(score), 11))
        tx = left + p["threshold"] * px_per
        body.append(f'<line x1="{tx:.1f}" y1="{bars_top - 2:.1f}" x2="{tx:.1f}" y2="{bars_bottom + 2:.1f}" '
                    f'stroke="{THRESH}" stroke-width="1.5" stroke-dasharray="4,3"/>')
        y = bars_bottom + group_pad

    height = int(y + 36)
    footer = ("* default tag. Dashed line = threshold (0.75 x best). "
              "Bar length = verified passes over the persona's cases.")
    body.append(text(12, y + 14, footer, 11, fill=GREY))
    head = [text(12, 22, "Verified passes per persona, by model", 15, weight="bold")]

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" {FONT}>',
           f'<rect width="{width}" height="{height}" fill="{BG}"/>']
    out += head + body
    out.append("</svg>")
    return "\n".join(out) + "\n"


def scatter_svg(data: dict) -> str:
    runs = data["runs"]
    total = runs[0]["realworld_total"]
    width, height = 720, 520
    x0, x1 = 90.0, 680.0   # plot left/right
    y0, y1 = 440.0, 60.0   # plot bottom (0 passes) / top (total passes)

    def px(params: float) -> float:
        return x0 + (params - 1.0) / 8.0 * (x1 - x0)

    def py(passes: float) -> float:
        return y0 + passes / total * (y1 - y0)

    label_dy = {"prism-bonsai-8b-q1": -10, "prism-ternary-8b-q2": 18}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" {FONT}>',
           f'<rect width="{width}" height="{height}" fill="{BG}"/>',
           text(width / 2, 26, f"Parameters vs real-world passes (of {total})", 15, "middle", "bold")]

    for v in range(0, total + 1, 8):
        gy = py(v)
        out.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" stroke="{GRID}"/>')
        out.append(text(x0 - 8, gy + 4, str(v), 11, "end"))
    out.append(text(24, (y0 + y1) / 2, "real-world passes", 12, "middle"))
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{TEXT}"/>')
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{TEXT}"/>')

    for params, label in ((1.7, "1.7B"), (4, "4B"), (8, "8B")):
        out.append(f'<line x1="{px(params):.1f}" y1="{y0}" x2="{px(params):.1f}" y2="{y0 + 5}" stroke="{TEXT}"/>')
        out.append(text(px(params), y0 + 20, label, 11, "middle"))
    out.append(text((x0 + x1) / 2, y0 + 42, "parameters (billions)", 12, "middle"))

    for i, run in enumerate(runs):
        cx, cy = px(run["params"]), py(run["realworld_passes"])
        color = PALETTE[i % len(PALETTE)]
        dx, dy = 10, label_dy.get(run["tag"], 4)
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{color}"/>')
        out.append(text(cx + dx, cy + dy, f"{run['tag']} ({run['realworld_passes']})", 11))

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    data = load_results()
    PERSONA_SVG.write_text(persona_svg(data), encoding="utf-8")
    SCATTER_SVG.write_text(scatter_svg(data), encoding="utf-8")
    print(PERSONA_SVG)
    print(SCATTER_SVG)


if __name__ == "__main__":
    main()
