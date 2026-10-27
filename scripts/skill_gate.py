"""Propose-and-gate skill learning, in stages. A candidate SKILL.md goes through four gates; it is written to the working
tree only when all pass. It is never committed. Benchmark calls are injected so tests stub them.

Stage 1, prepare(): gates (1) under 1.2k characters, (2) offline tests, (3) no regression on the level's cases at n>=3.
  When all pass it writes a review request and saves the benchmark rates, then stops with status awaiting_review.
Stage 2, any agent: the reviewer writes the verdict file named in the request (see AGENTS.md). No API is called here.
Stage 3, finish(): gate (4) reads the verdict. It must match the candidate's SHA-256, and its reviewer_model must be one
  of REVIEWER_MODELS. Only then is the skill written (when apply=True).
"""
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from router.config import ROOT

MAX_CHARS = 1200
MIN_N = 3
SKILLS = ROOT / "router" / "skills"
CANDIDATES = ROOT / "router" / "skills_candidates"
REVIEWS = ROOT / "router" / "skills_review"
REVIEWER_MODELS = ("claude-sonnet-5-5", "claude-opus-5-5")  # the only models whose verdict is accepted, any level
SUGGESTED = {"low": "claude-sonnet-5-5", "high": "claude-opus-5-5"}  # the model the request asks for: L1-L3 / L4-L6


@dataclass
class Verdict:
    passed: bool | None  # None: waiting for a reviewer
    gate: str  # length | tests | floor | regression | awaiting_review | review | verdict | ok
    reason: str


def _partial(b):
    """Partial-credit line for the report, from optional keys the bench may add; empty when it adds none."""
    keys = ("tests_passed", "tests_total", "first_edit_step", "tool_errors")
    got = {k: b[k] for k in keys if k in b}
    return "" if not got else "; partial: " + ", ".join(f"{k}={v}" for k, v in got.items())


def level_of(skill):
    m = re.fullmatch(r"code-l([1-6])", skill)
    if not m:
        raise ValueError(f"not a leveled coding skill: {skill}")
    return int(m.group(1))


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_candidate(skill, text, ts=None):
    ts = ts or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = CANDIDATES / skill / f"{ts}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def review_paths(skill, digest):
    d = REVIEWS / skill
    return {"request": d / f"{digest}.request.md", "state": d / f"{digest}.state.json", "verdict": d / f"{digest}.verdict.json"}


def request_text(skill, digest, text, level):
    return (f"# Skill review request: {skill}\n\n"
            f"candidate_sha256: {digest}\n"
            f"suggested reviewer model: {SUGGESTED['low' if level <= 3 else 'high']}\n\n"
            "## Your task\n\n"
            "Review the candidate note below for a small local coding model. Approve only if it is specific, does not "
            "change the task, and is safe to use. You cannot edit it.\n\n"
            f"Write the verdict to `{review_paths(skill, digest)['verdict'].name}` in this folder, as JSON with these "
            "fields: candidate_sha256 (copied from above), skill, approved (true or false), reason (one sentence), "
            "reviewer_tool (claude-code, codex or opencode), reviewer_model (the exact model id you run as). "
            "Change no other file. Procedure: AGENTS.md, section 'Skill gate review'.\n\n"
            "## Candidate\n\n```markdown\n" + text + "\n```\n")


def prepare(skill, text, run_tests, run_bench):
    """Stage 1. run_tests() -> (ok, output); run_bench(skill, text, level) -> {"n", "candidate", "baseline"} rates.
    Returns a final Verdict for a rejected candidate, or Verdict(None, "awaiting_review", request path)."""
    level = level_of(skill)
    path = save_candidate(skill, text)  # every proposal is kept, approved or not
    if len(text) >= MAX_CHARS:
        return Verdict(False, "length", f"{len(text)} chars, limit is under {MAX_CHARS}")
    ok, out = run_tests()
    if not ok:
        return Verdict(False, "tests", f"offline tests failed: {str(out)[-200:]}")
    b = run_bench(skill, text, level)
    if b["n"] < MIN_N:
        return Verdict(False, "regression", f"n={b['n']}, need n>={MIN_N}")
    if b["baseline"] == 0 and b["candidate"] == 0:  # both below floor: nothing to compare, not a regression
        return Verdict(False, "floor", f"baseline 0/{b['n']}: below floor, skill gate skipped{_partial(b)}")
    if b["candidate"] <= b["baseline"]:  # a tie is not an improvement
        return Verdict(False, "regression",
                       f"verified {b['candidate']:.2f} not above baseline {b['baseline']:.2f}{_partial(b)}")
    digest = sha256(text)
    p = review_paths(skill, digest)
    p["request"].parent.mkdir(parents=True, exist_ok=True)
    p["request"].write_text(request_text(skill, digest, text, level), encoding="utf-8")
    state = {"skill": skill, "sha256": digest, "candidate_path": str(path), "bench": b}
    p["state"].write_text(json.dumps(state, indent=1), encoding="utf-8")
    return Verdict(None, "awaiting_review", str(p["request"]))


def _latest_state(skill):
    files = sorted((REVIEWS / skill).glob("*.state.json"), key=lambda f: f.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"no prepared candidate for {skill}; run the gate without --finish first")
    return json.loads(files[-1].read_text(encoding="utf-8"))


def finish(skill, apply=True):
    """Stage 3. Reads the verdict for the newest prepared candidate and gate (4) decides. Writes the skill only when
    the verdict approves it and apply is True."""
    state = _latest_state(skill)
    digest = state["sha256"]
    text = Path(state["candidate_path"]).read_text(encoding="utf-8")
    if sha256(text) != digest:
        return Verdict(False, "verdict", "candidate file changed since it was prepared; run the gate again")
    verdict_file = review_paths(skill, digest)["verdict"]
    if not verdict_file.exists():
        return Verdict(None, "awaiting_review", f"no verdict yet; write {verdict_file}")
    try:
        v = json.loads(verdict_file.read_text(encoding="utf-8"))
    except ValueError as e:
        return Verdict(False, "verdict", f"verdict file is not valid JSON: {e}")
    if v.get("candidate_sha256") != digest:
        return Verdict(False, "verdict", "verdict is for a different candidate text")
    model = v.get("reviewer_model")
    if model not in REVIEWER_MODELS:
        return Verdict(False, "verdict", f"reviewer model '{model}' is not accepted; accepted: {', '.join(REVIEWER_MODELS)}")
    if not isinstance(v.get("approved"), bool):
        return Verdict(False, "verdict", "approved must be true or false")
    reason = str(v.get("reason", ""))
    if not v["approved"]:
        return Verdict(False, "review", reason)
    if apply:
        (SKILLS / skill / "SKILL.md").write_text(text, encoding="utf-8")
    return Verdict(True, "ok", reason)
