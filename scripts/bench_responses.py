"""Export every stored benchmark response per model: Benchmark/responses/<model>.md.
Joins gateway/events.jsonl* (task_start: model, prompt, ts) with gateway/tasks.db (status, summary, detail)."""
import datetime as dt
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from gateway.config import DB_PATH, ROOT
from scripts.bench_real import cases

OUT = ROOT / "Benchmark" / "responses"


def main():
    by_prompt = {task: cid for cid, _a, _s, task, _c in cases()}
    starts = {}
    for p in (ROOT / "gateway" / "events.jsonl.1", ROOT / "gateway" / "events.jsonl"):
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("kind") == "task_start" and e.get("attempt", 1) == 1:
                    starts[e["id"]] = e
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    tasks = {r["id"]: r for r in db.execute("SELECT id,status,summary,detail,error FROM tasks")}
    per = defaultdict(lambda: defaultdict(list))
    for tid, e in starts.items():
        cid = by_prompt.get(e.get("prompt"))
        if cid and tid in tasks:
            per[e["model"]][cid].append((e["ts"], tid, tasks[tid]))
    order = [c[0] for c in cases()]
    OUT.mkdir(parents=True, exist_ok=True)
    idx = []
    for model, cs in sorted(per.items()):
        lines = [f"# {model}", "", "Every stored response, per case, oldest first. Pass/fail verification is in the model-comparison table; "
                 "`status` here is only whether the gateway returned an answer.", ""]
        n = 0
        for cid in order:
            for i, (ts, tid, t) in enumerate(sorted(cs.get(cid, []), key=lambda x: x[0]), 1):
                n += 1
                when = dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                body = (t["detail"] or t["summary"] or t["error"] or "(empty)").strip()
                lines += [f"## {cid} #{i}  ·  {when}  ·  task {tid}  ·  status {t['status']}", "", "````text", body[:4000], "````", ""]
        fn = re.sub(r"[^A-Za-z0-9._-]+", "_", model) + ".md"
        (OUT / fn).write_text("\n".join(lines), encoding="utf-8")
        idx.append(f"- [{model}]({fn}) — {n} responses")
    (OUT / "README.md").write_text("# Stored responses per model\n\n" + "\n".join(idx) + "\n", encoding="utf-8")
    print(f"{len(per)} models, {sum(len(v) for m in per.values() for v in m.values())} responses -> {OUT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
