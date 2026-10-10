# Prompt: start a benchmark from scratch

Attach this file and `Benchmark/Template/README.md`, then paste the text between the lines.

---
Run a new TokenFrugal benchmark round from scratch.

1. Read `Benchmark/Template/README.md` and follow its no-overlap rules. Do not modify `bench/`, the existing
   `Benchmark/*` files or any earlier round.
2. Ask me for: round name, models to test (Ollama tags), context window, VRAM limit, and whether
   `gateway/personas.yaml` may change (default: no).
3. Create the round: `python Benchmark/Template/new_round.py <YYYYMMDD-name>`.
4. Run each model solo with `run_round.sh <round-id> <model>`, serially on the GPU, in the background, and report
   every 10 minutes. Models over the VRAM limit are skipped and listed as skipped.
5. Build the individual-model table (see `RESULT_TABLE_FORMAT.md`). Then rank cascade combos: the primary runs all
   cases, the partner runs only the cases the primary did not fully pass, and a combo only counts if it beats the best
   solo model on score and on time. Run the top candidates for real into the same round.
6. Save tables, responses and a short measured-only conclusion inside the round folder. Show me the diff.
7. Commit with the human author only (no Co-Authored-By, no "generated with" footer). Do not push; ask first.
---
