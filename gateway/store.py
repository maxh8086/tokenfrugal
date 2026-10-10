"""SQLite task store: every task keeps its full result under task_id for follow-ups and resume."""
import json
import sqlite3
import time
import uuid

from .config import DB_PATH

HEARTBEAT_EVERY = 30  # seconds between heartbeats from a running gateway
STALE_AFTER = 120  # a running row with no heartbeat for this long belongs to a dead gateway


def _db():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id TEXT PRIMARY KEY, agent TEXT, role TEXT, prompt TEXT, status TEXT,
        summary TEXT, detail TEXT, messages TEXT, error TEXT, attempts INTEGER DEFAULT 0)""")
    for column in ("trail TEXT", "heartbeat REAL"):  # databases created before these columns existed
        try:
            c.execute(f"ALTER TABLE tasks ADD COLUMN {column}")
        except sqlite3.OperationalError:
            pass
    return c


def create(agent, role, prompt) -> str:
    tid = uuid.uuid4().hex[:10]
    with _db() as c:
        c.execute("INSERT INTO tasks(id,agent,role,prompt,status,heartbeat) VALUES(?,?,?,?,'running',?)",
                  (tid, agent, role, prompt, time.time()))
    return tid


def beat(tid) -> None:
    """Show that the gateway running this task is alive. Called every HEARTBEAT_EVERY seconds while it runs."""
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
    """Mark 'running' tasks whose gateway stopped heartbeating as failed. Live gateways keep their rows fresh, so this is safe with several gateways running. Rows without a heartbeat count as stale."""
    cutoff = time.time() - stale_after
    with _db() as c:
        return c.execute("UPDATE tasks SET status='failed', error=? WHERE status='running' AND (heartbeat IS NULL OR heartbeat < ?)",
                         (reason, cutoff)).rowcount


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
