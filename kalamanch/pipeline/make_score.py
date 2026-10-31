"""Synthesize a dramatic cinematic score with ffmpeg only (no model, no download) and optionally mix it under a narrated video.

Usage:
  python make_score.py score <seconds> <out.wav> [ffmpeg]
  python make_score.py mix <video.mp4> <out.mp4> [ffmpeg]   # score ducks under the narration (sidechain), video stream copied
Layers: detuned low drone with slow tremolo, pink-noise riser that swells to the end, soft sub pulse, hall echo.
"""
import re
import subprocess
import sys
import tempfile
import os

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _publish import publish


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stderr[-1500:])
    return r


def make_score(ff, seconds, out):
    d = seconds
    graph = ""
    for i, (a, f) in enumerate([(0.5, 55), (0.35, 82.5), (0.3, 110.4), (0.18, 164.8)]):
        graph += f"aevalsrc='{a}*sin(2*PI*{f}*t)*(0.8+0.2*sin(2*PI*0.18*t))':s=44100:d={d}[d{i}];"
    graph += "[d0][d1][d2][d3]amix=inputs=4:normalize=0,lowpass=f=900[drone];"
    graph += (f"anoisesrc=color=pink:d={d}:a=0.5,highpass=f=300,lowpass=f=3500,"
              f"volume='pow(t/{d},2.2)':eval=frame[riser];")
    graph += f"aevalsrc='0.9*sin(2*PI*48*t)*pow(max(0,sin(PI*t*0.8)),24)':s=44100:d={d}[pulse];"
    graph += ("[drone][riser][pulse]amix=inputs=3:weights=1 0.35 0.9:normalize=0,"
              "aecho=0.8:0.6:380|740:0.35|0.2,"
              f"afade=t=in:d=1.5,afade=t=out:st={d - 1.8}:d=1.8,loudnorm=I=-20:TP=-2[out]")
    run([ff, "-y", "-v", "error", "-filter_complex", graph, "-map", "[out]", "-ar", "44100", "-ac", "2", out])


def mix(ff, video, out):
    info = subprocess.run([ff, "-i", video], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    total = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    score = os.path.join(tempfile.mkdtemp(), "score.wav")
    make_score(ff, total, score)
    graph = ("[0:a]asplit=2[vo][sc_key];[1:a]volume=0.9[mus];"
             "[mus][sc_key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=500[ducked];"
             "[vo][ducked]amix=inputs=2:weights=1 0.85:normalize=0,alimiter=limit=0.95[a]")
    run([ff, "-y", "-v", "error", "-i", video, "-i", score, "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out])
    print("wrote", out, flush=True)
    publish(out)


if __name__ == "__main__":
    ff = sys.argv[-1] if sys.argv[-1].lower().endswith("ffmpeg.exe") or sys.argv[-1] == "ffmpeg" else "ffmpeg"
    if sys.argv[1] == "score":
        make_score(ff, float(sys.argv[2]), sys.argv[3])
        print("wrote", sys.argv[3], flush=True)
        publish(sys.argv[3])
    elif sys.argv[1] == "mix":
        mix(ff, sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
