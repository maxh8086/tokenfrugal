"""Neo4j plan store: tasks, dependencies, runs and a status-event log (revert = undo events).

Graph: (:Task)-[:DEPENDS_ON]->(:Task), (:Task)-[:HAS_RUN]->(:Run), (:Task)-[:HAS_EVENT]->(:Event),
(:Task)-[:LINKED_TO]->(:Commit). Full run output stays in the SQLite store, linked by gateway_task_id.
All functions are synchronous and return compact text (or plain values where noted).
"""
import os
import re
import subprocess
import time
from datetime import datetime, timezone

from . import store

TAG = os.getenv("PLAN_TAG", "main")
RETENTION_DAYS = int(os.getenv("PLAN_RETENTION_DAYS", "30"))
URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7697")
STATUSES = ("pending", "in_progress", "done", "blocked", "cancelled")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
REPO = os.getenv("CC_WORKSPACE") or os.getcwd()
_driver = None


class PlanError(Exception):
    pass


def parse_auth(value: str | None) -> tuple[str, str]:
    """NEO4J_AUTH is 'user/password'."""
    if not value or "/" not in value:
        raise PlanError("NEO4J_AUTH not set (run scripts/mcp_up)")
    user, pw = value.split("/", 1)
    return user, pw


def _drv():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase
        _driver = GraphDatabase.driver(URI, auth=parse_auth(os.environ.get("NEO4J_AUTH")),
                                       notifications_min_severity="OFF")
    return _driver


def _q(cypher: str, **params) -> list[dict]:
    with _drv().session() as s:
        return [r.data() for r in s.run(cypher, **params)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def wait_ready(timeout: float = 60) -> None:
    end = time.time() + timeout
    while True:
        try:
            _drv().verify_connectivity()
            return
        except Exception as e:  # noqa: BLE001
            if time.time() > end:
                raise PlanError(f"neo4j not reachable: {e}") from e
            time.sleep(2)


def init() -> None:
    _q("CREATE CONSTRAINT task_id IF NOT EXISTS FOR (t:Task) REQUIRE t.id IS UNIQUE")
    _q("MERGE (c:Counter {name:'task'}) ON CREATE SET c.n = 0")


def check_evidence(evidence: str, repo: str | None = None) -> str:
    """Return a label for valid evidence ('commit' or 'run'), else raise PlanError."""
    ev = (evidence or "").strip()
    row = store.get(ev) if ev else None
    if row and row["status"] == "done":  # checked first: gateway ids are hex and look like short SHAs
        return "run"
    if SHA.match(ev):
        r = subprocess.run(["git", "-C", repo or REPO, "cat-file", "-e", f"{ev}^{{commit}}"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return "commit"
        raise PlanError(f"evidence {ev}: no such commit")
    raise PlanError("evidence must be an existing git commit sha or a finished gateway task id")


def add(title: str, depends: list[int] | None = None, priority: int = 0, detail: str = "", tag: str = "") -> str:
    tag = tag or TAG
    deps = [int(d) for d in depends or []]
    if deps:
        have = {r["id"] for r in _q("MATCH (t:Task) WHERE t.id IN $d RETURN t.id AS id", d=deps)}
        missing = [d for d in deps if d not in have]
        if missing:
            raise PlanError(f"unknown dependencies: {missing}")
    rows = _q("""MERGE (c:Counter {name:'task'}) SET c.n = coalesce(c.n,0)+1
                 WITH c CREATE (t:Task {id:c.n, tag:$tag, title:$title, detail:$detail, status:'pending',
                                        priority:$prio, created:$at, updated:$at})
                 WITH t UNWIND (CASE WHEN size($deps)=0 THEN [null] ELSE $deps END) AS d
                 OPTIONAL MATCH (x:Task {id:d}) FOREACH (_ IN CASE WHEN x IS NULL THEN [] ELSE [1] END |
                     CREATE (t)-[:DEPENDS_ON]->(x))
                 RETURN DISTINCT t.id AS id""", tag=tag, title=title, detail=detail, prio=int(priority), at=_now(), deps=deps)
    return f"task {rows[0]['id']} added"


def _event(task_id: int, new: str, allowed: tuple, by: str, note: str) -> bool:
    ts = time.time_ns()
    rows = _q("""MATCH (t:Task {id:$id}) WHERE t.status IN $allowed
                 CREATE (t)-[:HAS_EVENT]->(:Event {type:'status', old:t.status, new:$new, at:$at, ts:$ts,
                                                   by:$by, note:$note, undone:false})
                 SET t.status=$new, t.updated=$at RETURN t.id AS id""",
              id=int(task_id), allowed=list(allowed), new=new, at=_now(), ts=ts, by=by, note=note)
    return bool(rows)


def _status_of(task_id: int) -> str | None:
    rows = _q("MATCH (t:Task {id:$id}) RETURN t.status AS s", id=int(task_id))
    return rows[0]["s"] if rows else None


def set_status(task_id: int, new: str, by: str = "", note: str = "", allowed: tuple = STATUSES) -> str:
    if new not in STATUSES:
        raise PlanError(f"status must be one of {STATUSES}")
    if _event(task_id, new, allowed, by, note):
        return f"task {task_id} -> {new}"
    cur = _status_of(task_id)
    raise PlanError(f"unknown task {task_id}" if cur is None else f"task {task_id} is {cur}; cannot go to {new}")


def claim(task_id: int, by: str = "") -> str:
    blockers = _q("""MATCH (:Task {id:$id})-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
                     RETURN d.id AS id""", id=int(task_id))
    if blockers:
        raise PlanError(f"task {task_id} blocked by {[b['id'] for b in blockers]}")
    return set_status(task_id, "in_progress", by, "claimed", allowed=("pending",))


def done(task_id: int, evidence: str, note: str = "", by: str = "", repo: str | None = None) -> str:
    kind = check_evidence(evidence, repo)
    msg = set_status(task_id, "done", by, f"{kind}:{evidence} {note}".strip(),
                     allowed=("pending", "in_progress", "blocked"))
    if kind == "commit":
        _q("""MATCH (t:Task {id:$id}) MERGE (c:Commit {sha:$sha}) MERGE (t)-[:LINKED_TO]->(c)""",
           id=int(task_id), sha=evidence.strip())
    return msg


def next_task(tag: str = "") -> str:
    rows = _q("""MATCH (t:Task {tag:$tag, status:'pending'})
                 WHERE NOT EXISTS { MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done' }
                 RETURN t.id AS id, t.title AS title, t.detail AS detail, t.priority AS p
                 ORDER BY p DESC, id LIMIT 1""", tag=tag or TAG)
    if not rows:
        return "no ready task"
    r = rows[0]
    return f"next: {r['id']} {r['title']}" + (f" | {r['detail']}" if r["detail"] else "")


def record_run(task_id: int, gateway_task_id: str, agent: str, role: str, status: str,
               summary: str = "", error: str = "") -> None:
    _q("""MATCH (t:Task {id:$id}) CREATE (t)-[:HAS_RUN]->(:Run {gateway_task_id:$g, agent:$a, role:$r,
          status:$s, summary:$sum, error:$e, at:$at})""",
       id=int(task_id), g=gateway_task_id, a=agent, r=role, s=status, sum=summary[:600], e=error[:300], at=_now())


def status(task_id: int) -> str:
    rows = _q("""MATCH (t:Task {id:$id})
                 OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task)
                 OPTIONAL MATCH (t)-[:HAS_RUN]->(r:Run)
                 RETURN t.title AS title, t.status AS s, t.priority AS p,
                        collect(DISTINCT d.id + ':' + d.status) AS deps,
                        collect(DISTINCT r.gateway_task_id + ':' + r.status) AS runs""", id=int(task_id))
    if not rows or rows[0]["title"] is None:
        return f"unknown task {task_id}"
    r = rows[0]
    return (f"{task_id} [{r['s']}] {r['title']} | deps: {', '.join(map(str, r['deps'])) or '-'}"
            f" | runs: {', '.join(r['runs'][-3:]) or '-'}")


def blockers(task_id: int) -> str:
    rows = _q("""MATCH (:Task {id:$id})-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
                 RETURN d.id AS id, d.title AS title, d.status AS s ORDER BY id""", id=int(task_id))
    return "; ".join(f"{r['id']} [{r['s']}] {r['title']}" for r in rows) or "none"


def note(task_id: int, text: str, by: str = "") -> str:
    rows = _q("""MATCH (t:Task {id:$id}) CREATE (t)-[:HAS_EVENT]->(:Event {type:'note', note:$n, by:$by,
                 at:$at, ts:$ts, undone:false}) RETURN t.id AS id""",
              id=int(task_id), n=text[:500], by=by, at=_now(), ts=time.time_ns())
    if not rows:
        raise PlanError(f"unknown task {task_id}")
    return f"noted on {task_id}"


def overview(tag: str = "", limit: int = 25) -> str:
    tag = tag or TAG
    counts = _q("MATCH (t:Task {tag:$tag}) RETURN t.status AS s, count(*) AS n", tag=tag)
    rows = _q("""MATCH (t:Task {tag:$tag}) WHERE t.status <> 'done'
                 OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
                 RETURN t.id AS id, t.status AS s, t.title AS title, collect(d.id) AS wait
                 ORDER BY id LIMIT $lim""", tag=tag, lim=int(limit))
    head = ", ".join(f"{c['s']}={c['n']}" for c in counts) or "empty"
    lines = [f"{r['id']} [{r['s']}] {r['title']}" + (f" (waits {r['wait']})" if r["wait"] else "") for r in rows]
    return f"plan '{tag}': {head}" + ("\n" + "\n".join(lines) if lines else "")


def _undo(task_id: int, ts: int, by: str, note_: str) -> bool:
    rows = _q("""MATCH (t:Task {id:$id})-[:HAS_EVENT]->(e:Event {type:'status', ts:$ts, undone:false})
                 SET e.undone = true
                 CREATE (t)-[:HAS_EVENT]->(:Event {type:'revert', old:t.status, new:e.old, at:$at,
                                                   ts:$now, by:$by, note:$note, undone:false})
                 SET t.status = e.old, t.updated = $at RETURN t.id AS id""",
              id=int(task_id), ts=ts, at=_now(), now=time.time_ns(), by=by, note=note_)
    return bool(rows)


def revert(task_id: int, by: str = "claude") -> str:
    """Undo the latest not-yet-undone status change of one task."""
    rows = _q("""MATCH (:Task {id:$id})-[:HAS_EVENT]->(e:Event {type:'status', undone:false})
                 RETURN e.ts AS ts, e.old AS old, e.new AS new ORDER BY ts DESC LIMIT 1""", id=int(task_id))
    if not rows:
        return f"task {task_id}: nothing to revert"
    e = rows[0]
    _undo(task_id, e["ts"], by, f"revert {e['new']}->{e['old']}")
    return f"task {task_id}: {e['new']} -> {e['old']}"


def rollback(since: str, tag: str = "", by: str = "claude") -> str:
    """Undo every status change in a plan made after an ISO timestamp."""
    try:
        dt = datetime.fromisoformat(since)
        cut = int((dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp() * 1e9)
    except ValueError as e:
        raise PlanError(f"since must be ISO time, e.g. 2026-10-08T12:00:00 ({e})") from e
    rows = _q("""MATCH (t:Task {tag:$tag})-[:HAS_EVENT]->(e:Event {type:'status', undone:false})
                 WHERE e.ts > $cut RETURN t.id AS id, e.ts AS ts ORDER BY ts DESC""", tag=tag or TAG, cut=cut)
    n = sum(_undo(r["id"], r["ts"], by, f"rollback since {since}") for r in rows)
    return f"rolled back {n} change(s) since {since}"


def update_from(task_id: int, by: str = "claude") -> str:
    """Re-open a task and every task that depends on it (transitively) that was started or done."""
    rows = _q("""MATCH (d:Task)-[:DEPENDS_ON*0..]->(:Task {id:$id})
                 WHERE d.status IN ['done','in_progress','blocked'] RETURN DISTINCT d.id AS id ORDER BY id""",
              id=int(task_id))
    for r in rows:
        _event(r["id"], "pending", STATUSES, by, f"update_from {task_id}")
    return f"re-opened {[r['id'] for r in rows]}"


def prune(days: int | None = None) -> str:
    """Delete finished (done/cancelled) tasks untouched for `days`, with their runs/events, unless an open task depends on them."""
    days = RETENTION_DAYS if days is None else days
    if days <= 0:
        return "retention off"
    cut = datetime.fromtimestamp(time.time() - days * 86400, timezone.utc).isoformat(timespec="seconds")
    rows = _q("""MATCH (t:Task) WHERE t.status IN ['done','cancelled'] AND t.updated < $cut
                 AND NOT EXISTS { MATCH (o:Task)-[:DEPENDS_ON]->(t) WHERE NOT o.status IN ['done','cancelled'] }
                 OPTIONAL MATCH (t)-[:HAS_RUN]->(r:Run) OPTIONAL MATCH (t)-[:HAS_EVENT]->(e:Event)
                 WITH t, collect(DISTINCT r) AS rs, collect(DISTINCT e) AS es
                 FOREACH (x IN rs | DETACH DELETE x) FOREACH (x IN es | DETACH DELETE x)
                 DETACH DELETE t RETURN count(*) AS n""", cut=cut)
    n = rows[0]["n"] if rows else 0
    return f"pruned {n} task(s) older than {days}d"


def checkpoint(tag: str = "") -> str:
    """When every task in the tag is finished, prune it (retention applies); called after each completion."""
    rows = _q("""MATCH (t:Task {tag:$tag}) WHERE NOT t.status IN ['done','cancelled'] RETURN count(t) AS n""", tag=tag or TAG)
    return prune() if rows and rows[0]["n"] == 0 else "open tasks remain"
