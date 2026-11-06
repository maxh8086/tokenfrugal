"""Manual Haiku baseline driver over the team tasks in scripts/bench_team_tasks.py. A cloud Haiku agent does each task by
hand, and the same checks as scripts/bench.py grade the answers. Commands:
  python -m scripts.haiku_cmp setup
      clears and seeds the scratch folder (bench_checks.SCRATCH) with every task's SEEDS files, then prints JSON
      {id: {"agent", "prompt"}} with the workspace paths rewritten to the local scratch folder.
  python -m scripts.haiku_cmp check <id> [answer-file]
      runs the task's check on the answer text (empty when no file is given) and prints
      "<id> <True|False> <first 120 chars of answer>". Exit 2 for an unknown id. The scratch-file checks
      (rename_done, sandbox_tests) read the scratch folder, so they pass only when the cloud agent's files are there.
Ids are "<team>-<index>": the TEAM_TASKS key (the same key SEEDS and EXPECT_ROOT use; agent slugs repeat across teams)
and the 0-based position in that key's list. scripts/bench.py has no id scheme of its own."""
import json
import sys

from router.config import SYNAPTREE_PROJECT
from scripts import bench_checks
from scripts.bench_team_tasks import EXPECT_ROOT, SEEDS, TEAM_TASKS

LOCAL = str(bench_checks.SCRATCH).replace("\\", "/")


def local(text):
    """Rewrite the tool-side paths to host paths: the scratch folder, and the /workspace/<project> root."""
    root = LOCAL.rsplit("/bench/scratch", 1)[0]
    return text.replace(bench_checks.WS, LOCAL).replace(f"/workspace/{SYNAPTREE_PROJECT}", root)


def tasks():
    """{id: (role key, index, agent, prompt, check name)} for every team task, in TEAM_TASKS order."""
    out = {}
    for role, items in TEAM_TASKS.items():
        for idx, (agent, prompt, check) in enumerate(items):
            out[f"{role}-{idx}"] = (role, idx, agent, prompt, check)
    return out


def setup():
    bench_checks.SCRATCH.mkdir(parents=True, exist_ok=True)
    bench_checks.clean_scratch()  # no leftovers from an earlier run, or a stale file could pass a check
    out = {}
    for tid, (role, idx, agent, prompt, _check) in tasks().items():
        err = bench_checks.seed_files(bench_checks.SCRATCH, SEEDS.get((role, idx), {}))
        if err:
            sys.exit(f"setup failed at {tid}: {err}")
        out[tid] = {"agent": agent, "prompt": local(prompt)}
    print(json.dumps(out, indent=1))
    return 0


def check(tid, answer_file=None):
    items = tasks()
    if tid not in items:
        print(f"unknown id {tid!r}; ids are <team>-<index>, print them with setup", file=sys.stderr)
        return 2
    role, idx, _agent, _prompt, check_name = items[tid]
    answer = open(answer_file, encoding="utf-8").read() if answer_file else ""
    try:
        ok = bench_checks.check_passes(check_name, answer, bench_checks.SCRATCH, EXPECT_ROOT.get((role, idx)))
    except bench_checks.InfraFailure as e:  # docker or host problem: infra, not a model fail
        print(f"{tid} infra {str(e)[:120]}")
        return 3
    print(tid, bool(ok), answer[:120].replace("\n", " "))
    return 0


def main(argv):
    if argv[1:] == ["setup"]:
        return setup()
    if len(argv) in (3, 4) and argv[1] == "check":
        return check(argv[2], argv[3] if len(argv) == 4 else None)
    print("usage: python -m scripts.haiku_cmp setup | check <id> [answer-file]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
