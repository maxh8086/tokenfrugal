cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
export PYTHONPATH=.
echo "### A granite-thinker + yarn3b-builder"
TOKENFRUGAL_MODEL_THINKER=ts-granite4-micro-16384 .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag confirmA 2>&1 | grep -E "realworld/|wrote"
ollama stop ts-granite4-micro-16384; 
echo "### B granite-thinker + qwen25c-7b builder"
TOKENFRUGAL_MODEL_THINKER=ts-granite4-micro-16384 TOKENFRUGAL_MODEL_BUILDER=ts-qwen25c-7b-16384 .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag confirmB 2>&1 | grep -E "realworld/|wrote"
echo CONFIRM-DONE
