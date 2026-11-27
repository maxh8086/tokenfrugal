"""Replay task fb-002: narrate() runs the Kokoro container and writes the WAV (subprocess.run mocked, offline)."""
import json
import os
import sys
import tempfile
import types
from unittest import mock

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

ARGV = ["docker", "run", "--rm", "-i", "maxh8086/voice:1",
        "/opt/venv-kokoro/bin/python", "/opt/voice-ui/kokoro_speak.py", "speak"]
WAV = b"RIFF\x00\x00\x00\x00WAVEfake"


def fail(message):
    print("FAIL:", message)
    return 1


def result(returncode, stdout=b"", stderr=b""):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def run_narrate(sf, fake, *args, **kwargs):
    calls = []

    def recorder(argv, **kw):
        calls.append((argv, kw))
        return fake

    with mock.patch("subprocess.run", side_effect=recorder):
        sf.narrate(*args, **kwargs)
    return calls


def sent_payload(kw):
    payload = kw.get("input")
    if not isinstance(payload, bytes):
        raise AssertionError("input is not bytes")
    return json.loads(payload.decode("utf-8"))


def main():
    try:
        import scripts.story_film as sf
    except Exception as exc:
        return fail("cannot import scripts.story_film: %r" % (exc,))
    if not callable(getattr(sf, "narrate", None)):
        return fail("narrate is not callable")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.wav")
        try:
            calls = run_narrate(sf, result(0, WAV), "Hello there.", out)
        except Exception as exc:
            return fail("narrate raised %r on success" % (exc,))
        if len(calls) != 1:
            return fail("expected one subprocess.run call, got %d" % len(calls))
        argv, kw = calls[0]
        if list(argv) != ARGV:
            return fail("argv is %r" % (list(argv),))
        if kw.get("capture_output") is not True:
            return fail("capture_output is not True")
        if kw.get("check") is not False:
            return fail("check is not False")
        try:
            decoded = sent_payload(kw)
        except Exception as exc:
            return fail("stdin JSON unreadable: %r" % (exc,))
        if decoded != {"text": "Hello there.", "voice": "am_michael", "speed": 1.0}:
            return fail("default stdin JSON is %r" % (decoded,))
        with open(out, "rb") as handle:
            if handle.read() != WAV:
                return fail("out_wav does not hold the stdout bytes")

        out2 = os.path.join(tmp, "out2.wav")
        calls = run_narrate(sf, result(0, WAV), "Hi", out2, voice="af_bella", speed=1.25)
        if len(calls) != 1 or sent_payload(calls[0][1]) != {"text": "Hi", "voice": "af_bella", "speed": 1.25}:
            return fail("explicit voice and speed are not sent as given")

        err_out = os.path.join(tmp, "err.wav")
        try:
            run_narrate(sf, result(1, b"", b"loading model\nboom: last line\n"), "Hi", err_out)
        except RuntimeError as exc:
            message = str(exc)
            if "boom: last line" not in message:
                return fail("RuntimeError does not carry the last stderr line: %r" % (message,))
            if "loading model" in message:
                return fail("RuntimeError carries an earlier stderr line: %r" % (message,))
        except Exception as exc:
            return fail("non-zero exit raised %r, expected RuntimeError" % (exc,))
        else:
            return fail("non-zero exit did not raise")
        if os.path.exists(err_out):
            return fail("out_wav was written after a failed run")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
