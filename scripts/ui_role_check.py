"""Offline checks for the pending UI roles. No model is called.

Checks, per role in tf-roles.yaml `pending_roles` whose name starts with `ui-`:
  - no `model:` key (a model is assigned only after the live smoke passes)
  - `improve: gated` is set
  - each skill file exists and has a `## <role-name>` section
  - each tool is named in the role's profile file, or is a native server tool (warning only)

Usage: python scripts/ui_role_check.py [--strict]
Exit code 1 on any error (or any warning with --strict).
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TF_ROLES = ROOT / "router" / "tf-roles.yaml"
SKILLS = ROOT / "router" / "skills"
PROFILES = ROOT / "profiles"
PREFIX = "ui-"


def load_pending(tf_roles: Path = TF_ROLES) -> dict:
    cfg = yaml.safe_load(tf_roles.read_text(encoding="utf-8")) or {}
    return {k: v for k, v in (cfg.get("pending_roles") or {}).items() if k.startswith(PREFIX)}


def profile_text(profile: str, profiles: Path = PROFILES) -> str:
    p = profiles / f"{profile}.yaml"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def tool_in_profile(tool: str, text: str) -> bool:
    return re.search(rf"^\s*-\s*(name:\s*)?{re.escape(tool)}\s*$", text, re.MULTILINE) is not None


def check_role(name: str, entry: dict, *, skills: Path = SKILLS, profiles: Path = PROFILES) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if "model" in entry:
        errors.append("has a model key; assign a model only after the live smoke passes")
    if entry.get("improve") != "gated":
        errors.append("improve is not 'gated'")
    for s in entry.get("skills") or []:
        path = skills / s / "SKILL.md"
        if not path.exists():
            errors.append(f"skill file missing: {path}")
            continue
        if not re.search(rf"^## {re.escape(name)}\s*$", path.read_text(encoding="utf-8"), re.MULTILINE):
            errors.append(f"skill {s} has no '## {name}' section")
    profile = entry.get("profile")
    profile_names = profile if isinstance(profile, list) else [profile] if profile else []
    text = "\n".join(profile_text(p, profiles) for p in profile_names)
    native = set(entry.get("native") or [])
    if not native:  # native servers (sandbox, synaptree) expose their own tools, so only profile-only roles are checked
        for tool in entry.get("tools") or []:
            if not (text and tool_in_profile(tool, text)):
                warnings.append(f"tool '{tool}' not found in profile {profile_names}")
    return errors, warnings


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    pending = load_pending()
    if not pending:
        print("no ui- roles in pending_roles")
        return 0
    bad = 0
    for name, entry in pending.items():
        errors, warnings = check_role(name, entry)
        status = "FAIL" if errors else ("WARN" if warnings else "OK")
        print(f"{status:4} {name}")
        for e in errors:
            print(f"     error: {e}")
        for w in warnings:
            print(f"     warn:  {w}")
        bad += bool(errors) or (strict and bool(warnings))
    print(f"{len(pending)} role(s) checked, {bad} with problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
