// Colour tagging for the final MP4 (D51). HyperFrames exposes no pixel-format or colour flags, so every
// output is re-encoded once by ffmpeg with yuv420p and bt709 tags. No LUT is used. Pure argv builder and checker.

export const COLOUR_TARGET = Object.freeze({
  pix_fmt: 'yuv420p',
  color_space: 'bt709',
  color_primaries: 'bt709',
  color_transfer: 'bt709',
});

// argv that re-encodes the video stream with the D51 tags and copies the audio stream unchanged.
export function colourArgs({ input, out }) {
  return [
    '-y', '-nostdin', '-i', input,
    '-map', '0',
    '-c:v', 'libx264', '-crf', '16', '-preset', 'medium',
    '-pix_fmt', COLOUR_TARGET.pix_fmt,
    '-colorspace', COLOUR_TARGET.color_space,
    '-color_primaries', COLOUR_TARGET.color_primaries,
    '-color_trc', COLOUR_TARGET.color_transfer,
    '-c:a', 'copy',
    '-movflags', '+faststart',
    out,
  ];
}

// Given one video stream as ffprobe reports it (-show_streams), returns the list of mismatches. Empty means it passes.
export function colourFailures(stream) {
  const out = [];
  for (const [key, want] of Object.entries(COLOUR_TARGET)) {
    const got = stream ? stream[key] : undefined;
    if (got !== want) out.push(`${key} is ${got === undefined ? 'missing' : got}, expected ${want}`);
  }
  return out;
}
