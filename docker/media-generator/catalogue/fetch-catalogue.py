#!/usr/bin/env python3
"""Fetch the HyperFrames catalogue files that are not committed, from the pins in FETCH.json.

    python3 fetch-catalogue.py [--hyperframes-version X.Y.Z] <manifest_dir> <out_dir>

<manifest_dir> is the directory that holds FETCH.json and overrides/ (the catalogue directory in the repo).
<out_dir> must not exist or must be empty. Every fetched file is written below <out_dir> at its
catalogue-relative path (for example kinetic-center-build/compositions/components/vendor/geist.css).

Sources, all pinned in FETCH.json:

* "registry": each item is fetched with `npx --yes hyperframes@<hyperframes_cli> add <item> --json --no-clipboard`
  in a scratch directory; each listed file must exist and match its sha256.
* "patches": exact-text replacements applied to a registry file (base "registry"); the patched bytes must match the
  sha256 recorded in the patch.
* "npm": files taken from an npm tarball, whose sha256 is checked before extraction.
* "overrides": authored files shipped in overrides/, checked against their sha256.

The script exits 1 on a missing file, a sha256 mismatch, a patch that does not apply exactly once, a
destination that already exists, or a duplicate destination. Standard library only.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

NPM_REGISTRY = "https://registry.npmjs.org"


def fail(msg):
    sys.stderr.write("fetch-catalogue: %s\n" % msg)
    sys.exit(1)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main(argv):
    args = argv[1:]
    expect_hf = None
    if len(args) >= 2 and args[0] == "--hyperframes-version":
        expect_hf = args[1]
        args = args[2:]
    if len(args) != 2:
        sys.stderr.write(__doc__)
        return 2
    manifest_dir, out_dir = os.path.abspath(args[0]), os.path.abspath(args[1])

    with open(os.path.join(manifest_dir, "FETCH.json"), encoding="utf-8") as fh:
        fetch = json.load(fh)
    hf_version = fetch["hyperframes_cli"]
    if expect_hf is not None and expect_hf != hf_version:
        fail("FETCH.json pins hyperframes %s but the build passes %s" % (hf_version, expect_hf))

    if os.path.exists(out_dir) and os.listdir(out_dir):
        fail("output directory exists and is not empty: %s" % out_dir)
    os.makedirs(out_dir, exist_ok=True)

    data = {}  # catalogue-relative path -> bytes

    # 1. Registry items at the pinned CLI version.
    npx = shutil.which("npx")
    if npx is None:
        fail("npx not found on PATH")
    for item in sorted(fetch["registry"]):
        files = fetch["registry"][item]
        work = tempfile.mkdtemp(prefix="hf-%s-" % item)
        try:
            cwd = os.path.join(work, item)
            # npx can fail transiently (network, npm cache lock). Retry the whole add in a clean directory.
            for attempt in range(1, 4):
                shutil.rmtree(cwd, ignore_errors=True)
                os.makedirs(cwd)
                proc = subprocess.run(
                    [npx, "--yes", "hyperframes@" + hf_version, "add", item, "--json", "--no-clipboard"],
                    cwd=cwd, capture_output=True, text=True, timeout=600)
                if proc.returncode == 0:
                    break
                last = "exit %d; stdout: %s; stderr: %s" % (
                    proc.returncode, proc.stdout.strip()[-300:], proc.stderr.strip()[-300:])
                sys.stderr.write("fetch-catalogue: hyperframes add %s attempt %d failed (%s)\n" % (item, attempt, last))
            else:
                fail("hyperframes add %s failed 3 times: %s" % (item, last))
            for rel in sorted(files):
                src = os.path.join(cwd, *rel.split("/"))
                if not os.path.isfile(src):
                    fail("registry output missing %s/%s" % (item, rel))
                with open(src, "rb") as fh:
                    blob = fh.read()
                if sha256_bytes(blob) != files[rel]["sha256"]:
                    fail("sha256 mismatch for registry file %s/%s" % (item, rel))
                data[item + "/" + rel] = blob
        finally:
            shutil.rmtree(work, ignore_errors=True)

    # 2. Patches on registry bytes.
    for p in fetch.get("patches", []):
        key = p["dest"]
        if p.get("base") != "registry":
            fail("unknown patch base for %s: %r" % (key, p.get("base")))
        if key not in data:
            fail("patch target is not a registry file: %s" % key)
        text = data[key].decode("utf-8")
        for r in p["replace"]:
            n = text.count(r["old"])
            if n != 1:
                fail("patch for %s: old text occurs %d times" % (key, n))
            text = text.replace(r["old"], r["new"], 1)
        blob = text.encode("utf-8")
        if sha256_bytes(blob) != p["sha256"]:
            fail("sha256 mismatch after patching %s" % key)
        data[key] = blob

    # 3. npm tarballs (checked before extraction; only the listed members are read).
    for pkg in fetch.get("npm", []):
        name = pkg["package"].split("/")[-1]
        url = "%s/%s/-/%s-%s.tgz" % (NPM_REGISTRY, pkg["package"], name, pkg["version"])
        with urllib.request.urlopen(url, timeout=120) as resp:
            tgz = resp.read()
        if sha256_bytes(tgz) != pkg["tarball_sha256"]:
            fail("tarball sha256 mismatch for %s@%s" % (pkg["package"], pkg["version"]))
        with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as tf:
            for f in pkg["files"]:
                try:
                    member = tf.getmember("package/" + f["source"])
                except KeyError:
                    fail("tarball of %s@%s has no member %s" % (pkg["package"], pkg["version"], f["source"]))
                blob = tf.extractfile(member).read()
                if sha256_bytes(blob) != f["sha256"]:
                    fail("sha256 mismatch for %s from %s@%s" % (f["source"], pkg["package"], pkg["version"]))
                data[f["dest"]] = blob

    # 4. Authored overrides shipped next to the manifest.
    for o in fetch.get("overrides", []):
        src = os.path.join(manifest_dir, *o["source"].split("/"))
        with open(src, "rb") as fh:
            blob = fh.read()
        if sha256_bytes(blob) != o["sha256"]:
            fail("sha256 mismatch for override %s" % o["source"])
        data[o["dest"]] = blob

    # 5. Write everything; refuse to overwrite anything.
    for dest in sorted(data):
        dst = os.path.join(out_dir, *dest.split("/"))
        if os.path.exists(dst):
            fail("destination already exists: %s" % dest)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(data[dest])

    print("fetch-catalogue: wrote %d files (hyperframes %s, %d registry items, %d patches, %d npm files)"
          % (len(data), hf_version, len(fetch["registry"]), len(fetch.get("patches", [])),
             sum(len(p["files"]) for p in fetch.get("npm", []))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
