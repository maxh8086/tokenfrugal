"""Model manifest: what each generator needs, where it comes from, and what to offer if the user declines.

check:       paths (relative to the model folder) that must exist for the model to count as present.
sources:     (repo_id, allow_patterns or None, destination subfolder, {downloaded prefix: renamed prefix}).
required_by: scripts (relative to kalamanch/) that cannot run without the model; "script:variant" limits it to
             one first argument (chain_gen.py ltx).
gated:       the Hugging Face repo needs `huggingface-cli login` and an accepted licence.
alternatives: shown when the user declines the download; the agent asks before pulling any of them.
"""

MODELS = {
    "ltx-video-2b-distilled": {
        "check": ["ltxv-2b-0.9.8-distilled.safetensors", "text_encoder", "vae_0.9.8/diffusion_pytorch_model.safetensors"],
        "sources": [
            ("Lightricks/LTX-Video", ["ltxv-2b-0.9.8-distilled.safetensors", "model_index.json", "scheduler/*",
                                      "tokenizer/*", "text_encoder/*", "transformer/*", "vae/*"], "", {}),
            ("Lightricks/LTX-Video-0.9.8-13B-distilled", ["vae/*"], "", {"vae": "vae_0.9.8"}),
        ],
        "required_by": ["generators/generate_ltx.py", "generators/ltx_spec_test.py", "pipeline/chain_gen.py:ltx",
                        "experiments/ltx_bf16_transformer_test.py", "experiments/ltx_guid_test.py",
                        "experiments/ltx_t5bf16_test.py", "experiments/ltx_vae098_test.py",
                        "experiments/convert_ltx_t5_8bit.py"],
        "alternatives": ["wan2.2-ti2v-5b-q4km (smaller transformer, slower)"],
    },
    "wan2.2-ti2v-5b-q4km": {
        "check": ["Wan2.2-TI2V-5B-Q4_K_M.gguf", "VAE/Wan2.2_VAE.safetensors", "diffusers/transformer/config.json",
                  "diffusers/text_encoder", "diffusers/vae"],
        "sources": [
            ("QuantStack/Wan2.2-TI2V-5B-GGUF", ["Wan2.2-TI2V-5B-Q4_K_M.gguf", "VAE/*"], "", {}),
            ("Wan-AI/Wan2.2-TI2V-5B-Diffusers", ["model_index.json", "scheduler/*", "text_encoder/*", "tokenizer/*",
                                                 "vae/*", "transformer/config.json"], "diffusers", {}),
        ],
        "required_by": ["generators/wan_test.py", "pipeline/chain_gen.py:wan22"],
        "alternatives": ["ltx-video-2b-distilled (faster, weaker on hands)"],
    },
    "wan2.1-t2v-1.3b": {
        "check": ["diffusion_pytorch_model.safetensors", "Wan2.1_VAE.pth", "models_t5_umt5-xxl-enc-bf16.pth"],
        "sources": [("Wan-AI/Wan2.1-T2V-1.3B", ["diffusion_pytorch_model.safetensors", "Wan2.1_VAE.pth",
                                                "models_t5_umt5-xxl-enc-bf16.pth", "config.json", "google/umt5-xxl/*"], "", {})],
        "required_by": [],
        "alternatives": [],
    },
    "omniavatar-1.3b": {
        "check": ["pytorch_model.pt", "wav2vec2-base-960h"],
        "sources": [("OmniAvatar/OmniAvatar-1.3B", None, "", {}),
                    ("facebook/wav2vec2-base-960h", None, "wav2vec2-base-960h", {})],
        "required_by": [],
        "alternatives": [],
    },
    "nimvideo-cogvideox-2b-img2vid": {
        "check": ["model_index.json", "transformer"],
        "sources": [("NimVideo/cogvideox-2b-img2vid", None, "", {})],
        "required_by": ["generators/nimvideo_test.py", "pipeline/chain_gen.py:nimvideo"],
        "alternatives": ["ltx-video-2b-distilled"],
    },
    "svd-xt-1.1": {
        "check": ["model_index.json", "unet", "vae"],
        "sources": [("stabilityai/stable-video-diffusion-img2vid-xt-1-1",
                     ["model_index.json", "*/config.json", "*.fp16.safetensors", "scheduler/*", "feature_extractor/*"], "", {})],
        "gated": True,
        "required_by": ["generators/generate_svd.py"],
        "alternatives": ["ltx-video-2b-distilled (not gated)"],
    },
}
