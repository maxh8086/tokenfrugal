"""Print or record this machine's hardware so results stay comparable.

    python Benchmark/script/hardware.py [--json]
"""
import json
import platform
import shutil
import subprocess
import sys


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""


def info():
    d = {"os": platform.platform(), "cpu": platform.processor() or platform.machine(),
         "python": platform.python_version(), "cores": None, "ram_gb": None,
         "gpu": "", "vram_gb": None, "ollama": ""}
    try:
        import psutil
        d["cores"] = psutil.cpu_count(logical=False)
        d["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        pass
    if shutil.which("nvidia-smi"):
        lines = _run(["nvidia-smi", "--query-gpu=name,memory.total",
                      "--format=csv,noheader,nounits"]).splitlines()
        if lines:
            name, mem = [x.strip() for x in lines[0].split(",")]
            d["gpu"], d["vram_gb"] = name, round(float(mem) / 1024)
    d["ollama"] = _run(["ollama", "--version"])
    d["id"] = f"{d['gpu'] or 'cpu-only'} {d['vram_gb'] or ''}GB".replace(" GB", "").strip()
    return d


if __name__ == "__main__":
    d = info()
    if "--json" in sys.argv:
        print(json.dumps(d, indent=2))
    else:
        print("\n".join(f"{k:8} {v}" for k, v in d.items()))
