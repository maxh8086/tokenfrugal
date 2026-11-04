"""Story generation runner for the tokenfrugal story-test benchmark.

Runs four passes (story, critic, anti-ai, humanizer) per topic per model
against the local Ollama API using only the standard library.

Usage:
  python run_stories.py           full run (all models, topics 1-5)
  python run_stories.py --test    single test call: model ts-granite4-micro-65536:latest, prompt "Say OK"

Stop rule: any failed call (HTTP error, timeout, empty response) writes
RUN_FAILED.md and stops the whole run immediately.
"""

import argparse
import csv
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR = os.path.join(HERE, "drafts")
STOCK_PATH = os.path.join(HERE, "stock-phrases.txt")
OUT_DIR = os.path.join(HERE, "outputs")
CSV_PATH = os.path.join(HERE, "runs.csv")
FAIL_PATH = os.path.join(HERE, "RUN_FAILED.md")
LOG_PATH = os.path.join(HERE, "run_stories.log")

API_URL = "http://localhost:11434/api/generate"
HTTP_TIMEOUT = 900
OPTIONS = {"num_ctx": 32768, "num_predict": 8192, "temperature": 0.1}

MODELS = [
    ("ts-gemma4-e4b-65536:latest", "gemma-4-e4b"),
    ("ts-qwen3-8-9b-distill-65536:latest", "qwen3-8-9b-distill"),
    ("ts-qwen3-5-4b-q6k-65536:latest", "qwen3-5-4b-q6k"),
    ("ts-nemotron-3-nano-4b-65536:latest", "nemotron-3-nano-4b"),
    ("ts-llama3-1-8b-65536:latest", "llama3-1-8b"),
    ("ts-granite4-tiny-h-65536:latest", "granite4-tiny-h"),
    ("ts-qwen2-5-7b-32768:latest", "qwen2-5-7b"),
    ("ts-ministral-3-8b-65536:latest", "ministral-3-8b"),
    ("ts-granite4-micro-65536:latest", "granite4-micro"),
]

TOPICS = [1, 2, 3, 4, 5]
PASSES = ["story", "critic", "anti-ai", "humanizer"]

PROMPTS = {
    "story": "Rewrite the draft below as a short story of 600 to 900 words. "
             "Keep every event in the draft. Output only the story.",
    "critic": "List the weakest points of the story below: plot gaps, choices "
              "with no reason, vague detail. Output a numbered list and no rewrite.",
    "humanizer": "Make a final pass for natural voice. Keep the plot. "
                 "Output only the final story.",
}

CSV_HEADER = ["model", "topic", "pass", "seconds", "gpu_used", "status", "error"]


def log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def call_ollama(model, prompt, keep_alive="5m"):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "keep_alive": keep_alive,
        "options": OPTIONS,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return (body.get("response") or "").strip()


def describe_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            detail = ""
        return f"HTTPError {exc.code}: {exc.reason} {detail}".strip()
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return f"Timeout after {HTTP_TIMEOUT}s: {exc}"
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (socket.timeout, TimeoutError)):
        return f"Timeout after {HTTP_TIMEOUT}s: {exc.reason}"
    return f"{type(exc).__name__}: {exc}"


def gpu_used(tag):
    """Return 'yes' if `ollama ps` shows the model with PROCESSOR containing GPU."""
    try:
        out = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        ).stdout
    except Exception as exc:
        log(f"WARN ollama ps failed: {exc}")
        return "no"
    short = tag.split(":")[0]
    for line in out.splitlines()[1:]:
        cols = line.split()
        if not cols:
            continue
        if cols[0] in (tag, short) and "GPU" in line:
            return "yes"
    return "no"


def append_csv(row):
    new_file = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(CSV_HEADER)
        writer.writerow(row)


def fail_and_stop(tag, topic, pass_name, error):
    with open(FAIL_PATH, "w", encoding="utf-8") as fh:
        fh.write("# Run failed\n\n")
        fh.write(f"- time: {datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"- model: {tag}\n")
        fh.write(f"- topic: {topic}\n")
        fh.write(f"- pass: {pass_name}\n")
        fh.write(f"- error: {error}\n")
    log(f"FAILED model={tag} topic={topic} pass={pass_name} error={error}. Run stopped.")
    sys.exit(1)


ANTI_AI_PROMPT = ("Revise the story using the critique. Remove every phrase in the list "
                  "below. Vary sentence length. Output only the revised story.")


def get_prompt(pass_name):
    """Return the prompt head for a pass. The anti-ai prompt embeds the stock-phrase
    list, read from disk at run time, verbatim, one phrase per line."""
    if pass_name == "anti-ai":
        phrases = read_text(STOCK_PATH).strip()
        return ANTI_AI_PROMPT + "\n\nPhrase list:\n" + phrases
    return PROMPTS[pass_name]


def run_pass(tag, slug, topic, pass_name, input_text):
    prompt = get_prompt(pass_name) + "\n\n" + input_text
    start = time.monotonic()
    try:
        response = call_ollama(tag, prompt)
        seconds = round(time.monotonic() - start, 1)
        if not response:
            raise RuntimeError("empty response")
        gpu = gpu_used(tag)
        out_path = os.path.join(OUT_DIR, slug, f"topic-{topic}", f"{pass_name}.md")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(response + "\n")
    except Exception as exc:
        seconds = round(time.monotonic() - start, 1)
        error = describe_error(exc)
        gpu = gpu_used(tag)
        append_csv([tag, topic, pass_name, seconds, gpu, "error", error])
        fail_and_stop(tag, topic, pass_name, error)
    append_csv([tag, topic, pass_name, seconds, gpu, "ok", ""])
    log(f"ok model={tag} topic={topic} pass={pass_name} seconds={seconds} gpu={gpu}")
    return response


def unload(tag):
    try:
        call_ollama(tag, "", keep_alive=0)
        log(f"unloaded model={tag}")
    except Exception as exc:
        # Unload failure does not stop the run; the stop rule covers generation calls.
        log(f"WARN unload failed model={tag} error={describe_error(exc)}")


def run_test():
    tag = "ts-granite4-micro-65536:latest"
    log(f"TEST start model={tag} prompt='Say OK'")
    start = time.monotonic()
    try:
        response = call_ollama(tag, "Say OK")
        seconds = round(time.monotonic() - start, 1)
        if not response:
            raise RuntimeError("empty response")
    except Exception as exc:
        error = describe_error(exc)
        log(f"TEST FAILED error={error}")
        print(f"TEST FAILED: {error}")
        return 1
    gpu = gpu_used(tag)
    log(f"TEST ok seconds={seconds} gpu={gpu} response={response!r}")
    print(f"TEST OK seconds={seconds} gpu={gpu} response={response!r}")
    return 0


def run_full():
    if not os.path.isdir(DRAFTS_DIR):
        raise SystemExit(f"missing drafts dir: {DRAFTS_DIR}")
    log(f"START full run pid={os.getpid()} python={sys.executable}")
    if os.path.exists(STOCK_PATH):
        log(f"anti-ai prompt embeds stock-phrase list from {STOCK_PATH}")
    for tag, slug in MODELS:
        log(f"MODEL start {tag} -> {slug}")
        for topic in TOPICS:
            draft = read_text(os.path.join(DRAFTS_DIR, f"topic-{topic}.md")).strip()
            story = run_pass(tag, slug, topic, "story", draft)
            critic = run_pass(tag, slug, topic, "critic", story)
            anti_input = story + "\n\nCritique:\n" + critic
            anti = run_pass(tag, slug, topic, "anti-ai", anti_input)
            run_pass(tag, slug, topic, "humanizer", anti)
        unload(tag)
        log(f"MODEL done {tag}")
    log("DONE all models and topics")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="single test call only")
    args = parser.parse_args()
    if args.test:
        return run_test()
    run_full()
    return 0


if __name__ == "__main__":
    sys.exit(main())
