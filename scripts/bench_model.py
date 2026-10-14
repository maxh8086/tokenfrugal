"""Run the TokenFrugal benchmark against one model or endpoint.

Usage:
    # Ollama model tag: used for every role (persona overrides disabled)
    python scripts/bench_model.py --model qwen3:8b

    # OpenAI-compatible endpoint (e.g. a llama.cpp or vLLM server)
    python scripts/bench_model.py --url http://127.0.0.1:8282/v1

Exactly one of --model or --url is required. Results are written to
bench/<tag>/ under the repo root. The tag defaults to the sanitized model
tag, or the sanitized host+port of --url.

Standard library only.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent


def _sanitize(text: str) -> str:
    """Make a string safe for use as a directory name (no ':' or '/')."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return cleaned or "bench"


def _url_tag(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "endpoint"
    if parsed.port is not None:
        return _sanitize(f"{host}_{parsed.port}")
    return _sanitize(host)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run scripts.bench (output + realworld) for one model or endpoint.",
    )
    parser.add_argument(
        "--model",
        metavar="TAG",
        help="Ollama model tag, used for builder and thinker roles (e.g. qwen3:8b).",
    )
    parser.add_argument(
        "--url",
        metavar="BASE",
        help="OpenAI-compatible base URL (e.g. http://127.0.0.1:8282/v1).",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=2,
        help="Number of benchmark repetitions (default: 2).",
    )
    parser.add_argument(
        "--tag",
        metavar="STR",
        help="Output tag; defaults to the model tag or the sanitized URL host+port.",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if bool(args.model) == bool(args.url):
        parser.error("exactly one of --model or --url is required")

    if args.n < 1:
        parser.error("--n must be at least 1")

    if args.tag:
        tag = _sanitize(args.tag)
    elif args.model:
        tag = _sanitize(args.model)
    else:
        tag = _url_tag(args.url)

    env = os.environ.copy()
    if args.url:
        target = f"url={args.url}"
        env["TOKENFRUGAL_LLM_URL"] = args.url
        model_override = "none (endpoint serves its own model)"
    else:
        target = "ollama (default LLM URL)"
        env["TOKENFRUGAL_MODEL_BUILDER"] = args.model
        env["TOKENFRUGAL_MODEL_THINKER"] = args.model
        env["TOKENFRUGAL_PERSONA_MODELS"] = "0"
        model_override = args.model

    out_rel = f"bench/{tag}"
    out_dir = REPO_ROOT / "bench" / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    env["PYTHONPATH"] = str(REPO_ROOT)
    env["BENCH_OUT_DIR"] = out_rel

    print(f"Target:         {target}", flush=True)
    print(f"Model override: {model_override}", flush=True)
    print(f"Output dir:     {out_dir}", flush=True)
    print(f"Tag:            {tag}", flush=True)

    cmd = [
        sys.executable,
        "-m",
        "scripts.bench",
        "--n",
        str(args.n),
        "--only",
        "output,realworld",
        "--tag",
        tag,
    ]
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
