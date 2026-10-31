#!/usr/bin/env python3
"""Raw talking clip -> finished 9:16 short, all inside the video-editor image.

Usage: vedit <clip.mp4> [--out name] [--no-music]
Steps: ffmpeg audio extract -> whisper.cpp word timestamps -> compose_intro.py (sentence cuts, push-in zoom,
blurred bars, word captions) -> make_score.py mix (ducked synthesized score). Output lands in /work/Render.
Relative clip names are looked up in /work/Raw.
"""
import argparse
import os
import subprocess
import sys

SCRIPTS = "/opt/pipeline"
NO_SPEECH = "WARNING: no speech detected, no captions"


def count_words(path):
    """Number of word tokens in whisper-cli -oj output (blank and [MARKER] tokens do not count)."""
    import json
    import re
    try:
        segs = json.load(open(path, encoding="utf-8")).get("transcription", [])
    except (OSError, ValueError):
        return 0
    return sum(1 for s in segs if not s.get("text", "").strip().startswith("[") and re.search(r"\w", s.get("text", "")))


def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit(f"step failed ({r.returncode}): {cmd[0]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-music", action="store_true")
    a = ap.parse_args()
    clip = a.clip if os.path.isabs(a.clip) else os.path.join("/work/Raw", a.clip)
    name = a.out or os.path.splitext(os.path.basename(clip))[0] + "-short"
    render = "/work/Render"
    tmp = "/tmp/vedit"
    os.makedirs(tmp, exist_ok=True)
    for d in ("Raw", "References", "Render"):
        os.makedirs(f"/work/{d}", exist_ok=True)
    wav, words = f"{tmp}/a.wav", f"{tmp}/words"
    run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-vn", "-ar", "16000", "-ac", "1", wav])
    run(["whisper-cli", "-m", os.environ["WHISPER_MODEL_PATH"], "-f", wav, "-oj", "-ml", "1", "-sow", "-of", words, "-np"])
    no_speech = count_words(words + ".json") == 0
    if no_speech:
        # Exit code stays 0 on purpose: the output is still written, just without captions.
        print(NO_SPEECH, file=sys.stderr, flush=True)
    composed = f"{render}/{name}{'' if a.no_music else '.nomusic'}.mp4"
    run([sys.executable, f"{SCRIPTS}/compose_intro.py", clip, "-", composed, "ffmpeg", "--words", words + ".json"])
    if not a.no_music:
        final = f"{render}/{name}.mp4"
        run([sys.executable, f"{SCRIPTS}/make_score.py", "mix", composed, final, "ffmpeg"])
        os.remove(composed)
    print("done ->", render + (f" ({NO_SPEECH})" if no_speech else ""), flush=True)


if __name__ == "__main__":
    main()
