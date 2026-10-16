"""Model facts from a local Ollama server: quantization, file size, context window and VRAM/CPU split.

    python Benchmark/script/modelinfo.py <model> [endpoint]

Stdlib only. Any failure, or an endpoint that is not Ollama, returns every key blank ('').
"""
import json
import sys
import urllib.request

TIMEOUT = 5
DEFAULT_HOST = "http://localhost:11434"
KEYS = ("compression_level", "model_file_size_gb", "context_window_tokens", "model_max_context_tokens", "gpu_memory_used_gb", "shared_system_memory_gb")


def _call(url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _host(endpoint: str) -> str:
    e = (endpoint or "").strip().rstrip("/")
    if e.endswith("/v1"):
        e = e[:-3]
    e = e.rstrip("/")
    return e or DEFAULT_HOST


def _matches(entry: dict, model: str) -> bool:
    names = {entry.get("name"), entry.get("model")}
    return model in names or (model + ":latest") in names


def _gb(n) -> float:
    return round(n / 2**30, 2)


def info(model: str, endpoint: str, peak_tokens: int = 0) -> dict:
    out = {k: "" for k in KEYS}
    try:
        host = _host(endpoint)
        show = _call(host + "/api/show", {"model": model})
        out["compression_level"] = (show.get("details") or {}).get("quantization_level") or ""
        for key, val in (show.get("model_info") or {}).items():
            if key.endswith(".context_length") and isinstance(val, int) and not isinstance(val, bool):
                out["model_max_context_tokens"] = val
                break
        for line in (show.get("parameters") or "").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "num_ctx":
                out["context_window_tokens"] = int(parts[1])
                break

        ps = _call(host + "/api/ps")
        entry = next((m for m in ps.get("models") or [] if _matches(m, model)), None)
        if entry is not None:
            size = entry.get("size") or 0
            size_vram = entry.get("size_vram") or 0
            out["model_file_size_gb"] = _gb(size)
            out["gpu_memory_used_gb"] = _gb(size_vram)
            out["shared_system_memory_gb"] = _gb(max(size - size_vram, 0)) if size else ""
            if entry.get("context_length"):
                out["context_window_tokens"] = int(entry["context_length"])
        else:
            tags = _call(host + "/api/tags")
            tag = next((m for m in tags.get("models") or [] if _matches(m, model)), None)
            if tag is not None and tag.get("size"):
                out["model_file_size_gb"] = _gb(tag["size"])

    except Exception:  # noqa: BLE001
        return {k: "" for k in KEYS}
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: modelinfo.py <model> [endpoint]")
    print(json.dumps(info(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST), indent=2))
