"""Media briefing (stdio). Mode B: turns a short written brief into a narrated motion-graphics MP4 in Render.

Slice 1 stub: validates the brief and returns the error strings. The render stages (voice, HyperFrames,
mux, music bed, stills gate) are added in later tasks; a valid brief returns "error: not built yet" until then.
"""
import re
from pathlib import Path

from fastmcp import FastMCP

from router.media_workspace import media_dir

mcp = FastMCP("media-briefing")

MAX_WORDS = 90
LENGTH_MIN_S = 20
LENGTH_MAX_S = 30
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_ .()-]{0,119}")


class BriefError(ValueError):
    """Raised with the exact error text returned to the caller (after 'error: ')."""


def validate(text: str, length_target_s: float, music: bool, out_name: str, render_dir: Path) -> dict:
    """Check one brief. Returns the normalised fields or raises BriefError with the message."""
    words = (text or "").split()
    if not words:
        raise BriefError("error: text is empty")
    if len(words) > MAX_WORDS:
        raise BriefError(f"error: text over {MAX_WORDS} words ({len(words)})")
    if not isinstance(length_target_s, (int, float)) or isinstance(length_target_s, bool) \
            or not LENGTH_MIN_S <= length_target_s <= LENGTH_MAX_S:
        raise BriefError(f"error: length_target_s must be {LENGTH_MIN_S} to {LENGTH_MAX_S}")
    if not isinstance(music, bool):
        raise BriefError("error: music must be true or false")
    name = (out_name or "").strip()
    if not _NAME.fullmatch(name) or ".." in name:
        raise BriefError("error: bad output name")
    if (render_dir / f"{name}.mp4").exists() or (render_dir / f"{name}.run").exists():
        raise BriefError("error: out_name_exists")
    return {"text": " ".join(words), "length_target_s": length_target_s, "music": music, "out_name": name}


@mcp.tool()
def brief(text: str, out_name: str, length_target_s: float = 25, music: bool = False) -> str:
    """Make a narrated motion-graphics MP4 from a short brief. text = the narration (max 90 words).
    out_name = bare output name, written to Render/<out_name>.mp4. length_target_s = 20 to 30 seconds.
    music = True adds the neutral music bed. Returns exit=0 and the Render path, or an error line."""
    try:
        validate(text, length_target_s, music, out_name, media_dir() / "Render")
        return "error: not built yet"
    except BriefError as e:
        return str(e)
    except Exception as e:  # noqa: BLE001
        return f"error: {type(e).__name__}: {str(e)[:150]}"


if __name__ == "__main__":
    mcp.run()
