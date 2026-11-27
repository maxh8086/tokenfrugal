"""Replay runner for the S2 measurement plan (docs/designs/subagent-runtime-design.md, Measurement plan (S2)).

Part A: argument parsing, the per-run environment, the settings copy, scope_ok before grading, the child
process (one fresh Python per run, started in the router checkout) and one JSON line per run.
Part B1: result grading (pass, fail, infra), steps, a child that crashes or times out, the wrong-router
check in the child, and one rerun after an infra result.
Part B2: --rerun-against (two more runs of each task whose result differs from the base arm) and --check-corpus.

Standard library only. The router is imported only inside the child process, never by the runner, so the
tests do not load router/config.py (which reads .env). packet.json is validated with router/packet.py loaded by
file path, which imports only pydantic.

Usage: python -m scripts.replay --arm NAME --router PATH --repo NAME=PATH [--venv NAME=PATH] [--env K=V ...] [--runs N]
                               [--rerun-against BASE_ARM]
       python -m scripts.replay --check-corpus [--repo NAME=PATH] [--venv NAME=PATH]
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKET_FILE = ROOT / "router" / "packet.py"
RESULT_PREFIX = "REPLAY_RESULT "
CHILD_TIMEOUT = 3600  # seconds; a run takes 88-212 s on the reference GPU
CHECK_TIMEOUT = 600  # seconds for check.py; a timeout is a failed check
BUSY = "workspace_busy"
LOCAL_CHILD_FLAG = "--child"
INFRA_KINDS = ("gpu_busy", "infra", BUSY)  # error kinds the router writes for host or backend trouble
WRONG_ROUTER_EXIT = 3
PASSING_OUTCOMES = ("done", "satisfied")


def _pairs(ap, items, flag):
    out = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name:
            ap.error(f"{flag} expects NAME=VALUE, got {item!r}")
        out[name] = value
    return out


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="python -m scripts.replay", description="Replay coding tasks against one router arm.")
    ap.add_argument("--arm", default="", help="arm name, used in the results file name")
    ap.add_argument("--router", default="", help="router checkout (a worktree) to run")
    ap.add_argument("--repo", action="append", default=[], metavar="NAME=PATH", help="task repository checkout")
    ap.add_argument("--venv", action="append", default=[], metavar="NAME=PATH", help="venv for a repository (default <repo>/.venv)")
    ap.add_argument("--env", action="append", default=[], metavar="K=V", help="extra environment for the router process")
    ap.add_argument("--runs", type=int, default=1, help="runs per task")
    ap.add_argument("--rerun-against", default="", metavar="BASE_ARM", help="rerun differing tasks twice against BASE_ARM's newest results")
    ap.add_argument("--check-corpus", action="store_true", help="validate the task folders and exit")
    args = ap.parse_args(argv)
    if not args.check_corpus and (not args.arm or not args.router):
        ap.error("--arm and --router are required unless --check-corpus is given")
    args.repo = _pairs(ap, args.repo, "--repo")
    args.venv = _pairs(ap, args.venv, "--venv")
    args.env = _pairs(ap, args.env, "--env")
    return args


def venv_bin_dir(venv, os_name=None):
    return Path(venv) / ("Scripts" if (os_name or os.name) == "nt" else "bin")


def venv_python(venv, os_name=None):
    return venv_bin_dir(venv, os_name) / ("python.exe" if (os_name or os.name) == "nt" else "python")


def run_env(base, *, gateway_dir, workspace, venv, extra=None):
    """Environment for one router process. Isolation keys are set last so no --env value can override them."""
    env = dict(base)
    env.update(extra or {})
    path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
    env[path_key] = os.pathsep.join([str(venv_bin_dir(venv)), env.get(path_key, "")]).rstrip(os.pathsep)
    gateway = Path(gateway_dir)
    env["GATEWAY_DB"] = str(gateway / "tasks.db")
    env["GATEWAY_EVENTS"] = str(gateway / "events.jsonl")
    env["CC_WORKSPACE"] = str(workspace)
    env["TOKENFRUGAL_HOST_ACCEPT_PATHS"] = str(workspace)
    env["TOKENFRUGAL_ACCEPT_VENV"] = str(venv)
    return env


def copy_settings(src_root, router_root):
    """A worktree has none of the untracked settings: copy .env and router/*.json from the main checkout."""
    src, dst = Path(src_root), Path(router_root)
    if os.path.realpath(src) == os.path.realpath(dst):
        return []
    copied = []
    for item in [src / ".env", *sorted((src / "router").glob("*.json"))]:
        if item.is_file():
            target = dst / item.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            copied.append(str(target))
    return copied


def child_mode(router_root):
    """A checkout with router/packet.py takes packets; an older one (the base arm) takes the old prompt path."""
    return "packet" if (Path(router_root) / "router" / "packet.py").is_file() else "legacy"


def _path_key(path):
    """Same as router/checker.py _path_key: slashes, and case-folded on Windows and macOS."""
    path = path.replace("\\", "/")
    return path.casefold() if os.name == "nt" or sys.platform == "darwin" else path


def glob_matches(path, pattern):
    """Slash-separated glob as in router/checker.py _glob_matches: * stays in one folder, ** crosses folders."""
    path, pattern = _path_key(path), _path_key(pattern)
    pieces, i = ["^"], 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if pattern[i + 1:i + 2] == "*":
                i += 1
                if pattern[i + 1:i + 2] == "/":
                    i += 1
                    pieces.append("(?:.*/)?")
                else:
                    pieces.append(".*")
            else:
                pieces.append("[^/]*")
        elif char == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(char))
        i += 1
    pieces.append("$")
    return re.match("".join(pieces), path) is not None


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)
    return done.stdout.decode("utf-8", "replace")


def changed_paths(worktree, base_commit):
    """Tracked and non-ignored untracked changes against base_commit. Stages everything in the worktree."""
    _git(worktree, "add", "-A")
    return [p for p in _git(worktree, "diff", "--cached", "--name-only", "-z", base_commit).split("\0") if p]


def scope_ok(worktree, base_commit, must_not_change):
    return not any(glob_matches(path, pattern) for path in changed_paths(worktree, base_commit) for pattern in must_not_change)


def grade_run(worktree, base_commit, must_not_change, run_check):
    """scope is measured before the grader runs, so files the grader writes are not counted."""
    scope = scope_ok(worktree, base_commit, must_not_change)
    return scope, bool(run_check())


def make_worktree(repo, base_commit, dest):
    subprocess.run(["git", "worktree", "add", "--detach", str(dest), base_commit], cwd=repo, check=True, capture_output=True)


def remove_worktree(repo, dest):
    subprocess.run(["git", "worktree", "remove", "--force", str(dest)], cwd=repo, capture_output=True)
    shutil.rmtree(dest, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True)


def plain_prompt(packet):
    """The base arm's prompt: the packet's text with a plain Accept line (no backticks, space-joined argv)."""
    lines = [f"Goal: {packet['goal']}"]
    if packet.get("requirements"):
        lines.append("Requirements:")
        lines.extend(f"- {item}" for item in packet["requirements"])
    lines.append("Files:")
    for file in packet["files"]:
        entry = f"- {file['path']}"
        if file.get("new"):
            entry += " (new)"
        if file.get("lines"):
            start, end = file["lines"]
            entry += f" lines {start}-{end}"
        lines.append(entry)
    if packet.get("context"):
        lines.append(f"Context: {packet['context']}")
    if packet.get("accept"):
        lines.append("Accept: " + " ".join(packet["accept"]))
    return "\n".join(lines)


class SetupFault(RuntimeError):
    """A setup problem (for example the child imported another router). The runner stops and writes no record."""


def read_jsonl(path):
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def last_saved(events_path):
    """The saved field of the last task_done or task_failed event in the run's events file."""
    for event in reversed(read_jsonl(events_path)):
        if event.get("kind") in ("task_done", "task_failed"):
            return event.get("saved")
    return None


def count_steps(events_path, tid):
    """The largest n of the task's step events, or None when the task is unknown or had no step."""
    if tid is None:
        return None
    steps = [e.get("n") for e in read_jsonl(events_path)
             if e.get("kind") == "step" and e.get("id") == tid and isinstance(e.get("n"), int)]
    return max(steps) if steps else None


def finish_child(tid, reply, get_row, events_path):
    """What the child prints. Without a task row, store.get is not called and the row fields are null."""
    if tid is None:
        return {"tid": None, "reply": reply, "status": None, "outcome": None,
                "error_kind": BUSY if reply.startswith(BUSY) else "refused", "saved": None,
                "model_tag": None, "peak_ctx": None}
    row = get_row(tid) or {}
    return {"tid": tid, "reply": reply, "status": row.get("status"), "outcome": row.get("outcome"),
            "error_kind": row.get("error_kind"), "saved": last_saved(events_path),
            "model_tag": row.get("model_tag"), "peak_ctx": row.get("peak_ctx")}


def grade(child, steps, check_ok, scope_ok):
    """infra: host or backend trouble, or a child that crashed before any step. pass: the run ended done or satisfied
    (outcome, or status when outcome is null as on an old checkout) with the check and the scope both ok. Else fail."""
    if child["error_kind"] in INFRA_KINDS:
        return "infra"
    if child["error_kind"] == "crashed" and steps is None:
        return "infra"
    if child["tid"] is None:
        return "fail"
    ended = child["outcome"] if child["outcome"] is not None else child["status"]
    return "pass" if ended in PASSING_OUTCOMES and check_ok and scope_ok else "fail"


def blank_child(error_kind, reply):
    """The child's fields when it printed no result line (crash, timeout)."""
    return {"tid": None, "reply": reply, "status": None, "outcome": None, "error_kind": error_kind,
            "saved": None, "model_tag": None, "peak_ctx": None}


def build_record(task_id, arm, run_no, child, *, steps, check_ok, scope_ok, secs):
    return {"id": task_id, "arm": arm, "run": run_no, "result": grade(child, steps, check_ok, scope_ok),
            "outcome": child["outcome"], "status": child["status"], "stop": child["error_kind"],
            "check_ok": check_ok, "scope_ok": scope_ok, "secs": secs, "steps": steps,
            "peak_ctx": child["peak_ctx"], "model_tag": child["model_tag"], "est_saved_tokens": child["saved"]}


def run_with_infra_rerun(run_once_fn):
    """Runs once; an infra record is kept and the task is run one more time, at most twice in all."""
    records = []
    for attempt in (1, 2):
        record = run_once_fn(attempt)
        record["attempt"] = attempt
        records.append(record)
        if record["result"] != "infra":
            break
    return records


def parse_child(stdout):
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX):])
    return None


def results_path(root, arm, day):
    return Path(root) / "Benchmark" / "replay" / "results" / f"{arm}-{day:%Y%m%d}.jsonl"


def append_record(root, arm, record, day):
    path = results_path(root, arm, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def load_task(folder):
    folder = Path(folder)
    meta = tomllib.loads((folder / "task.toml").read_text(encoding="utf-8"))
    packet = json.loads((folder / "packet.json").read_text(encoding="utf-8"))
    return {"id": folder.name, "folder": folder, "meta": meta, "packet": packet}


def router_under(router_file, router_root):
    """True when the imported router package lies inside the --router checkout (realpath, normcase, path boundary)."""
    found = os.path.normcase(os.path.realpath(router_file))
    root = os.path.normcase(os.path.realpath(router_root)).rstrip(os.sep)
    return found.startswith(root + os.sep)


def child_main(stdin_text):
    """Runs inside the router checkout (cwd and sys.path), one task, then prints one marked JSON line."""
    payload = json.loads(stdin_text)
    sys.path.insert(0, payload["router"])
    import asyncio
    import router as router_pkg  # noqa: E402  (imported after sys.path is set)
    if not router_under(router_pkg.__file__, payload["router"]):
        print(f"replay child: router imported from {router_pkg.__file__}, not under {payload['router']}", file=sys.stderr)
        sys.exit(WRONG_ROUTER_EXIT)
    from router import config, server, store  # noqa: E402
    from router.packet import Packet  # noqa: E402
    agent, task_type = payload["agent"], payload.get("task_type", "")
    if payload["mode"] == "packet":
        packet = Packet.model_validate(payload["packet"])
        tid, reply = asyncio.run(server.start_packet_task(agent, packet, task_type))
    else:
        role = config.resolve_role(agent, server.CFG)
        tid = store.create(agent, role["role"], payload["prompt"])
        reply = asyncio.run(server._execute(tid, agent, role, payload["prompt"]))
    out = finish_child(tid, reply, store.get, os.environ["GATEWAY_EVENTS"])
    print(RESULT_PREFIX + json.dumps(out), flush=True)


def run_check(check_cmd, cwd, env):
    """check.py exit 0 is a pass. A check that runs past CHECK_TIMEOUT is a failed check, and the runner goes on."""
    try:
        return subprocess.run(check_cmd, cwd=str(cwd), env=env, capture_output=True, timeout=CHECK_TIMEOUT).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def base_results_file(root, base_arm):
    """The newest Benchmark/replay/results/<base_arm>-<YYYYMMDD>.jsonl, or None. Other arm names never match."""
    folder = Path(root) / "Benchmark" / "replay" / "results"
    pattern = re.compile(rf"{re.escape(base_arm)}-(\d{{8}})\.jsonl")
    best = None
    if folder.is_dir():
        for path in folder.iterdir():
            found = pattern.fullmatch(path.name)
            if found and (best is None or found.group(1) > best[0]):
                best = (found.group(1), path)
    return best[1] if best else None


def base_results(path):
    """task id -> result of the base arm's last non-infra line for that task."""
    out = {}
    for row in read_jsonl(path):
        if row.get("result") != "infra" and "id" in row and "result" in row:
            out[row["id"]] = row["result"]
    return out


def rerun_ids(records, base):
    """Task ids whose arm result (last non-infra record) differs from the base arm's. A task absent from the base is not rerun."""
    arm = {}
    for row in records:
        if row.get("result") != "infra":
            arm[row["id"]] = row.get("result")
    return [tid for tid, result in arm.items() if tid in base and base[tid] != result]


PACKET_MODEL = None


def packet_model():
    """router/packet.py loaded by file path (pydantic only). The router package itself is never imported here."""
    global PACKET_MODEL
    if PACKET_MODEL is None:
        spec = importlib.util.spec_from_file_location("replay_router_packet", PACKET_FILE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        PACKET_MODEL = module.Packet
    return PACKET_MODEL


def task_problems(folder, model):
    problems = []
    try:
        meta = tomllib.loads((folder / "task.toml").read_text(encoding="utf-8"))
    except FileNotFoundError:
        meta = {}
        problems.append("task.toml missing")
    except (OSError, ValueError) as exc:
        meta = {}
        problems.append(f"task.toml invalid: {exc}")
    for key in ("repo", "base_commit", "agent"):
        value = meta.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"task.toml needs a non-empty {key}")
    packet = None
    try:
        packet = model.model_validate(json.loads((folder / "packet.json").read_text(encoding="utf-8")))
    except FileNotFoundError:
        problems.append("packet.json missing")
    except (OSError, ValueError) as exc:
        problems.append(f"packet.json invalid: {exc}")
    if not (folder / "check.py").is_file():
        problems.append("check.py missing")
    if packet is not None and packet.accept is not None:
        argv = packet.accept
        if " ".join(argv).split() != argv:
            problems.append(f"accept does not survive \" \".join(argv).split(): {argv!r}")
    return problems


def corpus_check(root, repos, venvs):
    """Returns (task count, problems). Every task folder under Benchmark/replay (except results) is checked, and each
    venv named by --venv, or by --repo with its default <repo>/.venv, must be an existing folder."""
    corpus = Path(root) / "Benchmark" / "replay"
    folders = sorted(p for p in corpus.iterdir() if p.is_dir() and p.name != "results") if corpus.is_dir() else []
    model = packet_model()
    problems = []
    for folder in folders:
        problems.extend(f"{folder.name}: {p}" for p in task_problems(folder, model))
    for name in sorted(set(repos) | set(venvs)):
        venv = Path(venvs[name]) if name in venvs else Path(repos[name]) / ".venv"
        if not venv.is_dir():
            problems.append(f"venv {name}: {venv} is not an existing folder")
    return len(folders), problems


def run_once(task, arm, router, repo, venv, extra_env, run_no):
    meta = task["meta"]
    tmp = Path(tempfile.mkdtemp(prefix="replay-"))
    ws, gateway = tmp / "ws", tmp / "gateway"
    gateway.mkdir()
    try:
        make_worktree(repo, meta["base_commit"], ws)
        env = run_env(os.environ, gateway_dir=gateway, workspace=ws, venv=venv, extra=extra_env)
        payload = {"router": str(router), "mode": child_mode(router), "agent": meta["agent"],
                   "task_type": meta.get("task_type", ""), "packet": task["packet"], "prompt": plain_prompt(task["packet"])}
        started = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), LOCAL_CHILD_FLAG], input=json.dumps(payload),
                                  text=True, capture_output=True, cwd=str(router), env=env, timeout=CHILD_TIMEOUT)
        except subprocess.TimeoutExpired:
            child = blank_child("timeout", f"timeout after {CHILD_TIMEOUT}s")
        else:
            if proc.returncode == WRONG_ROUTER_EXIT:
                raise SetupFault(f"the child did not import the router under {router}: {proc.stderr.strip()[-300:]}")
            child = parse_child(proc.stdout) or blank_child("crashed", proc.stderr[-400:])
        secs = round(time.monotonic() - started, 2)
        steps = count_steps(gateway / "events.jsonl", child["tid"])
        check = [str(venv_python(venv)), str(task["folder"] / "check.py")]
        scope, check_ok = grade_run(ws, meta["base_commit"], task["packet"].get("must_not_change", []),
                                    lambda: run_check(check, ws, env))
        return build_record(task["id"], arm, run_no, child, steps=steps, check_ok=check_ok, scope_ok=scope, secs=secs)
    finally:
        remove_worktree(repo, ws)
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == [LOCAL_CHILD_FLAG]:
        child_main(sys.stdin.read())
        return 0
    args = parse_args(argv)
    if args.check_corpus:
        count, problems = corpus_check(ROOT, args.repo, args.venv)
        for problem in problems:
            print(f"problem: {problem}")
        print(f"tasks: {count}")
        return 1 if problems else 0
    base = {}
    if args.rerun_against:
        base_file = base_results_file(ROOT, args.rerun_against)
        if base_file is None:
            print(f"replay: no results file for base arm {args.rerun_against!r} under Benchmark/replay/results", file=sys.stderr)
            return 2
        base = base_results(base_file)
    router = Path(args.router).resolve()
    copy_settings(ROOT, router)
    tasks = []
    for folder in sorted((ROOT / "Benchmark" / "replay").glob("*/task.toml")):
        task = load_task(folder.parent)
        if task["meta"]["repo"] not in args.repo:
            print(f"replay: task {task['id']} needs --repo {task['meta']['repo']}=PATH", file=sys.stderr)
            return 2
        tasks.append(task)

    def targets(task):
        name = task["meta"]["repo"]
        repo = Path(args.repo[name]).resolve()
        return repo, Path(args.venv.get(name) or repo / ".venv")

    def run_task(task, run_numbers):
        repo, venv = targets(task)
        records = []
        for run_no in run_numbers:
            for record in run_with_infra_rerun(lambda attempt: run_once(task, args.arm, router, repo, venv, args.env, run_no)):
                append_record(ROOT, args.arm, record, date.today())
                print(json.dumps(record, sort_keys=True), flush=True)
                records.append(record)
        return records

    try:
        done = {task["id"]: run_task(task, range(1, args.runs + 1)) for task in tasks}
        if args.rerun_against:
            for task in tasks:
                if task["id"] in rerun_ids(done[task["id"]], base):
                    run_task(task, (args.runs + 1, args.runs + 2))
    except SetupFault as exc:
        print(f"replay: stopped, setup fault: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
