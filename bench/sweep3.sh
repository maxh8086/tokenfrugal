#!/bin/bash
# waits for pulls, builds a 16k variant per base model, runs the 4 failing cases (n=2), one model loaded at a time
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
until grep -q BONSAI-DONE bench/pull2.log; do sleep 15; done
for base in granite3.3:8b llama3.1:8b qwen2.5:7b qwen3:8b ministral-3:8b gemma3:4b gemma4:e4b qwen2.5vl:7b deepseek-r1:8b starcoder2:7b MichelRosselli/bonsai-27b; do
  ollama show "$base" >/dev/null 2>&1 || { echo "### $base MISSING"; continue; }
  tag="ts-$(echo "$base" | tr '/:.' '---' | tr 'A-Z' 'a-z')-16384"
  printf 'FROM %s\nPARAMETER num_ctx 16384\nPARAMETER temperature 0.1\n' "$base" > "models/trial/$tag.Modelfile"
  ollama create "$tag" -f "models/trial/$tag.Modelfile" >/dev/null 2>&1
  echo "### $tag"
  TOKENFRUGAL_MODEL_BUILDER=$tag TOKENFRUGAL_MODEL_THINKER=$tag BENCH_CASES=write_tests,rename_across_files,summarize_readme,role_browser \
   PYTHONPATH=. .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag $tag 2>&1 | grep -E "realworld/|wrote"
  ollama ps | tail -n +2
  ollama stop $tag >/dev/null 2>&1
done
echo SWEEP3-DONE
