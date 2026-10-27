"""Gated self-improvement for tf-roles.

A role may propose a unified diff to its own skill files. A proposal is stored in
router/improvements/proposals.json and is never applied by the role. Only `approve`
applies one, after `git apply --check` passes. Nothing else writes to the repo.

  python -m scripts.role_improve propose <role> <diff_file> --reason "..."
  python -m scripts.role_improve list [--status proposed]
  python -m scripts.role_improve show <id>
  python -m scripts.role_improve approve <id>
  python -m scripts.role_improve reject <id> [--reason "..."]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TF_ROLES = ROOT / "router" / "tf-roles.yaml"
STORE = ROOT / "router" / "improvements" / "proposals.json"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _load_store(store: Path) -> list[dict]:
    if not store.exists():
        return []
    return json.loads(store.read_text(encoding="utf-8"))


def _save_store(store: Path, items: list[dict]) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _config(tf_roles: Path) -> dict:
    return yaml.safe_load(tf_roles.read_text(encoding="utf-8")) or {}


def allowed_paths(cfg: dict, role: str) -> set[str]:
    """Files a role's proposal may touch: its own skill files, and only the scopes the config allows."""
    si = cfg.get("self_improve") or {}
    if not si.get("enabled"):
        raise ValueError("self_improve is disabled in tf-roles.yaml")
    if si.get("gate") != "approval":
        raise ValueError("self_improve gate must be 'approval'")
    entry = (cfg.get("roles") or {}).get(role) or (cfg.get("pending_roles") or {}).get(role)
    if entry is None:
        raise ValueError(f"unknown role '{role}'")
    if entry.get("improve") != "gated":
        raise ValueError(f"role '{role}' is not opted in (improve: gated)")
    if "skills" not in (si.get("scope") or []):
        raise ValueError("skills are not in self_improve.scope")
    return {f"router/skills/{s}/SKILL.md" for s in entry.get("skills") or []}


def diff_paths(diff_text: str) -> set[str]:
    """Paths a unified diff touches, from its +++ / --- headers (a/ and b/ prefixes removed)."""
    out = set()
    for line in diff_text.splitlines():
        if line.startswith(("+++ ", "--- ")):
            p = line[4:].split("\t")[0].strip()
            if p == "/dev/null":
                continue
            if p.startswith(("a/", "b/")):
                p = p[2:]
            out.add(p.replace("\\", "/"))
    return out


def propose(role: str, diff_text: str, reason: str, *, tf_roles: Path = TF_ROLES, store: Path = STORE) -> dict:
    allowed = allowed_paths(_config(tf_roles), role)
    if not allowed:
        raise ValueError(f"role '{role}' has no skills to improve")
    touched = diff_paths(diff_text)
    if not touched:
        raise ValueError("diff has no file headers")
    bad = sorted(touched - allowed)
    if bad:
        raise ValueError(f"diff touches files outside '{role}' skills: {', '.join(bad)}")
    items = _load_store(store)
    item = {
        "id": max((i["id"] for i in items), default=0) + 1,
        "role": role,
        "reason": reason,
        "files": sorted(touched),
        "diff": diff_text,
        "status": "proposed",
        "created": _now(),
    }
    items.append(item)
    _save_store(store, items)
    return item


def _find(items: list[dict], pid: int) -> dict:
    for i in items:
        if i["id"] == pid:
            return i
    raise ValueError(f"no proposal {pid}")


def approve(pid: int, *, root: Path = ROOT, store: Path = STORE) -> dict:
    items = _load_store(store)
    item = _find(items, pid)
    if item["status"] != "proposed":
        raise ValueError(f"proposal {pid} is {item['status']}, not proposed")
    with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False, encoding="utf-8", newline="\n") as fh:
        fh.write(item["diff"])
        patch = fh.name
    try:
        check = subprocess.run(["git", "apply", "--check", "--recount", patch], cwd=root, capture_output=True, text=True)
        if check.returncode != 0:
            item["status"] = "failed"
            item["error"] = (check.stderr or check.stdout).strip()
            _save_store(store, items)
            raise ValueError(f"git apply --check failed: {item['error']}")
        subprocess.run(["git", "apply", "--recount", patch], cwd=root, check=True)
    finally:
        Path(patch).unlink(missing_ok=True)
    item["status"] = "applied"
    item["decided"] = _now()
    _save_store(store, items)
    return item


def reject(pid: int, reason: str = "", *, store: Path = STORE) -> dict:
    items = _load_store(store)
    item = _find(items, pid)
    if item["status"] != "proposed":
        raise ValueError(f"proposal {pid} is {item['status']}, not proposed")
    item["status"] = "rejected"
    item["decided"] = _now()
    if reason:
        item["reject_reason"] = reason
    _save_store(store, items)
    return item


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="role_improve", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("role")
    p.add_argument("diff_file")
    p.add_argument("--reason", required=True)
    p = sub.add_parser("list")
    p.add_argument("--status")
    p = sub.add_parser("show")
    p.add_argument("id", type=int)
    p = sub.add_parser("approve")
    p.add_argument("id", type=int)
    p = sub.add_parser("reject")
    p.add_argument("id", type=int)
    p.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "propose":
            item = propose(a.role, Path(a.diff_file).read_text(encoding="utf-8"), a.reason)
            print(f"proposal {item['id']} stored as proposed for {item['role']}: {', '.join(item['files'])}")
        elif a.cmd == "list":
            for i in _load_store(STORE):
                if a.status and i["status"] != a.status:
                    continue
                print(f"{i['id']}\t{i['status']}\t{i['role']}\t{i['created']}\t{i['reason']}")
        elif a.cmd == "show":
            print(json.dumps(_find(_load_store(STORE), a.id), indent=2, ensure_ascii=False))
        elif a.cmd == "approve":
            item = approve(a.id)
            print(f"applied proposal {item['id']}: {', '.join(item['files'])}")
        elif a.cmd == "reject":
            item = reject(a.id, a.reason)
            print(f"rejected proposal {item['id']}")
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
