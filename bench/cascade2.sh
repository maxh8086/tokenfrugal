cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
export PYTHONPATH=. PYTHONIOENCODING=utf-8
until grep -q CASCADE-DONE bench/cascade.log; do sleep 20; done
.venv/Scripts/python.exe -m scripts.cascade_run bench/20261009-234628-full-defaults-yarn3b-llama32.json ts-gemma4-e4b-16384 defaults-then-gemma4 2>&1 | grep -E "primary|realworld/|wrote"
echo CASCADE2-DONE
