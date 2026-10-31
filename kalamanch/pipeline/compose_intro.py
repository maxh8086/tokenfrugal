"""Turn a lip-synced talking clip into a produced 9:16 short: sentence cuts, slow push-in, blurred bars, word captions.

Usage: python kalamanch/pipeline/compose_intro.py <talking.mp4> <script.txt> <out.mp4> [ffmpeg] [--words whisper.json]
The clip must carry the narration audio. Word times are estimated from the speech/pause pattern of that audio
(characters per word over the voiced time), so no speech-recognition model is needed. With --words (whisper-cli
-oj --max-len 1 --split-on-word output) the real word times are used and the script file may be "-".
Zoom levels alternate per sentence (wide, close, mid) so one clip still reads as several shots.
"""
import os
import re
import subprocess
import sys
import tempfile

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _publish import publish

W, H, FPS = 1080, 1920, 30
ZOOMS = [1.0, 1.22, 1.1]
PUSH = 0.05  # extra zoom reached by the end of each cut


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def voiced_spans(ff, media, total):
    log = run([ff, "-i", media, "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"]).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    spans, cur = [], 0.0
    for i, s in enumerate(starts):
        if s > cur:
            spans.append((cur, s))
        cur = ends[i] if i < len(ends) else total
    if cur < total:
        spans.append((cur, total))
    return [(a, b) for a, b in spans if b - a > 0.05]


def duration(ff, media):
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", run([ff, "-i", media]).stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def source_size(ff, media):
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", run([ff, "-i", media]).stderr)
    return int(m[1]), int(m[2])


def whisper_words(path):
    import json
    out = []
    for seg in json.load(open(path, encoding="utf-8"))["transcription"]:
        t = seg["text"].strip()
        if not t or t.startswith("["):
            continue
        a, b = seg["offsets"]["from"] / 1000, seg["offsets"]["to"] / 1000
        if out and not re.search(r"\w", t):
            out[-1] = (out[-1][0] + t, out[-1][1], out[-1][2])
        elif out and not seg["text"].startswith(" ") and re.search(r"\w", t):
            out[-1] = (out[-1][0] + t, out[-1][1], b)
        else:
            out.append((t, a, b))
    return out


def word_times(words, spans):
    voiced = sum(b - a for a, b in spans)
    weights = [len(re.sub(r"\W", "", w)) + 1 for w in words]
    scale = voiced / sum(weights)
    out, acc = [], 0.0
    for w, wt in zip(words, weights):
        out.append((w, acc, acc + wt * scale))
        acc += wt * scale
    mapped = []
    for w, a, b in out:
        mapped.append((w, to_real(a, spans), to_real(b, spans, end=True)))
    return mapped


def to_real(v, spans, end=False):
    for a, b in spans:
        length = b - a
        if v < length or (end and v <= length):
            return a + v
        v -= length
    return spans[-1][1]


def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def write_ass(path, timed):
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\n\n[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
            "Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,"
            "MarginV,Encoding\nStyle: W,Arial Black,110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,"
            "0,0,1,9,2,2,40,40,230,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,"
            "Effect,Text\n") % (W, H)
    with open(path, "w", encoding="utf-8") as f:
        f.write(head)
        for i, (w, a, b) in enumerate(timed):
            end = timed[i + 1][1] if i + 1 < len(timed) and timed[i + 1][1] - b < 0.4 else b
            text = re.sub(r"[^\w'-]", "", w).upper()
            f.write(f"Dialogue: 0,{ass_time(a)},{ass_time(end)},W,,0,0,0,,{text}\n")


def main():
    args = sys.argv[1:]
    words_json = args.pop(args.index("--words") + 1) if "--words" in args else None
    if words_json:
        args.remove("--words")
    clip, script, out = args[:3]
    ff = args[3] if len(args) > 3 else "ffmpeg"
    total = duration(ff, clip)
    sw, sh = source_size(ff, clip)
    fg_h = int(W * sh / sw) // 2 * 2
    if words_json:
        timed = whisper_words(words_json)
        sentences, cur = [], []
        # whisper often drops sentence punctuation and its word ends touch the next start,
        # so a detected silence also ends a sentence
        pauses = [spans_[0] for spans_ in voiced_spans(ff, clip, total)[1:]]
        for i, (w, a_, b_) in enumerate(timed):
            cur.append(w)
            nxt = timed[i + 1][1] if i + 1 < len(timed) else None
            if re.search(r"[.!?]$", w) or (nxt is not None and any(b_ - 0.15 <= p_ <= nxt + 0.15 for p_ in pauses)):
                sentences.append(" ".join(cur))
                cur = []
        if cur:
            sentences.append(" ".join(cur))
    else:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", open(script, encoding="utf-8").read().strip()) if s.strip()]
        words = [w for s in sentences for w in s.split()]
        timed = word_times(words, voiced_spans(ff, clip, total))
    cuts, i = [0.0], 0
    for s in sentences[:-1]:
        i += len(s.split())
        cuts.append(timed[i][1] - 0.05)
    cuts.append(total)

    tmp = tempfile.mkdtemp()
    ass = os.path.join(tmp, "cap.ass")
    write_ass(ass, [t for t in timed if re.sub(r"\W", "", t[0])])
    parts = []
    for k in range(len(cuts) - 1):
        a, b = cuts[k], cuts[k + 1]
        z0 = ZOOMS[k % len(ZOOMS)]
        frames = max(1, round((b - a) * FPS))
        zoom = f"{z0}+{PUSH}*on/{frames}"
        parts.append(
            f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps={FPS},scale=2160:-2,"
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih*0.38-(ih/zoom*0.38)':d=1:s={W}x{fg_h}:fps={FPS}[f{k}]")
    n = len(cuts) - 1
    graph = ";".join(parts) + ";" + "".join(f"[f{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=0[fg];"
    graph += (f"[0:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:5,"
              f"eq=brightness=-0.08[bg0];[bg0]trim=0:{total:.3f},setpts=PTS-STARTPTS[bg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[v0];[v0]subtitles={os.path.basename(ass)}[v]")
    cmd = [ff, "-y", "-v", "error", "-i", os.path.abspath(clip), "-filter_complex", graph, "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", os.path.abspath(out)]
    r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stderr[-1500:])
    print("wrote", out, f"{n} cuts, {len(timed)} words", flush=True)
    publish(out)


if __name__ == "__main__":
    main()
