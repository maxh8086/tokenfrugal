"""Neutral music bed for Mode B slice 1 (decision D10).

A quiet, steady C major pad: C3, E3, G3 sine partials under a slow 0.1 Hz
amplitude swell. No noise, no pulse, no rising pitch. Deterministic.

Usage:
    python -I make_bed.py [duration_s=25.0] [out_path=renders\\bed.wav]
"""
import os
import sys

import numpy as np
import soundfile as sf

SR = 48000
CHORD_HZ = (130.81, 164.81, 196.00)  # C3, E3, G3
PARTIAL_GAIN = (0.6, 0.5, 0.4)       # relative level per chord tone
SECOND_HARMONIC_GAIN = 0.15          # very low octave partial
SWELL_HZ = 0.1
SWELL_DEPTH = 0.3                    # swell runs 0.7 .. 1.0 of level
FADE_S = 2.0
PEAK = 0.25                          # full-scale peak before loudness step
DEFAULT_DURATION = 25.0
DEFAULT_OUT = os.path.join("renders", "bed.wav")


def make_bed(duration_s: float) -> np.ndarray:
    n = int(round(duration_s * SR))
    t = np.arange(n, dtype=np.float64) / SR

    mix = np.zeros(n, dtype=np.float64)
    for f, g in zip(CHORD_HZ, PARTIAL_GAIN):
        mix += g * np.sin(2.0 * np.pi * f * t)
        mix += g * SECOND_HARMONIC_GAIN * np.sin(2.0 * np.pi * 2.0 * f * t)

    swell = (1.0 - SWELL_DEPTH) + SWELL_DEPTH * 0.5 * (
        1.0 + np.sin(2.0 * np.pi * SWELL_HZ * t - np.pi / 2.0)
    )
    mix *= swell

    fade_n = min(int(round(FADE_S * SR)), n // 2)
    if fade_n > 0:
        ramp = np.linspace(0.0, 1.0, fade_n, endpoint=False)
        mix[:fade_n] *= ramp
        mix[n - fade_n:] *= ramp[::-1]

    peak = float(np.max(np.abs(mix)))
    if peak > 0.0:
        mix *= PEAK / peak
    return mix.astype(np.float64)


def main(argv):
    duration_s = float(argv[1]) if len(argv) > 1 else DEFAULT_DURATION
    out_path = argv[2] if len(argv) > 2 else DEFAULT_OUT
    if duration_s <= 0:
        raise SystemExit("duration must be positive")

    audio = make_bed(duration_s)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    sf.write(out_path, audio, SR, subtype="PCM_24")
    print(f"wrote {out_path}: {len(audio)} samples, {SR} Hz, mono, PCM_24")


if __name__ == "__main__":
    main(sys.argv)
