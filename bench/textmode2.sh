#!/bin/bash
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
until grep -q TEXT-DONE bench/textmode.log; do sleep 20; done
for m in llama3.2:3b-16k qwen2.5-coder-yarn:3b ts-qwen25c-7b-16384; do
  echo "### text $m"
  TOKENFRUGAL_TOOL_MODE=text TOKENFRUGAL_MODEL_BUILDER=$m TOKENFRUGAL_MODEL_THINKER=$m \
  BENCH_CASES=write_tests,rename_across_files,summarize_readme,role_browser \
  PYTHONPATH=. .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag text-${m//[:.]/-}
  ollama stop $m
done
echo TEXT2-DONE
