"""Consolidate PRISM benchmark runs into bench/results.json.

Reads the converted bench JSON files (top-level keys tag, stamp, n, results),
builds one summary entry per run, and selects a default model per persona.

Output section choice: each persona is measured on the role that matches its
work. Code-oriented personas use results.output.builder; the rest use
results.output.thinker.

Selection rule per persona:
  score(tag)  = sum of verified passes (k of "k/n") over the persona's cases
  best        = max score across runs
  threshold   = 0.75 * best
  qualifying  = tags with score >= threshold
  default     = qualifying tag with smallest params, ties broken by smallest
                sum of realworld p50 seconds over the persona's cases
  best == 0   -> default is None
"""

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "bench" / "results.json"

PARAMS = {
    "prism-bonsai-1.7b-q1": 1.7,
    "prism-ternary-1.7b-q2": 1.7,
    "prism-bonsai-4b-q1": 4,
    "prism-ternary-4b-q2": 4,
    "prism-bonsai-8b-q1": 8,
    "prism-ternary-8b-q2": 8,
}

INPUTS = [
    "bench/prism-round2/20261011-161141-prism-bonsai-4b-q1.json",
    "bench/prism-round2/20261011-162234-prism-bonsai-1.7b-q1.json",
    "bench/prism-round2/20261011-162616-prism-ternary-1.7b-q2.json",
    "bench/prism-round2/20261011-163241-prism-bonsai-8b-q1.json",
    "bench/prism-round2/20261011-172151-prism-ternary-4b-q2.json",
    "bench/prism-ternary-8b-q2/20261011-174049-prism-ternary-8b-q2.json",
]

CASE_PERSONA = {
    "write_function": "engineering-backend-architect",
    "fix_bug": "engineering-backend-architect",
    "write_tests": "engineering-backend-architect",
    "rename_across_files": "engineering-backend-architect",
    "find_symbol": "engineering-backend-architect",
    "review_sqli": "testing-code-reviewer",
    "debug_trace": "engineering-sre",
    "summarize_readme": "engineering-technical-writer",
    "role_research": "support-docs-writer",
    "role_analyzer": "engineering-software-architect",
    "role_data": "gis-analyst",
    "role_docs": "engineering-technical-writer",
    "role_security": "security-auditor",
    "role_designer": "design-ui-designer",
    "role_browser": "testing-evidence-collector",
    "role_tracker": "project-management-project-shepherd",
}

BUILDER_CASES = {
    "write_function", "fix_bug", "write_tests", "rename_across_files", "find_symbol",
}


def _persona_cases(persona):
    return [c for c, p in CASE_PERSONA.items() if p == persona]


def _personas():
    seen = []
    for persona in CASE_PERSONA.values():
        if persona not in seen:
            seen.append(persona)
    return seen


def _persona_role(persona):
    return "builder" if any(c in BUILDER_CASES for c in _persona_cases(persona)) else "thinker"


def _passes(verified):
    return int(str(verified).split("/")[0])


def _total(verified):
    return int(str(verified).split("/")[1])


def load_run(path):
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    data = json.loads(path.read_text(encoding="utf-8"))
    tag = data["tag"]
    if tag not in PARAMS:
        raise KeyError(f"unknown tag {tag!r} in {path}")
    results = data["results"]
    realworld = results.get("realworld", {})
    cases = {}
    passes = 0
    total = 0
    for name, case in realworld.items():
        passes += _passes(case["verified"])
        total += _total(case["verified"])
        cases[name] = {
            "verified": case["verified"],
            "ran": case["ran"],
            "p50": float(case.get("s", {}).get("p50", 0.0)),
        }
    output = {}
    raw_output = results.get("output", {})
    for persona in _personas():
        role = _persona_role(persona)
        table = raw_output.get(role, {})
        output[persona] = {
            mt: {
                "tok_per_s": float(v["tok_per_s"]),
                "p50": float(v.get("s", {}).get("p50", 0.0)),
                "fails": int(v.get("fails", 0)),
            }
            for mt, v in table.items()
        }
    return {
        "tag": tag,
        "stamp": data["stamp"],
        "params": PARAMS[tag],
        "n": data["n"],
        "realworld_passes": passes,
        "realworld_total": total,
        "cases": cases,
        "output": output,
    }


def select_personas(runs):
    personas = {}
    for persona in _personas():
        cases = _persona_cases(persona)
        scores = {}
        p50_sum = {}
        for run in runs:
            tag = run["tag"]
            score = 0
            p50 = 0.0
            for c in cases:
                entry = run["cases"].get(c)
                if entry is None:
                    continue
                score += _passes(entry["verified"])
                p50 += entry["p50"]
            scores[tag] = score
            p50_sum[tag] = p50
        best = max(scores.values()) if scores else 0
        threshold = 0.75 * best
        if best == 0:
            qualifying = []
            default = None
        else:
            qualifying = [t for t in scores if scores[t] >= threshold]
            params_by_tag = {r["tag"]: r["params"] for r in runs}
            default = min(
                qualifying,
                key=lambda t: (params_by_tag[t], p50_sum[t], t),
            )
        personas[persona] = {
            "cases": cases,
            "scores": scores,
            "best": best,
            "threshold": threshold,
            "qualifying": qualifying,
            "default": default,
        }
    return personas


def _legacy_unconverted():
    legacy = []
    for path in sorted((REPO_ROOT / "bench").rglob("*.json")):
        if path == OUT_PATH:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            legacy.append(path.relative_to(REPO_ROOT).as_posix())
            continue
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, dict) or "realworld" not in results:
            legacy.append(path.relative_to(REPO_ROOT).as_posix())
    return legacy


def build(paths):
    runs = [load_run(p) for p in paths]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runs": runs,
        "personas": select_personas(runs),
        "legacy_unconverted": _legacy_unconverted(),
    }


def main():
    result = build(INPUTS)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
