"""Offline replay acceptance check. Run from the task worktree."""
import os
import sys
from pathlib import Path

for key in list(os.environ):
    if key.startswith("TOKENFRUGAL_"):
        del os.environ[key]
sys.dont_write_bytecode = True
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import ast
import io
import json
from unittest.mock import patch

scripts = ROOT / "Benchmark/script"
sys.path.insert(0, str(scripts))
fields = "quant file_gb num_ctx max_ctx vram_gb cpu_offload_pct ctx_used_pct ctx_free_tokens".split()
host = "http://localhost:11434"
gib = 2**30
running = [{"model": "sample:latest", "size": 2*gib, "size_vram": gib//2, "context_length": 512}]


def reply(request, data=None, timeout=None, **kwargs):
    url = getattr(request, "full_url", request)
    assert timeout == 5
    if url == host + "/api/show":
        assert json.loads(getattr(request, "data", None) or data) == {"model": "sample"}
        payload = {"details": {"quantization_level": "Q4"}, "model_info": {"x.context_length": 4096},
                   "parameters": "temperature 1\nnum_ctx 256"}
    elif url == host + "/api/ps":
        payload = {"models": running}
    elif url == host + "/api/tags":
        payload = {"models": [{"name": "sample:latest", "size": 3*gib}]}
    else:
        raise AssertionError(url)
    return io.BytesIO(json.dumps(payload).encode())


with patch("urllib.request.urlopen", side_effect=reply) as network:
    import modelinfo
    assert modelinfo.info("sample", host + "/v1/", 64) == dict(zip(fields, ["Q4", 2, 512, 4096, 0.5, 75, 12.5, 448]))
    running.clear()
    assert modelinfo.info("sample", host) == dict(zip(fields, ["Q4", 3, 256, 4096, "", "", "", ""]))
    network.side_effect = OSError("offline")
    assert modelinfo.info("sample", host) == dict.fromkeys(fields, "")

tree = ast.parse((scripts / "run_benchmark.py").read_text(encoding="utf-8"))
assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "META" for t in n.targets))
meta = ast.literal_eval(assignment.value)
assert meta[meta.index("tokens_out_per_run")+1:] == fields
