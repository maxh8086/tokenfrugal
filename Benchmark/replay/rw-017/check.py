"""Replay task rw-017: gateway/config.py loads optional gateway/config_overrides.json environment defaults (offline)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
SOURCE = os.path.join(ROOT, "gateway", "config.py")
KEYS = ["RW017_NEW", "RW017_PRESET", "RW017_OTHER"]
CHILD = "import json, os\nimport gateway.config\nprint(json.dumps({k: os.environ.get(k) for k in %r}))" % (KEYS,)


def fail(message):
    print("FAIL:", message)
    return 1


def scenario(tmp, pkg, override_text):
    path = os.path.join(pkg, "gateway", "config_overrides.json")
    if os.path.exists(path):
        os.remove(path)
    if override_text is not None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(override_text)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("TOKENFRUGAL_", "RW017_"))}
    env["MCP_ENV_FILE"] = os.path.join(tmp, "absent.env")
    env["RW017_PRESET"] = "keep"
    done = subprocess.run([sys.executable, "-c", CHILD], cwd=pkg, env=env, capture_output=True, text=True, timeout=120)
    if done.returncode != 0:
        return None, "child exited %d: %s" % (done.returncode, done.stderr.strip()[-300:])
    return json.loads(done.stdout.strip().splitlines()[-1]), ""


def main():
    tmp = tempfile.mkdtemp(prefix="rw017-")
    try:
        pkg = os.path.join(tmp, "pkg")
        os.makedirs(os.path.join(pkg, "gateway"))
        shutil.copyfile(SOURCE, os.path.join(pkg, "gateway", "config.py"))
        open(os.path.join(pkg, "gateway", "__init__.py"), "w").close()
        cases = [
            ("missing file", None, {"RW017_NEW": None, "RW017_PRESET": "keep"}),
            ("valid file", json.dumps({"env": {"RW017_NEW": "new-value", "RW017_OTHER": "7", "RW017_PRESET": "from-file"}}),
             {"RW017_NEW": "new-value", "RW017_OTHER": "7", "RW017_PRESET": "keep"}),
            ("invalid file", "{not json", {"RW017_NEW": None, "RW017_PRESET": "keep"}),
        ]
        for name, text, expected in cases:
            got, problem = scenario(tmp, pkg, text)
            if problem:
                return fail("%s: %s" % (name, problem))
            for key, want in expected.items():
                if got.get(key) != want:
                    return fail("%s: %s is %r, expected %r" % (name, key, got.get(key), want))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
