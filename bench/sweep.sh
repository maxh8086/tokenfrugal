#!/bin/bash
# usage: sweep.sh -> 4 failing cases per candidate model/context, one model loaded at a time
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
for tag in ts-qwen25c-7b-16384 ts-qwen3-4b-16384 ts-phi4-mini-16384 ts-granite4-micro-16384 ts-qwen25c-7b-32768 ts-qwen3-4b-32768 ts-phi4-mini-32768 ts-granite4-micro-32768; do
  echo "### $tag"
  TOKENFRUGAL_MODEL_BUILDER=$tag TOKENFRUGAL_MODEL_THINKER=$tag BENCH_CASES=write_tests,rename_across_files,summarize_readme,role_browser \
   PYTHONPATH=. .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag $tag 2>&1 | grep -E "realworld/|wrote"
  ollama ps | tail -n +2
  ollama stop $tag >/dev/null 2>&1
done
echo SWEEP-DONE
