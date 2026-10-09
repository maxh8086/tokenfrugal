for m in granite3.3:8b llama3.1:8b qwen2.5:7b qwen3:8b ministral-3:8b gemma3:4b gemma4:e4b qwen2.5vl:7b deepseek-r1:8b starcoder2:7b; do
  echo "### pull $m"; ollama pull $m 2>&1 | tr '\r' '\n' | tail -n 1
done
echo PULL-DONE
