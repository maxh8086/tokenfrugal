"""Run a kalamanch script after the model pre-check.

Usage: python kalamanch/run.py generators/generate_ltx.py <args...>
       python kalamanch/run.py pipeline/chain_gen.py ltx <photo> <audio.wav> <out.mp4>
Missing weights are listed with their size and you are asked before anything downloads.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "common"))
sys.path.insert(0, os.path.dirname(HERE))  # repo root, for router.gpu_lease
from _models import MODELS, require  # noqa: E402
from router import gpu_lease  # noqa: E402


def needed(script, args):
    key = script.replace("\\", "/")
    names = []
    for n, m in MODELS.items():
        for r in m["required_by"]:
            path, _, variant = r.partition(":")
            if path == key and (not variant or (args and args[0] == variant)):
                names.append(n)
    return names


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    script, args = sys.argv[1], sys.argv[2:]
    require(*needed(script, args))
    ollama = os.getenv("TF_OLLAMA_NATIVE_URL", "http://127.0.0.1:11434")
    try:  # every run starts a generator, so every run takes the GPU lease
        lease = gpu_lease.acquire("kalamanch", script, job_id=f"run-{os.getpid()}-{int(time.time())}", ollama_url=ollama)
    except gpu_lease.GpuError as e:
        print(f"GPU lease not taken: {e}", file=sys.stderr)
        return 1

    proc = subprocess.Popen([sys.executable, os.path.join(HERE, script), *args])

    def lost(e):
        print(f"GPU lease lost ({e}); stopping {script}", file=sys.stderr)
        proc.kill()

    stop = gpu_lease.start_heartbeat(lease, on_lost=lost)
    try:
        return proc.wait()
    finally:
        stop.set()
        try:
            gpu_lease.release(lease)
        except gpu_lease.GpuError as e:
            print(f"GPU lease not released: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
