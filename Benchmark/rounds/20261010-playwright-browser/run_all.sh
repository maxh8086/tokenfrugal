#!/bin/bash
# serial on the GPU: every model x every toolkit
cd "$(dirname "$0")/../../.."
for m in llama3.2:3b-16k qwen2.5-coder-yarn:3b ts-qwen3-8b-16384 ts-qwen25c-7b-16384 ts-gemma4-e4b-16384; do
  echo "=== $m"
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe Benchmark/rounds/20261010-playwright-browser/run_pw.py "$m" 2>&1 | grep -E "^(A|B|C)-|Traceback"
done
echo ALLDONE
