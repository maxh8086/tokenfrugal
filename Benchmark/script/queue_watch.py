"""Supervisor for the model benchmark queue. Runs each tag in LIST, watches its log for stalls,
kills and unloads a stalled run, retries stalled models once, cleans hard/ after each batch of 3,
then rebuilds the report.

    python Benchmark/script/queue_watch.py LIST [--idle 900] [--post-done 300] [--cap 7200] [--poll 30]
                                                [--tracker DIR] [--dry-run] [--fake] [--no-report]

LIST has one model per line: "TAG" runs all four roles, "TAG ROLES" runs only those roles
(comma-separated, as in run_benchmark.py --role), e.g. "cogito:8b thinker". Blank lines are skipped.

Stall reasons, checked in this order:
    b  "== realworld done" was seen and no "wrote" line came after it for --post-done seconds
    a  no new realworld case line ("realworld/<case> #<n> ... ran=...") for --idle seconds.
       Other output (docker, router, retries) does not count as progress.
    c  the model ran longer than --cap seconds

Test options (not for real runs):
    --fake      models named fake-stall / fake-idle / fake-* use fake child commands instead of
                run_benchmark.py. Implies --no-report. Hard cleanup runs under --tracker (not the repo)
                and the final ollama unload is skipped, so a live queue is not touched.
    --dry-run   every model runs a harmless child that exits 0. Same side-effect limits as --fake.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TAIL_BYTES = 65536
QUEUE_LOG = None  # set in main()
ALL_ROLES = "builder,thinker,hard,coding"
# One line per finished case repeat, as printed by scripts/bench_real.py.
CASE_RE = re.compile(r"realworld/\S+ #\d+ +[\d.]+s \S+ ran=")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def note(line):
    # Append to queue-run.log and echo to the console.
    with open(QUEUE_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def child_cmd(m, args, roles):
    if args.dry_run:
        return [sys.executable, "-c", "print('dry-run ok', flush=True)"]
    if args.fake and m.startswith("fake-"):
        if m == "fake-stall":
            code = "import time; print('== realworld done in 1s', flush=True); time.sleep(100000)"
        elif m == "fake-idle":
            code = "import time; time.sleep(100000)"
        else:
            code = "print('ok', flush=True)"
        return [sys.executable, "-c", code]
    return [PY, "-I", str(ROOT / "Benchmark" / "script" / "run_benchmark.py"), "--model", m, "--role", roles]


def tail_lines(path):
    # Read only the last TAIL_BYTES of the log. The first line may be cut, so drop it.
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(max(0, size - TAIL_BYTES))
        text = f.read().decode("utf-8", errors="replace")
    lines = [l.rstrip() for l in text.splitlines()]
    if size > TAIL_BYTES and lines:
        lines = lines[1:]
    return lines


def read_new(path, pos):
    # Read complete lines written after byte offset pos. Returns (new offset, lines).
    size = os.path.getsize(path)
    if size <= pos:
        return pos, []
    with open(path, "rb") as f:
        f.seek(pos)
        data = f.read(size - pos)
    cut = data.rfind(b"\n") + 1  # a partly written last line waits for the next poll
    return pos + cut, data[:cut].decode("utf-8", errors="replace").splitlines()


def ollama_stop(name):
    try:
        subprocess.run(["ollama", "stop", name], capture_output=True, timeout=60)
    except Exception:
        pass  # ollama missing or not running is not fatal


def run_model(m, roles, args, logs):
    """Run one model under watch. Returns the exit code, or 'STALL' after killing it."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", m)
    log_path = logs / (safe + ".log")
    with open(log_path, "w", encoding="utf-8") as logf:
        proc = subprocess.Popen(child_cmd(m, args, roles), cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=logf, stderr=logf)
        start = time.time()
        done_at = None  # first time we saw a pending "== realworld done" line
        pos = 0  # byte offset read so far, for the case-line scan
        progress_t = start  # last time a new case line appeared (or the run started)
        while proc.poll() is None:
            time.sleep(args.poll)
            if proc.poll() is not None:
                break
            now_t = time.time()
            pos, new = read_new(log_path, pos)
            if any(CASE_RE.search(l) for l in new):
                progress_t = now_t
            lines = tail_lines(log_path)
            last = next((l.strip() for l in reversed(lines) if l.strip()), "")
            marks = [k for k, l in enumerate(lines) if l.startswith("== realworld done")]
            pending = bool(marks) and not any("wrote" in l for l in lines[marks[-1] + 1:])
            done_at = (done_at or now_t) if pending else None
            idle = now_t - progress_t
            reason = None
            if done_at is not None and now_t - done_at > args.post_done:
                reason = "b"
            elif idle > args.idle:
                reason = "a"
            elif now_t - start > args.cap:
                reason = "c"
            if reason:
                note(f"STALL {m} reason={reason} idle={int(idle)} last={last[:160]} pid={proc.pid}")
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                else:
                    proc.kill()
                proc.wait()
                ollama_stop(m)
                return "STALL"
        return proc.returncode


def batch_cleanup(base, args):
    # Port of the run_queue.sh hard/ rule: delete a set only if its json is listed in hard_test.csv.
    hard = base / "hard"
    csv_path = base / "hard_test.csv"
    csv_lines = csv_path.read_text(encoding="utf-8").splitlines() if csv_path.exists() else []
    removed = kept = 0
    for jf in sorted(hard.glob("*.json")) if hard.is_dir() else []:
        if any(f",{jf.name}," in l for l in csv_lines):
            removed += 1
            for p in (jf, hard / (jf.stem + ".md"), hard / (jf.stem + "_hard_results.csv")):
                try:
                    p.unlink()
                except OSError:
                    pass
        else:
            kept += 1
    try:
        hard.rmdir()
    except OSError:
        pass  # not empty, or missing
    note(f"hard/ cleanup: removed {removed}, kept {kept} not in hard_test.csv {now()}")


def ollama_loaded():
    try:
        out = subprocess.run(["ollama", "ps"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60).stdout
    except Exception:
        return []
    return [l.split()[0] for l in out.splitlines()[1:] if l.split()]


def main():
    global QUEUE_LOG
    ap = argparse.ArgumentParser(description="Run the model queue with stall detection.")
    ap.add_argument("list", help="text file, one model tag per line")
    ap.add_argument("--idle", type=int, default=900)
    ap.add_argument("--post-done", type=int, default=300)
    ap.add_argument("--cap", type=int, default=7200)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--tracker", default="Benchmark/results/tracker")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fake", action="store_true", help="test only: fake child commands for fake-* models")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    test = args.fake or args.dry_run
    no_report = args.no_report or test
    tracker = ROOT / args.tracker  # an absolute --tracker replaces ROOT
    logs = tracker / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    QUEUE_LOG = tracker / "queue-run.log"
    failed = tracker / "failed.list"
    # Cleanup base: repo results in a real run, the tracker dir in test mode.
    base = tracker if test else ROOT / "Benchmark" / "results"

    with open(args.list, encoding="utf-8") as f:
        entries = [l.split() for l in f if l.strip()]
    jobs = [(e[0], e[1] if len(e) > 1 else ALL_ROLES) for e in entries]  # (tag, roles)
    n = len(jobs)
    stalled = []

    for i, (m, roles) in enumerate(jobs):
        if i % 3 == 0:
            note(f"=== batch {i // 3 + 1:02d} start {now()}")
        note(f"--- [{i + 1}/{n}] {m} [{roles}] start {now()}")
        status = run_model(m, roles, args, logs)
        if status == "STALL":
            stalled.append((m, roles))
            with open(failed, "a", encoding="utf-8") as f:
                f.write(m + "\n")
        note(f"--- [{i + 1}/{n}] {m} exit={status} {now()}")
        if i % 3 == 2 or i == n - 1:
            batch_cleanup(base, args)
            note(f"=== batch {i // 3 + 1:02d} done {now()}")

    # Retry pass: only models that stalled in this run, once more.
    for m, roles in stalled:
        note(f"--- retry {m} [{roles}] start {now()}")
        status = run_model(m, roles, args, logs)
        note(f"--- retry {m} exit={status} {now()}")
        if status == "STALL":
            note(f"PERMANENT-FAIL {m} {now()}")

    if not test:
        for name in ollama_loaded():
            ollama_stop(name)

    if not no_report:
        note(f"=== report start {now()}")
        with open(QUEUE_LOG, "a", encoding="utf-8") as f:
            rc = subprocess.run([PY, "-I", str(ROOT / "Benchmark" / "script" / "build_report.py"),
                                 "--update", "no"], cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=f, stderr=subprocess.STDOUT).returncode
        note(f"=== report done exit={rc} {now()}")
    note("ALL_DONE")


if __name__ == "__main__":
    main()
