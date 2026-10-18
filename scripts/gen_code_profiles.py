"""Generate profiles/code-l1..l6.yaml: one Docker MCP profile per coding level, reusing server entries from the
base profiles so image pins stay in one place. Each level carries only the servers its role needs."""
import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"

# level -> (description, [(base profile, server name)])
LEVELS = {
    1: ("L1 single-function fixes", [("build", "ts-fs-rw")]),
    2: ("L2 single-file features", [("build", "ts-fs-rw")]),
    3: ("L3 multi-file changes", [("build", "ts-fs-rw")]),
    4: ("L4 structural refactors", [("build", "ts-fs-rw"), ("analyze", "ast-grep")]),
    5: ("L5 debug from failing tests", [("build", "ts-fs-rw"), ("analyze", "ts-git"), ("debug", "sequentialthinking")]),
    6: ("L6 code-graph guided changes", [("build", "ts-fs-rw")]),
}


def _name(server: dict) -> str:
    return server.get("snapshot", {}).get("server", {}).get("name") or server.get("name", "")


def build(level: int) -> dict:
    _, picks = LEVELS[level]
    base = {}
    servers = []
    for prof, name in picks:
        data = base.setdefault(prof, yaml.safe_load((PROFILES / f"{prof}.yaml").read_text(encoding="utf-8")))
        entry = next(s for s in data["servers"] if _name(s) == name or s.get("name") == name)
        servers.append(copy.deepcopy(entry))
    first = base[picks[0][0]]
    return {"version": 1, "id": f"code-l{level}", "name": f"code-l{level}",
            "secrets": first["secrets"], "servers": servers}


def main() -> None:
    for lvl in LEVELS:
        out = PROFILES / f"code-l{lvl}.yaml"
        out.write_text(yaml.safe_dump(build(lvl), sort_keys=False, width=120), encoding="utf-8")
        print("wrote", out.name)


if __name__ == "__main__":
    main()
