# Text encoder quantization and render evaluation (FLUX.2 klein, Qwen3-4B)

Status: 2026-11-05. The bf16 baseline render is done (section 3.9). Q4_K_S is the chosen encoder and is the only Qwen3-4B file kept locally and in the repos. Cleanup is done (section 4): the FP8 files and the merged bf16 file were deleted from disk, the FP8 file was removed from `maxh8086/tokenfrugal-flux2-klein-4b-fp8`, and the Q4_K_S GGUF is published at `maxh8086/tokenfrugal-qwen3-4b-q4ks` (public).

## 1. Goal

Replace the bf16 Qwen3-4B text encoder used by FLUX.2 klein with a smaller file, keep it only if output quality is not hurt, and record the evidence in each model repo.

## 2. Files

| Role | File | Size |
| --- | --- | --- |
| bf16 reference (not downloaded yet) | `Qwen/Qwen3-4B` safetensors (2 shards) | about 8.0 GB |
| F16 GGUF (intermediate) | `scratchpad/qwen3-4b-f16.gguf` | 8,829,197,216 B |
| Q4_K_S GGUF (kept candidate) | `models/image_generation/comfy-t2i/text_encoders/qwen3-4b-Q4_K_S.gguf` | 2,602,097,056 B |
| FP8 safetensors (from HF `Qwen/Qwen3-4B-FP8`, shards merged) | `models/image_generation/comfy-t2i/text_encoders/qwen3-4b-fp8.safetensors` | 5,190,053,664 B |

The FP8 file has 252 `F8_E4M3` tensors, 252 `weight_scale_inv` tensors and 399 BF16 tensors. It uses HF block-wise FP8 scaling.

## 3. Steps performed

### 3.1 Build llama.cpp tools on the host (no container)

Source: `C:\Users\vaibh\Downloads\Projects\llama.cpp\llama.cpp` (commit 10b8b7553). CUDA off. Visual Studio Build Tools and cmake were installed system-wide, outside the repos.

```bash
cd /c/Users/vaibh/Downloads/Projects/llama.cpp/llama.cpp
cmake -B build -DGGML_CUDA=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j 8 --target llama-quantize llama-perplexity
```

Copies used by tokenfrugal (gitignored, `tools/llama.cpp/bin/`):

```bash
cp build/bin/Release/llama-quantize.exe /c/Users/vaibh/Downloads/Projects/tokenfrugal/tools/llama.cpp/bin/
cp build/bin/Release/*.dll              /c/Users/vaibh/Downloads/Projects/tokenfrugal/tools/llama.cpp/bin/
/c/Users/vaibh/Downloads/Projects/tokenfrugal/tools/llama.cpp/bin/llama-quantize.exe --help
```

### 3.2 Convert HF to F16 GGUF (one model at a time)

`gguf-py` cannot write K-quants, so the conversion path is HF to F16 GGUF, then `llama-quantize`. The converter needs huggingface-hub 1.x, which conflicts with the global Python (2.2.0). It was run with a scratchpad-only install, and the global Python was not changed.

```bash
export MSYS_NO_PATHCONV=1
SCR=/c/Users/vaibh/AppData/Local/Temp/claude/048adbe4a86ce95e/c8ade746-37e7-400f-955b-7bb35680397a/scratchpad
pip install --target "$SCR/pylib" "huggingface-hub>=1.0"
PYTHONPATH="$SCR/pylib" python llama.cpp/convert_hf_to_gguf.py "$SCR/qwen3-4b-hf" \
  --outtype f16 --outfile "$SCR/qwen3-4b-f16.gguf" > "$SCR/convert.log" 2>&1
```

`qwen3-4b-hf/` holds the config and tokenizer files, plus a hard link to the source weights.

### 3.3 Quantize F16 to Q4_K_S

```bash
TOOLS=/c/Users/vaibh/Downloads/Projects/tokenfrugal/tools/llama.cpp/bin
$TOOLS/llama-quantize.exe "$SCR/qwen3-4b-f16.gguf" \
  "/c/Users/vaibh/Downloads/Projects/tokenfrugal/models/image_generation/comfy-t2i/text_encoders/qwen3-4b-Q4_K_S.gguf" Q4_K_S \
  > "$SCR/quantize.log" 2>&1
ls -l /c/Users/vaibh/Downloads/Projects/tokenfrugal/models/image_generation/comfy-t2i/text_encoders/qwen3-4b-Q4_K_S.gguf
```

Expected size: about 2.60 GB, from 8.83 GB F16.

### 3.4 Quality check 1: perplexity (text)

Same text sample and parameters for both files. Lower is better.

```bash
PPL=/c/Users/vaibh/Downloads/Projects/llama.cpp/llama.cpp/build/bin/Release/llama-perplexity.exe
$PPL -m "$SCR/qwen3-4b-f16.gguf" -f "$SCR/ppl_text.txt" -c 512 -t 8 -ngl 0 > "$SCR/ppl_f16.log" 2>&1
$PPL -m "<path to Q4_K_S gguf>"  -f "$SCR/ppl_text.txt" -c 512 -t 8 -ngl 0 > "$SCR/ppl_q4.log"  2>&1
grep "Final estimate" "$SCR/ppl_f16.log" "$SCR/ppl_q4.log"
```

Results:

| Model | PPL | Relative to F16 |
| --- | --- | --- |
| F16 | 10.3028 +/- 1.10517 | baseline |
| Q4_K_S | 10.8623 +/- 1.16969 | +5.4% |

### 3.5 Test: ComfyUI render with each encoder

Only the text encoder changes between runs. Everything else is fixed.

- Container: `tokenfrugal/comfyui:1` through `docker-compose.gpu.yml` (project `tokenfrugal-gpu`). The compose stack was started for the run and stopped afterwards.
- Workflow: `scratchpad/samples/workflow_fp8_<n>.json` and `workflow_gguf_<n>.json`. The GGUF one uses `DualCLIPLoaderGGUF` or `CLIPLoaderGGUF` with the Q4_K_S file. The FP8 one uses `CLIPLoader` with the FP8 safetensors.
- Settings: 768x768, 4 steps, euler sampler, cfg 1.0, seed n for prompt n.
- Prompts (5): red bicycle, blue teapot, small dog, brick house, orange juice.

Driver: `scratchpad/run_klein_compare.py` (submits each workflow to the ComfyUI API and saves the output image). Output log: `scratchpad/samples/render.log`, which ends with `ALL DONE`.

```bash
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
docker compose -f docker-compose.gpu.yml up -d comfyui
python "$SCR/run_klein_compare.py" > "$SCR/samples/render.log" 2>&1
docker compose -f docker-compose.gpu.yml stop comfyui
```

### 3.6 Quality check 2: image metrics and visual review

Metrics are grayscale PSNR and SSIM (7x7 uniform window, manual implementation, since scikit-image is not installed). These measure how far the two renders differ, not which one is better. A visual check is required.

```bash
python "$SCR/metrics_sheet.py"
```

Output: 5 pairs with PSNR and SSIM, plus `samples/contact_sheet.png` (FP8 left, Q4_K_S right).

### 3.7 Result: 5-prompt comparison

| # | Prompt | FP8 PSNR (dB) | FP8 SSIM | FP8 wall (s) | Q4_K_S wall (s) |
| --- | --- | --- | --- | --- | --- |
| 1 | red bicycle, white wall | 10.91 | 0.5437 | 26.5 | 43.2 |
| 2 | blue ceramic teapot | 10.78 | 0.5709 | 28.3 | 42.4 |
| 3 | small dog, green field | 10.67 | 0.3881 | 28.2 | 42.7 |
| 4 | old brick house, ivy | 10.88 | 0.2445 | 28.3 | 42.9 |
| 5 | orange juice, marble | 12.03 | 0.7077 | 28.3 | 44.8 |

Visual result: the FP8 renders show a flat teal texture and no subject in 5 of 5. The Q4_K_S renders show the described subject in 5 of 5. The low PSNR and SSIM are caused by that failure. They do not score quality.

Conclusion so far: the FP8 encoder does not work in ComfyUI as loaded. The Q4_K_S encoder does.

### 3.8 Recording results

- Each model repo got a `## Local quality check` section in its README (script `scratchpad/hf_eval_cards.py`, uploaded with `huggingface_hub` `upload_file`, then verified by re-downloading each README).
- The contact sheet was uploaded to `maxh8086/tokenfrugal-flux2-klein-4b-fp8` at `eval/klein_fp8_vs_q4ks_contact_sheet.png`.
- All 9 repos stay public (`repo_info(...).private == False`).

### 3.9 bf16 baseline render (done 2026-11-05)

Purpose: check whether the FP8 file format causes the failure, using the unquantized encoder.

Steps:

```bash
export MSYS_NO_PATHCONV=1
SCR=/c/Users/vaibh/AppData/Local/Temp/claude/048adbe4a86ce95e/c8ade746-37e7-400f-955b-7bb35680397a/scratchpad
cd /c/Users/vaibh/Downloads/Projects/tokenfrugal
# 1. Download the bf16 reference (3 shards, about 8.0 GB total), log to the scratchpad
huggingface-cli download Qwen/Qwen3-4B --local-dir "$SCR/qwen3-4b-bf16-shards" --include "*.safetensors" "*.json" > "$SCR/dl_bf16.log" 2>&1
# 2. Merge the shards into one file, streaming (no full model in RAM)
python "$SCR/stream_merge.py" "$SCR/qwen3-4b-bf16-shards" \
  models/image_generation/comfy-t2i/text_encoders/qwen3-4b-bf16.safetensors
# 3. Start ComfyUI and render the five prompts with the bf16 encoder
docker compose -f docker-compose.gpu.yml up -d comfyui
python "$SCR/run_klein_bf16.py" > "$SCR/samples/render_bf16.log" 2>&1
docker compose -f docker-compose.gpu.yml stop comfyui
```

Checks: the merged file has 398 tensors, all BF16, matching `model.safetensors.index.json`. Each render took 64.7 to 80.8 s. The log ends with `ALL DONE`.

Metrics (grayscale, 7x7 SSIM window, same as section 3.6):

| # | bf16 vs Q4_K_S PSNR (dB) | bf16 vs Q4_K_S SSIM | bf16 vs FP8 PSNR (dB) | bf16 vs FP8 SSIM |
| --- | --- | --- | --- | --- |
| 1 | 19.06 | 0.854 | 11.00 | 0.558 |
| 2 | 15.15 | 0.824 | 10.14 | 0.567 |
| 3 | 14.28 | 0.691 | 11.95 | 0.389 |
| 4 | 18.35 | 0.748 | 10.82 | 0.246 |
| 5 | 17.37 | 0.856 | 11.93 | 0.708 |

Contact sheet (bf16, FP8, Q4_K_S per row): `scratchpad/samples/contact_sheet_3way.png`.

Reading: bf16 and Q4_K_S are much closer to each other than bf16 is to FP8. The FP8 file is far from the bf16 reference, so the FP8 format is the likely cause of the broken renders. The metrics measure distance, not quality, so visual review of the bf16 render is still the decision basis.

## 4. Not done

- Done since section 3.9: visual review of the 3-way sheet (bf16 and Q4_K_S match; FP8 is noise), klein HF README updated with the bf16 section and the 3-way sheet uploaded to `eval/klein_bf16_fp8_q4ks_contact_sheet.png`, bf16 shard folder deleted (~8 GB freed).
- Done 2026-11-05, cleanup (user chose "Q4 only, delete bf16"):
  1. Uploaded `qwen3-4b-Q4_K_S.gguf` (2,602,097,056 bytes) to `maxh8086/tokenfrugal-qwen3-4b-q4ks` with a model card (perplexity, source, Apache-2.0). Remote size matched the local file. Repo set to public.
  2. Removed `qwen3-4b-fp8.safetensors` from `maxh8086/tokenfrugal-flux2-klein-4b-fp8`. The image model `flux-2-klein-4b-fp8.safetensors` and `flux2-vae.safetensors` stay. The klein README was updated to match.
  3. Updated `scripts/hf_models.json` (klein entry drops the FP8 encoder; new `qwen3-4b-q4ks` entry), `scripts/fetch_comfy_models.sh` (FP8 shard fetches removed), and `docker/comfyui/workflows/flux1-dev-text-to-image.json` (the CLIP node is now `CLIPLoaderGGUF` with `qwen3-4b-Q4_K_S.gguf`, with the download URL pointing to the Q4 repo).
  4. Deleted from disk: `qwen3-4b-bf16.safetensors`, `qwen3-4b-fp8.safetensors`, `qwen3-4b-fp8-00001.safetensors`, `qwen3-4b-fp8-00002.safetensors`. Kept: `qwen3-4b-Q4_K_S.gguf`, and the `qwen3vl-4b-fp8` files (untested; Mage-Flow depends on them).
- Not yet verified: that the flux1-dev workflow loads the Q4 GGUF in ComfyUI after the node change (run the workflow once the stack is up). C: has about 22 GB free after the deletions.
- Verification of FP8 Qwen3-VL-4B. Same format, not tested.
- Output test for LTX 0.9.8 GGUF and SDXL-Turbo workflows in ComfyUI.
- Licence check before the repos stay public (several licences are marked UNVERIFIED in `scripts/hf_models.json`).

## 5. Decision pending

Use the Q4_K_S encoder in the manifest in place of the FP8 file. Options:
1. Replace `qwen3-4b-fp8` with Q4_K_S in `scripts/hf_models.json`, and re-upload the GGUF to the klein repo.
2. Run the bf16 baseline first (needs disk space) to see if the FP8 file can be repaired.

## 6. How to reproduce

Run the commands in section 3 in order. Each stage stops the GPU container before the next starts.

## 7. Disk space blocker

C: has 8.3 GB free. The bf16 Qwen3-4B download needs about 8.0 GB, and the F16 GGUF (8.8 GB) is the largest intermediate. Free space before section 4's first item, for example by deleting `scratchpad/qwen3-4b-f16.gguf` once the Q4_K_S file is verified.
