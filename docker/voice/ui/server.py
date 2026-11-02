"""Voice profile UI server: record or upload a reference clip, save it with a consent note, list profiles.

Standard library only. The container sets VOICE_UI_HOST=0.0.0.0 so the published port works; the host publishes it
on 127.0.0.1 only. Recording uses the browser's MediaRecorder, which works on localhost without HTTPS.
"""
import base64
import binascii
import datetime
import http.server
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
PROFILE_DIR = pathlib.Path(os.environ.get("VOICE_PROFILE_DIR", "/work/voices"))
HOST = os.environ.get("VOICE_UI_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOICE_UI_PORT", "8080"))
MAX_BODY = 25 * 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
NOTE_MAX = 500
EXT_BY_MIME = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav",
               "audio/mp4": "m4a"}


def list_profiles():
    profiles = []
    if PROFILE_DIR.is_dir():
        for meta in sorted(PROFILE_DIR.glob("*/profile.json")):
            try:
                profiles.append(json.loads(meta.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return profiles


def convert_to_wav(src, dst):
    """Re-encode the browser clip to 24 kHz mono WAV (the rate the converter expects)."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is not available in this image")
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "24000", str(dst)],
                   check=True, timeout=120)


def create_profile(req):
    name = str(req.get("name", "")).strip()
    note = str(req.get("consent_note", "")).strip()
    if not NAME_RE.match(name):
        return 400, {"error": "name must be 2-41 chars: lowercase letters, digits, - or _"}
    if req.get("consent_confirmed") is not True:
        return 400, {"error": "consent must be confirmed before a clip can be saved"}
    if not note or len(note) > NOTE_MAX:
        return 400, {"error": f"consent note is required (max {NOTE_MAX} chars)"}
    try:
        audio = base64.b64decode(req.get("audio_b64", ""), validate=True)
    except (binascii.Error, TypeError, ValueError):
        return 400, {"error": "audio_b64 is not valid base64"}
    if not audio:
        return 400, {"error": "no audio received"}

    folder = PROFILE_DIR / name
    if folder.exists():
        return 409, {"error": f"profile '{name}' already exists"}
    ext = EXT_BY_MIME.get(str(req.get("mime", "")).split(";")[0], "webm")
    folder.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw = pathlib.Path(tmp) / f"raw.{ext}"
            raw.write_bytes(audio)
            convert_to_wav(raw, folder / "clip.wav")
    except (RuntimeError, subprocess.SubprocessError, OSError) as err:
        shutil.rmtree(folder, ignore_errors=True)
        return 500, {"error": f"could not convert the clip: {err}"}

    profile = {
        "name": name,
        "clip": "clip.wav",
        "source": str(req.get("source", "unknown"))[:20],
        "consent_note": note,
        "consent_confirmed": True,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    (folder / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return 201, profile


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, payload):
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/profiles":
            self._send_json(200, {"profiles": list_profiles()})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._send_json(413, {"error": "request body missing or larger than 25 MB"})
            return
        try:
            req = json.loads(self.rfile.read(length))
        except ValueError:
            self._send_json(400, {"error": "body is not valid JSON"})
            return

        if self.path == "/api/profiles":
            status, payload = create_profile(req)
            self._send_json(status, payload)
        elif self.path == "/api/speak":
            # Synthesis is not wired yet: it waits on the Kokoro / OpenVoice numpy decision in docker/voice/Dockerfile.
            self._send_json(501, {"error": "speech synthesis is not wired yet"})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with http.server.ThreadingHTTPServer((HOST, PORT), Handler) as server:
        print(f"voice UI on http://{HOST}:{PORT}  profiles in {PROFILE_DIR}", flush=True)
        server.serve_forever()
