#!/bin/bash
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
for m in qwen2.5vl:7b deepseek-r1:8b starcoder2:7b MichelRosselli/bonsai-27b; do
  echo "### pull $m"; ollama pull "$m" 2>&1 | tr '\r' '\n' | tail -1
done
echo PULLS-DONE
