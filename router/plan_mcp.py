"""Worker-facing plan tools (stdio). Exposed to the local `tracker` role and the Haiku plan-worker, never to Claude."""
from fastmcp import FastMCP

from . import plan

mcp = FastMCP("plan")


def _safe(fn, *a, **kw) -> str:
    try:
        return fn(*a, **kw)
    except plan.PlanError as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        return f"error: {type(e).__name__}: {str(e)[:150]}"


@mcp.tool()
def plan_next() -> str:
    """Get the next ready pending task (all dependencies done), highest priority first."""
    return _safe(plan.next_task)


@mcp.tool()
def plan_claim(task_id: int) -> str:
    """Start a pending task whose dependencies are done (pending -> in_progress)."""
    return _safe(plan.claim, task_id, "worker")


@mcp.tool()
def plan_status(task_id: int) -> str:
    """Show a task's status, dependencies and recent runs."""
    return _safe(plan.status, task_id)


@mcp.tool()
def plan_blockers(task_id: int) -> str:
    """List unfinished dependencies that block a task."""
    return _safe(plan.blockers, task_id)


@mcp.tool()
def plan_done(task_id: int, evidence: str, note: str = "") -> str:
    """Mark a task done. evidence = a real git commit sha or a finished gateway task id."""
    return _safe(plan.done, task_id, evidence, note, "worker")


@mcp.tool()
def plan_note(task_id: int, text: str) -> str:
    """Attach a short progress note to a task."""
    return _safe(plan.note, task_id, text, "worker")


if __name__ == "__main__":
    mcp.run()
