"""Live smoke: one tiny task per role/profile. Usage: python -m scripts.smoke [role ...]"""
import asyncio
import sys
import time

from gateway.config import load_personas, resolve_role
from gateway.loop import leaf, run

CFG = load_personas()
TASKS = {
    "builder": ("engineering-backend-architect", "Read /workspace/README.md and name the first heading."),
    "analyzer": ("engineering-software-architect", "Use search_graph to find function resolve_role and say which file defines it."),
    "reviewer": ("engineering-code-reviewer", "Use git_diff on the workspace and say in one line whether anything changed."),
    "debugger": ("engineering-sre", "Read /workspace/gateway/loop.py and name the exception class it defines."),
    "docs": ("engineering-technical-writer", "List the files in the workspace root directory."),
    "security": ("engineering-privacy-engineer", "Use search_files under /workspace to call search_files with path /workspace and pattern 'example', then list the matching file names."),
    "data": ("engineering-data-engineer", "List the directory of the workspace root."),
    "designer": ("design-ui-designer", "Call high_level_overview and report what it says in one line."),
    "browser": ("design-persona-walkthrough", "Call navigate_page with url http://host.docker.internal:9100, then call take_snapshot and report the page title."),
    "tracker": ("project-management-project-shepherd", "Call plan_next and report the task it returns, or say there is no ready task."),
    "research": ("academic-historian", "Call web_search for 'python asyncio tutorial', then report the first result title."),
}


EXPECT = {'tracker': 'task', 'security': '.env.example', 'reviewer': 'change', 'research': 'asyncio', 'browser': 'Login', 'builder': 'TokenFrugal', 'analyzer': 'config.py', 'debugger': 'LoopError', 'docs': 'README', 'data': 'README', 'designer': 'penpot'}


async def one(role_name):
    agent, task = TASKS[role_name]
    role = resolve_role(agent, CFG)
    t = time.time()
    try:
        out, _ = await asyncio.wait_for(run(agent, role, task), 240)
        ok = EXPECT.get(role_name, "").lower() in out.lower()
        return f"{'PASS' if ok else 'WRONG'} {role_name:9} {time.time()-t:5.0f}s {role.get('profile') or '-':10} {out[:90]!r}"
    except BaseException as e:  # noqa: BLE001
        return f"FAIL {role_name:9} {time.time()-t:5.0f}s {role.get('profile') or '-':10} {type(leaf(e)).__name__}: {str(leaf(e))[:120]}"


async def main():
    for r in (sys.argv[1:] or TASKS):
        print(await one(r), flush=True)

asyncio.run(main())
