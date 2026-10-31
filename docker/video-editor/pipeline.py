#!/usr/bin/env python3
"""Raw talking clip -> finished 9:16 short, all inside the video-editor image.

Usage: vedit <clip.mp4> [--out name] [--no-music]
Steps: ffmpeg audio extract -> whisper.cpp word timestamps -> compose_intro.py (sentence cuts, push-in zoom,
blurred bars, word captions) -> make_score.py mix (ducked synthesized score). Output lands in /work/Render.
Relative clip names are looked up in /work/Raw.

Clips without an audio stream, or whose audio is silent or has no words, are rendered without captions
(a WARNING line on stderr and in the done line) and exit 0. Whisper is not run on silent audio.
"""
import argparse
import json
import os
import re
import subprocess
import sys

SCRIPTS = "/opt/pipeline"
NO_SPEECH = "WARNING: no speech detected, no captions"
NO_AUDIO = "WARNING: no audio stream, no captions"
# Peak level below this (dBFS) counts as silence. Measured: digital silence -91 dB, white noise at -49 dB
# (whisper: [BLANK_AUDIO]), real speech -0.3 dB.
SILENCE_DB = -50.0
# whisper-cli no-speech probability threshold (its default is 0.60). Measured: it does not change the result on
# the test clips; the energy gate and the non-speech token filter do the work.
NO_SPEECH_THOLD = "0.9"


def speech_segments(path):
    """whisper-cli -oj segments that are recognised speech.

    Non-speech notes such as [BLANK_AUDIO] or (upbeat music) are dropped, including notes that whisper splits
    over several tokens ("(upbeat" then " music)")."""
    try:
        segs = json.load(open(path, encoding="utf-8")).get("transcription", [])
    except (OSError, ValueError):
        return []
    out, closer = [], None
    for s in segs:
        t = s.get("text", "").strip()
        if closer is not None:
            if t.endswith(closer):
                closer = None
            continue
        if t[:1] in ("[", "("):
            close = "]" if t[0] == "[" else ")"
            if not t.endswith(close):
                closer = close
            continue
        if re.search(r"\w", t):
            out.append(s)
    return out


def write_words(path, segs):
    """Whisper-shaped json; compose_intro.py reads it. An empty list renders the picture without captions."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"transcription": segs}, f)


def has_audio(clip):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "csv=p=0", clip], capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() != ""


def peak_db(wav):
    """Peak level in dBFS from ffmpeg volumedetect; None when the file has no samples."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"max_volume: (-?[\d.]+) dB", r.stderr)
    return float(m[1]) if m else None


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
    wav, whisper_out, speech = f"{tmp}/a.wav", f"{tmp}/words", f"{tmp}/speech.json"
    status = None
    if not has_audio(clip):
        # compose_intro.py maps the clip's audio, so give the picture a silent track. No whisper run.
        status = NO_AUDIO
        silent = f"{tmp}/silent-track.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-map", "0:v:0", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", silent])
        clip = silent
        write_words(speech, [])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-vn", "-ar", "16000", "-ac", "1", wav])
        level = peak_db(wav)
        if level is None or level < SILENCE_DB:
            write_words(speech, [])
            status = NO_SPEECH
        else:
            run(["whisper-cli", "-m", os.environ["WHISPER_MODEL_PATH"], "-f", wav, "-oj", "-ml", "1", "-sow",
                 "-nth", NO_SPEECH_THOLD, "-of", whisper_out, "-np"])
            segs = speech_segments(whisper_out + ".json")
            write_words(speech, segs)
            if not segs:
                status = NO_SPEECH
    if status:
        # Exit code stays 0 on purpose: the output is still written, just without captions.
        print(status, file=sys.stderr, flush=True)
    composed = f"{render}/{name}{'' if a.no_music else '.nomusic'}.mp4"
    run([sys.executable, f"{SCRIPTS}/compose_intro.py", clip, "-", composed, "ffmpeg", "--words", speech])
    if not a.no_music:
        final = f"{render}/{name}.mp4"
        run([sys.executable, f"{SCRIPTS}/make_score.py", "mix", composed, final, "ffmpeg"])
        os.remove(composed)
    print("done ->", render + (f" ({status})" if status else ""), flush=True)


if __name__ == "__main__":
    main()
