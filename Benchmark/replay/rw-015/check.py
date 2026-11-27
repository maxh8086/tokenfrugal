"""Replay task rw-015: gateway/config.py check_persona() accepts known persona slugs and rejects others (offline)."""
import os
import sys

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
CFG = {
    "overrides": {"override-slug": {}},
    "persona_models": {"model-slug": {}},
    "persona_skills": {"skill-slug": {}},
    "members": {"team-one": ["member-slug"], "team-two": ["other-member"]},
}
KNOWN = ["override-slug", "model-slug", "skill-slug", "member-slug", "other-member"]


def fail(message):
    print("FAIL:", message)
    return 1


def error_for(slug):
    return "unknown persona '%s'; call list_roles for valid slugs" % slug


def main():
    try:
        from gateway.config import check_persona
    except Exception as exc:
        return fail("cannot import check_persona: %r" % (exc,))
    try:
        for slug in KNOWN:
            if check_persona(slug, CFG) != "":
                return fail("check_persona(%r) did not return an empty string" % (slug,))
        got = check_persona("ghost-slug", CFG)
        if got != error_for("ghost-slug"):
            return fail("unknown slug returned %r" % (got,))
        for cfg in ({}, {"members": {}}):
            got = check_persona("model-slug", cfg)
            if got != error_for("model-slug"):
                return fail("cfg %r returned %r for model-slug, expected the error" % (cfg, got))
    except Exception as exc:
        return fail("check_persona raised %r" % (exc,))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
