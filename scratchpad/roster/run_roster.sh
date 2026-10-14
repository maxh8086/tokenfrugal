#!/usr/bin/env bash
# 16k Ollama roster, one model at a time. Existing local tags only (no pulls).
cd "C:/Users/vaibh/Downloads/Projects/tokenfrugal" || exit 1
TAGS=(
ts-qwen3-8b-16384 ts-qwen3-4b-16384 ts-gemma4-e4b-16384 ts-gemma3-4b-16384
ts-ministral-3-8b-16384 ts-qwen2-5-7b-16384 ts-qwen25c-7b-16384 ts-llama3-1-8b-16384
ts-granite3-3-8b-16384 ts-granite4-micro-16384 ts-phi4-mini-16384 ts-deepseek-r1-8b-16384
ts-deepseek-r1-distill-qwen-7b-16384 ts-starcoder2-7b-16384 ts-qwen2-5vl-7b-16384
llama3.2:3b-16k qwen2.5-coder-yarn:3b
)
for t in "${TAGS[@]}"; do
  echo "=== $(date '+%F %T') START $t"
  .venv/Scripts/python.exe scripts/bench_model.py --model "$t" --n 2 && echo "=== $(date '+%F %T') OK $t" || echo "=== $(date '+%F %T') FAIL $t"
done
echo "=== $(date '+%F %T') ROSTER DONE"
