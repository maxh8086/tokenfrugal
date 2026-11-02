"""Run the content pipeline stages in order for one slug, in-process through the router.

Usage:
  python scripts/content_pipeline.py SLUG --topic "..."            # dry plan: prints stages, calls no model
  python scripts/content_pipeline.py SLUG --topic "..." --confirm  # runs the stages

The roles write their files under content/<slug>/ in the media workspace; this script writes nothing itself.
Each stage is dispatched the way dispatch_task does it (store row, then server._execute). A stage whose last
task failed or stopped is resumed from its saved messages; a stage whose last task is done is skipped.
The run stops at the first stage that does not finish.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from router import store  # noqa: E402
from router.config import load_tf_roles, resolve_role  # noqa: E402

# (stage name, slug) in run order. Stage 1 is the content-outline slug (role content-research, writes 01-research.md).
# Factcheck runs before draft because draft reads 02-facts.md.
STAGES = [
    ("outline", "content-outline"),
    ("factcheck", "content-factcheck"),
    ("draft", "content-draft"),
    ("critic", "content-critic"),
    ("humanize", "content-humanize"),
    ("antislop", "content-antislop"),
    ("executive", "content-executive"),
]
AUDIENCE = "CIOs, CTOs and Enterprise Architects"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


def stage_prompt(slug: str, stage_slug: str, topic: str) -> str:
    text = f"Task: slug={slug}."
    if stage_slug == "content-outline":
        text += f" Topic: {topic}. Audience: {AUDIENCE}."
    return text


def plan_lines(slug: str, topic: str, cfg: dict, last_of) -> list[str]:
    """One line per stage: role, model, time limit and what a run would do. last_of(slug) -> last task row or None."""
    lines = [f"Content pipeline for slug '{slug}' (topic: {topic!r})",
             f"Stage files go to content/{slug}/ under the media workspace (written by the roles)."]
    for i, (name, stage_slug) in enumerate(STAGES, 1):
        role = resolve_role(stage_slug, cfg)
        last = last_of(stage_slug)
        if last and last["status"] == "done":
            action = "done, skipped"
        elif last and last["status"] in ("failed", "running"):
            action = f"resume task {last['id']} ({last['status']})"
        else:
            action = "new run"
        lines.append(f"{i}. {name:<9} {stage_slug:<18} role {role['role']:<15} model {role['model']:<18} "
                     f"limit {role.get('timeout_s')}s  {action}")
    lines.append("Dry run: no model was called. Add --confirm to run the stages.")
    return lines


async def run_stage(slug: str, stage_slug: str, topic: str, last) -> tuple[str, str]:
    """Run or resume one stage. Returns (task_id, final status)."""
    from router import server  # imported here: it starts the router's MCP app only when a run is requested

    cfg = load_tf_roles()
    role = resolve_role(stage_slug, cfg)
    if last and last["status"] in ("failed", "running"):
        row = store.get(last["id"])
        tid = row["id"]
        await server._execute(tid, stage_slug, role, row["prompt"], row["messages"] or None)
    else:
        text = stage_prompt(slug, stage_slug, topic)
        tid = store.create(stage_slug, role["role"], text)
        await server._execute(tid, stage_slug, role, store.with_templates(role["role"], text), None)
    return tid, store.get(tid)["status"]


async def run_pipeline(slug: str, topic: str) -> int:
    cfg = load_tf_roles()
    for name, stage_slug in STAGES:
        last = store.last_for(stage_slug)
        if last and last["status"] == "done":
            print(f"{name}: done earlier (task {last['id']}), skipped", flush=True)
            continue
        tid, status = await run_stage(slug, stage_slug, topic, last)
        print(f"{name}: task {tid} {status}", flush=True)
        if status != "done":
            print(f"stopped at {name}; fix the cause and run again to resume", file=sys.stderr)
            return 1
    print(f"pipeline finished for {slug}; see content/{slug}/")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("slug", help="folder name under content/, e.g. ai-banking-2026")
    ap.add_argument("--topic", required=True, help="what the outline stage should cover")
    ap.add_argument("--confirm", action="store_true", help="call the models (default: print the plan only)")
    args = ap.parse_args(argv)
    if not SLUG_RE.match(args.slug):
        print(f"invalid slug {args.slug!r}: use lowercase letters, digits and hyphens", file=sys.stderr)
        return 2
    if not args.confirm:
        print("\n".join(plan_lines(args.slug, args.topic, load_tf_roles(), store.last_for)))
        return 0
    return asyncio.run(run_pipeline(args.slug, args.topic))


if __name__ == "__main__":
    sys.exit(main())
