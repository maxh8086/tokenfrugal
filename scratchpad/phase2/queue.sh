#!/usr/bin/env bash
cd "C:/Users/vaibh/Downloads/Projects/tokenfrugal"
export TOKENFRUGAL_TASK_TIMEOUT=300
MODELS=$(ollama list | awk 'NR>1{print $1}' | grep -v -E '^(qwen2.5-coder-yarn:3b|llama3.2:3b-16k|ts-michelrosselli-bonsai-27b-16384|MichelRosselli/bonsai-27b)$' | sed 's/:latest$//')
for m in $MODELS; do
  echo "$(date +%H:%M:%S) START $m"
  python scripts/bench_model.py --model "$m" > "scratchpad/phase2/$(echo "$m" | tr '/:' '__').log" 2>&1
  echo "$(date +%H:%M:%S) END $m rc=$?"
done
echo "$(date +%H:%M:%S) QUEUE DONE"
