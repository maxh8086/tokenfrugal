# ComfyUI Tier B sign-off

Tier B settings (lossy knobs: TeaCache, fewer steps, other quantizations) never pass automatically.
`python scripts/comfy_quality.py` writes a side-by-side clip pair for each Tier B variant and prints the
instructions. Only a setting signed off here may become a default. Clips live in
`Benchmark/results/comfy_reference/` (git-ignored).

| Date | Setting | Seeds | Decision (accept or reject) | Signed off by | Notes |
| --- | --- | --- | --- | --- | --- |
