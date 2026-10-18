"""Propose-and-gate skill learning. A candidate SKILL.md goes through four gates in order and is written to the
working tree only when all pass. It is never committed. Model and benchmark calls are injected so tests stub them.

Gates: (1) under 1.2k characters, (2) offline tests, (3) no regression on the level's cases at n>=3,
(4) reviewer approval: Sonnet 5.5 for L1-L3, Opus 5.5 for L4-L6. The reviewer returns a verdict only and cannot edit the skill."""
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from router.config import ROOT

MAX_CHARS = 1200
MIN_N = 3
SKILLS = ROOT / "router" / "skills"
CANDIDATES = ROOT / "router" / "skills_candidates"
REVIEWERS = {"low": "claude-sonnet-5-5", "high": "claude-opus-5-5"}


@dataclass
class Verdict:
    passed: bool
    gate: str  # length | tests | regression | review | ok
    reason: str


def level_of(skill):
    m = re.fullmatch(r"code-l([1-6])", skill)
    if not m:
        raise ValueError(f"not a leveled coding skill: {skill}")
    return int(m.group(1))


def reviewer_model(level):
    return REVIEWERS["low" if level <= 3 else "high"]


def save_candidate(skill, text, ts=None):
    ts = ts or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = CANDIDATES / skill / f"{ts}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def gate(skill, text, run_tests, run_bench, review, apply=True):
    """run_tests() -> (ok, output); run_bench(skill, text, level) -> {"n", "candidate", "baseline"} verified rates;
    review(model, skill, text) -> (approved, reason)."""
    level = level_of(skill)
    if len(text) >= MAX_CHARS:
        return Verdict(False, "length", f"{len(text)} chars, limit is under {MAX_CHARS}")
    ok, out = run_tests()
    if not ok:
        return Verdict(False, "tests", f"offline tests failed: {str(out)[-200:]}")
    b = run_bench(skill, text, level)
    if b["n"] < MIN_N:
        return Verdict(False, "regression", f"n={b['n']}, need n>={MIN_N}")
    if b["candidate"] < b["baseline"]:
        return Verdict(False, "regression", f"verified {b['candidate']:.2f} < baseline {b['baseline']:.2f}")
    approved, why = review(reviewer_model(level), skill, text)
    if not approved:
        return Verdict(False, "review", why)
    if apply:
        (SKILLS / skill / "SKILL.md").write_text(text, encoding="utf-8")
    return Verdict(True, "ok", why)
