#!/bin/bash
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
M=qwen2.5-coder-yarn:3b
TOKENFRUGAL_MODEL_BUILDER=$M TOKENFRUGAL_MODEL_THINKER=$M PYTHONPATH=. PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.bench --only realworld --n 2 --tag full-yarn3b-solo > bench/yarn3b_solo.log 2>&1
ollama stop $M >/dev/null 2>&1
F=$(ls bench/*full-yarn3b-solo.json | tail -1)
PYTHONPATH=. PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.cascade_run $F ts-gemma4-e4b-16384 yarn3b-solo-then-gemma4 >> bench/yarn3b_solo.log 2>&1
echo YARN-DONE >> bench/yarn3b_solo.log
