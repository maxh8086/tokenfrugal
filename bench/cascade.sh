cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
export PYTHONPATH=. PYTHONIOENCODING=utf-8
P=.venv/Scripts/python.exe
$P -m scripts.cascade_run bench/20261010-010608-full-ts-qwen25c-7b-16384.json ts-gemma4-e4b-16384 qwen25c-then-gemma4 2>&1 | grep -E "primary|realworld/|wrote"
$P -m scripts.cascade_run bench/20261009-235757-full-llama3-2-3b-16k.json ts-gemma4-e4b-16384 llama32-then-gemma4 2>&1 | grep -E "primary|realworld/|wrote"
$P -m scripts.cascade_run bench/20261010-030639-full-ts-gemma4-e4b-16384.json llama3.2:3b-16k gemma4-then-llama32 2>&1 | grep -E "primary|realworld/|wrote"
echo CASCADE-DONE
