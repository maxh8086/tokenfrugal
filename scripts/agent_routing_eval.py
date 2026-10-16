"""Evaluate keyword-based agent routing against labelled tasks."""

import argparse
import json
import re
import sys
from typing import Dict, List, Optional, Tuple

import yaml

SLUG_SECTIONS = ("agent_models", "overrides", "agent_skills")


def load_agent_slugs(agents_path: str) -> List[str]:
    """Return sorted union of agent slugs across the slug-keyed sections."""
    with open(agents_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    slugs = set()
    for section in SLUG_SECTIONS:
        slugs.update((data.get(section) or {}).keys())
    return sorted(slugs)


def keyword_route(task: str, slugs: List[str]) -> Optional[str]:
    """Pick the slug whose hyphen-separated parts best match task words."""
    task_tokens = set(re.findall(r"[a-z0-9]+", task.lower()))
    best_slug, best_count = None, 0
    for slug in sorted(slugs):
        count = sum(1 for part in slug.split("-") if len(part) >= 4 and part in task_tokens)
        if count > best_count:
            best_slug, best_count = slug, count
    return best_slug


def validate_labels(rows: List[Dict[str, str]], slugs: List[str]) -> List[Tuple[int, str]]:
    """Return (index, agent) for every row whose agent is not a known slug."""
    known = set(slugs)
    return [(i, row["persona"]) for i, row in enumerate(rows) if row["persona"] not in known]


def score_predictions(labels: List[str], predictions: List[Optional[str]]) -> Dict:
    """Score predictions against labels; a missing or None prediction is wrong."""
    total = len(labels)
    correct = 0
    per_agent: Dict[str, Dict[str, int]] = {}
    for i, label in enumerate(labels):
        pred = predictions[i] if i < len(predictions) else None
        stats = per_agent.setdefault(label, {"correct": 0, "total": 0})
        stats["total"] += 1
        if pred is not None and pred == label:
            correct += 1
            stats["correct"] += 1
    accuracy = correct / total if total else 0.0
    return {"accuracy": accuracy, "correct": correct, "total": total, "per_agent": per_agent}


def load_jsonl(path: str) -> List[Dict]:
    """Load a JSONL file, skipping blank lines."""
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _fmt(result: Dict) -> str:
    return f"{result['accuracy']:.3f} ({result['correct']}/{result['total']})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate keyword agent routing.")
    parser.add_argument("--agents", default="router/agents.yaml", help="agents YAML path")
    parser.add_argument("--labels", required=True, help="labels JSONL with 'task' and 'persona'")
    parser.add_argument("--predictions", help="predictions JSONL with 'persona'")
    args = parser.parse_args(argv)

    rows = load_jsonl(args.labels)
    slugs = load_agent_slugs(args.agents)

    bad = validate_labels(rows, slugs)
    if bad:
        for index, agent in bad:
            print(f"bad row {index}: unknown agent {agent!r}")
        return 2

    labels = [row["persona"] for row in rows]
    keyword_preds = [keyword_route(row["task"], slugs) for row in rows]
    print(f"keyword baseline accuracy: {_fmt(score_predictions(labels, keyword_preds))}")

    if args.predictions:
        pred_rows = load_jsonl(args.predictions)
        preds = [row.get("persona") for row in pred_rows]
        print(f"predictions accuracy: {_fmt(score_predictions(labels, preds))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
