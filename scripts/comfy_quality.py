"""Quality baseline and tuning for the ComfyUI workflow (design docs/designs/comfyui-gpu-lease.md, Piece 5).

  python scripts/comfy_quality.py --workflow ltx098 --seeds 3              # reference and repeat runs, thresholds
  python scripts/comfy_quality.py --workflow ltx098 --seeds 3 --variant teacache

What it does:
  1. For each seed, runs the unchanged workflow twice: a reference clip (kept under Benchmark/results/comfy_reference/,
     git-ignored) and a repeat. The repeat is compared with the reference to measure the noise.
  2. Derives the Tier A thresholds from those repeat comparisons (see tier_a_threshold).
  3. Runs each requested variant at the same seeds. Tier A variants pass or are DROPPED; Tier B variants never pass
     automatically: a side-by-side clip pair is written and the author signs off in Benchmark/results/comfy_signoff.md.

Quality comes before speed: a failing Tier A variant is reported as dropped even when it is faster.

Metrics: PSNR on the luma plane and a simplified SSIM (8x8 non-overlapping blocks, not the Gaussian-window
reference). numpy, scikit-image, OpenCV and imageio are not installed in .venv, so both are pure Python. Clips
are decoded with ffmpeg (rawvideo, gray). Pure Python makes a 65-frame 512x704 comparison take a while; that is
accepted for a tuning tool that runs rarely.

Needs the GPU for the runs (through scripts/comfy_spike.py, with the same refusal guards).
"""
import argparse
import glob
import json
import math
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import comfy_spike as spike  # noqa: E402

SIGNOFF_MD = spike.RESULTS / "comfy_signoff.md"
SEED_POOL = (101, 202, 303, 404, 505)  # --seeds N takes the first N
PSNR_CAP_DB = 100.0  # identical frames give infinite PSNR; cap it
K_SIGMA = 3.0  # threshold = mean - max(K_SIGMA * std, floor margin) over the repeat runs
PSNR_MARGIN_FLOOR_DB = 0.5  # the tolerance is never tighter than this, even when the repeats agree exactly
SSIM_MARGIN_FLOOR = 0.002

# Tier A: neutral knobs, expected to leave the picture unchanged. Tier B: lossy knobs, never auto-pass.
# A variant's patch is a function dict -> dict applied to the workflow. None means no patch is defined yet:
# the node ids and class names must be verified on the GPU first (docker/comfyui/workflows/ltx098.NOTES.md).
VARIANTS = {
    "attention-kernel": {"tier": "A", "what": "attention kernel (a ComfyUI launch flag, not a workflow patch)",
                         "patch": None},
    "offload": {"tier": "A", "what": "offload settings", "patch": None},
    "prompt-cache": {"tier": "A", "what": "caching of encoded prompts", "patch": None},
    "non-model-precision": {"tier": "A", "what": "precision of non-model nodes", "patch": None},
    "teacache": {"tier": "B", "what": "TeaCache (lossy)", "patch": None},
    "fewer-steps": {"tier": "B", "what": "fewer sampler steps (lossy)", "patch": None},
    "other-quant": {"tier": "B", "what": "other model quantization (lossy)", "patch": None},
}


# ---------------------------------------------------------------- pure metrics

def psnr_frame(a, b, peak=255.0):
    """PSNR in dB between two equal-length 8-bit planes (bytes or memoryview). Identical planes give PSNR_CAP_DB."""
    if len(a) != len(b):
        raise ValueError(f"frame sizes differ: {len(a)} and {len(b)} bytes")
    if not len(a):
        raise ValueError("empty frame")
    squared = sum((x - y) * (x - y) for x, y in zip(a, b))
    if squared == 0:
        return PSNR_CAP_DB
    mse = squared / len(a)
    return min(PSNR_CAP_DB, 10.0 * math.log10(peak * peak / mse))


def ssim_frame(a, b, width, height, block=8):
    """Simplified SSIM on a luma plane: mean of the SSIM over non-overlapping block x block windows (K1 0.01, K2 0.03,
    L 255). Not the Gaussian-window reference implementation; only comparable with other numbers from this function."""
    if len(a) != width * height or len(b) != width * height:
        raise ValueError("plane size does not match width x height")
    c1, c2 = (0.01 * 255.0) ** 2, (0.03 * 255.0) ** 2
    total, count = 0.0, 0
    for top in range(0, height - block + 1, block):
        for left in range(0, width - block + 1, block):
            xs, ys = [], []
            for row in range(top, top + block):
                off = row * width + left
                xs.extend(a[off:off + block])
                ys.extend(b[off:off + block])
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            vx = sum((x - mx) ** 2 for x in xs) / n
            vy = sum((y - my) ** 2 for y in ys) / n
            cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
            total += ((2 * mx * my + c1) * (2 * cov + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))
            count += 1
    if count == 0:
        raise ValueError(f"plane {width}x{height} is smaller than the {block}x{block} block")
    return total / count


def frames_from_raw(raw, width, height):
    """Splits raw gray frames (concatenated, width x height each) into per-frame memoryviews."""
    size = width * height
    if size <= 0 or len(raw) % size:
        raise ValueError(f"raw length {len(raw)} is not a whole number of {width}x{height} frames")
    view = memoryview(raw)
    return [view[i:i + size] for i in range(0, len(raw), size)]


def compare_frames(frames_a, frames_b, width, height):
    """Per-frame PSNR and SSIM lists for two clips of the same length and size."""
    if len(frames_a) != len(frames_b):
        raise ValueError(f"frame counts differ: {len(frames_a)} and {len(frames_b)}")
    psnrs = [psnr_frame(a, b) for a, b in zip(frames_a, frames_b)]
    ssims = [ssim_frame(a, b, width, height) for a, b in zip(frames_a, frames_b)]
    return psnrs, ssims


def tier_a_threshold(values, floor_margin):
    """Lowest mean a variant may reach: mean - max(K_SIGMA * std, floor_margin), over the repeat-run values
    (one per seed). The floor keeps the tolerance from collapsing to zero when repeats agree exactly."""
    if len(values) < 2:
        raise ValueError("at least two repeat values are needed to measure noise")
    spread = statistics.stdev(values)
    return statistics.mean(values) - max(K_SIGMA * spread, floor_margin)


def evaluate_tier_a(psnr_values, ssim_values, psnr_threshold, ssim_threshold):
    """True when the mean PSNR and the mean SSIM over the seeds are both at or above their thresholds."""
    if not psnr_values or not ssim_values:
        return False
    return (statistics.mean(psnr_values) >= psnr_threshold) and (statistics.mean(ssim_values) >= ssim_threshold)


def side_by_side_cmd(clip_a, clip_b, out_path):
    """ffmpeg command that stacks two clips side by side (video only)."""
    return ["ffmpeg", "-y", "-v", "error", "-i", str(clip_a), "-i", str(clip_b),
            "-filter_complex", "hstack=inputs=2", "-an", str(out_path)]


# ---------------------------------------------------------------- ffmpeg decoding

def _ffmpeg_needed():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are needed to decode clips (not found on PATH)")


def probe_size(path):
    _ffmpeg_needed()
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "json", str(path)],
                         capture_output=True, check=True, timeout=60)
    stream = json.loads(out.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def decode_gray(path):
    """(width, height, frames) of the luma plane of a clip, read through ffmpeg."""
    width, height = probe_size(path)
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True, timeout=1800)
    return width, height, frames_from_raw(out.stdout, width, height)


def compare_clips(ref_path, cand_path):
    """(mean_psnr, mean_ssim, frames) between two clip files."""
    rw, rh, ref_frames = decode_gray(ref_path)
    cw, ch, cand_frames = decode_gray(cand_path)
    if (rw, rh) != (cw, ch):
        raise ValueError(f"clip sizes differ: {rw}x{rh} and {cw}x{ch}")
    psnrs, ssims = compare_frames(ref_frames, cand_frames, rw, rh)
    return statistics.mean(psnrs), statistics.mean(ssims), len(psnrs)


# ---------------------------------------------------------------- files

def reference_path(workflow, seed, ext=".mp4"):
    return spike.REFERENCE_DIR / f"ref_{workflow}_seed{seed}{ext}"


def find_reference(workflow, seed):
    matches = sorted(glob.glob(str(spike.REFERENCE_DIR / f"ref_{workflow}_seed{seed}.*")))
    return Path(matches[0]) if matches else None


def signoff_instructions(variant, clips):
    lines = [f"Tier B setting '{variant}' is never accepted automatically.",
             "Side-by-side clips to compare:"]
    lines += [f"  {c}" for c in clips]
    lines += [f"Watch each pair, then add a row to {SIGNOFF_MD}:",
              f"  | <date> | {variant} | <seeds> | accept or reject | <your name> | <notes> |",
              "Only signed-off Tier B settings may become defaults."]
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(description="ComfyUI quality baseline (PSNR and SSIM) and Tier A/B tuning.")
    p.add_argument("--workflow", default=spike.DEFAULT_WORKFLOW, help="workflow name in docker/comfyui/workflows")
    p.add_argument("--seeds", type=int, default=3, help=f"number of seeds, 1 to {len(SEED_POOL)}")
    p.add_argument("--variant", action="append", default=[], help="variant name (repeatable); see VARIANTS")
    p.add_argument("--prompt", default=spike.DEFAULT_PROMPT)
    p.add_argument("--comfy-url", default=spike.DEFAULT_COMFY_URL)
    p.add_argument("--ollama-url", default=spike.DEFAULT_OLLAMA_NATIVE)
    p.add_argument("--container", default=spike.DEFAULT_CONTAINER)
    return p


def _run(args, seed, settings, tag, patch=None):
    wf_path = spike.WORKFLOW_DIR / f"{args.workflow}.json"
    return spike.run_once(workflow_path=wf_path, seed=seed, prompt=args.prompt, settings=settings,
                          out_dir=spike.REFERENCE_DIR, comfy_url=args.comfy_url, container=args.container,
                          ollama_native=args.ollama_url, tag=tag, patch=patch)


def _keep_clip(row, dest):
    src = Path(row["output_path"])
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dest)
    row["output_path"] = str(dest)
    return dest


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not 1 <= args.seeds <= len(SEED_POOL):
        print(f"--seeds must be between 1 and {len(SEED_POOL)}")
        return 2
    for name in args.variant:
        if name not in VARIANTS:
            print(f"Unknown variant {name!r}; defined: {', '.join(VARIANTS)}")
            return 2
    wf_path = spike.WORKFLOW_DIR / f"{args.workflow}.json"
    try:
        spike.load_workflow(wf_path)
    except spike.WorkflowError as e:
        print(f"Workflow error: {e}")
        return 2
    try:
        spike.require_free_gpu(args.comfy_url, args.ollama_url)
    except spike.GuardRefused as e:
        print("Refusing to run; the GPU is not free for ComfyUI:")
        for problem in e.problems:
            print(f"  - {problem}")
        return 2

    seeds = SEED_POOL[:args.seeds]
    spike.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    seeds_ref = {}
    noise_psnr, noise_ssim = [], []
    for seed in seeds:
        ref = find_reference(args.workflow, seed)
        if ref is None:
            row = _run(args, seed, "reference=unchanged", f"ref_{args.workflow}")
            ref = _keep_clip(row, reference_path(args.workflow, seed, Path(row["output_path"]).suffix))
            spike.append_row(spike.BASELINE_CSV, row)
        seeds_ref[seed] = ref
        rep = _run(args, seed, "repeat=1", f"rep_{args.workflow}")
        p, s, n = compare_clips(ref, rep["output_path"])
        rep["psnr"], rep["ssim"] = p, s
        spike.append_row(spike.BASELINE_CSV, rep)
        noise_psnr.append(p)
        noise_ssim.append(s)
        print(f"seed {seed}: repeat vs reference  PSNR {p:.3f} dB  SSIM {s:.5f}  ({n} frames)")

    thr_psnr = tier_a_threshold(noise_psnr, PSNR_MARGIN_FLOOR_DB)
    thr_ssim = tier_a_threshold(noise_ssim, SSIM_MARGIN_FLOOR)
    thresholds = f"threshold_psnr={thr_psnr:.3f};threshold_ssim={thr_ssim:.5f}"
    print(f"Noise from {len(seeds)} repeat runs: PSNR mean {statistics.mean(noise_psnr):.3f} dB, "
          f"SSIM mean {statistics.mean(noise_ssim):.5f}")
    print(f"Tier A thresholds: PSNR >= {thr_psnr:.3f} dB, SSIM >= {thr_ssim:.5f} "
          f"(floors {PSNR_MARGIN_FLOOR_DB} dB and {SSIM_MARGIN_FLOOR})")

    if not args.variant:
        print("No variant requested. Defined variants:")
        for name, v in VARIANTS.items():
            state = "patch defined" if v["patch"] else "NOT RUN: no workflow patch yet"
            print(f"  {name} (Tier {v['tier']}): {v['what']}; {state}")
        return 0

    for name in args.variant:
        v = VARIANTS[name]
        if v["patch"] is None:
            print(f"NOT RUN: {name}: no workflow patch is defined yet (node ids unverified; see ltx098.NOTES.md)")
            continue
        clips, p_vals, s_vals = [], [], []
        for seed in seeds:
            row = _run(args, seed, f"variant={name};tier={v['tier']};{thresholds}", f"var_{name}", patch=v["patch"])
            p, s, _n = compare_clips(seeds_ref[seed], row["output_path"])
            row["psnr"], row["ssim"] = p, s
            spike.append_row(spike.BASELINE_CSV, row)
            p_vals.append(p)
            s_vals.append(s)
            clips.append(row["output_path"])
        if v["tier"] == "A":
            ok = evaluate_tier_a(p_vals, s_vals, thr_psnr, thr_ssim)
            verdict = "KEPT (passes Tier A)" if ok else "DROPPED (fails Tier A threshold; quality before speed)"
            print(f"{name}: mean PSNR {statistics.mean(p_vals):.3f} dB, mean SSIM {statistics.mean(s_vals):.5f} -> {verdict}")
        else:
            pair = Path(spike.REFERENCE_DIR) / f"sbs_{name}_{args.workflow}.mp4"
            if shutil.which("ffmpeg"):
                subprocess.run(side_by_side_cmd(seeds_ref[seeds[0]], clips[0], pair), check=True, timeout=1800)
                print(f"{name}: side-by-side pair {pair}")
            else:
                print(f"{name}: ffmpeg not found; build the pair with: "
                      + " ".join(side_by_side_cmd(seeds_ref[seeds[0]], clips[0], pair)))
            print(signoff_instructions(name, [str(seeds_ref[seeds[0]]), clips[0]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
