"""Append-only activity log for the Node dashboard (ui/server.js). Never raises: the UI is optional."""
import json
import os
import time
from pathlib import Path

import yaml

from .config import COMPOSE_PROJECT, OLLAMA_URL, ROOT

EVENTS_PATH = Path(os.getenv("GATEWAY_EVENTS", Path(__file__).parent / "events.jsonl"))
ROLES_PATH = EVENTS_PATH.with_name("roles.json")
UI_TEXT = Path(__file__).parent / "ui.yaml"
MAX_BYTES = 2_000_000
USAGE_FIELDS = ("ts", "pid", "kind", "id", "role", "model", "saved", "task", "agent", "calls", "input", "output")  # long-term ledger for the dashboard usage popup


def emit(kind: str, **fields) -> None:
    """kind: task_start | step | tool | say | task_done | task_failed. Every line carries ts and the gateway pid."""
    try:
        if EVENTS_PATH.exists() and EVENTS_PATH.stat().st_size > MAX_BYTES:
            os.replace(EVENTS_PATH, EVENTS_PATH.with_suffix(".jsonl.1"))
        line = json.dumps({"ts": time.time(), "pid": os.getpid(), "kind": kind, **fields}, ensure_ascii=False)
        with EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        if kind in ("task_done", "task_failed"):  # events.jsonl rotates; usage.jsonl keeps month-long totals
            row = {"ts": time.time(), "pid": os.getpid(), "kind": kind, **fields}
            with EVENTS_PATH.with_name("usage.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({k: row[k] for k in USAGE_FIELDS if k in row}) + "\n")
    except (OSError, yaml.YAMLError):
        pass


def roles_rows(cfg: dict) -> list[dict]:
    return [{"role": k, "model": cfg["models"][v["model"]], "profile": v.get("profile") or "",
             "backends": v.get("compose", []), "native": v.get("native", []), "tools": v["tools"], "max_steps": v["max_steps"]}
            for k, v in cfg["roles"].items()]


def write_roles(cfg: dict) -> None:
    try:
        ROLES_PATH.write_text(json.dumps({"roles": roles_rows(cfg), "divisions": cfg["divisions"],
                                          "root": str(ROOT), "llm_url": OLLAMA_URL, "compose_project": COMPOSE_PROJECT,
                                          "ui": yaml.safe_load(UI_TEXT.read_text(encoding="utf-8"))}), encoding="utf-8")
    except (OSError, yaml.YAMLError):
        pass
