#!/bin/bash
# usage: scripts/seq.sh <suite> <tagprefix> model...   sequential, no early drop
# suite: hard | coding. Output goes to Benchmark/results/<suite>.
cd "$(dirname "$0")/.." || exit 1
suite=$1; P=$2; shift 2
for m in "$@"; do
  s=$(echo "$m" | tr '/:' '--')
  echo "=== $P $m $suite $(date +%T)"
  BENCH_SUITE=$suite BENCH_OUT_DIR=Benchmark/results/$suite \
  TOKENFRUGAL_MODEL_BUILDER="$m" TOKENFRUGAL_MODEL_THINKER="$m" PYTHONPATH=. \
    .venv/Scripts/python.exe -m scripts.bench --only realworld --n 3 --tag "$P-$suite-$s" 2>&1 | tail -25
done
echo "=== SEQ DONE $P $suite $(date +%T)"
