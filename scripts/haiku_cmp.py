"""Driver for the Haiku comparison: `setup` seeds all cases and prints tasks, `check` verifies results with the same checks as bench_real.
Usage: python -m scripts.haiku_cmp setup | check <case_id> [answer-file]"""
import json, sys
from scripts import bench_real as b

LOCAL = str(b.SCRATCH).replace("\\", "/")
def local(t): return t.replace(b.WS, LOCAL).replace(f"/workspace/{b.SYNAPTREE_PROJECT}", LOCAL.rsplit("/bench/scratch", 1)[0])
cs = {c[0]: c for c in b.cases()}
if sys.argv[1] == "setup":
    b.SCRATCH.mkdir(parents=True, exist_ok=True)
    out = {}
    for cid, agent, setup, task, check in cs.values():
        setup(); out[cid] = local(task)
    print(json.dumps(out, indent=1))
else:
    cid = sys.argv[2]
    ans = open(sys.argv[3], encoding="utf-8").read() if len(sys.argv) > 3 else ""
    ok, note = cs[cid][4](ans)
    print(cid, bool(ok), str(note)[:120])
