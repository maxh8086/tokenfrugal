import asyncio
import json
from collections import Counter

from .outcomes import Stop


class AcceptPolicy:
    """Track call repetition and the first accept result for a single model run."""

    def __init__(self, task_files, run_accept_fn, budget, *, normalize=str):
        self._normalize = normalize
        self._files = {normalize(path) for path in task_files}
        self._written = set()
        self._calls = Counter()
        self._tripped = False
        self._run_accept = run_accept_fn
        self._budget = budget
        self.last_result = None
        self.stale = False

    def before_call(self, name, args) -> str | None:
        key = (name, json.dumps(args, sort_keys=True))
        self._calls[key] += 1
        if self._calls[key] >= 3:
            self._tripped = True
            return "tool error: same call repeated 3 times with no write; change approach"
        return None

    async def after_tool(self, name, args, out) -> str:
        if (name not in ("write_file", "edit_file", "move_file") or out.startswith("tool error")
                or args.get("dryRun")):
            return out
        self._calls.clear()
        if self.last_result is not None:
            self.stale = True
            return out
        if name == "move_file":
            self._written.discard(self._normalize(args["source"]))
        self._written.add(self._normalize(args["destination" if name == "move_file" else "path"]))
        if self._files and self._files <= self._written and self._run_accept is not None:
            with self._budget.pause():
                self.last_result = await asyncio.to_thread(self._run_accept)
            if self.last_result is not None:
                verdict = "PASS" if self.last_result.ok else f"FAIL {self.last_result.first_error}"
                return f"{out}\naccept: {verdict}"
        return out

    def stop(self) -> Stop | None:
        return Stop.REPEAT_GUARD if self._tripped else None
