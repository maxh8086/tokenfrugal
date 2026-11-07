#!/usr/bin/env python3
"""Copy the build-time libraries listed in LIBS.json into the catalogue, checking every file's sha256.

Run by the media-generator Dockerfile after `npm install` has put the pinned packages in LIBS_ROOT:

    python3 install-libs.py <catalogue_dir> <libs_root>

<libs_root> is the directory that contains node_modules/ (the npm install directory). For each entry in
LIBS.json the source is <libs_root>/node_modules/<package>/<source> and the destination is
<catalogue_dir>/<dest>. The script exits 1 when:

* a source file is missing, or its sha256 differs from LIBS.json (a different version was installed);
* a destination already exists (a vendored copy was left in the catalogue, or the step ran twice).

Standard library only.
"""
import hashlib
import json
import os
import shutil
import sys

# Maps the npm alias used by the Dockerfile (directory name under node_modules) to the package directory.
ALIAS_DIRS = {
    "gsap": "gsap",
    "three-r181": "three-r181",
    "three-r184": "three-r184",
    "d3-delaunay": "d3-delaunay",
    "clipper-lib": "clipper-lib",
    "@fontsource/inter": os.path.join("@fontsource", "inter"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    catalogue, libs_root = os.path.abspath(argv[1]), os.path.abspath(argv[2])
    with open(os.path.join(catalogue, "LIBS.json"), encoding="utf-8") as fh:
        libs = json.load(fh)

    problems = []
    for entry in libs["files"]:
        pkg = entry["package"]
        if pkg not in ALIAS_DIRS or pkg not in libs["packages"]:
            problems.append("unknown package %s for %s" % (pkg, entry["dest"]))
            continue
        src = os.path.join(libs_root, "node_modules", ALIAS_DIRS[pkg], entry["source"].replace("/", os.sep))
        dst = os.path.join(catalogue, entry["dest"].replace("/", os.sep))
        if not os.path.isfile(src):
            problems.append("missing source %s" % src)
            continue
        if os.path.exists(dst):
            problems.append("destination already exists (vendored copy left in catalogue?) %s" % entry["dest"])
            continue
        actual = sha256(src)
        if actual != entry["sha256"]:
            problems.append("sha256 mismatch for %s: expected %s, got %s" % (entry["dest"], entry["sha256"], actual))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)

    if problems:
        for p in problems:
            sys.stderr.write("install-libs: %s\n" % p)
        return 1
    print("install-libs: copied %d files from %d packages" % (len(libs["files"]), len(libs["packages"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
