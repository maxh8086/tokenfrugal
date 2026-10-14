#!/usr/bin/env bash
# Pull GGUF substitutes for the five failed models; create 16k variants; bench after roster finishes.
cd "C:/Users/vaibh/Downloads/Projects/tokenfrugal" || exit 1
LOG=scratchpad/roster/queue_gguf.log
BASES=(
"hf.co/bartowski/google_gemma-3-12b-it-GGUF:Q4_K_M"
"hf.co/bartowski/Mistral-Nemo-Instruct-2407-GGUF:Q4_K_M"
"hf.co/bartowski/Mistral-NeMo-Minitron-8B-Instruct-GGUF:Q4_K_M"
)
mkdir -p models/trial
READY=()
for base in "${BASES[@]}"; do
  echo "=== $(date '+%F %T') PULL START $base" >> "$LOG"
  if ollama pull "$base" >> "$LOG" 2>&1; then
    echo "=== $(date '+%F %T') PULL OK $base" >> "$LOG"
    tag="ts-$(echo "$base" | sed 's/:Q4_K_M$//' | tr '/:.' '---' | tr 'A-Z' 'a-z')-16384"
    printf 'FROM %s\nPARAMETER num_ctx 16384\nPARAMETER temperature 0.1\n' "$base" > "models/trial/$tag.Modelfile"
    if ollama create "$tag" -f "models/trial/$tag.Modelfile" >> "$LOG" 2>&1; then
      echo "=== $(date '+%F %T') CREATE OK $tag" >> "$LOG"; READY+=("$tag")
    else
      echo "=== $(date '+%F %T') CREATE FAIL $tag" >> "$LOG"
    fi
  else
    echo "=== $(date '+%F %T') PULL FAIL $base" >> "$LOG"
  fi
done
echo "=== $(date '+%F %T') PULLS DONE ready=${#READY[@]} ${READY[*]}" >> "$LOG"
until grep -q "ROSTER DONE" scratchpad/roster/roster.log 2>/dev/null; do sleep 60; done
for t in "${READY[@]}"; do
  echo "=== $(date '+%F %T') BENCH START $t" >> "$LOG"
  .venv/Scripts/python.exe scripts/bench_model.py --model "$t" --n 2 >> "$LOG" 2>&1 && echo "=== $(date '+%F %T') BENCH OK $t" >> "$LOG" || echo "=== $(date '+%F %T') BENCH FAIL $t" >> "$LOG"
done
echo "=== $(date '+%F %T') QUEUE DONE" >> "$LOG"
