#!/usr/bin/env python3
"""Fetch the HyperFrames catalogue files that are not committed, from the pins in FETCH.json.

    python3 fetch-catalogue.py [--hyperframes-version X.Y.Z] <manifest_dir> <out_dir>

<manifest_dir> is the directory that holds FETCH.json, LIBS.json and overrides/ (the catalogue directory in the repo, or
the same three files staged together, as the Dockerfile does).
<out_dir> must not exist or must be empty. Every fetched file is written below <out_dir> at its
catalogue-relative path (for example kinetic-center-build/compositions/components/vendor/geist.css).

Sources, all pinned in FETCH.json:

* "registry": each item's registry-item.json is read from the HyperFrames registry (the same host and layout that
  `hyperframes@<hyperframes_cli> add` uses), its file list must match the listed files exactly, and each file is
  downloaded directly and must match its sha256. The CLI is not used for this: it caps every file download at 10 s
  for the whole retry chain, and large files (for example glass-shard-title's 1.6 MB HDR) exceed that on ordinary
  links, so the CLI step failed on both the host and in the container.
* "patches": exact-text replacements applied to a registry file (base "registry"); the patched bytes must match the
  sha256 recorded in the patch.
* "npm": files taken from an npm tarball, whose sha256 is checked before extraction.
* "overrides": authored files shipped in overrides/, checked against their sha256.

The script exits 1 on a missing file, a sha256 mismatch, a patch that does not apply exactly once, a
destination that already exists, or a duplicate destination. Standard library only.
"""
import concurrent.futures
import hashlib
import http.client
import io
import json
import os
import sys
import tarfile
import time
import urllib.request

NPM_REGISTRY = "https://registry.npmjs.org"
# Same host and layout as the HyperFrames CLI's default registry, at the release tag that matches FETCH.json's
# hyperframes_cli. The branch "main" moves; the tag does not.
REGISTRY_BASE = "https://raw.githubusercontent.com/heygen-com/hyperframes/v0.8.223/registry"
ITEM_TYPE_DIRS = {"hyperframes:block": "blocks", "hyperframes:component": "components"}
# urllib timeouts apply to each socket read, so a slow but progressing download is not cut off.
HTTP_READ_TIMEOUT_S = 120
HTTP_ATTEMPTS = 5
DOWNLOAD_WORKERS = 8
LOCK_FILE = "hyperframes.lock.json"


def fail(msg):
    sys.stderr.write("fetch-catalogue: %s\n" % msg)
    sys.exit(1)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def http_get(url, what):
    """GET url, retrying transient failures with exponential backoff. Exits 1 after HTTP_ATTEMPTS failures."""
    last = None
    for attempt in range(1, HTTP_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=HTTP_READ_TIMEOUT_S) as resp:
                return resp.read()
        except (OSError, http.client.HTTPException) as err:  # URLError and socket.timeout are OSError
            last = err
            if attempt < HTTP_ATTEMPTS:
                sys.stderr.write("fetch-catalogue: %s attempt %d failed (%s); retrying\n" % (what, attempt, err))
                time.sleep(2 ** attempt)
    fail("%s failed %d times: %s (%s)" % (what, HTTP_ATTEMPTS, last, url))


def registry_asset_url(item_type, name, file_entry):
    if file_entry.get("url") is not None:
        url = file_entry["url"]
        if not url.startswith("https://"):
            fail("unsafe file url for %s: %s" % (name, url))
        return url
    return "%s/%s/%s/%s" % (REGISTRY_BASE, ITEM_TYPE_DIRS[item_type], name, file_entry["path"])


def cli_written_bytes(item_type, item, target, blob):
    """The bytes the HyperFrames CLI writes for a registry file.

    The CLI puts a header line naming the item at the top of each block composition (.html). The pins record the
    written bytes, so the header is added here before hashing. Components and other files are written unchanged.
    """
    if item_type == "hyperframes:block" and target.endswith(".html"):
        return ("<!-- hyperframes-registry-item: %s -->\n" % item).encode("utf-8") + blob
    return blob


def libs_destinations(manifest_dir):
    """Catalogue-relative paths that install-libs.py writes from LIBS.json (for example shaders.iife.js, Inter fonts).

    A registry file at one of these paths is replaced by the bundle, so it must not be written here (install-libs.py
    refuses to overwrite it). Its bytes are still hashed for the lock map.
    """
    with open(os.path.join(manifest_dir, "LIBS.json"), encoding="utf-8") as fh:
        return {entry["dest"] for entry in json.load(fh)["files"]}


def fetch_registry(manifest_dir, fetch):
    """Return {catalogue-relative path: bytes} for every registry file listed in FETCH.json.

    hyperframes.lock.json is written by the CLI, not served by the registry. It is rebuilt here as the CLI wrote it:
    a JSON map from each registry file of the item to its sha256, keys sorted case-insensitively. Its sha256 is pinned.
    Registry files replaced by LIBS.json are in the registry but not written: their bytes are only hashed, for that map.
    """
    replaced_by_libs = libs_destinations(manifest_dir)
    index = json.loads(http_get(REGISTRY_BASE + "/registry.json", "registry index").decode("utf-8"))
    types = {entry["name"]: entry["type"] for entry in index["items"]}
    jobs = []  # (key, url) for every registry file, pinned or not
    plans = {}  # item -> (ordered registry targets, pinned targets)
    for item in sorted(fetch["registry"]):
        if item not in types:
            fail("registry item %s is not in the registry index" % item)
        item_type = types[item]
        if item_type not in ITEM_TYPE_DIRS:
            fail("registry item %s has unsupported type %s" % (item, item_type))
        meta_url = "%s/%s/%s/registry-item.json" % (REGISTRY_BASE, ITEM_TYPE_DIRS[item_type], item)
        meta = json.loads(http_get(meta_url, "registry-item.json for %s" % item).decode("utf-8"))
        pinned = fetch["registry"][item]
        if LOCK_FILE not in pinned:
            fail("FETCH.json has no pin for %s/%s" % (item, LOCK_FILE))
        by_target = {}
        for entry in meta["files"]:
            if entry["target"] in by_target:
                fail("registry item %s lists target %s twice" % (item, entry["target"]))
            by_target[entry["target"]] = entry
        if LOCK_FILE in by_target:
            fail("registry item %s serves %s; the lock is built by this script" % (item, LOCK_FILE))
        want = set(pinned) - {LOCK_FILE}
        missing = sorted(want - set(by_target))
        unexpected = sorted(set(by_target) - want)
        if missing or [t for t in unexpected if item + "/" + t not in replaced_by_libs]:
            fail("registry item %s file list differs from FETCH.json: missing %s, unexpected %s" % (
                item, missing, unexpected))
        targets = list(by_target)
        plans[item] = (targets, pinned)
        for target in targets:
            jobs.append((item + "/" + target, registry_asset_url(item_type, item, by_target[target])))

    def download(job):
        key, url = job
        return key, http_get(url, "download %s" % key)

    blobs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        for key, blob in pool.map(download, jobs):
            blobs[key] = blob

    data = {}
    for item, (targets, pinned) in plans.items():
        digests = {}
        for target in targets:
            blob = cli_written_bytes(types[item], item, target, blobs[item + "/" + target])
            digests[target] = sha256_bytes(blob)
            if target in pinned:
                if digests[target] != pinned[target]["sha256"]:
                    fail("sha256 mismatch for registry file %s/%s" % (item, target))
                data[item + "/" + target] = blob
        # The CLI writes the map with its keys sorted case-insensitively (assets/... before TEMPLATE.md).
        ordered = {t: digests[t] for t in sorted(digests, key=str.lower)}
        lock = (json.dumps(ordered, indent=2) + "\n").encode("utf-8")
        if sha256_bytes(lock) != pinned[LOCK_FILE]["sha256"]:
            fail("rebuilt %s/%s does not match its pinned sha256" % (item, LOCK_FILE))
        data[item + "/" + LOCK_FILE] = lock
    return data


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

    # 1. Registry items (direct downloads, sha256 checked per file).
    data = fetch_registry(manifest_dir, fetch)  # catalogue-relative path -> bytes

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
