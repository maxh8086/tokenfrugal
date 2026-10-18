"""Apply the benchmark ranking to the product: ui/index.html RANKED/DOTS and the router/agents.yaml default models.

    python Benchmark/script/update_recommendations.py [--dry-run]

Uses the same per-role ranking and status dots as build_report.py (all local runs in benchmark.csv).
The top model of each role (builder cases -> builder, thinker cases -> thinker) becomes the default.
"""
import re
import sys

from ranking import B, BUILDER_CASES, THINKER_CASES, DOT, _status, _sort_role, _role_agg

ROOT = B.parent
UI = ROOT / "ui" / "index.html"
AGENTS = ROOT / "router" / "agents.yaml"


def ranked(cases):
    return [(n, DOT[_status(m)]) for n, m in _sort_role(_role_agg(cases))]


def main(dry=False):
    picks = {"builder": ranked(BUILDER_CASES), "thinker": ranked(THINKER_CASES)}
    if not all(picks.values()):
        print("no ranked models in benchmark.csv; nothing changed")
        return 1
    q = lambda xs: "[" + ", ".join(f"'{x}'" for x in xs) + "]"
    body = "".join(f"    {k}: {q([n for n, _ in v])},{chr(10)}" for k, v in picks.items())
    ranked_js = "const RANKED = {" + chr(10) + body + "  };"
    dots_js = "const DOTS = { " + ", ".join(f"{k}: {q([d for _, d in v])}" for k, v in picks.items()) + " };"
    ui = UI.read_text(encoding="utf-8")
    ui2, n1 = re.subn(r"const RANKED = \{.*?\};", lambda m: ranked_js, ui, count=1, flags=re.S)
    ui2, n2 = re.subn(r"const DOTS = \{.*?\};", lambda m: dots_js, ui2, count=1, flags=re.S)
    if (n1, n2) != (1, 1):
        raise SystemExit("RANKED/DOTS not found in ui/index.html")
    ag = AGENTS.read_text(encoding="utf-8")
    ag2 = ag
    for role, v in picks.items():
        ag2, k = re.subn(rf"(?m)^(  {role}: ).*$", lambda m: m.group(1) + v[0][0], ag2, count=1)
        if k != 1:
            raise SystemExit(f"models.{role} not found in agents.yaml")
    for role, v in picks.items():
        print(f"{role}: default -> {v[0][1]} {v[0][0]}   (ranked: {', '.join(d + ' ' + n for n, d in v)})")
    if dry:
        print("dry run, no files written")
        return 0
    UI.write_text(ui2, encoding="utf-8")
    AGENTS.write_text(ag2, encoding="utf-8")
    print("updated ui/index.html and router/agents.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
