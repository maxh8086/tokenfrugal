"""Replay task fb-001: parse_story() returns the expected sentence list (offline, no model)."""
import os
import sys
import tempfile

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

STORY = (
    "**[Opening shot: a workshop at dawn]**\n"
    "\"The engine is ready. Turn the key!\"\n"
)
EXPECTED = ["The engine is ready.", "Turn the key!"]


def fail(message):
    print("FAIL:", message)
    return 1


def main():
    try:
        from scripts.story_film import parse_story
    except Exception as exc:
        return fail("cannot import parse_story: %r" % (exc,))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "story.md")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(STORY)
        try:
            got = parse_story(path)
        except Exception as exc:
            return fail("parse_story raised %r" % (exc,))
    if got != EXPECTED:
        return fail("parse_story returned %r, expected %r" % (got, EXPECTED))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
