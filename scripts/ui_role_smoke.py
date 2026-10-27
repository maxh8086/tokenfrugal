"""Live smoke for pending UI roles. Calls a local model. Run only after the user confirms.

Each role gets one small task on fixture files in the workspace, and the result is checked
on disk where the role writes files. Read-only browser roles (lighthouse, console, vision) only
check that the run finished, so their replies still need a manual read. Nothing is written to tf-roles.yaml: the role is
resolved from a copy of the config with the chosen model.

Usage:
  python scripts/ui_role_smoke.py --list
  python scripts/ui_role_smoke.py --model <ollama-tag-or-builder|thinker> --confirm [ui-layout ...]
  Needs CC_WORKSPACE set to a folder the file tools may write to. Fixtures go in <CC_WORKSPACE>/ui-smoke.
Without --confirm the script prints the plan and exits without any model call.
"""
import asyncio
import copy
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from router.config import load_tf_roles, resolve_role  # noqa: E402
from router.loop import leaf, run  # noqa: E402

import csv  # noqa: E402
import datetime as dt  # noqa: E402

FIXTURE_DIR = "ui-smoke"
# Own results file. benchmark.csv is not touched; rows are merged there only after the UI roles are final.
RESULTS = Path(__file__).resolve().parent.parent / "Benchmark" / "results" / "ui_roles.csv"
COLUMNS = ["date", "role", "model", "status", "seconds", "detail"]
SPEC = """# Spec
Page with a header and two columns on wide screens, one column on phones.
Use only the colour and spacing tokens from tokens.css.
"""
TOKENS = """:root {
  --color-bg: #ffffff;
  --color-text: #111111;
  --space-2: 8px;
  --space-4: 16px;
}
"""
PAGE_BAD = """<!doctype html><html><body><div style="color:#ff0000;padding:13px">Hello</div></body></html>
"""

# role -> (agency slug used for dispatch, task text, check(folder) -> bool)
TASKS = {
    "ui-components": ("ui-test-components",
        f"Read /workspace/{FIXTURE_DIR}/spec.md. Write /workspace/{FIXTURE_DIR}/button.html with one accessible button labelled 'Save'. Run run_tests, then report pass or the failure.",
        lambda d: "<button" in (d / "button.html").read_text(encoding="utf-8", errors="ignore").lower()),
    "ui-layout": ("ui-test-layout",
        f"Read /workspace/{FIXTURE_DIR}/spec.md and tokens.css. Write /workspace/{FIXTURE_DIR}/layout.html with a responsive two-column grid. Mobile first. Run run_tests, then report pass or the failure.",
        lambda d: "grid" in (d / "layout.html").read_text(encoding="utf-8", errors="ignore").lower()),
    "ui-polish": ("ui-test-polish",
        f"Read /workspace/{FIXTURE_DIR}/page.html. Replace the raw colour and px values with tokens from tokens.css. Edit only that file. Run run_tests, then report pass or the failure.",
        lambda d: "#ff0000" not in (d / "page.html").read_text(encoding="utf-8", errors="ignore").lower()),
    "ui-tokens": ("ui-test-tokens",
        f"Read /workspace/{FIXTURE_DIR}/spec.md. Write /workspace/{FIXTURE_DIR}/tokens2.css with primitive, semantic and component token layers. Run run_tests, then report pass or the failure.",
        lambda d: "--" in (d / "tokens2.css").read_text(encoding="utf-8", errors="ignore") if (d / "tokens2.css").exists() else False),
    "ui-tokens-check": ("ui-test-tokens-check",
        f"Search /workspace/{FIXTURE_DIR}/page.html for raw colour or px values. Report one line per raw value as file:line - value. Do not edit files.",
        lambda d: (d / "page.html").read_text(encoding="utf-8", errors="ignore") == PAGE_BAD),  # read-only: file unchanged
    "ui-a11y-check": ("ui-test-a11y",
        f"Audit /workspace/{FIXTURE_DIR}/page.html against the accessibility checklist. Do not edit files. Output file:line - rule - problem.",
        lambda d: (d / "page.html").read_text(encoding="utf-8", errors="ignore") == PAGE_BAD),  # file unchanged
    "ui-review-lighthouse": ("ui-test-lighthouse",
        "Navigate to {url}, run lighthouse_audit, and report the four scores.",
        lambda d: True),
    "ui-review-console": ("ui-test-console",
        "Navigate to {url}, list console messages, and report errors and warnings or 'pass'.",
        lambda d: True),
    "ui-vision-review": ("ui-test-vision",
        "Navigate to {url}, take a screenshot, and report up to 5 findings.",
        lambda d: True),
    "ui-webapp-test": ("ui-test-webapp",
        f"Write /workspace/{FIXTURE_DIR}/check.py, a Playwright script that opens {{url}} and asserts the page has a title. Run run_tests, then report pass or the failure.",
        lambda d: (d / "check.py").exists()),
}


def fixtures(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "spec.md").write_text(SPEC, encoding="utf-8")
    (folder / "tokens.css").write_text(TOKENS, encoding="utf-8")
    (folder / "page.html").write_text(PAGE_BAD, encoding="utf-8")


def record(rows: list[dict]) -> None:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    new = not RESULTS.exists()
    with RESULTS.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rows)


def config_for(name: str, slug: str, model: str) -> dict:
    """Copy of the live config with this one pending role made dispatchable on `model`. The file is not changed."""
    cfg = copy.deepcopy(load_tf_roles())
    entry = dict(yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "router" / "tf-roles.yaml").read_text(encoding="utf-8"))["pending_roles"][name])
    entry["model"] = model
    cfg["roles"][name] = entry
    cfg["models"].setdefault(model, model)
    cfg["overrides"][slug] = name
    return cfg


async def one(name: str, cfg_base_model: str, url: str, workspace: Path) -> str:
    slug, task, check = TASKS[name]
    cfg = config_for(name, slug, cfg_base_model)
    role = resolve_role(slug, cfg)
    folder = workspace / FIXTURE_DIR
    fixtures(folder)
    t = time.time()
    try:
        out, _ = await asyncio.wait_for(run(slug, role, task.format(url=url)), 240)
        ok = bool(check(folder))
        return f"{'PASS' if ok else 'FAIL'} {name:22} {time.time()-t:5.0f}s {out[:90]!r}"
    except BaseException as e:  # noqa: BLE001
        return f"ERROR {name:22} {time.time()-t:5.0f}s {type(leaf(e)).__name__}: {str(leaf(e))[:120]}"


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for n in TASKS:
            print(n)
        return 0
    model = argv[argv.index("--model") + 1] if "--model" in argv else None
    url = argv[argv.index("--url") + 1] if "--url" in argv else "http://host.docker.internal:9100"
    names = [a for a in argv if a in TASKS]
    unknown = [a for a in argv if a.startswith("ui-") and a not in TASKS]
    if unknown:
        print(f"unknown role(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    names = names or list(TASKS)
    if not model:
        print("--model is required (an Ollama tag, or builder/thinker)", file=sys.stderr)
        return 2
    if "--confirm" not in argv:
        print(f"plan: {len(names)} role(s) on model {model} against {url}: {', '.join(names)}")
        print("nothing run. Add --confirm to call the model.")
        return 0
    ws = os.environ.get("CC_WORKSPACE")
    if not ws:
        print("CC_WORKSPACE is not set", file=sys.stderr)
        return 2

    async def go():
        bad = 0
        rows = []
        for n in names:
            line = await one(n, model, url, Path(ws))
            bad += not line.startswith("PASS")
            print(line, flush=True)
            status, seconds, detail = line.split(" ", 1)[0], line.split()[2] if len(line.split()) > 2 else "", line
            rows.append({"date": dt.date.today().isoformat(), "role": n, "model": model,
                         "status": status, "seconds": seconds.rstrip("s"), "detail": detail[:200]})
        record(rows)
        print(f"results appended to {RESULTS}")
        return bad

    return 1 if asyncio.run(go()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
