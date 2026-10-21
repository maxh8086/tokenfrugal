#!/usr/bin/env bash
# Runs queue.lst in batches of 3 (full suite + coding). Writes status to queue-run.log. Does NOT commit or push.
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal || exit 1
T=Benchmark/results/tracker
PY=.venv/Scripts/python.exe
LOG="$T/queue-run.log"
mapfile -t MODELS < <(tr -d '\r' < "$T/queue.lst" | grep -v '^$')
n=${#MODELS[@]}
# Batch end. hard/ should stay empty: each per-run hard JSON is already recorded in hard_test.csv (store.py).
# A set is deleted only when its source_file is in that CSV; anything else is kept and counted in the log.
clean_hard() {
  local dir=Benchmark/results/hard csv=Benchmark/results/hard_test.csv f base stem removed=0 kept=0
  [ -d "$dir" ] || return 0
  for f in "$dir"/*.json; do
    [ -e "$f" ] || continue
    base=$(basename "$f")
    stem=${base%.json}
    if grep -qF ",$base," "$csv"; then
      rm -f "$dir/$stem.json" "$dir/$stem.md" "$dir/${stem}_hard_results.csv"
      removed=$((removed + 1))
    else
      kept=$((kept + 1))
    fi
  done
  rmdir "$dir" 2>/dev/null
  echo "hard/ cleanup: removed $removed, kept $kept not in hard_test.csv $(date -Is)" >> "$LOG"
}

for ((i = 0; i < n; i++)); do
  m=${MODELS[$i]}
  if (( i % 3 == 0 )); then echo "=== batch $(printf %02d $((i / 3 + 1))) start $(date -Is)" >> "$LOG"; fi
  safe=$(echo "$m" | sed 's/[^A-Za-z0-9._-]/_/g')
  echo "--- [$((i + 1))/$n] $m start $(date -Is)" >> "$LOG"
  "$PY" -I Benchmark/script/run_benchmark.py "$m" "$m" --coding </dev/null > "$T/logs/$safe.log" 2>&1
  echo "--- [$((i + 1))/$n] $m exit=$? $(date -Is)" >> "$LOG"
  if (( i % 3 == 2 || i == n - 1 )); then
    "$PY" -I Benchmark/script/build_report.py --update no </dev/null >> "$LOG" 2>&1
    clean_hard
    echo "=== batch $(printf %02d $((i / 3 + 1))) done $(date -Is)" >> "$LOG"
  fi
done
echo ALL_DONE >> "$LOG"
