"""Live Neo4j smoke for the plan store (prune, checkpoint, dependency guard, evidence).
Usage: scripts/mcp_up.sh plan  (or .ps1), then: python -m scripts.smoke_plan
Uses a throwaway tag and a ~55-year retention window, so it can only ever delete its own back-dated tasks.
"""
import subprocess
import sys
import time

from gateway import plan

OLD = "1960-01-01T00:00:00+00:00"
TAG = f"smoke-{int(time.time())}"
fails = []


def check(name, cond, got=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else f"-> {got!r}")
    if not cond:
        fails.append(name)


def count(status=None):
    q = "MATCH (t:Task {tag:$tag}) " + ("WHERE t.status=$s " if status else "") + "RETURN count(t) AS n"
    return plan._q(q, tag=TAG, s=status)[0]["n"]


def tid(msg):
    return int(msg.split()[1])


def main():
    plan.wait_ready()
    plan.init()
    base = plan._q("MATCH (e:Event) WHERE NOT (e)<-[:HAS_EVENT]-() RETURN count(e) AS n")[0]["n"]
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=plan.REPO).stdout.strip()
    try:
        a = tid(plan.add("smoke A", tag=TAG))
        b = tid(plan.add("smoke B (needs A)", depends=[a], tag=TAG))
        check("done without evidence is refused", _raises(lambda: plan.done(a, "nothing")))
        plan.claim(a, by="smoke")
        plan.done(a, sha, by="smoke")
        check("A done with real commit", count("done") == 1)
        check("checkpoint keeps open tasks", plan.checkpoint(TAG) == "open tasks remain")

        plan._q("MATCH (t:Task {id:$i}) SET t.updated=$old", i=a, old=OLD)
        plan.prune(20000)
        check("prune spares done task that an open task depends on", count("done") == 1)

        plan.claim(b, by="smoke")
        plan.done(b, sha, by="smoke")
        plan._q("MATCH (t:Task {tag:$tag}) SET t.updated=$old", tag=TAG, old=OLD)
        old, plan.RETENTION_DAYS = plan.RETENTION_DAYS, 20000
        try:
            out = plan.checkpoint(TAG)
        finally:
            plan.RETENTION_DAYS = old
        check("checkpoint prunes finished tag", out.startswith("pruned") and count() == 0, out)
        orphans = plan._q("MATCH (e:Event) WHERE NOT (e)<-[:HAS_EVENT]-() RETURN count(e) AS n")[0]["n"]
        check("prune leaves no new orphaned events", orphans <= base, (base, orphans))
    finally:
        plan._q("MATCH (t:Task {tag:$tag}) DETACH DELETE t", tag=TAG)
    print("smoke_plan:", "OK" if not fails else f"{len(fails)} failed")
    return 1 if fails else 0


def _raises(fn):
    try:
        fn()
    except plan.PlanError:
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
