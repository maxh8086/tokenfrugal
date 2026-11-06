"""SQLite task store: every task keeps its full result under task_id for follow-ups and resume."""
import json
import os
import re
import sqlite3
import time
import uuid

from .config import DB_PATH

HEARTBEAT_EVERY = 30  # seconds between heartbeats from a running router
STALE_AFTER = 120  # a running row with no heartbeat for this long belongs to a dead router
TEMPLATE_MAX = 2  # approved templates placed before one task
TEMPLATE_BUDGET_TOKENS = 1500  # their combined size; the rest of the 16-32k window is for the task and tool output


def _db():
    c = sqlite3.connect(DB_PATH, timeout=30)  # wait for concurrent writers instead of failing after Python's 5s default
    c.execute("PRAGMA journal_mode=WAL")  # readers and writers stop blocking each other
    c.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id TEXT PRIMARY KEY, agent TEXT, role TEXT, prompt TEXT, status TEXT,
        summary TEXT, detail TEXT, messages TEXT, error TEXT, attempts INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS templates(
        id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, task_type TEXT DEFAULT '',
        title TEXT NOT NULL, tags TEXT DEFAULT '[]', body TEXT NOT NULL, source_task_id TEXT DEFAULT '',
        status TEXT DEFAULT 'approved', approved_by TEXT DEFAULT '', approved_at REAL,
        uses INTEGER DEFAULT 0, last_used REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS runs(
        id TEXT PRIMARY KEY, slug TEXT NOT NULL, action TEXT NOT NULL, params TEXT DEFAULT '{}',
        status TEXT NOT NULL, stage TEXT DEFAULT '', error TEXT DEFAULT '', cancel_requested INTEGER DEFAULT 0,
        created_at REAL, updated_at REAL, heartbeat REAL, finished_at REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS quota(
        day TEXT NOT NULL, tool TEXT NOT NULL, calls INTEGER DEFAULT 0, units INTEGER DEFAULT 0,
        PRIMARY KEY(day, tool))""")
    for column in ("trail TEXT", "heartbeat REAL", "error_kind TEXT", "run_id TEXT"):  # databases created before these columns existed
        try:
            c.execute(f"ALTER TABLE tasks ADD COLUMN {column}")
        except sqlite3.OperationalError:
            pass
    return c


def create(agent, role, prompt, run_id: str | None = None) -> str:
    tid = uuid.uuid4().hex[:10]
    with _db() as c:
        c.execute("INSERT INTO tasks(id,agent,role,prompt,status,heartbeat,run_id) VALUES(?,?,?,?,'running',?,?)",
                  (tid, agent, role, prompt, time.time(), run_id))
    return tid


def beat(tid) -> None:
    """Show that the router running this task is alive. Called every HEARTBEAT_EVERY seconds while it runs."""
    with _db() as c:
        c.execute("UPDATE tasks SET heartbeat=? WHERE id=? AND status='running'", (time.time(), tid))


def update(tid, **kw):
    if "messages" in kw:
        kw["messages"] = json.dumps(kw["messages"])
    sets = ",".join(f"{k}=?" for k in kw)
    with _db() as c:
        c.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*kw.values(), tid))


TRAIL_MAX = 200  # newest events kept per task; older ones are dropped


def append_trail(tid, event: dict) -> None:
    """Keep the step-by-step event trail (step, tool, retry, fail) so get_detail can explain a failed run."""
    with _db() as c:
        r = c.execute("SELECT trail FROM tasks WHERE id=?", (tid,)).fetchone()
        if not r:
            return
        trail = (json.loads(r[0]) if r[0] else []) + [event]
        c.execute("UPDATE tasks SET trail=? WHERE id=?", (json.dumps(trail[-TRAIL_MAX:], ensure_ascii=False), tid))


def sweep_stale(reason: str, stale_after: float = STALE_AFTER) -> int:
    """Mark 'running' tasks whose router stopped heartbeating as failed. Live gateways keep their rows fresh, so this is safe with several gateways running. Rows without a heartbeat count as stale."""
    cutoff = time.time() - stale_after
    with _db() as c:
        runs = c.execute("UPDATE runs SET status='failed', error=?, finished_at=? WHERE status IN (%s) AND (heartbeat IS NULL OR heartbeat < ?)"
                         % ",".join("?" * len(ACTIVE)), (reason, time.time(), *ACTIVE, cutoff)).rowcount
        tasks = c.execute("UPDATE tasks SET status='failed', error=?, error_kind='error' WHERE status='running' AND (heartbeat IS NULL OR heartbeat < ?)",
                          (reason, cutoff)).rowcount
    return tasks + runs


def last_for(agent, slug: str | None = None) -> dict | None:
    """Newest task row for one agent slug (id and status only), or None. Used to resume a pipeline stage.
    With slug, only rows of runs for that slug count, so a second slug never reuses another slug's stages."""
    with _db() as c:
        if slug is None:
            r = c.execute("SELECT id, status FROM tasks WHERE agent=? ORDER BY rowid DESC LIMIT 1", (agent,)).fetchone()
        else:
            r = c.execute("SELECT t.id, t.status FROM tasks t JOIN runs r ON r.id = t.run_id "
                          "WHERE t.agent=? AND r.slug=? ORDER BY t.rowid DESC LIMIT 1", (agent, slug)).fetchone()
    return {"id": r[0], "status": r[1]} if r else None


# ---- runs (Studio and command-line pipeline runs) ----
ACTIVE = ("queued", "waiting_gpu", "running", "cancelling")  # a run in one of these states blocks a new start
RUN_STATES = ACTIVE + ("done", "failed", "cancelled")


def create_run(slug: str, action: str, params: dict | None = None) -> str:
    rid = uuid.uuid4().hex[:10]
    now = time.time()
    with _db() as c:
        c.execute("INSERT INTO runs(id,slug,action,params,status,created_at,updated_at,heartbeat) VALUES(?,?,?,?,'queued',?,?,?)",
                  (rid, slug, action, json.dumps(params or {}, ensure_ascii=False), now, now, now))
    return rid


def set_run(rid: str, **kw) -> None:
    kw["updated_at"] = time.time()
    sets = ",".join(f"{k}=?" for k in kw)
    with _db() as c:
        c.execute(f"UPDATE runs SET {sets} WHERE id=?", (*kw.values(), rid))


def run_beat(rid: str) -> None:
    with _db() as c:
        c.execute("UPDATE runs SET heartbeat=? WHERE id=? AND status IN (%s)" % ",".join("?" * len(ACTIVE)),
                  (time.time(), rid, *ACTIVE))


def finish_run(rid: str, status: str, error: str = "") -> None:
    now = time.time()
    set_run(rid, status=status, error=error, finished_at=now)


def request_cancel(rid: str) -> bool:
    """Ask a run to stop at its next stage boundary. Returns False when the run is not active."""
    with _db() as c:
        return c.execute("UPDATE runs SET cancel_requested=1, status=CASE WHEN status='queued' THEN 'cancelled' ELSE 'cancelling' END, "
                         "updated_at=? WHERE id=? AND status IN (%s)" % ",".join("?" * len(ACTIVE)),
                         (time.time(), rid, *ACTIVE)).rowcount == 1


def cancel_requested(rid: str) -> bool:
    with _db() as c:
        r = c.execute("SELECT cancel_requested FROM runs WHERE id=?", (rid,)).fetchone()
    return bool(r and r[0])


def active_run() -> dict | None:
    """The run that holds the pipeline right now. A run whose heartbeat is stale belongs to a dead router and does not count."""
    cutoff = time.time() - STALE_AFTER
    with _db() as c:
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM runs WHERE status IN (%s) AND heartbeat >= ? ORDER BY created_at DESC LIMIT 1"
                      % ",".join("?" * len(ACTIVE)), (*ACTIVE, cutoff)).fetchone()
    return _run_dict(r) if r else None


def get_run(rid: str) -> dict | None:
    with _db() as c:
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
    return _run_dict(r) if r else None


def list_runs(limit: int = 10) -> list[dict]:
    with _db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_run_dict(r) for r in rows]


def _run_dict(r) -> dict:
    d = dict(r)
    d["params"] = json.loads(d.get("params") or "{}")
    d["cancel_requested"] = bool(d.get("cancel_requested"))
    return d


# ---- quota (YouTube Data API units, estimated) ----
def record_quota(day: str, tool: str, calls: int, units: int) -> None:
    with _db() as c:
        c.execute("INSERT INTO quota(day,tool,calls,units) VALUES(?,?,?,?) ON CONFLICT(day,tool) "
                  "DO UPDATE SET calls=calls+excluded.calls, units=units+excluded.units", (day, tool, calls, units))


def quota_day(day: str) -> list[dict]:
    with _db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT tool, calls, units FROM quota WHERE day=? ORDER BY tool", (day,)).fetchall()
    return [dict(r) for r in rows]


def get(tid) -> dict | None:
    with _db() as c:
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["messages"] = json.loads(d["messages"] or "[]")
    d["trail"] = json.loads(d.get("trail") or "[]")
    return d


def add_template(role: str, title: str, body: str, approved_by: str, task_type: str = "", tags: list[str] | None = None,
                 source_task_id: str = "") -> int:
    """Store an approved template. Manual approval only: approved_by must name the person who approved it."""
    if not approved_by.strip():
        raise ValueError("a template needs approved_by: nothing is stored without a manual approval")
    with _db() as c:
        cur = c.execute("INSERT INTO templates(role,task_type,title,tags,body,source_task_id,status,approved_by,approved_at)"
                        " VALUES(?,?,?,?,?,?, 'approved', ?, ?)",
                        (role, task_type, title, json.dumps(tags or []), body, source_task_id, approved_by, time.time()))
        return cur.lastrowid


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{3,}", text.lower()))


def _body(text: str) -> str:
    """A template body is text, or the path of a file that holds it."""
    if len(text) < 260 and os.path.isfile(text):
        with open(text, encoding="utf-8") as f:
            return f.read()
    return text


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1  # rough: about four characters per token


def pick_templates(role: str, task: str, task_type: str = "", limit: int = TEMPLATE_MAX,
                   budget: int = TEMPLATE_BUDGET_TOKENS) -> list[dict]:
    """Approved templates for this role that match the task, best first.
    Ranking: same task_type, then tag overlap, then keyword overlap with the title. A template with no match is never used."""
    words = _words(task)
    with _db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM templates WHERE role=? AND status='approved'", (role,)).fetchall()
    scored = []
    for r in rows:
        tag_hits = len(set(json.loads(r["tags"] or "[]")) & words)
        kw_hits = len(_words(r["title"]) & words)
        same_type = bool(task_type) and r["task_type"] == task_type
        if same_type or tag_hits or kw_hits:
            scored.append(((same_type, tag_hits, kw_hits), r))
    scored.sort(key=lambda s: s[0], reverse=True)
    picked, used = [], 0
    for _, r in scored:
        if len(picked) >= limit:
            break
        body = _body(r["body"])
        cost = estimate_tokens(body)
        if used + cost > budget:
            continue
        picked.append({"id": r["id"], "title": r["title"], "body": body})
        used += cost
    if picked:
        with _db() as c:
            c.executemany("UPDATE templates SET uses=uses+1, last_used=? WHERE id=?",
                          [(time.time(), p["id"]) for p in picked])
    return picked


def with_templates(role: str, task: str, task_type: str = "") -> str:
    """The prompt sent to the model: matching approved templates first, then the task text unchanged."""
    picked = pick_templates(role, task, task_type)
    if not picked:
        return task
    head = "\n\n".join(f"[template: {p['title']}]\n{p['body']}" for p in picked)
    return f"{head}\n\n[task]\n{task}"


def list_templates() -> list[dict]:
    """Approved templates, for display only. Nothing is applied from this list; a template runs only when pick_templates matches it."""
    with _db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT id, role, task_type, title, uses FROM templates WHERE status='approved' ORDER BY role, id").fetchall()
    return [dict(r) for r in rows]
