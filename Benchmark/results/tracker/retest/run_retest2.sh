#!/usr/bin/env bash
# Second retest: code_l4_rename (ast-grep path hint) and hard_long_summary (sentence counter fix) only.
set -u
cd "C:/Users/vaibh/Downloads/Projects/tokenfrugal" || exit 1
export ANTHROPIC_API_KEY="$(powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')" | tr -d '\r')"
export PYTHONPATH="$PWD" PYTHONIOENCODING=utf-8 CC_WORKSPACE="$(dirname "$PWD")"
export TOKENFRUGAL_MODEL_BUILDER=claude-haiku-5-5 TOKENFRUGAL_MODEL_THINKER=claude-haiku-5-5
export TOKENFRUGAL_LLM_URL=https://api.anthropic.com/v1 TOKENFRUGAL_LLM_API_KEY="$ANTHROPIC_API_KEY"
OUT="$PWD/Benchmark/results/tracker/retest"
export BENCH_OUT_DIR="$OUT"
echo "== coding: code_l4_rename"
BENCH_SUITE=coding BENCH_CASES=code_l4_rename .venv/Scripts/python.exe -m scripts.bench --only realworld --n 3 --tag retest2-coding </dev/null
echo "CODING_EXIT=$?"
echo "== hard: hard_long_summary"
BENCH_SUITE=hard BENCH_CASES=hard_long_summary .venv/Scripts/python.exe -m scripts.bench --only realworld --n 3 --tag retest2-hard </dev/null
echo "HARD_EXIT=$?"
echo "RETEST_DONE"
