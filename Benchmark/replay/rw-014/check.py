"""Replay task rw-014: scripts/persona_routing_eval.py scores keyword persona routing on fixtures (offline)."""
import contextlib
import io
import os
import sys
import tempfile

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

PERSONAS = """persona_models:
  engineering-backend-architect: model-a
  finance-analyst: model-b
overrides:
  engineering-sre: model-c
persona_skills:
  security-auditor: skill-a
  finance-analyst: skill-b
"""
SLUGS = ["engineering-backend-architect", "engineering-sre", "finance-analyst", "security-auditor"]
ROUTE_CASES = [
    ("Review the backend services", "engineering-backend-architect"),
    ("architect review", "engineering-backend-architect"),
    ("engineering finance", "engineering-backend-architect"),
    ("Security-AUDITOR, please", "security-auditor"),
    ("security auditor finance", "security-auditor"),
    ("sre", None),
    ("hello world", None),
    ("", None),
]


def fail(message):
    print("FAIL:", message)
    return 1


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def check_functions(pre, tmp):
    personas = os.path.join(tmp, "personas.yaml")
    write(personas, PERSONAS)
    got = pre.load_persona_slugs(personas)
    if list(got) != SLUGS:
        return "load_persona_slugs returned %r, expected %r" % (got, SLUGS)
    for task, want in ROUTE_CASES:
        got = pre.keyword_route(task, SLUGS[::-1])
        if got != want:
            return "keyword_route(%r) returned %r, expected %r" % (task, got, want)
    bad = pre.validate_labels([{"task": "review", "persona": p} for p in ("finance-analyst", "nope", None)], SLUGS)
    if [persona for _, persona in bad] != ["nope", None]:
        return "validate_labels returned %r" % (bad,)
    labels = ["a", "b", "b", "c"]
    want = {"accuracy": 0.5, "correct": 2, "total": 4,
            "per_persona": {"a": {"correct": 1, "total": 1}, "b": {"correct": 0, "total": 2}, "c": {"correct": 1, "total": 1}}}
    outcomes = []
    for representation in (labels, [{"task": "review", "persona": label} for label in labels]):
        try:
            score = pre.score_predictions(representation, ["a", "a", None, "c"])
        except (AttributeError, TypeError, KeyError) as exc:
            outcomes.append(repr(exc))
            continue
        if score == want:
            break
        outcomes.append(score)
    else:
        return "score_predictions produced %r, expected %r" % (outcomes, want)
    empty = pre.score_predictions([], [])
    if empty.get("accuracy") != 0.0 or empty.get("total") != 0 or empty.get("correct") != 0:
        return "score_predictions on empty input returned %r" % (empty,)
    rows = os.path.join(tmp, "rows.jsonl")
    write(rows, '{"persona": "a"}\n\n{"persona": "b"}\n')
    loaded = pre.load_jsonl(rows)
    if loaded != [{"persona": "a"}, {"persona": "b"}]:
        return "load_jsonl returned %r" % (loaded,)
    return ""


def check_main(pre, tmp):
    personas = os.path.join(tmp, "personas.yaml")
    labels = os.path.join(tmp, "labels.jsonl")
    bad = os.path.join(tmp, "bad.jsonl")
    preds = os.path.join(tmp, "preds.jsonl")
    write(personas, PERSONAS)
    write(labels, '{"persona": "finance-analyst", "task": "budget review"}\n{"persona": "security-auditor", "task": "audit"}\n')
    write(bad, '{"persona": "nope", "task": "budget review"}\n')
    write(preds, '{"persona": "finance-analyst"}\n{"persona": "security-auditor"}\n')
    with contextlib.redirect_stdout(io.StringIO()):
        codes = [
            pre.main(["--personas", personas, "--labels", labels]),
            pre.main(["--personas", personas, "--labels", labels, "--predictions", preds]),
            pre.main(["--personas", personas, "--labels", bad]),
        ]
    if codes != [0, 0, 2]:
        return "main returned %r, expected [0, 0, 2]" % (codes,)
    return ""


def main():
    try:
        import scripts.persona_routing_eval as pre
    except Exception as exc:
        return fail("cannot import scripts.persona_routing_eval: %r" % (exc,))
    with tempfile.TemporaryDirectory() as tmp:
        try:
            problem = check_functions(pre, tmp) or check_main(pre, tmp)
        except Exception as exc:
            return fail("raised %r" % (exc,))
    if problem:
        return fail(problem)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
