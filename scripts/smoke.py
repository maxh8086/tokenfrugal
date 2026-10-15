"""Live smoke: one tiny task per role/profile. Usage: python scripts/smoke.py [--list] [role ...]"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from router.config import load_personas, resolve_role
from router.loop import leaf, run

CFG = load_personas()
TASKS = {
    "builder": ("engineering-backend-architect", "Read /workspace/README.md and name the first heading."),
    "analyzer": ("engineering-software-architect", "Use search_graph to find function resolve_role and say which file defines it."),
    "reviewer": ("engineering-code-reviewer", "Use git_diff on the workspace and say in one line whether anything changed."),
    "debugger": ("engineering-sre", "Read /workspace/router/loop.py and name the exception class it defines."),
    "docs": ("engineering-technical-writer", "Call read_file on /workspace/README.md and name its first heading."),
    "security": ("engineering-privacy-engineer", "Use search_files under /workspace to call search_files with path /workspace and pattern 'example', then list the matching file names."),
    "sonar": ("engineering-privacy-engineer", "Call search_sonar_issues_in_projects once and report how many issues it returned, or the error text it gave."),
    "data": ("engineering-data-engineer", "Call list_directory with path /workspace and name one file you see."),
    "designer": ("design-ui-designer", "Call high_level_overview and report what it says in one line."),
    "browser": ("design-persona-walkthrough", "Call navigate_page with url http://host.docker.internal:9100, then call take_snapshot and report the page title."),
    "tracker": ("project-management-project-shepherd", "Call plan_next and report the task it returns, or say there is no ready task."),
    "research": ("academic-historian", "Call web_search for 'python asyncio tutorial', then report the first result title."),
}


EXPECT = {'tracker': 'task', 'security': 'README', 'sonar': 'issue', 'reviewer': 'change', 'research': 'asyncio', 'browser': 'snapshot', 'builder': 'TokenFrugal', 'analyzer': 'config.py', 'debugger': 'LoopError', 'docs': 'TokenFrugal', 'data': 'README', 'designer': 'penpot'}


async def one(role_name):
    agent, task = TASKS[role_name]
    role = resolve_role(agent, CFG)
    t = time.time()
    try:
        out, _ = await asyncio.wait_for(run(agent, role, task), 900 if role_name in ("security", "sonar") else 240)
        ok = EXPECT.get(role_name, "").lower() in out.lower()
        return f"{'PASS' if ok else 'WRONG'} {role_name:9} {time.time()-t:5.0f}s {str(role.get('profile') or '-'):10} {out[:90]!r}"
    except BaseException as e:  # noqa: BLE001
        return f"FAIL {role_name:9} {time.time()-t:5.0f}s {str(role.get('profile') or '-'):10} {type(leaf(e)).__name__}: {str(leaf(e))[:120]}"


async def main():
    bad = 0
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    unknown = [n for n in names if n not in TASKS]
    if unknown:
        print(f"unknown role(s): {', '.join(unknown)}; known: {', '.join(TASKS)}", file=sys.stderr)
        return 2
    for r in (names or TASKS):
        line = await one(r)
        bad += not line.startswith("PASS")
        print(line, flush=True)
    return bad

if "--list" in sys.argv:
    for name in TASKS:
        print(name)
    sys.exit(0)

_rc = asyncio.run(main())
sys.exit(_rc if _rc == 2 else (1 if _rc else 0))
