"""Step 8g replay report: the S2 gate, the reported sign test and the S3 trigger, from one pair of arms.

    python -m scripts.replay_report --base BASE_ARM --candidate ARM
    python -m scripts.replay_report --verify-record RESULTS_MD --base BASE_ARM --candidate ARM

Reads Benchmark/replay/results/<arm>-<YYYYMMDD>.jsonl (the newest file for each arm) and the task folders under
Benchmark/replay. Standard library only, apart from bench.pct, which is imported where it is used.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

from scripts import replay

ROOT = replay.ROOT
GATE_SHARE = 0.80  # the gate needs ceil(0.8 * N) passing tasks
SIGNIFICANCE = 0.05
S3_SHARE = 0.50  # the S3 trigger: accept_failed share strictly above this
FAIL_EXIT = 1
MISSING_EXIT = 2


class ReportError(Exception):
    pass


def read_records(path):
    rows = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def task_ids(root):
    return sorted(p.parent.name for p in (Path(root) / "Benchmark" / "replay").glob("*/task.toml"))


def need_count(n):
    return -(-4 * n // 5)  # ceil(0.8 * n), in integers


def is_infra(row):
    return row.get("result") == "infra" or row.get("stop") in replay.INFRA_KINDS


def ended(row):
    return row["outcome"] if row.get("outcome") is not None else row.get("status")


def run_passes(row):
    return ended(row) in replay.PASSING_OUTCOMES and bool(row.get("check_ok")) and bool(row.get("scope_ok"))


def is_false_success(row):
    return ended(row) in replay.PASSING_OUTCOMES and not (row.get("check_ok") and row.get("scope_ok"))


def task_passes(rows):
    """One task's records in file order. Infra rows are ignored and the last record of each run number counts.
    One run passes when that run passes; with more runs, at least 2 must pass (2 of 3 after a rerun)."""
    last = {}
    for row in rows:
        if not is_infra(row):
            last[row["run"]] = row
    if not last:
        return False
    needed = 1 if len(last) == 1 else 2
    return sum(run_passes(r) for r in last.values()) >= needed


def passed_tasks(rows, ids):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["id"], []).append(row)
    return {t: task_passes(grouped.get(t, [])) for t in ids}


def sign_test_p(plus, minus):
    """One-sided exact sign test: the chance of at least `plus` wins in `plus + minus` fair coin flips."""
    n = plus + minus
    return sum(math.comb(n, k) for k in range(plus, n + 1)) / 2 ** n


def accept_failed_share(rows):
    failed_runs = [r for r in rows if not is_infra(r) and r.get("outcome") == "failed"]
    hits = sum(1 for r in failed_runs if r.get("stop") == "accept_failed")
    share = hits / len(failed_runs) if failed_runs else 0.0
    return share, hits, len(failed_runs)


def percentile_90(rows):
    from scripts import bench  # imported here: importing bench loads the router configuration

    return bench.pct([r["secs"] for r in rows if not is_infra(r) and r.get("secs") is not None], 90)


def latest_results(root, arm):
    path = replay.base_results_file(root, arm)
    if path is None:
        raise ReportError(f"no results file for arm {arm!r} under Benchmark/replay/results")
    return path


def relative(root, path):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def compute(root, base_arm, cand_arm, base_file, cand_file):
    """Returns (report lines, GATE line, S3 decision line)."""
    ids = task_ids(root)
    n = len(ids)
    base_rows, cand_rows = read_records(base_file), read_records(cand_file)
    base_pass, cand_pass = passed_tasks(base_rows, ids), passed_tasks(cand_rows, ids)
    passed = sum(cand_pass.values())
    base_passed = sum(base_pass.values())
    false_successes = sum(1 for r in cand_rows if not is_infra(r) and is_false_success(r))
    need = need_count(n)
    gate_ok = n > 0 and passed >= need and false_successes == 0
    share, hits, failed_total = accept_failed_share(cand_rows)
    plus = sum(1 for t in ids if cand_pass[t] and not base_pass[t])
    minus = sum(1 for t in ids if base_pass[t] and not cand_pass[t])
    p = sign_test_p(plus, minus)
    with_run = {r["id"] for r in cand_rows if not is_infra(r)}
    spared = {}
    for r in cand_rows:
        if not is_infra(r):
            spared[r["id"]] = spared.get(r["id"], 0) + (r.get("est_saved_tokens") or 0)

    def half(prefix):
        sel = [t for t in ids if t.startswith(prefix)]
        return sum(cand_pass[t] for t in sel), sum(base_pass[t] for t in sel), len(sel)

    fb_c, fb_b, fb_n = half("fb-")
    rw_c, rw_b, rw_n = half("rw-")
    b90, c90 = percentile_90(base_rows), percentile_90(cand_rows)
    gate = (f"GATE: {'PASS' if gate_ok else 'FAIL'} base={base_arm} candidate={cand_arm} "
            f"results={relative(root, cand_file)} passed={passed}/{n} false_successes={false_successes} "
            f"accept_failed_share={share:.2f}")
    s3 = f"S3 decision: {'build' if (not gate_ok or share > S3_SHARE) else 'skip'}"
    lines = [
        f"Replay report: base={base_arm} ({relative(root, base_file)}), candidate={cand_arm} ({relative(root, cand_file)})",
        f"Corpus: {n} tasks. The gate needs {need} passing tasks and no false success.",
        f"Candidate passed {passed}/{n}; false successes {false_successes}.",
        f"Base passed {base_passed}/{n} (reported, not gating).",
        f"Tasks without a candidate run: {', '.join(t for t in ids if t not in with_run) or 'none'}",
        f"FB tasks: candidate {fb_c}/{fb_n}, base {fb_b}/{fb_n}",
        f"rw tasks: candidate {rw_c}/{rw_n}, base {rw_b}/{rw_n}",
        f"Sign test (reported, not gating): candidate-only {plus}, base-only {minus}, one-sided p={p:.4f}",
        ("The improvement is distinguishable from noise (p < 0.05)." if p < SIGNIFICANCE else
         "The improvement cannot be told apart from noise (p >= 0.05)."),
        f"90th percentile run seconds: base={'n/a' if b90 is None else b90} "
        f"candidate={'n/a' if c90 is None else c90}",
        "Estimated tokens spared per task (estimated, not measured usage):",
    ]
    lines += [f"  {t}: estimated tokens spared {spared.get(t, 0)}" for t in ids]
    lines.append(f"accept_failed share (candidate, non-infra runs with outcome failed): {hits}/{failed_total} = {share:.2f}")
    lines += [gate, s3]
    return lines, gate, s3


def verify(root, md_path, base_arm, cand_arm):
    try:
        recorded = Path(md_path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"replay_report: cannot read {md_path}: {exc}", file=sys.stderr)
        return MISSING_EXIT
    pair = f" base={base_arm} candidate={cand_arm} "
    found = [i for i, line in enumerate(recorded) if line.startswith("GATE: ") and pair in line]
    if not found:
        print(f"replay_report: no GATE line for base={base_arm} candidate={cand_arm} in {md_path}", file=sys.stderr)
        return FAIL_EXIT
    index = found[-1]
    gate_line = recorded[index]
    match = re.search(r" results=(\S+) ", gate_line)
    if match is None:
        print("replay_report: the GATE line names no results file", file=sys.stderr)
        return FAIL_EXIT
    cand_file = Path(match.group(1))
    if not cand_file.is_absolute():
        cand_file = Path(root) / cand_file
    if not cand_file.is_file():
        print(f"replay_report: results file not found: {cand_file}", file=sys.stderr)
        return MISSING_EXIT
    try:
        base_file = latest_results(root, base_arm)
    except ReportError as exc:
        print(f"replay_report: {exc}", file=sys.stderr)
        return MISSING_EXIT
    _, gate, s3 = compute(root, base_arm, cand_arm, base_file, cand_file)
    following = [line for line in recorded[index + 1:] if line.strip()]
    recorded_s3 = following[0] if following and following[0].startswith("S3 decision:") else None
    if recorded_s3 is None:
        print(f"replay_report: no S3 decision line after the GATE line in {md_path}", file=sys.stderr)
        return FAIL_EXIT
    problems = []
    if gate_line != gate:
        problems.append(f"  GATE recorded:   {gate_line}\n  GATE recomputed: {gate}")
    if recorded_s3 != s3:
        problems.append(f"  S3 recorded:     {recorded_s3}\n  S3 recomputed:   {s3}")
    if problems:
        print("replay_report: the record does not match the results file:\n" + "\n".join(problems), file=sys.stderr)
        return FAIL_EXIT
    print(f"verified: {gate}\n{s3}")
    return 0


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="python -m scripts.replay_report", description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True, metavar="ARM", help="the base arm")
    ap.add_argument("--candidate", required=True, metavar="ARM", help="the candidate arm")
    ap.add_argument("--verify-record", metavar="RESULTS_MD",
                    help="check the GATE and S3 lines recorded for this arm pair against the results file")
    return ap.parse_args(argv)


def main(argv=None, root=None):
    argv = sys.argv[1:] if argv is None else argv
    root = ROOT if root is None else Path(root)
    args = parse_args(argv)
    if args.verify_record:
        return verify(root, args.verify_record, args.base, args.candidate)
    try:
        base_file = latest_results(root, args.base)
        cand_file = latest_results(root, args.candidate)
    except ReportError as exc:
        print(f"replay_report: {exc}", file=sys.stderr)
        return MISSING_EXIT
    lines, _, _ = compute(root, args.base, args.candidate, base_file, cand_file)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
