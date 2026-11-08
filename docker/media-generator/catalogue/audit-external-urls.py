#!/usr/bin/env python3
"""Audit the HyperFrames catalogue for external resources, without network access.

The catalogue is split in two. Committed files (licences, notices, LIBS.json, scripts) live in this folder. The
composition trees and fonts are not committed: fetch-catalogue.py writes them from the pins in FETCH.json. MANIFEST.json
lists every file of the full catalogue with its sha256 and origin ("committed" or "fetched").

Default run (repo only): scans the committed text files. Fetched files are not on disk, so they are not scanned and
the report says how many were skipped.

    python audit-external-urls.py [catalogue_dir]

Full run: `--tree DIR` scans a complete post-fetch catalogue (committed files plus fetched files, at catalogue-relative
paths) and checks every file's sha256 against MANIFEST.json and, for fetched files, against FETCH.json. The check
of per-item counts (files and loaded URLs in MANIFEST.json "items") is part of this run. `--record` writes the counts
from the tree into MANIFEST.json instead of checking them.

    python audit-external-urls.py --tree <fetched_tree> [--record] [catalogue_dir]

The audit separates two kinds of URL found in the catalogue's files:

* LOADED: a URL the page or its scripts fetch when rendered (src/href of non-link elements, link[href],
  CSS url() and @import, ES import/export specifiers, dynamic import(), importmap values, and fetch/Worker/
  Image/XHR/sendBeacon/.src calls with a literal URL). These must be zero for the offline image.
* INERT: anything else (comments, licence text, SKILL.md documentation, SVG namespaces, <a href> links).
  Reported by host so the reader can see what is left and why it does not load.

It also checks that every relative import in the vendored JavaScript resolves on disk, that each bare specifier has
an importmap entry in the page that loads it, and that MANIFEST.json matches the files.

Exit 0 when there are no loaded external URLs, no unresolved imports and no manifest problems; otherwise 1.
Standard library only.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys

TEXT_EXT = {'.html', '.htm', '.css', '.js', '.mjs', '.md', '.svg', '.json', '.txt'}
URL_RE = re.compile(r'(?:https?:)?//[^\s"\'`)<>,;\\]+')
LOADING_URL = r'((?:https?:)?//[^"\'`)\s]+)'

TAG_RE = re.compile(r'<([a-zA-Z][\w-]*)\b([^>]*)>')
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']')
CSS_URL_RE = re.compile(r'url\(\s*["\']?' + LOADING_URL)
CSS_IMPORT_RE = re.compile(r'@import\s+(?:url\(\s*)?["\']?((?:https?:)?//[^"\'\s)]+)')
JS_FROM_RE = re.compile(r'(?:import|export)\b[^;\n]*?\bfrom\s*["\']([^"\']+)["\']')
JS_BARE_IMPORT_RE = re.compile(r'\bimport\s*\(?\s*["\']([^"\']+)["\']')
JS_CALL_RE = re.compile(r'(?:fetch|importScripts|Worker|Image|WebSocket|XMLHttpRequest|sendBeacon)\s*\(\s*["\'`]((?:https?:)?//[^"\'`]+)')
JS_SRC_ASSIGN_RE = re.compile(r'\.src\s*=\s*["\'`]((?:https?:)?//[^"\'`]+)')
IMPORTMAP_RE = re.compile(r'<script[^>]*type\s*=\s*["\']importmap["\'][^>]*>(.*?)</script>', re.S | re.I)
LOADING_ATTRS = {'src', 'poster', 'data', 'srcset', 'action', 'xlink:href'}
SELF = 'audit-external-urls.py'


def is_external(u):
    return u.startswith('http://') or u.startswith('https://') or u.startswith('//')


def host_of(u):
    m = re.match(r'(?:https?:)?//([^/\s"\'`)]+)', u)
    return m.group(1).lower() if m else u


def scan_file(path, rel, loaded, navigation):
    ext = os.path.splitext(path)[1].lower()
    text = open(path, encoding='utf-8', errors='replace').read()
    if ext in ('.html', '.htm'):
        for m in IMPORTMAP_RE.finditer(text):
            for u in URL_RE.findall(m.group(1)):
                loaded.append((rel, 'importmap', u))
        for tag, attrs in TAG_RE.findall(text):
            tag = tag.lower()
            for name, val in ATTR_RE.findall(attrs):
                name = name.lower()
                if not is_external(val):
                    continue
                if name == 'href' and tag in ('a', 'area'):
                    navigation.append((rel, tag, val))
                elif name == 'href' or name in LOADING_ATTRS:
                    loaded.append((rel, f'<{tag} {name}>', val))
        for u in CSS_URL_RE.findall(text):
            loaded.append((rel, 'css url()', u))
        for u in CSS_IMPORT_RE.findall(text):
            loaded.append((rel, '@import', u))
        scan_js(text, rel, loaded)
    elif ext in ('.css',):
        for u in CSS_URL_RE.findall(text):
            loaded.append((rel, 'css url()', u))
        for u in CSS_IMPORT_RE.findall(text):
            loaded.append((rel, '@import', u))
    elif ext in ('.js', '.mjs'):
        scan_js(text, rel, loaded)


def scan_js(text, rel, loaded):
    for spec in JS_FROM_RE.findall(text) + JS_BARE_IMPORT_RE.findall(text):
        if is_external(spec):
            loaded.append((rel, 'import', spec))
    for u in JS_CALL_RE.findall(text) + JS_SRC_ASSIGN_RE.findall(text):
        loaded.append((rel, 'script call', u))


def build_time_dests(root):
    # Library files listed in LIBS.json are installed by the image at build time, so they are absent from the repo.
    path = os.path.join(root, 'LIBS.json')
    if not os.path.isfile(path):
        return set()
    return {f['dest'] for f in json.load(open(path, encoding='utf-8'))['files']}


def fetched_pins(root):
    """Map each fetched catalogue path to the sha256 that FETCH.json pins for it."""
    path = os.path.join(root, 'FETCH.json')
    if not os.path.isfile(path):
        return {}
    fetch = json.load(open(path, encoding='utf-8'))
    pins = {}
    for item, files in fetch.get('registry', {}).items():
        for rel, v in files.items():
            pins[item + '/' + rel] = v['sha256']
    for p in fetch.get('patches', []):  # a patch replaces the registry bytes, so its sha wins
        pins[p['dest']] = p['sha256']
    for pkg in fetch.get('npm', []):
        for f in pkg['files']:
            pins[f['dest']] = f['sha256']
    for o in fetch.get('overrides', []):
        pins[o['dest']] = o['sha256']
    return pins


def check_imports(root, files, build_time):
    problems = []
    for rel in files:
        if os.path.splitext(rel)[1].lower() not in ('.js', '.mjs'):
            continue
        if '/vendor/' not in '/' + rel:
            continue
        base = os.path.dirname(os.path.join(root, rel))
        text = open(os.path.join(root, rel), encoding='utf-8', errors='replace').read()
        # Drop comment lines so commented-out imports (for example "// import glyf from './tables/glyf'") are ignored.
        text = '\n'.join(line for line in text.split('\n') if not line.lstrip().startswith(('//', '/*', '*')))
        for spec in JS_FROM_RE.findall(text) + JS_BARE_IMPORT_RE.findall(text):
            if spec.startswith('.') or spec.startswith('/'):
                target = os.path.normpath(os.path.join(base, spec.split('?')[0]))
                target_rel = os.path.relpath(target, root).replace(os.sep, '/')
                if not os.path.isfile(target) and target_rel not in build_time:
                    problems.append((rel, spec, 'relative target missing'))
            elif spec not in ('three',) and not spec.startswith('three/addons/'):
                problems.append((rel, spec, 'bare specifier not in the vendored set'))
    return problems


def check_bare_has_importmap(root, files):
    problems = []
    for rel in files:
        if os.path.splitext(rel)[1].lower() not in ('.html', '.htm'):
            continue
        html = open(os.path.join(root, rel), encoding='utf-8', errors='replace').read()
        bare = set()
        for m in re.finditer(r'<script[^>]*type\s*=\s*["\']module["\'][^>]*>(.*?)</script>', html, re.S | re.I):
            bare.update(s for s in JS_FROM_RE.findall(m.group(1)) + JS_BARE_IMPORT_RE.findall(m.group(1)) if not s.startswith('.') and not s.startswith('/') and not is_external(s))
        if bare and not IMPORTMAP_RE.search(html):
            problems.append((rel, sorted(bare), 'bare module specifiers without an importmap'))
    return problems


def sha256_file(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def list_files(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != '__pycache__']
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, '/'))
    return sorted(out)


def check_manifest(root, committed, pins, tree):
    """Return (problems, manifest) for MANIFEST.json against the repo, FETCH.json and (if given) the full tree."""
    path = os.path.join(root, 'MANIFEST.json')
    if not os.path.isfile(path):
        return ['MANIFEST.json missing'], None
    manifest = json.load(open(path, encoding='utf-8'))
    problems = []
    listed = {}
    for e in manifest.get('files', []):
        listed[e['path']] = e
    for p, e in sorted(listed.items()):
        origin = e.get('origin')
        if origin == 'committed':
            full = os.path.join(root, p)
            if not os.path.isfile(full):
                problems.append(f'manifest lists missing committed file {p}')
            elif sha256_file(full) != e['sha256']:
                problems.append(f'sha256 changed {p}')
        elif origin == 'fetched':
            if pins.get(p) != e['sha256']:
                problems.append(f'manifest sha differs from FETCH.json for {p}')
            if os.path.isfile(os.path.join(root, p)):
                problems.append(f'fetched file is also committed {p}')
        else:
            problems.append(f'bad origin {origin!r} for {p}')
    for p in sorted(pins):
        if p not in listed or listed[p].get('origin') != 'fetched':
            problems.append(f'FETCH.json entry not listed as fetched in manifest {p}')
    for rel in committed:
        if rel != 'MANIFEST.json' and (rel not in listed or listed[rel].get('origin') != 'committed'):
            problems.append(f'committed file not in manifest {rel}')
    if tree is not None:
        tree_files = set(list_files(tree)) - {'MANIFEST.json'}
        for p in sorted(set(listed) - tree_files):
            problems.append(f'manifest lists file missing from tree {p}')
        for p in sorted(tree_files - set(listed)):
            problems.append(f'tree file not in manifest {p}')
        for p, e in sorted(listed.items()):
            full = os.path.join(tree, p)
            if p in tree_files and sha256_file(full) != e['sha256']:
                problems.append(f'tree sha256 differs from manifest {p}')
    return problems, manifest


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('catalogue', nargs='?', default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--tree', help='complete post-fetch catalogue to scan (committed plus fetched files)')
    ap.add_argument('--record', action='store_true', help='with --tree: write per-item counts into MANIFEST.json')
    args = ap.parse_args(argv[1:])
    root = os.path.abspath(args.catalogue)
    tree = os.path.abspath(args.tree) if args.tree else None
    if args.record and tree is None:
        ap.error('--record needs --tree')

    committed = [f for f in list_files(root) if f != 'MANIFEST.json']
    pins = fetched_pins(root)
    scan_root = tree or root
    scan_files = [f for f in (list_files(scan_root) if tree else committed)
                  if os.path.splitext(f)[1].lower() in TEXT_EXT and f != SELF and f != 'MANIFEST.json']

    loaded, navigation = [], []
    for rel in scan_files:
        scan_file(os.path.join(scan_root, rel), rel, loaded, navigation)

    inert = collections.Counter()
    loaded_set = {u for _, _, u in loaded}
    for rel in scan_files:
        text = open(os.path.join(scan_root, rel), encoding='utf-8', errors='replace').read()
        for u in URL_RE.findall(text):
            host = host_of(u)
            if u not in loaded_set and re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', host):
                inert[host] += 1

    import_problems = check_imports(scan_root, scan_files, build_time_dests(root))
    bare_problems = check_bare_has_importmap(scan_root, scan_files)
    manifest_problems, manifest = check_manifest(root, committed, pins, tree)

    # Per-item counts: files and loaded URLs, recorded in MANIFEST.json "items" and checked against the tree.
    item_problems = []
    item_counts = {}
    if manifest is not None and tree is not None:
        all_paths = sorted(e['path'] for e in manifest['files'])
        for item in manifest.get('items', []):
            name = item['name']
            n_files = sum(1 for p in all_paths if p.startswith(name + '/'))
            n_loaded = sum(1 for rel, _, _ in loaded if rel.startswith(name + '/'))
            item_counts[name] = (n_files, n_loaded)
            if not args.record and (item.get('files'), item.get('loaded_urls')) != (n_files, n_loaded):
                item_problems.append(f'{name}: MANIFEST records files={item.get("files")} '
                                     f'loaded_urls={item.get("loaded_urls")}, tree has {n_files}/{n_loaded}')
        if args.record:
            for item in manifest.get('items', []):
                item['files'], item['loaded_urls'] = item_counts[item['name']]
            with open(os.path.join(root, 'MANIFEST.json'), 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(manifest, fh, indent=2, sort_keys=True)
                fh.write('\n')
            item_problems = []
            print('MANIFEST.json item counts recorded from the tree')

    print(f'files scanned: {len(scan_files)} ({"tree " + tree if tree else "committed files only"})')
    if tree is None:
        print(f'fetched files not scanned (run with --tree to scan them): {len(pins)}')
    print(f'LOADED external URLs: {len(loaded)}')
    for rel, kind, u in loaded:
        print(f'  {rel} [{kind}] {u}')
    print(f'navigation links (not loaded): {len(navigation)}')
    for rel, tag, u in navigation:
        print(f'  {rel} [{tag}] {u}')
    print('inert URL hosts (comments, licence text, documentation, namespaces):')
    for host, n in sorted(inert.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f'  {host}: {n}')
    print(f'unresolved vendored imports: {len(import_problems)}')
    for rel, spec, why in import_problems:
        print(f'  {rel}: {spec} ({why})')
    print(f'bare specifier problems: {len(bare_problems)}')
    for rel, specs, why in bare_problems:
        print(f'  {rel}: {specs} ({why})')
    print(f'manifest problems: {len(manifest_problems)}')
    for p in manifest_problems:
        print(f'  {p}')
    print(f'item count problems: {len(item_problems)}')
    for p in item_problems:
        print(f'  {p}')

    ok = not loaded and not import_problems and not bare_problems and not manifest_problems and not item_problems
    print('RESULT: ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
