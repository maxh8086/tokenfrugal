"""Evaluate keyword-based agent routing against labelled tasks.

Label file (``--labels``): JSONL, one object per non-blank line. Fields read by
this script, taken from ``validate_labels``, ``main`` and ``keyword_route``:

- ``task`` (str, required): the task text. Only read by ``keyword_route``.
- ``agent`` (str, required): the expected slug. Must be a known slug, i.e. a
  key of ``agent_models``, ``overrides`` or ``agent_skills`` in the agents
  YAML (``--agents``, default ``router/agents.yaml``). Any other field is ignored.

Predictions file (``--predictions``, optional): JSONL, one object per line, in the
same order as the labels. Only ``agent`` (str or missing/null) is read. Missing
or null means a miss. Missing lines past the end also count as misses.

Unknown label slugs are an error. The CLI prints ``bad row <index>: unknown agent
<slug>`` for each one (index is the 0-based position among non-blank label lines)
and exits 2 before scoring. Pass ``--allow-unknown`` to drop those rows from
scoring instead; the output then states how many rows were excluded and lists them.
Predictions are dropped at the same positions so the two stay aligned.
"""

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
    return [(i, row["agent"]) for i, row in enumerate(rows) if row["agent"] not in known]


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
    parser.add_argument("--labels", required=True, help="labels JSONL with 'task' and 'agent'")
    parser.add_argument("--predictions", help="predictions JSONL with 'agent'")
    parser.add_argument(
        "--allow-unknown",
        action="store_true",
        help="exclude rows whose agent is not a known slug (reported) instead of failing",
    )
    args = parser.parse_args(argv)

    rows = load_jsonl(args.labels)
    slugs = load_agent_slugs(args.agents)
    pred_rows = load_jsonl(args.predictions) if args.predictions else None

    bad = validate_labels(rows, slugs)
    if bad and not args.allow_unknown:
        for index, agent in bad:
            print(f"bad row {index}: unknown agent {agent!r}")
        return 2

    dropped = {index for index, _ in bad}
    keep = [i for i in range(len(rows)) if i not in dropped]
    if bad:
        print(f"excluded {len(bad)} row(s) with unknown agent from scoring:")
        for index, agent in bad:
            print(f"  bad row {index}: unknown agent {agent!r}")
        rows = [rows[i] for i in keep]
        if pred_rows is not None:
            pred_rows = [pred_rows[i] if i < len(pred_rows) else {} for i in keep]

    labels = [row["agent"] for row in rows]
    keyword_preds = [keyword_route(row["task"], slugs) for row in rows]
    print(f"keyword baseline accuracy: {_fmt(score_predictions(labels, keyword_preds))}")

    if pred_rows is not None:
        preds = [row.get("agent") for row in pred_rows]
        print(f"predictions accuracy: {_fmt(score_predictions(labels, preds))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
