# Run builder+thinker combos as real tests: run <tag> <builder-model> <thinker-model>.
# Candidates come from Benchmark/combos.md (python -m scripts.bench_combo). Then re-run bench_combo to publish.
#!/bin/bash
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
run() { # tag builder thinker
  echo "### $1"
  TOKENFRUGAL_MODEL_BUILDER=$2 TOKENFRUGAL_MODEL_THINKER=$3 PYTHONPATH=. PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag "pair-$1" 2>&1 | grep -E "realworld/|wrote"
  ollama stop "$2" >/dev/null 2>&1; ollama stop "$3" >/dev/null 2>&1
}
run gemma4-builder-llama32-thinker ts-gemma4-e4b-16384 llama3.2:3b-16k
run gemma4-builder-granite4-thinker ts-gemma4-e4b-16384 ts-granite4-micro-16384
run granite4-solo ts-granite4-micro-16384 ts-granite4-micro-16384
echo PAIRS-DONE
