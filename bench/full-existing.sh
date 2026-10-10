#!/bin/bash
# waits for the new-model sweep, then runs the full 16-case suite (n=2) on the already-tested models with the current code
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
true
run() { # tag builder thinker
  echo "### $1 FULL"
  TOKENFRUGAL_MODEL_BUILDER=$2 TOKENFRUGAL_MODEL_THINKER=$3 PYTHONPATH=. .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag "full-$1" 2>&1 | grep -E "realworld/|wrote"
  ollama stop "$2" >/dev/null 2>&1; ollama stop "$3" >/dev/null 2>&1
}
run defaults-yarn3b-llama32 qwen2.5-coder-yarn:3b llama3.2:3b-16k
run llama3-2-3b-16k llama3.2:3b-16k llama3.2:3b-16k
run ts-granite4-micro-16384 ts-granite4-micro-16384 ts-granite4-micro-16384
run ts-qwen3-4b-16384 ts-qwen3-4b-16384 ts-qwen3-4b-16384
run ts-phi4-mini-16384 ts-phi4-mini-16384 ts-phi4-mini-16384
run ts-gemma3-4b-16384 ts-gemma3-4b-16384 ts-gemma3-4b-16384
run ts-qwen25c-7b-16384 ts-qwen25c-7b-16384 ts-qwen25c-7b-16384
run ts-qwen25c-7b-builder-granite-thinker ts-qwen25c-7b-16384 ts-granite4-micro-16384
echo FULLEXISTING-DONE
