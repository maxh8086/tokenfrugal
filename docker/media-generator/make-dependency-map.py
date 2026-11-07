#!/usr/bin/env python3
"""Generate DEPENDENCY-MAP.md for the media-generator image from the files in this folder.

Reads only local files (Dockerfile, fonts.txt, fonts.lock if present, render-engine/package.json,
render-engine/package-lock.json, catalogue/MANIFEST.json if present). No network, no timestamps,
so the output is byte-identical on every run.

    python3 make-dependency-map.py           # write DEPENDENCY-MAP.md
    python3 make-dependency-map.py --check   # exit 1 if DEPENDENCY-MAP.md is out of date

The script fails (exit 2) if the Dockerfile has an ARG pin that the map would not list, or a
reference repo without a licence entry below, so a new pin cannot slip into the image unrecorded.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "DEPENDENCY-MAP.md")

# Licences of the pinned reference repos. Source: the comment above the reference-repo RUN in the Dockerfile.
# Every fetch_pin line must have an entry here (checked below).
REF_LICENCES = {
    "reelforge": "Apache-2.0",
    "hyperframes-motion-library": "MIT",
    "hyperframes-student-kit": "MIT",
    "product-launch-motion": "MIT",
    "animated-diagrams-skill": "Apache-2.0",
    "design-engineering": "MIT",
}

# Catalogue libraries installed at build time: LIBS.json alias -> the Dockerfile ARG that pins its version.
LIB_ARGS = {
    "gsap": "GSAP_VERSION",
    "three-r181": "THREE_R181_VERSION",
    "three-r184": "THREE_R184_VERSION",
    "d3-delaunay": "D3_DELAUNAY_VERSION",
    "clipper-lib": "CLIPPER_LIB_VERSION",
    "@fontsource/inter": "FONTSOURCE_INTER_VERSION",
    "shaders": "SHADERS_VERSION",
}

# Licence text for global npm packages that are not in a lockfile in this repo.
GLOBAL_NPM_LICENCES = {
    "remotion": "Remotion licence (not recorded in repo; check before commercial use)",
    "@remotion/cli": "Remotion licence (not recorded in repo; check before commercial use)",
    "hyperframes": "Apache-2.0 (per docs/designs/hyperframes-catalog-licences.md)",
}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def md_cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(md_cell(c) for c in row) + " |")
    return "\n".join(out)


def main():
    dockerfile = read("Dockerfile")
    lines = dockerfile.splitlines()

    # Logical RUN instructions: backslash-continued lines joined, with the line each one starts on.
    # Only RUN instructions install things; comments in the Dockerfile mention the same commands.
    runs = []
    cur = None
    for no, line in enumerate(lines, 1):
        if cur is None and line.startswith("RUN "):
            cur = [no, ""]
        if cur is not None:
            piece = line.rstrip()
            cont = piece.endswith("\\")
            cur[1] += " " + (piece[:-1] if cont else piece)
            if not cont:
                runs.append((cur[0], cur[1]))
                cur = None
    run_lines = " ".join(text for _, text in runs)

    errors = []

    # --- ARG pins -------------------------------------------------------------------------
    args = {}  # name -> (value, line number)
    for no, line in enumerate(lines, 1):
        m = re.match(r"^ARG\s+(\w+)=(\S+)\s*$", line)
        if m:
            args[m.group(1)] = (m.group(2), no)

    def arg_value(name):
        if name not in args:
            errors.append("ARG %s is referenced but not declared" % name)
            return "?"
        return args[name][0]

    base = re.search(r"^FROM\s+(\S+)", dockerfile, re.M)
    base_image = base.group(1) if base else "?"

    # --- apt packages ---------------------------------------------------------------------
    apt_rows = []
    for start, text in runs:
        for m in re.finditer(r"apt-get install -y --no-install-recommends\s+([^&;]+)", text):
            for tok in m.group(1).split():
                if tok.startswith(("$", "-", "&")):
                    continue
                apt_rows.append((tok, "Dockerfile line %d" % start))

    # --- fonts (fonts.txt + optional fonts.lock) -------------------------------------------
    font_names = []
    for line in read("fonts.txt").splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            font_names.append(s)
    lock_versions = {}
    lock_path = os.path.join(HERE, "fonts.lock")
    lock_present = os.path.exists(lock_path)
    if lock_present:
        for line in read("fonts.lock").splitlines():
            parts = line.split()
            if len(parts) == 2:
                lock_versions[parts[0]] = parts[1]

    # --- global npm (Dockerfile) ----------------------------------------------------------
    global_npm = []
    for m in re.finditer(r'"(@?[\w./-]+)@\$\{(\w+)\}"', run_lines):
        if "npm install -g" in run_lines[max(0, m.start() - 200): m.start()]:
            global_npm.append((m.group(1), m.group(2)))

    # --- render-engine npm -----------------------------------------------------------------
    pkg = json.loads(read("render-engine/package.json"))
    lock = json.loads(read("render-engine/package-lock.json"))
    lock_pkgs = lock.get("packages", {})
    lock_prod = sum(1 for k, v in lock_pkgs.items() if k and not v.get("dev"))

    def lock_entry(name):
        return lock_pkgs.get("node_modules/" + name, {})

    engine_rows = []
    for name, spec in sorted(pkg.get("dependencies", {}).items()):
        e = lock_entry(name)
        engine_rows.append((name, spec, e.get("version", "not in lock"), e.get("license", "?"), "dependency"))
    for name, spec in sorted(pkg.get("overrides", {}).items()):
        e = lock_entry(name)
        engine_rows.append((name, spec, e.get("version", "not in lock"), e.get("license", "?"), "override"))

    # --- pip -------------------------------------------------------------------------------
    pip_rows = []
    pm = re.search(r"pip3 install[^&]*", run_lines)
    if pm:
        for tok in re.findall(r'"([^"]+)"|(\S+)', pm.group(0)):
            spec = tok[0] or tok[1]
            if spec.startswith(("-", "pip3", "install")) or spec == "--break-system-packages":
                continue
            pinned = "==" in spec
            pip_rows.append((spec, "pinned" if pinned else "NOT pinned (floats to newest)"))

    # --- source builds ---------------------------------------------------------------------
    whisper_tag = re.search(r'git clone --depth 1 --branch "\$\{(\w+)\}" https://github.com/ggml-org/whisper.cpp', run_lines)
    manim = re.search(r'git clone --branch "\$\{(\w+)\}" https://github.com/ManimCommunity/manim', run_lines)
    manim_commit = re.search(r'checkout --detach "\$\{(\w+)\}"', run_lines)
    model = re.search(r"download-ggml-model\.sh \"\$\{(\w+)\}\"", run_lines)

    # --- reference repos -------------------------------------------------------------------
    refs = []
    for m in re.finditer(r'fetch_pin (\S+) (\S+) "\$(\w+)"', run_lines):
        refs.append((m.group(1), m.group(2), m.group(3)))
    for dirname, repo, argname in refs:
        if dirname not in REF_LICENCES:
            errors.append("reference repo %s has no licence entry in make-dependency-map.py" % dirname)

    # --- catalogue (optional, written by the catalogue step) -------------------------------
    catalogue = []
    manifest_path = os.path.join(HERE, "catalogue", "MANIFEST.json")
    if os.path.exists(manifest_path):
        manifest = json.loads(read("catalogue/MANIFEST.json"))
        cat_root = os.path.join(HERE, "catalogue")
        # Loaded external URLs per item, counted with the same scanner the audit uses (no network).
        import importlib.util
        spec = importlib.util.spec_from_file_location("audit_external_urls", os.path.join(cat_root, "audit-external-urls.py"))
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        for name in manifest["items"]:
            files = [e["path"] for e in manifest["files"] if e["path"].startswith(name + "/")]
            loaded, navigation = [], []
            for rel in files:
                if os.path.splitext(rel)[1].lower() in audit.TEXT_EXT:
                    audit.scan_file(os.path.join(cat_root, rel), rel, loaded, navigation)
            catalogue.append({"item": name, "files": len(files),
                              "notice": name + "/NOTICE.md", "loaded_urls": len(loaded)})

    # --- catalogue libraries (LIBS.json; installed by the Dockerfile catalogue RUN) ----------
    lib_rows = []
    libs_path = os.path.join(HERE, "catalogue", "LIBS.json")
    if os.path.exists(libs_path):
        libs = json.loads(read("catalogue/LIBS.json"))
        for alias, info in sorted(libs["packages"].items()):
            version = info["npm"].rsplit("@", 1)[1]
            argname = LIB_ARGS.get(alias)
            if argname is None:
                errors.append("catalogue library %s has no ARG in LIB_ARGS (make-dependency-map.py)" % alias)
                continue
            if argname not in args:
                errors.append("catalogue library %s needs ARG %s in the Dockerfile" % (alias, argname))
                continue
            if args[argname][0] != version:
                errors.append("ARG %s is %s but catalogue/LIBS.json pins %s" % (argname, args[argname][0], version))
            file_count = sum(1 for f in libs["files"] if f["package"] == alias)
            lib_rows.append((alias, info["npm"], argname, info["licence"], file_count))

    # ==== render ===========================================================================
    out = []
    out.append("# Dependency map: media-generator image")
    out.append("")
    out.append("Generated by `docker/media-generator/make-dependency-map.py` from the files in this folder. "
               "Do not edit by hand: change the source file, then run `python3 make-dependency-map.py`. "
               "`--check` exits 1 when this file is out of date. The image copies this file to `/opt/DEPENDENCY-MAP.md`.")
    out.append("")
    out.append("Fixed by the Dockerfile itself: the base image, every `ARG` pin, the npm lockfile and `fonts.txt`. "
               "Versions the build resolves at run time (Debian apt packages, chromium) are marked as such.")
    out.append("")

    out.append("## Base image")
    out.append("")
    out.append(table(["Item", "Pin", "Source"], [("Base image", base_image, "Dockerfile FROM (digest pin)")]))
    out.append("")

    out.append("## ARG pins")
    out.append("")
    out.append("One row per `ARG` in the Dockerfile. Changing a value here means changing the Dockerfile.")
    out.append("")
    arg_rows = [(n, v, "Dockerfile line %d" % ln) for n, (v, ln) in sorted(args.items(), key=lambda kv: kv[1][1])]
    out.append(table(["ARG", "Pinned value", "Where"], arg_rows))
    out.append("")

    out.append("## Global npm (Dockerfile)")
    out.append("")
    out.append("Installed with `npm install -g`. Each version comes from an `ARG`.")
    out.append("")
    out.append(table(["Package", "Version", "ARG", "Licence"],
                     [(n, arg_value(a), a, GLOBAL_NPM_LICENCES.get(n, "not recorded in repo")) for n, a in global_npm]))
    out.append("")

    out.append("## render-engine npm (render-engine/package.json)")
    out.append("")
    out.append("Installed with `npm install --omit=dev` from `render-engine/package-lock.json`. "
               "The lockfile pins %d production packages (direct and transitive) in total. Versions below come from it."
               % lock_prod)
    out.append("")
    out.append(table(["Package", "Declared", "Locked version", "Licence", "Kind"], engine_rows))
    out.append("")

    out.append("## pip (Dockerfile)")
    out.append("")
    out.append(table(["Package", "Pin"], pip_rows))
    out.append("")
    out.append("Installed with `pip3 install --break-system-packages`, so the system Python gets them.")
    out.append("")

    out.append("## Source builds")
    out.append("")
    src_rows = []
    if whisper_tag:
        src_rows.append(("whisper.cpp (whisper-cli)", "tag " + arg_value(whisper_tag.group(1)),
                         "https://github.com/ggml-org/whisper.cpp", "not recorded in repo (check upstream)"))
    if model:
        src_rows.append(("whisper model", arg_value(model.group(1)),
                         "download-ggml-model.sh from the whisper.cpp tag (no checksum pinned)", "not recorded in repo (check upstream)"))
    if manim:
        src_rows.append(("Manim Community", "tag " + arg_value(manim.group(1)),
                         "https://github.com/ManimCommunity/manim", "not recorded in repo (check upstream)"))
    if manim_commit:
        src_rows.append(("Manim Community commit", arg_value(manim_commit.group(1)),
                         "checked out detached after the tag clone", "not recorded in repo (check upstream)"))
    src_rows.append(("Manim Python deps", "floating (venv /opt/manim-venv)", "pip install of /opt/manim, no lockfile", "per package"))
    out.append(table(["Component", "Pin", "Source", "Licence"], src_rows))
    out.append("")
    out.append("Manim is installed in its own venv (`/opt/manim-venv`). Tex and MathTeX need LaTeX, which is not in the image.")
    out.append("")

    if lib_rows:
        out.append("## Catalogue libraries (npm, installed at build time)")
        out.append("")
        out.append("The catalogue `RUN` in the Dockerfile installs each package at the version in its `ARG`. "
                   "`catalogue/install-libs.py` then copies each file listed in `catalogue/LIBS.json` into the catalogue and checks its sha256. "
                   "The build fails on a mismatch.")
        out.append("")
        out.append(table(["Package (alias)", "npm spec", "ARG", "Licence", "Files copied"], lib_rows))
        out.append("")

    out.append("## Browsers")
    out.append("")
    out.append(table(["Component", "Pin", "Source"], [
        ("chromium", "Debian bookworm version at build time (not pinned)", "apt, plus /etc/chromium.d/mgen (--no-sandbox)"),
        ("chrome-headless-shell", "version chosen by hyperframes %s" % arg_value("HYPERFRAMES_VERSION"),
         "`hyperframes browser ensure`, linked to /usr/local/bin/chrome-headless-shell"),
    ]))
    out.append("")

    out.append("## Reference repos (pinned commit SHAs)")
    out.append("")
    ref_rows = []
    for dirname, repo, argname in refs:
        ref_rows.append((dirname, "github.com/" + repo, argname, arg_value(argname), REF_LICENCES.get(dirname, "?")))
    out.append(table(["Directory under /opt/refs", "Repo", "ARG", "Commit", "Licence"], ref_rows))
    out.append("")

    out.append("## apt packages (Dockerfile)")
    out.append("")
    out.append("Debian bookworm main. The version of each package is whatever the build resolves; it is not pinned in this repo.")
    out.append("")
    out.append(table(["Package", "Where"], apt_rows))
    out.append("")

    out.append("## Fonts (fonts.txt)")
    out.append("")
    out.append("%d Debian font packages. Versions come from `fonts.lock`, which the image writes at build time to `/opt/fonts/fonts.lock`."
               % len(font_names))
    out.append("")
    if lock_present:
        font_rows = [(n, lock_versions.get(n, "not in fonts.lock")) for n in font_names]
    else:
        font_rows = [(n, "resolved at build (see /opt/fonts/fonts.lock)") for n in font_names]
    out.append(table(["Package", "Version"], font_rows))
    out.append("")

    out.append("## Tesseract (OCR for burned-in captions)")
    out.append("")
    tess = [r for r in apt_rows if r[0].startswith("tesseract")]
    out.append(table(["Package", "Where"], tess + [("tesseract-ocr-osd", "Debian dependency of tesseract-ocr (not listed in Dockerfile)")]))
    out.append("")

    if catalogue:
        out.append("## Vendored HyperFrames catalogue subset (catalogue/)")
        out.append("")
        out.append("Only the NOTICE-FOUND items from docs/designs/hyperframes-catalog-licences.md. Each item's notices sit next to its files. "
                   "Library files are not vendored: see the catalogue libraries section above.")
        out.append("")
        out.append(table(["Item", "Files", "Notice file", "Loaded external URLs"],
                         [(c["item"], c["files"], c["notice"], c["loaded_urls"]) for c in catalogue]))
        out.append("")

    text = "\n".join(out)

    # Self-check: every ARG line has exactly one row in the ARG table.
    arg_table_rows = sum(1 for r in arg_rows)
    if arg_table_rows != len(args):
        errors.append("ARG table has %d rows, Dockerfile has %d ARG lines" % (arg_table_rows, len(args)))
    for name in args:
        if ("| %s |" % name) not in text:
            errors.append("ARG %s missing from the map" % name)
    if errors:
        for e in errors:
            sys.stderr.write("make-dependency-map: %s\n" % e)
        sys.exit(2)

    if "--check" in sys.argv[1:]:
        current = read("DEPENDENCY-MAP.md") if os.path.exists(OUT) else ""
        if current != text:
            sys.stderr.write("DEPENDENCY-MAP.md is out of date: run python3 make-dependency-map.py\n")
            sys.exit(1)
        print("DEPENDENCY-MAP.md is up to date (%d ARG pins)" % len(args))
        return

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote DEPENDENCY-MAP.md (%d ARG pins, %d apt packages, %d font packages)" % (len(args), len(apt_rows), len(font_names)))


if __name__ == "__main__":
    main()
