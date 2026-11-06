#!/usr/bin/env python3
"""Raw talking clip -> finished 9:16 short, all inside the video-editor image.

Usage: mgen <clip.mp4> [--out name] [--no-music] [--captions auto|on|off]
Steps: ffmpeg audio extract -> whisper.cpp word timestamps -> compose_intro.py (sentence cuts, push-in zoom,
blurred bars, word captions) -> make_score.py mix (ducked synthesized score). Output lands in /work/Render.
Relative clip names are looked up in /work/Raw.

Clips without an audio stream, or whose audio is silent or has no words, are rendered without captions
(a WARNING line on stderr and in the done line) and exit 0. Whisper is not run on silent audio.

--captions auto (default) OCRs the lower 60 % of 8 evenly spaced frames with tesseract. If the clip already has
burned-in subtitles (2+ real words in at least 3 of the 8 frames) mgen adds no word captions and prints a NOTE; the
rest of the render is unchanged. on always adds word captions, off never does.
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
BURNED_NOTE = "NOTE: burned-in subtitles detected, skipping word captions"
OFF_NOTE = "NOTE: captions off, skipping word captions"
# Burned-in subtitle detection (--captions auto). Thresholds were measured on the reference clips and the clean
# speech clip, see the handoff report.
OCR_SAMPLES = 8           # evenly spaced frames per clip
# Lower 60 % of the frame, upscaled 3x before OCR. Measured: burned-in subtitles sit at about 45-55 % of the height
# on the reference clips (the lower 40 % missed them), and tesseract reads small subtitle text only at 3x.
OCR_CROP = "crop=iw:ih*0.6:0:ih*0.4,scale=iw*3:ih*3"
OCR_MIN_CONF = 60         # tesseract word confidence, 0-100
OCR_MIN_WORDS = 2         # real words in one frame for that frame to count as a subtitle frame
OCR_MIN_FRAMES = 3        # subtitle frames out of OCR_SAMPLES for the clip to count as burned-in
REAL_WORD = re.compile(r"[A-Za-z]{3,}[.,!?;:]?$")
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


def real_words(tsv):
    """Words from tesseract TSV output (word rows, level 5) with confidence >= OCR_MIN_CONF that look like words:
    3+ letters and a vowel. Noise such as "|", "l1" or "ii" is dropped."""
    out = []
    for row in tsv.splitlines()[1:]:
        f = row.split("\t")
        if len(f) < 12 or f[0] != "5":
            continue
        try:
            conf = float(f[10])
        except ValueError:
            continue
        w = f[11].strip()
        if conf >= OCR_MIN_CONF and REAL_WORD.match(w) and re.search(r"[aeiouyAEIOUY]", w):
            out.append(w)
    return out


def detect_burned_in(clip, tmp):
    """(is_burned_in, real-word count per sampled frame). Frames that fail to extract count as 0 words."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", clip],
                       capture_output=True, text=True)
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        return False, []
    png = os.path.join(tmp, "ocr-frame.png")
    counts = []
    for i in range(OCR_SAMPLES):
        t = dur * (i + 0.5) / OCR_SAMPLES
        f = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", clip, "-frames:v", "1", "-vf",
                            OCR_CROP, "-y", png], capture_output=True, text=True)
        if f.returncode or not os.path.exists(png):
            counts.append(0)
            continue
        o = subprocess.run(["tesseract", png, "stdout", "-l", "eng", "--psm", "6", "tsv"],
                           capture_output=True, text=True)
        counts.append(len(real_words(o.stdout)) if o.returncode == 0 else 0)
        os.remove(png)
    hits = sum(c >= OCR_MIN_WORDS for c in counts)
    return hits >= OCR_MIN_FRAMES, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--captions", choices=("auto", "on", "off"), default="auto",
                    help="word captions: auto skips them when the clip has burned-in subtitles (default), on always "
                         "adds them, off never adds them")
    a = ap.parse_args()
    clip = a.clip if os.path.isabs(a.clip) else os.path.join("/work/Raw", a.clip)
    name = a.out or os.path.splitext(os.path.basename(clip))[0] + "-short"
    # --out may come with the .mp4 suffix; the final path adds it, so strip it here to avoid name.mp4.mp4.
    if name.endswith(".mp4"):
        name = name[: -len(".mp4")]
    render = "/work/" + os.environ.get("VIDEO_EDITOR_RENDER_DIR", "Render")
    tmp = "/tmp/mgen"
    os.makedirs(tmp, exist_ok=True)
    for d in ("Raw", "References"):
        os.makedirs(f"/work/{d}", exist_ok=True)
    os.makedirs(render, exist_ok=True)
    wav, whisper_out, speech = f"{tmp}/a.wav", f"{tmp}/words", f"{tmp}/speech.json"
    notes = []
    if a.captions == "off":
        notes.append(OFF_NOTE)
    elif a.captions == "auto":
        burned, counts = detect_burned_in(clip, tmp)
        print(f"ocr: real words per sampled frame {counts} -> "
              f"{'burned-in subtitles' if burned else 'no burned-in subtitles'}", file=sys.stderr, flush=True)
        if burned:
            notes.append(BURNED_NOTE)
    if not has_audio(clip):
        # compose_intro.py maps the clip's audio, so give the picture a silent track. No whisper run.
        notes.append(NO_AUDIO)
        silent = f"{tmp}/silent-track.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-map", "0:v:0", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", silent])
        clip = silent
        write_words(speech, [])
    elif notes:
        # Captions are skipped (off, or burned-in subtitles): no whisper run, the picture renders without word captions.
        write_words(speech, [])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-vn", "-ar", "16000", "-ac", "1", wav])
        level = peak_db(wav)
        if level is None or level < SILENCE_DB:
            write_words(speech, [])
            notes.append(NO_SPEECH)
        else:
            run(["whisper-cli", "-m", os.environ["WHISPER_MODEL_PATH"], "-f", wav, "-oj", "-ml", "1", "-sow",
                 "-nth", NO_SPEECH_THOLD, "-of", whisper_out, "-np"])
            segs = speech_segments(whisper_out + ".json")
            write_words(speech, segs)
            if not segs:
                notes.append(NO_SPEECH)
    for n in notes:
        # Exit code stays 0 on purpose: the output is still written, just without captions.
        print(n, file=sys.stderr, flush=True)
    composed = f"{render}/{name}{'' if a.no_music else '.nomusic'}.mp4"
    run([sys.executable, f"{SCRIPTS}/compose_intro.py", clip, "-", composed, "ffmpeg", "--words", speech])
    if not a.no_music:
        final = f"{render}/{name}.mp4"
        run([sys.executable, f"{SCRIPTS}/make_score.py", "mix", composed, final, "ffmpeg"])
        os.remove(composed)
    print("done ->", render + (f" ({'; '.join(notes)})" if notes else ""), flush=True)


if __name__ == "__main__":
    main()
