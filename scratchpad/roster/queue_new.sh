#!/usr/bin/env bash
# Second queue: pull five new models now (in parallel with the running roster),
# build 16k ts-* variants with the same Modelfile convention as bench/sweep3.sh,
# then bench them after roster.log reports ROSTER DONE.
cd "C:/Users/vaibh/Downloads/Projects/tokenfrugal" || exit 1
LOG=scratchpad/roster/queue_new.log
BASES=(
"gemma4:12b-nvfp4"
"hf.co/NeoChen1024/gemma-3-12b-it-NVFP4"
"hf.co/DataSnake/Mistral-Nemo-Instruct-2407-NVFP4-FP8"
"hf.co/nvidia/Llama-3.1-Nemotron-Nano-VL-8B-V1-FP4-QAD"
"mistral-nemo-minitron-8b-instruct:q4_k_m"
)
mkdir -p models/trial
READY=()
for base in "${BASES[@]}"; do
  echo "=== $(date '+%F %T') PULL START $base" >> "$LOG"
  if ollama pull "$base" >> "$LOG" 2>&1; then
    echo "=== $(date '+%F %T') PULL OK $base" >> "$LOG"
    tag="ts-$(echo "$base" | tr '/:.' '---' | tr 'A-Z' 'a-z')-16384"
    printf 'FROM %s\nPARAMETER num_ctx 16384\nPARAMETER temperature 0.1\n' "$base" > "models/trial/$tag.Modelfile"
    if ollama create "$tag" -f "models/trial/$tag.Modelfile" >> "$LOG" 2>&1; then
      echo "=== $(date '+%F %T') CREATE OK $tag" >> "$LOG"
      READY+=("$tag")
    else
      echo "=== $(date '+%F %T') CREATE FAIL $tag" >> "$LOG"
    fi
  else
    echo "=== $(date '+%F %T') PULL FAIL $base" >> "$LOG"
  fi
done
echo "=== $(date '+%F %T') PULLS DONE ready=${#READY[@]}" >> "$LOG"

# Wait for the first roster to finish before benching (avoid contention).
until grep -q "ROSTER DONE" scratchpad/roster/roster.log 2>/dev/null; do sleep 60; done
echo "=== $(date '+%F %T') ROSTER FINISHED, starting new-model bench" >> "$LOG"
for t in "${READY[@]}"; do
  echo "=== $(date '+%F %T') START $t" >> "$LOG"
  .venv/Scripts/python.exe scripts/bench_model.py --model "$t" --n 2 >> "$LOG" 2>&1 && echo "=== $(date '+%F %T') OK $t" >> "$LOG" || echo "=== $(date '+%F %T') FAIL $t" >> "$LOG"
done
echo "=== $(date '+%F %T') QUEUE DONE" >> "$LOG"
