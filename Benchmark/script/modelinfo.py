"""Model facts from a local Ollama server: quantization, file size, context window and VRAM/CPU split.

    python Benchmark/script/modelinfo.py <model> [endpoint]

Stdlib only. Any failure, or an endpoint that is not Ollama, returns every key blank ('').
"""
import json
import sys
import urllib.request

TIMEOUT = 5
DEFAULT_HOST = "http://localhost:11434"
KEYS = ("quant", "file_gb", "num_ctx", "max_ctx", "vram_gb", "cpu_offload_pct", "ctx_used_pct", "ctx_free_tokens")


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
        out["quant"] = (show.get("details") or {}).get("quantization_level") or ""
        for key, val in (show.get("model_info") or {}).items():
            if key.endswith(".context_length") and isinstance(val, int) and not isinstance(val, bool):
                out["max_ctx"] = val
                break
        for line in (show.get("parameters") or "").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "num_ctx":
                out["num_ctx"] = int(parts[1])
                break

        ps = _call(host + "/api/ps")
        entry = next((m for m in ps.get("models") or [] if _matches(m, model)), None)
        if entry is not None:
            size = entry.get("size") or 0
            size_vram = entry.get("size_vram") or 0
            out["file_gb"] = _gb(size)
            out["vram_gb"] = _gb(size_vram)
            out["cpu_offload_pct"] = round(100 * (size - size_vram) / size, 1) if size else ""
            if entry.get("context_length"):
                out["num_ctx"] = int(entry["context_length"])
        else:
            tags = _call(host + "/api/tags")
            tag = next((m for m in tags.get("models") or [] if _matches(m, model)), None)
            if tag is not None and tag.get("size"):
                out["file_gb"] = _gb(tag["size"])

        if peak_tokens and out["num_ctx"]:
            out["ctx_used_pct"] = round(100 * peak_tokens / out["num_ctx"], 1)
            out["ctx_free_tokens"] = out["num_ctx"] - peak_tokens
    except Exception:  # noqa: BLE001
        return {k: "" for k in KEYS}
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: modelinfo.py <model> [endpoint]")
    print(json.dumps(info(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST), indent=2))
