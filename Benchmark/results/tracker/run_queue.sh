#!/usr/bin/env bash
# Runs queue.lst in batches of 3 (full suite + coding). Writes status to queue-run.log. Does NOT commit or push.
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal || exit 1
T=Benchmark/results/tracker
PY=.venv/Scripts/python.exe
LOG="$T/queue-run.log"
mapfile -t MODELS < <(tr -d '\r' < "$T/queue.lst" | grep -v '^$')
n=${#MODELS[@]}
for ((i = 0; i < n; i++)); do
  m=${MODELS[$i]}
  if (( i % 3 == 0 )); then echo "=== batch $(printf %02d $((i / 3 + 1))) start $(date -Is)" >> "$LOG"; fi
  safe=$(echo "$m" | sed 's/[^A-Za-z0-9._-]/_/g')
  echo "--- [$((i + 1))/$n] $m start $(date -Is)" >> "$LOG"
  "$PY" -I Benchmark/script/run_benchmark.py "$m" "$m" --coding </dev/null > "$T/logs/$safe.log" 2>&1
  echo "--- [$((i + 1))/$n] $m exit=$? $(date -Is)" >> "$LOG"
  if (( i % 3 == 2 || i == n - 1 )); then
    "$PY" -I Benchmark/script/build_report.py --update no </dev/null >> "$LOG" 2>&1
    echo "=== batch $(printf %02d $((i / 3 + 1))) done $(date -Is)" >> "$LOG"
  fi
done
echo ALL_DONE >> "$LOG"
