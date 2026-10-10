"""Browser-toolkit round: Chrome DevTools slim (A) vs Playwright (B) vs Playwright + Lighthouse only (C).
Does not touch gateway/personas.yaml: the role dict is overridden here.
Usage: PYTHONPATH=. python Benchmark/rounds/20261010-playwright-browser/run_pw.py <ollama-tag> [toolkit ...]
"""
import asyncio, json, sys, time
from pathlib import Path
import gateway.loop as L
from gateway.config import load_personas, resolve_role

RID = "20261010-playwright-browser"
OUT = Path(__file__).parent / "raw"
URL = "http://host.docker.internal:9101"
AGENT = "testing-evidence-collector"
PW_RULE = " Browser: call browser_navigate with `url` first, then browser_snapshot."
TOOLKITS = {
    "A-chrome-devtools": ("browser", ["navigate_page", "take_snapshot", "list_console_messages", "list_network_requests", "lighthouse_audit"], L.BROWSER_RULE),
    "B-playwright": ("browser-pw", ["browser_navigate", "browser_snapshot", "browser_click", "browser_fill_form", "browser_console_messages", "browser_network_requests"], PW_RULE),
    "C-playwright+lighthouse": ("browser-pwlh", ["browser_navigate", "browser_snapshot", "browser_click", "browser_fill_form", "browser_console_messages", "navigate_page", "lighthouse_audit"],
                                PW_RULE + " For performance scores use navigate_page then lighthouse_audit."),
}
has = lambda *w: (lambda a: all(x in a.lower() for x in w))
CASES = [  # id, task, check, toolkits that can do it
    ("pw_heading", f"Open {URL} and report the page heading.", has("acme dashboard"), "ABC"),
    ("pw_click", f"Open {URL}, click the 'Show details' button and report the text that appears.", has("order 4821"), "BC"),
    ("pw_login", f"Open {URL}, type 'sam' into the Username field, click 'Sign in' and report the welcome message.", has("welcome back, sam"), "BC"),
    ("pw_console", f"Open {URL} and report the console error message.", has("widget-init failed"), "ABC"),
    ("pw_network", f"Open {URL} and report which request failed and its HTTP status.", has("missing", "404"), "AB"),
    ("pw_perf", f"Run a Lighthouse audit on {URL} and report the performance score.", has("performance"), "AC"),
]


async def main(model, kits):
    cfg = load_personas()
    res = {}
    for kit in kits:
        prof, tools, rule = TOOLKITS[kit]
        L.BROWSER_RULE = rule
        for cid, task, chk, who in CASES:
            if kit[0] not in who:
                continue
            runs = []
            for i in range(2):  # n=2
                role = resolve_role(AGENT, cfg)
                role.update(model=model, profile=prof, tools=tools, role="browser", max_steps=8)
                t = time.time()
                try:
                    out, _ = await asyncio.wait_for(L.run(AGENT, role, task), 300)
                    good, note = chk(out), out[:100].replace("\n", " ")
                except BaseException as e:  # noqa: BLE001
                    good, note = False, f"{type(L.leaf(e)).__name__}: {str(L.leaf(e))[:90]}"
                dt = round(time.time() - t, 1)
                runs.append({"s": dt, "verified": bool(good), "note": note})
                print(f"{kit} {cid} #{i+1} {dt}s ok={good} {note}"[:190], flush=True)
            res.setdefault(kit, {})[cid] = {"verified": f"{sum(r['verified'] for r in runs)}/2", "s": round(sum(r['s'] for r in runs) / 2, 1), "runs": runs}
    OUT.mkdir(exist_ok=True)
    (OUT / f"{RID}-{model.replace(':', '-').replace('/', '-')}.json").write_text(json.dumps({"round": RID, "model": model, "results": res}, indent=1), encoding="utf-8")

asyncio.run(main(sys.argv[1], sys.argv[2:] or list(TOOLKITS)))
