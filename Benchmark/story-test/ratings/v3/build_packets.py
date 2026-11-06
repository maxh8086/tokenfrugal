"""Build blind rating packets for prompt set v3.

For each destination: 9 models x 3 passes (story, anti-ai, humanizer) = 27 items.
Items carry a random ID only. The key (ID -> model, pass, topic, source) is written
outside the items folder so raters never see it. The critic pass is not rated.

Usage: python build_packets.py
"""

import hashlib
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
STORY_TEST = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTPUTS = os.path.join(STORY_TEST, "outputs-v3")
ITEMS = os.path.join(HERE, "items")
KEYS = os.path.join(HERE, "_key")
RAW = os.path.join(HERE, "raw")

DATE = "20261104"
SET = "v3"

MODELS = [
    "gemma-4-e4b", "qwen3-8-9b-distill", "qwen3-5-4b-q6k", "nemotron-3-nano-4b",
    "llama3-1-8b", "granite4-tiny-h", "qwen2-5-7b", "ministral-3-8b", "granite4-micro",
]
PASSES = ["story", "anti-ai", "humanizer"]

# Destination topic, as in v2 (seeded assignment, one topic per destination).
TOPIC = {
    "youtube-shorts": 4,
    "instagram-reels": 5,
    "facebook-reels": 1,
    "linkedin": 2,
    "long-form": 3,
}

ITEM4 = {
    "youtube-shorts": "Loop and call to action (20): the ending loops back into the opening hook, or it prompts a share.",
    "instagram-reels": "Loop and call to action (20): the ending loops back into the opening hook, or it prompts a share.",
    "facebook-reels": "Loop and call to action (20): the ending loops back into the opening hook, or it prompts a share.",
    "linkedin": "Closing question (20): the last line is one specific professional question a reader can answer in a comment, tied to the business lesson.",
    "long-form": "Resolution (20): the ending resolves the central conflict set up in act one.",
}

RUBRIC = """You rate one short story text out of 100. You do not know which model wrote it. Score only the text.

Items:
1. 3-second hook (30): the opening line introduces a bizarre, impossible, or high-stakes paradox, or starts at the climax.
2. Concept and what-if factor (25): the premise is a hyper-niche mashup or unusual crossover that forces curiosity.
3. Narrative pacing (25): short, punchy sentences that would need a new visual every 2 to 3 seconds, with no dead air.
4. {item4}

Rules: give each item an integer within its maximum. Be strict. Do not reward length. Judge the text as written. Total = sum of the four items.

Output format: for every item file in this folder (not the rubric), output one line:
id,hook,concept,pacing,item4,total
Output only those lines, plus a header line first: id,hook,concept,pacing,item4,total
"""


def item_id(dest, model, pass_name):
    seed = f"{DATE}-{SET}-{dest}-{model}-{pass_name}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6]


def main():
    for folder in (ITEMS, KEYS):
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)
    for dest, topic in TOPIC.items():
        item_dir = os.path.join(ITEMS, dest)
        os.makedirs(item_dir, exist_ok=True)
        key = {}
        for model in MODELS:
            for pass_name in PASSES:
                src = os.path.join(OUTPUTS, dest, model, f"topic-{topic}", f"{pass_name}.md")
                if not os.path.isfile(src):
                    raise SystemExit(f"missing output: {src}")
                iid = item_id(dest, model, pass_name)
                if iid in key:
                    raise SystemExit(f"ID collision {iid} in {dest}")
                with open(src, "r", encoding="utf-8") as fh:
                    text = fh.read().strip()
                with open(os.path.join(item_dir, f"{iid}.md"), "w", encoding="utf-8") as fh:
                    fh.write(text + "\n")
                key[iid] = {"model": model, "pass": pass_name, "topic": topic, "source": src}
        with open(os.path.join(KEYS, f"{dest}.json"), "w", encoding="utf-8") as fh:
            json.dump(key, fh, indent=2)
        with open(os.path.join(HERE, f"RUBRIC-{dest}.md"), "w", encoding="utf-8") as fh:
            fh.write(RUBRIC.format(item4=ITEM4[dest]))
        print(dest, len(key), "items")
    os.makedirs(RAW, exist_ok=True)


if __name__ == "__main__":
    main()
