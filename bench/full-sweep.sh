#!/bin/bash
# pulls the remaining models, then runs ALL 16 realworld cases (n=2) on every new model, one model loaded at a time
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
for m in qwen2.5vl:7b deepseek-r1:8b starcoder2:7b MichelRosselli/bonsai-27b; do
  echo "### pull $m"; ollama pull "$m" 2>&1 | tr '\r' '\n' | tail -1
done
echo PULLS-DONE
for base in granite3.3:8b llama3.1:8b qwen2.5:7b qwen3:8b ministral-3:8b gemma3:4b gemma4:e4b qwen2.5vl:7b deepseek-r1:8b starcoder2:7b MichelRosselli/bonsai-27b; do
  ollama show "$base" >/dev/null 2>&1 || { echo "### $base MISSING"; continue; }
  tag="ts-$(echo "$base" | tr '/:.' '---' | tr 'A-Z' 'a-z')-16384"
  printf 'FROM %s\nPARAMETER num_ctx 16384\nPARAMETER temperature 0.1\n' "$base" > "models/trial/$tag.Modelfile"
  ollama create "$tag" -f "models/trial/$tag.Modelfile" >/dev/null 2>&1
  echo "### $tag FULL"
  TOKENFRUGAL_MODEL_BUILDER=$tag TOKENFRUGAL_MODEL_THINKER=$tag \
   PYTHONPATH=. .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag full-$tag 2>&1 | grep -E "realworld/|wrote|passed"
  ollama ps | tail -n +2
  ollama stop $tag >/dev/null 2>&1
done
echo FULLSWEEP-DONE
