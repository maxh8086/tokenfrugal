"""Neo4j store for YouTube trend runs and seen-video tracking.

Neo4j Community runs a single database ("neo4j"), so this store does not use a
separate database. Its nodes carry the labels YtVideo and YtRun, which keeps
them apart from the plan store's Task and Run nodes.

Graph:
  (:YtVideo {video_id})                  one node per video, ever seen
  (:YtRun {run_id, region, at})          one node per discover run
  (:YtRun)-[:SAW {views, likes}]->(:YtVideo)

Every function takes a `run` callable, run(cypher, **params) -> list[dict].
`default_run()` builds it from router.plan so the plan store's driver and
credentials are reused. Tests pass a fake.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys


def default_run():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from router import plan

    def run(cypher, **params):
        return plan._q(cypher, **params)

    return run


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init(run) -> None:
    run("CREATE CONSTRAINT yt_video_id IF NOT EXISTS FOR (v:YtVideo) REQUIRE v.video_id IS UNIQUE")
    run("CREATE INDEX yt_run_id IF NOT EXISTS FOR (r:YtRun) ON (r.run_id)")


def seen_ids(run, video_ids) -> set:
    ids = [i for i in video_ids if i]
    if not ids:
        return set()
    rows = run("MATCH (v:YtVideo) WHERE v.video_id IN $ids RETURN v.video_id AS id", ids=ids)
    return {r["id"] for r in rows}


def record_run(run, run_id: str, region: str, items: list[dict]) -> dict:
    """Store one discover run. Returns {"new": n, "seen": n} for this run's videos."""
    ids = [it["video_id"] for it in items if it.get("video_id")]
    already = seen_ids(run, ids)
    run(
        "MERGE (r:YtRun {run_id: $run_id}) SET r.region = $region, r.at = $at",
        run_id=run_id, region=region, at=_now(),
    )
    rows = [
        {"video_id": it["video_id"], "title": it.get("title"),
         "channel_id": it.get("channel_id"), "channel_title": it.get("channel_title"),
         "published_at": it.get("published_at"), "views": int(it.get("views") or 0),
         "likes": int(it.get("likes") or 0)}
        for it in items if it.get("video_id")
    ]
    if rows:
        run(
            "UNWIND $rows AS row "
            "MERGE (v:YtVideo {video_id: row.video_id}) "
            "SET v.title = row.title, v.channel_id = row.channel_id, "
            "    v.channel_title = row.channel_title, v.published_at = row.published_at, "
            "    v.last_seen = $at "
            "WITH v, row "
            "MATCH (r:YtRun {run_id: $run_id}) "
            "MERGE (r)-[s:SAW]->(v) SET s.views = row.views, s.likes = row.likes",
            rows=rows, run_id=run_id, at=_now(),
        )
    new = len([i for i in ids if i not in already])
    return {"new": new, "seen": len(ids) - new}


def run_summary(run, run_id: str) -> list[dict]:
    """Videos linked to a run, highest views first."""
    return run(
        "MATCH (r:YtRun {run_id: $run_id})-[s:SAW]->(v:YtVideo) "
        "RETURN v.video_id AS video_id, v.title AS title, s.views AS views, s.likes AS likes "
        "ORDER BY s.views DESC",
        run_id=run_id,
    )
