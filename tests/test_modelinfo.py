import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Benchmark" / "script"))

import modelinfo  # noqa: E402

GB = 2**30
BLANK = {k: "" for k in modelinfo.KEYS}


class FakeResp:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def router(routes):
    """Fake urlopen: routes maps a URL suffix to a payload (or an exception to raise)."""
    def fake(req, timeout=None):
        url = req.full_url
        for suffix, payload in routes.items():
            if url.endswith(suffix):
                if isinstance(payload, Exception):
                    raise payload
                return FakeResp(payload)
        raise urllib.error.URLError(f"no route for {url}")
    return fake


SHOW = {
    "details": {"quantization_level": "Q4_K_M"},
    "model_info": {"general.architecture": "qwen2", "qwen2.context_length": 32768},
    "parameters": "stop \"<|im_end|>\"\nnum_ctx 8192\n",
}
PS = {"models": [{"name": "qwen2.5-coder-yarn:3b", "model": "qwen2.5-coder-yarn:3b",
                  "size": 4 * GB, "size_vram": 3 * GB, "context_length": 16384}]}
TAGS = {"models": [{"name": "qwen2.5-coder-yarn:3b", "model": "qwen2.5-coder-yarn:3b", "size": 2 * GB}]}


class ModelInfo(unittest.TestCase):
    def test_full_parse_with_ps_entry_and_peak(self):
        fake = router({"/api/show": SHOW, "/api/ps": PS})
        with mock.patch("urllib.request.urlopen", side_effect=fake):
            got = modelinfo.info("qwen2.5-coder-yarn:3b", "http://localhost:11434/v1", 4096)
        self.assertEqual(got["quant"], "Q4_K_M")
        self.assertEqual(got["max_ctx"], 32768)
        self.assertEqual(got["file_gb"], 4.0)
        self.assertEqual(got["vram_gb"], 3.0)
        self.assertEqual(got["cpu_offload_pct"], 25.0)
        self.assertEqual(got["num_ctx"], 16384)  # /api/ps context_length wins over parameters
        self.assertEqual(got["ctx_used_pct"], 25.0)
        self.assertEqual(got["ctx_free_tokens"], 12288)

    def test_num_ctx_from_parameters_when_not_loaded_and_tags_fallback(self):
        fake = router({"/api/show": SHOW, "/api/ps": {"models": []}, "/api/tags": TAGS})
        with mock.patch("urllib.request.urlopen", side_effect=fake):
            got = modelinfo.info("qwen2.5-coder-yarn:3b", "http://h:1234/v1/")
        self.assertEqual(got["num_ctx"], 8192)
        self.assertEqual(got["file_gb"], 2.0)
        self.assertEqual(got["vram_gb"], "")
        self.assertEqual(got["cpu_offload_pct"], "")
        self.assertEqual(got["ctx_used_pct"], "")  # no peak given
        self.assertEqual(got["ctx_free_tokens"], "")

    def test_latest_tag_matches_and_host_is_normalised(self):
        ps_entry = {"models": [{"name": "llama3.2:3b-16k:latest", "size": GB, "size_vram": GB}]}
        fake = router({"/api/show": SHOW, "/api/ps": ps_entry})
        with mock.patch("urllib.request.urlopen", side_effect=fake) as m:
            got = modelinfo.info("llama3.2:3b-16k", "http://host.docker.internal:11434/")
        self.assertEqual(got["file_gb"], 1.0)
        self.assertEqual(got["cpu_offload_pct"], 0.0)
        urls = [c.args[0].full_url for c in m.call_args_list]
        self.assertEqual(urls[0], "http://host.docker.internal:11434/api/show")
        self.assertEqual(m.call_args_list[0].kwargs["timeout"], 5)

    def test_unreachable_endpoint_gives_all_blanks(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            self.assertEqual(modelinfo.info("m", "http://localhost:11434/v1", 100), BLANK)

    def test_non_ollama_endpoint_gives_all_blanks(self):
        err = urllib.error.HTTPError("https://api.example/v1/api/show", 404, "Not Found", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            self.assertEqual(modelinfo.info("gpt-x", "https://api.example/v1", 100), BLANK)

    def test_bad_json_gives_all_blanks(self):
        class Bad(FakeResp):
            def read(self):
                return b"<html>not json</html>"
        with mock.patch("urllib.request.urlopen", return_value=Bad({})):
            self.assertEqual(modelinfo.info("m", "http://localhost:11434"), BLANK)


if __name__ == "__main__":
    unittest.main()
