"""Studio run backend (docs/designs/studio-and-collector-roles.md, Piece 2).

A start request is one JSON file in STUDIO_DIR/requests. poll_loop claims the oldest file with os.replace
(only one claimer can win a file), creates the run record and executes it. One run is active at a time:
a start is refused while a run is active or another request is waiting. Runs keep their state in the
`runs` table (store.py), so studio_status can report a run that was killed and restarted.

Actions: `collect` (the three collector roles), `pipeline` (the seven content stages for one slug),
`save_feed` (adds an RSS feed URL to the saved list; no run), `store` (writes today's collector files to Neo4j
through studio_store; docs/designs/studio-write-path.md).
"""
import asyncio
import ipaddress
import json
import os
import re
import socket
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from . import events, gpu_lease, media_workspace, secrets_store, store, studio_store
from .config import RSS_MAX_FEEDS, RSS_MAX_URL, STUDIO_CLAIM_TIMEOUT, STUDIO_DIR, load_tf_roles, resolve_role

POLL_SECONDS = 1  # how often poll_loop looks for a waiting request
GPU_POLL_SECONDS = 15  # how often a waiting run checks the GPU lease
RUN_ACTIONS = ("collect", "pipeline", "store")
ACTIONS = RUN_ACTIONS + ("save_feed",)
COLLECT_ROLES = {"reddit-hn": "content-analyst-reddit-hn", "rss": "content-analyst-rss", "youtube": "content-analyst-youtube"}
COLLECT_SLUG = "trends"  # collect runs write under content/trends/raw/
QUOTA_UNITS = {"searchVideos": 100, "getVideoDetails": 1}  # YouTube Data API units per call (estimated)
SOURCE_SECRETS = {"youtube": ["YOUTUBE_API_KEY"], "curator": ["DATABASE_URI"]}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
TOPIC_MAX = 300
_BLOCKED_HOSTS = ("localhost",)


class FeedRefused(ValueError):
    """A feed URL that must not be saved. The message says why, and never includes secrets."""


# ---- time and quota -------------------------------------------------------------------------------

def _nth_sunday(year: int, month: int, n: int) -> datetime:
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    first_sunday = first + timedelta(days=(6 - first.weekday()) % 7)
    return first_sunday + timedelta(weeks=n - 1)


def pacific_day(now: datetime | None = None) -> str:
    """Calendar date in US Pacific time, which is when the YouTube quota resets. Stdlib only (no tzdata needed).
    US rules: DST from the second Sunday of March 02:00 PST (10:00 UTC) to the first Sunday of November 02:00 PDT (09:00 UTC)."""
    utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    dst_start = _nth_sunday(utc.year, 3, 2).replace(hour=10)
    dst_end = _nth_sunday(utc.year, 11, 1).replace(hour=9)
    offset = -7 if dst_start <= utc < dst_end else -8
    return (utc + timedelta(hours=offset)).date().isoformat()


def record_quota_call(tool: str, now: datetime | None = None) -> None:
    """Count one successful YouTube call against today's Pacific date. Never raises: a quota write must not fail a task."""
    try:
        store.record_quota(pacific_day(now), tool, 1, QUOTA_UNITS.get(tool, 0))
    except Exception as exc:  # noqa: BLE001 - recording is best-effort
        events.emit("studio_error", error=f"quota record failed: {type(exc).__name__}")


# ---- RSS feed list --------------------------------------------------------------------------------

def _feeds_path():
    return STUDIO_DIR / "rss_feeds.json"


def load_feeds() -> list[str]:
    try:
        data = json.loads(_feeds_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [u for u in data.get("feeds", []) if isinstance(u, str)] if isinstance(data, dict) else []


def _write_feeds(feeds: list[str]) -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _feeds_path().with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(json.dumps({"feeds": feeds}, indent=2), encoding="utf-8")
    os.replace(tmp, _feeds_path())


def check_feed_url(url: str) -> str:
    """Return the cleaned URL, or raise FeedRefused. Only http/https; no loopback, private, link-local or reserved addresses."""
    url = (url or "").strip()
    if not url:
        raise FeedRefused("no feed URL given")
    if len(url) > RSS_MAX_URL:
        raise FeedRefused(f"feed URL is longer than {RSS_MAX_URL} characters")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise FeedRefused("feed URL is malformed") from None
    if parts.scheme not in ("http", "https"):
        raise FeedRefused("only http and https feeds are allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise FeedRefused("feed URL has no host")
    if host in _BLOCKED_HOSTS or host.endswith(".localhost"):
        raise FeedRefused("loopback host refused")
    try:
        infos = socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    except OSError:
        raise FeedRefused("feed host does not resolve") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise FeedRefused("private, loopback or link-local address refused")
    return url


def save_feed(url: str) -> str:
    cleaned = check_feed_url(url)
    feeds = load_feeds()
    if cleaned in feeds:
        return f"feed already saved ({len(feeds)} on the list)"
    if len(feeds) >= RSS_MAX_FEEDS:
        raise FeedRefused(f"the feed list is full ({RSS_MAX_FEEDS}); remove one first")
    _write_feeds(feeds + [cleaned])
    return f"feed saved ({len(feeds) + 1} on the list)"


# ---- secrets --------------------------------------------------------------------------------------

def secret_report(sources) -> list[str]:
    """Secret names the given sources need that have no file. Names only: never a value or a path."""
    wanted = sorted({name for src in sources for name in SOURCE_SECRETS.get(src, [])})
    return secrets_store.missing(wanted)


# ---- requests -------------------------------------------------------------------------------------

def _requests_dir():
    d = STUDIO_DIR / "requests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def validate_request(action: str, params: dict) -> str | None:
    """None when the request is acceptable, else the reason it is refused."""
    if action not in RUN_ACTIONS:
        return f"unknown action {action!r}; use collect, pipeline or store"
    if action == "pipeline":
        slug = params.get("slug", "")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            return "pipeline needs a slug: lowercase letters, digits and hyphens"
        topic = params.get("topic", "")
        if not isinstance(topic, str) or not topic.strip() or len(topic) > TOPIC_MAX:
            return f"pipeline needs a topic of 1 to {TOPIC_MAX} characters"
    if action == "collect":
        sources = params.get("sources") or list(COLLECT_ROLES)
        if not isinstance(sources, list) or not sources or any(s not in COLLECT_ROLES for s in sources):
            return f"collect sources must be a list of {', '.join(COLLECT_ROLES)}"
    return None


def enqueue(action: str, params: dict) -> dict:
    """Write one request file. Refused while a run is active or another request waits."""
    err = validate_request(action, params)
    if err:
        return {"ok": False, "message": err}
    active = store.active_run()
    if active:
        return {"ok": False, "message": f"run {active['id']} ({active['action']} for {active['slug']}) is {active['status']}; wait or cancel it first"}
    waiting = list(_requests_dir().glob("*.json"))
    if waiting:
        return {"ok": False, "message": "a request is already waiting to start; it runs first"}
    rid = uuid.uuid4().hex[:10]
    d = _requests_dir()
    tmp = d / f"{rid}.tmp"
    tmp.write_text(json.dumps({"id": rid, "action": action, "params": params}, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, d / f"{rid}.json")
    return {"ok": True, "message": f"request {rid} queued ({action}); the router starts it within a few seconds", "request": rid}


def _expire_requests(now: float) -> None:
    for p in _requests_dir().glob("*.json"):
        try:
            if now - p.stat().st_mtime > STUDIO_CLAIM_TIMEOUT:
                p.unlink()
                events.emit("studio_request_expired", request=p.stem)
        except OSError:
            continue


def claim_once(now: float | None = None) -> tuple[str, str, dict] | None:
    """Claim the oldest waiting request and create its run record. Returns (run_id, action, params), or None.
    os.replace moves the file to a claimed name, so a second claimer of the same file gets FileNotFoundError and moves on."""
    _expire_requests(now or time.time())
    if store.active_run():
        return None
    d = _requests_dir()
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    for p in files:
        claimed = p.with_name(f"{p.stem}.{os.getpid()}.claimed")
        try:
            os.replace(p, claimed)
        except FileNotFoundError:
            continue  # another claimer took it
        try:
            req = json.loads(claimed.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            req = None
        finally:
            claimed.unlink(missing_ok=True)
        if not isinstance(req, dict):
            events.emit("studio_error", error="request file unreadable; dropped")
            continue
        action, params = req.get("action", ""), req.get("params") or {}
        slug = params.get("slug") if action == "pipeline" else COLLECT_SLUG
        rid = store.create_run(str(slug or COLLECT_SLUG), action, params)
        err = validate_request(action, params)
        if err:
            store.finish_run(rid, "failed", err)
            return None
        return rid, action, params
    return None


# ---- execution ------------------------------------------------------------------------------------

async def _beat(rid: str) -> None:
    while True:
        store.run_beat(rid)
        await asyncio.sleep(store.HEARTBEAT_EVERY)


async def _wait_for_gpu(rid: str) -> bool:
    """Wait while the GPU lease is held. Returns False when the run was cancelled while waiting."""
    while True:
        if store.cancel_requested(rid):
            return False
        try:
            gpu_lease.check_for_ollama()
            return True
        except gpu_lease.GpuBusy:
            store.set_run(rid, status="waiting_gpu", stage="waiting_gpu")
            await asyncio.sleep(GPU_POLL_SECONDS)


async def _collect(rid: str, sources: list[str]) -> int:
    from router import server  # imported here: it starts the router's MCP app only when a run is requested

    cfg = load_tf_roles()
    missing = secret_report(sources)
    if missing:
        events.emit("studio_secret_missing", names=missing, run=rid)
    feeds = load_feeds() if "rss" in sources else []
    today = date.today().isoformat()
    failed = False
    for src in sources:
        if store.cancel_requested(rid):
            return 1
        store.set_run(rid, stage=f"collect:{src}")
        agent = COLLECT_ROLES[src]
        role = resolve_role(agent, cfg)
        task = f"Task: collect {src} items for {today}."
        if src == "rss":
            task += (" Feeds: " + ", ".join(feeds)) if feeds else " No feeds are saved; report that and stop."
        tid = store.create(agent, role["role"], task, run_id=rid)
        await server._execute(tid, agent, role, store.with_templates(role["role"], task, ""), None)
        if store.get(tid)["status"] != "done":
            failed = True
    return 1 if failed else 0


def store_collected(rid: str, day: str | None = None) -> int:
    """Store the collector files for one day (content/trends/raw/<day>-*.json) once each. Returns 0 or 1.
    A refusal ends the run as failed with the refusal text, which names an item index and never its content."""
    day = day or date.today().isoformat()
    raw = media_workspace.media_dir() / "content" / COLLECT_SLUG / "raw"
    files = sorted(raw.glob(f"{day}-*.json")) if raw.is_dir() else []
    try:
        rows: list[dict] = []
        for p in files:
            suffix = p.stem[len(day) + 1:]  # reddit-hn, rss or youtube
            rows.extend(studio_store.rows_from_raw(p, suffix if suffix in ("rss", "youtube") else None))
        if not rows:
            store.set_run(rid, stage="store:none")
            events.emit("studio_store", run=rid, files=len(files), stored=0)
            return 0
        store.set_run(rid, stage="store:embed")
        vectors = studio_store.embed([r["title"] + "\n" + r["body"][:2000] for r in rows])
        for r, vec in zip(rows, vectors):
            r["embedding"] = vec
        store.set_run(rid, stage="store:write")
        n = studio_store.write_items(studio_store.neo4j_write, rows, run_id=rid)
    except studio_store.StoreRefused as exc:
        store.finish_run(rid, "failed", str(exc)[:300])
        return 1
    events.emit("studio_store", run=rid, files=len(files), stored=n)
    return 0


async def execute(rid: str, action: str, params: dict) -> int:
    """Run one claimed request to its end state. Returns 0 when done, 1 otherwise."""
    beat = asyncio.create_task(_beat(rid))
    try:
        if action == "store":
            if store.cancel_requested(rid):
                store.finish_run(rid, "cancelled")
                return 1
            store.set_run(rid, status="running")
            rc = await asyncio.to_thread(store_collected, rid)
        elif action == "pipeline":
            if not await _wait_for_gpu(rid):
                store.finish_run(rid, "cancelled")
                return 1
            from scripts import content_pipeline  # the stage runner lives in scripts/
            rc = await content_pipeline.run_pipeline(params["slug"], params["topic"], run_id=rid)
        else:
            if store.cancel_requested(rid):
                store.finish_run(rid, "cancelled")
                return 1
            store.set_run(rid, status="running")
            rc = await _collect(rid, params.get("sources") or list(COLLECT_ROLES))
        run = store.get_run(rid)
        if run and run["status"] in store.ACTIVE:  # run_pipeline finishes its own run; collect does not
            if store.cancel_requested(rid):
                store.finish_run(rid, "cancelled")
            else:
                store.finish_run(rid, "done" if rc == 0 else "failed")
        return rc
    except BaseException as exc:
        store.finish_run(rid, "failed", f"{type(exc).__name__}: {exc}"[:300])
        raise
    finally:
        beat.cancel()


async def poll_loop() -> None:
    """Started by the router lifespan. One request at a time: the next claim waits for the current run to end."""
    while True:
        try:
            claimed = await asyncio.to_thread(claim_once)
            if claimed:
                rid, action, params = claimed
                if store.get_run(rid)["status"] == "queued":
                    await execute(rid, action, params)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop keeps running; the error is logged
            events.emit("studio_error", error=f"{type(exc).__name__}: {str(exc)[:160]}")
        await asyncio.sleep(POLL_SECONDS)


# ---- tool entry points ----------------------------------------------------------------------------

def start(action: str, slug: str = "", topic: str = "", sources: str = "", feed_url: str = "") -> str:
    """Body of the studio_run tool. Returns the text the tool sends back."""
    action = (action or "").strip()
    if action == "cancel":
        active = store.active_run()
        if not active:
            return "no active run to cancel"
        if store.request_cancel(active["id"]):
            return f"run {active['id']} will stop at its next stage boundary"
        return f"run {active['id']} is not cancellable now"
    if action == "save_feed":
        try:
            return save_feed(feed_url)
        except FeedRefused as exc:
            return f"feed refused: {exc}"
    if action == "store":
        params = {}
    elif action == "pipeline":
        params = {"slug": (slug or "").strip(), "topic": (topic or "").strip()}
    elif action == "collect":
        names = [s.strip() for s in (sources or "").split(",") if s.strip()]
        params = {"sources": names or list(COLLECT_ROLES)}
    else:
        params = {}
    return enqueue(action, params)["message"]


def status() -> dict:
    today = pacific_day()
    waiting = len(list(_requests_dir().glob("*.json")))
    return {
        "active": store.active_run(),
        "recent": store.list_runs(5),
        "waiting_requests": waiting,
        "quota": {"day": today, "rows": store.quota_day(today), "note": "estimated units, reset at Pacific midnight"},
        "missing_secrets": secret_report(list(SOURCE_SECRETS)),
    }


def format_status(st: dict) -> str:
    lines = []
    active = st["active"]
    lines.append(f"active: {active['id']} {active['action']} {active['slug']} {active['status']} stage={active['stage'] or '-'}"
                 if active else "active: none")
    lines.append(f"waiting requests: {st['waiting_requests']}")
    for r in st["recent"]:
        lines.append(f"run {r['id']} {r['action']} {r['slug']} {r['status']}" + (f" ({r['error']})" if r["error"] else ""))
    q = st["quota"]
    used = sum(row["units"] for row in q["rows"])
    lines.append(f"youtube quota {q['day']}: about {used} units (estimated)")
    if st["missing_secrets"]:
        lines.append("missing secrets: " + ", ".join(st["missing_secrets"])
                     + " (set with python -m router.secrets_store set NAME)")
    return "\n".join(lines)
