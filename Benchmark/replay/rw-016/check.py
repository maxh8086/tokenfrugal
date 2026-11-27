"""Replay task rw-016: scripts/bench_append.py appends a CSV result row to the model comparison table (offline)."""
import csv
import os
import subprocess
import sys
import tempfile

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
SCRIPT = os.path.join(ROOT, "scripts", "bench_append.py")
TABLE = os.path.join(ROOT, "Benchmark", "model-comparison.md")
HEADER = "| Model / run tag"
TAG = "rw016-check-tag"
DATE = "2026-10-12"
NOTES = "a|b\nc"


def fail(message):
    print("FAIL:", message)
    return 1


def run(args):
    return subprocess.run([sys.executable, SCRIPT] + args, cwd=ROOT, capture_output=True, text=True, timeout=120)


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def table_end(lines):
    start = next(i for i, line in enumerate(lines) if line.startswith(HEADER))
    end = start + 1
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return end


def scenario(csv_path, original):
    helped = run(["--help"])
    if helped.returncode != 0:
        return "--help exited %d" % helped.returncode
    dry = run([csv_path, "--date", DATE, "--dry-run"])
    if dry.returncode != 0:
        return "dry run exited %d: %s" % (dry.returncode, dry.stderr.strip())
    if read_bytes(TABLE) != original:
        return "dry run changed Benchmark/model-comparison.md"
    if "%s (tested %s)" % (TAG, DATE) not in dry.stdout:
        return "dry run output lacks the dated tag: %r" % (dry.stdout,)
    if "a\\|b<br>c" not in dry.stdout or "a|b" in dry.stdout:
        return "dry run output does not show the escaped notes cell: %r" % (dry.stdout,)
    real = run([csv_path, "--date", DATE])
    if real.returncode != 0:
        return "append exited %d: %s" % (real.returncode, real.stderr.strip())
    if TAG not in real.stdout:
        return "append printed no confirmation with the tag: %r" % (real.stdout,)
    changed = read_bytes(TABLE)
    before = original.decode("utf-8").splitlines()
    after = changed.decode("utf-8").splitlines()
    if len(after) != len(before) + 1:
        return "expected exactly one new line, got %d" % (len(after) - len(before))
    end = table_end(before)
    if after[:end] != before[:end] or after[end + 1:] != before[end:]:
        return "the new line is not directly after the table's last row, or another line changed"
    new = after[end]
    if not (new.startswith("|") and TAG in new and DATE in new and "a\\|b<br>c" in new):
        return "inserted line %r lacks the dated tag or the escaped notes" % (new,)
    dup = run([csv_path, "--date", DATE])
    if dup.returncode != 1:
        return "duplicate tag and date exited %d, expected 1" % dup.returncode
    if not dup.stderr.strip():
        return "duplicate run printed nothing on stderr"
    if read_bytes(TABLE) != changed:
        return "duplicate run changed the table"
    return ""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "result.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["tag", "score", "notes"])
            writer.writerow([TAG, "0.75", NOTES])
        original = read_bytes(TABLE)
        problem = ""
        try:
            problem = scenario(csv_path, original)
        except Exception as exc:
            problem = "raised %r" % (exc,)
        finally:
            with open(TABLE, "wb") as handle:
                handle.write(original)
    if problem:
        return fail(problem)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
