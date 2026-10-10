#!/usr/bin/env bash
# Usage: run_round.sh <round-id> <builder-model> [thinker-model]
# Runs the 16 realworld cases (2 runs each), writing ONLY to Benchmark/rounds/<round-id>/raw.
set -e
RID=$1; B=$2; T=${3:-$2}
D="Benchmark/rounds/$RID"
[ -d "$D/raw" ] || { echo "run new_round.py $RID first"; exit 1; }
TAG="$RID-$(echo "$B+$T" | tr -c 'A-Za-z0-9\n' '-' | cut -c1-60)"
if ls "$D/raw"/*"$TAG"* >/dev/null 2>&1; then echo "tag $TAG already has results in this round"; exit 1; fi
BENCH_OUT_DIR="$D/raw" TOKENFRUGAL_MODEL_BUILDER=$B TOKENFRUGAL_MODEL_THINKER=$T \
  PYTHONPATH=. PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag "$TAG"
