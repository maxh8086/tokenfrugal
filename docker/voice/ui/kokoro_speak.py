"""Kokoro speech helper for the voice UI. Runs under KOKORO_PYTHON (the Kokoro venv), not under the server's python.

  python kokoro_speak.py list    -> stdout: JSON {"voices": [...]}
  python kokoro_speak.py speak   -> stdin: JSON {"text": ..., "voice": ..., "speed": ...}; stdout: WAV (mono, 16-bit)

Exit codes: 0 ok, 2 bad request (message on stderr), 1 model or runtime failure (traceback on stderr).
Model files come from KOKORO_MODEL_PATH and KOKORO_VOICES_PATH, set in docker/voice/Dockerfile.
"""
import contextlib
import io
import json
import os
import sys
import wave

MAX_CHARS = 1000
SPEED_MIN, SPEED_MAX = 0.5, 2.0


class BadRequest(ValueError):
    pass


def validate(req, voices):
    """Return (text, voice, speed) or raise BadRequest. Pure: no model needed, so it is unit-tested directly."""
    text = str(req.get("text", "")).strip()
    if not text or len(text) > MAX_CHARS:
        raise BadRequest(f"text must be 1 to {MAX_CHARS} characters")
    voice = str(req.get("voice", ""))
    if voice not in voices:
        raise BadRequest(f"unknown voice: {voice!r}")
    try:
        speed = float(req.get("speed", 1.0))
    except (TypeError, ValueError):
        raise BadRequest("speed must be a number")
    if not SPEED_MIN <= speed <= SPEED_MAX:
        raise BadRequest(f"speed must be between {SPEED_MIN} and {SPEED_MAX}")
    return text, voice, speed


def lang_for(voice):
    """Kokoro voice ids start with the accent: b* is British English, a* is American."""
    return "en-gb" if voice.startswith("b") else "en-us"


def to_wav_bytes(samples, rate):
    import numpy as np

    pcm = (np.clip(np.asarray(samples, dtype="float32"), -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(int(rate))
        out.writeframes(pcm.tobytes())
    return buf.getvalue()


@contextlib.contextmanager
def native_stdout_to_stderr():
    """ONNX Runtime writes its provider banners to file descriptor 1 from C code, which corrupts the JSON or WAV
    on stdout. Point fd 1 at fd 2 while the model runs, then restore it."""
    sys.stdout.flush()
    saved = os.dup(1)
    os.dup2(2, 1)
    try:
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)


def main(argv):
    try:
        if argv not in (["list"], ["speak"]):
            raise BadRequest("usage: kokoro_speak.py list | speak")
        from kokoro_onnx import Kokoro

        with native_stdout_to_stderr():
            kokoro = Kokoro(os.environ["KOKORO_MODEL_PATH"], os.environ["KOKORO_VOICES_PATH"])
            voices = sorted(kokoro.get_voices())
        if argv == ["list"]:
            sys.stdout.write(json.dumps({"voices": voices}))
            return 0
        try:
            req = json.load(sys.stdin)
        except ValueError:
            raise BadRequest("body is not valid JSON")
        if not isinstance(req, dict):
            raise BadRequest("body must be a JSON object")
        text, voice, speed = validate(req, voices)
        with native_stdout_to_stderr():
            samples, rate = kokoro.create(text, voice=voice, speed=speed, lang=lang_for(voice))
        sys.stdout.buffer.write(to_wav_bytes(samples, rate))
        sys.stdout.buffer.flush()
        return 0
    except BadRequest as err:
        sys.stderr.write(f"error: {err}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
