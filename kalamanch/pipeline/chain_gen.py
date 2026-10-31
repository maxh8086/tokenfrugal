"""Chained image-to-video for the audio-length comparison: each model makes clips that continue from the last frame
until the total covers the audio, then the frames are trimmed to the audio length.

Usage: python kalamanch/run.py pipeline/chain_gen.py <wan22|ltx|nimvideo> <photo> <audio.wav> <out.mp4> [prompt]
The whole photo is kept: it is letterboxed onto the model's frame, never cropped, so the head stays in frame.
Output is silent video at the model's native fps; the caller muxes audio for side-by-side viewing.
"""
import os
import sys
import time

import wave

import torch
from diffusers.utils import export_to_video
from PIL import Image

# shared helpers live in ../common (flat next to the script inside the container image)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from _inputs import photo_path
from _models import require, use_models_dir  # noqa: E402
from _publish import publish

PROMPT = ("A realistic video of a man in a navy suit speaking directly to the camera, with loud, emphatic, "
          "directing hand gestures that match his words. His facial expressions are animated and full of emotion. "
          "His upper body and both hands stay in frame. The background has subtle animated light motion while the "
          "camera stays steady.")


def letterbox(img, w, h):
    img = img.convert("RGB")
    s = min(w / img.width, h / img.height)
    nw, nh = round(img.width * s), round(img.height * s)
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(img.resize((nw, nh), Image.LANCZOS), ((w - nw) // 2, (h - nh) // 2))
    return canvas


def chain(run_clip, first_image, total_frames):
    """run_clip(image) -> list of PIL frames. Clip k starts from the last frame of clip k-1."""
    frames, cur = [], first_image
    while len(frames) < total_frames:
        clip = run_clip(cur)
        frames.extend(clip if not frames else clip[1:])  # clip[0] repeats the previous last frame
        cur = clip[-1]
        print(f"clips_done {len(frames)}/{total_frames} frames", flush=True)
    return frames[:total_frames]


def anchored(run_clip, anchor_image, total_frames, overlap=4):
    """Every segment starts from the original photo (no drift carried forward). The first `overlap` frames of each
    new segment are cross-faded over the tail of the previous one so the seam does not jump."""
    frames, seg = [], 0
    while len(frames) < total_frames:
        clip = run_clip(anchor_image, seed=42 + seg)  # new seed per segment so the gestures differ
        if not frames:
            frames.extend(clip)
        else:
            base = len(frames) - overlap
            for i in range(overlap):
                frames[base + i] = Image.blend(frames[base + i], clip[i], (i + 1) / (overlap + 1))
            frames.extend(clip[overlap:])
        seg += 1
        print(f"clips_done {len(frames)}/{total_frames} frames (segment {seg})", flush=True)
    return frames[:total_frames]


def hybrid(run_clip, anchor_image, total_frames, tail_len=9):
    """Like anchored(), but each new segment is also conditioned on the last `tail_len` frames of the output so far.
    The tail carries motion across the seam; the photo stays in as the identity anchor. The first tail_len frames of
    the new clip are cross-faded over the tail, so the seam does not repeat or jump."""
    frames, seg, tail = [], 0, None
    while len(frames) < total_frames:
        clip = run_clip(anchor_image, seed=42 + seg, tail=tail)
        if not frames:
            frames.extend(clip)
        else:
            base = len(frames) - tail_len
            for i in range(tail_len):
                frames[base + i] = Image.blend(frames[base + i], clip[i], (i + 1) / (tail_len + 1))
            frames.extend(clip[tail_len:])
        tail = frames[-tail_len:]
        seg += 1
        print(f"clips_done {len(frames)}/{total_frames} frames (segment {seg}, hybrid)", flush=True)
    return frames[:total_frames]


def build(name):
    if name == "wan22":
        from diffusers import AutoencoderKLWan, FlowMatchEulerDiscreteScheduler, GGUFQuantizationConfig, WanImageToVideoPipeline, WanTransformer3DModel
        base = "wan2.2-ti2v-5b-q4km"
        d = f"{base}/diffusers"
        transformer = WanTransformer3DModel.from_single_file(
            f"{base}/" + os.environ.get("WAN_GGUF", "Wan2.2-TI2V-5B-Q4_K_M.gguf"), config=f"{d}/transformer",
            quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16), torch_dtype=torch.bfloat16)
        vae = AutoencoderKLWan.from_pretrained(f"{d}/vae", torch_dtype=torch.bfloat16)
        te = None
        if os.environ.get("WAN_TE") in ("8bit", "nf4"):  # trimmed variant: bitsandbytes UMT5 text encoder
            from transformers import BitsAndBytesConfig, UMT5EncoderModel
            q = (BitsAndBytesConfig(load_in_8bit=True) if os.environ["WAN_TE"] == "8bit" else
                 BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16))
            te = UMT5EncoderModel.from_pretrained(f"{d}/text_encoder", quantization_config=q, torch_dtype=torch.bfloat16)
        extra = {"text_encoder": te} if te is not None else {}
        pipe = WanImageToVideoPipeline.from_pretrained(d, transformer=transformer, vae=vae, torch_dtype=torch.bfloat16, **extra)
        pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config, shift=float(os.environ.get("WAN_SHIFT", 3.0)))
        embeds = {}
        if te is not None:  # the bnb encoder cannot be offloaded: encode the prompt once, then free it
            with torch.no_grad():
                pe, ne = pipe.encode_prompt(PROMPT, do_classifier_free_guidance=True, device="cuda", max_sequence_length=512)
            embeds = {"prompt_embeds": pe.cpu(), "negative_prompt_embeds": ne.cpu()}
            pipe.text_encoder = None
            del te
            import gc
            gc.collect()
            torch.cuda.empty_cache()
        pipe.enable_model_cpu_offload()
        W, H, N, FPS = 480, 832, 81, 16

        def run(image, seed=42):
            return pipe(image=image, prompt=None if embeds else PROMPT, height=H, width=W, num_frames=N,
                        num_inference_steps=int(os.environ.get("WAN_STEPS", 30)), guidance_scale=float(os.environ.get("WAN_CFG", 6.0)), max_sequence_length=512, output_type="pil",
                        **{k: v.to("cuda") for k, v in embeds.items()},
                        generator=torch.Generator(device="cuda").manual_seed(seed)).frames[0]
        return run, W, H, FPS

    if name == "wana14b":  # Wan2.2 I2V A14B MoE: two Q4_K_S GGUF experts (high/low noise), block-level group offload
        import gc
        from diffusers import AutoencoderKLWan, GGUFQuantizationConfig, WanImageToVideoPipeline, WanTransformer3DModel
        from transformers import BitsAndBytesConfig, UMT5EncoderModel
        base = "wan22-i2v-a14b"
        d = f"{base}/diffusers"
        q = GGUFQuantizationConfig(compute_dtype=torch.bfloat16)
        hi = WanTransformer3DModel.from_single_file(f"{base}/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf", config=f"{d}/transformer", quantization_config=q, torch_dtype=torch.bfloat16)
        lo = WanTransformer3DModel.from_single_file(f"{base}/LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf", config=f"{d}/transformer_2", quantization_config=q, torch_dtype=torch.bfloat16)
        vae = AutoencoderKLWan.from_pretrained(f"{d}/vae", torch_dtype=torch.bfloat16)
        te = UMT5EncoderModel.from_pretrained("wan2.2-ti2v-5b-q4km/diffusers/text_encoder", quantization_config=BitsAndBytesConfig(load_in_8bit=True), torch_dtype=torch.bfloat16)
        pipe = WanImageToVideoPipeline.from_pretrained(d, transformer=hi, transformer_2=lo, vae=vae, text_encoder=te, torch_dtype=torch.bfloat16)
        with torch.no_grad():
            pe, ne = pipe.encode_prompt(PROMPT, do_classifier_free_guidance=True, device="cuda", max_sequence_length=512)
        pe, ne = pe.cpu(), ne.cpu()
        pipe.text_encoder = None; del te; gc.collect(); torch.cuda.empty_cache()
        for t in (hi, lo):
            t.enable_group_offload(onload_device=torch.device("cuda"), offload_device=torch.device("cpu"), offload_type="block_level", num_blocks_per_group=int(os.environ.get("A14B_BLOCKS", 2)))
        vae.enable_tiling(); vae.to("cuda")
        W, H, N, FPS = int(os.environ.get("A14B_W", 480)), int(os.environ.get("A14B_H", 832)), int(os.environ.get("A14B_N", 81)), 16

        def run(image, seed=42):
            return pipe(image=image, prompt=None, prompt_embeds=pe.to("cuda"), negative_prompt_embeds=ne.to("cuda"), height=H, width=W, num_frames=N,
                        num_inference_steps=int(os.environ.get("WAN_STEPS", 20)), guidance_scale=float(os.environ.get("WAN_CFG", 3.5)), output_type="pil",
                        generator=torch.Generator(device="cuda").manual_seed(seed)).frames[0]
        return run, W, H, FPS

    if name == "wanfun":  # Wan2.2 Fun 5B InP: 100-channel input = noise(48) + mask(4) + masked-video latents(48), custom loop
        import gc
        from diffusers import AutoencoderKLWan, FlowMatchEulerDiscreteScheduler, GGUFQuantizationConfig, WanImageToVideoPipeline, WanTransformer3DModel
        from transformers import BitsAndBytesConfig, UMT5EncoderModel
        base = "wan2.2-ti2v-5b-q4km"
        d = f"{base}/diffusers"
        transformer = WanTransformer3DModel.from_single_file(
            f"{base}/Wan2.2-Fun-5B-InP-Q4_K_M.gguf", config=f"{d}/transformer_fun",
            quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16), torch_dtype=torch.bfloat16)
        vae = AutoencoderKLWan.from_pretrained(f"{d}/vae", torch_dtype=torch.bfloat16)
        te = UMT5EncoderModel.from_pretrained(f"{d}/text_encoder", quantization_config=BitsAndBytesConfig(load_in_8bit=True), torch_dtype=torch.bfloat16)
        pipe = WanImageToVideoPipeline.from_pretrained(d, transformer=transformer, vae=vae, text_encoder=te, torch_dtype=torch.bfloat16)
        with torch.no_grad():
            pe, ne = pipe.encode_prompt(PROMPT, do_classifier_free_guidance=True, device="cuda", max_sequence_length=512)
        pe, ne = pe.cpu(), ne.cpu()
        pipe.text_encoder = None; del te; gc.collect(); torch.cuda.empty_cache()
        sched = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config, shift=float(os.environ.get("WAN_SHIFT", 5.0)))
        vae.enable_tiling()
        W, H, N, FPS = 480, 832, 81, 16
        steps, cfg = int(os.environ.get("WAN_STEPS", 20)), float(os.environ.get("WAN_CFG", 5.0))
        mean = torch.tensor(vae.config.latents_mean).view(1, -1, 1, 1, 1).to("cuda", torch.float32)
        inv_std = (1.0 / torch.tensor(vae.config.latents_std)).view(1, -1, 1, 1, 1).to("cuda", torch.float32)

        @torch.no_grad()
        def run(image, seed=42):
            T, h, w = (N - 1) // 4 + 1, H // 16, W // 16
            img = pipe.video_processor.preprocess(image, height=H, width=W).to("cuda", torch.bfloat16)  # [1,3,H,W] in [-1,1]
            video = torch.cat([img.unsqueeze(2), torch.zeros(1, 3, N - 1, H, W, device="cuda", dtype=torch.bfloat16)], dim=2)
            vae.to("cuda")
            lat = vae.encode(video).latent_dist.mode().float()
            lat = (lat - mean) * inv_std  # masked-video latents
            vae.to("cpu"); torch.cuda.empty_cache()
            msk = torch.zeros(1, 1, N, h, w, device="cuda"); msk[:, :, 0] = 1
            msk = torch.cat([msk[:, :, :1].repeat(1, 1, 4, 1, 1), msk[:, :, 1:]], dim=2)
            msk = msk.view(1, T, 4, h, w).transpose(1, 2)  # [1,4,T,h,w]
            cond = torch.cat([msk, lat], dim=1).to(torch.bfloat16)
            g = torch.Generator(device="cuda").manual_seed(seed)
            x = torch.randn(1, 48, T, h, w, device="cuda", generator=g, dtype=torch.float32)
            sched.set_timesteps(steps, device="cuda")
            transformer.to("cuda")
            pe_c, ne_c = pe.to("cuda", torch.bfloat16), ne.to("cuda", torch.bfloat16)
            for i, t in enumerate(sched.timesteps):
                inp = torch.cat([x.to(torch.bfloat16), cond], dim=1)
                ts = t.expand(1)
                c = transformer(hidden_states=inp, timestep=ts, encoder_hidden_states=pe_c, return_dict=False)[0]
                u = transformer(hidden_states=inp, timestep=ts, encoder_hidden_states=ne_c, return_dict=False)[0]
                x = sched.step((u + cfg * (c - u)).float(), t, x, return_dict=False)[0]
                print(f"step {i + 1}/{steps}", flush=True)
            transformer.to("cpu"); torch.cuda.empty_cache()
            vae.to("cuda")
            out = vae.decode((x / inv_std + mean).to(torch.bfloat16), return_dict=False)[0]
            vae.to("cpu"); torch.cuda.empty_cache()
            return pipe.video_processor.postprocess_video(out, output_type="pil")[0]
        return run, W, H, FPS

    if name == "kand":  # Kandinsky 6.0 Lite distill (3B, 10 steps, makes audio too: the audio is dropped here)
        from diffusers import Kandinsky6TI2VAPipeline
        pipe = Kandinsky6TI2VAPipeline.from_pretrained("kandinsky-6-lite", torch_dtype=torch.bfloat16)
        pipe.enable_model_cpu_offload()
        W, H, N, FPS = 480, 864, 121, 24

        def run(image, seed=42):
            out = pipe(prompt=PROMPT, image=image, height=H, width=W, num_frames=N, num_inference_steps=10,
                       guidance_scale=1.0, generator=torch.Generator(device="cuda").manual_seed(seed))
            return out.frames[0]
        return run, W, H, FPS

    if name == "cog15":  # CogVideoX1.5 5B I2V, nf4 transformer so it fits 8 GB
        from diffusers import BitsAndBytesConfig, CogVideoXImageToVideoPipeline, CogVideoXTransformer3DModel
        base = "cogvideox1.5-5b-i2v"
        q = (BitsAndBytesConfig(load_in_8bit=True) if os.environ.get("COG_Q") == "8bit" else
             BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16))
        transformer = CogVideoXTransformer3DModel.from_pretrained(base, subfolder="transformer", quantization_config=q, torch_dtype=torch.bfloat16)
        pipe = CogVideoXImageToVideoPipeline.from_pretrained(base, transformer=transformer, torch_dtype=torch.bfloat16)
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
        pipe.vae.enable_slicing()
        W, H, N, FPS = 432, 768, int(os.environ.get("COG_FRAMES", 81)), 16  # rope grid is capped at the base 48x85 patches: height <= 768

        def run(image, seed=42):
            return pipe(image=image, prompt=PROMPT, height=H, width=W, num_frames=N,
                        num_inference_steps=int(os.environ.get("COG_STEPS", 30)), guidance_scale=6.0,
                        generator=torch.Generator(device="cuda").manual_seed(seed)).frames[0]
        return run, W, H, FPS

    if name == "ltx":
        from diffusers import AutoencoderKLLTXVideo, FlowMatchEulerDiscreteScheduler, LTXImageToVideoPipeline, LTXVideoTransformer3DModel
        from transformers import T5EncoderModel
        base = "ltx-video-2b-distilled"
        if os.environ.get("LTX_TE") == "gguf":  # trimmed variant: Q4_K_M T5 from the 0.9.6 GGUF folder
            text_encoder = T5EncoderModel.from_pretrained("ltx-0.9.6-gguf", gguf_file="t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                                                          torch_dtype=torch.bfloat16, device_map="cuda")
        elif os.environ.get("LTX_TE") == "fp4":  # bitsandbytes FP4 T5: encode once, then free it
            from transformers import BitsAndBytesConfig
            q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="fp4", bnb_4bit_compute_dtype=torch.bfloat16)
            text_encoder = T5EncoderModel.from_pretrained(f"{base}/text_encoder", quantization_config=q,
                                                          torch_dtype=torch.bfloat16, device_map="cuda")
        elif os.environ.get("LTX_TE") == "fp8":  # FP8 (e4m3) weight storage, upcast to bf16 per Linear
            text_encoder = T5EncoderModel.from_pretrained(f"{base}/text_encoder", torch_dtype=torch.bfloat16)
            def _fp8_forward(mod):
                return lambda x: torch.nn.functional.linear(x, mod.w8.to(x.dtype), mod.bias)
            for m in text_encoder.modules():
                if isinstance(m, torch.nn.Linear):  # keep an fp8 copy; weight stays a bf16 stub so T5 does not cast inputs to fp8
                    m.register_buffer("w8", m.weight.data.to(torch.float8_e4m3fn), persistent=False)
                    m.weight.data = torch.empty(0, dtype=torch.bfloat16)
                    m.forward = _fp8_forward(m)
            text_encoder.to("cuda")
        else:
            text_encoder = T5EncoderModel.from_pretrained(f"{base}/text_encoder", torch_dtype=torch.bfloat16, device_map="cuda")
        transformer = LTXVideoTransformer3DModel.from_single_file(f"{base}/ltxv-2b-0.9.8-distilled.safetensors", torch_dtype=torch.bfloat16)
        vae = AutoencoderKLLTXVideo.from_pretrained(f"{base}/vae_0.9.8", torch_dtype=torch.bfloat16)
        pipe = LTXImageToVideoPipeline.from_pretrained(base, transformer=transformer, vae=vae, text_encoder=None, torch_dtype=torch.bfloat16)
        pipe.text_encoder = text_encoder
        distilled = [1.0, 0.9937, 0.9875, 0.9812, 0.975, 0.9094, 0.725, 0.4219]
        pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config, use_dynamic_shifting=False, shift=1.0)
        orig_set = pipe.scheduler.set_timesteps
        pipe.scheduler.set_timesteps = lambda num_inference_steps=None, device=None, sigmas=None, mu=None, timesteps=None, **kw: orig_set(sigmas=distilled, device=device)
        if os.environ.get("CHAIN_MODE") == "hybrid":  # the condition pipeline takes the photo plus a frame tail
            from diffusers import LTXConditionPipeline
            pipe = LTXConditionPipeline(scheduler=pipe.scheduler, vae=pipe.vae, text_encoder=pipe.text_encoder,
                                        tokenizer=pipe.tokenizer, transformer=pipe.transformer)
        embeds = {}
        if os.environ.get("LTX_TE") in ("fp8", "fp4"):
            import gc
            with torch.no_grad():
                pe, pm, _, _ = pipe.encode_prompt(PROMPT, do_classifier_free_guidance=False, device="cuda")
            embeds = {"prompt_embeds": pe.cpu(), "prompt_attention_mask": pm.cpu()}
            pipe.text_encoder = None; del text_encoder; gc.collect(); torch.cuda.empty_cache()
        pipe.enable_model_cpu_offload()
        W, H, N, FPS = 512, 704, 97, 24

        def run(image, seed=42, tail=None):
            kw = dict(prompt=None if embeds else PROMPT, **{k: v.to("cuda") for k, v in embeds.items()}, width=W, height=H, num_frames=N, guidance_scale=1.0,
                      decode_timestep=0.05, decode_noise_scale=0.025,
                      generator=torch.Generator(device="cuda").manual_seed(seed))
            if tail is None:
                return pipe(image=image, **kw).frames[0]
            from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition
            conds = [LTXVideoCondition(image=image, frame_index=0, strength=1.0),
                     LTXVideoCondition(video=tail, frame_index=0, strength=float(os.environ.get("TAIL_STRENGTH", "0.6")))]
            return pipe(conditions=conds, **kw).frames[0]
        return run, W, H, FPS

    if name == "nimvideo":
        from diffusers import CogVideoXImageToVideoPipeline
        base = "nimvideo-cogvideox-2b-img2vid"
        pipe = CogVideoXImageToVideoPipeline.from_pretrained(base, torch_dtype=torch.float16)
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
        pipe.vae.enable_slicing()
        W, H, N, FPS = 720, 480, 49, 8

        def run(image, seed=42):
            return pipe(image=image, prompt=PROMPT, height=H, width=W, num_frames=N, num_inference_steps=50,
                        guidance_scale=6.0, generator=torch.Generator(device="cuda").manual_seed(seed)).frames[0]
        return run, W, H, FPS

    sys.exit(f"unknown model: {name}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # model folders are relative to this script
    name = sys.argv[1]
    photo = photo_path(sys.argv[2] if len(sys.argv) > 2 else None)
    audio = sys.argv[3]
    out = sys.argv[4]
    prompt_override = sys.argv[5] if len(sys.argv) > 5 else None
    if prompt_override:
        globals()["PROMPT"] = prompt_override

    with wave.open(audio) as wav:
        seconds = wav.getnframes() / wav.getframerate()
    run, W, H, FPS = build(name)
    total = round(seconds * FPS)
    print(f"model {name} audio_seconds {seconds:.2f} target_frames {total} size {W}x{H} fps {FPS}", flush=True)

    # Default "anchor": every segment starts from the original photo (identity checked at 0, 10 and 20 s).
    # CHAIN_MODE=chain restores the old behaviour: each segment starts from the last frame of the previous one.
    mode = os.environ.get("CHAIN_MODE", "anchor")
    start = time.time()
    anchor = letterbox(Image.open(photo), W, H)
    if mode == "hybrid" and name != "ltx":
        sys.exit("CHAIN_MODE=hybrid is only built for ltx")
    if mode == "anchor":
        frames = anchored(run, anchor, total)
    elif mode == "hybrid":
        frames = hybrid(run, anchor, total)
    else:
        frames = chain(run, anchor, total)
    print(f"generation_seconds {time.time() - start:.1f}", flush=True)
    export_to_video(frames, out, fps=FPS)
    print("wrote", out, flush=True)
    publish(out)


if __name__ == "__main__":
    main()
