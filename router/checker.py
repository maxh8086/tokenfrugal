"""Deterministic checks on a repo after a delegated change: git status, patch applicability, lint and acceptance command.
Reads git and the filesystem only; no model calls."""
import os
import subprocess

from router.lint import check_python


def files_changed(repo: str) -> list[str]:
    r = subprocess.run(["git", "-C", repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                       capture_output=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip())
    entries = r.stdout.decode("utf-8", "replace").split("\0")
    paths = set()
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        xy, path = e[:2], e[3:]
        if "R" in xy or "C" in xy:
            # rename/copy: the next NUL-separated field is the origin path; keep the new one
            i += 1
        paths.add(path)
    return sorted(paths)


def diff_applies(diff_text: str, repo: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(["git", "-C", repo, "apply", "--check", "-"], input=diff_text,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except subprocess.TimeoutExpired:
        return False, "timed out after 30s"
    if r.returncode == 0:
        return True, ""
    return False, (r.stderr or r.stdout).strip()[:300]


def lint_python(paths: list[str], repo: str) -> list[str]:
    problems = []
    for p in paths:
        full = os.path.join(repo, p)
        if not p.endswith(".py") or not os.path.isfile(full):
            continue
        with open(full, encoding="utf-8") as f:
            msg = check_python(f.read())
        if msg:
            problems.append(f"{p}: {msg}")
    return problems


def run_accept(cmd: list[str], repo: str, timeout: int = 120) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, out[-300:]


def check_deterministic(repo: str, accept_cmd: list[str] | None, diff_text: str | None, timeout: int = 120) -> dict:
    items = []
    if accept_cmd is not None:
        ok, detail = run_accept(accept_cmd, repo, timeout)
        items.append({"name": "accept", "tag": "deterministic", "passed": ok, "detail": detail})
    changed = files_changed(repo)
    problems = lint_python(changed, repo)
    items.append({"name": "lint", "tag": "deterministic", "passed": not problems,
                  "detail": "; ".join(problems) or "clean"})
    if diff_text is not None:
        ok, detail = diff_applies(diff_text, repo)
        items.append({"name": "diff_applies", "tag": "deterministic", "passed": ok, "detail": detail})
    items.append({"name": "files_changed", "tag": "deterministic", "passed": True,
                  "detail": ", ".join(changed) or "none"})
    return {"items": items, "passed": all(i["passed"] for i in items)}
