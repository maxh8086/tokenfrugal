"""Story generation runner for the tokenfrugal story-test benchmark.

Runs four passes (story, critic, anti-ai, humanizer) per topic per model
against the local Ollama API using only the standard library.

Destination gate: a full run needs --destination, one of the platforms in
DESTINATIONS. Each destination has its own story rules, critic checks,
sentence cap and keep-rules. Outputs, CSV and failure file are kept per
destination, so runs for different platforms never overwrite each other.

Usage:
  python run_stories.py --list-destinations                 print the destinations
  python run_stories.py --destination youtube-shorts        full run for one destination
  python run_stories.py --test                              single test call: model ts-granite4-micro-65536:latest, prompt "Say OK"

Stop rule: any failed call (HTTP error, timeout, empty response) writes
RUN_FAILED-<destination>.md and stops the whole run immediately.
"""

import argparse
import csv
import json
import os
import random
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
OUTPUTS_ROOT = os.path.join(HERE, "outputs")
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
SHUFFLE_SEED = 20261104


def destination_topics():
    """Assign each topic to one destination: a seeded shuffle of the topics, paired
    with the destinations in their listed order. Reproducible; one topic per destination."""
    topics = list(TOPICS)
    random.Random(f"{SHUFFLE_SEED}-topics").shuffle(topics)
    return dict(zip(DESTINATIONS, topics))


def topic_order(dest):
    """The single topic assigned to this destination, as a one-item list."""
    return [destination_topics()[dest]]

# One entry per placement. Criteria come from the platform table in
# docs/designs/story-criteria-gap-analysis.md (section 1a). Word counts and
# sentence caps for the non-Shorts platforms are assumptions, to be confirmed.
DESTINATIONS = {
    "youtube-shorts": {
        "label": "YouTube Shorts",
        "words": "120 to 180",
        "sentence_max": 15,
        "keep": "Keep the first line and the final line word for word.",
        "story": "Rewrite the draft below as a YouTube Shorts script of 120 to 180 words. "
                 "Open the first line on the climax or on a bizarre, impossible, or "
                 "high-stakes paradox. Keep the premise unusual and specific. Use short "
                 "sentences, one new visual beat per sentence, no sentence over 15 words. "
                 "End with a final line that echoes the opening line so the video loops. "
                 "Keep the core events of the draft. Output only the script.",
        "critic": "Score the script below against four items: (1) the first line is a "
                  "paradox or climax, (2) the premise is unusual and specific, (3) sentences "
                  "are short and each adds a visual beat, (4) the last line echoes the first. "
                  "For each item that fails, name it and the line that fails it. Output a "
                  "numbered list and no rewrite.",
    },
    "instagram-reels": {
        "label": "Instagram Reels",
        "words": "120 to 170",
        "sentence_max": 18,
        "keep": "Keep the first line word for word. Keep the share prompt in the final line.",
        "story": "Rewrite the draft below as an Instagram Reels script of 120 to 170 words. "
                 "Open the first line with a curiosity hook that a muted viewer reads at "
                 "once, such as a surprising claim or a question the story answers. Keep "
                 "the premise relatable and specific. Use short sentences, one visual beat "
                 "each, no sentence over 18 words. End with one line that prompts a direct "
                 "share, in the form 'Send this to the friend who...'. Keep the core events "
                 "of the draft. Output only the script.",
        "critic": "Score the script below against four items: (1) the first line is a "
                  "curiosity hook a muted viewer reads at once, (2) the premise is relatable "
                  "and specific, (3) sentences are short, each adds one visual beat, and none "
                  "is over 18 words, (4) the last line prompts a direct share, such as 'Send "
                  "this to the friend who...'. For each item that fails, name it and the line "
                  "that fails it. Output a numbered list and no rewrite.",
    },
    "facebook-reels": {
        "label": "Facebook Reels",
        "words": "120 to 170",
        "sentence_max": 18,
        "keep": "Keep the first line word for word.",
        "story": "Rewrite the draft below as a Facebook Reels script of 120 to 170 words for "
                 "an older audience. Open the first line on a relatable moment or a what-if "
                 "question that taps nostalgia or a familiar trope. Keep the setting specific "
                 "and recognisable. Use short sentences with room to breathe, one visual "
                 "beat per sentence, no sentence over 18 words. End with a final line that "
                 "closes on a warm, shareable note. Keep the core events of the draft. "
                 "Output only the script.",
        "critic": "Score the script below against four items: (1) the first line is a "
                  "relatable moment or a what-if question, (2) the setting is specific and "
                  "recognisable, (3) sentences are short with room to breathe, and none is "
                  "over 18 words, (4) the final line closes on a warm, shareable note. For "
                  "each item that fails, name it and the line that fails it. Output a "
                  "numbered list and no rewrite.",
    },
    "linkedin": {
        "label": "LinkedIn",
        "words": "130 to 180",
        "sentence_max": 20,
        "keep": "Keep the first line word for word. Keep the final question word for word.",
        "story": "Rewrite the draft below as a LinkedIn video script of 130 to 180 words. "
                 "Frame the story as a professional parable with one clear business lesson. "
                 "Open the first line on a concrete work situation. Keep the tone calm, "
                 "confident and documentary, not dramatic. Use clear sentences, no sentence "
                 "over 20 words. End with one specific professional question that invites "
                 "comments. Keep the core events of the draft. Output only the script.",
        "critic": "Score the script below against four items: (1) the first line is a "
                  "concrete work situation, (2) a clear business lesson is stated or implied, "
                  "(3) the tone is calm and documentary, not dramatic, and no sentence is over "
                  "20 words, (4) the final line is one specific professional question. For "
                  "each item that fails, name it and the line that fails it. Output a "
                  "numbered list and no rewrite.",
    },
    "long-form": {
        "label": "Long-form (5 to 20 min)",
        "words": "130 to 180",
        "sentence_max": 25,
        "keep": "Keep the three act breaks in place.",
        "story": "Rewrite the draft below as a long-form narrative script of 130 to 180 "
                 "words. Use three acts: setup, conflict, resolution. Build the world with "
                 "specific lore, the character's motive, and the atmosphere of the setting. "
                 "Alternate dialogue valleys with action peaks. Use clear sentences, no "
                 "sentence over 25 words. Keep the core events of the draft. Output only the "
                 "script.",
        "critic": "Score the script below against four items: (1) three acts are clear: "
                  "setup, conflict, resolution, (2) the setting, lore and atmosphere are "
                  "specific, (3) the character's motive is stated and drives an action, (4) "
                  "tension rises and releases, with no long run of flat exposition. For each "
                  "item that fails, name it and the passage that fails it. Output a numbered "
                  "list and no rewrite.",
    },
}

# Prompt set v3 (2026-11-04). Same destinations, models, topics and rubric as v2; only the
# prompts change, for the weak points found in the v2 ratings:
#   - the target sits in the middle of the word range, and the anti-AI and humanizer
#     passes must not shorten the text below the range (v2 Shorts median fell 114 -> 91);
#   - line 1 must state the stakes (hook was the lowest-scoring item on LinkedIn and long-form);
#   - the final line has a named form per destination (Facebook close was the weakest item);
#   - the no-repeat rule (qwen3-8-9b-distill looped on long-form in v2).
V3_OVERRIDES = {
    "youtube-shorts": {
        "story": "Rewrite the draft below as a YouTube Shorts script of about 150 words "
                 "(120 to 180 is the limit). Line 1 must be a single sentence that states the "
                 "impossible or high-stakes fact itself, so the viewer knows the stakes at once. "
                 "Build the premise as a what-if the viewer must watch to resolve. Use short "
                 "sentences, one new visual beat per sentence, no sentence over 15 words. The "
                 "final line must repeat a key phrase or image from line 1, so the video loops "
                 "back to its start. Keep the core events of the draft. Output only the script.",
        "critic": "Score the script below against four items: (1) line 1 is a single sentence "
                  "that states an impossible or high-stakes fact, (2) the premise is a what-if "
                  "the viewer must watch to resolve, (3) sentences are short, each adds one "
                  "visual beat, and none is over 15 words, (4) the final line repeats a key "
                  "phrase or image from line 1. For each item that fails, name it and the line "
                  "that fails it. Also state whether the length is 120 to 180 words. Output a "
                  "numbered list and no rewrite.",
        "keep": "Keep the first line and the final line word for word.",
        "length_rule": "Keep the length between 120 and 170 words, and aim for about 150. Do not "
                       "shorten it below 120 words. Never repeat a sentence.",
    },
    "instagram-reels": {
        "story": "Rewrite the draft below as an Instagram Reels script of about 145 words "
                 "(120 to 170 is the limit). Line 1 must be a curiosity hook a muted viewer "
                 "reads at once: a surprising claim, or a question the story answers before the "
                 "end. Keep the premise relatable and specific. Use short sentences, one visual "
                 "beat each, no sentence over 18 words. The final line must be a direct share "
                 "prompt in the form 'Send this to the friend who...', completed with a trait "
                 "that fits the story. Keep the core events of the draft. Output only the script.",
        "critic": "Score the script below against four items: (1) line 1 is a curiosity hook a "
                  "muted viewer reads at once, (2) the premise is relatable and specific, (3) "
                  "sentences are short, each adds one visual beat, and none is over 18 words, (4) "
                  "the final line is a direct share prompt in the form 'Send this to the friend "
                  "who...'. For each item that fails, name it and the line that fails it. Also "
                  "state whether the length is 120 to 170 words. Output a numbered list and no "
                  "rewrite.",
        "keep": "Keep the first line word for word. Keep the share prompt in the final line.",
        "length_rule": "Keep the length between 120 and 170 words, and aim for about 145. Do not "
                       "shorten it below 120 words. Never repeat a sentence.",
    },
    "facebook-reels": {
        "story": "Rewrite the draft below as a Facebook Reels script of about 145 words (120 to "
                 "170 is the limit) for an older audience. Line 1 must be a relatable moment or a "
                 "what-if question that taps nostalgia or a familiar everyday trope. Keep the "
                 "setting specific and recognisable: name a place, an object, or a time of day. "
                 "Use short sentences with room to breathe, one visual beat per sentence, no "
                 "sentence over 18 words. The final line must be a warm closing line that names "
                 "a feeling the viewer shares, such as nostalgia or gratitude, in one sentence. "
                 "Keep the core events of the draft. Output only the script.",
        "critic": "Score the script below against four items: (1) line 1 is a relatable moment or "
                  "a what-if question, (2) the setting is specific and recognisable, naming a "
                  "place, an object or a time, (3) sentences are short with room to breathe, and "
                  "none is over 18 words, (4) the final line is a warm closing line that names a "
                  "feeling the viewer shares. For each item that fails, name it and the line that "
                  "fails it. Also state whether the length is 120 to 170 words. Output a numbered "
                  "list and no rewrite.",
        "keep": "Keep the first line word for word.",
        "length_rule": "Keep the length between 120 and 170 words, and aim for about 145. Do not "
                       "shorten it below 120 words. Never repeat a sentence.",
    },
    "linkedin": {
        "story": "Rewrite the draft below as a LinkedIn video script of about 155 words (130 to "
                 "180 is the limit). Frame the story as a professional parable with one clear "
                 "business lesson. Line 1 must be a concrete work situation with a named role or "
                 "task. Keep the tone calm, confident and documentary, not dramatic. Use clear "
                 "sentences, no sentence over 20 words. State the business lesson in one sentence "
                 "in the middle. The final line must be one specific professional question a "
                 "reader can answer in a single comment, tied to that lesson. Keep the core events "
                 "of the draft. Output only the script.",
        "critic": "Score the script below against four items: (1) line 1 is a concrete work "
                  "situation with a role or task, (2) one clear business lesson is stated in the "
                  "middle, (3) the tone is calm and documentary, and no sentence is over 20 words, "
                  "(4) the final line is one specific question a reader can answer in one comment, "
                  "tied to the lesson. For each item that fails, name it and the line that fails "
                  "it. Also state whether the length is 130 to 180 words. Output a numbered list "
                  "and no rewrite.",
        "keep": "Keep the first line word for word. Keep the final question word for word.",
        "length_rule": "Keep the length between 130 and 180 words, and aim for about 155. Do not "
                       "shorten it below 130 words. Never repeat a sentence.",
    },
    "long-form": {
        "story": "Rewrite the draft below as a long-form narrative script of about 155 words "
                 "(130 to 180 is the limit). Use three acts: setup, conflict, resolution, with no "
                 "act labels in the text. Open the setup on the character and a specific setting, "
                 "with a name, a place and a time of day. State the character's motive in the "
                 "setup, and let it drive the conflict. Alternate one quiet line with one action "
                 "beat. Use clear sentences, no sentence over 25 words. The resolution must settle "
                 "the central conflict set up in the first act. Keep the core events of the draft. "
                 "Output only the script.",
        "critic": "Score the script below against four items: (1) three acts are clear: a setup, "
                  "a conflict and a resolution, (2) the setting, lore and atmosphere are specific, "
                  "(3) the character's motive is stated and drives an action, (4) tension rises and "
                  "releases, and the resolution settles the conflict from act one. For each item "
                  "that fails, name it and the passage that fails it. Also state whether the length "
                  "is 130 to 180 words. Output a numbered list and no rewrite.",
        "keep": "Keep the three act breaks in place.",
        "length_rule": "Keep the length between 130 and 180 words, and aim for about 155. Do not "
                       "shorten it below 130 words. Never repeat a sentence.",
    },
}

DESTINATIONS_V3 = {key: {**spec, **V3_OVERRIDES[key]} for key, spec in DESTINATIONS.items()}
PROMPT_SETS = {"v2": DESTINATIONS, "v3": DESTINATIONS_V3}
PROMPT_SET = "v2"  # set by --prompt-set in main()


def spec_for(dest):
    """The destination spec for the active prompt set."""
    return PROMPT_SETS[PROMPT_SET][dest]


CSV_HEADER = ["model", "topic", "pass", "seconds", "gpu_used", "status", "error"]


def log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_prompts(dest):
    """Return the prompt head for each pass, for one destination and the active prompt set."""
    spec = spec_for(dest)
    rule = (" " + spec["length_rule"]) if spec.get("length_rule") else ""
    return {
        "story": spec["story"],
        "critic": spec["critic"],
        "anti-ai": (f"Revise the script using the critique. Remove every phrase in the list "
                    f"below. Keep every sentence under {spec['sentence_max']} words. "
                    f"{spec['keep']}{rule} Output only the revised script."),
        "humanizer": (f"Make a final pass for natural voice. {spec['keep']} Keep sentences "
                      f"under {spec['sentence_max']} words.{rule} Output only the final script."),
    }


def dest_paths(dest):
    """Output folder, runs CSV, failure file and gate file. v2 keeps the original names;
    other prompt sets write to outputs-<set>/ with a set prefix on the CSV and failure file."""
    if PROMPT_SET == "v2":
        root, tag = OUTPUTS_ROOT, ""
    else:
        root, tag = os.path.join(HERE, f"outputs-{PROMPT_SET}"), f"{PROMPT_SET}-"
    out = os.path.join(root, dest)
    return {
        "out": out,
        "csv": os.path.join(HERE, f"runs-{tag}{dest}.csv"),
        "fail": os.path.join(HERE, f"RUN_FAILED-{tag}{dest}.md"),
        "gate": os.path.join(out, "gate.json"),
    }


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


def append_csv(csv_path, row):
    new_file = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    with open(csv_path, "a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(CSV_HEADER)
        writer.writerow(row)


def fail_and_stop(paths, dest, tag, topic, pass_name, error):
    with open(paths["fail"], "w", encoding="utf-8") as fh:
        fh.write("# Run failed\n\n")
        fh.write(f"- time: {datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"- destination: {dest}\n")
        fh.write(f"- model: {tag}\n")
        fh.write(f"- topic: {topic}\n")
        fh.write(f"- pass: {pass_name}\n")
        fh.write(f"- error: {error}\n")
    log(f"FAILED destination={dest} model={tag} topic={topic} pass={pass_name} error={error}. Run stopped.")
    sys.exit(1)


def run_pass(paths, dest, prompts, tag, slug, topic, pass_name, input_text):
    head = prompts[pass_name]
    if pass_name == "anti-ai":
        # The stock-phrase list is read from disk at run time, verbatim, one phrase per line.
        head += "\n\nPhrase list:\n" + read_text(STOCK_PATH).strip()
    prompt = head + "\n\n" + input_text
    start = time.monotonic()
    try:
        response = call_ollama(tag, prompt)
        seconds = round(time.monotonic() - start, 1)
        if not response:
            raise RuntimeError("empty response")
        gpu = gpu_used(tag)
        out_path = os.path.join(paths["out"], slug, f"topic-{topic}", f"{pass_name}.md")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(response + "\n")
    except Exception as exc:
        seconds = round(time.monotonic() - start, 1)
        error = describe_error(exc)
        gpu = gpu_used(tag)
        append_csv(paths["csv"], [tag, topic, pass_name, seconds, gpu, "error", error])
        fail_and_stop(paths, dest, tag, topic, pass_name, error)
    append_csv(paths["csv"], [tag, topic, pass_name, seconds, gpu, "ok", ""])
    log(f"ok destination={dest} model={tag} topic={topic} pass={pass_name} seconds={seconds} gpu={gpu}")
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


def run_full(dest):
    if not os.path.isdir(DRAFTS_DIR):
        raise SystemExit(f"missing drafts dir: {DRAFTS_DIR}")
    paths = dest_paths(dest)
    prompts = build_prompts(dest)
    spec = spec_for(dest)
    order = topic_order(dest)
    os.makedirs(paths["out"], exist_ok=True)
    with open(paths["gate"], "w", encoding="utf-8") as fh:
        json.dump({
            "destination": dest,
            "label": spec["label"],
            "words": spec["words"],
            "sentence_max": spec["sentence_max"],
            "topic_order": order,
            "gate_time": datetime.now().isoformat(timespec="seconds"),
        }, fh, indent=2)
    log(f"topic order destination={dest} {order}")
    log(f"START full run destination={dest} prompt_set={PROMPT_SET} ({spec['label']}, {spec['words']} words) "
        f"pid={os.getpid()} python={sys.executable}")
    if os.path.exists(STOCK_PATH):
        log(f"anti-ai prompt embeds stock-phrase list from {STOCK_PATH}")
    for tag, slug in MODELS:
        log(f"MODEL start {tag} -> {slug}")
        for topic in order:
            draft = read_text(os.path.join(DRAFTS_DIR, f"topic-{topic}.md")).strip()
            story = run_pass(paths, dest, prompts, tag, slug, topic, "story", draft)
            critic = run_pass(paths, dest, prompts, tag, slug, topic, "critic", story)
            anti_input = story + "\n\nCritique:\n" + critic
            anti = run_pass(paths, dest, prompts, tag, slug, topic, "anti-ai", anti_input)
            run_pass(paths, dest, prompts, tag, slug, topic, "humanizer", anti)
        unload(tag)
        log(f"MODEL done {tag}")
    log(f"DONE all models and topics destination={dest}")


def list_destinations():
    for key, spec in DESTINATIONS.items():
        print(f"{key:18} {spec['label']:24} {spec['words']:12} sentence max {spec['sentence_max']}")


def main():
    global PROMPT_SET
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="single test call only")
    parser.add_argument("--list-destinations", action="store_true", help="print the destinations and exit")
    parser.add_argument("--destination", choices=sorted(DESTINATIONS),
                        help="where the story will be placed; required for a full run")
    parser.add_argument("--prompt-set", choices=sorted(PROMPT_SETS), default="v2",
                        help="prompt version: v2 (original destination prompts) or v3 "
                             "(revised prompts, written to outputs-v3/ and runs-v3-<destination>.csv)")
    args = parser.parse_args()
    PROMPT_SET = args.prompt_set
    if args.list_destinations:
        list_destinations()
        return 0
    if args.test:
        return run_test()
    if not args.destination:
        parser.error("--destination is required for a full run. Confirm where the story is "
                     "placed first (see --list-destinations).")
    run_full(args.destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
