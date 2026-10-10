"""SQLite task store: every task keeps its full result under task_id for follow-ups and resume."""
import json
import sqlite3
import uuid

from .config import DB_PATH


def _db():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id TEXT PRIMARY KEY, agent TEXT, role TEXT, prompt TEXT, status TEXT,
        summary TEXT, detail TEXT, messages TEXT, error TEXT, attempts INTEGER DEFAULT 0)""")
    try:  # databases created before the event trail existed
        c.execute("ALTER TABLE tasks ADD COLUMN trail TEXT")
    except sqlite3.OperationalError:
        pass
    return c


def create(agent, role, prompt) -> str:
    tid = uuid.uuid4().hex[:10]
    with _db() as c:
        c.execute("INSERT INTO tasks(id,agent,role,prompt,status) VALUES(?,?,?,?,'running')",
                  (tid, agent, role, prompt))
    return tid


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
