"""Replay task rw-010: open_role() opens one profile session per name in a list (offline, Docker mocked)."""
import asyncio
import contextlib
import os
import re
import subprocess
import sys
from unittest import mock

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

OPENED = []


@contextlib.asynccontextmanager
async def fake_open_profile(profile):
    OPENED.append(profile)
    yield ("session", profile)


@contextlib.asynccontextmanager
async def fake_open_native(name):
    OPENED.append(("native", name))
    yield ("native-session", name)


def fail(message):
    print("FAIL:", message)
    return 1


def opened_by(profile, native=None):
    import gateway.mcp_client as mc

    OPENED.clear()

    async def go():
        async with mc.open_role(profile, native=native):
            pass

    with mock.patch.object(mc, "open_profile", fake_open_profile), \
            mock.patch.object(mc, "open_native", fake_open_native):
        asyncio.run(go())
    return list(OPENED)


def new_test_file_passes():
    path = os.path.join(ROOT, "tests", "test_open_role_profiles.py")
    if not os.path.isfile(path):
        return False
    proc = subprocess.run([sys.executable, "-m", "unittest", "tests.test_open_role_profiles", "-q"],
                          cwd=ROOT, capture_output=True, text=True, timeout=300)
    combined = proc.stdout + proc.stderr
    ran = re.search(r"Ran ([1-9]\d*) tests?", combined)
    return proc.returncode == 0 and ran is not None and "OK" in combined


def main():
    if opened_by(["build", "analyze", "debug"]) != ["build", "analyze", "debug"]:
        return fail("a list did not open each profile once")
    if opened_by("build") != ["build"]:
        return fail("a string profile did not open once")
    if opened_by(None) != []:
        return fail("None opened a profile")
    with_native = opened_by(["build", "analyze"], native=["synaptree"])
    if [x for x in with_native if isinstance(x, str)] != ["build", "analyze"]:
        return fail("list profiles with native servers opened %r" % (with_native,))
    if ("native", "synaptree") not in with_native:
        return fail("native server was not added")
    if not new_test_file_passes():
        return fail("tests/test_open_role_profiles.py is missing or its tests fail")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
