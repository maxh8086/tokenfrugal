#!/bin/bash
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
for m in ts-phi4-mini-16384 ts-gemma3-4b-16384; do
  echo "### text $m"
  TOKENFRUGAL_TOOL_MODE=text TOKENFRUGAL_MODEL_BUILDER=$m TOKENFRUGAL_MODEL_THINKER=$m \
  BENCH_CASES=write_tests,rename_across_files,summarize_readme,role_browser \
  PYTHONPATH=. .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag text-$m
  ollama stop $m
done
echo TEXT-DONE
