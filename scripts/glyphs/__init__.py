from pathlib import Path

_DIR = Path(__file__).resolve().parent


def glyph(name: str) -> str:
    """Return the SVG text for ``name``; fall back to document.svg if unavailable."""
    if not name or "/" in name or "\\" in name or ".." in name:
        return (_DIR / "document.svg").read_text(encoding="utf-8")
    path = _DIR / f"{name}.svg"
    if not path.is_file():
        return (_DIR / "document.svg").read_text(encoding="utf-8")
    return path.read_text(encoding="utf-8")
